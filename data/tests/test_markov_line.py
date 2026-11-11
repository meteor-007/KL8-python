# -*- coding: utf-8 -*-
"""
马尔可夫链与特征直线校准模块工业级单元与集成测试套件 (Markov Line Test Suite)
========================================================================
遵循 AI 工业级编码四大铁律：
  1. 测试驱动与物理结果强校验 (TDD & I/O Verification)
  2. 零伪代码与全逻辑覆盖
  3. 对抗性极限与边界测试 (极端和值、单期越界、冷号极值)
  4. 端到端服务链路与落盘文件物理校验 (>0 字节, JSON Schema)
"""

import os
import json
import pytest
import numpy as np

from backend.modules.markov_line.feature_extractor import FeatureExtractor, DrawFeature, PRIME_SET
from backend.modules.markov_line.state_space import StateSpace, StateDefinition
from backend.modules.markov_line.markov_engine import MarkovEngine
from backend.modules.markov_line.line_calibrator import LineCalibrator, LineFitResult, ResidualReboundSignal
from backend.modules.markov_line.decoder import MarkovLineDecoder
from backend.modules.markov_line.service import run_markov_line_pipeline, get_output_paths


class TestFeatureExtractor:
    """测试特征提取器的正确性与鲁棒性"""

    def test_extract_basic_features(self):
        extractor = FeatureExtractor(total_balls=80)
        # 构造一组标准 20 码
        numbers = [2, 3, 5, 7, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 79, 80]
        prev_nums = [1, 2, 3, 4, 10, 20]
        omissions = {b: b % 5 for b in range(1, 81)}

        feat = extractor.extract_single_draw_basic(
            issue="2026200",
            numbers=numbers,
            prev_numbers=prev_nums,
            current_omissions=omissions,
        )

        assert feat.issue == "2026200"
        assert feat.sum_val == sum(numbers)
        assert feat.span_val == 80 - 2
        assert feat.odd_count + feat.even_count == 20
        assert feat.big_count + feat.small_count == 20
        assert feat.repeat_count == len(set(numbers) & set(prev_nums))
        assert feat.tail_entropy > 0.0
        assert sum(feat.zone_density) == 20

    def test_adversarial_empty_numbers(self):
        extractor = FeatureExtractor(total_balls=80)
        with pytest.raises(ValueError):
            extractor.extract_single_draw_basic("2026201", [])

    def test_consecutive_pairs_and_neighbors(self):
        extractor = FeatureExtractor(total_balls=80)
        # 含有 3 对连号: (1,2), (2,3), (10,11)
        numbers = [1, 2, 3, 10, 11] + list(range(20, 35))
        prev_nums = [15, 50]
        feat = extractor.extract_single_draw_basic("2026202", numbers, prev_nums)
        assert feat.consecutive_pairs >= 3


class TestStateSpace:
    """测试状态空间分箱映射与编解码"""

    def test_state_space_coverage(self):
        space = StateSpace()
        assert space.num_states == 6
        assert len(space.id_to_state) == 6
        assert len(space.key_to_id) == 6

    def test_encode_decode_roundtrip(self):
        space = StateSpace()
        extractor = FeatureExtractor()
        # 低和值 + 离散无连号 + 冷号回补态
        low_nums = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39]  # sum = 400 (<785)
        feat = extractor.extract_single_draw_basic(
            issue="2026203",
            numbers=low_nums,
            current_omissions={b: 10 for b in range(1, 81)},
        )

        state_id = space.encode(feat)
        assert 0 <= state_id < 6
        state_def = space.decode(state_id)
        assert state_def.sum_level == "SUM_LOW"
        assert state_def.momentum_level == "COLD_REBOUND"

    def test_invalid_state_id(self):
        space = StateSpace()
        with pytest.raises(KeyError):
            space.decode(999)


