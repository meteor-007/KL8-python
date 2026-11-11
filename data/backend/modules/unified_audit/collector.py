# -*- coding: utf-8 -*-
"""从现有产物采集统一对账快照（不重算引擎）。"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from backend.modules.unified_audit.bridges import build_bridge_shortlist, build_strategy_flags
from backend.modules.unified_audit.schema import empty_row
from backend.utils.paths import get_project_root


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _ints(vals) -> List[int]:
    out: List[int] = []
    for x in vals or []:
        try:
            out.append(int(x))
        except Exception:
            pass
    return out


def _kill_avg_high_rate(proj_dir: str) -> Dict[str, Any]:
    """KillSeeker 已下架：跳过杀号文件采集，恒返回空指标。"""
    _ = proj_dir
    return {"avg_high_rate": None, "n": None}


def collect_snapshot(proj_dir: Optional[str] = None, target_period: Optional[int] = None) -> Dict[str, Any]:
    root = proj_dir or get_project_root()
    sixteen = _load_json(os.path.join(root, "storage", "cache", "sixteen_period", "latest_summary.json")) or {}
    brief = sixteen.get("daily_ops_brief") or {}
    board = brief.get("bucket_dimension_board") or sixteen.get("bucket_dimension_board") or {}
    if not board and isinstance(sixteen.get("daily_ops_brief"), dict):
        board = (sixteen.get("daily_ops_brief") or {}).get("bucket_dimension_board") or {}
    # board often nested inside brief from engine attach
    if not board:
        board = {}

    prime = _load_json(os.path.join(root, "storage", "stats", "prime_tail_entropy_analysis.json")) or {}
    tri = _load_json(os.path.join(root, "storage", "points", "tri_high_analysis.json")) or {}
    pick2 = _load_json(os.path.join(root, "storage", "outputs", "gold_pick2", "gold_pick2_latest.json")) or {}
    supp = _load_json(os.path.join(root, "storage", "outputs", "point_suppression", "suppression_latest.json")) or {}
    tri_points = _load_json(os.path.join(root, "storage", "points", "tri_high_points.json")) or {}

    tp = int(target_period or brief.get("target_period") or sixteen.get("target_period") or 0)
    based = int(brief.get("latest_period") or sixteen.get("latest_period") or prime.get("based_on_period") or 0)
    row = empty_row(tp, based)

    tip3 = _ints(brief.get("tip3") or sixteen.get("ops_tip3"))
    top5 = _ints(brief.get("top5") or sixteen.get("ops_top5"))
    top12 = _ints(brief.get("top12") or sixteen.get("ops_top12"))
    rebound = brief.get("rebound") or {}
    edge = board.get("freq4_edge_cohort") or {}
    homology4 = _ints(edge.get("nums"))
    midhot_picks4 = _ints(edge.get("midhot_picks"))

    row["a_tip3"] = tip3
    row["a_top5"] = top5
    row["a_top12"] = top12
    row["a_rebound"] = {
        "gold": rebound.get("gold"),
        "silver": rebound.get("silver"),
        "bronze": rebound.get("bronze"),
    }
    row["a_homology4"] = homology4
    row["a_scoring_version"] = brief.get("scoring_version") or sixteen.get("scoring_version")

    pa = prime.get("prime_attendance_analysis") or {}
    twin_block = prime.get("twin_prime_radar_analysis") or {}
    twins = twin_block.get("recommended_twins") or []
    twin_pair = []
    if twins:
        twin_pair = _ints((twins[0] or {}).get("pair") or [])
    road = prime.get("road_012_analysis") or {}
    row["b_vip_top5"] = _ints(pa.get("top5_prime_recommend"))
    row["b_twin_pair"] = twin_pair
    row["b_road_ratio"] = road.get("current_ratio")

    rec = tri.get("recommendations") or {}
    row["tri_high_gold"] = rec.get("resonance_gold_single")
    row["tri_high_pair"] = _ints(rec.get("gold_pair"))
    row["tri_high_top5"] = _ints(rec.get("top5"))
    row["tri_high_cold"] = _ints(rec.get("cold_strikes"))

    # 录入层冷高（用于桥接）
    cold_high_input: List[int] = []
    records = tri_points.get("records") or []
    for r in records:
        if str(r.get("period")) == str(tp):
            cold_high_input = _ints(r.get("cold_high"))
            break
    if not cold_high_input:
        cold_high_input = _ints(rec.get("cold_strikes"))

    row["pick2_golden"] = pick2.get("golden")
    row["pick2_hot"] = pick2.get("hot")
    g0 = pick2.get("golden")
    h0 = pick2.get("hot")
    pair = []
    if g0 is not None and h0 is not None:
        pair = sorted([int(g0), int(h0)])
    else:
        topg = pick2.get("top5_golden") or []
        if topg and isinstance(topg[0], dict):
            pair = _ints((topg[0] or {}).get("pair"))
    row["pick2_pair"] = pair

    top1 = supp.get("top1") or {}
    row["suppression_top1"] = top1.get("num") if isinstance(top1, dict) else top1
    row["suppression_top3"] = [
        int(x.get("num")) for x in (supp.get("top3_candidates") or [])
        if isinstance(x, dict) and x.get("num") is not None
    ]

    row["kill_high"] = []
    kr = _kill_avg_high_rate(root)
    row["kill_avg_high_rate"] = kr.get("avg_high_rate")
    row["kill_high_n"] = kr.get("n")

    ops_pool = list(dict.fromkeys(top12 + tip3 + top5))
    bridges = build_bridge_shortlist(
        ops_pool=ops_pool,
        vip_top5=row["b_vip_top5"],
        rebound=row["a_rebound"],
        cold_high=cold_high_input,
        homology4=homology4,
        midhot_picks4=midhot_picks4,
    )
    # midhot picks4 fallback from edge payload already used
    if not midhot_picks4:
        bridges = build_bridge_shortlist(
            ops_pool=ops_pool,
            vip_top5=row["b_vip_top5"],
            rebound=row["a_rebound"],
            cold_high=cold_high_input,
            homology4=homology4,
            midhot_picks4=[],
        )
    row["bridge_shortlist"] = bridges["bridge_shortlist"]
    row["bridge_details"] = bridges["bridge_details"]

    # 形态：尾0 / 频3 / 同源
    tail0_count = None
    te = prime.get("tail_entropy_analysis") or {}
    for t in te.get("tail_details") or []:
        if int(t.get("tail") or -1) == 0:
            tail0_count = int(t.get("current_count") or 0)
            break
    freq3 = (board.get("freq3") or {}) if board else {}
    # board may be attached on sixteen root after analyze
    if not freq3:
        # try nested from summary keys
        pass
    # Also try reading from brief if engine put board there later
    bd = sixteen.get("bucket_dimension_board") or board
    freq3 = (bd.get("freq3") or {}) if isinstance(bd, dict) else {}
    edge2 = (bd.get("freq4_edge_cohort") or edge) if isinstance(bd, dict) else edge

    row["strategy_flags"] = build_strategy_flags(
        tail0_count=tail0_count,
        freq3_count=freq3.get("count"),
        freq3_streak_high=freq3.get("streak_high"),
        homology_count=len(_ints(edge2.get("nums"))) if isinstance(edge2, dict) else len(homology4),
        road_counts={
            "r0": int(road.get("count_r0") or 0),
            "r1": int(road.get("count_r1") or 0),
            "r2": int(road.get("count_r2") or 0),
        },
    )
    # 同源展示门控字段
    row["strategy_flags"]["homology_count"] = len(homology4)
    row["meta"] = {
        "sixteen_path": "storage/cache/sixteen_period/latest_summary.json",
        "prime_path": "storage/stats/prime_tail_entropy_analysis.json",
    }
    # prefer brief bridges if engine already computed
    if brief.get("bridge_shortlist"):
        row["bridge_shortlist"] = _ints(brief.get("bridge_shortlist"))
        row["bridge_details"] = brief.get("bridge_details") or row["bridge_details"]
    if brief.get("strategy_flags"):
        # merge engine flags over collector
        merged = dict(row["strategy_flags"])
        merged.update(brief.get("strategy_flags") or {})
        row["strategy_flags"] = merged
    return row
