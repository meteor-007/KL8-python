# -*- coding: utf-8 -*-
"""
test_challenger_m1_2.py — Challenger M1-2 对抗性极限压力测试与数据纯净性防线审查
=============================================================================
【对抗挑战专家 2 (Challenger M1-2) 专属实证套件】：
  1. 专项挑战【绝对防守禁区掩码 (DefenseMaskExtractor)】：
     - 0 杀号至 25 杀号上限边界极限测试；
     - 十年区间配额约束 (max_per_decade) 极端倾斜攻击与防团灭测试；
     - 真实开奖数据滚动提取与极端样本退化测试。
  2. 专项挑战【特征数据包强校验 (UnifiedFeatureBundle)】：
     - 维度不匹配攻击 (Dimension mismatch injection)；
     - 非布尔掩码类型篡改 (Dtype corruption)；
     - NaN / Inf 脏数据渗透攻击 (Poison tensor injection)；
     - 非对称共现矩阵拓扑破坏 (Asymmetry attack)；
     - 杀号超额/安全码不足熔断拦截 (Safe numbers count boundary)；
     - JSON 序列化无损往返保真度 (Serialization fidelity)。
  3. 历史数据无未来信息泄漏对抗检验 (Anti-future data leakage verification)。
"""

import os
import sys
import math
import json
import unittest
import numpy as np
from typing import List, Dict, Any

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.modules.legacy.unified_brain.feature_extractors import (
    NUM_TOTAL,
    DefenseMaskExtractor,
    UnifiedFeatureBundle,
    FeatureEngineeringPipeline,
    FeatureEngineeringLayer,
    load_historical_draws,
    _get_draw_period,
    _get_draw_nums,
)


def _generate_synthetic_draws(n_draws: int = 60, start_period: int = 2026100) -> List[Dict[str, Any]]:
    """生成确定性合成历史开奖数据供压力测试使用"""
    np.random.seed(42)
    draws = []
    for i in range(n_draws):
        period = start_period + i
        nums = sorted(list(np.random.choice(np.arange(1, 81), size=20, replace=False)))
        draws.append({
            "period": period,
            "date": f"2026-01-{(i % 28) + 1:02d}",
            "nums": [int(x) for x in nums],
            "nums_set": set(int(x) for x in nums)
        })
    return draws


class TestAdversarialKillSizeBoundaries(unittest.TestCase):
    """
    【战区一：DefenseMask 已退役 KillSeeker】
    恒返回全 True 安全掩码与空杀号集；kill_size 参数被忽略。
    """

    def setUp(self):
        self.extractor = DefenseMaskExtractor()
        self.draws = _generate_synthetic_draws(60, 2026100)
        self.target_period = 2026150

    def test_always_all_safe_regardless_of_kill_size(self):
        for k in [0, 1, 15, 18, 20, 22, 25, 30]:
            with self.subTest(kill_size=k):
                mask, kills, meta = self.extractor.extract_with_meta(
                    self.draws, self.target_period, kill_size=k
                )
                self.assertEqual(len(kills), 0)
                self.assertEqual(int(np.sum(mask)), NUM_TOTAL)
                self.assertEqual(int(np.sum(~mask)), 0)
                self.assertEqual(mask.dtype, bool)
                self.assertIn("retired", meta)

    def test_monte_carlo_always_safe(self):
        np.random.seed(12345)
        for trial in range(20):
            k = np.random.randint(0, 26)
            p = np.random.randint(2026135, 2026160)
            mask, kills, meta = self.extractor.extract_with_meta(
                self.draws, p, kill_size=k
            )
            self.assertEqual(len(kills), 0, f"Trial {trial}")
            self.assertEqual(int(np.sum(mask)), NUM_TOTAL, f"Trial {trial}")


class TestAdversarialDecadeBalanceConstraint(unittest.TestCase):
    """
    【战区二：KillSeeker 配额算法已随模块拆除】
    `_select_kills_balanced` 不再存在；DefenseMask 恒空杀。
    """

    def test_no_select_kills_balanced_api(self):
        self.assertFalse(hasattr(DefenseMaskExtractor, "_select_kills_balanced"))

    def test_extract_empty_kills(self):
        ext = DefenseMaskExtractor()
        draws = _generate_synthetic_draws(30, 2026100)
        mask, kills, _ = ext.extract_with_meta(draws, 2026130, kill_size=15)
        self.assertEqual(kills, [])
        self.assertTrue(bool(np.all(mask)))


