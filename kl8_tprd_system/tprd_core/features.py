#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TPRD v4.0 15维物理与带符号偏态特征工程模块
严格时间单向因果流，无前瞻泄漏 (No Data Leakage)
"""

from typing import Tuple
import numpy as np
from .constants import IS_PRIME, ROAD_ID, ZONE_ID, TAIL_ID, ROAD_MU, PRIME_MU


def build_features(B: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    基于开奖二值张量 B (N x 81)，向量化计算全量 15 维因果特征
    B[t, n] = 1 表示第 t 期开出了号码 n
    返回:
      X: (N, 80, 15) 特征张量
      road_counts: (N, 3) 012路每期开出计数
      prime_counts: (N,) 质数每期开出计数
    """
    N = B.shape[0]

    # 1. 遗漏追踪 (f1)
    omission = np.zeros((N, 81), dtype=np.float32)
    cur_om = np.zeros(81, dtype=np.float32)
    for t in range(N):
        omission[t] = cur_om
        cur_om = np.where(B[t] == 1, 0.0, cur_om + 1.0)

    # 2. 累积前缀和加速滑动窗口频次计算
    csum = np.vstack([np.zeros((1, 81)), np.cumsum(B, axis=0)])

    def rolling_freq(w: int) -> np.ndarray:
        res = np.zeros((N, 81), dtype=np.float32)
        for t in range(w, N):
            res[t] = csum[t] - csum[t - w]
        return res

    f_last5 = rolling_freq(5)    # f4: 近5期频次
    f_last15 = rolling_freq(15)  # f5: 近15期频次
    f_last30 = rolling_freq(30)  # f6: 近30期频次
    f_last120 = rolling_freq(120)

    # f2: 平滑均值遗漏
    avg_om = (120.0 + 3.0) / (f_last120 + 1.0) - 1.0
    # f3: 遗漏弹性比
    elastic = omission / np.maximum(1.0, avg_om)
    # f7: 短期动能比
    momentum = (f_last5 / 5.0) / ((f_last15 / 15.0) + 1e-4)

    # 3. 物理拓扑特征：邻居引力 (f8) 与 上期重号 (f9)
    neighbor = np.zeros((N, 81), dtype=np.float32)
    repeat = np.zeros((N, 81), dtype=np.float32)
    for t in range(1, N):
        repeat[t] = B[t - 1]
        for n in range(1, 81):
            raw_g = (1.0 if n > 1 and B[t - 1, n - 1] else 0.0) + (1.0 if n < 80 and B[t - 1, n + 1] else 0.0)
            neighbor[t, n] = min(1.5, raw_g)

    # 4. 宏观守恒统计 (012路、质合、同尾)
    road_counts = np.zeros((N, 3), dtype=np.float32)
    prime_counts = np.zeros(N, dtype=np.float32)
    tail_counts = np.zeros((N, 10), dtype=np.float32)
    for t in range(N):
        for r in range(3):
            road_counts[t, r] = np.sum(B[t, 1:][ROAD_ID[1:] == r])
        prime_counts[t] = np.sum(B[t, 1:] * IS_PRIME[1:])
        for tl in range(10):
            tail_counts[t, tl] = np.sum(B[t, 1:][TAIL_ID[1:] == tl])

    # 5. 带符号动态赤字与联动特征
    macro_road = np.zeros((N, 81), dtype=np.float32)   # f12
    macro_prime = np.zeros((N, 81), dtype=np.float32)  # f13
    tail_mom = np.zeros((N, 81), dtype=np.float32)     # f14

    for t in range(3, N):
        r_def = np.array([np.sum(ROAD_MU[r] - road_counts[t - 3:t, r]) for r in range(3)])
        p_def = np.sum(PRIME_MU - prime_counts[t - 3:t])
        tl_sum = np.sum(tail_counts[t - 3:t], axis=0)
        for n in range(1, 81):
            macro_road[t, n] = r_def[int(ROAD_ID[n])]
            macro_prime[t, n] = (2.0 * IS_PRIME[n] - 1.0) * p_def
            tail_mom[t, n] = (tl_sum[TAIL_ID[n]] - np.sum(B[t - 3:t, n])) / 3.0

    # 6. 组合 80 个号码的 15 维特征矩阵
    X = np.zeros((N, 80, 15), dtype=np.float32)
    for n in range(1, 81):
        idx = n - 1
        X[:, idx] = np.column_stack([
            omission[:, n], avg_om[:, n], elastic[:, n], f_last5[:, n], f_last15[:, n],
            f_last30[:, n], momentum[:, n], neighbor[:, n], repeat[:, n],
            np.full(N, ROAD_ID[n]), np.full(N, IS_PRIME[n]),
            macro_road[:, n], macro_prime[:, n], tail_mom[:, n], np.full(N, ZONE_ID[n])
        ])

    return X, road_counts, prime_counts
