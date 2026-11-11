# -*- coding: utf-8 -*-
"""统一对账账本：snapshot / settle 假数据。"""
from __future__ import annotations

import json
import os
import tempfile

from backend.modules.unified_audit.bridges import build_bridge_shortlist, build_strategy_flags
from backend.modules.unified_audit.ledger import load_by_period, upsert_row
from backend.modules.unified_audit.schema import empty_row, settle_hits


def test_settle_hits_and_ledger_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        row = empty_row(2026248, 2026247)
        row["a_tip3"] = [1, 2, 3]
        row["a_top5"] = [1, 2, 3, 4, 5]
        row["a_top12"] = list(range(1, 13))
        row["b_vip_top5"] = [1, 10, 20, 30, 40]
        row["b_twin_pair"] = [11, 13]
        row["pick2_pair"] = [1, 2]
        row["suppression_top1"] = 1
        row["suppression_top3"] = [1, 2, 3]
        row["bridge_shortlist"] = [1, 10]
        row["kill_high"] = [70, 71, 72, 73]
        row["a_scoring_version"] = "ops_pts_v4"
        upsert_row(row, tmp)

        loaded = load_by_period(2026248, tmp)
        assert loaded is not None
        assert loaded["a_tip3"] == [1, 2, 3]

        actual = [1, 2, 11, 13, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]
        settled = settle_hits(loaded, actual)
        assert settled["settled"] is True
        assert settled["hits"]["tip3_hits"] == 2
        assert settled["hits"]["top5_hits"] == 2
        assert settled["hits"]["vip_hits"] == 1
        assert settled["hits"]["twin_double"] is True
        assert settled["hits"]["pick2_both"] is True
        assert settled["hits"]["suppression_top1_hit"] is True
        assert settled["hits"]["bridge_hits"] == 1
        assert settled["hits"]["kill_high_opened"] == 0
        assert settled["hits"]["kill_high_miss_rate"] == 0.0

        upsert_row(settled, tmp)
        again = load_by_period(2026248, tmp)
        assert again["settled"] is True
        assert again["hits"]["tip3_hits"] == 2

        # latest json
        latest_path = os.path.join(tmp, "storage", "reviews", "unified_daily_audit_latest.json")
        # ledger writes under proj_dir/storage/reviews — our tmp is proj_dir
        from backend.modules.unified_audit.ledger import latest_path as lp
        p = lp(tmp)
        assert os.path.exists(p)
        with open(p, "r", encoding="utf-8") as f:
            j = json.load(f)
        assert j["target_period"] == 2026248


def test_bridges_and_strategy_flags():
    b = build_bridge_shortlist(
        ops_pool=[1, 2, 3, 4, 5],
        vip_top5=[3, 9, 10],
        rebound={"gold": 7, "silver": 8, "bronze": 9},
        cold_high=[7, 20],
        homology4=[4, 5, 6, 7],
        midhot_picks4=[4, 11],
        max_n=6,
    )
    assert 3 in b["bridge_shortlist"]  # ops∩VIP
    assert 7 in b["bridge_shortlist"]  # rebound∩冷高
    assert 4 in b["bridge_shortlist"]  # 同源∩精选

    flags = build_strategy_flags(
        tail0_count=0,
        freq3_count=21,
        freq3_streak_high=0,
        homology_count=6,
        road_counts={"r0": 3, "r1": 9, "r2": 8},
    )
    assert flags["tail0_extinct"] is True
    assert flags["freq3_extreme"] is True
    assert flags["homology_ge5"] is True
    assert flags["homology_evidence_active"] is True
    assert flags["tactical_boost_allowed"] is True  # r0=3 ≤4
    assert flags["stance"] == "heavy"
