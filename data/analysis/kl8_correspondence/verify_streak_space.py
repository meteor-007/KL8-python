# -*- coding: utf-8 -*-
"""V4 —— "连续命中"幻觉的定量证明（本工程最核心的验证）。

APP 的展示逻辑
--------------
用户看到的不是"某一条预先写死的规则"，而是：在**成千上万条候选规则**里，
挑出**当前正好在连中**的那一条展示给你看。这叫事后挑选（post-hoc selection）。

本脚本回答三个问题
------------------
Q1  在真实的 2101 期数据上，任一时刻"当前连中 >= k 期"的候选规则有多少条？
Q2  同样的统计量，在**纯随机生成**的 2101 期数据上是多少？（对照组）
Q3  真实数据与随机数据能否区分？如果不能，"连续9次/14次"就不能作为规律的证据。

候选规则空间（贴近 APP 实际展示形态）
------------------------------------
紫球：第 t 期第 p 位，p = 1..20
橙球：第 t+d 期第 c, c+1, c+2 位（连续窗口，与截图中的连线形态一致），c = 1..18
期差：d = -6..+2
属性：A) 和值 012 路对应   B) 和值尾数大小对应
=> 每个属性 20 × 18 × 9 = 3240 条候选规则
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

OUT_JSON = "v4_streak_space.json"
OFFSETS = list(range(-6, 3))          # 9 个期差
POS = 20                              # 20 个位次
WIN = 18                              # 连续三球窗口起点 c=1..18


def gen_random_draws(n_periods: int, rng) -> np.ndarray:
    """生成 n_periods 期、每期 80 选 20 的纯随机数据（升序）。"""
    out = np.empty((n_periods, POS), dtype=np.int16)
    for t in range(n_periods):
        out[t] = np.sort(rng.choice(np.arange(1, 81), size=POS, replace=False))
    return out


def build_bits(A: np.ndarray, attr: str) -> np.ndarray:
    """返回 (K, N) 布尔矩阵：K = len(OFFSETS)*WIN*POS 条候选规则，N 期。"""
    N = A.shape[0]
    if attr == "r012":
        purple = (A % 3)                                    # (N,20)
        purple_ok = lambda pv: pv                       # noqa: E731
    else:
        purple = ((A % 10) >= 5).astype(np.int8)            # 尾数大小 大=True
    mats = []
    for d in OFFSETS:
        # 对齐：橙球期 = t + d
        idx = np.arange(N) + d
        valid = (idx >= 0) & (idx < N)
        src = A[np.clip(idx, 0, N - 1)]                      # (N,20)
        for c in range(WIN):                                 # c=0..17 -> 位次 c+1..c+3
            s = src[:, c] + src[:, c + 1] + src[:, c + 2]     # (N,)
            if attr == "r012":
                orange = (s % 3)[:, None]                     # (N,1)
                eq = (orange == purple)                       # (N,20)
            else:
                orange = ((s % 10) >= 5)[:, None]
                eq = (orange == purple.astype(bool))
            eq &= valid[:, None]
            mats.append(eq.T)                                 # (20, N)
    return np.concatenate(mats, axis=0)                       # (K, N)


def streak_ge_counts(bits: np.ndarray, t_list, K: int) -> dict:
    """对每个 t，统计"截至 t-1 已连中 >= K"的规则条数（t 本身不计入）。"""
    n_rules = bits.shape[0]
    run = np.zeros(n_rules, dtype=np.int16)     # 到上一期为止的连中长度
    out = {}
    want = set(t_list)
    for t in range(bits.shape[1]):
        if t in want:
            out[t] = int((run >= K).sum())
        # 更新：本期结果影响下一期的 run
        run = np.where(bits[:, t], run + 1, 0)
    return out


def analyse(A: np.ndarray, tag: str, rng, ks=(9, 14)) -> dict:
    N = A.shape[0]
    res = {"tag": tag, "n_periods": N}
    for attr in ("r012", "tailsize"):
        bits = build_bits(A, attr)
        res[attr] = {"n_rules": int(bits.shape[0]), "base_rate": round(float(bits.mean()), 4)}
        t_list = list(range(300, N))
        for K in ks:
            c = streak_ge_counts(bits, t_list, K)
            arr = np.array([c[t] for t in t_list])
            res[attr][f"ge{K}"] = {
                "mean": round(float(arr.mean()), 3),
                "median": int(np.median(arr)),
                "max": int(arr.max()),
                "pct_periods_nonzero": round(float((arr > 0).mean()), 4),
                "pct_ge2": round(float((arr >= 2).mean()), 4),
            }
        # 任一时刻的"最长可用连中"
        run = np.zeros(bits.shape[0], dtype=np.int16)
        best_series = []
        for t in range(N):
            if t >= 300:
                best_series.append(int(run.max()) if run.size else 0)
            run = np.where(bits[:, t], run + 1, 0)
        res[attr]["max_streak_available"] = {
            "median": int(np.median(best_series)),
            "p90": int(np.percentile(best_series, 90)),
            "max": int(max(best_series)),
        }
    return res


if __name__ == "__main__":
    periods, idx = load_index()
    A_real = np.array([idx[p] for p in periods], dtype=np.int16)
    rng = np.random.default_rng(20261022)

    print(f"真实数据: {A_real.shape[0]} 期")
    real = analyse(A_real, "real", rng)
    for attr in ("r012", "tailsize"):
        print(f"  [真实/{attr}] rules={real[attr]['n_rules']} base={real[attr]['base_rate']}")
        for K in (9, 14):
            print(f"    连中>= {K}: {real[attr]['ge%d' % K]}")
        print(f"    任一时刻最长可用连中: {real[attr]['max_streak_available']}")

    print("\n随机对照（独立同分布，80选20）:")
    rand_runs = []
    for rep in range(3):
        A_rand = gen_random_draws(A_real.shape[0], rng)
        r = analyse(A_rand, f"random{rep}", rng)
        rand_runs.append(r)
        print(f"  [随机{rep}/tailsize] 连中>=9: {r['tailsize']['ge9']}")
        print(f"  [随机{rep}/tailsize] 连中>=14: {r['tailsize']['ge14']}")
        print(f"  [随机{rep}/r012]    连中>=9: {r['r012']['ge9']}")

    # 汇总对照
    comp = {}
    for attr in ("r012", "tailsize"):
        for K in (9, 14):
            key = f"ge{K}"
            comp[f"{attr}_{key}"] = {
                "real_mean": real[attr][key]["mean"],
                "real_pct_nonzero": real[attr][key]["pct_periods_nonzero"],
                "random_mean_range": [
                    min(r[attr][key]["mean"] for r in rand_runs),
                    max(r[attr][key]["mean"] for r in rand_runs),
                ],
                "random_pct_nonzero_range": [
                    min(r[attr][key]["pct_periods_nonzero"] for r in rand_runs),
                    max(r[attr][key]["pct_periods_nonzero"] for r in rand_runs),
                ],
            }
    for k, v in comp.items():
        print(f"  对照 {k}: 真实均值={v['real_mean']} 随机区间={v['random_mean_range']}")

    save_json(OUT_JSON, {"real": real, "random": rand_runs, "compare": comp,
                         "offsets": OFFSETS, "note": "连中数按 t-1 及以前计，t 为待预测期"})
    print("\nsaved ->", os.path.join(OUT, OUT_JSON))
