# -*- coding: utf-8 -*-
"""
test_e2e_features.py — Tier 1: 功能契约单点测试 (Category-Partition & Feature Contracts)
=====================================================================================
【测试目标 (大白话)】：
  验证五大特征提取器（看势头、蹭热度、老经验、找搭档、防守雷区）、
  统一决策主脑（80维状态空间概率解算）、四级决策（金胆、选2、Top5、Top12）、
  自进化损失计算（Focal Loss残差纠偏）以及 Web 后端 API 的核心功能单点契约。
"""
import os
import sys
import unittest
import numpy as np
from fastapi.testclient import TestClient

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.core.unified_brain.feature_extractors import FeatureEngineeringLayer, NUM_TOTAL
from backend.core.unified_brain.unified_brain import UnifiedDecisionBrain
from backend.core.unified_brain.loss_and_backprop import UnifiedBrainEvolutionEngine
from backend.api.api_server import app


class TestTier1FeatureExtractors(unittest.TestCase):
    """五大物理特征提供器核心输出契约测试 (大白话：检查五个给主脑提供情报的师傅干活是否合规)"""

    @classmethod
    def setUpClass(cls):
        cls.data_root = PROJ_DIR
        cls.feature_layer = FeatureEngineeringLayer(cls.data_root)
        draws = cls.feature_layer.draws
        cls.target_period = (draws[-1]["period"] + 1) if draws else 2026234

    def test_01_time_inertia_extractor_contract(self):
        """1. 时序惯性张量 (大白话：看冷热势头) 输出契约验证"""
        f_time = self.feature_layer.extract_time_features(self.target_period, lambda_decay=0.95)
        self.assertIsInstance(f_time, np.ndarray)
        self.assertEqual(f_time.shape, (NUM_TOTAL,), "时序特征向量必须严格为 80 维")
        self.assertTrue(np.all(f_time >= 0.0) and np.all(f_time <= 1.0), "时序特征值必须归一化在 [0.0, 1.0] 之间")
        # 只要历史开奖非空，最大值应为 1.0
        if np.any(f_time > 0):
            self.assertAlmostEqual(np.max(f_time), 1.0, places=4, msg="最大值必须归一化为 1.0")

    def test_02_spatial_energy_extractor_contract(self):
        """2. 空间高斯能量密度势能 (大白话：蹭热度，看哪片区域扎堆) 输出契约验证"""
        f_space = self.feature_layer.extract_spatial_energy_features(self.target_period, sigma=2.5)
        self.assertIsInstance(f_space, np.ndarray)
        self.assertEqual(f_space.shape, (NUM_TOTAL,), "空间能量向量必须严格为 80 维")
        self.assertTrue(np.all(f_space >= 0.0) and np.all(f_space <= 1.0), "空间能量值必须在 [0.0, 1.0] 之间")
        if np.any(f_space > 0):
            self.assertAlmostEqual(np.max(f_space), 1.0, places=4, msg="最大值必须归一化为 1.0")

    def test_03_discrete_rule_extractor_contract(self):
        """3. 离散形态规则向量 (大白话：经典老经验与形态出击) 输出契约验证"""
        f_rule = self.feature_layer.extract_discrete_rule_features(self.target_period)
        self.assertIsInstance(f_rule, np.ndarray)
        self.assertEqual(f_rule.shape, (NUM_TOTAL,), "形态规则向量必须严格为 80 维")
        self.assertTrue(np.all(f_rule >= 0.0) and np.all(f_rule <= 1.0), "规则特征值必须在 [0.0, 1.0] 之间")

    def test_04_topological_cooccurrence_extractor_contract(self):
        """4. 拓扑共现与跟随粘性矩阵 (大白话：找跟班与连体搭档) 输出契约验证"""
        f_topo, co_matrix = self.feature_layer.extract_topological_cooccurrence(self.target_period, window=50)
        self.assertIsInstance(f_topo, np.ndarray)
        self.assertIsInstance(co_matrix, np.ndarray)
        self.assertEqual(f_topo.shape, (NUM_TOTAL,), "拓扑牵引向量必须严格为 80 维")
        self.assertEqual(co_matrix.shape, (NUM_TOTAL, NUM_TOTAL), "共现矩阵必须为 80x80 方阵")
        self.assertTrue(np.all(f_topo >= 0.0) and np.all(f_topo <= 1.0), "拓扑激发特征值必须在 [0.0, 1.0] 之间")
        # 验证共现矩阵对称性 (Co-occurrence 是无向双向共现)
        self.assertTrue(np.allclose(co_matrix, co_matrix.T), "双元共现矩阵必须严格对称")

    def test_05_defense_mask_extractor_contract(self):
        """5. 绝对防守禁区掩码 (KillSeeker 下架后恒为全安全全 True) 提取与契约验证"""
        kill_size = 15
        f_mask = self.feature_layer.extract_defense_mask(self.target_period, kill_size=kill_size)
        self.assertIsInstance(f_mask, np.ndarray)
        self.assertEqual(f_mask.shape, (NUM_TOTAL,), "雷区掩码向量必须严格为 80 维")
        self.assertEqual(f_mask.dtype, bool, "雷区掩码必须为布尔类型")
        killed_count = int(np.sum(~f_mask))
        self.assertEqual(killed_count, 0, "KillSeeker下架后杀号雷区数量必须为 0")


