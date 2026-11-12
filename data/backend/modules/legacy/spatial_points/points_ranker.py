# -*- coding: utf-8 -*-
"""
重点点位分析 (空间点位打分与精排) - 一级区域筛选与二级非线性精排器
================================================================
一级筛选：对全盘 80 点位按加权分数降序排序，锁定 Top 10 重点点位及其 3 号环绕区域
二级精排：在强势点位区域内部，按遗漏深度做非线性回补增强精排，去重提取：
  - 核心五码 (Core 5): 精排前 5 码（核心金胆梯队）
  - 精选十码 (Top 10): 精选主推 10 码（主力进攻梯队）
  - 扩展十五 (Ext 15): 扩展防守 15 码（大盘覆盖梯队）
8 分区空间均衡性检测（识别 01-10 至 71-80 各分区的覆盖与空缺）
"""
import math
from typing import Dict, List, Any, Tuple, Optional
from core.spatial_points.points_engine import sigmoid, NUM_BALLS


ZONES = [
    ("01-10", 1, 10),
    ("11-20", 11, 20),
    ("21-30", 21, 30),
    ("31-40", 31, 40),
    ("41-50", 41, 50),
    ("51-60", 51, 60),
    ("61-70", 61, 70),
    ("71-80", 71, 80),
]


def rank_spatial_picks(
    points_data: Dict[int, Dict[str, Any]],
    candidate_points: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    基于 80 点位空间特征执行一级区域筛选与二级非线性精排

    candidate_points: 若传入（如今日 20 个点位），则只在此候选集内打分排序，
                     产出的 core5/ten/ext15 均是该候选集的子集；为 None 时保持全盘 80 号精排。
    """
    if candidate_points is not None:
        cand_set = set(candidate_points)
        # 只对候选集内的点位排序
        order = sorted(cand_set, key=lambda n: -points_data[n]["score"])
    else:
        cand_set = None
        order = sorted(points_data.keys(), key=lambda n: -points_data[n]["score"])

    top10_points = order[:10]
    top_regions = [points_data[n]["region"] for n in top10_points]

    # 二级精排: 依序从点位区域取遗漏最大的号码, 结合点位分数与非线性回补增强, 去重集满 15 码
    # 若限定候选集，则只在候选集内挑选，避免选出候选池之外的号码
    best_scores = {}
    for n in order:
        region = points_data[n]["region"]
        if cand_set is not None:
            region_members = [m for m in region if m in cand_set] or [n]
        else:
            region_members = region
        # 在该区域内按遗漏深度降序选最优候选号码
        cand = sorted(region_members, key=lambda m: -points_data[m]["features"]["gap"])
        c = cand[0]
        gap_c = points_data[c]["features"]["gap"]
        # 非线性回补增强公式
        enhanced_score = points_data[n]["score"] * (1.0 + 0.5 * sigmoid(gap_c / 8.0))
        best_scores[c] = max(best_scores.get(c, 0.0), enhanced_score)
        if len(best_scores) >= 15:
            break

    ranked = sorted(best_scores.keys(), key=lambda m: -best_scores[m])
    
    # 兜底确保有 15 码
    if len(ranked) < 15:
        for n in order:
            if n not in ranked:
                ranked.append(n)
            if len(ranked) >= 15:
                break

    ten = ranked[:10]
    core5 = ten[:5]
    ext15 = ranked[:15]

    # 8 分区覆盖检测
    zone_stats = []
    missing_zones = []
    for zone_name, z_start, z_end in ZONES:
        zone_ten_hits = [m for m in ten if z_start <= m <= z_end]
        zone_all_hits = [m for m in ext15 if z_start <= m <= z_end]
        hit_count = len(zone_ten_hits)
        zone_stats.append({
            "zone": zone_name,
            "range": [z_start, z_end],
            "ten_count": hit_count,
            "ten_nums": zone_ten_hits,
            "ext_count": len(zone_all_hits),
            "is_covered": hit_count > 0
        })
        if hit_count == 0:
            missing_zones.append(zone_name)

    # Top10 点位详情
    top10_details = []
    for n in top10_points:
        p_info = points_data[n]
        top10_details.append({
            "point": n,
            "region": p_info["region"],
            "score": p_info["score"],
            "p_value": p_info["p_value"],
            "is_significant": p_info["is_significant"],
            "features": p_info["features"]
        })

    return {
        "order": order,
        "top10_points": top10_points,
        "top_regions": top_regions,
        "top10_details": top10_details,
        "core5": core5,
        "ten": ten,
        "ext15": ext15,
        "core5_str": "-".join(f"{x:02d}" for x in core5),
        "ten_str": "-".join(f"{x:02d}" for x in ten),
        "ext15_str": "-".join(f"{x:02d}" for x in ext15),
        "zone_stats": zone_stats,
        "missing_zones": missing_zones,
        "is_zone_balanced": len(missing_zones) == 0
    }
