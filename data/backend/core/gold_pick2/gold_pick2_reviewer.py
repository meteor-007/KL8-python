# -*- coding: utf-8 -*-
"""
定金选2 快乐8 滚动样本外复盘与置信评估引擎 (Walk-Forward Auditor)
=============================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 样本外滚动复盘 (Walk-Forward OOF)：只使用各期历史真实截断数据，逐期推演预测并与真实开奖对账，杜绝任何未来函数泄露。
2. 科学统计评估：
   - 金胆单码命中率 vs 理论随机基线 (25.0%) -> 计算 Lift 提升倍数与 Z 统计量
   - 热号金胆命中率 vs 理论随机基线 (25.0%)
   - Top 1 黄金配对组合 "中2" 命中率 vs 理论随机基线 (6.01%) -> 计算组合 Lift
   - Top 1 组合 "至少中1" 命中率
   - 温号池 (遗漏4-8期) 单码平均命中率
3. 三级置信定级：
   - 🟢 高置信 (Level 1): Lift >= 1.20 且 Z >= 1.64
   - 🟡 中置信 (Level 2): Lift >= 1.00 且 Z >= 0.84
   - 🔴 无置信/观望 (Level 3): 未达到基线要求
"""
import os
import sys
import math
from typing import Dict, List, Any, Optional, Tuple

from core.gold_pick2.gold_pick2_engine import (
    calculate_gold_pick2_features,
    BASE_SINGLE,
    BASE_PAIR
)


def compute_confidence(gold_rate: float, n_samples: int) -> Dict[str, Any]:
    """计算金胆统计置信评级与 Z-Score"""
    p = BASE_SINGLE
    if n_samples <= 0:
        return {
            "level": 3,
            "badge": "🔴 Level 3",
            "title": "无置信 (观望)",
            "z_score": 0.0,
            "lift": 0.0,
            "description": "🔴 无置信 (Level 3) - 观望 (样本不足)"
        }

    se = (p * (1 - p) / n_samples) ** 0.5
    z = (gold_rate - p) / se if se > 0 else 0.0
    lift = gold_rate / p if p > 0 else 0.0

    if lift >= 1.20 and z >= 1.64:
        level = 1
        badge = "🟢 Level 1"
        title = "高置信 (黄金胜率)"
        desc = f"🟢 高置信 (Level 1) (Lift={lift:.2f}x, z={z:.2f})"
    elif lift >= 1.00 and z >= 0.84:
        level = 2
        badge = "🟡 Level 2"
        title = "中置信 (中性信号)"
        desc = f"🟡 中置信 (Level 2) (Lift={lift:.2f}x, z={z:.2f})"
    else:
        level = 3
        badge = "🔴 Level 3"
        title = "无置信 (谨慎观望)"
        desc = f"🔴 无置信 (Level 3) - 观望 (Lift={lift:.2f}x, z={z:.2f})"

    return {
        "level": level,
        "badge": badge,
        "title": title,
        "z_score": round(z, 2),
        "lift": round(lift, 2),
        "description": desc
    }


def walk_forward_evaluate_pick2(draws: List[Dict[str, Any]], n_review: int = 30) -> Dict[str, Any]:
    """
    进行近 N 期样本外滚动推演与实盘对账流水生成
    """
    m = len(draws)
    if m < 30:
        return {
            "error": "历史数据不足 30 期，无法进行 Walk-Forward 复盘",
            "rows": [],
            "stats": {}
        }

    start_idx = max(30, m - n_review)
    rows = []
    
    g_hits = 0
    h_hits = 0
    t1_both_hits = 0
    t1_one_hits = 0
    warm_hits_total = 0
    warm_count_total = 0
    total_eval = 0

    for t in range(start_idx, m):
        # 严格用 t 之前的数据做预测
        pred = calculate_gold_pick2_features(draws, cutoff_idx=t)
        if not pred:
            continue

        actual_draw = draws[t]
        actual_nums = actual_draw["nums"]
        period = actual_draw["period"]
        date_str = actual_draw["date"]

        golden = pred["golden"]
        hot = pred["hot"]
        top_pairs = pred["top5_golden"]
        top1 = top_pairs[0]["pair"] if top_pairs else None
        warm = pred["warm"]

        g_hit = golden in actual_nums
        h_hit = hot in actual_nums

        top1_both = bool(top1 and set(top1).issubset(actual_nums))
        top1_one = bool(top1 and bool(set(top1) & actual_nums))

        warm_hit_cnt = len([x for x in warm if x in actual_nums])
        warm_total_cnt = len(warm)

        if g_hit:
            g_hits += 1
        if h_hit:
            h_hits += 1
        if top1_both:
            t1_both_hits += 1
        if top1_one:
            t1_one_hits += 1

        warm_hits_total += warm_hit_cnt
        warm_count_total += warm_total_cnt
        total_eval += 1

        rows.append({
            "period": period,
            "date": date_str,
            "golden": golden,
            "hot": hot,
            "golden_hit": g_hit,
            "hot_hit": h_hit,
            "top1_pair": top1,
            "top1_str": f"{top1[0]:02d}-{top1[1]:02d}" if top1 else "--",
            "top1_both": top1_both,
            "top1_one": top1_one,
            "warm_hits": warm_hit_cnt,
            "warm_total": warm_total_cnt,
            "actual_nums": actual_draw.get("sorted_nums", sorted(list(actual_nums)))
        })

    # 统计指标
    g_rate = g_hits / total_eval if total_eval > 0 else 0.0
    h_rate = h_hits / total_eval if total_eval > 0 else 0.0
    t1_both_rate = t1_both_hits / total_eval if total_eval > 0 else 0.0
    t1_one_rate = t1_one_hits / total_eval if total_eval > 0 else 0.0
    warm_rate = warm_hits_total / warm_count_total if warm_count_total > 0 else 0.0

    conf = compute_confidence(g_rate, total_eval)

    stats = {
        "n_periods": total_eval,
        "golden_hit_count": g_hits,
        "golden_hit_rate": round(g_rate * 100, 2),
        "golden_lift": round(g_rate / BASE_SINGLE, 2) if BASE_SINGLE > 0 else 1.0,
        "hot_hit_count": h_hits,
        "hot_hit_rate": round(h_rate * 100, 2),
        "hot_lift": round(h_rate / BASE_SINGLE, 2) if BASE_SINGLE > 0 else 1.0,
        "top1_both_count": t1_both_hits,
        "top1_both_rate": round(t1_both_rate * 100, 2),
        "top1_both_lift": round(t1_both_rate / BASE_PAIR, 2) if BASE_PAIR > 0 else 1.0,
        "top1_one_count": t1_one_hits,
        "top1_one_rate": round(t1_one_rate * 100, 2),
        "warm_pool_hit_rate": round(warm_rate * 100, 2),
        "confidence": conf
    }

    return {
        "rows": list(reversed(rows)),
        "stats": stats
    }
