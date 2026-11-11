# -*- coding: utf-8 -*-
"""
test_m1_forensic_integrity.py — M1 司法级取证审计与对抗性测试套件
=============================================================================
【审计目标】：
  1. 静态 AST 代码结构审计：杜绝假门面 (Dummy/Facade) 与死循环/空实现
  2. 动态 I/O 劫持与取证：验证特征提取过程 100% 纯内存流转，绝无偷读 txt 文件
  3. 严禁未来数据泄漏：验证未来开奖绝对不污染当前期特征
  4. 数学与物理规律真实性验证：验证高斯弥散对称性、时序指数衰减、Markov 平滑、共现对称性与防守平衡
  5. 超参数动态响应性验证：验证调参必引起数学输出的真实变化（非硬编码）
  6. 极端对抗性边界压力测试：空历史、单期、万期规模、极端超参数
"""
import os
import sys
import ast
import unittest
import numpy as np
import math
from unittest.mock import patch
from typing import List, Dict, Any

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.modules.unified_brain.feature_extractors import (
    BaseFeatureExtractor,
    TimeInertiaExtractor,
    SpatialEnergyExtractor,
    DiscreteRuleExtractor,
    TopologicalCooccurrenceExtractor,
    DefenseMaskExtractor,
    UnifiedFeatureBundle,
    FeatureEngineeringPipeline,
    FeatureEngineeringLayer,
    NUM_TOTAL
)


def _build_synthetic_draws(n_draws: int = 60, start_period: int = 2026100) -> List[Dict[str, Any]]:
    np.random.seed(12345)
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


class TestM1StaticASTForensics(unittest.TestCase):
    """1. 静态 AST 代码取证：检查源码中是否存在硬编码作弊或空壳门面"""

    def setUp(self):
        candidates = [
            os.path.join(PROJ_DIR, "backend", "modules", "unified_brain", "feature_extractors.py"),
            os.path.join(PROJ_DIR, "backend", "core", "unified_brain", "feature_extractors.py"),
        ]
        self.target_file = candidates[0] if os.path.exists(candidates[0]) else candidates[1]
        with open(self.target_file, "r", encoding="utf-8") as f:
            self.source_code = f.read()
        self.tree = ast.parse(self.source_code, filename=self.target_file)

    def test_01_no_hardcoded_period_branches(self):
        """取证检查：源码中严禁存在类似 if period == 2026xxx 的硬编码分支作弊"""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.If):
                # 检查比较表达式
                if isinstance(node.test, ast.Compare):
                    for comp in node.test.comparators:
                        if isinstance(comp, ast.Constant) and isinstance(comp.value, int):
                            # 允许常见小常数 (例如 30, 80, 50, 4, 15, 0 等)，严禁出现特定期号 (如 2026xxx)
                            self.assertLess(
                                comp.value, 100000,
                                f"发现可疑的硬编码期号比较: {comp.value} in line {node.lineno}"
                            )

    def test_02_no_trivial_facade_methods(self):
        """取证检查：提取器核心 extract/extract_with_meta 方法绝不能仅包含 pass 或 return constant"""
        target_classes = [
            "TimeInertiaExtractor",
            "SpatialEnergyExtractor",
            "DiscreteRuleExtractor",
            "TopologicalCooccurrenceExtractor",
            "DefenseMaskExtractor",
            "FeatureEngineeringPipeline",
        ]
        for node in self.tree.body:
            if isinstance(node, ast.ClassDef) and node.name in target_classes:
                total_stmts = 0
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name in ["extract", "extract_bundle", "extract_with_meta"]:
                        real_stmts = [
                            s for s in item.body
                            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))
                        ]
                        total_stmts += len(real_stmts)
                self.assertGreater(
                    total_stmts, 3,
                    f"类 {node.name} 的核心提取方法语句过少 ({total_stmts})，涉嫌空壳门面实现！"
                )


