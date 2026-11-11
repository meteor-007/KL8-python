# -*- coding: utf-8 -*-
"""熵值评估与分布均衡度监控（§4.12）→ H7 熵/均衡。

**v1.0 的硬错误**：定义 p_i = freq_i / 20。但 freq_i 是全样本出现次数，
总和 Σfreq = 20T，于是 Σp = 20T/20 = T ≠ 1 —— 根本不是概率分布。
实测 H_num = −Σp ln p < 0、H* < 0，与"H* ∈ [0,1]"直接矛盾。

**v2.0 修正**：p_i = freq_i / Σ_j freq_j（等价于 freq_i / (20T)），
H_num = −Σ p_i ln p_i，H* = H_num / ln 80 ∈ [0,1]（均匀分布 → 1）。
本模块用 numerics.entropy_normalized 计算，天然落在 [0,1]。

四个子模块：
  1. 号码熵   全样本 1–80 出现次数分布的归一化香农熵 H*
  2. 场域熵   8 段场域（每段 10 号，§4.3）命中分布的归一化熵，衡量场域均衡
  3. 滑动熵   30 期滑窗熵序列 + 时序波动；用 config.entropy_low_quantile
              （默认 10% 分位）判定"低熵异常有序期"
  4. KL 散度  近期分布 vs 全样本分布，异常大则告警

打分（§4.12 第 5 条）：熵偏低（有序）时，集中于少数场域的号更可能延续；
熵偏高（均衡）时转向回补冷号。二者按 regime 权重平滑混合。

**无前视**：draws 由调用方裁剪到目标期之前（最新在前），本模块只读 draws。
scores 覆盖全 80 号；expanded_set 不用于限制计算范围（§3.5）。
"""
from __future__ import annotations

import math

from .contracts import ModuleResult
from .data_io import Draw
from .numerics import (EPS, MIN_SAMPLE, clip01, entropy_normalized, finite,
                       rank_normalize, safe_div, safe_log, stdev,
                       theoretical_std)
from .points import NumberStats

NUM_BALLS = 80
N_ZONES = 8
ZONE_SIZE = 10
WINDOW = 30                 # 滑动熵滑窗长度（§4.12 第 3 条）
P_HIT = 20.0 / 80.0


# ── 小工具 ────────────────────────────────────────────────────

def _zone_of(n: int) -> int:
    """号码 → 场域下标 0..7（[1-10],[11-20],…,[71-80]，§4.3）。"""
    return (n - 1) // ZONE_SIZE


def _quantile(values: list[float], q: float) -> float:
    """线性插值分位数（空序列返回 0.0），全部走 finite 清洗。"""
    vals = sorted(finite(v, 0.0) for v in values)
    if not vals:
        return 0.0
    if len(vals) == 1:
        return vals[0]
    q = min(1.0, max(0.0, finite(q, 0.0)))
    pos = q * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def _counts(draws_sub: list[Draw]) -> list[int]:
    """1..80 出现次数（下标 0 不用）。"""
    c = [0] * (NUM_BALLS + 1)
    for d in draws_sub:
        for x in d.numbers:
            if 1 <= x <= NUM_BALLS:
                c[x] += 1
    return c


def _prefix_counts(draws: list[Draw]) -> list[list[int]]:
    """前缀计数：P[i] = draws[:i] 的 1..80 计数（P[0] 全 0，下标 0 不用）。

    滑窗计数是 O(窗口长 × 20)，而滑窗序列要枚举 T−win+1 个窗口；
    用前缀和把每次查询降到 O(80)，实测是本模块最大热点。
    """
    cur = [0] * (NUM_BALLS + 1)
    P = [list(cur)]
    for d in draws:
        for x in d.numbers:
            if 1 <= x <= NUM_BALLS:
                cur[x] += 1
        P.append(list(cur))
    return P


def _window_counts(P: list[list[int]], start: int, win: int) -> list[int]:
    """由前缀和取 draws[start:start+win] 的计数（O(80)）。"""
    a, b = P[start], P[start + win]
    return [b[k] - a[k] for k in range(NUM_BALLS + 1)]


def _zone_counts(freq: list[int]) -> list[int]:
    """把号码计数归并到 8 段场域。"""
    z = [0] * N_ZONES
    for n in range(1, NUM_BALLS + 1):
        z[_zone_of(n)] += freq[n]
    return z


