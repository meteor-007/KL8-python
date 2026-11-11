# -*- coding: utf-8 -*-
"""变分神经主动推理系统单元与对抗性测试 (Unit & Adversarial Tests)。

【测试目标】:
  1. 验证 FlyWire 先验图谱的数学性质 (归一化、严格正定、无 NaN)；
  2. 验证拓扑弹性重连机制 (剪枝阈值、时间衰减)；
  3. 验证 ACT-UCA 坐标上升自由能极小化收敛性与 KL 散度告警；
  4. 验证 Keystone 枢纽中心性与选2双飞搭档提炼；
  5. Challenger 对抗性压测（脏数据、越界球号、空输入、奇异矩阵防御）。

@author Antigravity Quant Team
@since 2026-09-20
"""

import os
import sys
import pytest
import numpy as np

# 确保 backend 在系统路径中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "backend")

if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.modules.active_inference.graph_prior import GraphPriorBuilder, TOTAL_BALLS
from backend.modules.active_inference.dynamic_rewire import DynamicRewirer
from backend.modules.active_inference.free_energy_cavi import FreeEnergyOptimizer, ALERT_KL_DIVERGENCE_THRESHOLD
from backend.modules.active_inference.keystone import KeystoneExtractor
from backend.modules.active_inference.engine import ActiveInferenceEngine


@pytest.fixture
def mock_historical_draws():
    """构造 50 期合法的模拟开奖数据 (每期恰好 20 个 1..80 之间的不重复球)。"""
    rng = np.random.RandomState(42)
    draws = []
    for _ in range(50):
        # 产生 20 个不重复的 1..80 号码并排序
        balls = sorted(rng.choice(np.arange(1, 81), size=20, replace=False).tolist())
        draws.append(balls)
    return draws


class TestActiveInferenceModule:
    """变分主动推理模块核心测试套件。"""

    def test_flywire_prior_builder_properties(self, mock_historical_draws):
        """测试 1: FlyWire 先验图谱的数学规范性。"""
        builder = GraphPriorBuilder()
        prior_matrix = builder.build_prior_matrix(mock_historical_draws, use_cache=False)

        # 校验形状
        assert prior_matrix.shape == (TOTAL_BALLS, TOTAL_BALLS)
        # 校验无 NaN 和 Inf 毒丸
        assert not np.isnan(prior_matrix).any()
        assert not np.isinf(prior_matrix).any()
        # 校验全为严格正数 (狄利克雷平滑保证)
        assert (prior_matrix > 0.0).all()
        # 校验行概率和归一化为 1.0 (容差 1e-5)
        row_sums = prior_matrix.sum(axis=1)
        np.testing.assert_allclose(row_sums, np.ones(TOTAL_BALLS), atol=1e-5)

    def test_dynamic_rewirer_functionality(self, mock_historical_draws):
        """测试 2: 拓扑弹性重连器与边剪枝。"""
        builder = GraphPriorBuilder()
        prior_matrix = builder.build_prior_matrix(mock_historical_draws, use_cache=False)

        rewirer = DynamicRewirer(window_size=20, decay_factor=0.60)
        posterior_q, ef_norm, rw_norm = rewirer.rewire_network(mock_historical_draws, prior_matrix)

        assert posterior_q.shape == (TOTAL_BALLS, TOTAL_BALLS)
        assert ef_norm.shape == (TOTAL_BALLS,)
        assert rw_norm.shape == (TOTAL_BALLS,)
        assert not np.isnan(posterior_q).any()
        # 对角线元素应为 0（无自环）
        np.testing.assert_allclose(np.diag(posterior_q), np.zeros(TOTAL_BALLS), atol=1e-6)
        # 行归一化校验
        row_sums = posterior_q.sum(axis=1)
        np.testing.assert_allclose(row_sums, np.ones(TOTAL_BALLS), atol=1e-5)

    def test_act_uca_free_energy_cavi_optimizer(self, mock_historical_draws):
        """测试 3: ACT-UCA 变分坐标上升求解器收敛与变盘检测。"""
        builder = GraphPriorBuilder()
        prior = builder.build_prior_matrix(mock_historical_draws, use_cache=False)
        rewirer = DynamicRewirer(window_size=20)
        q, ef, rw = rewirer.rewire_network(mock_historical_draws, prior)

        optimizer = FreeEnergyOptimizer(max_iters=30)
        res = optimizer.optimize_potentials(ef, rw, q, prior)

        # 潜能向量长度与取值范围校验
        assert res.optimal_potentials.shape == (TOTAL_BALLS,)
        assert (res.optimal_potentials >= 0.0).all() and (res.optimal_potentials <= 1.0).all()
        # 自由能与 KL 散度非负
        assert res.kl_divergence >= 0.0
        assert res.iterations_run > 0

    def test_keystone_extractor_gold3_and_pairs(self, mock_historical_draws):
        """测试 4: Keystone 枢纽提取器 Top 3 金胆与选2搭档。"""
        builder = GraphPriorBuilder()
        prior = builder.build_prior_matrix(mock_historical_draws, use_cache=False)
        rewirer = DynamicRewirer(window_size=20)
        q, ef, rw = rewirer.rewire_network(mock_historical_draws, prior)
        optimizer = FreeEnergyOptimizer(max_iters=20)
        opt_res = optimizer.optimize_potentials(ef, rw, q, prior)

        extractor = KeystoneExtractor()
        keystone_res = extractor.extract_keystones_and_bonds(q, opt_res.optimal_potentials, top_pair_count=3)

        gold_3 = keystone_res.keystone_gold_3
        # 校验 Top 3 恰好为 3 个不同球且在 1..80 之间
        assert len(gold_3) == 3
        assert len(set(gold_3)) == 3
        assert all(1 <= b <= 80 for b in gold_3)

        # 校验选2搭档
        assert len(keystone_res.top_pair_bonds) == 3
        for b1, b2, score in keystone_res.top_pair_bonds:
            assert 1 <= b1 <= 80
            assert 1 <= b2 <= 80
            assert b1 != b2
            assert score >= 0.0

    def test_end_to_end_engine_pipeline(self, mock_historical_draws):
        """测试 5: 主动推理引擎 H-E-A-D 端到端全流程。"""
        engine = ActiveInferenceEngine(recent_window_size=25)
        res = engine.run_prediction(mock_historical_draws, target_issue="2026999")

        assert res.target_issue == "2026999"
        assert len(res.golden_keystones_3) == 3
        assert len(res.predicted_top5) == 5
        assert len(res.predicted_top12) == 12
        assert len(res.best_pair_bonds) == 3
        assert "Keystone 枢纽金胆" in res.summary_report


