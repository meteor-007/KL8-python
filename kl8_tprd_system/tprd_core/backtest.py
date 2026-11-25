#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TPRD v4.0 严格样本外滚动回测与对账引擎 (Walk-Forward Backtester)
绝无前瞻数据污染，输出全盘命中率与相对基准 Lift 倍率
"""

from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np
from .model_v40 import infer_period_v40


def run_walk_forward_backtest(
    draws: List[Dict],
    X: np.ndarray,
    B: np.ndarray,
    road_counts: np.ndarray,
    test_periods: int = 30
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    执行严格 Walk-Forward 滚动外样本回测
    """
    N = len(draws)
    start_t = max(240, N - test_periods)

    records = []
    for t in range(start_t, N):
        actual = draws[t]['set']
        period_id = draws[t]['period']
        draw_date = draws[t]['date']

        pred = infer_period_v40(t, X, B, road_counts)

        p20 = set(pred['pool_20'])
        p25 = set(pred['pool_25'])
        p30 = set(pred['pool_30'])
        t5 = pred['top5_leaders']

        hit_20 = len(actual.intersection(p20))
        hit_25 = len(actual.intersection(p25))
        hit_30 = len(actual.intersection(p30))
        hit_top1 = 1 if t5[0] in actual else 0
        hit_top3 = len(actual.intersection(set(t5[:3])))
        hit_top5 = len(actual.intersection(set(t5)))

        hit_p2_bets = sum(1 for d in pred['pick2_details'] if d['pair'][0] in actual and d['pair'][1] in actual)

        records.append({
            "期号": period_id,
            "开奖日期": draw_date,
            "20码命中": hit_20,
            "25码命中": hit_25,
            "30码命中": hit_30,
            "独胆Top1命中": hit_top1,
            "三胆Top3命中": hit_top3,
            "五码Top5命中": hit_top5,
            "选2网格命中注数": hit_p2_bets,
            "20码和值": sum(pred['pool_20']),
            "开奖号码": " ".join(f"{n:02d}" for n in sorted(list(actual)))
        })

    df = pd.DataFrame(records)

    # 计算均值与 Lift 倍率
    mean_20 = float(df['20码命中'].mean())
    mean_25 = float(df['25码命中'].mean())
    mean_30 = float(df['30码命中'].mean())

    lift_20 = mean_20 / 5.00
    lift_25 = mean_25 / 6.25
    lift_30 = mean_30 / 7.50

    p2_total_bets = len(df) * 4
    p2_hit_bets = int(df['选2网格命中注数'].sum())
    p2_win_rate = p2_hit_bets / max(1, p2_total_bets)

    summary = {
        "test_count": len(df),
        "mean_20": mean_20, "lift_20": lift_20,
        "mean_25": mean_25, "lift_25": lift_25,
        "mean_30": mean_30, "lift_30": lift_30,
        "top1_acc": float(df['独胆Top1命中'].mean()),
        "top3_mean": float(df['三胆Top3命中'].mean()),
        "top5_mean": float(df['五码Top5命中'].mean()),
        "p2_hit_bets": p2_hit_bets,
        "p2_total_bets": p2_total_bets,
        "p2_win_rate": p2_win_rate,
        "p2_lift": p2_win_rate / (190.0 / 3160.0)
    }

    return df, summary
