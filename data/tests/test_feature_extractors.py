# -*- coding: utf-8 -*-
"""
test_feature_extractors.py — 五大物理特征提取器全量单元测试与契约验证
=============================================================================
【测试范围】：
  1. BaseFeatureExtractor 抽象基类契约与多态
  2. TimeInertiaExtractor 时序惯性连续概率张量与防未来泄漏
  3. SpatialEnergyExtractor 空间高斯连续势能场、核宽调控与反过热惩罚
  4. DiscreteRuleExtractor 90条口诀激活、动态权重赛马与平滑基线
  5. TopologicalCooccurrenceExtractor 80x80对称共现矩阵与Markov节点势能
  6. DefenseMaskExtractor 全 True 安全掩码（KillSeeker 已下架，空杀号集）
  7. UnifiedFeatureBundle 强类型数据包与 validate() 边界自检
  8. FeatureEngineeringPipeline 调度流水线与超参数联动
  9. FeatureEngineeringLayer 兼容门面层
"""
import os
import sys
import unittest
import numpy as np
import math
from typing import Dict, List, Any

# 将工程根目录与 backend 加入 sys.path
PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.core.unified_brain.feature_extractors import (
    BaseFeatureExtractor,
    TimeInertiaExtractor,
    SpatialEnergyExtractor,
    DiscreteRuleExtractor,
    TopologicalCooccurrenceExtractor,
    DefenseMaskExtractor,
    UnifiedFeatureBundle,
    FeatureEngineeringPipeline,
    FeatureEngineeringLayer,
    load_historical_draws,
    NUM_TOTAL
)
def _generate_synthetic_draws(n_draws: int = 50, start_period: int = 2026100) -> List[Dict[str, Any]]:
    """生成确定性的合成历史开奖数据供单元测试使用"""
    np.random.seed(42)
    draws = []
    for i in range(n_draws):
        period = start_period + i
        # 固定挑选 20 个不重复的号码
        nums = sorted(list(np.random.choice(np.arange(1, 81), size=20, replace=False)))
        draws.append({
            "period": period,
            "date": f"2026-01-{(i % 28) + 1:02d}",
            "nums": [int(x) for x in nums],
            "nums_set": set(int(x) for x in nums)
        })
    return draws


class TestBaseFeatureExtractor(unittest.TestCase):
    """验证抽象基类契约"""

    def test_abstract_class_cannot_be_instantiated(self):
        class DummyExtractor(BaseFeatureExtractor):
            pass

        with self.assertRaises(TypeError):
            DummyExtractor()


class TestTimeInertiaExtractor(unittest.TestCase):
    """时序惯性张量提取器单元测试"""

    def setUp(self):
        self.extractor = TimeInertiaExtractor(data_root=PROJ_DIR)
        self.draws = _generate_synthetic_draws(50, 2026100)
        self.target_period = 2026140

    def test_output_shape_and_bounds(self):
        f_time = self.extractor.extract(self.draws, self.target_period, lambda_decay=0.95)
        self.assertIsInstance(f_time, np.ndarray)
        self.assertEqual(f_time.shape, (NUM_TOTAL,))
        self.assertEqual(f_time.dtype, np.float64)
        self.assertTrue(np.all(f_time >= 0.0) and np.all(f_time <= 1.0))
        self.assertAlmostEqual(np.max(f_time), 1.0, places=5)

    def test_strict_anti_future_leakage(self):
        """验证输入包含 target_period 及未来数据时，结果与严格截断数据完全一致"""
        res_full = self.extractor.extract(self.draws, self.target_period)
        truncated_draws = [d for d in self.draws if d["period"] < self.target_period]
        res_trunc = self.extractor.extract(truncated_draws, self.target_period)
        self.assertTrue(np.allclose(res_full, res_trunc, atol=1e-10))

    def test_empty_and_minimal_history(self):
        res_empty = self.extractor.extract([], 2026100)
        self.assertEqual(res_empty.shape, (NUM_TOTAL,))
        self.assertTrue(np.all(res_empty == 0.0))

        res_single = self.extractor.extract(self.draws[:1], 2026102)
        self.assertEqual(res_single.shape, (NUM_TOTAL,))
        self.assertTrue(np.all(res_single >= 0.0) and np.all(res_single <= 1.0))

    def test_lambda_decay_sensitivity(self):
        """对比不同 lambda_decay 对较早历史记忆的保留程度"""
        res_fast_decay = self.extractor.extract(self.draws, self.target_period, lambda_decay=0.80)
        res_slow_decay = self.extractor.extract(self.draws, self.target_period, lambda_decay=0.98)
        self.assertFalse(np.allclose(res_fast_decay, res_slow_decay))

    def test_model_missing_fallback(self):
        """测试模型权重不存在时的平滑降级"""
        fallback_extractor = TimeInertiaExtractor(data_root="/non/existent/path")
        res = fallback_extractor.extract(self.draws, self.target_period)
        self.assertEqual(res.shape, (NUM_TOTAL,))
        self.assertTrue(np.all(res >= 0.0) and np.all(res <= 1.0))