def _kl(short_counts: list[int], long_counts: list[int]) -> float:
    """KL(短期 ‖ 长期)，拉普拉斯平滑避免 q=0 导致对数发散。"""
    s = sum(short_counts[1:])
    l = sum(long_counts[1:])
    if s <= 0 or l <= 0:
        return 0.0
    out = 0.0
    for n in range(1, NUM_BALLS + 1):
        p = (short_counts[n] + 1.0) / (s + float(NUM_BALLS))
        q = (long_counts[n] + 1.0) / (l + float(NUM_BALLS))
        # 拉普拉斯平滑保证 p,q > 0，此处直接用 math 即可（等价于 safe_*，去掉热路径函数调用）
        out += p * math.log(p / q)
    return max(0.0, finite(out, 0.0))


def _cfg_threshold(cfg, name: str, default: float) -> float:
    """从 cfg.thresholds 取阈值，缺键/异常一律回退默认值。"""
    try:
        val = getattr(cfg.thresholds, name, None)
    except Exception:
        val = None
    return default if val is None else finite(val, default)


# ── 主入口 ────────────────────────────────────────────────────

def analyze(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg) -> ModuleResult:
    """熵值评估与分布均衡度监控（§4.12）。draws 最新在前、已裁剪到目标期之前。"""
    res = ModuleResult(name="entropy", scores={})
    T = len(draws)

    if T < MIN_SAMPLE:
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期")
        res.add("risk", f"- 熵值评估：历史仅 {T} 期，样本不足，已跳过。", order=40)
        return res

    P = _prefix_counts(draws)
    freq = _counts(draws)                       # 全样本 1..80 出现次数

    # ① 号码熵 H*（均匀 → 1）
    h_star = entropy_normalized(freq[1:])
    h_num = h_star * math.log(NUM_BALLS)

    # ② 场域熵：8 段命中分布的均衡度
    zc = _zone_counts(freq)
    zone_entropy = entropy_normalized(zc)
    total_hits = sum(zc)
    zone_share = [safe_div(c, total_hits, 0.0) for c in zc]   # 1/8 为均衡基准

    # ③ 滑动熵：30 期滑窗熵序列
    win = min(WINDOW, T)
    h_series = [entropy_normalized(_window_counts(P, i, win)[1:])
                for i in range(0, T - win + 1)]
    h_short = h_series[0]                        # draws[0:win] = 最近 win 期
    h_long = h_star
    h_std = stdev(h_series)

    q_low = _cfg_threshold(cfg, "entropy_low_quantile", 0.10)
    q_low = min(0.5, max(0.0, q_low))
    h_threshold = _quantile(h_series, q_low)

    # regime：r=1 → 低熵（有序，延续逻辑）；r=0 → 高熵（均衡，回补逻辑）
    r = 0.5
    if len(h_series) >= 5 and (max(h_series) - min(h_series)) > EPS:
        pct = sum(1 for h in h_series if h <= h_short) / len(h_series)
        r = clip01((q_low - pct) / max(q_low, 0.01))
    low_entropy_alert = bool(h_short < h_threshold) and len(h_series) >= 5

    # ④ KL 散度：近期窗口分布 vs 全样本分布
    kl = _kl(_window_counts(P, 0, win), freq)
    kl_series = [_kl(_window_counts(P, i, win), freq)
                 for i in range(0, T - win + 1)]
    kl_hi = _quantile(kl_series, 1.0 - q_low)    # 高尾分位（默认 90%）
    kl_alert = bool(kl > kl_hi) and len(kl_series) >= 5

    # ⑤ 打分：延续（热号 + 热场域）与回补（冷号 + 冷场域）按 regime 混合
    ns = list(range(1, NUM_BALLS + 1))
    std = theoretical_std(T, P_HIT)
    exp_hit = T * P_HIT
    z = [safe_div(freq[n] - exp_hit, std, 0.0) for n in ns]

    z_hot = rank_normalize(z)
    z_cold = rank_normalize([-v for v in z])

    zone_bias = [zone_share[_zone_of(n)] - 1.0 / N_ZONES for n in ns]
    zone_hot = rank_normalize(zone_bias)
    zone_cold = rank_normalize([-v for v in zone_bias])

    cont = {n: clip01(0.5 * z_hot[i] + 0.5 * zone_hot[i])
            for i, n in enumerate(ns)}
    reb = {n: clip01(0.5 * z_cold[i] + 0.5 * zone_cold[i])
           for i, n in enumerate(ns)}
    scores = {n: clip01(r * cont[n] + (1.0 - r) * reb[n]) for n in ns}
    res.scores = scores

    # ── 指标 ──
    top_cont = sorted(ns, key=lambda n: (-cont[n], n))[:5]
    top_reb = sorted(ns, key=lambda n: (-reb[n], n))[:5]
    never_drawn = sum(1 for n in ns if freq[n] == 0)
    hottest_zone = max(range(N_ZONES), key=lambda i: zone_share[i])

    res.metrics = {
        "T": T,
        "window": win,
        "H_num": round(h_num, 4),
        "H_star": round(h_star, 5),
        "zone_entropy": round(zone_entropy, 5),
        "h_short": round(h_short, 5),
        "h_long": round(h_long, 5),
        "h_series_std": round(h_std, 5),
        "entropy_low_quantile": round(q_low, 4),
        "entropy_low_threshold": round(h_threshold, 5),
        "regime_continuation_weight": round(r, 4),
        "regime": ("有序/延续" if r >= 0.5 else "均衡/回补") if len(h_series) >= 5 else "中性",
        "kl_divergence": round(kl, 5),
        "kl_alert_threshold": round(kl_hi, 5),
        "low_entropy_alert": int(low_entropy_alert),
        "kl_alert": int(kl_alert),
        "zone_share": [round(v, 4) for v in zone_share],
        "hottest_zone": f"[{hottest_zone * ZONE_SIZE + 1}-{(hottest_zone + 1) * ZONE_SIZE}]",
        "never_drawn_numbers": never_drawn,
        "top_continuation": top_cont,
        "top_rebound": top_reb,
        "expanded_size": len(expanded_set or ()),
        "sub_scores": {
            "continuation": {n: round(cont[n], 4) for n in ns},
            "rebound": {n: round(reb[n], 4) for n in ns},
        },
    }
    res.diagnostics = {
        "T": T,
        "entropy_series_len": len(h_series),
        "numbers_never_drawn": never_drawn,
        "base_stats_provided": bool(base_stats),
    }

    # ── narrative ──
    res.add("macro",
            f"- **号码熵**：H* = {h_star:.4f}（H_num = {h_num:.3f}，满分 ln80 ≈ "
            f"{math.log(NUM_BALLS):.3f}），全样本 80 号出现分布"
            f"{'接近均匀' if h_star > 0.99 else '略偏集中'}。", order=20)
    res.add("macro",
            f"- **场域均衡**：8 段场域熵 = {zone_entropy:.4f}，偏热段 "
            f"{res.metrics['hottest_zone']}（份额 {zone_share[hottest_zone]:.3f}，"
            f"均衡基准 0.125）。", order=21)
    res.add("macro",
            f"- **熵的时序**：30 期滑窗熵 当前 {h_short:.4f} / 长期 {h_long:.4f}，"
            f"波动 σ = {h_std:.4f}；低熵阈值（{q_low:.0%} 分位）= {h_threshold:.4f}，"
            f"当前处于「{res.metrics['regime']}」档（延续权重 {r:.2f}）。", order=22)

    if low_entropy_alert:
        res.add("risk",
                f"- 熵值告警：最近 {win} 期熵 {h_short:.4f} 低于 {q_low:.0%} 分位阈值 "
                f"{h_threshold:.4f}，属**低熵异常有序期**，号码集中于少数场域，"
                f"延续逻辑加权至 {r:.2f}。", order=41)
    if kl_alert:
        res.add("risk",
                f"- 分布漂移告警：近期分布 vs 全样本 KL = {kl:.4f}，"
                f"超过 {1 - q_low:.0%} 分位阈值 {kl_hi:.4f}，分布结构发生异常偏移。",
                order=42)
    if never_drawn:
        res.add("risk",
                f"- 熵值评估：{never_drawn} 个号码在全样本中从未开出，其 p_i = 0 "
                f"对熵无贡献，已按 §3.6 跳过。", order=43)

    return res
