# -*- coding: utf-8 -*-
"""
隐能量场计算模块 (Energy Field)
================================
包含:
  - calc_energy_field(): 号码能量场分布（含邻号扩散 + 反过热衰减惩罚）
  - calc_overheating_penalty(): 极度过热号码均值回归惩罚乘数
  - calc_omission_sigmoid(): 遗漏Sigmoid回补分数
"""
import math
from typing import Dict, List


def calc_overheating_penalty(history: List[Dict],
                             lookback: int = 5,
                             max_hits_threshold: int = 3) -> Dict[int, float]:
    """
    计算极度过热号码的均值回归衰减惩罚
    大白话：近5期开出>=3次的超大热门，火久必冷，施加平滑降权，避免追高被套
    """
    counts = {n: 0 for n in range(1, 81)}
    for h in history[:lookback]:
        for n in h.get('numbers', []):
            counts[n] += 1
    penalties = {}
    for n in range(1, 81):
        c = counts[n]
        if c >= max_hits_threshold:
            # 连续或极高频开出，施加平滑指数衰减
            penalties[n] = math.exp(-(c - max_hits_threshold + 1) * 0.40)
        else:
            penalties[n] = 1.0
    return penalties


def calc_energy_field(history: List[Dict],
                      decay_rate: float = 0.5,
                      diffusion_factor: float = 0.4,
                      apply_overheating_decay: bool = True) -> Dict[int, float]:
    """计算号码的能量场分布——隐能量场

    Args:
        history: 开奖历史 [{issue, numbers}, ...], 降序(最新在前)
        decay_rate: 时间衰减率
        diffusion_factor: 邻号扩散因子
        apply_overheating_decay: 是否启用反过热衰减惩罚

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

    if apply_overheating_decay and history:
        penalties = calc_overheating_penalty(history)
        for n in range(1, 81):
            field[n] *= penalties.get(n, 1.0)

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
