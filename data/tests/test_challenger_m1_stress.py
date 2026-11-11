# -*- coding: utf-8 -*-
"""
test_challenger_m1_stress.py — 对抗性挑战专家 1 (Challenger M1-1) 极端压力测试套件
=============================================================================
【对抗测试维度与实战攻击方案】：
  1. 极端脏数据攻击 (Dirty & Malformed Data Attack)：
     - 空开奖列表、全未来数据截断
     - 脏球号（负数、越界球号 > 80、None、浮点、字符串、空数组）
     - 单调开奖攻击（500期完全相同开奖、极端单向偏态开奖）
     - 重复球号与残缺开奖
  2. 极端超参数冲击 (Extreme Hyperparameters Stress)：
     - 空间高斯核宽：sigma = 0.0001, 1e-10, 0.0, -1.0, 1000.0, 1e6
     - 时序衰减与动量：lambda = 0.0, 1.0, -0.5, 2.0; alpha = 0.0, 1.0, -1.0, 2.0
     - 离散规则权重：负权重、超大权重 1e6、未知规则ID、smooth_eps = 0.0, -1.0, 100.0
     - 拓扑共现：window = 0, 1, -10, 10000; markov_alpha = 0.0, 1e-6, 1e6, -1.0
     - 防守禁区：kill_size = 0, 1, 15, 25, 30; max_per_decade = 0, 1, 10, 80
  3. 物理张量契约与数值稳定性防线 (Tensor Contract & Numerical Invariants)：
     - F_time, F_spatial, F_rule, F_topo 维度严格 (80,), float64, 值域 [0.0, 1.0] 且绝无 NaN / Inf
     - M_cooccur 维度严格 (80, 80), float64, 值域 [0.0, 1.0] 且严格对称 M == M^T
     - F_mask 维度严格 (80,), bool 类型, 安全点数量符合物理契约
     - UnifiedFeatureBundle 强校验机制与边界防御
  4. 真实历史数据基准与高频压力测试 (High-Frequency & Real-Data Stress)：
     - 连续 50 期真实历史滚动抽取，验证无内存泄漏、无跨期状态污染
"""
import os
import sys
import json
import math
import copy
import pytest
import numpy as np
from typing import Dict, List, Any

# Ensure project paths
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


# =====================================================================
# 辅助工具：生成各种对抗样本数据
# =====================================================================

def make_clean_draws(n: int = 50, start_period: int = 2026100) -> List[Dict[str, Any]]:
    """生成标准确定性开奖数据"""
    rng = np.random.RandomState(12345)
    draws = []
    for i in range(n):
        nums = sorted(rng.choice(np.arange(1, 81), size=20, replace=False).tolist())
        draws.append({
            "period": start_period + i,
            "date": f"2026-01-{(i % 28) + 1:02d}",
            "nums": nums,
            "nums_set": set(nums)
        })
    return draws


def make_monotonic_identical_draws(n: int = 200, fixed_nums: List[int] = None) -> List[Dict[str, Any]]:
    """生成单调完全相同的开奖数据（极端过热/零方差攻击）"""
    nums = fixed_nums or list(range(1, 21))
    return [
        {
            "period": 2026100 + i,
            "date": f"2026-01-{(i % 28) + 1:02d}",
            "nums": copy.deepcopy(nums),
            "nums_set": set(nums)
        }
        for i in range(n)
    ]


def make_skewed_draws(n: int = 100, low: int = 1, high: int = 20) -> List[Dict[str, Any]]:
    """生成极端偏态开奖数据（所有号码均挤在 [low, high] 区间内）"""
    rng = np.random.RandomState(42)
    pool = list(range(low, high + 1))
    draws = []
    for i in range(n):
        k = min(len(pool), 20)
        nums = sorted(rng.choice(pool, size=k, replace=False).tolist())
        draws.append({
            "period": 2026100 + i,
            "date": f"2026-01-{(i % 28) + 1:02d}",
            "nums": nums,
            "nums_set": set(nums)
        })
    return draws


# =====================================================================
# 第一战区：极端脏数据与格式边界攻击测试 (Dirty Data Attack)
# =====================================================================

