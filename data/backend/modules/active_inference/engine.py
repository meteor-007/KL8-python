# -*- coding: utf-8 -*-
"""变分神经主动推理主控引擎 (Active Inference Main Engine)。

【业务背景与架构定位】:
本模块是《变分神经主动推理图预测模块》的主控核心类，完整实现原图中的
「H-E-A-D -> 主动推理决策」四步闭环体系：
  - H (Hypothesis，假设网络): 基于全历史 FlyWire 构建长期先验大底拓扑；
  - E (Evidence，验算证据): 吸收近期 30 期滑动开奖样本，执行拓扑弹性重连；
  - A (Action / Inference，变分推断): 调用 ACT-UCA 变分算法，最小化自由能 F 并审计 KL 散度；
  - D (Decision，决策输出): 结合 Keystone 枢纽中心性，生成 Top 3 金胆、Top 5 优选、
                            Top 12 底池与黄金连体搭档（选2双飞）。

【契约与设计来源】:
系统顶层接口，可供每日流水线（Nightly Pipeline）、独立脚本或回测引擎调用。

@author Antigravity Quant Team
@since 2026-09-20
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Sequence, List, Tuple, Dict, Any, Optional
import numpy as np

from .graph_prior import GraphPriorBuilder
from .dynamic_rewire import DynamicRewirer
from .free_energy_cavi import FreeEnergyOptimizer, FreeEnergyOptimizationResult
from .keystone import KeystoneExtractor, KeystoneExtractionResult

logger = logging.getLogger("ActiveInference.Engine")


@dataclass(frozen=True)
class ActiveInferencePredictionResult:
    """主动推理预测结算总账单（对外暴露视图对象 VO）。"""
    target_issue: str  # 目标预测期号
    golden_keystones_3: Tuple[int, int, int]  # Top 3 枢纽金胆（大白话：带头大哥）
    predicted_top5: List[int]  # Top 5 变分优选号码
    predicted_top12: List[int]  # Top 12 变分底池号码
    best_pair_bonds: List[Tuple[int, int, float]]  # 黄金选2连体双飞搭档及强度
    free_energy: float  # 最终变分自由能 F（天平打分值）
    kl_divergence: float  # Q 与 P 的相对熵 (D_KL)
    is_market_regime_shift: bool  # 是否发出「大环境变盘了」预警
    summary_report: str  # 大白话实操点评简报


class ActiveInferenceEngine:
    """变分神经主动推理主控引擎（大白话：主动推理操盘主机）。"""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        recent_window_size: int = 30,
        kl_lambda: float = 0.35,
        graph_gamma: float = 0.25
    ) -> None:
        """装配初始化主动推理引擎各子系统组件。"""
        self.prior_builder = GraphPriorBuilder(cache_dir=cache_dir)
        self.rewirer = DynamicRewirer(window_size=recent_window_size)
        self.optimizer = FreeEnergyOptimizer(kl_lambda=kl_lambda, graph_gamma=graph_gamma)
        self.keystone_extractor = KeystoneExtractor()

    def run_prediction(
        self,
        all_draws_asc: Sequence[Sequence[int]],
        target_issue: str = "NEXT"
    ) -> ActiveInferencePredictionResult:
        """执行 H-E-A-D 主动推理预测全流程。

        // 步骤 1: H 环节 (Hypothesis) —— 构建/加载 FlyWire 先验图谱 P(FlyWire)
        // 步骤 2: E 环节 (Evidence) —— 摄取近期开奖时序证据，执行拓扑弹性动态图重连 Q
        // 步骤 3: A 环节 (Action / Inference) —— 运行 ACT-UCA 变分算法，解出各球潜能 z* 与自由能 F
        // 步骤 4: D 环节 (Decision) —— 提取 Keystone 枢纽中心性，生成金胆、Top 榜单与选2双飞
        // 步骤 5: 组装大白话操盘点评与结构化结果

        @param all_draws_asc: 按时间**升序**排列的历史开奖序列（最老在前，最新在后）
        @param target_issue: 待预测的目标期号标识
        @return: 结构化的预测结算对象
        """
        # 边界与空安全前置防御
        if not all_draws_asc or len(all_draws_asc) < 15:
            raise ValueError(
                f"[ActiveInferenceEngine] 开奖样本不足 ({len(all_draws_asc) if all_draws_asc else 0} < 15)，"
                f"无法启动主动推理决策闭环！"
            )

        # 步骤 1: H 阶段 —— 全脑先验骨架
        logger.info("[H 环节: 假设网络] 正在构建/加载 FlyWire 先验拓扑骨架...")
        prior_p = self.prior_builder.build_prior_matrix(all_draws_asc)

        # 步骤 2: E 阶段 —— 证据输入与拓扑弹性重连
        logger.info("[E 环节: 验算证据] 摄取近卫军滑动证据，执行拓扑弹性动态重连与 EF/RW 特征提取...")
        posterior_q, ef_norm, rw_norm = self.rewirer.rewire_network(all_draws_asc, prior_p)

        # 步骤 3: A 阶段 —— 变分自由能极小化求解
        logger.info("[A 环节: 变分推断] 启动 ACT-UCA 坐标上升求解器，融合双核先验极小化自由能 F...")
        optimization_res: FreeEnergyOptimizationResult = self.optimizer.optimize_potentials(
            ef_momentum=ef_norm,
            rw_rebound=rw_norm,
            q_matrix=posterior_q,
            prior_matrix=prior_p
        )

        # 步骤 4: D 阶段 —— Keystone 枢纽提取与决策输出
        logger.info("[D 环节: 决策输出] 提取 Keystone 枢纽中心性，筛选带头大哥与连体搭档...")
        keystone_res: KeystoneExtractionResult = self.keystone_extractor.extract_keystones_and_bonds(
            q_matrix=posterior_q,
            potentials=optimization_res.optimal_potentials,
            top_pair_count=3
        )

        # 组装推荐序列
        gold_3 = keystone_res.keystone_gold_3
        top_5 = keystone_res.top_ranked_balls[:5]
        top_12 = keystone_res.top_ranked_balls[:12]
        pair_bonds = keystone_res.top_pair_bonds

        # 步骤 5: 生成大白话操盘点评
        gold_str = "、".join(f"{b:02d}" for b in gold_3)
        top5_str = "、".join(f"{b:02d}" for b in top_5)
        pair_desc_list = [f"({p[0]:02d}, {p[1]:02d})" for p in pair_bonds]
        pair_str = "，".join(pair_desc_list)

        regime_comment = (
            "【风控警告】KL 散度超标（大白话：大环境变盘了！），庄家盘口发生剧烈偏移，建议防守轻仓！"
            if optimization_res.is_market_regime_shift
            else "【盘面平稳】KL 散度在基线以内（大白话：走势守规矩），先验骨架稳定，可正常按策略执行。"
        )

        summary_text = (
            f"[目标期号]: {target_issue}\n"
            f"[Keystone 枢纽金胆 (Top 3)]: {gold_str} (大白话：带头大哥，处于能量流动核心，出它带出一窝)\n"
            f"[变分极优 Top 5]: {top5_str}\n"
            f"[黄金连体搭档 (选2双飞)]: {pair_str} (大白话：死活粘在一起的连体婴)\n"
            f"[结算自由能 F]: {optimization_res.total_free_energy:.2f} | 散度 D_KL: {optimization_res.kl_divergence:.3f}\n"
            f"[盘口态势]: {regime_comment}"
        )

        return ActiveInferencePredictionResult(
            target_issue=target_issue,
            golden_keystones_3=gold_3,
            predicted_top5=top_5,
            predicted_top12=top_12,
            best_pair_bonds=pair_bonds,
            free_energy=optimization_res.total_free_energy,
            kl_divergence=optimization_res.kl_divergence,
            is_market_regime_shift=optimization_res.is_market_regime_shift,
            summary_report=summary_text
        )
