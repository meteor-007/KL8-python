# -*- coding: utf-8 -*-
"""audit_lib —— 快乐8 "对应规律" 独立统计审计 专用公共库。

只被 audit_*.py 使用；不改动 common.py / 项目其它文件。
所有模板扫描、游程统计、精确分布、多重比较工具集中在这里，保证各步骤口径一致。
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # .../analysis/kl8_correspondence
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from common import (  # noqa: E402
    chi2_sf,
    load_index,
    normal_cdf,
    save_json,
    save_text,
)

# ───────────────────────── 常量 ─────────────────────────
SEED = 2026280            # 固定随机种子，保证可重复
T_DEFAULT = 2101          # 序列长度
PURPLE_POS = tuple(range(1, 13))          # 紫球位次 1..12
O_POS = tuple(range(1, 13))               # 橙球位次取自 1..12
COMBOS = tuple(
    (a, b, c)
    for a in O_POS for b in O_POS for c in O_POS
    if a < b < c
)                                          # C(12,3) = 220
N_COMBOS = len(COMBOS)                     # 220
OFFSETS = tuple(range(-6, 7))              # 期差 d ∈ [-6, +6]
N_OFFSETS = len(OFFSETS)                   # 13
ATTRS = ("A", "B")
ATTR_DESC = {
    "A": "规则A: 三球和值 012 路 == 紫球 012 路",
    "B": "规则B: 三球和值尾数大小 == 紫球自身尾数大小",
}
RULE_P = {"A": 1.0 / 3.0, "B": 0.5}        # 理论偶然命中率（均匀假设下的天花板）

# 扁平索引： idx = ((p-1)*220 + c) * 13 + (d+6)
N_PER_ATTR = len(PURPLE_POS) * N_COMBOS * N_OFFSETS   # 34320
N_ALL = N_PER_ATTR * 2                                # 68640


# ───────────────────────── 数据 ─────────────────────────
def load_draws():
    """返回 (periods, num[T,20] int32 升序)。"""
    periods, idx = load_index()
    num = np.array([idx[p] for p in periods], dtype=np.int32)
    assert num.shape[1] == 20, num.shape
    return list(periods), num


def attr_encode(vals, attr):
    """把号码/和值编码成规则属性类别。attr='A' -> 0/1/2；attr='B' -> 0(小)/1(大)。"""
    v = np.asarray(vals)
    if attr == "A":
        return (v % 3).astype(np.int8)
    if attr == "B":
        return ((v % 10) >= 5).astype(np.int8)
    raise ValueError(attr)


def triple_sum_matrix(num):
    """(T,220) 每期内 C(12,3) 个位次组合的和值。"""
    ci = np.array(COMBOS, dtype=np.int64) - 1  # (220,3)
    s = num[:, ci[:, 0]] + num[:, ci[:, 1]] + num[:, ci[:, 2]]
    return s.astype(np.int32)


def grid_arrays(num):
    """{'A': {'purple': (T,12), 'triple': (T,220)}, 'B': {...}}"""
    s = triple_sum_matrix(num)
    out = {}
    for attr in ATTRS:
        out[attr] = {
            "purple": attr_encode(num[:, :12], attr),
            "triple": attr_encode(s, attr),
        }
    return out


def valid_range(T, d):
    """紫球期 t 的有效范围 [t0, t1]（闭区间），橙球期 = t+d。"""
    t0 = max(0, -d)
    t1 = min(T - 1, T - 1 - d)
    return t0, t1


def flat_names():
    """扁平索引 -> (attr, purple_pos, combo, d)。"""
    for attr in ATTRS:
        for p in PURPLE_POS:
            for ci, c in enumerate(COMBOS):
                for di, d in enumerate(OFFSETS):
                    yield (( (p - 1) * N_COMBOS + ci) * N_OFFSETS + di), attr, p, c, d


# ───────────────────────── 游程统计 ─────────────────────────
def block_stats(mat, ks=(9, 14), want_runs=True):
    """对一个 (R, n) 布尔矩阵逐行做游程统计。

    返回 dict:
      hits[R], n, maxrun[R], maxrun_start[R], trailing[R],
      total_runs_ge{k}, row_has_ge{k}[R],
      run_hist{k}[R]  (长度恰为 k 的游程个数, 只统计 k in ks)
    """
    mat = np.ascontiguousarray(mat, dtype=bool)
    R, n = mat.shape
    idx = np.arange(n, dtype=np.int32)
    lf = np.maximum.accumulate(np.where(mat, np.int32(-1), idx), axis=1)
    runlen = idx[None, :] - lf            # (R,n) 以 t 结尾的连击长度
    maxrun = runlen.max(axis=1)
    am = runlen.argmax(axis=1)
    maxrun_start = am - maxrun + 1
    trailing = runlen[:, -1].copy()
    hits = mat.sum(axis=1)
    del runlen, lf

    res = {
        "n": n,
        "hits": hits.astype(np.int32),
        "maxrun": maxrun.astype(np.int32),
        "maxrun_start": maxrun_start.astype(np.int32),
        "trailing": trailing.astype(np.int32),
    }
    if not want_runs:
        return res
    padded = np.zeros((R, n + 2), dtype=np.int8)
    padded[:, 1:-1] = mat
    d = np.diff(padded, axis=1)           # (R,n+1)
    del padded
    sr, sc = np.where(d == 1)
    er, ec = np.where(d == -1)
    assert np.array_equal(sr, er), "start/end 行号不一致"
    ln = (ec - sc).astype(np.int32)
    del d
    for k in ks:
        sel = ln >= k
        res[f"total_runs_ge{k}"] = int(sel.sum())
        res[f"row_runs_ge{k}"] = np.bincount(sr[sel], minlength=R).astype(np.int32)
        res[f"row_has_ge{k}"] = res[f"row_runs_ge{k}"] > 0
    # 每行最长游程的起始（含并列取最早）已由 maxrun_start 给出
    res["_run_lens"] = ln
    res["_run_rows"] = sr
    res["_run_starts"] = sc
    return res


# ───────────────────────── 全网格扫描 ─────────────────────────
def scan_grid(num, attrs=ATTRS, offsets=OFFSETS, ks=(9, 14), collect=True):
    """穷举扫描 紫球位次 × 橙三球位次组合 × 期差 × 属性。

    返回 dict，键为 attr，内含扁平数组（长度 = 12*220*13 = 34320）：
      purple_pos, combo_idx, d, n, hits, rate, maxrun, maxrun_start, trailing,
      total_runs_ge9/14 (标量), row_has_ge9/14 (bool 数组)
    """
    ga = grid_arrays(num)
    T = num.shape[0]
    out = {}
    for attr in attrs:
        P = ga[attr]["purple"]
        S = ga[attr]["triple"]
        NP, NC = len(PURPLE_POS), N_COMBOS
        R = NP * NC
        arr = {
            "n": np.zeros((len(offsets), R), dtype=np.int32),
            "hits": np.zeros((len(offsets), R), dtype=np.int32),
            "maxrun": np.zeros((len(offsets), R), dtype=np.int32),
            "maxrun_start": np.zeros((len(offsets), R), dtype=np.int32),
            "trailing": np.zeros((len(offsets), R), dtype=np.int32),
            "row_runs_ge9": np.zeros((len(offsets), R), dtype=np.int32),
            "row_has_ge9": np.zeros((len(offsets), R), dtype=bool),
            "row_has_ge14": np.zeros((len(offsets), R), dtype=bool),
            "tot_ge9": np.zeros(len(offsets), dtype=np.int64),
            "tot_ge14": np.zeros(len(offsets), dtype=np.int64),
            "margin_purple": np.zeros((NP, 3), dtype=np.float64),   # attr A 有 3 类
            "margin_triple": None,
        }
        stats_blocks = []
        for di, d in enumerate(offsets):
            t0, t1 = valid_range(T, d)
            n = t1 - t0 + 1
            pv = P[t0:t1 + 1]              # (n,12)
            sv = S[t0 + d:t1 + 1 + d]      # (n,220)
            hit = pv[:, :, None] == sv[:, None, :]     # (n,12,220)
            mat = np.ascontiguousarray(hit.transpose(1, 2, 0)).reshape(R, n)
            del hit
            st = block_stats(mat, ks=ks)
            del mat
            arr["n"][di] = n
            arr["hits"][di] = st["hits"]
            arr["maxrun"][di] = st["maxrun"]
            arr["maxrun_start"][di] = st["maxrun_start"]
            arr["trailing"][di] = st["trailing"]
            arr["row_runs_ge9"][di] = st["row_runs_ge9"]
            arr["row_has_ge9"][di] = st["row_has_ge9"]
            arr["row_has_ge14"][di] = st["row_has_ge14"]
            arr["tot_ge9"][di] = st["total_runs_ge9"]
            arr["tot_ge14"][di] = st["total_runs_ge14"]
            if di == 0:
                # 边际分布只与 d 的端点效应有关，取 d=0 作为主口径
                for pi in range(NP):
                    arr["margin_purple"][pi] = np.bincount(
                        pv[:, pi], minlength=3)[:3] / n
                arr["margin_triple"] = (sv[:, :, None] ==
                                        np.array([0, 1, 2])[None, None, :]
                                        ).sum(axis=0) / n   # (220,3)
            stats_blocks.append(st)
        arr["rate"] = arr["hits"] / arr["n"]
        # 填上 p,d,combo 元数据
        arr["purple_pos"] = np.repeat(np.arange(1, NP + 1), NC)
        arr["combo_idx"] = np.tile(np.arange(NC), NP)
        arr["d"] = np.array(offsets)
        out[attr] = arr
    return out


def summaries(arr, attr):
    """把扫描结果压平成 (attr, p, c1,c2,c3, d) 记录数组，便于统一分析。"""
    recs = []
    pur = arr["purple_pos"]
    ci = arr["combo_idx"]
    for di, d in enumerate(arr["d"]):
        for r in range(pur.size):
            c = COMBOS[ci[r]]
            recs.append((attr, int(pur[r]), c[0], c[1], c[2], int(d),
                         int(arr["n"][di, r]), int(arr["hits"][di, r]),
                         float(arr["rate"][di, r]), int(arr["maxrun"][di, r]),
                         int(arr["maxrun_start"][di, r]), int(arr["trailing"][di, r]),
                         int(arr["row_runs_ge9"][di, r]),
                         bool(arr["row_has_ge14"][di, r])))
    return recs


# ───────────────────────── 精确分布 ─────────────────────────
def prob_no_run(n, p, k):
    """精确 P(n 长 iid Bernoulli(p) 序列中不存在长度 >= k 的连击)。O(n*k)。"""
    if k <= 1:
        return 0.0 if p > 0 and n > 0 else 1.0
    f = np.zeros(k, dtype=np.float64)
    f[0] = 1.0
    q = 1.0 - p
    for _ in range(n):
        s = f.sum()
        g = np.empty_like(f)
        g[0] = q * s
        g[1:] = p * f[:-1]
        f = g
    return float(f.sum())


def prob_exist_run(n, p, k):
    return 1.0 - prob_no_run(n, p, k)


def maxrun_cdf(n, p, mmax=40):
    """P(maxrun <= m) 对 m=0..mmax（精确 DP）。"""
    out = []
    for m in range(mmax + 1):
        out.append(prob_no_run(n, p, m + 1))
    return np.array(out)


def maxrun_quantile(cdf, q):
    """cdf[m] = P(maxrun <= m)；返回最小 m 使 cdf[m] >= q。"""
    for m, v in enumerate(cdf):
        if v >= q:
            return m
    return len(cdf) - 1


# ───────────────────────── 蒙特卡洛 ─────────────────────────
def mc_maxrun_quantiles(n, p, sims, rng, batch=4000):
    """模拟 sims 条长度 n 的 Bernoulli(p) 序列，返回分位数与经验 P(maxrun>=9/14)。"""
    vals = np.empty(sims, dtype=np.int32)
    done = 0
    while done < sims:
        b = min(batch, sims - done)
        m = rng.random((b, n)) < p
        idx = np.arange(n, dtype=np.int32)
        lf = np.maximum.accumulate(np.where(m, np.int32(-1), idx), axis=1)
        vals[done:done + b] = (idx[None, :] - lf).max(axis=1)
        done += b
    return vals


def mc_any_run_over_templates(T, p, k, n_templates, sims, rng, chunk=572):
    """蒙特卡洛：每轮模拟 n_templates 条独立序列，估计 P(至少一条出现 >=k 连)。

    利用 iid 独立性做 chunk + 提前退出，控制单轮开销。
    """
    hit = 0
    for _ in range(sims):
        found = False
        left = n_templates
        while left > 0:
            b = min(chunk, left)
            left -= b
            m = rng.random((b, T)) < p
            idx = np.arange(T, dtype=np.int32)
            lf = np.maximum.accumulate(np.where(m, np.int32(-1), idx), axis=1)
            if ((idx[None, :] - lf) >= k).any():
                found = True
                break
        hit += int(found)
    return hit / sims


# ───────────────────────── 多重比较 ─────────────────────────
def z_test_rate(hits, n, p0):
    """二项 z 检验（双侧），返回 (z, p_two_sided)。"""
    hits = np.asarray(hits, dtype=np.float64)
    n = np.asarray(n, dtype=np.float64)
    p0 = np.asarray(p0, dtype=np.float64)
    se = np.sqrt(p0 * (1 - p0) / n)
    z = (hits / n - p0) / se
    p = 2.0 * (1.0 - np.array([normal_cdf(v) for v in z.ravel()])).reshape(z.shape)
    return z, np.clip(p, 0.0, 1.0)


def bonferroni(p, alpha=0.05):
    m = p.size
    adj = np.minimum(1.0, p * m)
    return adj, int((adj < alpha).sum())


def bh_fdr(p, alpha=0.05):
    """Benjamini-Hochberg，返回 (q_values, n_significant)。"""
    p = np.asarray(p, dtype=np.float64)
    m = p.size
    order = np.argsort(p)
    ps = p[order]
    qs = ps * m / np.arange(1, m + 1)
    # 从大到小取累计最小，保证单调
    qs = np.minimum.accumulate(qs[::-1])[::-1]
    qs = np.clip(qs, 0.0, 1.0)
    q = np.empty(m)
    q[order] = qs
    return q, int((q < alpha).sum())


# ───────────────────────── 杂项 ─────────────────────────
def pct(a, q):
    return float(np.percentile(np.asarray(a, dtype=np.float64), q))


def j(x, nd=6):
    """JSON 友好取整。"""
    if isinstance(x, (np.floating, float)):
        v = float(x)
        if not math.isfinite(v):
            return None
        return round(v, nd)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.ndarray):
        return [j(v, nd) for v in x.tolist()]
    return x


def save(name, obj):
    return save_json(name, obj)