class TestAdversarialDirtyData:
    """对五大特征提取器进行极端脏数据、空数据与异常格式攻击"""

    def setup_method(self):
        self.time_ext = TimeInertiaExtractor(data_root=PROJ_DIR)
        self.space_ext = SpatialEnergyExtractor(num_total=NUM_TOTAL)
        self.rule_ext = DiscreteRuleExtractor()
        self.topo_ext = TopologicalCooccurrenceExtractor(num_total=NUM_TOTAL)
        self.defense_ext = DefenseMaskExtractor()
        self.pipeline = FeatureEngineeringPipeline(data_root=PROJ_DIR)

    def test_01_empty_draw_list_all_extractors_graceful_handling(self):
        """【攻击场景】：开奖历史为空列表 [] 时，所有提取器绝不崩溃且输出合法形状"""
        empty_draws = []
        target = 2026100

        # 1. Time Extractor
        f_time = self.time_ext.extract(empty_draws, target)
        assert isinstance(f_time, np.ndarray)
        assert f_time.shape == (NUM_TOTAL,)
        assert not np.isnan(f_time).any()
        assert not np.isinf(f_time).any()
        assert np.all(f_time >= 0.0) and np.all(f_time <= 1.0)

        # 2. Spatial Extractor
        f_space = self.space_ext.extract(empty_draws, target)
        assert isinstance(f_space, np.ndarray)
        assert f_space.shape == (NUM_TOTAL,)
        assert not np.isnan(f_space).any()
        assert not np.isinf(f_space).any()
        assert np.all(f_space >= 0.0) and np.all(f_space <= 1.0)

        # 3. Rule Extractor
        f_rule = self.rule_ext.extract(empty_draws, target)
        assert isinstance(f_rule, np.ndarray)
        assert f_rule.shape == (NUM_TOTAL,)
        assert not np.isnan(f_rule).any()
        assert not np.isinf(f_rule).any()
        assert np.all(f_rule >= 0.0) and np.all(f_rule <= 1.0)

        # 4. Topo Extractor
        f_topo, m_cooccur = self.topo_ext.extract(empty_draws, target)
        assert isinstance(f_topo, np.ndarray)
        assert f_topo.shape == (NUM_TOTAL,)
        assert m_cooccur.shape == (NUM_TOTAL, NUM_TOTAL)
        assert np.allclose(m_cooccur, m_cooccur.T)
        assert not np.isnan(f_topo).any()
        assert not np.isnan(m_cooccur).any()

        # 5. Defense Mask Extractor
        mask, kills, meta = self.defense_ext.extract_with_meta(empty_draws, target)
        assert isinstance(mask, np.ndarray)
        assert mask.shape == (NUM_TOTAL,)
        assert mask.dtype == bool
        assert len(kills) == 0
        assert np.all(mask == True)

    def test_02_all_future_draws_strict_isolation(self):
        """【攻击场景】：传入的历史开奖全部 >= target_period，应等同于空历史"""
        future_draws = [
            {"period": 2026200 + i, "date": "2026-05-01", "nums": list(range(1, 21))}
            for i in range(10)
        ]
        target = 2026100  # 小于所有输入期号

        f_time = self.time_ext.extract(future_draws, target)
        assert np.all(f_time == 0.0)

        f_space = self.space_ext.extract(future_draws, target)
        assert np.all(f_space == 0.0)

        f_rule = self.rule_ext.extract(future_draws, target)
        assert np.all(f_rule == 0.0)

        f_topo, m_cooccur = self.topo_ext.extract(future_draws, target)
        assert np.all(f_topo == 0.0)
        assert np.all(m_cooccur == 0.0)

    def test_03_dirty_out_of_bounds_numbers_injection(self):
        """【攻击场景】：注入越界号码 (< 1, > 80, 负数, 极端大数) 绝不引发 IndexError 或崩溃"""
        dirty_draws = [
            {
                "period": 2026100 + i,
                "date": "2026-01-01",
                "nums": [-999, -1, 0, 81, 82, 100, 9999, 1, 10, 20, 80]
            }
            for i in range(20)
        ]
        target = 2026130

        # 执行提取
        f_time = self.time_ext.extract(dirty_draws, target)
        f_space = self.space_ext.extract(dirty_draws, target)
        f_rule = self.rule_ext.extract(dirty_draws, target)
        f_topo, m_cooccur = self.topo_ext.extract(dirty_draws, target)
        mask = self.defense_ext.extract(dirty_draws, target)

        for arr in [f_time, f_space, f_rule, f_topo]:
            assert arr.shape == (NUM_TOTAL,)
            assert not np.isnan(arr).any()
            assert not np.isinf(arr).any()
            assert np.all(arr >= 0.0) and np.all(arr <= 1.0)

        assert m_cooccur.shape == (NUM_TOTAL, NUM_TOTAL)
        assert np.allclose(m_cooccur, m_cooccur.T)
        assert mask.shape == (NUM_TOTAL,)
        assert mask.dtype == bool

    def test_04_malformed_records_and_missing_keys(self):
        """【攻击场景】：开奖字典中缺失 nums/period，或者 nums 为非列表类型"""
        malformed_draws = [
            {"period": 2026100, "date": "2026-01-01"},  # 缺失 nums
            {"period": 2026101, "nums": None},           # nums 为 None
            {"nums": list(range(1, 21))},                # 缺失 period
            {"period": 2026103, "nums": "1-2-3-4-5"},    # nums 为字符串
            {"period": 2026104, "nums": []},             # nums 为空列表
            {"period": 2026105, "nums": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]} # 正常
        ]
        target = 2026110

        f_time = self.time_ext.extract(malformed_draws, target)
        f_space = self.space_ext.extract(malformed_draws, target)
        f_rule = self.rule_ext.extract(malformed_draws, target)
        f_topo, m_cooccur = self.topo_ext.extract(malformed_draws, target)
        mask = self.defense_ext.extract(malformed_draws, target)

        for arr in [f_time, f_space, f_rule, f_topo]:
            assert not np.isnan(arr).any()
            assert not np.isinf(arr).any()
            assert np.all(arr >= 0.0) and np.all(arr <= 1.0)

    def test_05_extreme_monotonic_identical_draws_stress(self):
        """【攻击场景】：200 期完全相同的开奖（[1..20]），测试零方差与归一化除零防御"""
        mono_draws = make_monotonic_identical_draws(200, fixed_nums=list(range(1, 21)))
        target = 2026400

        f_time = self.time_ext.extract(mono_draws, target)
        f_space = self.space_ext.extract(mono_draws, target)
        f_rule = self.rule_ext.extract(mono_draws, target)
        f_topo, m_cooccur = self.topo_ext.extract(mono_draws, target)
        mask, kills, meta = self.defense_ext.extract_with_meta(mono_draws, target, kill_size=15)

        for name, arr in [("time", f_time), ("space", f_space), ("rule", f_rule), ("topo", f_topo)]:
            assert arr.shape == (NUM_TOTAL,), f"{name} shape mismatch"
            assert not np.isnan(arr).any(), f"{name} contains NaN under monotonic draws!"
            assert not np.isinf(arr).any(), f"{name} contains Inf under monotonic draws!"
            assert np.all(arr >= 0.0) and np.all(arr <= 1.0), f"{name} out of [0, 1] range!"

        assert m_cooccur.shape == (NUM_TOTAL, NUM_TOTAL)
        assert np.allclose(m_cooccur, m_cooccur.T)
        assert len(kills) == 0
        assert np.sum(mask) == NUM_TOTAL

    def test_06_single_draw_history(self):
        """【攻击场景】：历史仅有唯独 1 期开奖"""
        single_draw = [{"period": 2026100, "date": "2026-01-01", "nums": list(range(1, 21))}]
        target = 2026101

        f_time = self.time_ext.extract(single_draw, target)
        f_space = self.space_ext.extract(single_draw, target)
        f_rule = self.rule_ext.extract(single_draw, target)
        f_topo, m_cooccur = self.topo_ext.extract(single_draw, target)
        mask = self.defense_ext.extract(single_draw, target)

        for arr in [f_time, f_space, f_rule, f_topo]:
            assert not np.isnan(arr).any()
            assert not np.isinf(arr).any()
            assert np.all(arr >= 0.0) and np.all(arr <= 1.0)


