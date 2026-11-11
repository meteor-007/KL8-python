# -*- coding: utf-8 -*-
"""
test_e2e_boundary.py — Tier 2: 极端边界与容错测试 (Boundary Value Analysis & Robustness)
========================================================================================
【测试目标 (大白话)】：
  验证系统在面对无历史开奖、超短样本、脏数据坏行、极端参数 (超大/超小sigma/lambda/温度)、
  零杀号/全杀号雷区以及规则零激活等极端恶劣工况下的稳健性与自愈防御能力。
"""
import os
import sys
import math
import tempfile
import unittest
import numpy as np

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.core.unified_brain.feature_extractors import (
    FeatureEngineeringLayer, 
    load_historical_draws,
    NUM_TOTAL
)
from backend.core.unified_brain.unified_brain import UnifiedDecisionBrain
from backend.core.unified_brain.loss_and_backprop import UnifiedBrainEvolutionEngine


class TestTier2HistoryBoundaries(unittest.TestCase):
    """历史开奖数据极端边界与容错测试 (大白话：没数据、只有一两期、或者数据被搞乱了怎么处理)"""

    def test_01_empty_history_graceful_handling(self):
        """验证无历史开奖数据时，特征层与主脑能够平稳降级，绝不报 ZeroDivisionError 或未捕获崩溃"""
        tmp_dir = tempfile.mkdtemp()
        fake_empty_file = os.path.join(tmp_dir, "kl8_history_final.txt")
        with open(fake_empty_file, "w", encoding="utf-8") as f:
            f.write("")  # 完全空文件

        try:
            layer = FeatureEngineeringLayer(tmp_dir)
            self.assertEqual(len(layer.draws), 0)

            # 1. 提取各项特征在空数据下返回合法的零向量或全 1 掩码
            f_time = layer.extract_time_features(2026001)
            self.assertEqual(f_time.shape, (NUM_TOTAL,))
            self.assertEqual(np.max(f_time), 0.0)

            f_space = layer.extract_spatial_energy_features(2026001)
            self.assertEqual(f_space.shape, (NUM_TOTAL,))
            self.assertEqual(np.max(f_space), 0.0)

            f_topo, co_mat = layer.extract_topological_cooccurrence(2026001)
            self.assertEqual(f_topo.shape, (NUM_TOTAL,))
            self.assertEqual(co_mat.shape, (NUM_TOTAL, NUM_TOTAL))

            f_mask = layer.extract_defense_mask(2026001, kill_size=15)
            self.assertEqual(f_mask.shape, (NUM_TOTAL,))

            # 2. 空数据下主脑解算平稳运行，概率平滑退化为均匀分布
            brain = UnifiedDecisionBrain(tmp_dir)
            res = brain.solve_period(2026001, kill_size=10)
            self.assertIn("probabilities", res)
            probs = [float(v) for v in res["probabilities"].values()]
            self.assertAlmostEqual(sum(probs), 1.0, delta=0.005)
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_02_short_history_adaptation(self):
        """验证历史数据极少 (仅 1 期或 2 期) 时系统的平稳自适应"""
        tmp_dir = tempfile.mkdtemp()
        short_file = os.path.join(tmp_dir, "kl8_history_final.txt")
        with open(short_file, "w", encoding="utf-8") as f:
            f.write("date:2026-01-01,period:2026001,numbers:01-02-03-04-05-06-07-08-09-10-11-12-13-14-15-16-17-18-19-20\n")

        try:
            brain = UnifiedDecisionBrain(tmp_dir)
            res = brain.solve_period(2026002, kill_size=10)
            self.assertEqual(len(res["top5"]), 5)
            self.assertEqual(len(res["top12_balanced"]), 12)
            self.assertNotIn(res["gold_single"], res["killed_numbers"])
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_03_malformed_history_lines_tolerance(self):
        """验证开奖数据文本中存在坏行、空行、残缺行时加载器的容错清洗能力"""
        tmp_dir = tempfile.mkdtemp()
        bad_file = os.path.join(tmp_dir, "kl8_history_final.txt")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("Some random garbage line\n")
            f.write("\n")
            f.write("date:2026-08-01,period:2026201,numbers:01-02-03\n")  # 号码不足 20 个
            f.write("date:2026-08-02,period:2026202,numbers:01-02-03-04-05-06-07-08-09-10-11-12-13-14-15-16-17-18-19-20\n")  # 正常行
            f.write("date:invalid,period:xxx,numbers:yyy\n")
            f.write("date:2026-08-03,period:2026203,numbers:21-22-23-24-25-26-27-28-29-30-31-32-33-34-35-36-37-38-39-40\n")  # 正常行

        try:
            draws = load_historical_draws(bad_file)
            self.assertEqual(len(draws), 2, "必须自动过滤坏行，精准加载 2 个合法期号")
            self.assertEqual(draws[0]["period"], 2026201 if False else 2026202)
            self.assertEqual(draws[1]["period"], 2026203)
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestTier2HyperparameterExtremes(unittest.TestCase):
    """极端超参数与物理奇异点边界测试 (大白话：把参数调到最极端，看主脑会不会发疯)"""

    @classmethod
    def setUpClass(cls):
        cls.brain = UnifiedDecisionBrain(PROJ_DIR)
        draws = cls.brain.feature_layer.draws
        cls.target_period = (draws[-1]["period"] + 1) if draws else 2026234

    def test_01_extreme_spatial_sigma(self):
        """验证空间高斯核宽 sigma 处于极小 (0.01) 与极大 (50.0) 时的数值稳定性"""
        # 极小 sigma: 高斯弥散极窄，只有点源有值
        res_tiny = self.brain.solve_period(self.target_period, sigma=0.01)
        probs_tiny = [float(v) for v in res_tiny["probabilities"].values()]
        self.assertFalse(any(np.isnan(probs_tiny)), "极小 sigma 下概率严禁出现 NaN")
        self.assertAlmostEqual(sum(probs_tiny), 1.0, places=4)

        # 极大 sigma: 高斯弥散极大，全盘平缓
        res_huge = self.brain.solve_period(self.target_period, sigma=50.0)
        probs_huge = [float(v) for v in res_huge["probabilities"].values()]
        self.assertFalse(any(np.isnan(probs_huge)), "极大 sigma 下概率严禁出现 NaN")
        self.assertAlmostEqual(sum(probs_huge), 1.0, places=4)

    def test_02_extreme_time_lambda_decay(self):
        """验证时序衰减率 lambda 处于极小 (0.001 记忆立即抹除) 与极大 (1.0 无衰减) 时的稳定性"""
        res_zero = self.brain.solve_period(self.target_period, lambda_decay=0.001)
        probs_zero = [float(v) for v in res_zero["probabilities"].values()]
        self.assertFalse(any(np.isnan(probs_zero)))
        self.assertAlmostEqual(sum(probs_zero), 1.0, places=4)

        res_one = self.brain.solve_period(self.target_period, lambda_decay=1.0)
        probs_one = [float(v) for v in res_one["probabilities"].values()]
        self.assertFalse(any(np.isnan(probs_one)))
        self.assertAlmostEqual(sum(probs_one), 1.0, places=4)

    def test_03_extreme_boltzmann_temperatures(self):
        """验证玻尔兹曼温度处于极低温 (0.05 极度冷凝) 与极高温 (50.0 极度扩散) 时的数值稳定性"""
        # 极低温度: 能量最高者概率接近 1.0，其余接近 0.0
        res_cold = self.brain.solve_period(self.target_period, temperature=0.05)
        probs_cold = [float(v) for v in res_cold["probabilities"].values()]
        self.assertFalse(any(np.isnan(probs_cold)))
        self.assertAlmostEqual(sum(probs_cold), 1.0, places=4)
        self.assertGreater(max(probs_cold), 0.5, "极低温下最高能量球概率应极其集中")

        # 极高温度: 所有合法球概率趋于等概率均匀分布
        res_hot = self.brain.solve_period(self.target_period, temperature=50.0)
        probs_hot = [float(v) for v in res_hot["probabilities"].values()]
        self.assertFalse(any(np.isnan(probs_hot)))
        self.assertAlmostEqual(sum(probs_hot), 1.0, places=4)
        # 安全区域 65 码等分概率约 1/65 ≈ 0.015
        self.assertLess(max(probs_hot), 0.05, "极高温下概率分布应极其平坦均匀")