class TestAdversarialBundleValidationDestruction(unittest.TestCase):
    """
    【战区三：UnifiedFeatureBundle.validate() 数据纯净性强校验破坏测试】
    使用各种对抗性畸变、维度污染、类型破坏、脏数据攻击 validate()，验证是否能 100% 精准拦截。
    """

    def _create_standard_valid_bundle(self) -> UnifiedFeatureBundle:
        return UnifiedFeatureBundle(
            target_period=2026201,
            draw_date="2026-08-30",
            time_inertia=np.random.uniform(0, 1, 80).astype(np.float64),
            spatial_energy=np.random.uniform(0, 1, 80).astype(np.float64),
            rule_activation=np.random.uniform(0, 1, 80).astype(np.float64),
            topological_energy=np.random.uniform(0, 1, 80).astype(np.float64),
            cooccurrence_matrix=np.eye(80, dtype=np.float64),
            defense_mask=np.array([True] * 65 + [False] * 15, dtype=bool),
            killed_numbers=list(range(66, 81)),
            meta_info={"test": "ok"}
        )

    def test_baseline_valid_bundle_passes(self):
        """基线验证：合法数据包必须正常通过"""
        bundle = self._create_standard_valid_bundle()
        self.assertTrue(bundle.validate())

    def test_dimension_mismatch_attacks(self):
        """【维度篡改攻击】：任意特征张量形状不为 (80,) 或 (80, 80) 时必须触发 ValueError"""
        # 1. time_inertia 维度错误
        for bad_shape in [(79,), (81,), (80, 1), (1, 80), (80, 2)]:
            bundle = self._create_standard_valid_bundle()
            bundle.time_inertia = np.zeros(bad_shape, dtype=np.float64)
            with self.assertRaises(ValueError, msg=f"Failed to catch time_inertia shape {bad_shape}"):
                bundle.validate()

        # 2. spatial_energy 维度错误
        for bad_shape in [(79,), (81,), (2, 40)]:
            bundle = self._create_standard_valid_bundle()
            bundle.spatial_energy = np.zeros(bad_shape, dtype=np.float64)
            with self.assertRaises(ValueError, msg=f"Failed to catch spatial_energy shape {bad_shape}"):
                bundle.validate()

        # 3. rule_activation 维度错误
        bundle = self._create_standard_valid_bundle()
        bundle.rule_activation = np.zeros((90,), dtype=np.float64)
        with self.assertRaises(ValueError):
            bundle.validate()

        # 4. topological_energy 维度错误
        bundle = self._create_standard_valid_bundle()
        bundle.topological_energy = np.zeros((80, 80), dtype=np.float64)
        with self.assertRaises(ValueError):
            bundle.validate()

        # 5. cooccurrence_matrix 维度错误
        for bad_shape in [(80,), (79, 80), (80, 79), (80, 80, 1)]:
            bundle = self._create_standard_valid_bundle()
            bundle.cooccurrence_matrix = np.zeros(bad_shape, dtype=np.float64)
            with self.assertRaises(ValueError, msg=f"Failed to catch cooccurrence shape {bad_shape}"):
                bundle.validate()

        # 6. defense_mask 维度错误
        for bad_shape in [(79,), (81,), (80, 1)]:
            bundle = self._create_standard_valid_bundle()
            bundle.defense_mask = np.ones(bad_shape, dtype=bool)
            with self.assertRaises(ValueError, msg=f"Failed to catch defense_mask shape {bad_shape}"):
                bundle.validate()

    def test_defense_mask_dtype_corruption(self):
        """【掩码类型破坏攻击】：defense_mask 必须且只能为 bool，传入 int/float/object 必须被拒"""
        for bad_dtype in [np.int32, np.int64, np.float32, np.float64, np.uint8, object]:
            bundle = self._create_standard_valid_bundle()
            bundle.defense_mask = np.ones(80, dtype=bad_dtype)
            with self.assertRaises(ValueError, msg=f"Failed to catch bad defense_mask dtype {bad_dtype}"):
                bundle.validate()

    def test_nan_and_inf_poison_injection(self):
        """【NaN/Inf 脏数据毒丸注入】：任何张量注入 NaN 或 Inf 必须立即引爆拦截"""
        tensor_names = [
            "time_inertia", "spatial_energy", "rule_activation",
            "topological_energy", "cooccurrence_matrix"
        ]
        for name in tensor_names:
            # 注入 NaN
            bundle = self._create_standard_valid_bundle()
            arr = getattr(bundle, name).copy()
            if arr.ndim == 1:
                arr[42] = np.nan
            else:
                arr[10, 20] = np.nan
            setattr(bundle, name, arr)
            with self.assertRaises(ValueError, msg=f"Failed to catch NaN in {name}"):
                bundle.validate()

            # 注入 +Inf
            bundle = self._create_standard_valid_bundle()
            arr = getattr(bundle, name).copy()
            if arr.ndim == 1:
                arr[15] = np.inf
            else:
                arr[30, 30] = np.inf
            setattr(bundle, name, arr)
            with self.assertRaises(ValueError, msg=f"Failed to catch +Inf in {name}"):
                bundle.validate()

            # 注入 -Inf
            bundle = self._create_standard_valid_bundle()
            arr = getattr(bundle, name).copy()
            if arr.ndim == 1:
                arr[77] = -np.inf
            else:
                arr[5, 5] = -np.inf
            setattr(bundle, name, arr)
            with self.assertRaises(ValueError, msg=f"Failed to catch -Inf in {name}"):
                bundle.validate()

    def test_asymmetric_cooccurrence_matrix_attacks(self):
        """【非对称拓扑矩阵攻击】：共现矩阵必须严格对称 (M == M^T)"""
        # 1. 显式不对称破坏 (明显不对称，如方向性错误 0.85 vs 0.15)
        bundle = self._create_standard_valid_bundle()
        m = np.eye(80, dtype=np.float64)
        m[12, 34] = 0.85
        m[34, 12] = 0.15  # 严重不对称
        bundle.cooccurrence_matrix = m
        with self.assertRaises(ValueError, msg="Failed to catch grossly asymmetric cooccurrence matrix"):
            bundle.validate()

        # 2. 中等不对称破坏 (差值 0.001 > 1e-5 容差门限)
        bundle = self._create_standard_valid_bundle()
        m = np.eye(80, dtype=np.float64)
        m[10, 20] = 0.500
        m[20, 10] = 0.501  # 差值 1e-3
        bundle.cooccurrence_matrix = m
        with self.assertRaises(ValueError, msg="Failed to catch asymmetric violation with diff=1e-3"):
            bundle.validate()

        # 3. 临界不对称破坏 (差值 1e-4 > rtol=1e-5)
        bundle = self._create_standard_valid_bundle()
        m = np.eye(80, dtype=np.float64)
        m[10, 20] = 0.50000
        m[20, 10] = 0.50010  # 差值 1e-4, 相对误差 2e-4 > 1e-5
        bundle.cooccurrence_matrix = m
        with self.assertRaises(ValueError, msg="Failed to catch asymmetric violation with diff=1e-4"):
            bundle.validate()

        # 4. 浮点微差 (在 1e-10 以内，严格符合浮点容差) 应该通过
        bundle = self._create_standard_valid_bundle()
        m = np.eye(80, dtype=np.float64)
        m[10, 20] = 0.5000000000
        m[20, 10] = 0.50000000005  # 差值 5e-11 < 1e-8
        bundle.cooccurrence_matrix = m
        self.assertTrue(bundle.validate())

    def test_safe_numbers_count_boundaries(self):
        """【安全号码数量上下界拦截】：safe_count 必须在 [50, 80] 区间内"""
        # 1. 杀号过多，安全码仅剩 49 (< 50) -> 必须拦截
        bundle = self._create_standard_valid_bundle()
        bundle.defense_mask = np.array([True] * 49 + [False] * 31, dtype=bool)
        with self.assertRaises(ValueError, msg="Failed to reject safe_count=49 (< 50)"):
            bundle.validate()

        # 2. 全杀 (safe_count = 0) -> 必须拦截
        bundle = self._create_standard_valid_bundle()
        bundle.defense_mask = np.zeros(80, dtype=bool)
        with self.assertRaises(ValueError, msg="Failed to reject safe_count=0"):
            bundle.validate()

        # 3. 临界刚好 50 个安全码 (杀 30 码) -> 必须通过
        bundle = self._create_standard_valid_bundle()
        bundle.defense_mask = np.array([True] * 50 + [False] * 30, dtype=bool)
        self.assertTrue(bundle.validate())

        # 4. 0 杀号 (80 个安全码) -> 必须通过
        bundle = self._create_standard_valid_bundle()
        bundle.defense_mask = np.ones(80, dtype=bool)
        self.assertTrue(bundle.validate())

    def test_json_serialization_fidelity(self):
        """【JSON 序列化保真度与 Web API 契约验证】"""
        bundle = self._create_standard_valid_bundle()
        bundle_dict = bundle.to_dict()

        # 验证所有 numpy 结构都被成功转换为原生 Python 类型
        json_str = json.dumps(bundle_dict)
        self.assertIsInstance(json_str, str)
        self.assertGreater(len(json_str), 1000)

        # 反解验证字段完整性
        loaded = json.loads(json_str)
        self.assertEqual(loaded["target_period"], 2026201)
        self.assertEqual(loaded["draw_date"], "2026-08-30")
        self.assertEqual(len(loaded["time_inertia"]), 80)
        self.assertEqual(len(loaded["spatial_energy"]), 80)
        self.assertEqual(len(loaded["rule_activation"]), 80)
        self.assertEqual(len(loaded["topological_energy"]), 80)
        self.assertEqual(len(loaded["cooccurrence_matrix"]), 80)
        self.assertEqual(len(loaded["cooccurrence_matrix"][0]), 80)
        self.assertEqual(len(loaded["defense_mask"]), 80)
        self.assertEqual(loaded["safe_count"], 65)


