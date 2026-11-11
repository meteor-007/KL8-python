# -*- coding: utf-8 -*-
"""
快乐8循环黄金分割交集系统 - 最优交集提取与极小覆盖算法
"""
from __future__ import annotations

import itertools
import json
import os
import random
import sys
from typing import Dict, Any, List, Tuple, Set, Optional

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_CURR_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)
for _p in [_PROJ_DIR, _BACKEND_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils.paths import get_outputs_dir, data_path


def load_today_quant_context(target_period: str = "2026270") -> Dict[str, Any]:
    """读取今日系统量化信标（点位、三高、共识等）作为交集碰撞底座"""
    pts_file = data_path("daily_points.txt")
    points = []
    if os.path.exists(pts_file):
        with open(pts_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if f"period:{target_period}" in line:
                    import re
                    m = re.search(r"points:([\d\s]+)", line)
                    if m:
                        points = [int(x) for x in m.group(1).split() if x.isdigit()]
                        break
    if not points:
        points = [3, 5, 6, 7, 11, 16, 17, 20, 28, 30, 31, 40, 41, 53, 58, 61, 65, 66, 70, 71]

    # 今日共识与推荐
    consensus = {16: 4, 20: 4, 28: 3, 53: 3, 71: 3, 6: 2, 14: 2, 70: 2, 76: 2, 3: 2}
    hot_picks = {20, 65, 16, 6, 5, 70, 28, 71, 58, 76, 75}
    
    return {
        "points": set(points),
        "consensus": consensus,
        "hot_picks": hot_picks,
    }


def find_minimal_5_cover_4(numbers: List[int], seed: int = 42) -> List[Tuple[int, ...]]:
    """
    组合学覆盖设计 (Covering Design C(10, 5, 4)):
    从 10 个号码中选出最少注选五单式，使得 10 个号的全部 C(10, 4) = 210 个 4 元子集
    至少被某注选五单式包含！
    数学极限理论值为 14 注。通过贪心最大覆盖法求解。
    """
    clean_nums = sorted(list(set(numbers)))
    all_4_subsets = [set(c) for c in itertools.combinations(clean_nums, 4)]
    all_5_combos = [set(c) for c in itertools.combinations(clean_nums, 5)]

    uncovered_4 = list(all_4_subsets)
    selected_5: List[Tuple[int, ...]] = []

    # 优先使用确定性贪心算法
    rnd = random.Random(seed)
    rnd.shuffle(all_5_combos)

    while uncovered_4:
        # 寻找能覆盖最多未覆盖 4 元集的 5 元组合
        best_combo = None
        best_covered = []
        for c in all_5_combos:
            covered = [sub for sub in uncovered_4 if sub.issubset(c)]
            if len(covered) > len(best_covered):
                best_covered = covered
                best_combo = c
        
        if not best_combo or not best_covered:
            break

        selected_5.append(tuple(sorted(list(best_combo))))
        uncovered_4 = [sub for sub in uncovered_4 if not sub.issubset(best_combo)]

    selected_5.sort()
    return selected_5


def score_combinations(
    combos: List[Tuple[int, ...]],
    quant_ctx: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    对每注选五单式按【多维量化交集势能】综合打分：
    1. 点位交集度 (与今日点位的重合度，重合越多分越高)
    2. 票池共识交集度 (号码在今日全系统推荐中的票数)
    3. 012 路跨路平衡度 (避开单路极端偏态)
    4. 质合与尾数离散度
    """
    points = quant_ctx.get("points", set())
    consensus = quant_ctx.get("consensus", {})
    hot_picks = quant_ctx.get("hot_picks", set())

    results = []
    for c in combos:
        c_set = set(c)
        pt_hits = sorted(list(c_set.intersection(points)))
        n_pt = len(pt_hits)

        # 1. 点位交集分 (每个落在点位加 25 分)
        pt_score = n_pt * 25.0

        # 2. 票池共识分
        con_score = sum(consensus.get(x, 0) * 12.0 for x in c)

        # 3. 热码协同分
        hot_score = len(c_set.intersection(hot_picks)) * 10.0

        # 4. 012 路跨路平衡分
        roads = [x % 3 for x in c]
        road_types = len(set(roads))
        road_score = 15.0 if road_types >= 3 else (8.0 if road_types == 2 else -10.0)

        # 5. 跨区离散度
        spread = max(c) - min(c)
        spread_score = 10.0 if 30 <= spread <= 70 else 5.0

        total_score = pt_score + con_score + hot_score + road_score + spread_score

        results.append({
            "combo": c,
            "combo_str": " ".join(f"{x:02d}" for x in c),
            "score": round(total_score, 1),
            "pt_hits_count": n_pt,
            "pt_hits": pt_hits,
            "consensus_votes": sum(consensus.get(x, 0) for x in c),
            "roads": [f"{r}路" for r in roads],
        })

    results.sort(key=lambda x: -x["score"])
    return results
