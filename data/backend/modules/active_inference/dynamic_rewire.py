# -*- coding: utf-8 -*-
"""拓扑弹性与动态图重连器 (Dynamic Graph Rewirer - 高频时序动量与遗漏回补版)。

【业务背景与架构定位】:
本模块实现图中标注的「拓扑弹性 -> 动态图重连」（大白话：近卫军见风使舵换搭档）。
实战升级核心：
1. 采用高频半衰时序衰减（半衰期约 2 期），让系统敏锐捕捉上一期和前两期的极速爆发走势；
2. 彻底解耦先验大底的死锁绑定，后验图 Q 专注反映当下正在结伴而行的号码网络；
3. 产出高动态的号码能量场 (EF) 与遗漏回补 (RW) 势能特征，为变分推断提供稳健双核底座。

@author Antigravity Quant Team
@since 2026-09-20
"""

from __future__ import annotations

import logging
import math
from typing import Sequence, Tuple, Optional, Dict
import numpy as np

logger = logging.getLogger("ActiveInference.DynamicRewire")

# 常量定义
TOTAL_BALLS: int = 80
BALL_MIN_VAL: int = 1
BALL_MAX_VAL: int = 80
DEFAULT_RECENT_WINDOW: int = 30
DECAY_RATE_FAST: float = 0.60  # 快速半衰因子 (0.60^t)，最强加权近 1~3 期
OVERHEATING_THRESHOLD: int = 3  # 近 5 期开出 >= 3 次启动极度过热惩罚
EPSILON_SAFE: float = 1e-6