class TestTier1UnifiedBrainAndHierarchy(unittest.TestCase):
    """统一主脑概率解算与四级层级决策契约测试 (大白话：检验主脑算出来的概率和给出的4级方案)"""

    @classmethod
    def setUpClass(cls):
        cls.data_root = PROJ_DIR
        cls.brain = UnifiedDecisionBrain(cls.data_root)
        draws = cls.brain.feature_layer.draws
        cls.target_period = (draws[-1]["period"] + 1) if draws else 2026234
        cls.decision = cls.brain.solve_period(cls.target_period, sigma=2.5, lambda_decay=0.95, kill_size=15)

    def test_01_master_probability_distribution(self):
        """验证 80 维状态空间连续概率场与严格归一性 (大白话：所有合法号的概率加起来必须等于 1.0)"""
        probs_dict = self.decision["probabilities"]
        self.assertEqual(len(probs_dict), 80, "概率分布必须包含 1 到 80 全量号码")

        probs = np.array([float(probs_dict[str(i)]) for i in range(1, 81)])
        killed_nums = set(self.decision["killed_numbers"])
        
        # 1. 验证被杀号码概率严格物理归零
        for k in killed_nums:
            self.assertAlmostEqual(probs[k - 1], 0.0, places=5, msg=f"杀号雷区号码 {k} 概率必须严格物理归零 (P=0)")

        # 2. 验证总概率归一化
        total_prob = np.sum(probs)
        self.assertAlmostEqual(total_prob, 1.0, places=4, msg="全局概率之和必须严格归一为 1.0")

    def test_02_gold_single_decision_contract(self):
        """验证 ① 尖刀金胆 (1码) 输出契约 (大白话：必须是概率最高的安全号码)"""
        gold = self.decision["gold_single"]
        self.assertIsInstance(gold, int)
        self.assertTrue(1 <= gold <= 80, "金胆必须在 1-80 合法区间")
        self.assertNotIn(gold, self.decision["killed_numbers"], "金胆严禁出现在杀号雷区中")

        probs_dict = self.decision["probabilities"]
        gold_prob = probs_dict[str(gold)]
        max_prob = max(probs_dict.values())
        self.assertAlmostEqual(gold_prob, max_prob, places=4, msg="金胆必须对应全局概率场最高峰")

    def test_03_gold_pair_decision_contract(self):
        """验证 ② 黄金连体伴随 (定金选2) 输出契约 (大白话：以金胆为龙头，找到最强连体搭档)"""
        pair = self.decision["gold_pair"]
        self.assertIsInstance(pair, list)
        self.assertEqual(len(pair), 2, "黄金选2必须严格包含 2 个号码")
        self.assertEqual(pair[0], self.decision["gold_single"], "黄金选2第一个号码必须是尖刀金胆")
        self.assertNotEqual(pair[0], pair[1], "黄金选2的搭档球不能与金胆重复")
        self.assertTrue(all(1 <= x <= 80 for x in pair), "选2号码必须在 1-80 合法区间")
        self.assertTrue(all(x not in self.decision["killed_numbers"] for x in pair), "选2号码绝对不能在雷区中")

    def test_04_top5_assault_decision_contract(self):
        """验证 ③ 突击主力 (Top 5) 输出契约 (大白话：概率最高的前5个安全号码)"""
        top5 = self.decision["top5"]
        self.assertIsInstance(top5, list)
        self.assertEqual(len(top5), 5, "突击主力必须严格包含 5 个号码")
        self.assertEqual(len(set(top5)), 5, "突击主力号码必须互不相同")
        self.assertIn(self.decision["gold_single"], top5, "突击主力必须包含尖刀金胆")
        self.assertTrue(all(1 <= x <= 80 for x in top5), "Top5 号码必须在 1-80 合法区间")
        self.assertTrue(all(x not in self.decision["killed_numbers"] for x in top5), "Top5 严禁包含杀号雷区")

    def test_05_top12_balanced_decision_contract(self):
        """验证 ④ 8区覆盖底仓 (Top 12) 输出契约 (大白话：12码兼顾高概率与8大分区空间平衡)"""
        top12 = self.decision["top12_balanced"]
        self.assertIsInstance(top12, list)
        self.assertEqual(len(top12), 12, "底仓大底必须严格包含 12 个号码")
        self.assertEqual(len(set(top12)), 12, "Top12 号码必须互不相同")
        self.assertTrue(all(1 <= x <= 80 for x in top12), "Top12 号码必须在 1-80 合法区间")
        self.assertTrue(all(x not in self.decision["killed_numbers"] for x in top12), "Top12 严禁包含杀号雷区")

        # 验证 Top5 必须是 Top12 的子集
        top5_set = set(self.decision["top5"])
        top12_set = set(top12)
        self.assertTrue(top5_set.issubset(top12_set), "Top 12 必须完整包含 Top 5 核心主力")

        # 验证 8 大分区覆盖度 (1-10, 11-20, ..., 71-80)
        zones = {(x - 1) // 10 for x in top12}
        self.assertGreaterEqual(len(zones), 6, "12 码底仓必须覆盖至少 6 个以上不同分区，实现防守平衡")


class TestTier1EvolutionLossEngine(unittest.TestCase):
    """自进化 Focal Loss 残差与超参数微调契约测试 (大白话：检验根据昨天开奖算误差并改参数的引擎)"""

    def setUp(self):
        self.evo_engine = UnifiedBrainEvolutionEngine(PROJ_DIR)

    def test_01_nightly_calibration_contract(self):
        """验证夜间自进化反向校准接口契约"""
        draws = self.evo_engine.brain.feature_layer.draws
        target_period = (draws[-1]["period"] + 1) if draws else 2026234
        res = self.evo_engine.run_nightly_calibration(target_period)

        self.assertIsInstance(res, dict)
        self.assertIn("generation", res)
        self.assertIn("focal_loss", res)
        self.assertIn("sigma", res)
        self.assertIn("lambda_decay", res)
        self.assertIn("rationales", res)

        # 检查损失与参数合理性
        self.assertGreater(res["focal_loss"], 0.0, "Focal Loss 必须为正数")
        self.assertTrue(1.5 <= res["sigma"] <= 4.0, "空间高斯核宽 sigma 必须限制在安全区间 [1.5, 4.0]")
        self.assertTrue(0.85 <= res["lambda_decay"] <= 0.98, "时序半衰衰减率 lambda 必须限制在安全区间 [0.85, 0.98]")
        self.assertIsInstance(res["rationales"], list)
        self.assertGreater(len(res["rationales"]), 0, "必须给出参数微调的大白话理由")


class TestTier1WebAPICoreContracts(unittest.TestCase):
    """Web 后端 API 核心端点单点契约测试 (大白话：用客户端调接口，看返回格式对不对)"""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_api_unified_brain_contract(self):
        """验证 /api/quant/unified-brain 核心接口契约"""
        response = self.client.get("/api/quant/unified-brain")
        self.assertEqual(response.status_code, 200, "统一主脑 API 必须返回 200 OK")
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        payload = data.get("data", {})
        self.assertIn("gold_single", payload)
        self.assertIn("gold_pair", payload)
        self.assertIn("top5", payload)
        self.assertIn("top12_balanced", payload)
        self.assertIn("probabilities", payload)
        self.assertIn("killed_numbers", payload)

    def test_02_api_evolution_status_contract(self):
        """验证 /api/evolution/status 接口契约"""
        response = self.client.get("/api/evolution/status")
        self.assertEqual(response.status_code, 200, "自进化状态 API 必须返回 200 OK")
        data = response.json()
        self.assertEqual(data.get("status"), "ok")

    def test_03_api_system_status_contract(self):
        """验证 /api/system/status 接口契约"""
        response = self.client.get("/api/system/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ONLINE")
        self.assertIn("target_period", data)


if __name__ == "__main__":
    unittest.main()
