# -*- coding: utf-8 -*-
"""统一对账行 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def empty_row(target_period: int, based_on_period: Optional[int] = None) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "target_period": int(target_period),
        "based_on_period": int(based_on_period) if based_on_period is not None else None,
        "snapshot_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "settled": False,
        "settled_at": None,
        "actual_numbers": [],
        # A 轨
        "a_tip3": [],
        "a_top5": [],
        "a_top12": [],
        "a_rebound": {"gold": None, "silver": None, "bronze": None},
        "a_homology4": [],
        "a_scoring_version": None,
        # B 轨
        "b_vip_top5": [],
        "b_twin_pair": [],
        "b_road_ratio": None,
        # 其他舱
        "tri_high_gold": None,
        "tri_high_pair": [],
        "tri_high_top5": [],
        "tri_high_cold": [],
        "pick2_golden": None,
        "pick2_hot": None,
        "pick2_pair": [],
        "suppression_top1": None,
        "suppression_top3": [],
        "kill_high": [],
        "kill_avg_high_rate": None,
        "kill_high_n": None,
        # 桥接 / 形态
        "bridge_shortlist": [],
        "bridge_details": {},
        "strategy_flags": {},
        # 结算命中
        "hits": {},
    }


def hit_count(picks: List[int], actual: set) -> int:
    return sum(1 for n in picks if int(n) in actual)


def settle_hits(row: Dict[str, Any], actual_nums: List[int]) -> Dict[str, Any]:
    actual = {int(x) for x in actual_nums}
    tip3 = [int(x) for x in (row.get("a_tip3") or [])]
    top5 = [int(x) for x in (row.get("a_top5") or [])]
    top12 = [int(x) for x in (row.get("a_top12") or [])]
    vip = [int(x) for x in (row.get("b_vip_top5") or [])]
    twin = [int(x) for x in (row.get("b_twin_pair") or [])]
    tri5 = [int(x) for x in (row.get("tri_high_top5") or [])]
    cold = [int(x) for x in (row.get("tri_high_cold") or [])]
    bridge = [int(x) for x in (row.get("bridge_shortlist") or [])]
    kill_high = [int(x) for x in (row.get("kill_high") or [])]
    pair = [int(x) for x in (row.get("pick2_pair") or [])]
    supp1 = row.get("suppression_top1")
    supp3 = [int(x) for x in (row.get("suppression_top3") or [])]

    kill_high_hit = hit_count(kill_high, actual)  # 开出=杀号漏杀
    kill_n = len(kill_high)
    hits = {
        "tip3_hits": hit_count(tip3, actual),
        "tip3_n": len(tip3),
        "top5_hits": hit_count(top5, actual),
        "top5_n": len(top5),
        "top12_hits": hit_count(top12, actual),
        "top12_n": len(top12),
        "vip_hits": hit_count(vip, actual),
        "vip_n": len(vip),
        "twin_hits": hit_count(twin, actual),
        "twin_n": len(twin),
        "twin_double": len(twin) == 2 and hit_count(twin, actual) == 2,
        "tri_top5_hits": hit_count(tri5, actual),
        "tri_cold_hits": hit_count(cold, actual),
        "pick2_hits": hit_count(pair, actual),
        "pick2_both": len(pair) == 2 and hit_count(pair, actual) == 2,
        "suppression_top1_hit": bool(supp1 is not None and int(supp1) in actual),
        "suppression_top3_hits": hit_count(supp3, actual),
        "bridge_hits": hit_count(bridge, actual),
        "bridge_n": len(bridge),
        "kill_high_opened": kill_high_hit,
        "kill_high_n": kill_n,
        "kill_high_miss_rate": round(kill_high_hit / kill_n, 4) if kill_n else None,
        "kill_high_success_rate": round(1.0 - kill_high_hit / kill_n, 4) if kill_n else None,
    }
    row = dict(row)
    row["settled"] = True
    row["settled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row["actual_numbers"] = sorted(actual)
    row["hits"] = hits
    return row
