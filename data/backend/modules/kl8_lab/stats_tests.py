# -*- coding: utf-8 -*-
"""显著性检验、多重比较校正与功效分析（§9.5–§9.7）。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .numerics import (EPS, bh_fdr, bonferroni, hypergeom_mean,
                       hypergeom_var, min_detectable_lift, safe_div)

E_HITS = hypergeom_mean(5)     # 1.25，5 号对 20 个开奖号的命中期望
SD_HITS = math.sqrt(hypergeom_var(5))


@dataclass
class TestResult:
    label: str
    T: int
    mean_hits: float
    expected: float
    lift: float
    se: float
    z: float
    p_value: float
    q_value: float = 1.0
    significant: bool = False
    verdict: str = ""
    mde_lift: float = 0.0

    def render(self) -> str:
        return (f"{self.label}: T={self.T} 均值={self.mean_hits:.4f} "
                f"lift={self.lift:.4f} z={self.z:+.3f} p={self.p_value:.4f} "
                f"q={self.q_value:.4f} → {self.verdict}")


def _verdict(lift: float, q: float, alpha: float) -> str:
    """§9.7 的三档判定。禁止把"未达显著"包装成"接近有效"。"""
    if q < alpha and lift >= 1.0:
        return "统计显著"
    if lift >= 1.0:
        return "未达显著"
    return "劣于随机"


def evaluate(series: list[float], label: str = "", alpha: float = 0.05,
             expected: float = E_HITS) -> TestResult:
    """对逐期命中数序列做单样本 z 检验（H0: 均值 = expected）。

    用超几何方差而非二项方差（§9.6）。
    """
    T = len(series)
    if T == 0:
        return TestResult(label=label, T=0, mean_hits=0.0, expected=expected,
                          lift=0.0, se=0.0, z=0.0, p_value=1.0,
                          verdict="无样本", mde_lift=float("inf"))

    mean_hits = sum(series) / T
    se = SD_HITS / math.sqrt(T)
    z = safe_div(mean_hits - expected, se, 0.0)

    try:
        from scipy.stats import norm
        p = float(norm.sf(z))          # 单侧
    except Exception:
        p = 1.0 if z <= 0 else 0.0

    lift = safe_div(mean_hits, expected, 0.0)

    # 逐期命中数是离散的，n=5 时正态近似在单期不可靠；T 期均值靠 CLT，
    # 这里额外要求 T 足够，否则不宣称显著。
    if T < 30:
        p = max(p, 0.5)

    # 单次检验：以自身 p 判定。多重比较场景由 evaluate_methods 用校正后的 q 覆盖。
    return TestResult(
        label=label, T=T, mean_hits=mean_hits, expected=expected, lift=lift,
        se=se, z=z, p_value=p, q_value=p, significant=(p < alpha),
        mde_lift=min_detectable_lift(T), verdict=_verdict(lift, p, alpha),
    )


def evaluate_methods(per_method_hits: dict[str, list[float]],
                     alpha: float = 0.05,
                     method: str = "bh") -> dict[str, TestResult]:
    """对 11 个方法各自检验，并做**多重比较校正**（§9.6）。

    不做校正时，完全无效的系统上期望仍有 11 × 0.05 ≈ 0.55 个方法"显著"。
    """
    results = {m: evaluate(s, label=m, alpha=alpha) for m, s in per_method_hits.items()}
    names = list(results)
    if not names:
        return results

    pvals = [results[m].p_value for m in names]
    if method == "bonferroni":
        adj, rejects = bonferroni(pvals, alpha)
    else:
        adj, rejects = bh_fdr(pvals, alpha)

    for i, m in enumerate(names):
        results[m].q_value = adj[i]
        results[m].significant = rejects[i]
        results[m].verdict = _verdict(results[m].lift, adj[i], alpha)

    return results


def all_insignificant(results: dict[str, TestResult]) -> bool:
    """§9.8 退化分支的触发条件。"""
    if not results:
        return True
    return all(not r.significant for r in results.values())


def evaluate_variable(hits: list[float], sizes: list[int],
                      label: str = "", alpha: float = 0.05) -> TestResult:
    """每期抽取个数不同的情形（如拓展集合大小逐期变化）。

    残差 r_i = hits_i − n_i·K/N，Var[r_i] = hypergeom_var(n_i)。
    统计量 z = Σr_i / √ΣVar_i，在 H0 下服从标准正态。
    """
    T = len(hits)
    if T == 0 or T != len(sizes):
        return TestResult(label=label, T=0, mean_hits=0.0, expected=0.0,
                          lift=0.0, se=0.0, z=0.0, p_value=1.0,
                          verdict="无样本", mde_lift=float("inf"))

    exp_total = sum(n * 20.0 / 80.0 for n in sizes)
    var_total = sum(hypergeom_var(n) for n in sizes)
    resid = sum(hits) - exp_total
    z = safe_div(resid, math.sqrt(var_total) if var_total > EPS else 0.0, 0.0)

    try:
        from scipy.stats import norm
        p = float(norm.sf(z))
    except Exception:
        p = 1.0 if z <= 0 else 0.0
    if T < 30:
        p = max(p, 0.5)

    mean_hits = sum(hits) / T
    mean_expected = exp_total / T
    lift = safe_div(mean_hits, mean_expected, 0.0)
    mean_n = sum(sizes) / T
    mde = min_detectable_lift(T, n_draw=max(1, round(mean_n)))

    return TestResult(
        label=label, T=T, mean_hits=mean_hits, expected=mean_expected,
        lift=lift, se=math.sqrt(var_total) / T, z=z, p_value=p, q_value=p,
        significant=(p < alpha), mde_lift=mde,
        verdict=_verdict(lift, p, alpha),
    )


# ── 功效分析（§9.7）───────────────────────────────────────────

def power_table(windows: tuple[int, ...] = (277, 120, 60)) -> list[dict]:
    """最小可检测效果表（80% 功效、单侧 α=0.05）。"""
    rows = []
    for T in windows:
        mde = min_detectable_lift(T)
        se = SD_HITS / math.sqrt(T) if T > 0 else float("inf")
        rows.append({
            "T": T,
            "se": se,
            "mde_hits": E_HITS * (1 + mde),
            "mde_lift_pct": mde * 100.0,
        })
    return rows


def render_power_table(windows: tuple[int, ...] = (277, 120, 60)) -> str:
    rows = power_table(windows)
    lines = ["| 回测窗口 | T | SE | 最小可检测 mean_hits | 最小可检测 lift |",
             "|---|---|---|---|---|"]
    labels = {277: "全档案", 120: "近 120 期", 60: "近 60 期"}
    for r in rows:
        lines.append(f"| {labels.get(r['T'], '')} | {r['T']} | {r['se']:.4f} | "
                     f"{r['mde_hits']:.3f} | **+{r['mde_lift_pct']:.1f}%** |")
    return "\n".join(lines)


def min_detectable_lift_of(T: int) -> float:
    return min_detectable_lift(T)


# ── lift 置信区间 ─────────────────────────────────────────────

def lift_ci(series: list[float], expected: float = E_HITS,
            z: float = 1.96) -> tuple[float, float]:
    """lift 的近似 95% 置信区间。"""
    T = len(series)
    if T == 0 or expected <= EPS:
        return (0.0, float("inf"))
    mean_hits = sum(series) / T
    se = SD_HITS / math.sqrt(T)
    lo = safe_div(mean_hits - z * se, expected, 0.0)
    hi = safe_div(mean_hits + z * se, expected, 0.0)
    return (lo, hi)
