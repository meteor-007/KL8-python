# -*- coding: utf-8 -*-
"""
三维交集共识定胆与选2冷热对冲引擎单元测试与高压验证 (Unit & Adversarial Tests)
================================================================================
"""

import os
import sys
import pytest

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = os.path.dirname(_CURR_DIR)
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.modules.legacy.consensus_straddle.engine import (
    ConsensusStraddleEngine,
    ConsensusPredictionResult,
    MIN_STRADDLE_SPAN,
    MAX_STRADDLE_SPAN,
    TOTAL_BALL_COUNT,
)
from backend.modules.legacy.consensus_straddle.reviewer import ConsensusStraddleReviewer


def test_engine_basic_prediction():
    """测试基本推演功能与输出数据完整性。"""
    engine = ConsensusStraddleEngine()
    # 构造简单模拟数据 (25 期，每期 20 码)
    mock_draws = []
    for i in range(25):
        # 产生合法球号列表
        nums = [(i * 3 + j) % 80 + 1 for j in range(20)]
        mock_draws.append(sorted(set(nums)))

    # 填充不足20的情况
    for idx, d in enumerate(mock_draws):
        while len(d) < 20:
            d.append((len(d) + idx * 7) % 80 + 1)
            d = sorted(set(d))
        mock_draws[idx] = d

    res = engine.run_prediction(
        all_draws_asc=mock_draws,
        target_period=2026255,
        daily_points=[1, 3, 8, 10, 16, 20, 33, 35, 36, 40, 41, 45, 46, 47, 55, 60, 61, 65, 68, 73],
        tri_high_data={
            "repeat_high": [23, 24, 29, 47, 51, 59],
            "edge_high_left": [1, 53, 64, 61],
            "edge_high_right": [2, 52, 63, 48],
            "cold_high": [76, 33, 44, 55, 25, 20, 32, 45]
        }
    )

    assert isinstance(res, ConsensusPredictionResult)
    assert 1 <= res.consensus_gold <= TOTAL_BALL_COUNT
    assert 1 <= res.consensus_silver <= TOTAL_BALL_COUNT
    assert 1 <= res.consensus_bronze <= TOTAL_BALL_COUNT
    assert len(res.top3_gold_dān) == 3
    assert len(res.top5_defense_line) == 5

    # 验证选2对冲约束
    for p in res.top5_straddle_pairs:
        assert MIN_STRADDLE_SPAN <= p.span <= MAX_STRADDLE_SPAN
        assert p.attack_ball % 10 != p.defense_ball % 10
        assert abs(p.attack_ball - p.defense_ball) > 1
        assert p.pair_score > 0


def test_engine_empty_draws_exception():
    """测试空数据输入防御。"""
    engine = ConsensusStraddleEngine()
    with pytest.raises(ValueError):
        engine.run_prediction(all_draws_asc=[], target_period=2026255)


def test_reviewer_short_history_exception():
    """测试回测期数过大时的边界防守。"""
    reviewer = ConsensusStraddleReviewer()
    with pytest.raises(ValueError):
        reviewer.run_walk_forward_review(n_periods=99999, verbose=False)
