# -*- coding: utf-8 -*-
"""
重点点位分析 (空间点位打分与精排) - Walk-Forward 滚动复盘与置信评定器
================================================================
严格样本外切片回测 (Walk-Forward Validation, 严禁未来函数泄露)
- Top 10 命中数与 Lift 统计 (随机基线 2.50 码 / 25.0%)
- Core 5 核心五码命中数与 Lift 统计 (随机基线 1.25 码 / 25.0%)
- 一级点位区域命中率与 Lift 统计 (理论基线 58.35%)
- 二项近似显著性 z-score 检验与 3 级置信等级评定
"""
import math
from typing import Dict, List, Any, Tuple, Optional
from core.spatial_points.points_engine import (
    calculate_spatial_point_features,
    get_region_baseline
)
from core.spatial_points.points_ranker import rank_spatial_picks

BASELINE_TOP10 = 0.25   # 10 码基线命中率 25% (期望 2.5 码)
BASELINE_CORE5 = 0.25   # 5 码基线命中率 25% (期望 1.25 码)


def evaluate_confidence_level(avg_hit_rate: float, n_samples: int) -> Dict[str, Any]:
    """
    根据近 N 期 Top10 均命中率与样本量计算二项近似标准误与显著性 Z 评分
    """
    if n_samples <= 0:
        return {
            "level": 3,
            "badge": "🔴 无置信 (Level 3)",
            "description": "🔴 无置信 (Level 3) - 等权降级防守",
            "z_score": 0.0,
            "is_significant": False
        }

    p = BASELINE_TOP10
    # 每期选 10 码，n 期总共 10*n 次 Bernoulli 试验
    se = (p * (1.0 - p) / 10.0) ** 0.5 / (n_samples ** 0.5)
    z = (avg_hit_rate - p) / se if se > 0 else 0.0

    lift = avg_hit_rate / p if p > 0 else 1.0

    if lift >= 1.05 and z >= 1.64:
        level = 1
        badge = "🟢 高置信 (Level 1)"
        desc = f"🟢 高置信 (Level 1) (z={z:.2f}, 显著跑赢大盘)"
    elif lift >= 1.00 and z >= 0.84:
        level = 2
        badge = "🟡 中置信 (Level 2)"
        desc = f"🟡 中置信 (Level 2) (z={z:.2f}, 贴近大盘期望)"
    else:
        level = 3
        badge = "🔴 无置信 (Level 3)"
        desc = f"🔴 无置信 (Level 3) - 等权降级防守 (z={z:.2f})"

    return {
        "level": level,
        "badge": badge,
        "description": desc,
        "z_score": round(z, 2),
        "is_significant": z >= 1.64
    }


def walk_forward_evaluate(
    draws: List[Dict[str, Any]],
    n_periods: int = 30,
    candidate_pools: Optional[Dict[int, List[int]]] = None
) -> Dict[str, Any]:
    """
    执行近 n_periods 期的严格无未来泄露 Walk-Forward 滚动样本外评测

    candidate_pools: {期号: 该期点位列表}。若提供，每期在此候选池内精排（与今日推荐口径一致）；
                     缺失期号回退为全盘 80 号。为 None 时保持全盘 80 号精排。
    """
    m = len(draws)
    lo = max(0, m - n_periods)

    rows = []
    reg_base = get_region_baseline()

    for idx in range(lo, m):
        if idx < 2:
            continue

        # 严格只用 idx 之前的数据生成预测
        pts_data = calculate_spatial_point_features(draws, cutoff_idx=idx)
        pool = None
        if candidate_pools:
            pool = candidate_pools.get(draws[idx]["period"])
        picks = rank_spatial_picks(pts_data, candidate_points=pool)
        
        actual = draws[idx]
        act_nums = actual["nums"]
        
        t10_hits = len(set(picks["ten"]) & act_nums)
        c5_hits = len(set(picks["core5"]) & act_nums)
        reg_hits = sum(1 for r in picks["top_regions"] if set(r) & act_nums)
        
        rows.append({
            "period": actual["period"],
            "date": actual["date"],
            "actual_nums": actual["sorted_nums"],
            "ten": picks["ten"],
            "core5": picks["core5"],
            "ext15": picks["ext15"],
            "ten_hits": t10_hits,
            "core5_hits": c5_hits,
            "region_hits": reg_hits,
            "ten_hit_rate": round(t10_hits / 10.0, 4),
            "core5_hit_rate": round(c5_hits / 5.0, 4),
            "region_hit_rate": round(reg_hits / 10.0, 4),
            "ten_lift": round((t10_hits / 10.0) / BASELINE_TOP10, 2),
            "core5_lift": round((c5_hits / 5.0) / BASELINE_CORE5, 2),
        })

    n_count = len(rows)
    if n_count == 0:
        return {
            "rows": [],
            "n_count": 0,
            "avg_ten_hits": 0.0,
            "avg_core5_hits": 0.0,
            "avg_region_rate": 0.0,
            "oof_lift": 0.0,
            "core5_lift": 0.0,
            "region_lift": 0.0,
            "confidence": evaluate_confidence_level(0.0, 0),
            "baseline_top10": BASELINE_TOP10,
            "baseline_core5": BASELINE_CORE5,
            "baseline_region": round(reg_base, 4),
        }

    avg_t10 = sum(r["ten_hits"] for r in rows) / n_count
    avg_c5 = sum(r["core5_hits"] for r in rows) / n_count
    avg_reg = sum(r["region_hits"] for r in rows) / (n_count * 10.0)

    oof_lift = avg_t10 / 2.50
    core5_lift = avg_c5 / 1.25
    reg_lift = avg_reg / reg_base if reg_base > 0 else 1.0

    conf = evaluate_confidence_level(avg_t10 / 10.0, n_count)

    return {
        "rows": rows,
        "n_count": n_count,
        "avg_ten_hits": round(avg_t10, 2),
        "avg_core5_hits": round(avg_c5, 2),
        "avg_region_rate": round(avg_reg, 4),
        "oof_lift": round(oof_lift, 3),
        "core5_lift": round(core5_lift, 3),
        "region_lift": round(reg_lift, 3),
        "confidence": conf,
        "baseline_top10": BASELINE_TOP10,
        "baseline_core5": BASELINE_CORE5,
        "baseline_region": round(reg_base, 4),
    }
