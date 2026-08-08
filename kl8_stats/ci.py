# kl8_stats/ci.py
# -*- coding: utf-8 -*-
"""Wilson 二项置信区间。"""


def wilson_ci(k, n, z=1.96):
    """k 次成功 / n 次试验的 95% Wilson 置信区间。"""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))