class TestRealHistoricalDataStressAndAntiFuture(unittest.TestCase):
    """
    【战区四：真实开奖历史数据滚动压力与防未来信息泄漏实测】
    使用真实的 kl8_history_final.txt 进行多期滚动提取并检验。
    """

    def setUp(self):
        # 开奖历史在 storage/raw/ 下，不在项目根。
        # 之前写的是 os.path.join(PROJ_DIR, "kl8_history_final.txt")，文件根本不存在，
        # load_historical_draws 返回空列表 → 下面两个测试静默 skip —— 一直"通过"，实则从未跑过。
        from backend.utils.paths import data_path
        self.history_file = data_path("kl8_history_final.txt")
        self.draws = load_historical_draws(self.history_file)
        self.pipeline = FeatureEngineeringPipeline(data_root=PROJ_DIR)

    def test_real_history_rolling_50_periods_pipeline_stress(self):
        """在真实开奖历史最近 50 期上连续提取数据包，验证 100% 合法且不抛异常"""
        if len(self.draws) < 60:
            self.skipTest("真实开奖期数不足 60 期，跳过此测试")

        recent_draws = self.draws[-50:]
        for d in recent_draws:
            target_period = d["period"]
            with self.subTest(target_period=target_period):
                bundle = self.pipeline.extract_bundle(
                    draws=self.draws,
                    target_period=target_period,
                    hyperparams={"kill_size": 20, "max_per_decade": 4}
                )
                self.assertIsInstance(bundle, UnifiedFeatureBundle)
                # 强校验必须无条件通过
                self.assertTrue(bundle.validate())
                self.assertEqual(bundle.target_period, target_period)

                # KillSeeker 已下架（见 feature_extractors.DefenseMaskExtractor 文档）：
                # 不再产生任何杀号，防守掩码恒为全 True。这里校验的是**当前契约**。
                # 若将来重新启用杀号，本断言会失败 —— 届时请把 decade 分布（每区 ≤4 码）
                # 等约束一并补回来，而不是简单删掉断言。
                self.assertEqual(bundle.killed_numbers, [],
                                 f"{target_period}: KillSeeker 已下架，杀号应恒为空")
                self.assertTrue(bool(np.all(bundle.defense_mask)),
                                f"{target_period}: 防守掩码应全 True")

    def test_strict_anti_future_leakage_across_all_extractors(self):
        """【防未来数据渗透对抗验证】：向输入数据塞入当期及未来开奖，提取结果必须与严格截断历史完全一致"""
        if len(self.draws) < 50:
            self.skipTest("期数不足")

        target_period = self.draws[-10]["period"]

        # 包含未来数据的全量输入
        bundle_full = self.pipeline.extract_bundle(
            draws=self.draws,
            target_period=target_period,
            hyperparams={"kill_size": 15, "max_per_decade": 4}
        )

        # 严格截断未来数据的输入
        truncated_draws = [d for d in self.draws if d["period"] < target_period]
        bundle_trunc = self.pipeline.extract_bundle(
            draws=truncated_draws,
            target_period=target_period,
            hyperparams={"kill_size": 15, "max_per_decade": 4}
        )

        # 逐项特征严格一致性比对
        self.assertTrue(np.allclose(bundle_full.time_inertia, bundle_trunc.time_inertia, atol=1e-10))
        self.assertTrue(np.allclose(bundle_full.spatial_energy, bundle_trunc.spatial_energy, atol=1e-10))
        self.assertTrue(np.allclose(bundle_full.rule_activation, bundle_trunc.rule_activation, atol=1e-10))
        self.assertTrue(np.allclose(bundle_full.topological_energy, bundle_trunc.topological_energy, atol=1e-10))
        self.assertTrue(np.allclose(bundle_full.cooccurrence_matrix, bundle_trunc.cooccurrence_matrix, atol=1e-10))
        self.assertTrue(np.array_equal(bundle_full.defense_mask, bundle_trunc.defense_mask))
        self.assertEqual(bundle_full.killed_numbers, bundle_trunc.killed_numbers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
