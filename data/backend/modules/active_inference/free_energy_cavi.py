# -*- coding: utf-8 -*-
"""ACT-UCA 变分自由能优化器 (ACT-UCA Free Energy CAVI Optimizer - 双核先验版)。

【业务背景与架构定位】:
本模块实现变分自由能公式与 ACT-UCA 变分求解算法（大白话：天平打分器 + 轮流调参数）：
    F = E_Q[-log P(开奖|结构)] + D_KL[Q || P(FlyWire)]
升级核心：
将 EF（隐能量场/近期动量）与 RW（纯净池定胆/遗漏回补）作为双核经验先验注入变分推断中，
在变分迭代中通过拓扑邻域传播能量，同时受物理期望值约 20 颗球的宏观约束，
求解出既能捕捉走势斜率、又能吃准冷号反弹的最优激活潜能向量 z*。

@author Antigravity Quant Team
@since 2026-09-20
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence, Tuple, Optional
import numpy as np

logger = logging.getLogger("ActiveInference.FreeEnergyCAVI")

# 常量定义
TOTAL_BALLS: int = 80
EXPECTED_DRAW_SIZE: float = 20.0
MAX_CAVI_ITERATIONS: int = 40
CONVERGENCE_TOLERANCE: float = 1e-5
DEFAULT_KL_PENALTY_LAMBDA: float = 0.25
DEFAULT_GRAPH_SMOOTH_GAMMA: float = 0.25
DEFAULT_TEMPERATURE: float = 1.20
DEFAULT_MOMENTUM_ALPHA: float = 0.65
EPSILON_NUMERICAL: float = 1e-9
ALERT_KL_DIVERGENCE_THRESHOLD: float = 2.20


@dataclass(frozen=True)
class FreeEnergyOptimizationResult:
    """变分自由能优化结算结果（数据传输对象 VO）。"""
    optimal_potentials: np.ndarray  # 80 个球的变分后验激活概率向量 (80,)
    total_free_energy: float  # 最终收敛的变分自由能 F
    nll_loss: float  # 似然拟合负对数损失
    kl_divergence: float  # Q 与 P 的相对熵 (D_KL)
    is_converged: bool  # 是否在容差内收敛
    iterations_run: int  # 实际迭代轮数
    is_market_regime_shift: bool  # 是否触发变盘预警


class FreeEnergyOptimizer:
    """ACT-UCA 变分自由能优化器（大白话：天平打分求解器 - 双核版）。"""

    def __init__(
        self,
        kl_lambda: float = DEFAULT_KL_PENALTY_LAMBDA,
        graph_gamma: float = DEFAULT_GRAPH_SMOOTH_GAMMA,
        temperature: float = DEFAULT_TEMPERATURE,
        momentum_alpha: float = DEFAULT_MOMENTUM_ALPHA,
        max_iters: int = MAX_CAVI_ITERATIONS,
        tolerance: float = CONVERGENCE_TOLERANCE
    ) -> None:
        self.kl_lambda = max(0.01, kl_lambda)
        self.graph_gamma = max(0.01, graph_gamma)
        self.temperature = max(0.5, temperature)
        self.momentum_alpha = np.clip(momentum_alpha, 0.1, 0.9)
        self.max_iters = max(5, max_iters)
        self.tolerance = max(1e-7, tolerance)

    def calculate_kl_divergence(self, q_matrix: np.ndarray, p_matrix: np.ndarray) -> float:
        """计算两个图拓扑矩阵之间的全域相对熵 D_KL[Q || P]。"""
        q_safe = np.clip(q_matrix, EPSILON_NUMERICAL, 1.0)
        p_safe = np.clip(p_matrix, EPSILON_NUMERICAL, 1.0)
        kl_elements = q_safe * np.log(q_safe / p_safe)
        total_kl = float(np.sum(kl_elements) / TOTAL_BALLS)
        return max(0.0, total_kl)

    def optimize_potentials(
        self,
        ef_momentum: np.ndarray,
        rw_rebound: np.ndarray,
        q_matrix: np.ndarray,
        prior_matrix: np.ndarray
    ) -> FreeEnergyOptimizationResult:
        """运行基于 EF+RW 双核先验与拓扑共振的 ACT-UCA 变分优化。

        // 步骤 1: 构建双核物理先验分布: mu_0 = 0.55 * EF + 0.45 * RW
        // 步骤 2: 计算 D_KL[Q || P] 相对熵
        // 步骤 3: 映射到 Logit 空间启动 CAVI 坐标上升迭代
        // 步骤 4: 拓扑能量传播 + 温度退火 + 动量平滑 + 期望出球总量软约束
        // 步骤 5: 结算自由能 F 与变盘状态

        @param ef_momentum: 短期时序隐能量场归一化向量 (80,)
        @param rw_rebound: 遗漏 Sigmoid 回补势能归一化向量 (80,)
        @param q_matrix: 动态后验拓扑矩阵 Q (80, 80)
        @param prior_matrix: FlyWire 纯净先验矩阵 P (80, 80)
        @return: 变分自由能优化结算结果
        """
        # 步骤 1: 融合 EF 与 RW 构成出号潜能先验
        dual_prior = 0.55 * ef_momentum + 0.45 * rw_rebound
        # 融入 0.25 的均匀基线，避免极值 0 或 1
        smoothed_prior = 0.75 * dual_prior + 0.25 * 0.25
        smoothed_prior = np.clip(smoothed_prior, 0.04, 0.96)

        # 步骤 2: 计算 D_KL
        kl_val = self.calculate_kl_divergence(q_matrix, prior_matrix)

        # 步骤 3: 初始化
        current_z = smoothed_prior.copy()
        base_logit = np.log(smoothed_prior / (1.0 - smoothed_prior))

        prev_energy: float = float("inf")
        converged: bool = False
        iteration_count: int = 0

        # 步骤 4: 变分坐标上升 (CAVI)
        for it in range(self.max_iters):
            iteration_count = it + 1

            # 拓扑共振
            neighbor_resonance = q_matrix @ current_z

            # 结合邻域传播能量与温度退火
            raw_logits = (base_logit + self.graph_gamma * neighbor_resonance) / self.temperature
            raw_logits = np.clip(raw_logits, -5.0, 5.0)

            # Sigmoid 激活候选潜能
            candidate_z = 1.0 / (1.0 + np.exp(-raw_logits))

            # 动量阻尼更新
            updated_z = self.momentum_alpha * candidate_z + (1.0 - self.momentum_alpha) * current_z

            # 物理期望守恒软校准（总和向 20 靠拢）
            z_sum = np.sum(updated_z)
            if z_sum > EPSILON_NUMERICAL:
                scale_factor = (EXPECTED_DRAW_SIZE / z_sum) ** 0.40
                updated_z = np.clip(updated_z * scale_factor, 0.02, 0.98)

            # 计算损失与自由能
            eps = 1e-4
            nll_loss = -float(
                np.sum(
                    smoothed_prior * np.log(np.clip(updated_z, eps, 1.0)) +
                    (1.0 - smoothed_prior) * np.log(np.clip(1.0 - updated_z, eps, 1.0))
                )
            )
            graph_energy = float(0.5 * self.graph_gamma * np.sum((updated_z - neighbor_resonance) ** 2))
            current_free_energy = nll_loss + self.kl_lambda * kl_val + graph_energy

            if abs(prev_energy - current_free_energy) < self.tolerance:
                converged = True
                current_z = updated_z
                break

            prev_energy = current_free_energy
            current_z = updated_z

        # 步骤 5: 最终结算
        is_shift = kl_val >= ALERT_KL_DIVERGENCE_THRESHOLD

        final_nll = -float(
            np.sum(
                smoothed_prior * np.log(np.clip(current_z, 1e-4, 1.0)) +
                (1.0 - smoothed_prior) * np.log(np.clip(1.0 - current_z, 1e-4, 1.0))
            )
        )
        final_free_energy = final_nll + self.kl_lambda * kl_val

        return FreeEnergyOptimizationResult(
            optimal_potentials=current_z,
            total_free_energy=final_free_energy,
            nll_loss=final_nll,
            kl_divergence=kl_val,
            is_converged=converged,
            iterations_run=iteration_count,
            is_market_regime_shift=is_shift
        )
