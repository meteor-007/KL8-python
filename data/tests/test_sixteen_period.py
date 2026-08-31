# -*- coding: utf-8 -*-
"""
Unit tests for 16-Period Medium-Hot Frequency Projection and Combinatorial Engine
"""
import os
import pytest
from backend.core.sixteen_period.sixteen_engine import (
    SixteenPeriodEngine,
    load_draws_from_file,
    run_single_period_analysis,
    WINDOW_SIZE
)
from backend.core.sixteen_period.sixteen_reviewer import SixteenPeriodReviewer
from backend.api.data_service import QuantDataService


def test_load_draws():
    draws = load_draws_from_file()
    assert len(draws) >= WINDOW_SIZE
    assert "period" in draws[0]
    assert "nums" in draws[0]
    assert len(draws[0]["nums"]) == 20
    # verify sorted chronologically (oldest to newest)
    assert draws[-1]["period"] > draws[0]["period"]


def test_sixteen_engine_analysis():
    draws = load_draws_from_file()
    engine = SixteenPeriodEngine(draws)
    res = engine.analyze_at_index(len(draws) - 1)

    assert "target_period" in res
    assert "gold_dan" in res
    assert "silver_dan" in res
    assert "medium_top5" in res
    assert len(res["medium_top5"]) == 5
    assert "top5_pairs" in res
    assert len(res["top5_pairs"]) == 5
    assert "top5_triples" in res
    assert len(res["top5_triples"]) == 5

    # check 80 matrix
    assert len(res["matrix_80"]) == 80
    for item in res["matrix_80"]:
        assert 1 <= item["number"] <= 80
        assert 0 <= item["freq_16"] <= 16
        assert isinstance(item["is_outgoing"], bool)
        assert item["next_freq_if_nodraw"] <= item["freq_16"]
        assert item["next_freq_if_draw"] >= item["freq_16"]

    # check distribution counts sum to 80
    dist = res["distribution_counts"]
    total_count = sum(dist[k] for k in dist)
    assert total_count == 80


def test_sixteen_reviewer_walk_forward():
    draws = load_draws_from_file()
    reviewer = SixteenPeriodReviewer(draws)
    res = reviewer.run_walk_forward_review(n_periods=10)

    assert "stats" in res
    assert "rows" in res
    assert res["stats"]["n_periods"] == 10
    assert len(res["rows"]) == 10
    assert "gold_hit_rate" in res["stats"]
    assert "top5_avg_hits" in res["stats"]
    assert "top1_both_rate" in res["stats"]


def test_data_service_and_report_generation():
    ds = QuantDataService()
    summary = ds.get_sixteen_summary()
    assert summary is not None
    assert summary.get("target_period") is not None

    review = ds.get_sixteen_review(10)
    assert review is not None
    assert "stats" in review

    hist = ds.get_sixteen_history_list()
    assert len(hist) > 0
    detail = ds.get_sixteen_history_detail(hist[0]["filename"])
    assert len(detail.get("content", "")) > 0
