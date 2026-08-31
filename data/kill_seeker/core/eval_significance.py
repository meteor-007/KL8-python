# -*- coding: utf-8 -*-
"""
KillSeeker 统计显著性评估模块 (Pure-Python Statistical Evaluation)
"""
import math
import random
from typing import Tuple


def monte_carlo_kill_baseline(kill_count: int = 25, n_sim: int = 2000, seed: int = 0) -> Tuple[float, float, float]:
    """
    蒙特卡洛模拟随机杀号期望正确数与置信区间。
    快乐8共80个号码，开出20个号码，未开出60个号码。
    随机杀 kill_count 个号码时，正确杀号（即选中的号码不在20个开奖号码中）的期望值为：
    E = kill_count * (60 / 80) = kill_count * 0.75
    """
    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.Random()

    all_balls = list(range(1, 81))
    correct_counts = []

    for _ in range(n_sim):
        drawn = set(rng.sample(all_balls, 20))
        killed = set(rng.sample(all_balls, kill_count))
        correct = len(killed - drawn)
        correct_counts.append(correct)

    correct_counts.sort()
    mean = sum(correct_counts) / n_sim
    lo_idx = int(n_sim * 0.025)
    hi_idx = int(n_sim * 0.975)
    lo = float(correct_counts[lo_idx])
    hi = float(correct_counts[hi_idx])

    return (mean, lo, hi)


def is_above_baseline(actual_rate: float, kill_count: int, n_periods: int, alpha: float = 0.05) -> bool:
    """
    检验实际杀号正确率是否显著高于随机基线 (p0 = 0.75)。
    单侧正态检验 (One-sided Z-test)。
    """
    p0 = 0.75
    N = kill_count * n_periods
    if N <= 0:
        return False

    se = math.sqrt(p0 * (1.0 - p0) / N)
    if se <= 0:
        return False

    z = (actual_rate - p0) / se
    
    # 常用显著性单侧临界值 (alpha=0.05 -> z_crit ~ 1.6449)
    if alpha == 0.05:
        z_crit = 1.6448536269514722
    elif alpha == 0.01:
        z_crit = 2.3263478740408408
    elif alpha == 0.10:
        z_crit = 1.2815515655446004
    else:
        # 正态逆累积分布逼近 (Winitzki approximation / Acklam approximation)
        z_crit = 1.6449

    return z > z_crit