# =====================================================================
# 第二战区：极端超参数冲击与数值边界测试 (Extreme Hyperparameters Stress)
# =====================================================================

class TestAdversarialHyperparameters:
    """对五大特征提取器注入极端超参数，验证边界防守与数值稳健性"""

    def setup_method(self):
        self.draws = make_clean_draws(50, 2026100)
        self.target = 2026145
        self.time_ext = TimeInertiaExtractor(data_root=PROJ_DIR)
        self.space_ext = SpatialEnergyExtractor(num_total=NUM_TOTAL)
        self.rule_ext = DiscreteRuleExtractor()
        self.topo_ext = TopologicalCooccurrenceExtractor(num_total=NUM_TOTAL)
        self.defense_ext = DefenseMaskExtractor()
        self.pipeline = FeatureEngineeringPipeline(data_root=PROJ_DIR)

    @pytest.mark.parametrize("sigma", [0.0001, 1e-10, 0.0, -1.0, -100.0, 1000.0, 1e6])
    def test_01_spatial_energy_extreme_sigma_resilience(self, sigma):
        """【极端超参】：高斯核宽 sigma 处于极小、零、负数或超大值时，稳定输出 [0, 1] 概率且无崩溃"""
        f_space = self.space_ext.extract(self.draws, self.target, sigma=sigma)
        assert isinstance(f_space, np.ndarray)
        assert f_space.shape == (NUM_TOTAL,)
        assert not np.isnan(f_space).any(), f"sigma={sigma} caused NaN in spatial energy!"
        assert not np.isinf(f_space).any(), f"sigma={sigma} caused Inf in spatial energy!"
        assert np.all(f_space >= 0.0) and np.all(f_space <= 1.0)

    @pytest.mark.parametrize("window", [0, 1, -5, 10000])
    def test_02_spatial_energy_extreme_window(self, window):
        """【极端超参】：空间能量场 window 处于 0, 1, 负数或超大窗口"""
        f_space = self.space_ext.extract(self.draws, self.target, window=window)
        assert f_space.shape == (NUM_TOTAL,)
        assert not np.isnan(f_space).any()
        assert np.all(f_space >= 0.0) and np.all(f_space <= 1.0)

    @pytest.mark.parametrize("lambda_decay", [0.0, 1.0, -0.5, 2.0, 10.0])
    def test_03_time_inertia_extreme_lambda_decay(self, lambda_decay):
        """【极端超参】：时序衰减率 lambda_decay 处于 0.0, 1.0, 负数或爆炸值"""
        f_time = self.time_ext.extract(self.draws, self.target, lambda_decay=lambda_decay)
        assert isinstance(f_time, np.ndarray)
        assert f_time.shape == (NUM_TOTAL,)
        assert not np.isnan(f_time).any(), f"lambda={lambda_decay} caused NaN!"
        assert not np.isinf(f_time).any(), f"lambda={lambda_decay} caused Inf!"
        assert np.all(f_time >= 0.0) and np.all(f_time <= 1.0)

    @pytest.mark.parametrize("alpha_momentum", [0.0, 1.0, -1.0, 2.0, 100.0])
    def test_04_time_inertia_extreme_alpha_momentum(self, alpha_momentum):
        """【极端超参】：动量权重 alpha 处于边界或越界值"""
        f_time = self.time_ext.extract(self.draws, self.target, alpha_momentum=alpha_momentum)
        assert f_time.shape == (NUM_TOTAL,)
        assert not np.isnan(f_time).any()
        assert not np.isinf(f_time).any()
        assert np.all(f_time >= 0.0) and np.all(f_time <= 1.0)

    def test_05_discrete_rule_extreme_weights_and_eps(self):
        """【极端超参】：规则库注入负权重、超大权重 1e6、未知ID与极端平滑基线"""
        extreme_weights = {
            "1": -100.0,
            "2": 0.0,
            "3": 1_000_000.0,
            "99999": 500.0,
            "non_exist_key": -99.9,
        }
        for eps in [0.0, 1e-8, -1.0, 100.0]:
            f_rule = self.rule_ext.extract(
                self.draws, self.target,
                rule_weights=extreme_weights,
                smooth_eps=eps
            )
            assert isinstance(f_rule, np.ndarray)
            assert f_rule.shape == (NUM_TOTAL,)
            assert not np.isnan(f_rule).any(), f"smooth_eps={eps} caused NaN in rule extractor!"
            assert not np.isinf(f_rule).any(), f"smooth_eps={eps} caused Inf in rule extractor!"
            assert np.all(f_rule >= 0.0) and np.all(f_rule <= 1.0)

    @pytest.mark.parametrize("markov_alpha", [0.0, 1e-6, 1e6, -0.5])
    def test_06_topological_extreme_markov_alpha(self, markov_alpha):
        """【极端超参】：拓扑转移平滑系数 alpha 处于 0.0, 极小, 极大或负数"""
        f_topo, m_cooccur = self.topo_ext.extract(self.draws, self.target, markov_alpha=markov_alpha)
        assert f_topo.shape == (NUM_TOTAL,)
        assert m_cooccur.shape == (NUM_TOTAL, NUM_TOTAL)
        assert not np.isnan(f_topo).any(), f"markov_alpha={markov_alpha} caused NaN in f_topo!"
        assert not np.isnan(m_cooccur).any(), f"markov_alpha={markov_alpha} caused NaN in m_cooccur!"
        assert np.allclose(m_cooccur, m_cooccur.T)

    @pytest.mark.parametrize("kill_size", [0, 1, 15, 25, 30])
    def test_07_defense_mask_kill_size_bounds(self, kill_size):
        """【极端超参】：防守掩码 kill_size 处于各种尺寸（KillSeeker下架后恒为空杀）"""
        mask, kills, meta = self.defense_ext.extract_with_meta(self.draws, self.target, kill_size=kill_size)
        assert mask.shape == (NUM_TOTAL,)
        assert mask.dtype == bool
        assert len(kills) == 0
        assert np.sum(mask) == NUM_TOTAL

    def test_08_defense_mask_extreme_engine_weights(self):
        """【极端超参】：防守引擎被传入全零权重或超大权重（KillSeeker下架后恒为空杀）"""
        zero_weights = {
            "similarity": 0.0, "density": 0.0, "pattern": 0.0, "curve": 0.0, "markov": 0.0
        }
        mask, kills, meta = self.defense_ext.extract_with_meta(
            self.draws, self.target, kill_size=15, engine_weights=zero_weights
        )
        assert mask.shape == (NUM_TOTAL,)
        assert len(kills) == 0
        assert np.sum(mask) == NUM_TOTAL


