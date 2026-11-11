# -*- coding: utf-8 -*-
"""
点位012压缩推演引擎单元测试与对抗性压测 (Unit & Adversarial Tests)
================================================================================
"""
from __future__ import annotations

import os
import sys
import pytest

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = os.path.dirname(_CURR_DIR)
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.modules.point_road_compressor.engine import (
    PointRoadCompressor,
    PointRoadCompressorResult,
    get_road,
    get_zone_index,
    TOTAL_BALL_COUNT,
)


def test_compressor_basic_prediction():
    """测试基本推演功能、产物 Schema 与落盘物理校验。"""
    compressor = PointRoadCompressor()
    res = compressor.run_prediction(target_period="2026270")

    assert isinstance(res, PointRoadCompressorResult)
    assert res.target_period == "2026270"
    assert len(res.top3_gold) == 3
    assert len(res.top5_picks) == 5
    assert len(res.top10_defense) <= 10

    # 校验号码范围 1~80
    for num in res.top3_gold + res.top5_picks + res.top10_defense:
        assert 1 <= num <= TOTAL_BALL_COUNT

    # 校验选2跨路对冲
    assert len(res.gold_pairs) >= 1
    p_a, p_b = res.gold_pairs[0]
    assert 1 <= p_a <= TOTAL_BALL_COUNT
    assert 1 <= p_b <= TOTAL_BALL_COUNT
    assert p_a != p_b

    # 校验物理文件存在且大于0字节
    out_json = os.path.join(_PROJ_DIR, "storage", "outputs", "point_road_compressor", "point_road_compressed_2026270.json")
    out_md = os.path.join(_PROJ_DIR, "storage", "reports", "point_road_compressor_report_2026270.md")
    assert os.path.exists(out_json)
    assert os.path.getsize(out_json) > 100
    assert os.path.exists(out_md)
    assert os.path.getsize(out_md) > 100


def test_expand_neighborhood_logic():
    """测试正负2邻位引力展开与距离精算法。"""
    compressor = PointRoadCompressor()
    # 给定测试点位 [5, 10]
    pts = [5, 10]
    expanded = compressor.expand_neighborhood(pts, max_delta=2)

    # 5 的邻居: 3, 4, 5, 6, 7
    # 10 的邻居: 8, 9, 10, 11, 12
    assert 5 in expanded and expanded[5]["min_delta"] == 0 and expanded[5]["is_exact_point"]
    assert 4 in expanded and expanded[4]["min_delta"] == 1
    assert 3 in expanded and expanded[3]["min_delta"] == 2
    assert 10 in expanded and expanded[10]["min_delta"] == 0

    # 边界防守: 1 和 80 展开不得越界
    edge_pts = [1, 80]
    edge_exp = compressor.expand_neighborhood(edge_pts, max_delta=2)
    assert 0 not in edge_exp
    assert -1 not in edge_exp
    assert 81 not in edge_exp
    assert 82 not in edge_exp
    assert 1 in edge_exp and 2 in edge_exp and 3 in edge_exp
    assert 78 in edge_exp and 79 in edge_exp and 80 in edge_exp


def test_012_pruning_and_saturation():
    """测试 012 路偏态剪枝机制 (验证用户提出的 65 号剪枝场景)。"""
    compressor = PointRoadCompressor()
    # 构造模拟历史: 七区 (61-70) 中 2 路 (62, 65, 68) 连续密集出号
    mock_history = [
        {"issue": 2026269, "numbers": [62, 65, 68, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]},
        {"issue": 2026268, "numbers": [62, 65, 68, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]},
        {"issue": 2026267, "numbers": [62, 68, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]},
    ]

    macro_skew, zone_sat = compressor.analyze_012_skew(mock_history, lookback_macro=3, lookback_zone=3)
    z6 = zone_sat.get("zone_6", {})  # 61-70 是 zone_6 (0-indexed)
    assert z6.get("road_2_count", 0) >= 3

    # 当点位包含 65 时，65 应触发七区 2 路过度饱和剪枝
    pts = [65]
    expanded = compressor.expand_neighborhood(pts, max_delta=2)
    retained, pruned = compressor.score_and_compress(expanded, macro_skew, zone_sat, {})

    pruned_nums = [p["number"] for p in pruned]
    # 65 (2路) 应当在剪枝列表中
    assert 65 in pruned_nums
    pruned_item_65 = next(p for p in pruned if p["number"] == 65)
    assert "2路近3期过度饱和" in pruned_item_65["prune_reason"] or "过热" in pruned_item_65["prune_reason"]


def test_adversarial_boundary_conditions():
    """对抗性压测：空点位、越界号码、极值点位测试。"""
    compressor = PointRoadCompressor()
    # 空点位测试
    res_empty = compressor.score_and_compress({}, {}, {}, {})
    assert res_empty[0] == []
    assert res_empty[1] == []

    # 包含越界号的点位容错
    expanded = compressor.expand_neighborhood([-5, 0, 85, 999], max_delta=2)
    assert len(expanded) == 0  # 越界号被完全过滤

    # 选2搭档防守 (不足2码时)
    pairs = compressor.form_gold_pairs([])
    assert pairs == []
    pairs_single = compressor.form_gold_pairs([{"number": 10, "road": 1}])
    assert pairs_single == []


def test_walk_forward_review():
    """测试样本外滚动对账接口。"""
    compressor = PointRoadCompressor()
    review = compressor.run_walk_forward_review(n_periods=5, verbose=False)
    assert review.get("tested_periods", 0) > 0
    assert "avg_top3_hits" in review
    assert "lift_top3" in review
    assert "pruning_avoidance_rate" in review