class TestAdversarialAndBoundaries:
    """Challenger 对抗性极限边界攻击测试。"""

    def test_adversarial_insufficient_samples(self):
        """对抗测试 1: 样本不足时应抛出明确业务异常，禁止静默崩溃。"""
        engine = ActiveInferenceEngine()
        with pytest.raises(ValueError, match="开奖样本不足"):
            engine.run_prediction([[1, 2, 3]])

    def test_adversarial_dirty_and_out_of_range_balls(self):
        """对抗测试 2: 注入脏数据（负数、越界球号 999、0 号），引擎必须平稳过滤。"""
        dirty_draws = []
        for _ in range(30):
            dirty_draws.append([0, -5, 999, 10, 20, 30, 40, 50, 60, 70, 80])

        engine = ActiveInferenceEngine()
        # 不会崩溃，自动防御性清洗
        res = engine.run_prediction(dirty_draws, target_issue="DIRTY_TEST")
        assert len(res.golden_keystones_3) == 3
        assert all(1 <= b <= 80 for b in res.golden_keystones_3)

    def test_adversarial_extreme_kl_regime_shift(self):
        """对抗测试 3: 模拟极端变盘（后验 Q 与先验 P 完全正交倒挂），触发变盘预警。"""
        optimizer = FreeEnergyOptimizer()
        # 构造差异极大的正交矩阵
        p_uniform = np.full((TOTAL_BALLS, TOTAL_BALLS), 1.0 / TOTAL_BALLS)
        q_skewed = np.zeros((TOTAL_BALLS, TOTAL_BALLS))
        q_skewed[:, 0] = 0.999
        q_skewed += 1e-4
        q_skewed /= q_skewed.sum(axis=1, keepdims=True)

        kl_div = optimizer.calculate_kl_divergence(q_skewed, p_uniform)
        assert kl_div > ALERT_KL_DIVERGENCE_THRESHOLD
