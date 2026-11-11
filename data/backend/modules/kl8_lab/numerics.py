# -*- coding: utf-8 -*-
"""数值稳健性工具（§3.6）。

全部模块必须使用本文件的工具函数，不得直接做除法/取对数，
否则退化输入（某号从未开出、单期历史、空集合）会产生 nan/inf。
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

EPS = 1e-12
GEO_EPS = 1e-3          # §4.14 几何平均的 epsilon
MIN_SAMPLE = 30         # §3.6 样本量下限


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    """分母为 0 或过小时返回 default，绝不产生 nan/inf。"""
    if b is None or not _is_finite(b) or abs(b) < EPS:
        return default
    out = a / b
    return out if _is_finite(out) else default


def safe_log(x: float, default: float = 0.0) -> float:
    """x <= 0 时返回 default（该号跳过该子项）。"""
    if x is None or not _is_finite(x) or x <= 0:
        return default
    return math.log(x)


def _is_finite(x) -> bool:
    # 热路径：回测中调用量在千万级，用一次算术代替 math.isfinite 调用。
    # 有限值满足 v - v == 0；inf/inf 得 nan、nan 得 nan，均不满足。
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False
    return v - v == 0.0


def finite(x, default: float = 0.0) -> float:
    """把 nan/inf/None 统一压成 default（只做一次类型转换）。"""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if v - v == 0.0 else default


def clip01(x: float) -> float:
    return min(1.0, max(0.0, finite(x, 0.0)))


def clip(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, finite(x, lo)))


def rank_normalize(values: Sequence[float]) -> list[float]:
    """秩归一：并列取平均秩，线性映射到 [0, 1]。

    n == 1 → [0.5]；全部相等 → 全 0.5（平均秩落在中点）。
    选 rank 而非 min-max 的理由见 §5.2：z_score / Weibull 危险率 / 邻居数
    都是无界量且对极端值敏感，rank 归一对其天然稳健。
    """
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [0.5]

    vals = [finite(v, 0.0) for v in values]
    order = sorted(range(n), key=lambda i: vals[i])

    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0          # 0-based 平均秩
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1

    return [r / (n - 1) for r in ranks]


def minmax_normalize(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    vals = [finite(v, 0.0) for v in values]
    lo, hi = min(vals), max(vals)
    if hi - lo < EPS:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def sigmoid_normalize(values: Sequence[float]) -> list[float]:
    """以中位数为中心、稳健尺度做 sigmoid 压缩。"""
    if not values:
        return []
    vals = [finite(v, 0.0) for v in values]
    med = median(vals)
    mad = median([abs(v - med) for v in vals])
    scale = mad * 1.4826 if mad > EPS else 1.0
    return [1.0 / (1.0 + math.exp(-clip((v - med) / scale, -30, 30))) for v in vals]


def normalize(values: Sequence[float], method: str = "rank") -> list[float]:
    """统一归一化入口，方法由 config.thresholds.norm_method 决定。"""
    if method == "rank":
        return rank_normalize(values)
    if method == "minmax":
        return minmax_normalize(values)
    if method == "sigmoid":
        return sigmoid_normalize(values)
    raise ValueError(f"未知归一化方法: {method}")


def median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    s = sorted(finite(v, 0.0) for v in values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def mean(values: Sequence[float]) -> float:
    vals = [finite(v, 0.0) for v in values]
    return sum(vals) / len(vals) if vals else 0.0


def stdev(values: Sequence[float], ddof: int = 1) -> float:
    vals = [finite(v, 0.0) for v in values]
    n = len(vals)
    if n - ddof <= 0:
        return 0.0
    m = sum(vals) / n
    var = sum((v - m) ** 2 for v in vals) / (n - ddof)
    return math.sqrt(var) if var > 0 else 0.0


def geo_mean(a: float, b: float, eps: float = GEO_EPS) -> float:
    """几何平均（§4.14）。ε 落在乘积内，避免任一子项为 0 时整体归零。

    `sqrt(a·b + ε²)`：geo(0,0)=ε≠0，geo(1,1)=1，其余情形 ≈ sqrt(a·b)。
    """
    a = clip01(a)
    b = clip01(b)
    return clip01(math.sqrt(a * b + eps * eps))


def entropy_normalized(counts: Iterable[float]) -> float:
    """归一化 Shannon 熵 ∈ [0, 1]（§4.12）。

    均匀分布 → 1；全部集中在一个类别 → 0。
    """
    vals = [max(0.0, finite(c, 0.0)) for c in counts]
    total = sum(vals)
    if total <= EPS:
        return 0.0
    k = len(vals)
    if k <= 1:
        return 0.0
    h = 0.0
    for v in vals:
        if v <= 0:
            continue
        p = v / total
        h -= p * math.log(p)
    return clip01(h / math.log(k))


def theoretical_std(T: int, p: float = 0.25) -> float:
    """理论二项标准差 √(T·p·(1−p))（§2.5）。

    必须用理论值而非跨号经验标准差：实测 2063 期里各号出现次数集中在
    0.25T 附近，跨号经验 std 趋近 0，z_score 会爆炸。
    """
    if T <= 0:
        return 0.0
    return math.sqrt(T * p * (1.0 - p))


def hypergeom_mean(n_draw: int = 5, N: int = 80, K: int = 20) -> float:
    """超几何期望命中数 E[H] = n·K/N。默认取 5 号 → 1.25。"""
    return n_draw * K / N


def hypergeom_var(n_draw: int = 5, N: int = 80, K: int = 20) -> float:
    """超几何方差（§9.6）。注意不是二项方差 n·p·(1−p)。

    Var = n·(K/N)·(1−K/N)·(N−n)/(N−1)
    """
    if N <= 1:
        return 0.0
    p = K / N
    return n_draw * p * (1 - p) * (N - n_draw) / (N - 1)


def hypergeom_sf(k: int, n_draw: int, N: int, K: int) -> float:
    """P(X >= k)，超几何右尾。用于逐期命中数的显著性。"""
    from scipy.stats import hypergeom
    if k <= 0:
        return 1.0
    return float(hypergeom.sf(k - 1, N, K, n_draw))


def fisher_or_skip(table: list[list[int]], min_expected: float = 5.0):
    """卡方期望频数不足时改用 Fisher 精确检验（§3.6）。

    返回 (统计量, p值, 方法名)。2x2 才支持 Fisher，其余降级为 None。
    """
    from scipy.stats import chi2_contingency, fisher_exact
    arr = [list(map(float, row)) for row in table]
    if sum(sum(row) for row in arr) <= 0:            # 全零表：期望频数无定义
        return None, None, "degenerate"
    try:
        chi2, p, _, expected = chi2_contingency(arr, correction=False)
    except ValueError:
        return None, None, "degenerate"
    if expected.min() >= min_expected:
        return float(chi2), float(p), "chi2"
    if len(arr) == 2 and len(arr[0]) == 2:
        _, p_f = fisher_exact(arr)
        return None, float(p_f), "fisher"
    return None, None, "skipped"


def bh_fdr(pvalues: Sequence[float], q: float = 0.05) -> tuple[list[float], list[bool]]:
    """Benjamini–Hochberg FDR 校正（§9.6）。

    返回 (每个假设的 q 值, 是否拒绝)。q 值单调化以保证可解释性。
    """
    m = len(pvalues)
    if m == 0:
        return [], []
    ps = [clip01(finite(p, 1.0)) for p in pvalues]
    order = sorted(range(m), key=lambda i: ps[i])
    qvals = [1.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        val = ps[idx] * m / rank
        prev = min(prev, val)
        qvals[idx] = clip01(prev)
    return qvals, [qv < q for qv in qvals]


def bonferroni(pvalues: Sequence[float], alpha: float = 0.05) -> tuple[list[float], list[bool]]:
    """Bonferroni 校正：控制族错误率。"""
    m = len(pvalues)
    if m == 0:
        return [], []
    adj = [clip01(finite(p, 1.0) * m) for p in pvalues]
    return adj, [a < alpha for a in adj]


def wilson_lower(hits: int, trials: int, z: float = 1.96) -> float:
    """Wilson 单侧置信下界，用于比例类指标的稳健区间。

    退化输入（hits<0 / hits>trials / trials<=0）一律夹取，不抛异常（§3.6）。
    """
    trials = int(trials)
    if trials <= 0:
        return 0.0
    hits = min(max(int(hits), 0), trials)
    p = hits / trials
    denom = 1 + z * z / trials
    centre = p + z * z / (2 * trials)
    margin = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    return clip01((centre - margin) / denom)


def min_detectable_lift(T: int, n_draw: int = 5, power_z: float = 0.8416,
                        alpha_z: float = 1.6449) -> float:
    """最小可检测 lift（§9.7）。

    MDE_lift = (z_alpha + z_power) · SE / E[H]
    默认单侧 α=0.05、功效 80%。
    """
    if T <= 1:
        return float("inf")
    sd = math.sqrt(hypergeom_var(n_draw))
    se = sd / math.sqrt(T)
    e_h = hypergeom_mean(n_draw)
    if e_h <= EPS:
        return float("inf")
    return (alpha_z + power_z) * se / e_h
