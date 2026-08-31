# -*- coding: utf-8 -*-
"""
未开点位高压反弹与空间关联 样本外评估器 (Walk-Forward Evaluator)
================================================================================
严格时序切片无未来函数泄露：
  · 仅利用当期历史前序序列统计弹簧张力与替身矩阵
  · 评估 Top 1 单码命中率、Top 1 三号区命中率、S级共振命中率与 Lift 提升度
"""
import math
from collections import defaultdict
from typing import Dict, List, Any

from .suppression_engine import (
    PointSuppressionAnalyzer,
    get_period_picks,
    region_of,
    SINGLE_BASE,
    REGION_BASE,
    NUM
)


def evaluate_suppression_walk_forward(draws: List[Dict[str, Any]], test_window: int = 30) -> Dict[str, Any]:
    """
    严格 Walk-Forward 滚动时序样本外评估
    """
    total_draws = len(draws)
    start_t = max(60, total_draws - test_window)
    
    analyzer = PointSuppressionAnalyzer(draws)
    patterns = analyzer.analyze_historical_patterns(train_len=start_t)
    
    active_suppression = defaultdict(int)
    
    # 状态预热 (冷启动)
    for t in range(40, start_t):
        hist = draws[:t]
        act = draws[t]["nums"]
        picks = get_period_picks(hist)
        priority_pts = set(picks["top10"]).union(picks["strong"])
        new_supp = defaultdict(int)
        for n in range(1, NUM + 1):
            if n in priority_pts:
                new_supp[n] = (active_suppression[n] + 1) if n not in act else 0
            else:
                new_supp[n] = active_suppression[n] if (active_suppression[n] > 0 and n not in act) else 0
        active_suppression = new_supp
        
    eval_results = {
        "n_periods": 0,
        "top1_single_hit": 0,
        "top1_region_hit": 0,
        "top3_any_single_hit": 0,
        "top3_total_single_hits": 0,
        "s_level_total": 0,
        "s_level_single_hit": 0,
        "s_level_region_hit": 0,
        "period_logs": []
    }
    
    for t in range(start_t, total_draws):
        hist = draws[:t]
        act = draws[t]["nums"]
        period = draws[t]["period"]
        date_str = draws[t].get("date", "")
        
        ranked = analyzer.score_unhit_candidates(hist, active_suppression, patterns)
        
        # 记录本期测试表现
        if ranked:
            top1 = ranked[0]
            top3 = ranked[:3]
            
            t1_n = top1["num"]
            t1_s_hit = (t1_n in act)
            t1_r_hit = bool(region_of(t1_n) & act)
            
            eval_results["n_periods"] += 1
            if t1_s_hit:
                eval_results["top1_single_hit"] += 1
            if t1_r_hit:
                eval_results["top1_region_hit"] += 1
                
            top3_nums = [c["num"] for c in top3]
            t3_hits = len(set(top3_nums) & act)
            eval_results["top3_total_single_hits"] += t3_hits
            if t3_hits > 0:
                eval_results["top3_any_single_hit"] += 1
                
            # S级指标
            for cand in ranked:
                if cand.get("conf_grade") == "S":
                    eval_results["s_level_total"] += 1
                    if cand["num"] in act:
                        eval_results["s_level_single_hit"] += 1
                    if region_of(cand["num"]) & act:
                        eval_results["s_level_region_hit"] += 1

            eval_results["period_logs"].append({
                "period": period,
                "date": date_str,
                "top1_num": t1_n,
                "top1_score": top1["score"],
                "top1_k": top1["k_suppression"],
                "top1_grade": top1["conf_grade"],
                "top1_single_hit": t1_s_hit,
                "top1_region_hit": t1_r_hit,
                "top3_nums": top3_nums,
                "top3_hits": t3_hits,
                "actual_numbers": sorted(list(act))
            })
            
        # 滚动更新 active_suppression
        picks = get_period_picks(hist)
        priority_pts = set(picks["top10"]).union(picks["strong"])
        new_supp = defaultdict(int)
        for n in range(1, NUM + 1):
            if n in priority_pts:
                new_supp[n] = (active_suppression[n] + 1) if n not in act else 0
            else:
                new_supp[n] = active_suppression[n] if (active_suppression[n] > 0 and n not in act) else 0
        active_suppression = new_supp
        
    n = max(eval_results["n_periods"], 1)
    t1_single_rate = eval_results["top1_single_hit"] / n
    t1_reg_rate = eval_results["top1_region_hit"] / n
    t3_hit_rate = eval_results["top3_any_single_hit"] / n
    avg_t3_hits = eval_results["top3_total_single_hits"] / n
    
    t1_single_lift = t1_single_rate / SINGLE_BASE
    t1_reg_lift = t1_reg_rate / REGION_BASE
    
    # 评定置信等级
    se_reg = (REGION_BASE * (1 - REGION_BASE) / n) ** 0.5
    z_reg = (t1_reg_rate - REGION_BASE) / se_reg if se_reg > 0 else 0.0
    
    if t1_reg_lift >= 1.08 and z_reg >= 1.28:
        conf_desc = "🟢 高置信 (Level 1) - 黄金反弹周期"
        conf_code = "LEVEL_1"
    elif t1_reg_lift >= 1.00:
        conf_desc = "🟡 中置信 (Level 2) - 稳健回补区间"
        conf_code = "LEVEL_2"
    else:
        conf_desc = "🔴 弱置信 (Level 3) - 震荡观望区间"
        conf_code = "LEVEL_3"
        
    return {
        "n_periods": eval_results["n_periods"],
        "top1_single_hit": eval_results["top1_single_hit"],
        "top1_single_rate": round(t1_single_rate, 4),
        "top1_single_lift": round(t1_single_lift, 3),
        "top1_region_hit": eval_results["top1_region_hit"],
        "top1_region_rate": round(t1_reg_rate, 4),
        "top1_region_lift": round(t1_reg_lift, 3),
        "top3_any_hit_rate": round(t3_hit_rate, 4),
        "avg_top3_hits": round(avg_t3_hits, 2),
        "s_level_total": eval_results["s_level_total"],
        "s_level_single_hit": eval_results["s_level_single_hit"],
        "s_level_region_hit": eval_results["s_level_region_hit"],
        "z_score": round(z_reg, 2),
        "confidence": {
            "code": conf_code,
            "description": conf_desc,
            "z_score": round(z_reg, 2)
        },
        "period_logs": eval_results["period_logs"]
    }
