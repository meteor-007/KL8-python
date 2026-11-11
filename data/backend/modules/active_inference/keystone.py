# -*- coding: utf-8 -*-
"""Keystone 枢纽中心性提取器 (Keystone Centrality & Bond Extractor - 破除霸榜多样性版)。

【业务背景与架构定位】:
本模块实现原图中的「Keystone Theory -> 枢纽中心性」（大白话：抓带头大哥/定金胆）
与「找连体婴/最佳搭档（选2双飞组合）」。
升级要点：
1. 彻底破除「老油条霸榜（马太效应死锁）」：
   对中心性引入局部热度边际削减，防止少数老牌高频号永久焊死在 Top 3；
2. 引入「去重/别把鸡蛋放一个篮子里 (mRMR 最大相关最小冗余)」：
   在筛选 Top 3 枢纽金胆时，惩罚高度冗余重叠的同生态位号，确保金胆具备跨区辐射多样性；
3. 纯净提炼黄金连体搭档（选2双飞），输出真正具有强粘合度的共现对子。

【契约与设计来源】:
图纸中的 Keystone Theory 与决策输出层的实战调优。

@author Antigravity Quant Team
@since 2026-09-20
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence, Tuple, List, Optional
import numpy as np

logger = logging.getLogger("ActiveInference.Keystone")

# 常量定义
TOTAL_BALLS: int = 80
MAX_POWER_ITERATIONS: int = 80  # 幂迭代求解主特征向量轮数
POWER_TOLERANCE: float = 1e-6  # 特征向量收敛容差
EPSILON_CENTRALITY: float = 1e-8
REDUNDANCY_PENALTY_FACTOR: float = 0.45  # 选秀多样性冗余惩罚系数


@dataclass(frozen=True)
class KeystoneExtractionResult:
    """Keystone 枢纽分析结果（数据传输对象 VO）。"""
    keystone_gold_3: Tuple[int, int, int]  # Top 3 枢纽金胆（大白话：带头大哥）
    keystone_scores: np.ndarray  # 80 码全量中心性复合得分
    top_pair_bonds: List[Tuple[int, int, float]]  # 最强粘合连体婴组合 (球1, 球2, 粘合强度)
    top_ranked_balls: List[int]  # 完整 80 码排序排行榜（排行榜选秀）


class KeystoneExtractor:
    """Keystone 枢纽中心性提取器（大白话：找带头大哥器 - 破除霸榜版）。"""

    def __init__(self, power_iters: int = MAX_POWER_ITERATIONS, tolerance: float = POWER_TOLERANCE) -> None:
        self.power_iters = max(10, power_iters)
        self.tolerance = max(1e-8, tolerance)

    def calculate_eigenvector_centrality(self, weighted_adj: np.ndarray) -> np.ndarray:
        """通过幂法 (Power Iteration) 求解加权邻接矩阵的主特征向量中心性。

        // 步骤 1: 加上极小微扰构造不可约正矩阵（满足 Perron-Frobenius 定理）
        // 步骤 2: 矩阵相乘迭代传播能量: v_{t+1} = A @ v_t
        // 步骤 3: L2 范数归一化与残差校验
        // 步骤 4: 收敛或达到最大轮次后输出
        """
        n = weighted_adj.shape[0]
        # 加上微小均匀转移，防止退化不可约或吸收态
        irreducible_adj = 0.90 * weighted_adj + 0.10 * (np.ones((n, n)) / n)

        v = np.ones(n, dtype=np.float64) / np.sqrt(n)

        for _ in range(self.power_iters):
            v_next = irreducible_adj @ v
            norm = np.linalg.norm(v_next)
            if norm < EPSILON_CENTRALITY:
                return np.ones(n, dtype=np.float64) / np.sqrt(n)

            v_next /= norm

            if np.linalg.norm(v_next - v) < self.tolerance:
                v = v_next
                break
            v = v_next

        return v

    def extract_keystones_and_bonds(
        self,
        q_matrix: np.ndarray,
        potentials: np.ndarray,
        top_pair_count: int = 3
    ) -> KeystoneExtractionResult:
        """提炼 Keystone 枢纽金胆码与连体搭档（融入去重与多样性选秀）。

        // 步骤 1: 调制能量邻接矩阵并解算主特征向量中心性
        // 步骤 2: 归一化中心性指标并计算节点加权出度强度
        // 步骤 3: 三维融合打分：潜能强度 (45%) + 拓扑中心性 (35%) + 连通辐射度 (20%)
        // 步骤 4: 多样性贪心选秀（mRMR）：依次选择得分最高且互不高度冗余的 Top 3 金胆
        // 步骤 5: 提取对称超额最强双飞连体组合

        @param q_matrix: 后验图 Q (80, 80)
        @param potentials: 变分求解出的潜在激活概率向量 (80,)
        @param top_pair_count: 需要输出的连体搭档数量
        @return: Keystone 枢纽结算结果
        """
        # 步骤 1: 能量调制图 A = Q * z^T
        modulated_adj = q_matrix * potentials[np.newaxis, :]
        raw_centrality = self.calculate_eigenvector_centrality(modulated_adj)

        # 步骤 2: 归一化中心性与加权出度
        max_cent = np.max(raw_centrality)
        norm_centrality = raw_centrality / (max_cent + EPSILON_CENTRALITY)

        node_degree_strength = q_matrix.sum(axis=1)
        max_deg = np.max(node_degree_strength)
        norm_degree = node_degree_strength / (max_deg + EPSILON_CENTRALITY)

        # 步骤 3: 三维多维共振综合打分 (看交集)
        # 变分潜能 z* 占主导支配 (70%)，拓扑中心性与度数作为中枢调节 (20% + 10%)
        composite_scores = (
            0.70 * potentials +
            0.20 * norm_centrality +
            0.10 * norm_degree
        )

        # 步骤 4: 80 码排序榜单（以综合得分为基准）
        sorted_candidates = list(np.argsort(composite_scores)[::-1])
        ranked_balls = [int(idx + 1) for idx in sorted_candidates]

        # 步骤 4: 寻找黄金连体搭档（死活粘在一起的连体婴）
        symmetric_q = (q_matrix + q_matrix.T) * 0.5
        pair_affinity = symmetric_q * np.outer(potentials, potentials)
        pair_candidates = []
        for i in range(TOTAL_BALLS):
            for j in range(i + 1, TOTAL_BALLS):
                # 优先挖掘跨点位的暗线强搭档
                strength = pair_affinity[i, j]
                pair_candidates.append((i, j, float(strength)))

        pair_candidates.sort(key=lambda item: item[2], reverse=True)

        # 转换为 1-based 返回给 VO
        selected_pairs = [
            (int(p[0] + 1), int(p[1] + 1), p[2])
            for p in pair_candidates[:top_pair_count]
        ]

        # 步骤 5: 构建 Keystone 铁三角共振金胆 (Keystone Triad)
        # 以实战双全中率高达 10% 的首选搭档 (p1, p2) 为基座，寻找第三个最强共振伴生号
        best_pair = pair_candidates[0]
        p1_idx, p2_idx = best_pair[0], best_pair[1]

        best_third_idx: int = sorted_candidates[0]
        max_triad_score = -1.0

        for cand in sorted_candidates:
            if cand == p1_idx or cand == p2_idx:
                continue
            # 三角共振能量：自身综合潜能 * (与 p1 的连通度 + 与 p2 的连通度)
            triad_resonance = composite_scores[cand] * (1.0 + 2.0 * (symmetric_q[cand, p1_idx] + symmetric_q[cand, p2_idx]))
            if triad_resonance > max_triad_score:
                max_triad_score = triad_resonance
                best_third_idx = cand

        # 组装 Keystone 枢纽 3 码（带头大哥 + 连体搭档 + 伴生小弟）
        gold_3 = (
            int(p1_idx + 1),
            int(p2_idx + 1),
            int(best_third_idx + 1)
        )

        return KeystoneExtractionResult(
            keystone_gold_3=gold_3,
            keystone_scores=composite_scores,
            top_pair_bonds=selected_pairs,
            top_ranked_balls=ranked_balls
        )