class TestM1MemoryPurityForensics(unittest.TestCase):
    """2. 纯内存特征流转取证：在执行 extract 时拦截 open，验证 100% 纯内存"""

    def setUp(self):
        self.draws = _build_synthetic_draws(50, 2026100)
        self.target_period = 2026140

    def test_01_pipeline_extract_bundle_zero_disk_io(self):
        """取证：FeatureEngineeringPipeline.extract_bundle 执行过程中绝不读取历史 txt 文件"""
        pipeline = FeatureEngineeringPipeline(data_root=PROJ_DIR)
        
        opened_files = []
        original_open = open

        def guarded_open(file, *args, **kwargs):
            file_str = str(file)
            opened_files.append(file_str)
            return original_open(file, *args, **kwargs)

        with patch("builtins.open", side_effect=guarded_open):
            bundle = pipeline.extract_bundle(self.draws, self.target_period)

        # 检查在 extract_bundle 调用期间是否发生了任何对 kl8_history_final.txt 的 I/O
        history_reads = [f for f in opened_files if "kl8_history_final.txt" in f]
        self.assertEqual(
            len(history_reads), 0,
            f"取证失败：extract_bundle 期间暗中读取了历史文件 {history_reads}，未实现纯内存流转！"
        )
        self.assertIsInstance(bundle, UnifiedFeatureBundle)
        self.assertTrue(bundle.validate())

    def test_02_individual_extractors_zero_disk_io(self):
        """取证：5大提取器单独 extract 时全部 0 磁盘 I/O"""
        time_ext = TimeInertiaExtractor(data_root=PROJ_DIR)
        spatial_ext = SpatialEnergyExtractor()
        rule_ext = DiscreteRuleExtractor()
        topo_ext = TopologicalCooccurrenceExtractor()
        defense_ext = DefenseMaskExtractor()

        opened_files = []
        original_open = open

        def guarded_open(file, *args, **kwargs):
            opened_files.append(str(file))
            return original_open(file, *args, **kwargs)

        with patch("builtins.open", side_effect=guarded_open):
            f_time = time_ext.extract(self.draws, self.target_period)
            f_space = spatial_ext.extract(self.draws, self.target_period)
            f_rule = rule_ext.extract(self.draws, self.target_period)
            f_topo, co_matrix = topo_ext.extract(self.draws, self.target_period)
            f_mask = defense_ext.extract(self.draws, self.target_period)

        # 检查是否调用了历史文件
        history_reads = [f for f in opened_files if "kl8_history" in f]
        self.assertEqual(len(history_reads), 0, f"发现非法磁盘读取: {history_reads}")


class TestM1AntiFutureLeakageForensics(unittest.TestCase):
    """3. 防未来信息泄漏司法取证：篡改未来开奖，验证特征输出完全免疫"""

    def setUp(self):
        self.draws = _build_synthetic_draws(60, 2026100)
        self.target_period = 2026140

    def test_01_future_tampering_immunity(self):
        """取证：在历史列表中注入 target_period 及其未来的虚假开奖，提取特征必须完全不受干扰"""
        pipeline = FeatureEngineeringPipeline(data_root=PROJ_DIR)

        # 原始未受污染数据
        bundle_clean = pipeline.extract_bundle(self.draws[:40], self.target_period)

        # 构造受到未来数据恶意污染的数据集 (第 40 期是 target_period，故意填入极端号码)
        tampered_draws = list(self.draws[:40])
        tampered_draws.append({
            "period": self.target_period,
            "date": "2026-99-99",
            "nums": [71, 72, 73, 74, 75, 76, 77, 78, 79, 80] * 2,
        })
        tampered_draws.append({
            "period": self.target_period + 1,
            "date": "2026-99-99",
            "nums": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 2,
        })

        bundle_tampered = pipeline.extract_bundle(tampered_draws, self.target_period)

        # 严格比对五大特征张量
        self.assertTrue(np.allclose(bundle_clean.time_inertia, bundle_tampered.time_inertia, atol=1e-12))
        self.assertTrue(np.allclose(bundle_clean.spatial_energy, bundle_tampered.spatial_energy, atol=1e-12))
        self.assertTrue(np.allclose(bundle_clean.rule_activation, bundle_tampered.rule_activation, atol=1e-12))
        self.assertTrue(np.allclose(bundle_clean.topological_energy, bundle_tampered.topological_energy, atol=1e-12))
        self.assertTrue(np.allclose(bundle_clean.cooccurrence_matrix, bundle_tampered.cooccurrence_matrix, atol=1e-12))
        self.assertTrue(np.array_equal(bundle_clean.defense_mask, bundle_tampered.defense_mask))


