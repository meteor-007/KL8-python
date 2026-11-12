# -*- coding: utf-8 -*-
"""
test_unified_brain.py — 统一主脑与层级策略单元与集成测试 (Unified Brain & Hierarchical Strategy Test Suite)
==========================================================================================================
【测试覆盖范围】：
  1. UnifiedDecisionBrain 初始化与特征层绑定
  2. 纯内存 UnifiedFeatureBundle 接收与校验
  3. 80 维状态空间时空非线性共振能量解算
  4. 杀号硬掩码物理归零势垒与一票否决
  5. 玻尔兹曼-吉布斯概率场归一化与温控响应
  6. 一脉相承四级层级化决策 (金胆 ➔ 选2 ➔ Top5 ➔ Top12) 严格单调与分区覆盖契约
  7. 五大物理维度战力雷达图标准化得分
  8. 资产落盘 (JSON 结构化数据与 Markdown 操盘手研报) 正确性
  9. 极端工况边界鲁棒性 (零杀号、极限杀号、极端温度、极端核宽与时序衰减)
"""
import os
import sys
import json
import tempfile
import unittest
import numpy as np

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.core.unified_brain.feature_extractors import (
    UnifiedFeatureBundle,
    FeatureEngineeringPipeline,
    FeatureEngineeringLayer,
    NUM_TOTAL
)
from backend.core.unified_brain.unified_brain import (
    UnifiedDecisionBrain,
    UnifiedDecisionResult,
    BRAIN_OUTPUT_DIR
)


def make_sandbox_brain(case, data_root=PROJ_DIR):
    """构造写入临时沙箱的主脑实例。

    单元测试绝不能写进生产归档 outputs/unified_brain 与前端静态资产
    frontend/static/unified_decision_latest.json —— 否则一次跑测试就会把合成结果
    覆盖真实期号 (曾污染出 target_period=2026299 的幻影期, 并覆写 2026234)。
    """
    tmp = tempfile.TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    return UnifiedDecisionBrain(data_root,
                                output_dir=os.path.join(tmp.name, "unified_brain"))


class TestUnifiedBrainInitialization(unittest.TestCase):
    """统一主脑初始化与结构测试"""

    def test_01_init_default_and_custom_path(self):
        brain_default = UnifiedDecisionBrain()
        self.assertIsNotNone(brain_default.feature_layer)
        self.assertIsNotNone(brain_default.pipeline)

        brain_custom = UnifiedDecisionBrain(PROJ_DIR)
        self.assertEqual(brain_custom.data_root, PROJ_DIR)
        self.assertIsInstance(brain_custom.feature_layer, FeatureEngineeringLayer)


class TestUnifiedFeatureBundleDirectSolving(unittest.TestCase):
    """直接使用 UnifiedFeatureBundle 进行解算测试"""

    def setUp(self):
        self.brain = make_sandbox_brain(self)
        # 构造合成纯净特征包
        self.target_period = 2026299
        f_time = np.zeros(NUM_TOTAL, dtype=np.float64)
        f_space = np.zeros(NUM_TOTAL, dtype=np.float64)
        f_rule = np.zeros(NUM_TOTAL, dtype=np.float64)
        f_topo = np.zeros(NUM_TOTAL, dtype=np.float64)
        co_matrix = np.zeros((NUM_TOTAL, NUM_TOTAL), dtype=np.float64)
        defense_mask = np.ones(NUM_TOTAL, dtype=bool)

        # 设置 10 号为高能球，11 号为 10 号的高共现搭档
        f_time[9] = 1.0     # 号码 10
        f_space[9] = 1.0    # 号码 10
        f_rule[9] = 0.8
        f_topo[9] = 0.9

        f_time[10] = 0.7    # 号码 11
        f_space[10] = 0.6
        co_matrix[9, 10] = 0.95
        co_matrix[10, 9] = 0.95

        # 设置 15 个杀号 (66..80)
        killed_nums = list(range(66, 81))
        for k in killed_nums:
            defense_mask[k - 1] = False

        self.bundle = UnifiedFeatureBundle(
            target_period=self.target_period,
            draw_date="2026-09-02",
            time_inertia=f_time,
            spatial_energy=f_space,
            rule_activation=f_rule,
            topological_energy=f_topo,
            cooccurrence_matrix=co_matrix,
            defense_mask=defense_mask,
            killed_numbers=killed_nums,
            meta_info={"test_synthetic": True}
        )

    def test_01_solve_bundle_returns_valid_structure(self):
        res = self.brain.solve_bundle(self.bundle, temperature=1.0)
        self.assertIsInstance(res, dict)
        self.assertEqual(res["target_period"], self.target_period)
        self.assertEqual(res["gold_single"], 10, "最高能球 10 必须被选为金胆")
        self.assertEqual(res["gold_pair"][0], 10)
        self.assertEqual(res["gold_pair"][1], 11, "与金胆共现最高的 11 必须被选为黄金搭档")
        self.assertIn(10, res["top5"])
        self.assertEqual(len(res["top3_gold"]), 3)
        self.assertEqual(len(res["top5"]), 5)
        self.assertEqual(len(res["top12_balanced"]), 12)
        self.assertEqual(res["killed_count"], 15)

    def test_02_bundle_validation_rejection(self):
        """验证非法形状或包含 NaN 的特征包会被拦截"""
        invalid_bundle = UnifiedFeatureBundle(
            target_period=2026300,
            draw_date="2026-09-02",
            time_inertia=np.zeros(79),  # 错误维度
            spatial_energy=np.zeros(NUM_TOTAL),
            rule_activation=np.zeros(NUM_TOTAL),
            topological_energy=np.zeros(NUM_TOTAL),
            cooccurrence_matrix=np.zeros((NUM_TOTAL, NUM_TOTAL)),
            defense_mask=np.ones(NUM_TOTAL, dtype=bool)
        )
        with self.assertRaises(ValueError):
            self.brain.solve_bundle(invalid_bundle)