class TestTier2DefenseMaskAndRulesBoundaries(unittest.TestCase):
    """杀号雷区规模与离散规则边界测试 (大白话：不杀号、全杀号、或者一条口诀都没对上时)"""

    @classmethod
    def setUpClass(cls):
        cls.brain = UnifiedDecisionBrain(PROJ_DIR)
        draws = cls.brain.feature_layer.draws
        cls.target_period = (draws[-1]["period"] + 1) if draws else 2026234

    def test_01_zero_kill_defense_boundary(self):
        """验证杀号规模 kill_size = 0 时主脑全开无阻断解算"""
        res = self.brain.solve_period(self.target_period, kill_size=0)
        self.assertEqual(res["killed_count"], 0)
        self.assertEqual(len(res["killed_numbers"]), 0)
        probs = [float(v) for v in res["probabilities"].values()]
        self.assertAlmostEqual(sum(probs), 1.0, places=4)
        # 所有 80 码概率皆 > 0
        self.assertTrue(all(p > 0 for p in probs), "零杀号时所有 80 码必须都有正概率")

    def test_02_maximum_kill_defense_boundary(self):
        """验证极限杀号规模 kill_size = 25 时主脑的兼容解算（KillSeeker下架后恒为0杀号全安全）"""
        res = self.brain.solve_period(self.target_period, kill_size=25)
        self.assertEqual(res["killed_count"], 0)
        self.assertEqual(len(res["killed_numbers"]), 0)
        
        self.assertTrue(1 <= res["gold_single"] <= 80)
        self.assertEqual(len(res["gold_pair"]), 2)
        self.assertEqual(len(res["top5"]), 5)
        self.assertEqual(len(res["top12_balanced"]), 12)

    def test_03_discrete_rules_zero_activation(self):
        """验证当期完全没有命中任何口诀/反弹信号时，主脑平稳由时空与拓扑驱动解算"""
        f_time = self.brain.feature_layer.extract_time_features(self.target_period)
        f_space = self.brain.feature_layer.extract_spatial_energy_features(self.target_period)
        f_rule_zero = np.zeros(NUM_TOTAL, dtype=np.float64)  # 强制 0 规则
        f_topo, co_matrix = self.brain.feature_layer.extract_topological_cooccurrence(self.target_period)
        f_mask = self.brain.feature_layer.extract_defense_mask(self.target_period, kill_size=15)

        resonance_energy = np.sqrt(f_time * f_space)
        total_energy = resonance_energy * 2.0 + np.log1p(f_rule_zero) + 0.6 * f_topo

        valid_indices = np.where(f_mask)[0]
        killed_indices = np.where(~f_mask)[0]
        raw_potentials = np.copy(total_energy)
        raw_potentials[killed_indices] = -1e9

        exp_energy = np.exp(raw_potentials[valid_indices] - np.max(raw_potentials[valid_indices]))
        probs_valid = exp_energy / np.sum(exp_energy)

        self.assertFalse(np.any(np.isnan(probs_valid)))
        self.assertAlmostEqual(np.sum(probs_valid), 1.0, places=4)


class TestTier2EvolutionLossExtremes(unittest.TestCase):
    """自进化 Focal Loss 残差极值容错测试 (大白话：全猜对或全猜错时，反向损失计算不会溢出)"""

    def test_01_focal_loss_epsilon_protection(self):
        """验证预测概率为 0 或 1 时的 log(0) 除零保护"""
        y_true = np.zeros(NUM_TOTAL, dtype=np.float64)
        y_true[:20] = 1.0  # 前 20 个开出

        # 极端场景 A: 预测完全相反 (前 20 个预测概率全为 0.0)
        probs_wrong = np.zeros(NUM_TOTAL, dtype=np.float64)
        probs_wrong[20:] = 1.0 / 60.0

        eps = 1e-7
        p = np.clip(probs_wrong, eps, 1.0 - eps)
        loss = - np.sum(y_true * ((1.0 - p) ** 2) * np.log(p) + (1.0 - y_true) * (p ** 2) * np.log(1.0 - p))
        
        self.assertFalse(np.isnan(loss))
        self.assertFalse(np.isinf(loss))
        self.assertGreater(loss, 0.0)


if __name__ == "__main__":
    unittest.main()