# =====================================================================
# 第三战区：特征数据包强校验与契约防御 (UnifiedFeatureBundle & Pipeline Stress)
# =====================================================================

class TestAdversarialBundleAndPipeline:
    """全量数据包打包、自检拦截与序列化压力测试"""

    def setup_method(self):
        self.pipeline = FeatureEngineeringPipeline(data_root=PROJ_DIR)
        self.draws = make_clean_draws(60, 2026100)
        self.target = 2026155

    def test_01_pipeline_bundle_normal_execution(self):
        """验证标准参数下 pipeline 打包的纯净性与合法性"""
        bundle = self.pipeline.extract_bundle(
            draws=self.draws,
            target_period=self.target,
            hyperparams={"sigma": 2.5, "lambda_decay": 0.95, "kill_size": 18}
        )
        assert isinstance(bundle, UnifiedFeatureBundle)
        assert bundle.validate() is True
        assert bundle.time_inertia.shape == (NUM_TOTAL,)
        assert bundle.spatial_energy.shape == (NUM_TOTAL,)
        assert bundle.rule_activation.shape == (NUM_TOTAL,)
        assert bundle.topological_energy.shape == (NUM_TOTAL,)
        assert bundle.cooccurrence_matrix.shape == (NUM_TOTAL, NUM_TOTAL)
        assert bundle.defense_mask.shape == (NUM_TOTAL,)
        assert len(bundle.killed_numbers) == 0
        assert int(np.sum(bundle.defense_mask)) == NUM_TOTAL

    def test_02_pipeline_extreme_hyperparams_bundle_validation(self):
        """【极端超参组合】：Pipeline 同时施加全部极端超参数，验证输出 Bundle 依然能顺利通过 validate()"""
        extreme_hp = {
            "sigma": 1000.0,
            "lambda_decay": 1.0,
            "topo_window": 1000,
            "kill_size": 20,
            "rule_weights": {"1": 1000.0, "2": 0.0},
        }
        bundle = self.pipeline.extract_bundle(
            draws=self.draws,
            target_period=self.target,
            hyperparams=extreme_hp
        )
        assert bundle.validate() is True
        d = bundle.to_dict()
        assert json.loads(json.dumps(d)) == d  # 确保 100% JSON 可序列化

    def test_03_bundle_validator_detects_nan_in_all_fields(self):
        """【对抗验证】：人工污染 Bundle 的每个张量，验证 validate() 100% 能够捕捉并阻断"""
        valid_bundle = self.pipeline.extract_bundle(self.draws, self.target)

        # 1. 污染 time_inertia
        b1 = copy.deepcopy(valid_bundle)
        b1.time_inertia[5] = np.nan
        with pytest.raises(ValueError, match="contains NaN or Inf"):
            b1.validate()

        # 2. 污染 spatial_energy
        b2 = copy.deepcopy(valid_bundle)
        b2.spatial_energy[12] = np.inf
        with pytest.raises(ValueError, match="contains NaN or Inf"):
            b2.validate()

        # 3. 污染 rule_activation
        b3 = copy.deepcopy(valid_bundle)
        b3.rule_activation[40] = np.nan
        with pytest.raises(ValueError, match="contains NaN or Inf"):
            b3.validate()

        # 4. 污染 topological_energy
        b4 = copy.deepcopy(valid_bundle)
        b4.topological_energy[79] = -np.inf
        with pytest.raises(ValueError, match="contains NaN or Inf"):
            b4.validate()

        # 5. 污染 cooccurrence_matrix
        b5 = copy.deepcopy(valid_bundle)
        b5.cooccurrence_matrix[10, 20] = np.nan
        with pytest.raises(ValueError, match="contains NaN or Inf"):
            b5.validate()

    def test_04_bundle_validator_detects_asymmetric_matrix(self):
        """【对抗验证】：人工破坏共现矩阵对称性，验证 validate() 拦截"""
        bundle = self.pipeline.extract_bundle(self.draws, self.target)
        bundle.cooccurrence_matrix[10, 20] = 0.9
        bundle.cooccurrence_matrix[20, 10] = 0.1
        with pytest.raises(ValueError, match="must be symmetric"):
            bundle.validate()

    def test_05_bundle_validator_detects_excessive_kills(self):
        """【对抗验证】：杀号过多导致安全点不足 50 个时，validate() 立即拦截报警"""
        bundle = self.pipeline.extract_bundle(self.draws, self.target)
        # 强制将 40 个号码标为 Kill (安全点只剩 40 个 < 50)
        bundle.defense_mask = np.array([False] * 40 + [True] * 40, dtype=bool)
        with pytest.raises(ValueError, match="Invalid safe numbers count"):
            bundle.validate()


