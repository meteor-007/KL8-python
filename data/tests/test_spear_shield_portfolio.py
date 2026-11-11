# -*- coding: utf-8 -*-
"""
一胆拖三盾 · 选2组合拳自动化测试套件 (Test Spear-Shield Portfolio)
==============================================================
"""

import pytest
from backend.modules.spear_shield_portfolio.engine import (
    SpearShieldPortfolioEngine,
    PortfolioPredictionResult,
    MIN_STRADDLE_SPAN,
    MAX_STRADDLE_SPAN,
    TOTAL_BALL_COUNT
)
from backend.modules.spear_shield_portfolio.reviewer import SpearShieldPortfolioReviewer


def test_spear_shield_engine_prediction():
    engine = SpearShieldPortfolioEngine()
    mock_draws = []
    for i in range(25):
        nums = [(i * 3 + j) % 80 + 1 for j in range(20)]
        mock_draws.append(sorted(set(nums)))

    for idx, d in enumerate(mock_draws):
        while len(d) < 20:
            d.append((len(d) + idx * 7) % 80 + 1)
            d = sorted(set(d))
        mock_draws[idx] = d

    res = engine.run_prediction(
        all_draws_asc=mock_draws,
        target_period=2026255,
        daily_points=[1, 3, 8, 10, 16, 20, 33, 35, 36, 40],
        tri_high_data={"repeat_high": [23, 24], "cold_high": [76, 33]}
    )

    assert isinstance(res, PortfolioPredictionResult)
    assert 1 <= res.primary_spear <= TOTAL_BALL_COUNT
    assert len(res.shields) == 3
    assert len(res.pairs) == 3
    assert len(res.defense_line_4) == 4

    for p in res.pairs:
        assert p.spear == res.primary_spear
        assert p.shield in res.shields
        assert MIN_STRADDLE_SPAN <= p.span <= MAX_STRADDLE_SPAN
        assert p.spear % 10 != p.shield % 10
        assert abs(p.spear - p.shield) > 1


def test_spear_shield_reviewer_smoke():
    reviewer = SpearShieldPortfolioReviewer()
    # 冒烟测试 5 期回测
    review_res = reviewer.run_walk_forward_review(n_periods=5, verbose=False)

    assert "stats" in review_res
    assert review_res["stats"]["n_periods"] == 5
    assert len(review_res["rows"]) == 5
    assert review_res["no_lookahead_verified"] is True
