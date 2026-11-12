# -*- coding: utf-8 -*-
"""§4.2 周期性共振与波段节奏 Cyclic Patterns（`cyclic.py`）→ H4。

流程（严格对齐规格 §4.2）：
  1. 每号建 0/1 时序 ``x_n[t]``（1 = 该期开出），时序按**旧 → 新**排列；
  2. **前置白噪声检验**：Ljung-Box（lag=20，α = ``cfg.thresholds.cyclic_alpha``）。
     未通过者（p > α）直接判定"无周期结构"，``T_n = None``，**不进入后续步骤**；
  3. **自相关** ``acf_n(k)``，k = 1..20；显著性做**多重比较校正**
     （``cfg.thresholds.cyclic_correction`` ∈ {bonferroni, fdr_bh}，族 α = cyclic_alpha）；
  4. **周期估计**：校正后仍显著的 lag 中取**最高峰**作为 ``T_n``，无显著峰则 None；
  5. **波段节奏**：连续 1 的游程长度分布 vs 几何分布（i.i.d. 零假设）的卡方拟合优度；
  6. **共振群**：仅对 ``T_n ≠ None`` 的号码按 ``T_n`` 聚类（多个号共享同一周期）；
  7. **打分**：处于共振群 + 当前相位接近峰值。相位 ``phase_n = (t mod T_n) / T_n``，
     仅对 ``T_n ≠ None`` 的号有效。

> **实现注记（与规格的偏差，已记录于 diagnostics）**：规格写"用
> ``scipy.stats.ljungbox``"，但本环境 scipy 1.17.1 **并无该函数**，
> statsmodels 亦未安装（禁止新增依赖）。故按标准公式自实现 Ljung-Box：
> ``Q = T(T+2)·Σ_{k=1..h} r_k²/(T−k) ~ χ²(h)``，p 值由 ``scipy.stats.chi2.sf`` 给出，
> 与 scipy/ statsmodels 实现等价；ACF 与 Ljung-Box 共用同一批 ``r_k``。

无前视：只使用传入的 ``draws``（调用方已裁剪到目标期之前）。
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np

from .contracts import ModuleResult
from .data_io import Draw
from .numerics import (EPS, MIN_SAMPLE, bh_fdr, bonferroni, clip01, finite,
                       mean, normalize, rank_normalize, safe_div)
from .points import NumberStats

LAGS = 20                     # ACF / Ljung-Box 的最大滞后（§4.2）
P_HIT = 0.25                  # i.i.d. 零假设下单号单期命中概率 = 20/80
W_RESONANCE = 0.5             # 共振群规模子项权重
W_PHASE = 0.5                 # 相位接近峰值子项权重
MIN_RUNS = 8                  # 游程拟合优度所需的最少游程数


# ── 配置读取（Section 缺键返回 None，这里统一兜底）────────────────

def _thr(cfg, key: str, default):
    try:
        v = getattr(cfg.thresholds, key)
    except Exception:
        return default
    return default if v is None else v


def _alpha(cfg) -> float:
    a = _thr(cfg, "cyclic_alpha", None)
    if a is None:
        a = _thr(cfg, "alpha", 0.05)
    try:
        return float(a)
    except (TypeError, ValueError):
        return 0.05


def _correction(cfg) -> str:
    c = str(_thr(cfg, "cyclic_correction", "bonferroni") or "bonferroni").lower()
    return c if c in ("bonferroni", "fdr_bh", "fdr", "bh") else "bonferroni"


def _norm_method(cfg) -> str:
    m = _thr(cfg, "norm_method", "rank")
    return str(m) if m else "rank"


# ── 单号画像 ──────────────────────────────────────────────────

@dataclass
class CyclicProfile:
    """单号的周期画像。"""
    n: int
    T: int = 0                      # 序列长度
    hits: int = 0
    constant: bool = False          # 全 0 / 全 1，无结构
    lb_stat: float = 0.0
    lb_p: float = 1.0
    white_noise_pass: bool = False  # 是否通过前置 Ljung-Box（p <= alpha）
    acf: tuple[float, ...] = ()     # r_1..r_20
    period: int | None = None       # T_n
    acf_peak: float = 0.0           # 显著 lag 中的最高峰 |r|
    phase: float = 0.0              # (t mod T_n)/T_n，t = 下一期索引
    prox: float = 0.0               # 相位接近峰值度量 ∈ [0,1]
    run_p: float | None = None      # 游程拟合优度 p 值
    over_clustered: bool = False
    group_size: int = 1             # 共振群规模
    score_raw: float = 0.0


# ── 基础算子 ──────────────────────────────────────────────────

def _series(draws: list[Draw], n: int) -> np.ndarray:
    """0/1 时序，**旧 → 新**（draws 传入时最新在前，此处反转）。"""
    return np.fromiter((1.0 if n in d.numbers_set else 0.0
                        for d in reversed(draws)),
                       dtype=float, count=len(draws))


def _acf_and_lb(x: np.ndarray, h: int) -> tuple[list[float], float, float]:
    """返回 (r_1..r_h, Ljung-Box Q, p)。

    r_k = Σ_t (x[t]−x̄)(x[t−k]−x̄) / Σ_t (x[t]−x̄)²（§4.2 的定义）。
    Q = T(T+2)·Σ_k r_k²/(T−k)，H0 下 ~ χ²(h)。

    常数序列（方差 0）返回 ([], 0.0, 1.0)。
    """
    T = int(x.size)
    xm = x - x.mean()
    denom = float(np.dot(xm, xm))
    if T <= h or denom <= EPS:
        return [], 0.0, 1.0
    r = [float(np.dot(xm[k:], xm[:-k])) / denom for k in range(1, h + 1)]
    q = 0.0
    for k in range(1, h + 1):
        rk = finite(r[k - 1], 0.0)
        q += safe_div(rk * rk, float(T - k), 0.0)
    q *= T * (T + 2)
    try:
        from scipy.stats import chi2
        p = float(chi2.sf(q, h)) if q > 0 else 1.0
    except Exception:
        p = 1.0
    return r, finite(q, 0.0), clip01(finite(p, 1.0))


def _acf_pvalues(acf: list[float], T: int) -> list[float]:
    """白噪声下 r_k ≈ N(0, 1/T)，双侧 p 值（用于多重比较校正）。"""
    try:
        from scipy.stats import norm
        se = math.sqrt(T) if T > 0 else 0.0
        return [float(2.0 * norm.sf(abs(finite(r, 0.0)) * se)) if se > 0 else 1.0
                for r in acf]
    except Exception:
        return [1.0] * len(acf)


def _run_gof(x: np.ndarray, p0: float = P_HIT,
             min_runs: int = MIN_RUNS) -> tuple[float | None, bool]:
    """连续 1 的游程长度分布 vs 几何分布 Geometric(p0) 的卡方拟合优度。

    i.i.d. 零假设下 P(L=ℓ) = (1−p0)·p0^(ℓ−1)。两端补 0 使每个 1 游程都被 0 终止。
    期望频数 < 5 的箱按"最小期望优先"向相邻箱合并；不足 2 箱则跳过（§3.6）。
    返回 (p 值或 None, 是否过度聚集)。
    """
    padded = np.concatenate((np.zeros(1), x, np.zeros(1)))
    runs: list[int] = []
    cur = 0
    for v in padded:
        if v >= 0.5:
            cur += 1
        else:
            if cur > 0:
                runs.append(cur)
            cur = 0
    N = len(runs)
    if N < min_runs:
        return None, False

    maxlen = max(runs)
    obs = Counter(runs)

    def exp_l(L: int) -> float:
        return N * (1.0 - p0) * (p0 ** (L - 1))

    # 每项：(代表值, 观测, 期望)；箱按代表值升序、且相邻
    items = [(L, obs.get(L, 0), exp_l(L)) for L in range(1, maxlen + 1)]
    while len(items) > 2:
        i = min(range(len(items)), key=lambda j: items[j][2])
        if items[i][2] >= 5.0:
            break
        if i == 0:
            k = 1
        elif i == len(items) - 1:
            k = i - 1
        else:
            k = i - 1 if items[i - 1][2] <= items[i + 1][2] else i + 1
        lo, hi = min(i, k), max(i, k)
        merged = (items[lo][0], items[lo][1] + items[hi][1],
                  items[lo][2] + items[hi][2])
        items = items[:lo] + [merged] + items[hi + 1:]

    df = len(items) - 1
    if df < 1:
        return None, False
    chi2_stat = 0.0
    for _, o, e in items:
        if e > EPS:
            chi2_stat += (o - e) ** 2 / e
    try:
        from scipy.stats import chi2
        p = float(chi2.sf(chi2_stat, df))
    except Exception:
        return None, False
    p = clip01(finite(p, 1.0))
    obs_mean = mean([float(r) for r in runs])
    theo_mean = safe_div(1.0, 1.0 - p0, 0.0)
    over = bool(p < 0.05 and obs_mean > theo_mean)
    return p, over


# ── 主入口 ────────────────────────────────────────────────────

def analyze(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg) -> ModuleResult:
    """周期性共振分析（§4.2，签名严格遵循 §3.5）。"""
    res = ModuleResult(name="cyclic", scores={})
    alpha = _alpha(cfg)
    correction = _correction(cfg)
    norm_method = _norm_method(cfg)
    T = len(draws)

    if T < MIN_SAMPLE:
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期")
        res.add("risk", f"- 周期性共振：历史仅 {T} 期，样本不足，已跳过（权重按 0 处理）。")
        return res

    ns = list(range(1, 81))
    profiles: dict[int, CyclicProfile] = {}

    for n in ns:
        x = _series(draws, n)
        hits = int(x.sum())
        p = CyclicProfile(n=n, T=T, hits=hits)
        if hits == 0 or hits == T:
            p.constant = True
            profiles[n] = p
            continue

        acf, q, lbp = _acf_and_lb(x, LAGS)
        p.acf = tuple(acf)
        p.lb_stat = q
        p.lb_p = lbp
        p.white_noise_pass = bool(lbp <= alpha)

        if not p.white_noise_pass or not acf:
            # 未通过白噪声检验 → 无周期结构，不进入后续步骤
            profiles[n] = p
            continue

        # ── 多重比较校正（§4.2 步骤 3）──
        pvals = _acf_pvalues(acf, T)
        if correction in ("fdr_bh", "fdr", "bh"):
            _adj, rej = bh_fdr(pvals, q=alpha)
        else:
            _adj, rej = bonferroni(pvals, alpha=alpha)

        cands = [k for k in range(LAGS) if rej[k]]
        if cands:
            peak_k = max(cands, key=lambda k: abs(finite(acf[k], 0.0)))
            p.period = peak_k + 1                       # lag = k+1
            p.acf_peak = abs(finite(acf[peak_k], 0.0))

        # ── 波段节奏（§4.2 步骤 5）──
        p.run_p, p.over_clustered = _run_gof(x, P_HIT)
        profiles[n] = p

    # ── 共振群（§4.2 步骤 6）：仅对 T_n ≠ None 的号按 T_n 聚类 ──
    with_period = [n for n in ns if profiles[n].period is not None]
    period_counts = Counter(profiles[n].period for n in with_period)
    max_group = max(period_counts.values()) if period_counts else 0
    t_next = T                                     # 下一期索引（相位预测对象）
    for n in with_period:
        pr = profiles[n]
        pr.group_size = period_counts[pr.period]
        phase = safe_div(float(t_next % pr.period), float(pr.period), 0.0)
        pr.phase = clip01(phase)
        pr.prox = clip01(0.5 * (1.0 + math.cos(2.0 * math.pi * pr.phase)))

    # ── 打分（§4.2 步骤 7）──
    n_pass = sum(1 for n in ns if profiles[n].white_noise_pass)
    for n in with_period:
        pr = profiles[n]
        res_comp = safe_div(float(pr.group_size), float(max_group), 0.0)
        pr.score_raw = clip01(W_RESONANCE * res_comp + W_PHASE * pr.prox)

    scores: dict[int, float] = {n: 0.0 for n in ns}
    if with_period:
        raw_sub = [profiles[n].score_raw for n in with_period]
        try:
            norm_sub = normalize(raw_sub, norm_method)
        except Exception:
            norm_sub = rank_normalize(raw_sub)
        for i, n in enumerate(with_period):
            scores[n] = clip01(norm_sub[i])
    res.scores = scores

    # ── 指标与诊断 ──
    top_cyc = sorted(with_period,
                     key=lambda n: (-scores[n], n))[:5]
    top_groups = period_counts.most_common(5)
    over_clustered = [n for n in ns if profiles[n].over_clustered]

    res.metrics = {
        "T": T,
        "alpha": alpha,
        "correction": correction,
        "n_white_noise_pass": n_pass,
        "white_noise_pass_rate": round(safe_div(n_pass, 80, 0.0), 3),
        "n_with_period": len(with_period),
        "period_histogram": {int(k): int(v) for k, v in sorted(period_counts.items())},
        "top_resonance_groups": [(int(k), int(v)) for k, v in top_groups],
        "top_cyclic": [(n, profiles[n].period, round(profiles[n].phase, 2),
                        round(profiles[n].prox, 2), round(scores[n], 3))
                       for n in top_cyc],
        "n_over_clustered": len(over_clustered),
        "over_clustered": over_clustered[:10],
    }
    res.diagnostics = {
        "n_constant_series": sum(1 for n in ns if profiles[n].constant),
        "n_lb_computed": sum(1 for n in ns if profiles[n].acf),
        "lb_lag": LAGS,
        "lb_method": "self-implemented (scipy.stats.ljungbox 不可用)",
        "expanded_set_size": len(expanded_set or ()),
        "norm_method": norm_method,
        "score_scope": "全 1–80 号；仅对通过白噪声检验的号给非零分",
    }

    # ── narrative（数值全部取自上方 metrics）──
    if n_pass == 0:
        res.add("risk",
                f"- **周期性共振**：80 个号在滞后 {LAGS} 的 Ljung-Box 检验"
                f"（α={alpha:g}）下**无一通过白噪声检验，不构成周期证据**，"
                f"本模块全部得分置 0。", order=50)
    elif not with_period:
        res.add("risk",
                f"- **周期性共振**：仅 {n_pass}/80 个号通过 {LAGS} 阶 Ljung-Box 检验，"
                f"且无号在 **{correction}** 校正后仍有显著 ACF 峰——"
                f"**未通过白噪声检验，不构成周期证据**，本模块全部得分置 0。",
                order=50)
    else:
        dom = "、".join(f"T={k}({v}号)" for k, v in top_groups) or "无显著共振群"
        res.add("macro",
                f"- **周期结构**：{T} 期历史中 {n_pass}/80 个号通过 Ljung-Box"
                f"（lag={LAGS}, α={alpha:g}）白噪声检验，其中 {len(with_period)} 个"
                f"检出经 **{correction}** 校正后仍显著的 ACF 峰。", order=10)
        res.add("macro",
                f"- **共振群**：按周期聚类，主导周期为 {dom}，最大共振群 "
                f"{max_group} 个号。", order=11)
        if top_cyc:
            ex = "、".join(f"{n:02d}(T={profiles[n].period},"
                           f"相位={profiles[n].phase:.2f},"
                           f"峰位={profiles[n].prox:.2f})"
                           for n in top_cyc[:3])
            res.add("macro",
                    f"- **相位预警**：{ex} 当前相位接近周期峰值，共振分最高。",
                    order=12)
        if n_pass < 8:
            res.add("risk",
                    f"- 仅 {n_pass}/80 个号通过白噪声检验，周期证据薄弱，"
                    f"H4 中本模块贡献有限。", order=51)
    if over_clustered:
        res.add("risk",
                f"- **波段过度聚集**：{len(over_clustered)} 个号（如 "
                f"{'、'.join(f'{n:02d}' for n in over_clustered[:5])}）的连续开出游程"
                f"显著长于几何分布，存在聚集而非独立。", order=52)

    return res
