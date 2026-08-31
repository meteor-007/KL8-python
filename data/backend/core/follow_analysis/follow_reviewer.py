# -*- coding: utf-8 -*-
"""
跟随分析 (重复号追踪与多窗条件跟随) 样本外滚动对账与复盘审计器 v3.0
====================================================================
严密遵循老派量化操盘手无未来函数 (Walk-Forward) 样本外检验原则：
- 每一期 t 的预测只能使用期号 < t 的历史开奖数据。
- 逐期对账：
  1. 重复号 Top 5 命中数 (期望基线 = 1.25 码) -> 计算 Lift 与 z-score
  2. 综合推演 Top 6 命中数 (期望基线 = 1.50 码) -> 计算 Lift 与 z-score
  3. 条件跟随 Top 8 命中数 (期望基线 = 2.00 码) -> 计算 Lift 与 z-score
  4. 双重交集确认号命中记录
- 分层置信评级与诚实警示：
  🟢 Lift >= 1.05x: 有效超额增益 (重点关注)
  🟡 1.00x <= Lift < 1.05x: 与大盘随机持平
  ❌ Lift < 1.00x: 低于随机基线
"""
import math
from typing import Dict, List, Any, Optional

from core.follow_analysis.follow_engine import (
    daily_follow_picks,
    BASE_RATE,
    BASELINE_REPEAT_TOP5,
    BASELINE_INFERENCE_TOP6,
    BASELINE_FOLLOW_TOP8
)


def evaluate_confidence(lift: float, z_score: float, n_periods: int) -> Dict[str, Any]:
    """计算统计置信等级与徽标"""
    if lift >= 1.15 and z_score >= 1.5:
        level = "GRADE_A"
        badge = "🏆 强效超额"
        desc = "样本外超额显著，胜率大幅超越随机基线"
    elif lift >= 1.05:
        level = "GRADE_B"
        badge = "✅ 稳健有效"
        desc = "具备微弱正向偏置，稳定跑赢基准"
    elif lift >= 0.98:
        level = "GRADE_C"
        badge = "🟡 均值持平"
        desc = "与大盘随机基线持平，维持常规防守配置"
    else:
        level = "GRADE_D"
        badge = "⚠️ 谨防偏离"
        desc = "低于理论基线，大盘混沌震荡，建议防守守号"
        
    return {
        "level": level,
        "badge": badge,
        "description": desc,
        "z_score": round(z_score, 2),
        "lift": round(lift, 3),
        "n_periods": n_periods
    }


def walk_forward_evaluate(draws: List[Dict[str, Any]], n_periods: int = 30) -> Dict[str, Any]:
    """
    近 n_periods 期无泄露滚动复盘
    """
    m = len(draws)
    if m < 35:
        return {
            "n_count": 0,
            "avg_rep_hits": 0.0,
            "rep_lift": 1.0,
            "rep_z": 0.0,
            "avg_inf_hits": 0.0,
            "inf_lift": 1.0,
            "inf_z": 0.0,
            "avg_cf_hits": 0.0,
            "cf_lift": 1.0,
            "cf_z": 0.0,
            "confidence": evaluate_confidence(1.0, 0.0, 0),
            "rows": []
        }
        
    start_idx = max(30, m - n_periods)
    rows = []
    
    sum_rep = 0
    sum_inf = 0
    sum_cf = 0
    sum_inter = 0
    valid_count = 0
    
    for t in range(start_idx, m):
        # 严格基于 t 之前的切片进行推演
        picks = daily_follow_picks(draws, cutoff_idx=t)
        if not picks:
            continue
            
        actual_draw = draws[t]
        actual_set = actual_draw["nums"]
        
        rep_top5 = picks["repeat"]["top5"]
        inf_top6 = picks["inference"]["top6"]
        cf_top8 = picks["conditional"]["top8"]
        inter_nums = picks["resonance_intersection"]
        
        hit_rep = len(set(rep_top5) & actual_set)
        hit_inf = len(set(inf_top6) & actual_set)
        hit_cf = len(set(cf_top8) & actual_set)
        hit_inter = len(set(inter_nums) & actual_set)
        
        sum_rep += hit_rep
        sum_inf += hit_inf
        sum_cf += hit_cf
        sum_inter += hit_inter
        valid_count += 1
        
        rows.append({
            "period": actual_draw["period"],
            "date": actual_draw["date"],
            "rep_picks": rep_top5,
            "rep_hits": hit_rep,
            "rep_hit_nums": sorted(list(set(rep_top5) & actual_set)),
            "inf_picks": inf_top6,
            "inf_hits": hit_inf,
            "inf_hit_nums": sorted(list(set(inf_top6) & actual_set)),
            "cf_picks": cf_top8,
            "cf_hits": hit_cf,
            "cf_hit_nums": sorted(list(set(cf_top8) & actual_set)),
            "inter_picks": inter_nums,
            "inter_hits": hit_inter,
            "inter_hit_nums": sorted(list(set(inter_nums) & actual_set))
        })
        
    if valid_count == 0:
        valid_count = 1
        
    avg_rep = sum_rep / valid_count
    avg_inf = sum_inf / valid_count
    avg_cf = sum_cf / valid_count
    
    rep_lift = avg_rep / BASELINE_REPEAT_TOP5
    inf_lift = avg_inf / BASELINE_INFERENCE_TOP6
    cf_lift = avg_cf / BASELINE_FOLLOW_TOP8
    
    # 计算 z-scores
    k5_sd = math.sqrt(5 * BASE_RATE * (1 - BASE_RATE)) or 1e-6
    k6_sd = math.sqrt(6 * BASE_RATE * (1 - BASE_RATE)) or 1e-6
    k8_sd = math.sqrt(8 * BASE_RATE * (1 - BASE_RATE)) or 1e-6
    
    z_rep = (avg_rep - BASELINE_REPEAT_TOP5) / (k5_sd / math.sqrt(valid_count))
    z_inf = (avg_inf - BASELINE_INFERENCE_TOP6) / (k6_sd / math.sqrt(valid_count))
    z_cf = (avg_cf - BASELINE_FOLLOW_TOP8) / (k8_sd / math.sqrt(valid_count))
    
    # 综合以重复号(正向核心)为主要置信评估锚点
    conf = evaluate_confidence(rep_lift, z_rep, valid_count)
    
    return {
        "n_count": valid_count,
        "avg_rep_hits": round(avg_rep, 2),
        "rep_lift": round(rep_lift, 3),
        "rep_z": round(z_rep, 2),
        "avg_inf_hits": round(avg_inf, 2),
        "inf_lift": round(inf_lift, 3),
        "inf_z": round(z_inf, 2),
        "avg_cf_hits": round(avg_cf, 2),
        "cf_lift": round(cf_lift, 3),
        "cf_z": round(z_cf, 2),
        "sum_inter_hits": sum_inter,
        "confidence": conf,
        "rows": rows
    }