class TestMarkovEngine:
    """测试马尔可夫转移核心逻辑"""

    def test_fit_and_row_normalization(self):
        engine = MarkovEngine(num_states=10, half_life=20.0, smoothing_alpha=0.1)
        synthetic_seq = [0, 1, 2, 0, 1, 3, 4, 2, 1, 0, 5, 2, 1, 0] * 5
        engine.fit(synthetic_seq)

        assert engine.is_fitted
        # 验证一阶矩阵每一行之和均为 1.0 (容许浮点微弱误差)
        row_sums = engine.trans_matrix_1st.sum(axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-5)

        # 验证平稳分布和为 1.0
        assert np.isclose(np.sum(engine.stationary_dist), 1.0, atol=1e-5)

    def test_predict_next_state(self):
        engine = MarkovEngine(num_states=10)
        seq = [1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3]
        engine.fit(seq)

        prob_dist = engine.predict_next_state_distribution(current_state=2, prev_state=1)
        assert len(prob_dist) == 10
        assert np.isclose(np.sum(prob_dist), 1.0, atol=1e-5)
        # 在该序列中 2 总是转移到 3，故状态 3 概率应最高
        assert np.argmax(prob_dist) == 3


class TestLineCalibrator:
    """测试直线拟合校准与残差反弹检测"""

    def test_pp_straight_line_perfect_match(self):
        calibrator = LineCalibrator()
        # 构造一组完全一致的理论概率与经验频率
        probs = np.array([0.1, 0.2, 0.3, 0.4])
        emp = np.array([0.1, 0.2, 0.3, 0.4])

        res = calibrator.calibrate_pp_straight_line(probs, emp)
        assert res.is_straight is True
        assert np.isclose(res.r_squared, 1.0, atol=1e-3)
        assert np.isclose(res.ks_statistic, 0.0, atol=1e-3)

    def test_detect_residual_rebound(self):
        calibrator = LineCalibrator()
        # 模拟 50 期开奖，假设号码 77 在前 45 期一次都没出（深度凹陷），在最后 2 期开始出号（拐头反弹）
        draws = []
        for t in range(48):
            draws.append(list(range(1, 21)))  # 没有 77
        # 第 49、50 期出现 77
        draws.append([77] + list(range(1, 20)))
        draws.append([77] + list(range(1, 20)))

        signals = calibrator.detect_residual_rebound_signals(draws, window_size=50, total_balls=80)
        assert len(signals) == 80
        # 找到 77 号的信号
        sig_77 = next(s for s in signals if s.target_id == 77)
        assert sig_77.is_rebounding is True
        assert sig_77.rebound_strength > 0.0


class TestMarkovHyperparamOptimizer:
    """测试超参数闭环寻优与直线拉直能力"""

    def test_optimize_parameters_trajectory(self):
        from backend.modules.markov_line.calibrator_optimizer import MarkovHyperparamOptimizer
        optimizer = MarkovHyperparamOptimizer(num_states=10)
        # 构造长时序
        seq = [0, 1, 2, 3, 4, 1, 2, 0, 3, 2, 1, 4] * 6
        res = optimizer.optimize_parameters(seq, eval_window=30)

        assert res.best_half_life >= 15.0
        assert res.best_alpha >= 0.01
        assert res.best_beta >= 0.05
        assert len(res.trajectory) >= 10
        assert res.best_r2 > 0.0


class TestMarkovLinePipelineEndToEnd:
    """端到端完整流水线运行与物理文件落盘强校验"""

    def test_pipeline_execution_and_file_verification(self):
        result = run_markov_line_pipeline(limit=80)

        # 校验返回字段完整性
        assert result["module_name"] == "markov_line"
        assert len(result["top5_gold"]) == 5
        assert len(result["top12_elite"]) == 12
        assert all(1 <= b <= 80 for b in result["top5_gold"])
        assert all(1 <= b <= 80 for b in result["top12_elite"])

        # 校验直线校准数据
        cal = result["straight_line_calibration"]
        assert "r_squared" in cal
        assert "ks_statistic" in cal
        assert "is_straight" in cal

        # 物理落盘检验
        paths = get_output_paths()
        for key, fpath in paths.items():
            assert os.path.exists(fpath), f"目标物理文件未生成: {fpath}"
            fsize = os.path.getsize(fpath)
            assert fsize > 0, f"物理文件大小为0字节: {fpath}"

            if fpath.endswith(".json"):
                with open(fpath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    assert loaded["target_issue"] == result["target_issue"]
                    assert len(loaded["top5_gold"]) == 5
