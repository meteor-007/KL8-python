# KillSeeker/eval_significance.py
# -*- coding: utf-8 -*-
"""KillSeeker 显著性：随机杀号蒙特卡洛基线 + 二项检验。"""
import random
from kl8_stats.baselines import hypergeom_expect


def monte_carlo_kill_baseline(k_kill, n_balls=80, n_draw=20, n_sim=10000, seed=0):
    """随机杀 k_kill 个号（不中奖视角），正确杀号数分布。

    正确杀号 = 杀的号里没有出现在开奖号码中的个数。
    期望 = k_kill * (n_balls - n_draw) / n_balls = k_kill * 0.75。
    """
    rng = random.Random(seed)
    counts = []
    balls = list(range(1, n_balls + 1))
    for _ in range(n_sim):
        kill = set(rng.sample(balls, k_kill))
        drawn = set(rng.sample(balls, n_draw))
        counts.append(len(kill - drawn))
    mean = sum(counts) / n_sim
    sorted_c = sorted(counts)
    lo = sorted_c[int(0.025 * n_sim)]
    hi = sorted_c[int(0.975 * n_sim)]
    return mean, lo, hi


def is_above_baseline(hit_rate, k_kill, n_periods, alpha=0.05):
    """真实杀号率是否显著高于 75% 机会水平（单边二项检验近似）。"""
    # 用正态近似：p0=0.75, n=n_periods*k_kill 次试验
    import math
    p0 = 0.75
    n = n_periods * k_kill
    if n == 0:
        return False
    z = (hit_rate - p0) / math.sqrt(p0 * (1 - p0) / n)
    return z > 1.645  # 单边 5%