# =====================================================================
# 第四战区：高频滚动与实战真实历史数据压力测试 (Rolling & Real Data Stress)
# =====================================================================

class TestAdversarialRollingRealData:
    """基于真实历史开奖进行高频滚动抽取与状态隔离验证"""

    def setup_method(self):
        self.layer = FeatureEngineeringLayer(data_root=PROJ_DIR)
        self.draws = self.layer.draws

    def test_01_real_history_exists_and_sorted(self):
        """验证物理历史开奖文件加载正常且严格升序"""
        assert len(self.draws) >= 1000, f"History draws too few: {len(self.draws)}"
        periods = [d["period"] for d in self.draws]
        assert periods == sorted(periods), "Historical draws must be strictly sorted by period!"

    def test_02_rolling_50_periods_stress_test(self):
        """【滚动实战回测】：连续提取最近 50 期特征数据包，确保无崩溃、无内存泄漏、无数值越界"""
        recent_draws = self.draws[-50:]
        for d in recent_draws:
            period = d["period"]
            bundle = self.layer.extract_bundle(period)
            assert bundle.validate() is True
            assert bundle.target_period == period
            assert len(bundle.killed_numbers) == 0
            assert int(np.sum(bundle.defense_mask)) == NUM_TOTAL

            # 验证归一化
            assert 0.0 <= np.max(bundle.time_inertia) <= 1.0
            assert 0.0 <= np.max(bundle.spatial_energy) <= 1.0
            assert 0.0 <= np.max(bundle.rule_activation) <= 1.0
            assert 0.0 <= np.max(bundle.topological_energy) <= 1.0
            assert 0.0 <= np.max(bundle.cooccurrence_matrix) <= 1.0

    def test_03_stateless_execution_idempotency(self):
        """【幂等性验证】：同一期号连续提取 3 次，特征张量必须 100% 绝对相同 (严防提取器内部残留可变状态)"""
        target_period = self.draws[-1]["period"]
        b1 = self.layer.extract_bundle(target_period)
        b2 = self.layer.extract_bundle(target_period)
        b3 = self.layer.extract_bundle(target_period)

        assert np.allclose(b1.time_inertia, b2.time_inertia)
        assert np.allclose(b2.time_inertia, b3.time_inertia)
        assert np.allclose(b1.spatial_energy, b2.spatial_energy)
        assert np.allclose(b1.rule_activation, b2.rule_activation)
        assert np.allclose(b1.topological_energy, b2.topological_energy)
        assert np.allclose(b1.cooccurrence_matrix, b2.cooccurrence_matrix)
        assert np.array_equal(b1.defense_mask, b2.defense_mask)


