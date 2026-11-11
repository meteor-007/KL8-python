# -*- coding: utf-8 -*-
"""struct_* 系列脚本的共享统计/绘图工具。

约束：只读依赖 common.py，不修改 common.py 与项目其它文件。
所有随机过程使用固定种子，脚本可重复运行。
"""
from __future__ import annotations

import math
import os
from functools import lru_cache

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402
    HAS_MATPLOTLIB = True
except ImportError:
    matplotlib = None
    plt = None
    HAS_MATPLOTLIB = False

HERE = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.join(HERE, "figs")

# 中文字体候选（先探测再启用，避免方块乱码）
_CN_FONTS = ["Microsoft YaHei", "SimHei", "Noto Sans SC", "DengXian", "SimSun"]

N_BALLS = 80
M_DRAW = 20


# ───────────────────────────── 绘图环境 ─────────────────────────────
def setup_matplotlib(dpi: int = 150):
    """探测中文字体并设置 rcParams，返回实际启用的字体列表。"""
    if not HAS_MATPLOTLIB or plt is None:
        return ["no_matplotlib"]
    from matplotlib import font_manager as fm

    avail = {f.name for f in fm.fontManager.ttflist}
    picked = [f for f in _CN_FONTS if f in avail]
    if not picked:
        picked = ["sans-serif"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = picked + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120
    plt.rcParams["savefig.dpi"] = dpi
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.25
    os.makedirs(FIGS, exist_ok=True)
    return picked


def save_fig(fig, name: str) -> str:
    if not HAS_MATPLOTLIB or plt is None or fig is None:
        return ""
    os.makedirs(FIGS, exist_ok=True)
    path = os.path.join(FIGS, name)
    fig.savefig(path, dpi=plt.rcParams["savefig.dpi"], bbox_inches="tight")
    plt.close(fig)
    return path


# ───────────────────────────── 组合数学 ─────────────────────────────
@lru_cache(maxsize=None)
def _C(n: int, k: int) -> int:
    if k < 0 or n < 0 or k > n:
        return 0
    return math.comb(n, k)


def order_stat_pmf(k: int, N: int = N_BALLS, m: int = M_DRAW) -> list[float]:
    """升序第 k 位的精确分布 P(X_(k)=x)，索引 i 对应 x=i+1。"""
    tot = _C(N, m)
    return [_C(x - 1, k - 1) * _C(N - x, m - k) / tot for x in range(1, N + 1)]


def order_stat_cdf(k: int, x: int, N: int = N_BALLS, m: int = M_DRAW) -> float:
    """P(X_(k) <= x)（精确超几何和）。"""
    tot = _C(N, m)
    s = sum(_C(x, j) * _C(N - x, m - j) for j in range(k, m + 1))
    return s / tot


def order_stat_moments(k: int, N: int = N_BALLS, m: int = M_DRAW):
    """有限总体顺序统计量的精确均值/标准差（不放回抽样）。"""
    mean = k * (N + 1) / (m + 1)
    var = k * (m + 1 - k) * (N + 1) * (N - m) / ((m + 1) ** 2 * (m + 2))
    return mean, math.sqrt(var)


def hyper_pmf(N: int, K: int, n: int) -> dict[int, float]:
    """超几何分布 P(c)=C(K,c)C(N-K,n-c)/C(N,n)，返回 {c: p}。"""
    tot = _C(N, n)
    lo = max(0, n - (N - K))
    hi = min(n, K)
    return {c: _C(K, c) * _C(N - K, n - c) / tot for c in range(lo, hi + 1)}


def subset_sum_pmf(N: int = N_BALLS, m: int = M_DRAW) -> list[int]:
    """从 1..N 取 m 个号，和值 = s 的方案数（精确 DP），索引即 s。"""
    hi = m * N
    dp = [[0] * (hi + 1) for _ in range(m + 1)]
    dp[0][0] = 1
    for x in range(1, N + 1):
        for j in range(min(m, x), 0, -1):
            row, prev = dp[j], dp[j - 1]
            for s in range(hi, x - 1, -1):
                v = prev[s - x]
                if v:
                    row[s] += v
    return dp[m]


# ───────────────────────────── 检验工具 ─────────────────────────────
def chi2_gof(counts, exps, min_exp: float = 5.0) -> dict:
    """卡方拟合优度；相邻组并类直到期望 >= min_exp。dof = 并类后组数 - 1。"""
    counts = [float(c) for c in counts]
    exps = [float(e) for e in exps]
    cells: list[list[float]] = []
    cc = ee = 0.0
    for c, e in zip(counts, exps):
        cc += c
        ee += e
        if ee >= min_exp:
            cells.append([cc, ee])
            cc = ee = 0.0
    if cc > 0 or ee > 0:
        if cells and ee < min_exp:
            cells[-1][0] += cc
            cells[-1][1] += ee
        else:
            cells.append([cc, ee])
    chi2 = sum((c - e) ** 2 / e for c, e in cells if e > 0)
    dof = max(1, len(cells) - 1)
    return {
        "chi2": chi2,
        "dof": dof,
        "p": chi2_sf(chi2, dof),
        "n_cells": len(cells),
        "cells": [[round(c, 4), round(e, 4)] for c, e in cells],
    }


def chi2_sf(x: float, dof: int) -> float:
    """卡方上尾概率（正则化不完全伽马 Q(dof/2, x/2)）。"""
    a = dof / 2.0
    xx = x / 2.0
    if xx <= 0:
        return 1.0
    if xx < a + 1:
        term = 1.0 / a
        s = term
        n = a
        for _ in range(1000):
            n += 1
            term *= xx / n
            s += term
            if abs(term) < abs(s) * 1e-15:
                break
        p = s * math.exp(-xx + a * math.log(xx) - math.lgamma(a))
        return max(0.0, 1.0 - p)
    tiny = 1e-300
    b = xx + 1 - a
    c = 1 / tiny
    d = 1 / b if b != 0 else 1 / tiny
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return math.exp(-xx + a * math.log(xx) - math.lgamma(a)) * h


def normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def normal_sf(x: float) -> float:
    return 1.0 - normal_cdf(x)


def z_test_mean(values, mu: float, sd: float) -> dict:
    """已知标准差的均值检验（单样本 z）。"""
    n = len(values)
    mean = sum(values) / n
    se = sd / math.sqrt(n)
    z = (mean - mu) / se if se > 0 else 0.0
    return {
        "n": n,
        "mean": mean,
        "mu": mu,
        "sd_pop": sd,
        "se": se,
        "z": z,
        "p": 2 * (1 - normal_cdf(abs(z))),
    }


def chi2_independence(table) -> dict:
    """(r x c) 列联表独立性检验。"""
    rows = len(table)
    cols = len(table[0])
    tot = sum(sum(r) for r in table)
    rt = [sum(r) for r in table]
    ct = [sum(table[i][j] for i in range(rows)) for j in range(cols)]
    chi2 = 0.0
    for i in range(rows):
        for j in range(cols):
            e = rt[i] * ct[j] / tot
            if e > 0:
                chi2 += (table[i][j] - e) ** 2 / e
    dof = (rows - 1) * (cols - 1)
    return {"chi2": chi2, "dof": dof, "p": chi2_sf(chi2, dof)}


def autocorr(x, lag: int) -> float:
    n = len(x)
    m = sum(x) / n
    den = sum((v - m) ** 2 for v in x)
    num = sum((x[i] - m) * (x[i + lag] - m) for i in range(n - lag))
    return num / den


def ljung_box(x, h: int = 10) -> dict:
    """Ljung–Box Q 统计量。"""
    n = len(x)
    rs = [autocorr(x, lag) for lag in range(1, h + 1)]
    q = n * (n + 2) * sum(r * r / (n - k) for k, r in enumerate(rs, start=1))
    return {"h": h, "Q": q, "dof": h, "p": chi2_sf(q, h), "r": rs}


def bh_fdr(pvals, alpha: float = 0.05) -> dict:
    """Benjamini–Hochberg FDR 校正，返回 q 值与拒绝集合。"""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [1.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        val = min(prev, pvals[i] * m / rank)
        q[i] = val
        prev = val
    rej = [i for i in range(m) if q[i] <= alpha]
    return {"q": q, "reject": rej, "n_reject": len(rej), "alpha": alpha, "m": m}


def max_run_bool(bits, value=True) -> int:
    """最长连击（连续 value 的最大长度）。"""
    best = cur = 0
    for b in bits:
        if b == value:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def run_hist_bool(bits, value=True, cap: int = 20) -> list[int]:
    h = [0] * (cap + 1)
    cur = 0
    for b in list(bits) + [not value]:
        if b == value:
            cur += 1
        else:
            if cur:
                h[min(cur, cap)] += 1
            cur = 0
    return h


def quantiles(vals, qs=(0.05, 0.25, 0.5, 0.75, 0.95, 0.99)) -> dict:
    v = sorted(vals)
    n = len(v)

    def _q(p):
        if n == 0:
            return float("nan")
        pos = p * (n - 1)
        lo = int(math.floor(pos))
        hi = min(lo + 1, n - 1)
        w = pos - lo
        return v[lo] * (1 - w) + v[hi] * w

    return {f"p{int(p*100):02d}": _q(p) for p in qs}


def pct_rank(vals, x) -> float:
    """x 在 vals 中的百分位（<=x 的比例）。"""
    return sum(1 for v in vals if v <= x) / len(vals)


def runs_test(seq) -> dict:
    """Wald–Wolfowitz 游程检验（针对二值/布尔序列）。"""
    s = [bool(x) for x in seq]
    n = len(s)
    if n < 2:
        return {"runs": 0, "n1": 0, "n2": 0, "z": 0.0, "p": 1.0}
    n1 = sum(s)
    n2 = n - n1
    if n1 == 0 or n2 == 0:
        return {"runs": 1, "n1": n1, "n2": n2, "z": 0.0, "p": 1.0}
    r = 1 + sum(1 for i in range(1, n) if s[i] != s[i - 1])
    mu = 1.0 + (2.0 * n1 * n2) / n
    var = (2.0 * n1 * n2 * (2.0 * n1 * n2 - n)) / (n * n * (n - 1.0))
    sd = math.sqrt(max(var, 1e-12))
    z = (r - mu) / sd
    p = 2.0 * (1.0 - normal_cdf(abs(z)))
    return {"runs": r, "n1": n1, "n2": n2, "mean": mu, "sd": sd, "z": z, "p": p}

