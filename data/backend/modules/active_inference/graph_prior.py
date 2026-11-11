# -*- coding: utf-8 -*-
"""FlyWire 先验图谱构建器 (FlyWire Prior Graph Builder - 纯净超额互信息版)。

【业务背景与架构定位】:
本模块实现变分自由能公式中的先验分布骨架 P(FlyWire)（大白话：老祖宗祖训大底图）。
升级要点：
杜绝把“路人甲随机碰巧同框（基准概率 6.01%）”误认为“连体搭档”。
通过引入点互信息（Pointwise Mutual Information, PMI / Lift 提升度），
将千期历史共现矩阵和一阶马尔可夫转移矩阵（找跟班）与纯随机期望值进行对冲，
只提炼出统计显著大于随机期望的“超额共现与超额转移”，
形成高信噪比、纯净且能真实反映号码暗线绑定的先验骨架矩阵。

【契约与设计来源】:
变分自由能公式第二项：D_KL[Q || P(FlyWire)]。

@author Antigravity Quant Team
@since 2026-09-20
"""

from __future__ import annotations

import os
import logging
from typing import Sequence, Tuple, Optional
import numpy as np

# 日志记录器
logger = logging.getLogger("ActiveInference.GraphPrior")

# 常量定义：快乐8号码总数与基准参数（杜绝魔法数字）
TOTAL_BALLS: int = 80
BALLS_PER_DRAW: int = 20
BALL_MIN_VAL: int = 1
BALL_MAX_VAL: int = 80
EPSILON_SMOOTH: float = 1e-6  # 狄利克雷平滑系数
NEIGHBOR_DECAY_WEIGHT: float = 0.05  # 邻居号码物理扩散权重（看邻居）
CO_OCCURRENCE_LIFT_THRESHOLD: float = 1.02  # 超额共现启动门限（超越随机独立 2% 以上才算真搭档）
TRANSITION_LIFT_THRESHOLD: float = 1.02  # 超额转移启动门限