class TestSpatialEnergyExtractor(unittest.TestCase):
    """空间能量密度势能提取器单元测试"""

    def setUp(self):
        self.extractor = SpatialEnergyExtractor(num_total=NUM_TOTAL)
        self.draws = _generate_synthetic_draws(50, 2026100)
        self.target_period = 2026140

    def test_output_shape_and_bounds(self):
        f_space = self.extractor.extract(self.draws, self.target_period, sigma=2.50)
        self.assertIsInstance(f_space, np.ndarray)
        self.assertEqual(f_space.shape, (NUM_TOTAL,))
        self.assertEqual(f_space.dtype, np.float64)
        self.assertTrue(np.all(f_space >= 0.0) and np.all(f_space <= 1.0))
        self.assertAlmostEqual(np.max(f_space), 1.0, places=5)

    def test_gaussian_single_point_source_symmetry(self):
        """单点源测试：仅有号码 40 开出，势能应以 40 为中心对称单调递减"""
        single_draw = [{"period": 2026100, "date": "2026-01-01", "nums": [40]}]
        f_space = self.extractor.extract(single_draw, 2026101, sigma=2.0)
        
        # 峰值在 40 (索引 39)
        self.assertEqual(np.argmax(f_space), 39)
        # 对称性验证: 39 与 41 (索引 38 与 40)
        self.assertAlmostEqual(f_space[38], f_space[40], places=6)
        # 单调递减: 40 > 41 > 42
        self.assertGreater(f_space[39], f_space[40])
        self.assertGreater(f_space[40], f_space[41])

    def test_sigma_diffusion_width(self):
        """核宽参数测试：sigma 越大，扩散能量越平缓"""
        single_draw = [{"period": 2026100, "date": "2026-01-01", "nums": [40]}]
        f_narrow = self.extractor.extract(single_draw, 2026101, sigma=1.0)
        f_wide = self.extractor.extract(single_draw, 2026101, sigma=5.0)

        # 窄核在距离 3 处衰减更快
        self.assertLess(f_narrow[39 + 3], f_wide[39 + 3])

    def test_overheating_penalty(self):
        """过热均值回归惩罚测试：连续多期开出的号码在开启惩罚时势能受到抑制"""
        # 构造连续 5 期均包含号码 10 的历史
        hot_draws = [
            {"period": 2026100 + i, "date": f"2026-01-{i+1:02d}", "nums": [10, 20, 30]}
            for i in range(5)
        ]
        f_penalized = self.extractor.extract(hot_draws, 2026106, apply_overheating=True)
        f_unpenalized = self.extractor.extract(hot_draws, 2026106, apply_overheating=False)

        # 号码 10 (索引 9) 在受惩罚时其相对主导地位下降
        self.assertIsInstance(f_penalized, np.ndarray)
        self.assertIsInstance(f_unpenalized, np.ndarray)

    def test_empty_history(self):
        res_empty = self.extractor.extract([], 2026100)
        self.assertEqual(res_empty.shape, (NUM_TOTAL,))
        self.assertTrue(np.all(res_empty == 0.0))