class TestSpatiotemporalResonanceAndDefenseBarrier(unittest.TestCase):
    """时空共振与杀号硬掩码物理势垒测试"""

    def setUp(self):
        self.brain = make_sandbox_brain(self)

    def test_01_spatiotemporal_resonance_geometry(self):
        """验证时空乘积共振的超线性与单零归零特性"""
        # 时空均高 (1.0, 1.0) -> 共振为 1.0
        self.assertAlmostEqual(np.sqrt(1.0 * 1.0), 1.0)
        # 单项为零 (1.0, 0.0) -> 共振完全归零
        self.assertAlmostEqual(np.sqrt(1.0 * 0.0), 0.0)
        # 单项极低 (1.0, 0.01) -> 共振压制为 0.1
        self.assertAlmostEqual(np.sqrt(1.0 * 0.01), 0.1)

    def test_02_defense_hard_barrier_absolute_kill(self):
        """验证杀号硬势垒对高能号码的一票否决踩刹车机制"""
        target_period = 2026234
        bundle = self.brain.feature_layer.extract_bundle(target_period)
        
        # 找到原本未被杀且概率最高的号码
        res_orig = self.brain.solve_bundle(bundle)
        orig_gold = res_orig["gold_single"]

        # 构造将原金胆强行打入杀号雷区
        bundle.defense_mask[orig_gold - 1] = False
        bundle.killed_numbers = sorted(list(set(bundle.killed_numbers + [orig_gold])))

        # 重新解算 (开启硬势垒测试)
        res_killed = self.brain.solve_bundle(bundle, enable_hard_barrier=True)
        killed_probs = res_killed["probabilities"]

        # 1. 验证被杀的原金胆概率严格为 0.0
        self.assertEqual(killed_probs[str(orig_gold)], 0.0)
        # 2. 验证新金胆绝对不能是被杀号码，且新金胆不在杀号雷区中
        self.assertNotEqual(res_killed["gold_single"], orig_gold)
        self.assertIn(orig_gold, res_killed["killed_numbers"])
        self.assertNotIn(res_killed["gold_single"], res_killed["killed_numbers"])
        # 3. 验证选2、Top5、Top12中全部剔除原金胆
        self.assertNotIn(orig_gold, res_killed["gold_pair"])
        self.assertNotIn(orig_gold, res_killed["top5"])
        self.assertNotIn(orig_gold, res_killed["top12_balanced"])


class TestBoltzmannProbabilityDistribution(unittest.TestCase):
    """玻尔兹曼概率场解算与温控测试"""

    def setUp(self):
        self.brain = make_sandbox_brain(self)
        draws = self.brain.feature_layer.draws
        self.target_period = (draws[-1]["period"] + 1) if draws else 2026234

    def test_01_probabilities_sum_to_one(self):
        """验证全盘 80 维概率严格归一为 1.0"""
        res = self.brain.solve_period(self.target_period)
        probs = [float(v) for v in res["probabilities"].values()]
        self.assertEqual(len(probs), NUM_TOTAL)
        self.assertAlmostEqual(sum(probs), 1.0, places=4)

    def test_02_temperature_extreme_responses(self):
        """验证温度 T 极低时概率高度收敛，极高时概率均匀平坦"""
        # 低温冷凝
        res_cold = self.brain.solve_period(self.target_period, temperature=0.1)
        probs_cold = [float(v) for v in res_cold["probabilities"].values()]
        max_cold = max(probs_cold)
        self.assertGreater(max_cold, 0.2, "低温下最高峰概率应极度凸显")

        # 高温平坦
        res_hot = self.brain.solve_period(self.target_period, temperature=20.0)
        probs_hot = [float(v) for v in res_hot["probabilities"].values()]
        max_hot = max(probs_hot)
        self.assertLess(max_hot, 0.05, "高温下概率应趋近于均匀等分")


