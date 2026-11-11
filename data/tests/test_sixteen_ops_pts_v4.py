# -*- coding: utf-8 -*-
"""ops_pts_v4：点位频段 / 刚开不加 / tip 精选优先。"""
from __future__ import annotations

from unittest.mock import patch

from backend.modules.sixteen.sixteen_engine import build_daily_ops_brief


def _ball(n, freq, score, omission=2):
    return {
        "number": n,
        "freq_16": freq,
        "midhot_score": score,
        "score": score,
        "omission": omission,
        "recent_8_hits": 1,
    }


def test_ops_pts_v4_boost_freq_and_just_opened():
    midhot = [
        _ball(10, 4, 10.0),   # 点位∩频4 → 应 ×1.15
        _ball(11, 6, 10.0),   # 点位∩频6 → 不加
        _ball(12, 4, 9.5),    # 刚开∩点位 → 不加
        _ball(13, 4, 9.0),    # 非点位
        _ball(14, 5, 8.5),    # 点位∩频5∩精选
        _ball(15, 3, 8.0),
    ]
    points = {10, 11, 12, 14}
    with patch(
        "backend.modules.sixteen.sixteen_engine._load_points_for_period",
        return_value={"matched": True, "points": list(points), "period": 2026248, "source": "test"},
    ), patch(
        "backend.modules.sixteen.sixteen_engine._load_killseeker_sets",
        return_value={"available": False, "period": None, "high": [], "mid": [], "low": [], "all": []},
    ), patch(
        "backend.modules.sixteen.sixteen_engine._load_kill_avg_high_rate",
        return_value={"avg_high_rate": None, "n": 0, "source": None},
    ):
        brief = build_daily_ops_brief(
            target_period=2026248,
            latest_period=2026247,
            latest_nums=[12, 99],  # 12 刚开
            ball_details=[],
            midhot_ranked=midhot,
            rebound_ranked=[],
            freq_bucket_picks={
                "all_picks": [14, 10],
                "buckets": [{"bucket": "4", "pool_size": 2, "picks": [14, 10], "rests": [], "line": ""}],
            },
            co_matrix={},
        )

    assert brief["scoring_version"] == "ops_pts_v4"
    by_n = {r["number"]: r for r in brief["ranking"]}
    assert by_n[10]["points_boost"] == 1.15
    assert by_n[11]["points_boost"] == 1.0  # freq6
    assert by_n[12]["points_boost"] == 1.0  # 刚开
    assert by_n[14]["points_boost"] == 1.15

    # tip3 优先 点位∩精选 → 14,10 应靠前
    assert 14 in brief["tip3"]
    assert 10 in brief["tip3"]

    v3 = brief["scoring_contrast"]["raw_v3_contrast"]
    assert len(v3["tip3"]) == 3
    assert len(v3["top5"]) == 3
    assert brief["kill_shrink_mode"] == "off"


def test_kill_shrink_retired_top3_alias_fields():
    midhot = [
        _ball(1, 4, 20.0),
        _ball(2, 4, 19.0),
        _ball(3, 4, 18.0),
        _ball(4, 4, 17.0),
        _ball(5, 4, 16.0),
        _ball(6, 4, 15.0),
        _ball(7, 4, 14.0),
        _ball(8, 4, 13.0),
        _ball(9, 4, 12.0),
        _ball(10, 4, 11.0),
        _ball(11, 4, 10.0),
        _ball(12, 4, 9.0),
        _ball(13, 4, 8.0),
    ]
    high_kills = [8, 9, 10]
    with patch(
        "backend.modules.sixteen.sixteen_engine._load_points_for_period",
        return_value={"matched": True, "points": list(range(1, 14)), "period": 1, "source": "t"},
    ), patch(
        "backend.modules.sixteen.sixteen_engine._load_killseeker_sets",
        return_value={
            "available": True, "period": 1, "high": high_kills, "mid": [], "low": [], "all": high_kills,
        },
    ), patch(
        "backend.modules.sixteen.sixteen_engine._load_kill_avg_high_rate",
        return_value={"avg_high_rate": 0.80, "n": 20, "source": "t"},
    ):
        brief = build_daily_ops_brief(
            target_period=1,
            latest_period=0,
            latest_nums=[],
            ball_details=[],
            midhot_ranked=midhot,
            rebound_ranked=[],
            freq_bucket_picks={"all_picks": [], "buckets": []},
            co_matrix={},
        )

    assert brief["kill_shrink_mode"] == "off"
    tip3 = brief["tip3"]
    top5 = brief["top5"]
    top12 = brief["top12"]
    assert len(tip3) == 3
    assert len(top5) == 3
    assert len(top12) == 3
    assert top5 == tip3
    assert top12 == tip3
