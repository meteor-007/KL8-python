# -*- coding: utf-8 -*-
"""V7 —— 唯一一个"看起来像偏差"的发现，以及它为什么仍然不可用。

发现（由结构分析独立提出）
------------------------
2101 期整体和值尾数：小(0-4)=979，大(5-9)=1122
    z = +3.12, p = 0.0019（vs 0.5）
前半段 大占比 0.5476 (p=0.0022)，后半段 0.5205 (p=0.195) —— 方向一致但幅度衰减

本脚本回答四个问题
------------------
Q1 这个偏差是不是"和值尾数理论分布不均匀"造成的假象？→ 蒙特卡洛精确理论
Q2 它经得起多重比较校正吗？
Q3 它能不能预测下一期？（自相关 / 转移矩阵）
Q4 它能不能迁移到"对应规"规则B 上？（三球和值尾数是否也有偏）
"""
from __future__ import annotations

import collections
import itertools
import os
import sys

import numpy as np
from scipy.stats import binomtest, chi2_contingency

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

periods, idx = load_index()
draws = [idx[p] for p in periods]
N = len(draws)


def q1_theory():
    sums = [sum(d) for d in draws]
    tail = [s % 10 for s in sums]
    small = sum(1 for t in tail if t <= 4)
    big = N - small
    # 蒙特卡洛求"20球和值尾数"的真实理论分布（不是假设均匀）
    rng = np.random.default_rng(2026)
    M = 200_000
    cnt = np.zeros(10, dtype=np.int64)
    for _ in range(M):
        cnt[int(np.sort(rng.choice(np.arange(1, 81), 20, replace=False)).sum()) % 10] += 1
    th_big = cnt[5:].sum() / M
    p_vs_half = binomtest(big, N, 0.5).pvalue
    p_vs_theory = binomtest(big, N, th_big).pvalue
    return {
        "obs_small": small, "obs_big": big, "n": N,
        "obs_big_prop": round(big / N, 5),
        "tail_counts": {t: tail.count(t) for t in range(10)},
        "mc_theory_tail_props": {t: round(float(cnt[t] / M), 5) for t in range(10)},
        "mc_theory_big_prop": round(float(th_big), 5),
        "z_vs_half": round((big / N - 0.5) / (0.25 / N) ** 0.5, 3),
        "p_vs_half": round(float(p_vs_half), 6),
        "p_vs_mc_theory": round(float(p_vs_theory), 6),
        "conclusion": "理论分布本身接近均匀(0.4985)，实测偏差不能归因于理论不均匀",
    }


def q2_multiplicity(p: float):
    rows = []
    for m in (10, 20, 30, 50, 100):
        rows.append({"n_tests": m,
                     "bonferroni_threshold": round(0.05 / m, 6),
                     "bonferroni_significant": p < 0.05 / m,
                     "bh_threshold_if_smallest": round(0.05 / m, 6),
                     "bh_significant": p <= 0.05 / m})
    return {"p_value": p, "table": rows,
            "features_checked_in_this_report": ">=30（位次12 + 012路结构4 + 和值5 + 独立性约10）",
            "note": "在 m>=30 时 Bonferroni 与 BH 均不显著"}


def q3_predictive():
    tail = np.array([sum(d) % 10 for d in draws])
    big = (tail >= 5).astype(int)
    ac = {}
    for lag in (1, 2, 3, 5, 10):
        r = float(np.corrcoef(big[:-lag], big[lag:])[0, 1])
        ac[lag] = round(r, 4)
    tr = collections.defaultdict(lambda: [0, 0])
    for a, b in zip(big[:-1], big[1:]):
        tr[int(a)][int(b)] += 1
    trans = {k: {"n": sum(v), "p_big_next": round(v[1] / sum(v), 4)} for k, v in tr.items()}
    table = np.array([[tr[0][0], tr[0][1]], [tr[1][0], tr[1][1]]])
    chi2, p_chi, dof, _ = chi2_contingency(table, correction=False)
    half = N // 2
    seg = {}
    for name, s in (("前半", big[:half]), ("后半", big[half:])):
        b, n = int(s.sum()), len(s)
        seg[name] = {"p_big": round(b / n, 4), "n": n,
                     "p": round(float(binomtest(b, n, 0.5).pvalue), 4)}
    return {"autocorrelation": ac, "transition": trans,
            "chi2_transition": round(float(chi2), 4),
            "p_transition": round(float(p_chi), 4),
            "segments": seg,
            "conclusion": "自相关≈0.01，转移矩阵 p 不显著 → 该偏差对下一期无预测力"}


def q4_transfer():
    c = collections.Counter()
    for d in draws:
        for tri in itertools.combinations([int(x) for x in d], 3):
            c[tail_size(sum(tri) % 10)] += 1
    tot = sum(c.values())
    p = float(binomtest(c["大"], tot, 0.5).pvalue)
    return {"triple_big": c["大"], "triple_small": c["小"], "total": tot,
            "big_prop": round(c["大"] / tot, 5), "deviation": round(c["大"] / tot - 0.5, 5),
            "p_value": round(p, 4),
            "conclusion": "三球和值尾数完全无偏(偏差-0.0004, p=0.23) → 整体和值的偏差无法迁移到规则B"}


if __name__ == "__main__":
    q1 = q1_theory()
    print("Q1 理论 vs 实测:", json.dumps(q1, ensure_ascii=False)[:400])
    q2 = q2_multiplicity(q1["p_vs_half"])
    print("Q2 多重校正:", [(r["n_tests"], r["bonferroni_significant"]) for r in q2["table"]])
    q3 = q3_predictive()
    print("Q3 可预测性:", q3["autocorrelation"], "转移p=", q3["p_transition"], q3["segments"])
    q4 = q4_transfer()
    print("Q4 可迁移性:", q4)
    save_json("v7_tail_bias.json", {"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4,
                                    "summary": "整体和值尾数存在轻微偏差(z=3.12)，"
                                               "但不通过 m>=30 的多重校正、无自相关、"
                                               "且三球和值尾数完全无偏，故不可用于任何规则或下注"})
    print("saved v7_tail_bias.json")