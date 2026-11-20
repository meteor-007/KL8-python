# -*- coding: utf-8 -*-
"""V6 —— 正式显著性检验：3240 条候选规则 × 二项检验 × BH-FDR 多重校正。

假设
----
H0: 规则命中率 = 理论基准率（规则A: 1/3；规则B: 1/2）
H1: 偏离

如果"对应规律"是真规律，BH-FDR 校正后应仍有大量规则显著偏离基准；
如果只是巧合/事后挑选，校正后显著数应 ≈ 0。

对照组：用 80 选 20 生成的**纯随机 2101 期**跑同一套流程。
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from scipy.stats import binom

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

OFFSETS = list(range(-6, 3))
POS = 20
WIN = 18


def build_hit_matrix(A: np.ndarray, attr: str) -> np.ndarray:
    """(K, N) 布尔命中矩阵；K = 9 期差 × 18 窗口 × 20 位次 = 3240。"""
    N = A.shape[0]
    purple = (A % 3) if attr == "r012" else ((A % 10) >= 5).astype(np.int8)
    mats = []
    for d in OFFSETS:
        idx = np.arange(N) + d
        valid = (idx >= 0) & (idx < N)
        src = A[np.clip(idx, 0, N - 1)]
        for c in range(WIN):
            s = src[:, c] + src[:, c + 1] + src[:, c + 2]
            o = (s % 3) if attr == "r012" else ((s % 10) >= 5)
            mats.append(((o[:, None] == purple) & valid[:, None]).T)
    return np.concatenate(mats, axis=0)


def bh_fdr(pvals: np.ndarray, alpha=0.05):
    """Benjamini-Hochberg。返回 (显著个数, 判定阈值, 最小 p)。"""
    m = pvals.size
    order = np.argsort(pvals)
    sp = pvals[order]
    thresh = alpha * np.arange(1, m + 1) / m
    below = sp <= thresh
    kmax = int(np.max(np.where(below)[0]) + 1) if below.any() else 0
    return kmax, (float(thresh[kmax - 1]) if kmax else None), float(sp[0])


def analyse(A: np.ndarray, tag: str) -> dict:
    N = A.shape[0]
    res = {"tag": tag, "n_periods": N, "attrs": {}}
    for attr, base in (("r012", 1 / 3), ("tailsize", 0.5)):
        H = build_hit_matrix(A, attr)
        k = H.sum(axis=1).astype(float)          # (K,)
        n = float(N)
        rate = k / n
        se = math.sqrt(base * (1 - base) / n)
        z = (rate - base) / se
        # 精确双侧二项 p：2*min(P(X<=k), P(X>k))，上限 1
        p_lo = binom.cdf(k, n, base)
        p_hi = binom.sf(k - 1, n, base)
        p = np.minimum(1.0, 2 * np.minimum(p_lo, p_hi))
        kmax, thr, pmin = bh_fdr(p, 0.05)
        n_nominal = int((p < 0.05).sum())
        res["attrs"][attr] = {
            "n_rules": int(H.shape[0]),
            "base_rate": base,
            "mean_rate": round(float(rate.mean()), 5),
            "sd_rate": round(float(rate.std(ddof=1)), 5),
            "theoretical_sd": round(se, 5),
            "max_z": round(float(z.max()), 3),
            "min_z": round(float(z.min()), 3),
            "n_p_below_005": n_nominal,
            "expected_nominal_under_H0": round(0.05 * H.shape[0], 1),
            "n_significant_BH_FDR": int(kmax),
            "bh_threshold": thr,
            "min_p": round(pmin, 6),
            "best_rule": {"idx": int(np.argmax(rate)), "rate": round(float(rate.max()), 5)},
            "worst_rule": {"idx": int(np.argmin(rate)), "rate": round(float(rate.min()), 5)},
        }
        print(f"[{tag}/{attr}] rules={H.shape[0]} 均值={rate.mean():.5f} "
              f"sd={rate.std(ddof=1):.5f} (理论 {se:.5f})")
        print(f"    z∈[{z.min():.2f},{z.max():.2f}]  p<0.05 个数={n_nominal} "
              f"(H0期望 {0.05*H.shape[0]:.0f})  BH-FDR显著={kmax}  min_p={pmin:.4g}")
    return res


def single_rule_test(A: np.ndarray, attr: str, ppos: int, rows, opos, base: float):
    N = A.shape[0]
    b = []
    for t in range(N):
        if any(t + r < 0 or t + r >= N for r in rows):
            continue
        tri = [int(A[t + r][o - 1]) for r, o in zip(rows, opos)]
        if len(set(tri)) != 3:
            continue
        pu = int(A[t][ppos - 1])
        b.append((sum(tri) % 3 == pu % 3) if attr == "r012"
                 else (tail_size(sum(tri) % 10) == tail_size(pu % 10)))
    k, n = sum(b), len(b)
    se = math.sqrt(base * (1 - base) / n)
    p = float(min(1.0, 2 * min(binom.cdf(k, n, base), binom.sf(k - 1, n, base))))
    return {"attr": attr, "purple_pos": ppos, "rows": list(rows), "opos": list(opos),
            "n": n, "hits": k, "rate": round(k / n, 5), "base": base,
            "z": round((k / n - base) / se, 3), "p_two_sided": round(p, 4),
            "max_run": max_run(b), "significant_at_005": p < 0.05}


if __name__ == "__main__":
    periods, idx = load_index()
    A = np.array([idx[p] for p in periods], dtype=np.int16)
    N = A.shape[0]
    rng = np.random.default_rng(7)
    A_rand = np.array([np.sort(rng.choice(np.arange(1, 81), 20, replace=False))
                       for _ in range(N)], dtype=np.int16)

    real = analyse(A, "real")
    rand = analyse(A_rand, "random1")

    singles = {
        "ruleA_fixed": single_rule_test(A, "r012", 1, (1, 2, 2), (3, 2, 4), 1 / 3),
        "ruleB_fixed": single_rule_test(A, "tailsize", 2, (1, 2, 2), (3, 2, 4), 0.5),
        "ruleA_screenshot_geom": single_rule_test(A, "r012", 1, (-2, -1, -1), (3, 2, 4), 1 / 3),
    }
    for k, v in singles.items():
        print(f"  单规则 {k}: rate={v['rate']} z={v['z']} p={v['p_two_sided']} "
              f"最长连击={v['max_run']} 显著={v['significant_at_005']}")

    real["random_control"] = rand
    real["single_rules"] = singles
    real["note"] = "BH-FDR alpha=0.05；p 为精确双侧二项检验；候选规则 = 20位次×18窗口×9期差"
    save_json("v6_significance.json", real)
    print("saved v6_significance.json")