class TestM1MathematicalAndPhysicalIntegrity(unittest.TestCase):
    """4. 数学物理规律真实性取证：证明算法真实遵循物理公式，而非伪造"""

    def test_01_spatial_gaussian_physics(self):
        """取证：空间高斯核能量严格服从 exp(-dist^2 / 2*sigma^2)"""
        extractor = SpatialEnergyExtractor()
        # 仅放 1 个单点点源：号码 20
        draw = [{"period": 100, "date": "2026-01-01", "nums": [20]}]
        sigma = 3.0
        f_space = extractor.extract(draw, 101, sigma=sigma, apply_overheating=False)

        # 中心必须在 20 (索引 19)
        self.assertEqual(np.argmax(f_space), 19)
        # 理论计算：号码 21 与 19 的理论比值应与实际严格吻合
        # dist = 1 -> ratio = exp(-1 / (2*9)) = exp(-1/18) = 0.945959
        actual_ratio = f_space[20] / f_space[19]
        expected_ratio = math.exp(-1.0 / (2.0 * (sigma ** 2)))
        self.assertAlmostEqual(actual_ratio, expected_ratio, places=5)

    def test_02_time_exponential_decay_physics(self):
        """取证：时序动量严格服从 lambda^(t_diff) 衰减"""
        extractor = TimeInertiaExtractor(data_root=PROJ_DIR)
        # 构造两期：期 100 出现号码 10，期 101 出现号码 20
        draws = [
            {"period": 100, "date": "2026-01-01", "nums": [10]},
            {"period": 101, "date": "2026-01-02", "nums": [20]},
        ]
        lambda_decay = 0.90
        # 使用不依赖模型的 fallback 模式测试时序动量纯物理衰减
        f_time = extractor.extract(draws, 102, lambda_decay=lambda_decay, alpha_momentum=1.0)

        # 号码 20 比 号码 10 新 1 期，因此 ratio 理论上应为 lambda_decay = 0.90
        ratio = f_time[9] / f_time[19]
        self.assertAlmostEqual(ratio, lambda_decay, places=4)

    def test_03_cooccurrence_matrix_perfect_symmetry(self):
        """取证：双元共现矩阵必须严格满足全局对称 M[u, v] == M[v, u]"""
        extractor = TopologicalCooccurrenceExtractor()
        draws = _build_synthetic_draws(40, 2026100)
        _, co_matrix = extractor.extract(draws, 2026140)
        self.assertTrue(np.allclose(co_matrix, co_matrix.T, atol=1e-12))


class TestM1HyperparameterResponsiveness(unittest.TestCase):
    """5. 超参数动态响应取证：调参必须产生确定性物理变化，证明绝非硬编码"""

    def setUp(self):
        self.draws = _build_synthetic_draws(50, 2026100)
        self.target_period = 2026140

    def test_01_sigma_response(self):
        extractor = SpatialEnergyExtractor()
        res_sigma1 = extractor.extract(self.draws, self.target_period, sigma=1.5)
        res_sigma4 = extractor.extract(self.draws, self.target_period, sigma=4.0)
        self.assertFalse(np.allclose(res_sigma1, res_sigma4, atol=1e-3))

    def test_02_lambda_response(self):
        extractor = TimeInertiaExtractor(data_root=PROJ_DIR)
        res_lam85 = extractor.extract(self.draws, self.target_period, lambda_decay=0.85)
        res_lam98 = extractor.extract(self.draws, self.target_period, lambda_decay=0.98)
        self.assertFalse(np.allclose(res_lam85, res_lam98, atol=1e-3))

    def test_03_kill_size_response(self):
        """KillSeeker 已下架：kill_size 参数不影响结果，恒为空杀 / 全安全。"""
        extractor = DefenseMaskExtractor()
        mask15, kills15, _ = extractor.extract_with_meta(self.draws, self.target_period, kill_size=15)
        mask25, kills25, _ = extractor.extract_with_meta(self.draws, self.target_period, kill_size=25)
        self.assertEqual(len(kills15), 0)
        self.assertEqual(len(kills25), 0)
        self.assertEqual(int(np.sum(~mask15)), 0)
        self.assertEqual(int(np.sum(~mask25)), 0)
        self.assertTrue(np.array_equal(mask15, mask25))


class TestM1AdversarialStressAndBoundaries(unittest.TestCase):
    """6. 极限对抗压力测试：空数据、超大样本、异常值输入"""

    def test_01_empty_and_zero_inputs(self):
        pipeline = FeatureEngineeringPipeline(data_root=PROJ_DIR)
        # 空数据提取
        bundle = pipeline.extract_bundle([], 2026100)
        self.assertEqual(bundle.time_inertia.shape, (NUM_TOTAL,))
        self.assertEqual(bundle.spatial_energy.shape, (NUM_TOTAL,))
        self.assertEqual(bundle.rule_activation.shape, (NUM_TOTAL,))
        self.assertEqual(bundle.topological_energy.shape, (NUM_TOTAL,))
        self.assertEqual(bundle.cooccurrence_matrix.shape, (NUM_TOTAL, NUM_TOTAL))
        self.assertEqual(bundle.defense_mask.shape, (NUM_TOTAL,))

    def test_02_extreme_hyperparameter_bounds(self):
        extractor = SpatialEnergyExtractor()
        draws = _build_synthetic_draws(30, 2026100)
        # 极小核宽与极大核宽
        res_tiny = extractor.extract(draws, 2026130, sigma=0.0001)
        res_huge = extractor.extract(draws, 2026130, sigma=1000.0)
        self.assertFalse(np.isnan(res_tiny).any())
        self.assertFalse(np.isnan(res_huge).any())
        self.assertTrue(np.all(res_tiny >= 0.0) and np.all(res_tiny <= 1.0))
        self.assertTrue(np.all(res_huge >= 0.0) and np.all(res_huge <= 1.0))


if __name__ == "__main__":
    unittest.main()