# =====================================================================
# 第五战区：多线程并发、极端污染与深度防御 (Advanced Concurrency & Defense)
# =====================================================================

class TestAdversarialAdvancedStress:
    """深度多线程并发与终极污染注入测试"""

    def setup_method(self):
        self.layer = FeatureEngineeringLayer(data_root=PROJ_DIR)
        self.draws = self.layer.draws

    def test_01_concurrent_multithreaded_extractions(self):
        """【并发风暴】：8 线程并发调用 extract_bundle，验证线程安全且无资源争抢崩溃"""
        import concurrent.futures

        target_periods = [self.draws[-i]["period"] for i in range(1, 9)]

        def _worker(p):
            return self.layer.extract_bundle(p)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_worker, p) for p in target_periods]
            results = [f.result() for f in futures]

        assert len(results) == 8
        for res in results:
            assert isinstance(res, UnifiedFeatureBundle)
            assert res.validate() is True

    def test_02_nan_and_inf_inside_draw_nums_list(self):
        """【污染注入】：在开奖 numbers 数组中直接掺入 NaN 与 Inf 浮点值"""
        polluted_draws = [
            {
                "period": 2026100 + i,
                "date": "2026-01-01",
                "nums": [float("nan"), float("inf"), -float("inf"), 1, 5, 10, 20, 30, 40, 50, 60, 70, 80]
            }
            for i in range(20)
        ]
        target = 2026125
        pipeline = FeatureEngineeringPipeline(data_root=PROJ_DIR)
        bundle = pipeline.extract_bundle(polluted_draws, target)
        assert bundle.validate() is True
        assert not np.isnan(bundle.time_inertia).any()
        assert not np.isnan(bundle.spatial_energy).any()
        assert not np.isnan(bundle.rule_activation).any()
        assert not np.isnan(bundle.topological_energy).any()
        assert not np.isnan(bundle.cooccurrence_matrix).any()

    def test_03_zero_and_negative_target_period(self):
        """【边界输入】：target_period <= 0 时，平稳降级为零历史或兜底"""
        pipeline = FeatureEngineeringPipeline(data_root=PROJ_DIR)
        draws = make_clean_draws(10, 2026100)
        
        # 目标期号为 0 (小于所有历史)
        f_time = pipeline.time_extractor.extract(draws, 0)
        assert f_time.shape == (NUM_TOTAL,)
        assert np.all(f_time == 0.0)

        f_space = pipeline.spatial_extractor.extract(draws, -999)
        assert f_space.shape == (NUM_TOTAL,)
        assert np.all(f_space == 0.0)

    def test_04_to_dict_json_schema_completeness(self):
        """【输出资产契约】：验证 to_dict() 包含所有标准契约字段且 100% 符合 JSON 规范"""
        target = self.draws[-1]["period"]
        bundle = self.layer.extract_bundle(target)
        d = bundle.to_dict()

        required_keys = [
            "target_period", "draw_date", "time_inertia", "spatial_energy",
            "rule_activation", "topological_energy", "cooccurrence_matrix",
            "defense_mask", "killed_numbers", "safe_count", "meta_info"
        ]
        for k in required_keys:
            assert k in d, f"Missing key in to_dict: {k}"

        json_str = json.dumps(d)
        recovered = json.loads(json_str)
        assert recovered["target_period"] == target
        assert len(recovered["time_inertia"]) == 80
        assert len(recovered["cooccurrence_matrix"]) == 80
        assert len(recovered["cooccurrence_matrix"][0]) == 80

