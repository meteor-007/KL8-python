# -*- coding: utf-8 -*-
"""A/B 桥接短名单 + 形态策略旗标。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


def _as_ints(vals) -> List[int]:
    out: List[int] = []
    for x in vals or []:
        try:
            out.append(int(x))
        except Exception:
            pass
    return out


def build_bridge_shortlist(
    *,
    ops_pool: List[int],
    vip_top5: List[int],
    rebound: Dict[str, Any],
    cold_high: List[int],
    homology4: List[int],
    midhot_picks4: List[int],
    max_n: int = 6,
) -> Dict[str, Any]:
    ops = set(_as_ints(ops_pool))
    vip = set(_as_ints(vip_top5))
    cold = set(_as_ints(cold_high))
    edge = set(_as_ints(homology4))
    picks4 = set(_as_ints(midhot_picks4))

    rb_nums = []
    for k in ("gold", "silver", "bronze"):
        v = (rebound or {}).get(k)
        if v is not None:
            try:
                rb_nums.append(int(v))
            except Exception:
                pass
    rb = set(rb_nums)

    inter_ops_vip = sorted(ops & vip)
    inter_rb_cold = sorted(rb & cold)
    inter_edge_pick = sorted(edge & picks4)

    ordered: List[int] = []
    details = {
        "ops_x_vip": inter_ops_vip,
        "rebound_x_cold_high": inter_rb_cold,
        "homology4_x_pick4": inter_edge_pick,
    }
    for group in (inter_ops_vip, inter_rb_cold, inter_edge_pick):
        for n in group:
            if n not in ordered:
                ordered.append(n)
            if len(ordered) >= max_n:
                break
        if len(ordered) >= max_n:
            break

    return {
        "bridge_shortlist": ordered[:max_n],
        "bridge_details": details,
    }


def build_strategy_flags(
    *,
    tail0_count: Optional[int],
    freq3_count: Optional[int],
    freq3_streak_high: Optional[int],
    homology_count: Optional[int],
    road_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    t0 = int(tail0_count) if tail0_count is not None else None
    f3 = int(freq3_count) if freq3_count is not None else None
    streak = int(freq3_streak_high or 0)
    h_n = int(homology_count) if homology_count is not None else None

    tail0_extinct = t0 == 0
    freq3_extreme = bool((f3 is not None and f3 >= 20) or streak >= 2)
    homology_ge5 = bool(h_n is not None and h_n >= 5)

    road = road_counts or {}
    r0 = int(road.get("r0") or road.get("0") or 0)
    r1 = int(road.get("r1") or road.get("1") or 0)
    r2 = int(road.get("r2") or road.get("2") or 0)
    road_extreme = any(x <= 4 or x >= 10 for x in (r0, r1, r2) if x)

    heavy_triggers = [k for k, v in {
        "tail0_extinct": tail0_extinct,
        "freq3_extreme": freq3_extreme,
        "homology_ge5": homology_ge5,
    }.items() if v]

    if heavy_triggers:
        stance = "heavy"
    elif road_extreme:
        stance = "normal"
    else:
        stance = "normal"

    return {
        "tail0_extinct": tail0_extinct,
        "freq3_extreme": freq3_extreme,
        "homology_ge5": homology_ge5,
        "homology_evidence_active": homology_ge5,
        "road_extreme": road_extreme,
        "tactical_boost_allowed": road_extreme,
        "stance": stance,
        "heavy_triggers": heavy_triggers,
        "note": (
            "加重仓触发: " + ",".join(heavy_triggers)
            if heavy_triggers
            else "常态仓：只出分桶/轻仓对照，勿满仓追涨"
        ),
    }
