# -*- coding: utf-8 -*-
"""底座：遗漏分析（§6.1）→ H2 遗漏反弹。

三部分：
  1. 连失追踪表 —— 每号当前连失 m、历史连失分布、中位/最大连失
  2. Weibull 危险率 —— 对历史连失长度拟合 weibull_min，h(m) = (k/λ)(m/λ)^(k−1)
     拟合失败（样本 < 30 或不收敛）→ 回退经验危险率 h(m) = 命中数/暴露期数
  3. Z 反弹分 —— z = (m − μ_miss)/σ_miss，μ/σ 来自该号**连失长度**的分布
     （注意与 §2.5 的 std 不同：那是出现次数的二项分布）

omission_z_rebound 同时导出给 §4.4 反向博弈门控使用。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .contracts import ModuleResult
from .data_io import Draw
from .numerics import (EPS, MIN_SAMPLE, clip01, finite, geo_mean, mean,
                       normalize, rank_normalize, safe_div, stdev)
from .points import NumberStats

WEIBULL_MIN_SAMPLES = 30


@dataclass
class OmissionProfile:
    """单号的连失画像。"""
    n: int
    current_miss: int
    gaps: list[int] = field(default_factory=list)     # 历史完整连失长度（两次命中之间）
    hazard: float = 0.0
    z_rebound: float = 0.0
    k: float = 0.0
    lam: float = 1.0
    fitted: bool = False


def _gap_series(draws_newest_first: list[Draw], n: int) -> tuple[int, list[int]]:
    """返回 (当前连失, 历史完整连失长度列表)。

    draws 最新在前，索引 0 为最近一期。
    索引 i 与 i+1 两次命中之间的空档长度 = 相邻命中索引之差 − 1。
    """
    hits = [i for i, d in enumerate(draws_newest_first) if n in d.numbers_set]
    if not hits:
        return len(draws_newest_first), []
    current = hits[0]
    gaps = [hits[i + 1] - hits[i] - 1 for i in range(len(hits) - 1)]
    return current, gaps


def _fit_weibull(gaps: list[int]) -> tuple[float, float, bool]:
    """拟合 weibull_min，返回 (k, λ, 是否成功)。

    连失长度含 0（连续两期命中），Weibull 定义域为 x >= 0，
    scipy 的 weibull_min 在 x=0 处密度可能为 inf；这里加 1 平移到
    「连失长度 + 1」上拟合，保持形状参数可比且避开退化点。
    """
    if len(gaps) < WEIBULL_MIN_SAMPLES:
        return 0.0, 1.0, False
    shifted = np.asarray([g + 1.0 for g in gaps], dtype=float)
    if shifted.std() < EPS:
        return 0.0, 1.0, False
    try:
        from scipy.stats import weibull_min
        k, loc, lam = weibull_min.fit(shifted, floc=0)
        if not (math.isfinite(k) and math.isfinite(lam)) or k <= 0 or lam <= 0:
            return 0.0, 1.0, False
        return float(k), float(lam), True
    except Exception:
        return 0.0, 1.0, False


def _hazard(k: float, lam: float, m: float) -> float:
    """Weibull 危险率 h(m) = (k/λ)·(m/λ)^(k−1)。"""
    if k <= 0 or lam <= 0:
        return 0.0
    m_eff = max(m, 1.0)
    try:
        return float((k / lam) * (m_eff / lam) ** (k - 1.0))
    except (OverflowError, ValueError):
        return 0.0


def _empirical_hazard(gaps: list[int], T: int, m: float) -> float:
    """经验危险率回退：命中次数 / 暴露期数。"""
    if T <= 0:
        return 0.0
    hits = len(gaps) + 1 if gaps else 0
    return clip01(safe_div(hits, T, 0.0) * max(m, 1.0))


def profile_number(draws: list[Draw], n: int) -> OmissionProfile:
    current, gaps = _gap_series(draws, n)
    T = len(draws)
    if not gaps:
        return OmissionProfile(n=n, current_miss=current, gaps=[], hazard=0.0,
                               z_rebound=0.0, fitted=False)

    k, lam, ok = _fit_weibull(gaps)
    if ok:
        haz = _hazard(k, lam, current)
    else:
        haz = _empirical_hazard(gaps, T, current)

    mu = mean(gaps)
    sd = stdev(gaps)
    z = safe_div(current - mu, sd, 0.0)

    return OmissionProfile(n=n, current_miss=current, gaps=gaps, hazard=haz,
                           z_rebound=finite(z, 0.0), k=k, lam=lam, fitted=ok)


def analyze_omission(draws: list[Draw],
                     expanded_set: set[int],
                     base_stats: dict[int, NumberStats] | None = None,
                     cfg=None) -> tuple[ModuleResult, dict[int, float]]:
    """遗漏分析。返回 (ModuleResult → H2, omission_z_rebound 供 §4.4 门控)。

    draws 必须最新在前，且已裁剪到目标期之前（无前视）。
    """
    res = ModuleResult(name="omission", scores={})
    T = len(draws)

    if T < MIN_SAMPLE:
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期")
        res.add("risk", f"- 遗漏分析：历史仅 {T} 期，数据不足，已跳过。")
        return res, {n: 0.0 for n in range(1, 81)}

    profiles = {n: profile_number(draws, n) for n in range(1, 81)}

    usable = [p for p in profiles.values() if p.gaps]
    fitted_ratio = safe_div(sum(1 for p in usable if p.fitted), len(usable), 0.0)
    if not usable:
        res.degrade("所有号码均无历史连失样本")
        res.add("risk", "- 遗漏分析：无可用连失样本，已跳过。")
        return res, {n: 0.0 for n in range(1, 81)}

    # ── 两个子项各自 rank 归一后等权合成 ──
    ns = list(range(1, 81))
    haz_norm = rank_normalize([profiles[n].hazard for n in ns])
    z_norm = rank_normalize([profiles[n].z_rebound for n in ns])

    scores = {n: clip01(0.5 * haz_norm[i] + 0.5 * z_norm[i])
              for i, n in enumerate(ns)}
    res.scores = scores

    # ── 统计口径：当前连失最大的若干号 ──
    top_miss = sorted(ns, key=lambda n: -profiles[n].current_miss)[:5]
    top_rebound = sorted(ns, key=lambda n: -profiles[n].z_rebound)[:5]

    res.metrics = {
        "T": T,
        "weibull_fit_ratio": round(fitted_ratio, 3),
        "top_miss": [(n, profiles[n].current_miss) for n in top_miss],
        "top_rebound": [(n, round(profiles[n].z_rebound, 2)) for n in top_rebound],
        "median_miss": round(mean([len(p.gaps) and mean(p.gaps) or 0
                                   for p in usable]), 2),
    }
    res.diagnostics = {
        "n_numbers_with_gaps": len(usable),
        "weibull_fitted": sum(1 for p in usable if p.fitted),
        "empirical_fallback": sum(1 for p in usable if not p.fitted),
    }

    # 拟合失败的号占比过半 → 本模块结论降级但不归零（危险率仍由经验回退给出）
    if fitted_ratio < 0.5:
        res.sufficient = False
        res.diagnostics["degraded"] = (
            f"仅 {fitted_ratio:.0%} 的号码 Weibull 拟合成功，其余用经验危险率回退")

    res.add("macro",
            f"- **遗漏结构**：当前连失最久的号码为 "
            f"{'、'.join(f'{n:02d}({profiles[n].current_miss}期)' for n in top_miss)}。",
            order=20)
    res.add("macro",
            f"- **反弹压力**（连失偏离自身历史均值）："
            f"{'、'.join(f'{n:02d}(z={profiles[n].z_rebound:+.2f})' for n in top_rebound)}。",
            order=21)
    if fitted_ratio < 1.0:
        res.add("risk",
                f"- 遗漏分析：{1 - fitted_ratio:.0%} 的号码 Weibull 拟合样本不足，"
                f"已回退到经验危险率。", order=40)

    z_rebound = {n: finite(profiles[n].z_rebound, 0.0) for n in ns}
    return res, z_rebound