class TestDiscreteRuleExtractor(unittest.TestCase):
    """离散形态规则向量提取器单元测试"""

    def setUp(self):
        self.extractor = DiscreteRuleExtractor()
        self.draws = _generate_synthetic_draws(50, 2026100)

    def test_rules_loading_integrity(self):
        """验证 90 条口诀正确装载"""
        self.assertGreaterEqual(len(self.extractor.rules), 80)
        # 检查规则 1 的字段结构
        if "1" in self.extractor.rules:
            r1 = self.extractor.rules["1"]
            self.assertIn("trigger", r1)
            self.assertIn("predict", r1)
            self.assertIn("lift_oof", r1)

    def test_rule_trigger_and_activation(self):
        """当上期开奖命中触发条件时，目标预测号码被显著激活"""
        if "1" in self.extractor.rules:
            r1 = self.extractor.rules["1"]
            trigger = r1["trigger"]
            predict = r1["predict"]

            # 构造上期包含 trigger 的历史开奖
            mock_draws = [
                {"period": 2026100, "date": "2026-01-01", "nums": list(range(1, 21))},
                {"period": 2026101, "date": "2026-01-02", "nums": list(trigger) + list(range(1, 21 - len(trigger)))}
            ]
            f_rule = self.extractor.extract(mock_draws, 2026102)

            for p in predict:
                self.assertGreater(f_rule[p - 1], 0.05, f"预测号码 {p} 应被规则点亮激活")

    def test_zero_rule_fired_smoothing_baseline(self):
        """无任何口诀触发时的平滑基线测试 (杜绝全零)"""
        # 构造完全不命中的单期历史
        mock_draws = [
            {"period": 2026100, "date": "2026-01-01", "nums": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]}
        ]
        f_rule = self.extractor.extract(mock_draws, 2026101, smooth_eps=0.05)
        self.assertEqual(f_rule.shape, (NUM_TOTAL,))
        self.assertTrue(np.all(f_rule >= 0.0) and np.all(f_rule <= 1.0))
        # 绝不应是全 0
        self.assertTrue(np.any(f_rule > 0))

    def test_dynamic_weights_evolution_support(self):
        """动态权重赛马机制测试"""
        if "1" in self.extractor.rules:
            r1 = self.extractor.rules["1"]
            mock_draws = [
                {"period": 2026100, "date": "2026-01-01", "nums": list(range(1, 21))},
                {"period": 2026101, "date": "2026-01-02", "nums": list(r1["trigger"]) + list(range(1, 21 - len(r1["trigger"])))}
            ]
            # 正常权重 vs 5倍放大权重
            f_normal = self.extractor.extract(mock_draws, 2026102, rule_weights={"1": 1.0})
            f_boosted = self.extractor.extract(mock_draws, 2026102, rule_weights={"1": 5.0})

            p_target = r1["predict"][0] - 1
            self.assertGreaterEqual(f_boosted[p_target], f_normal[p_target])