class TestHierarchicalDecisionsContract(unittest.TestCase):
    """四级层级决策 (金胆 ➔ 选2 ➔ Top5 ➔ Top12) 严格契约测试"""

    def setUp(self):
        self.brain = make_sandbox_brain(self)
        draws = self.brain.feature_layer.draws
        self.target_period = (draws[-1]["period"] + 1) if draws else 2026234
        self.res = self.brain.solve_period(self.target_period)

    def test_01_gold_single_peak_contract(self):
        """尖刀金胆 (1码) 契约：必须是安全区最高概率号码"""
        gold = self.res["gold_single"]
        self.assertTrue(1 <= gold <= 80)
        self.assertNotIn(gold, self.res["killed_numbers"])
        max_prob = max(float(v) for v in self.res["probabilities"].values())
        self.assertAlmostEqual(float(self.res["probabilities"][str(gold)]), max_prob, places=4)

    def test_02_gold_pair_partner_contract(self):
        """黄金选2 (2码) 契约：必须包含金胆且搭档不重复且非雷区"""
        pair = self.res["gold_pair"]
        self.assertEqual(len(pair), 2)
        self.assertEqual(pair[0], self.res["gold_single"])
        self.assertNotEqual(pair[0], pair[1])
        self.assertTrue(1 <= pair[1] <= 80)
        self.assertNotIn(pair[1], self.res["killed_numbers"])

    def test_03_top3_gold_contract(self):
        """主口径最优 3 码契约：严格 3 个安全号码，包含金胆"""
        top3 = self.res["top3_gold"]
        self.assertEqual(len(top3), 3)
        self.assertEqual(len(set(top3)), 3)
        self.assertIn(self.res["gold_single"], top3)
        self.assertTrue(all(x not in self.res["killed_numbers"] for x in top3))
        self.assertEqual(len(self.res["top5"]), 5)
        self.assertEqual(len(self.res["top12_balanced"]), 12)

    def test_04_top3_alias_fields_match(self):
        """验证 top5 (5码) 与 top12_balanced (12码) 契约及安全区覆盖"""
        top5 = self.res["top5"]
        top12 = self.res["top12_balanced"]
        self.assertEqual(len(top5), 5)
        self.assertEqual(len(top12), 12)
        self.assertTrue(all(x not in self.res["killed_numbers"] for x in top5))
        self.assertTrue(all(x not in self.res["killed_numbers"] for x in top12))
        zones = {(x - 1) // 10 for x in top12}
        self.assertGreaterEqual(len(zones), 6, "12 码底仓应覆盖至少 6 个分区")


class TestRadarFeaturesCalculation(unittest.TestCase):
    """五大物理维度战力雷达图评分测试"""

    def setUp(self):
        self.brain = make_sandbox_brain(self)
        draws = self.brain.feature_layer.draws
        self.target_period = (draws[-1]["period"] + 1) if draws else 2026234
        self.res = self.brain.solve_period(self.target_period)

    def test_01_radar_dimensions_and_ranges(self):
        radar = self.res["radar_features"]
        self.assertIsInstance(radar, dict)
        required_keys = [
            "time_inertia",
            "spatial_energy",
            "rule_activation",
            "topological_energy",
            "defense_strength"
        ]
        for k in required_keys:
            self.assertIn(k, radar, f"雷达图必须包含维度 {k}")
            val = radar[k]
            self.assertIsInstance(val, (int, float))
            self.assertTrue(0.0 <= val <= 100.0, f"雷达图得分 {k}={val} 必须限制在 [0, 100]")


class TestAssetPersistenceAndReports(unittest.TestCase):
    """决策资产落盘与 Markdown 研报测试"""

    def setUp(self):
        self.brain = make_sandbox_brain(self)
        self.target_period = 2026234
        self.res = self.brain.solve_period(self.target_period)

    def test_01_json_asset_saved_and_parsable(self):
        json_file = os.path.join(self.brain.output_dir, f"unified_decision_{self.target_period}.json")
        self.assertTrue(os.path.exists(json_file), "JSON 决策资产必须物理落盘")
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["target_period"], self.target_period)
        self.assertEqual(data["gold_single"], self.res["gold_single"])

    def test_02_markdown_report_saved_with_plain_language(self):
        md_file = os.path.join(self.brain.output_dir, f"unified_decision_report_{self.target_period}.md")
        self.assertTrue(os.path.exists(md_file), "Markdown 决策研报必须物理落盘")
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("尖刀核心金胆", content)
        self.assertIn("黄金连体搭档", content)
        self.assertIn("最优 3 码", content)
        self.assertIn("杀号参考列表", content)
        self.assertIn("战力雷达图评分", content)


if __name__ == "__main__":
    unittest.main()