class GraphPriorBuilder:
    """FlyWire 先验图谱构建器（大白话：全历史纯净神经骨架底图生成器）。

    核心职责：
    从全量历史开奖序列中提取超额关联特征，输出纯净的 80x80 先验共现转移矩阵 P(FlyWire)。
    """

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        """初始化图谱构建器。

        @param cache_dir: 缓存目录路径，若提供则会自动持久化或加载先验矩阵
        """
        self.cache_dir = cache_dir
        if self.cache_dir and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)

    def build_prior_matrix(
        self,
        historical_draws: Sequence[Sequence[int]],
        use_cache: bool = True
    ) -> np.ndarray:
        """根据历史开奖列表构建或加载纯净 P(FlyWire) 先验概率矩阵。

        // 步骤 1: 参数防守校验，确保样本数量充足
        // 步骤 2: 检查是否有磁盘缓存（增加版本指纹防读旧版）
        // 步骤 3: 统计单球出号频次与同期共现、跨期转移原始频次
        // 步骤 4: 扣除随机独立期望，提炼超额共现 Lift 与超额转移 Lift（超额互信息提纯）
        // 步骤 5: 叠加物理邻居扩散（看邻居），做 Laplace 狄利克雷平滑与行和归一化

        @param historical_draws: 按时序排列的开奖号码二维列表，每期恰好 20 个球
        @param use_cache: 是否启用磁盘高速缓存
        @return: 形状为 (80, 80) 的纯净正定先验概率分布矩阵 P
        """
        # 步骤 1: 防守性校验
        total_draw_count = len(historical_draws) if historical_draws else 0
        if not historical_draws or total_draw_count < 10:
            raise ValueError(
                f"[GraphPriorBuilder] 历史开奖样本数量过少 ({total_draw_count})，"
                f"无法构建可靠的 FlyWire 先验图谱（大白话：样本太少，算不出老祖宗祖训）"
            )

        cache_path = os.path.join(
            self.cache_dir, f"flywire_pure_prior_v2_n{total_draw_count}.npy"
        ) if self.cache_dir else None

        # 步骤 2: 命中缓存直接返回
        if use_cache and cache_path and os.path.exists(cache_path):
            try:
                cached_prior = np.load(cache_path)
                if cached_prior.shape == (TOTAL_BALLS, TOTAL_BALLS):
                    logger.info(f"成功加载 FlyWire 纯净先验矩阵缓存: {cache_path}")
                    return cached_prior
            except Exception as cache_err:
                logger.warning(f"读取先验缓存异常，将重新计算: {cache_err}")

        # 步骤 3: 累积单球频次、全局共现矩阵与时序转移矩阵
        single_ball_counts = np.zeros(TOTAL_BALLS, dtype=np.float64)
        raw_co_occurrence = np.zeros((TOTAL_BALLS, TOTAL_BALLS), dtype=np.float64)
        raw_transition = np.zeros((TOTAL_BALLS, TOTAL_BALLS), dtype=np.float64)

        prev_draw_set: Optional[set[int]] = None

        for raw_draw in historical_draws:
            # 过滤与安全转换：球号转为 0-based 索引 (0..79)
            valid_ball_indices = [
                int(ball) - 1 for ball in raw_draw
                if BALL_MIN_VAL <= int(ball) <= BALL_MAX_VAL
            ]
            valid_ball_set = set(valid_ball_indices)

            # 3.1 累加单球频次
            for i in valid_ball_indices:
                single_ball_counts[i] += 1.0

            # 3.2 同期共现频次统计（找连体婴/最佳搭档）
            for i in valid_ball_indices:
                for j in valid_ball_indices:
                    if i != j:
                        raw_co_occurrence[i, j] += 1.0

            # 3.3 跨期一阶转移频次统计（找跟班：昨天出 i，今天出 j）
            if prev_draw_set is not None:
                for prev_ball in prev_draw_set:
                    for curr_ball in valid_ball_set:
                        raw_transition[prev_ball, curr_ball] += 1.0

            prev_draw_set = valid_ball_set

        # 步骤 4: 超额互信息提纯（剔除 6.01% 的随机碰巧路人甲）
        # 两个号随机碰巧共现的期望频次: E[i, j] = (C_i * C_j) / N
        expected_co_matrix = np.outer(single_ball_counts, single_ball_counts) / float(total_draw_count)
        expected_co_matrix[expected_co_matrix < EPSILON_SMOOTH] = EPSILON_SMOOTH

        # 共现提升度 Lift
        co_lift_matrix = raw_co_occurrence / expected_co_matrix
        # 仅保留显著高于随机期望的超额部分（高于门限才保留，其余截断为 0）
        excess_co_matrix = np.maximum(0.0, co_lift_matrix - CO_OCCURRENCE_LIFT_THRESHOLD)

        # 转移提升度（找跟班）：昨天出 i，今天出任意号的基准期望为 20/80 = 25%
        # 期望转移频次 E_trans[i, j] = C_i * (C_j / N)
        expected_trans_matrix = np.outer(single_ball_counts, single_ball_counts) / float(total_draw_count)
        expected_trans_matrix[expected_trans_matrix < EPSILON_SMOOTH] = EPSILON_SMOOTH
        trans_lift_matrix = raw_transition / expected_trans_matrix
        excess_trans_matrix = np.maximum(0.0, trans_lift_matrix - TRANSITION_LIFT_THRESHOLD)

        # 步骤 5: 空间拓扑邻居平滑（看邻居：i 号与 i-1、i+1 存在走势连带）
        spatial_diffusion = np.zeros((TOTAL_BALLS, TOTAL_BALLS), dtype=np.float64)
        for i in range(TOTAL_BALLS):
            left_neighbor = max(0, i - 1)
            right_neighbor = min(TOTAL_BALLS - 1, i + 1)
            spatial_diffusion[i, left_neighbor] += NEIGHBOR_DECAY_WEIGHT
            spatial_diffusion[i, right_neighbor] += NEIGHBOR_DECAY_WEIGHT

        # 融合超额网络：超额共现 0.65 + 超额转移 0.25 + 邻域扩散 0.10
        fused_skeleton = (
            0.65 * excess_co_matrix +
            0.25 * excess_trans_matrix +
            0.10 * (spatial_diffusion * (np.mean(excess_co_matrix) + EPSILON_SMOOTH))
        )

        # 加上狄利克雷平滑微扰并归一化
        smoothed_graph = fused_skeleton + EPSILON_SMOOTH
        np.fill_diagonal(smoothed_graph, 0.0)  # 对角线清零
        smoothed_graph += EPSILON_SMOOTH

        row_sums = smoothed_graph.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0.0] = 1.0
        normalized_prior = smoothed_graph / row_sums

        # 写入缓存
        if cache_path:
            try:
                np.save(cache_path, normalized_prior)
                logger.info(f"已持久化 FlyWire 纯净先验矩阵至: {cache_path}")
            except Exception as write_err:
                logger.warning(f"缓存 FlyWire 纯净先验矩阵失败: {write_err}")

        return normalized_prior
