# -*- coding: utf-8 -*-
"""
隐能量场计算模块 (Energy Field)
================================
从 audit/v3_trinity_audit.py 迁移至此，
使其归入核心计算层而非审计层。

包含:
  - calc_energy_field(): 号码能量场分布（含邻号扩散）
  - calc_omission_sigmoid(): 遗漏Sigmoid回补分数
"""
import math
from typing import Dict, List


def calc_energy_field(history: List[Dict],
                      decay_rate: float = 0.5,
                      diffusion_factor: float = 0.4) -> Dict[int, float]:
    """计算号码的能量场分布——隐能量场

    Args:
        history: 开奖历史 [{issue, numbers}, ...], 降序(最新在前)
        decay_rate: 时间衰减率
        diffusion_factor: 邻号扩散因子

    Returns:
        {1: 5.2, 2: 3.1, ...}  80个号码的能量分数
    """
    field = {n: 0.0 for n in range(1, 81)}
    for i, h in enumerate(history[:30]):
        w = (decay_rate ** i) * (1 + diffusion_factor * (30 - i) / 30)
        for n in h['numbers']:
            field[n] += w
            # 邻号扩散
            for d in range(1, 4):
                if n + d <= 80:
                    field[n + d] += w * (diffusion_factor ** d) * 0.5
                if n - d >= 1:
                    field[n - d] += w * (diffusion_factor ** d) * 0.5
    return field


def calc_omission_sigmoid(history: List[Dict],
                          lookback: int = 50,
                          steepness: float = 0.3,
                          midpoint: float = 8.0) -> Dict[int, float]:
    """遗漏Sigmoid回补分数

    Args:
        history: 开奖历史, 降序
        lookback: 回看期数
        steepness: Sigmoid陡度
        midpoint: Sigmoid中点

    Returns:
        {1: 0.45, 2: 0.12, ...}  80个号码的遗漏回补分数
    """
    rw_scores = {}
    for n in range(1, 81):
        gap = 0
        for h in history[:lookback]:
            if n in h['numbers']:
                break
            gap += 1
        rw_scores[n] = 1.0 / (1.0 + math.exp(-steepness * (gap - midpoint)))
    return rw_scores