class DynamicRewirer:
    """拓扑弹性动态图重连器（大白话：高频热度换搭档器）。"""

    def __init__(
        self,
        window_size: int = DEFAULT_RECENT_WINDOW,
        decay_factor: float = DECAY_RATE_FAST
    ) -> None:
        self.window_size = max(10, window_size)
        self.decay_factor = np.clip(decay_factor, 0.3, 0.85)

    def extract_momentum_and_rebound(
        self,
        recent_draws_asc: Sequence[Sequence[int]]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """提取 80 码的短期时序动量场 (EF) 与遗漏回补势能 (RW)。

        // 步骤 1: 转换为倒序（最新一期为索引 0）
        // 步骤 2: 计算反过热衰减惩罚（近 5 期开出 >= 3 次的火久必冷均值回归）
        // 步骤 3: 累加带时间快速半衰衰减的隐能量场 EF
        // 步骤 4: 计算每个球当前的遗漏期数，并通过非线性 Sigmoid 映射为回补分数 RW

        @param recent_draws_asc: 升序开奖序列
        @return: (ef_momentum, rw_rebound) 归一化特征向量
        """
        reversed_draws = list(reversed(recent_draws_asc))
        actual_len = len(reversed_draws)

        # 步骤 1: 计算反过热惩罚（近 5 期）
        recent_5 = reversed_draws[:min(5, actual_len)]
        counts_5 = np.zeros(TOTAL_BALLS, dtype=np.float64)
        for d in recent_5:
            for b in d:
                if BALL_MIN_VAL <= int(b) <= BALL_MAX_VAL:
                    counts_5[int(b) - 1] += 1.0

        overheat_penalty = np.ones(TOTAL_BALLS, dtype=np.float64)
        for i in range(TOTAL_BALLS):
            c = counts_5[i]
            if c >= OVERHEATING_THRESHOLD:
                # 平滑指数衰减，防止追高挨套
                overheat_penalty[i] = math.exp(-(c - OVERHEATING_THRESHOLD + 1) * 0.45)

        # 步骤 2: 累加隐能量场 (EF)
        ef_scores = np.zeros(TOTAL_BALLS, dtype=np.float64)
        for t_idx, d in enumerate(reversed_draws[:min(self.window_size, actual_len)]):
            weight = (self.decay_factor ** t_idx)
            for b in d:
                idx = int(b) - 1
                if 0 <= idx < TOTAL_BALLS:
                    ef_scores[idx] += weight
                    # 邻号扩散（看邻居：左邻右舍各分得 20% 辐射能量）
                    if idx > 0:
                        ef_scores[idx - 1] += weight * 0.20
                    if idx < TOTAL_BALLS - 1:
                        ef_scores[idx + 1] += weight * 0.20

        # 施加反过热惩罚
        ef_scores *= overheat_penalty

        # 步骤 3: 遗漏 Sigmoid 回补势能 (RW)
        # 统计当前遗漏期数
        omissions = np.full(TOTAL_BALLS, actual_len, dtype=np.float64)
        for i in range(TOTAL_BALLS):
            b_num = i + 1
            for dist, d in enumerate(reversed_draws):
                if b_num in d:
                    omissions[i] = float(dist)
                    break

        # Sigmoid 回补映射：中心点 7 期，陡度 0.35（快乐8平均遗漏 4 期，7 期左右处于反弹爆发带）
        rw_scores = 1.0 / (1.0 + np.exp(-0.35 * (omissions - 7.0)))
        # 极冷号（遗漏 > 18 期）施加冷冻保护
        deep_freeze_mask = omissions > 18.0
        rw_scores[deep_freeze_mask] *= 0.50

        # Min-Max 归一化到 [0, 1]
        ef_norm = (ef_scores - np.min(ef_scores)) / (np.max(ef_scores) - np.min(ef_scores) + EPSILON_SAFE)
        rw_norm = (rw_scores - np.min(rw_scores)) / (np.max(rw_scores) - np.min(rw_scores) + EPSILON_SAFE)

        return ef_norm, rw_norm

    def rewire_network(
        self,
        recent_draws_asc: Sequence[Sequence[int]],
        prior_matrix: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """执行高频拓扑弹性动态重连，生成动态后验图 Q 与双核先验。

        @param recent_draws_asc: 升序开奖序列
        @param prior_matrix: FlyWire 纯净先验矩阵
        @return: (Q_posterior, ef_momentum, rw_rebound)
        """
        effective_draws = list(recent_draws_asc)[-self.window_size:]
        actual_len = len(effective_draws)
        if actual_len < 3:
            logger.warning("[DynamicRewirer] 近期样本不足，退回平滑先验")
            ef = np.full(TOTAL_BALLS, 0.5)
            rw = np.full(TOTAL_BALLS, 0.5)
            return prior_matrix.copy(), ef, rw

        # 提取 EF 动量场与 RW 回补场
        ef_norm, rw_norm = self.extract_momentum_and_rebound(effective_draws)

        # 计算带快速衰减的近期动态共现矩阵
        # 倒序遍历计算共现
        reversed_draws = list(reversed(effective_draws))
        dynamic_co_matrix = np.zeros((TOTAL_BALLS, TOTAL_BALLS), dtype=np.float64)

        for t_idx, d in enumerate(reversed_draws):
            w = self.decay_factor ** t_idx
            valid_indices = [int(b) - 1 for b in d if BALL_MIN_VAL <= int(b) <= BALL_MAX_VAL]
            for i in valid_indices:
                for j in valid_indices:
                    if i != j:
                        dynamic_co_matrix[i, j] += w

        # 节点状态调制：融合 EF 与 RW（综合活跃度）
        combined_activity = 0.55 * ef_norm + 0.45 * rw_norm
        activity_outer = np.outer(combined_activity, combined_activity)

        # 动态共现加成
        max_edge = np.max(dynamic_co_matrix)
        if max_edge > EPSILON_SAFE:
            norm_dynamic_edges = dynamic_co_matrix / max_edge
        else:
            norm_dynamic_edges = dynamic_co_matrix

        # 拓扑拉伸：只有两端节点都活跃，搭档连线才被大幅增强
        elastic_edges = norm_dynamic_edges * (1.0 + 1.5 * activity_outer)

        # 微量融合纯净先验（85% 近期动态 + 15% 历史超额先验，防止完全失真）
        q_raw = 0.85 * elastic_edges + 0.15 * prior_matrix + EPSILON_SAFE
        np.fill_diagonal(q_raw, 0.0)

        # 行和归一化
        row_sums = q_raw.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0.0] = 1.0
        normalized_q = q_raw / row_sums

        return normalized_q, ef_norm, rw_norm
