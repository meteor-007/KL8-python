# -*- coding: utf-8 -*-
"""⑪ 余数空间映射 + 周期共振（§4.11）→ H7（均衡子项）、H3（余数团块子项）。

把 1–80 号按 ``n mod m`` 映射到余数环，检测余数类的命中断层，并把
"严重失衡且历史回补快"的余数类中的号码加分。

v2.0 的两处修正（§4.11）：
  1. **期望按桶大小算**：m ∈ {8,10,12,13} 时 80 不一定被 m 整除
     （m=12 桶大小 6/7，m=13 桶大小 6/7），单期期望不是 20/m 而是
     ``E_r = size(r) × 20/80 = size(r)/4``。用 20/m 会把"桶更大"误判为超命中。
  2. **桶定义唯一**：``r = n mod m``，80 → 0（m=8 时 80 mod 8 = 0），
     绝不引入余数 m 这个越界桶。

统计量（§4.11 第 3 条）::

    z_r = (obs_r − N·E_r) / √( N · E_r · (1 − size(r)/80) )

其中 ``obs_r`` 为 N 期该余数类的总命中数。分母为 §4.11 给定的方差口径。

打分（§4.11 第 5 条）：落在"严重欠命中余数类"（>``remainder_z_alert``）
且该类历史回补快的号码加分。另导出两个子项供融合层使用：
  * ``clump_scores``   —— 余数团块强度 |z_r|（H3 余数团块子项）
  * ``balance_scores`` —— 欠命中回补强度 max(0, −z_r)（H7 均衡子项）

无前视：只使用传入的 draws（调用方已裁剪到目标期之前）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .contracts import ModuleResult
from .data_io import Draw, NUM_BALLS
from .numerics import (EPS, MIN_SAMPLE, clip01, finite, normalize,
                       safe_div)
from .points import NumberStats

# §4.11 修正 1：只取这 4 个模数
MODS: tuple[int, ...] = (8, 10, 12, 13)
ALERT_DEFAULT = 2.0            # cfg.thresholds.remainder_z_alert 的兜底


@dataclass
class ResidueClass:
    """单个余数类的失衡画像。"""
    m: int
    r: int
    numbers: list[int] = field(default_factory=list)
    size: int = 0
    exp_period: float = 0.0     # 单期期望 E_r = size/4
    obs: int = 0                # N 期总命中
    z: float = 0.0              # 失衡统计量
    rebound: float = 0.0        # 历史回补速度 ∈ [0,1]
    run_sign: int = 0           # 最新一期相对期望方向：+1 超 / −1 欠 / 0 平
    run_len: int = 0            # 连续同向期数（周期共振长度）
    under: bool = False         # 是否当前处于欠命中

    @property
    def severe_under(self) -> float:
        """超出告警阈值的欠命中深度（0 表示未达阈值）。"""
        return max(0.0, -self.z) if self.z < 0 else 0.0


# ── 公共辅助（便于单测复用） ────────────────────────────────────

def residue_buckets(m: int) -> dict[int, list[int]]:
    """余数桶：``r -> [n ∈ 1..80 : n mod m = r]``（80 → 0，不引入余数 m）。"""
    buckets: dict[int, list[int]] = {r: [] for r in range(m)}
    for n in range(1, NUM_BALLS + 1):
        buckets[n % m].append(n)
    return buckets


def expected_hits(N: int, size_r: int) -> float:
    """N 期该余数类的期望命中数：``E_r·N = N·size(r)/4``（§4.11 修正 1）。"""
    return N * (size_r / 4.0)


def _th(cfg, key: str, default):
    """从 cfg.thresholds 取阈值，缺键/缺 cfg 时兜底。"""
    th = getattr(cfg, "thresholds", None) if cfg is not None else None
    if th is None:
        return default
    val = getattr(th, key, None)
    return default if val is None else val


def _two_sided_p(z: float) -> float:
    """正态双侧 p 值 = erfc(|z|/√2)，避免 nan/inf。"""
    return clip01(math.erfc(abs(finite(z, 0.0)) / math.sqrt(2.0)))


def _class_series(draws: list[Draw], m: int) -> dict[int, list[int]]:
    """逐期余数类命中数，**最新在前**（与 draws 顺序一致）。"""
    series: dict[int, list[int]] = {r: [] for r in range(m)}
    for d in draws:
        cnt = [0] * m
        for n in d.numbers:
            cnt[n % m] += 1
        for r in range(m):
            series[r].append(cnt[r])
    return series


def _rebound_speed(crono: list[int], exp_period: float) -> float:
    """历史回补速度：欠命中期之后**下一期即回到期望以上**的比例。

    crono 为按时间升序（旧→新）的逐期命中数。无欠命中样本时取中性 0.5。
    """
    under_followed = 0
    rebounded = 0
    for t in range(len(crono) - 1):
        if crono[t] < exp_period:
            under_followed += 1
            if crono[t + 1] >= exp_period:
                rebounded += 1
    return clip01(safe_div(rebounded, under_followed, 0.5))


def _run(draws_newest_first: list[int], exp_period: float) -> tuple[int, int]:
    """最新起算的连续同向游程，返回 (方向, 长度)。方向 +1 超 / −1 欠 / 0 平。"""
    if not draws_newest_first:
        return 0, 0
    head = draws_newest_first[0]
    if head > exp_period:
        sign = 1
    elif head < exp_period:
        sign = -1
    else:
        return 0, 0
    length = 0
    for v in draws_newest_first:
        if sign > 0 and v > exp_period:
            length += 1
        elif sign < 0 and v < exp_period:
            length += 1
        else:
            break
    return sign, length


# ── 主入口 ─────────────────────────────────────────────────────

def analyze(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg) -> ModuleResult:
    """余数空间映射 + 周期共振（§4.11）。

    draws 必须**最新在前**、已裁剪到目标期之前（无前视）。对全 1–80 号打分，
    ``expanded_set`` 不用于限制计算范围（§3.5）。
    """
    res = ModuleResult(name="remainder", scores={})
    T = len(draws)

    # 样本不足：§3.6。余数失衡是聚合量，期数太少时 z 无意义 → 降级归零。
    if T < MIN_SAMPLE:
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期，余数失衡统计不可靠")
        res.metrics = {"T": T}
        res.add("risk",
                f"- **余数空间**：历史仅 {T} 期（< {MIN_SAMPLE}），"
                f"样本不足以估计余数失衡，本模块已跳过。", order=41)
        return res

    alert = float(_th(cfg, "remainder_z_alert", ALERT_DEFAULT))
    norm_method = _th(cfg, "norm_method", "rank")
    alpha = float(_th(cfg, "alpha", 0.05))

    zmap: dict[int, dict[int, float]] = {}
    rmap: dict[int, dict[int, float]] = {}
    classes_by_mod: dict[int, list[ResidueClass]] = {}

    for m in MODS:
        buckets = residue_buckets(m)
        series = _class_series(draws, m)
        cls_list: list[ResidueClass] = []
        for r in range(m):
            size = len(buckets[r])
            exp_period = size / 4.0
            obs = sum(series[r])
            exp_total = expected_hits(T, size)
            var = T * exp_period * (1.0 - size / float(NUM_BALLS))
            sd = math.sqrt(var) if var > EPS else 0.0
            z = safe_div(obs - exp_total, sd, 0.0)          # §4.11 第 3 条
            rebound = _rebound_speed(list(reversed(series[r])), exp_period)
            sign, rlen = _run(series[r], exp_period)
            cls_list.append(ResidueClass(
                m=m, r=r, numbers=list(buckets[r]), size=size,
                exp_period=exp_period, obs=obs, z=finite(z, 0.0),
                rebound=rebound, run_sign=sign, run_len=rlen,
                under=(z < 0)))
        classes_by_mod[m] = cls_list
        zmap[m] = {c.r: c.z for c in cls_list}
        rmap[m] = {c.r: c.rebound for c in cls_list}

    # ── 逐号原始量：三个子项 ──
    nums = list(range(1, NUM_BALLS + 1))
    gate_raw: list[float] = []      # §4.11 第 5 条：严重欠命中 × 回补速度
    cont_raw: list[float] = []      # H7 均衡子项：连续欠命中回补强度
    clump_raw: list[float] = []     # H3 余数团块子项：|z_r| 强度
    nm = float(len(MODS))
    for n in nums:
        g = c = k = 0.0
        for m in MODS:
            r = n % m
            z = zmap[m][r]
            g += max(0.0, -z - alert) * rmap[m][r]
            c += max(0.0, -z)
            k += abs(z)
        gate_raw.append(g / nm)
        cont_raw.append(c / nm)
        clump_raw.append(k / nm)

    # 主分：优先用 §4.11 第 5 条的阈值门控项；若无任何余数类越过告警阈值，
    # 退化为连续欠命中强度（方向一致，保证仍然有区分度），并在 diagnostics 标注。
    if max(gate_raw) > EPS:
        primary, primary_mode = gate_raw, "gated_rebound"
    else:
        primary, primary_mode = cont_raw, "fallback_continuous_underhit"

    scores_primary = normalize(primary, norm_method)
    scores_balance = normalize(cont_raw, norm_method)
    scores_clump = normalize(clump_raw, norm_method)
    scores = {n: clip01(scores_primary[i]) for i, n in enumerate(nums)}
    res.scores = scores

    balance_scores = {n: clip01(scores_balance[i]) for i, n in enumerate(nums)}
    clump_scores = {n: clip01(scores_clump[i]) for i, n in enumerate(nums)}

    # ── 显著性诊断：逐余数类双侧 z 检验 + BH 多重校正 ──
    pvals: list[float] = []
    alert_classes: list[tuple[int, int, float]] = []
    for m in MODS:
        for c in classes_by_mod[m]:
            pvals.append(_two_sided_p(c.z))
            if abs(c.z) > alert:
                alert_classes.append((m, c.r, round(c.z, 2)))
    from .numerics import bh_fdr
    _, rejects = bh_fdr(pvals, q=alpha)
    n_reject = int(sum(1 for x in rejects if x))

    # ── metrics ──
    mod_summary: dict[str, dict] = {}
    for m in MODS:
        cs = classes_by_mod[m]
        worst = max(cs, key=lambda c: abs(c.z))
        mod_summary[f"m{m}"] = {
            "sizes": [c.size for c in cs],
            "exp_period": [round(c.exp_period, 3) for c in cs],
            "z": [round(c.z, 2) for c in cs],
            "max_abs_z": (worst.r, round(worst.z, 2)),
            "alert": [(c.r, round(c.z, 2)) for c in cs if abs(c.z) > alert],
        }
    # primary 的下标 i 对应号码 i+1
    top_rebound = sorted(nums, key=lambda n: -primary[n - 1])[:10]

    res.metrics = {
        "T": T,
        "mods": list(MODS),
        "alert_threshold": alert,
        "primary_mode": primary_mode,
        "mod_summary": mod_summary,
        "alert_classes": alert_classes,
        "clump_scores": clump_scores,      # H3 余数团块子项
        "balance_scores": balance_scores,  # H7 均衡子项
    }
    res.diagnostics = {
        "n_classes_tested": len(pvals),
        "n_significant_after_fdr": n_reject,
        "fdr_q": alpha,
        "min_p": round(min(pvals), 5) if pvals else 1.0,
        "n_alert_classes": len(alert_classes),
        "primary_mode": primary_mode,
        "sub_items": ["clump_scores", "balance_scores"],
    }

    # ── narrative（真实数值） ──
    m_ref = 12
    cs_ref = classes_by_mod[m_ref]
    worst_ref = max(cs_ref, key=lambda c: abs(c.z))
    pos = [(c.r, c.z) for c in cs_ref if c.z > 0]
    neg = [(c.r, c.z) for c in cs_ref if c.z < 0]
    res.add("macro",
            f"- **余数失衡**（mod {m_ref}，桶大小 "
            f"{'/'.join(str(c.size) for c in cs_ref)}）：最强偏离为余数 "
            f"{worst_ref.r} 类，z={worst_ref.z:+.2f}。"
            f"超命中余数类 "
            f"{'、'.join(f'{r}(z={z:+.2f})' for r, z in pos) or '无'}；"
            f"欠命中余数类 "
            f"{'、'.join(f'{r}(z={z:+.2f})' for r, z in neg) or '无'}。",
            order=30)
    res.add("macro",
            f"- **余数回补/团块**：共 {len(alert_classes)} 个余数类越过告警阈值 "
            f"|z|>{alert}；主分口径为 {primary_mode}，"
            f"逐号回补分最高的号码为 "
            f"{'、'.join(f'{n:02d}' for n in top_rebound[:5])}。",
            order=31)
    if n_reject == 0:
        res.add("risk",
                f"- **余数空间**：{len(pvals)} 个余数类经 BH-FDR 校正后无显著失衡"
                f"（最小 p={min(pvals) if pvals else 1.0:.4f}），"
                f"余数结构当前接近均匀，相关分数仅供弱参考。", order=42)
    else:
        res.add("risk",
                f"- **余数空间**：{n_reject}/{len(pvals)} 个余数类经 BH-FDR 校正后显著失衡，"
                f"需警惕余数结构（如 mod 12 余数 {worst_ref.r} 类）的持续偏移。",
                order=42)

    return res
