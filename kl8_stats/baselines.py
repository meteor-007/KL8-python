# kl8_stats/baselines.py
# -*- coding: utf-8 -*-
"""快乐8随机基线：超几何期望与多号命中概率。"""
from math import comb


def hypergeom_expect(k_keep, n_balls=80, n_draw=20):
    """随机选 k_keep 个号，开奖抽 n_draw 个，期望命中数。"""
    return k_keep * n_draw / n_balls


def hit_rate_at_least_one(k, n_balls=80, n_draw=20):
    """随机选 k 个号，开奖抽 n_draw 个，至少命中 1 个的概率（不放回超几何）。"""
    if k <= 0:
        return 0.0
    if k > n_balls:
        raise ValueError("k 不能超过 n_balls")
    return 1.0 - comb(n_balls - n_draw, k) / comb(n_balls, k)


def random_topk_hit_ci(k, n_balls=80, n_draw=20, z=1.96):
    """随机 Top-k 期望命中数与 95% 近似区间（超几何均值 ± 2σ）。"""
    from kl8_stats.ci import wilson_ci
    mean = hypergeom_expect(k, n_balls, n_draw)
    # 超几何方差: n_draw * (k/n) * (1 - k/n) * (n - n_draw)/(n - 1)
    frac = k / n_balls
    var = n_draw * frac * (1 - frac) * (n_balls - n_draw) / (n_balls - 1)
    sd = var ** 0.5
    return mean, mean - z * sd, mean + z * sd