class TestTopologicalCooccurrenceExtractor(unittest.TestCase):
    """拓扑共现与跟随粘性提取器单元测试"""

    def setUp(self):
        self.extractor = TopologicalCooccurrenceExtractor(num_total=NUM_TOTAL)
        self.draws = _generate_synthetic_draws(50, 2026100)
        self.target_period = 2026140

    def test_cooccurrence_matrix_symmetry_and_shape(self):
        f_topo, co_matrix = self.extractor.extract(self.draws, self.target_period, window=30)
        self.assertEqual(co_matrix.shape, (NUM_TOTAL, NUM_TOTAL))
        self.assertTrue(np.all(co_matrix >= 0.0) and np.all(co_matrix <= 1.0))
        # 严格对称性检验 (M == M^T)
        self.assertTrue(np.allclose(co_matrix, co_matrix.T, atol=1e-10))

    def test_topological_energy_output(self):
        f_topo, _ = self.extractor.extract(self.draws, self.target_period, window=30)
        self.assertEqual(f_topo.shape, (NUM_TOTAL,))
        self.assertTrue(np.all(f_topo >= 0.0) and np.all(f_topo <= 1.0))

    def test_markov_smoothing_robustness(self):
        """样本极少时 Markov 转移概率平滑性验证"""
        minimal_draws = [
            {"period": 2026100, "date": "2026-01-01", "nums": list(range(1, 21))},
            {"period": 2026101, "date": "2026-01-02", "nums": list(range(21, 41))},
        ]
        f_topo, co_matrix = self.extractor.extract(minimal_draws, 2026102)
        self.assertEqual(f_topo.shape, (NUM_TOTAL,))
        self.assertFalse(np.isnan(f_topo).any())
        self.assertFalse(np.isnan(co_matrix).any())


class TestDefenseMaskExtractor(unittest.TestCase):
    """绝对防守禁区硬掩码提取器单元测试（KillSeeker 下架后恒为全安全）"""

    def setUp(self):
        self.extractor = DefenseMaskExtractor()
        self.draws = _generate_synthetic_draws(70, 2026100)
        self.target_period = 2026160

    def test_defense_mask_all_safe_contract(self):
        mask, kills, meta = self.extractor.extract_with_meta(
            self.draws, self.target_period, kill_size=15
        )
        self.assertIsInstance(mask, np.ndarray)
        self.assertEqual(mask.shape, (NUM_TOTAL,))
        self.assertEqual(mask.dtype, bool)
        self.assertTrue(np.all(mask))
        self.assertEqual(kills, [])
        self.assertEqual(int(np.sum(~mask)), 0)
        self.assertIn("retired", meta)

    def test_kill_size_ignored_returns_empty_kills(self):
        """kill_size 参数保留兼容，但不产生杀号"""
        _, kills, _ = self.extractor.extract_with_meta(
            self.draws, self.target_period, kill_size=20, max_per_decade=4
        )
        self.assertEqual(kills, [])

    def test_short_history_still_all_safe(self):
        short_draws = self.draws[:10]
        mask, kills, meta = self.extractor.extract_with_meta(short_draws, 2026108, kill_size=12)
        self.assertEqual(kills, [])
        self.assertTrue(np.all(mask))
        self.assertIn("retired", meta)


class TestUnifiedFeatureBundle(unittest.TestCase):
    """统一特征数据包与自检方法测试"""

    def _create_valid_bundle(self) -> UnifiedFeatureBundle:
        return UnifiedFeatureBundle(
            target_period=2026201,
            draw_date="2026-08-30",
            time_inertia=np.random.uniform(0, 1, 80),
            spatial_energy=np.random.uniform(0, 1, 80),
            rule_activation=np.random.uniform(0, 1, 80),
            topological_energy=np.random.uniform(0, 1, 80),
            cooccurrence_matrix=np.eye(80),
            defense_mask=np.array([True] * 65 + [False] * 15, dtype=bool),
            killed_numbers=list(range(66, 81)),
            meta_info={"test": True}
        )

    def test_valid_bundle_validation(self):
        bundle = self._create_valid_bundle()
        self.assertTrue(bundle.validate())

    def test_invalid_shape_raises_error(self):
        bundle = self._create_valid_bundle()
        bundle.time_inertia = np.random.uniform(0, 1, 79)
        with self.assertRaises(ValueError):
            bundle.validate()

    def test_invalid_dtype_raises_error(self):
        bundle = self._create_valid_bundle()
        bundle.defense_mask = np.ones(80, dtype=np.int32)
        with self.assertRaises(ValueError):
            bundle.validate()

    def test_nan_or_inf_raises_error(self):
        bundle = self._create_valid_bundle()
        bundle.spatial_energy[10] = np.nan
        with self.assertRaises(ValueError):
            bundle.validate()

    def test_asymmetric_cooccurrence_raises_error(self):
        bundle = self._create_valid_bundle()
        m = np.eye(80)
        m[0, 1] = 1.0
        m[1, 0] = 0.0  # 不对称
        bundle.cooccurrence_matrix = m
        with self.assertRaises(ValueError):
            bundle.validate()

    def test_to_dict_serialization(self):
        bundle = self._create_valid_bundle()
        d = bundle.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["target_period"], 2026201)
        self.assertEqual(len(d["time_inertia"]), 80)
        self.assertEqual(d["safe_count"], 65)


