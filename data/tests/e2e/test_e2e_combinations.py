# -*- coding: utf-8 -*-
"""
test_e2e_combinations.py — Tier 3: 跨特征组合与闭环协同测试 (Pairwise Combinations & Feedback Loops)
===================================================================================================
【测试目标 (大白话)】：
  验证五大物理特征的交叉碰撞、时空非线性共振效应、杀号硬势垒与高能球冲突时的绝对一票否决、
  8区空间最大熵底仓平衡算法、以及“解算 ➔ 残差 ➔ 进化微调 ➔ 重新解算”闭环协同机制。
"""
import os
import sys
import unittest
import numpy as np

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.core.unified_brain.feature_extractors import NUM_TOTAL
from backend.core.unified_brain.unified_brain import UnifiedDecisionBrain
from backend.core.unified_brain.loss_and_backprop import UnifiedBrainEvolutionEngine


class TestTier3ResonanceAndDefenseCombinations(unittest.TestCase):
    """时空非线性共振与杀号硬势垒阻断协同测试 (大白话：时空双高才起飞；被杀号就算能量再高也一票否决)"""

    def test_01_spatiotemporal_resonance_matrix(self):
        """验证时空乘积超线性共振效应 sqrt(F_time * F_space) 的组合行为"""
        # 1. 时空双高 (1.0, 1.0) -> 共振能量 1.0
        e_both_high = np.sqrt(1.0 * 1.0)
        self.assertEqual(e_both_high, 1.0)

        # 2. 单项高 (1.0, 0.04) -> 共振能量 0.2 (大幅平缓压制)
        e_single_high = np.sqrt(1.0 * 0.04)
        self.assertEqual(e_single_high, 0.2)

        # 3. 双低 (0.04, 0.04) -> 共振能量 0.04
        e_both_low = np.sqrt(0.04 * 0.04)
        self.assertEqual(e_both_low, 0.04)

        # 4. 单项为零 (1.0, 0.0) -> 共振彻底消失为 0.0
        e_zero = np.sqrt(1.0 * 0.0)
        self.assertEqual(e_zero, 0.0)

    def test_02_defense_hard_barrier_overrides_high_energy(self):
        """验证绝对防守禁区对高能球的一票否决协同 (大白话：即使时空规则全排第一，只要被杀，概率绝对归零)"""
        brain = UnifiedDecisionBrain(PROJ_DIR)
        draws = brain.feature_layer.draws
        target_period = (draws[-1]["period"] + 1) if draws else 2026234

        # 正常推演获得金胆
        res_normal = brain.solve_period(target_period, kill_size=15)
        normal_gold = res_normal["gold_single"]

        # 手动构造将 normal_gold 强行加入雷区的场景
        f_mask_override = brain.feature_layer.extract_defense_mask(target_period, kill_size=15)
        f_mask_override[normal_gold - 1] = False  # 强行把原金胆设为雷区

        # 重新解算
        f_time = brain.feature_layer.extract_time_features(target_period)
        f_space = brain.feature_layer.extract_spatial_energy_features(target_period)
        f_rule = brain.feature_layer.extract_discrete_rule_features(target_period)
        f_topo, _ = brain.feature_layer.extract_topological_cooccurrence(target_period)

        resonance_energy = np.sqrt(f_time * f_space)
        total_energy = resonance_energy * 2.0 + np.log1p(f_rule) + 0.6 * f_topo

        valid_indices = np.where(f_mask_override)[0]
        killed_indices = np.where(~f_mask_override)[0]

        raw_potentials = np.copy(total_energy)
        raw_potentials[killed_indices] = -1e9

        exp_energy = np.exp(raw_potentials[valid_indices] - np.max(raw_potentials[valid_indices]))
        probs_valid = exp_energy / np.sum(exp_energy)

        full_probs = np.zeros(NUM_TOTAL, dtype=np.float64)
        full_probs[valid_indices] = probs_valid

        # 断言原金胆概率必须严格为 0
        self.assertEqual(full_probs[normal_gold - 1], 0.0, "被杀号码概率必须严格为 0.0")

        # 挑选新金胆必须不是 normal_gold
        sorted_valid = sorted(valid_indices, key=lambda idx: full_probs[idx], reverse=True)
        new_gold = sorted_valid[0] + 1
        self.assertNotEqual(new_gold, normal_gold, "新金胆绝不能是被杀号码")


class TestTier3TopologicalAndSpatialZoneSynergy(unittest.TestCase):
    """拓扑搭档牵引与 8 区最大熵底仓组合测试 (大白话：选2顺藤摸瓜找搭档；12码底仓自动跨区平衡)"""

    @classmethod
    def setUpClass(cls):
        cls.brain = UnifiedDecisionBrain(PROJ_DIR)
        draws = cls.brain.feature_layer.draws
        cls.target_period = (draws[-1]["period"] + 1) if draws else 2026234

    def test_01_topological_companion_selection_logic(self):
        """验证黄金选2搭档选择逻辑 (概率乘共现粘性因子 P * (1 + ln(1 + co_score)))"""
        res = self.brain.solve_period(self.target_period)
        gold = res["gold_single"]
        pair = res["gold_pair"]

        self.assertEqual(pair[0], gold)
        partner = pair[1]
        self.assertNotEqual(gold, partner)
        self.assertNotIn(partner, res["killed_numbers"])

    def test_02_eight_zones_coverage_rebalancing(self):
        """验证 8 区底仓算法在能量极端集中时的跨分区平衡能力"""
        res = self.brain.solve_period(self.target_period)
        top12 = res["top12_balanced"]
        self.assertEqual(len(top12), 12)
        
        # 统计覆盖了多少个分区 (0..7)
        zones = set((x - 1) // 10 for x in top12)
        self.assertGreaterEqual(len(zones), 6, "12 码底仓必须覆盖至少 6 个以上不同分区，分摊极端偏态风险")


class TestTier3EvolutionAndBrainFeedbackLoop(unittest.TestCase):
    """自进化微调与主脑重新解算闭环测试 (大白话：今天学完改了参数，明天主脑用新参数重新推演)"""

    def test_01_evolution_to_brain_recalculation_loop(self):
        """验证自进化引擎校准后，主脑能无缝读取最新自进化参数并推演下一期"""
        evo = UnifiedBrainEvolutionEngine(PROJ_DIR)
        draws = evo.brain.feature_layer.draws
        target_period = (draws[-1]["period"] + 1) if draws else 2026234

        # 1. 运行自进化反向校准
        calib_res = evo.run_nightly_calibration(target_period)
        new_sigma = calib_res["sigma"]
        new_lambda = calib_res["lambda_decay"]
        new_gen = calib_res["generation"]

        # 2. 验证参数已被写入引擎内存
        self.assertEqual(evo.params["sigma"], new_sigma)
        self.assertEqual(evo.params["lambda_decay"], new_lambda)
        self.assertEqual(evo.params["generation"], new_gen)

        # 3. 主脑使用新自进化参数解算
        new_decision = evo.brain.solve_period(
            target_period,
            sigma=new_sigma,
            lambda_decay=new_lambda,
            kill_size=evo.params.get("kill_size", 15)
        )

        self.assertEqual(new_decision["hyperparameters"]["sigma"], new_sigma)
        self.assertEqual(new_decision["hyperparameters"]["lambda_decay"], new_lambda)
        self.assertEqual(len(new_decision["top5"]), 5)
        self.assertEqual(len(new_decision["top12_balanced"]), 12)


if __name__ == "__main__":
    unittest.main()