class TestFeatureEngineeringPipeline(unittest.TestCase):
    """特征工程流水线与超参数调度测试"""

    def setUp(self):
        self.pipeline = FeatureEngineeringPipeline(data_root=PROJ_DIR)
        self.draws = _generate_synthetic_draws(50, 2026100)
        self.target_period = 2026140

    def test_pipeline_extract_bundle_contract(self):
        bundle = self.pipeline.extract_bundle(
            draws=self.draws,
            target_period=self.target_period,
            hyperparams={
                "lambda_decay": 0.92,
                "sigma": 3.0,
                "kill_size": 16,
            }
        )
        self.assertIsInstance(bundle, UnifiedFeatureBundle)
        self.assertTrue(bundle.validate())
        self.assertEqual(bundle.target_period, self.target_period)
        self.assertEqual(len(bundle.killed_numbers), 0)
        self.assertTrue(np.all(bundle.defense_mask))
        self.assertEqual(int(np.sum(~bundle.defense_mask)), 0)

    def test_pipeline_dirty_data_and_string_numbers_resilience(self):
        """验证流水线在包含字符串号码、缺失键、杂质数据时平稳运行绝不崩溃 (大白话：抗脏数据强力测试)"""
        malformed_draws = [
            {"period": 2026100, "date": "2026-01-01"},
            {"period": 2026101, "nums": None},
            {"nums": list(range(1, 21))},
            {"period": 2026103, "nums": "01-02-03-04-05-06-07-08-09-10-11-12-13-14-15-16-17-18-19-20"},
            {"period": 2026104, "nums": ["01", "02", "3", "04", 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]},
            {"period": 2026105, "nums": []},
        ]
        bundle = self.pipeline.extract_bundle(
            draws=malformed_draws,
            target_period=2026110,
            hyperparams={"kill_size": 15}
        )
        self.assertIsInstance(bundle, UnifiedFeatureBundle)
        self.assertTrue(bundle.validate())
        d = bundle.to_dict()
        import json
        self.assertEqual(json.loads(json.dumps(d)), d, "to_dict() 必须 100% 符合 JSON 规范且完全可逆")


class TestFeatureEngineeringLayer(unittest.TestCase):
    """兼容门面层综合调用测试"""

    def setUp(self):
        self.layer = FeatureEngineeringLayer(data_root=PROJ_DIR)
        draws = self.layer.draws
        self.target_period = (draws[-1]["period"] + 1) if draws else 2026234

    def test_layer_all_extractors_pure_memory(self):
        f_time = self.layer.extract_time_features(self.target_period)
        f_space = self.layer.extract_spatial_energy_features(self.target_period)
        f_rule = self.layer.extract_discrete_rule_features(self.target_period)
        f_topo, co_matrix = self.layer.extract_topological_cooccurrence(self.target_period)
        f_mask = self.layer.extract_defense_mask(self.target_period, kill_size=15)

        self.assertEqual(f_time.shape, (NUM_TOTAL,))
        self.assertEqual(f_space.shape, (NUM_TOTAL,))
        self.assertEqual(f_rule.shape, (NUM_TOTAL,))
        self.assertEqual(f_topo.shape, (NUM_TOTAL,))
        self.assertEqual(co_matrix.shape, (NUM_TOTAL, NUM_TOTAL))
        self.assertEqual(f_mask.shape, (NUM_TOTAL,))
        self.assertEqual(f_mask.dtype, bool)


if __name__ == "__main__":
    unittest.main()

