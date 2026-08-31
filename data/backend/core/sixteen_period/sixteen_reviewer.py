# -*- coding: utf-8 -*-
"""
16期中热号频次决策 Walk-Forward 滚动样本外复盘审计器 (Sixteen-Period Reviewer)
=============================================================================
无任何未来函数泄露：
每期严格仅使用该期之前的 16 期及更早数据进行中热推演，并与实际开奖对账。
统计指标：
- 核心金胆命中率与 Lift 提升倍数
- 次席银胆命中率与 Lift
- 中热 Top 5 均期命中数 (基线 1.25 码)
- 中热 Top 10 均期命中数 (基线 2.50 码)
- Top 1 选2 组合中2率 (全中, 基线 6.01%) 与 至少中1率
- 中热号码池单码命中率 vs 25% 基线
"""
import os
import sys
import math
from typing import Dict, List, Any, Optional

try:
    from backend.utils.paths import get_project_root
    PROJ_DIR = get_project_root()
except Exception:
    curr = os.path.dirname(os.path.abspath(__file__))
    while curr and os.path.dirname(curr) != curr:
        if os.path.exists(os.path.join(curr, "kl8_history_final.txt")) or os.path.exists(os.path.join(curr, "GEMINI.md")):
            break
        curr = os.path.dirname(curr)
    PROJ_DIR = curr

if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

from backend.core.sixteen_period.sixteen_engine import SixteenPeriodEngine, load_draws_from_file, WINDOW_SIZE, BASE_SINGLE, BASE_PAIR


class SixteenPeriodReviewer:
    def __init__(self, draws: Optional[List[Dict[str, Any]]] = None):
        self.draws = draws if draws is not None else load_draws_from_file()
        self.engine = SixteenPeriodEngine(self.draws)

    def run_walk_forward_review(self, n_periods: int = 30) -> Dict[str, Any]:
        total_draws = len(self.draws)
        if total_draws < WINDOW_SIZE + 5:
            raise ValueError(f"历史开奖期数不足 {WINDOW_SIZE + 5} 期")

        n = min(n_periods, total_draws - WINDOW_SIZE)
        start_idx = total_draws - n

        rows = []
        gold_hits = 0
        silver_hits = 0
        top5_hit_total = 0
        top10_hit_total = 0
        top1_both_count = 0
        top1_one_count = 0
        med_pool_hits_total = 0
        med_pool_size_total = 0

        for idx in range(start_idx, total_draws):
            # target_idx = idx - 1 (严格使用上一期之前的数据进行推演)
            pred_idx = idx - 1
            pred_res = self.engine.analyze_at_index(pred_idx)

            actual_draw = self.draws[idx]
            actual_period = actual_draw["period"]
            actual_nums = actual_draw["nums"]
            actual_sorted = actual_draw["sorted_nums"]

            gold = pred_res["gold_dan"]
            silver = pred_res["silver_dan"]
            top5 = pred_res["medium_top5"]
            top10 = pred_res["medium_top10"]
            top1_pair = pred_res["top5_pairs"][0]["pair"] if pred_res["top5_pairs"] else [1, 2]
            top1_str = pred_res["top5_pairs"][0]["pair_str"] if pred_res["top5_pairs"] else "01-02"

            # 命中对账
            gold_hit = (gold in actual_nums)
            silver_hit = (silver in actual_nums)
            top5_hits = sum(1 for x in top5 if x in actual_nums)
            top10_hits = sum(1 for x in top10 if x in actual_nums)

            p1_hit = (top1_pair[0] in actual_nums)
            p2_hit = (top1_pair[1] in actual_nums)
            top1_both = (p1_hit and p2_hit)
            top1_one = (p1_hit or p2_hit)

            # 中热候选池整体命中
            med_cands = [c["number"] for c in pred_res["scored_candidates"]]
            med_hits = sum(1 for x in med_cands if x in actual_nums)

            if gold_hit: gold_hits += 1
            if silver_hit: silver_hits += 1
            top5_hit_total += top5_hits
            top10_hit_total += top10_hits
            if top1_both: top1_both_count += 1
            if top1_one: top1_one_count += 1
            med_pool_hits_total += med_hits
            med_pool_size_total += len(med_cands)

            rows.append({
                "period": actual_period,
                "date": actual_draw["date"],
                "gold": gold,
                "gold_hit": gold_hit,
                "silver": silver,
                "silver_hit": silver_hit,
                "top5": top5,
                "top5_hits": top5_hits,
                "top10": top10,
                "top10_hits": top10_hits,
                "top1_str": top1_str,
                "top1_both": top1_both,
                "top1_one": top1_one,
                "med_pool_hits": med_hits,
                "med_pool_size": len(med_cands),
                "actual_nums": actual_sorted
            })

        # 统计汇总
        gold_hit_rate = round(gold_hits / n * 100, 2)
        gold_lift = round(gold_hit_rate / (BASE_SINGLE * 100), 2)

        silver_hit_rate = round(silver_hits / n * 100, 2)
        silver_lift = round(silver_hit_rate / (BASE_SINGLE * 100), 2)

        top5_avg = round(top5_hit_total / n, 2)
        top5_lift = round(top5_avg / 1.25, 2)

        top10_avg = round(top10_hit_total / n, 2)
        top10_lift = round(top10_avg / 2.50, 2)

        top1_both_rate = round(top1_both_count / n * 100, 2)
        top1_both_lift = round(top1_both_rate / (BASE_PAIR * 100), 2)
        top1_one_rate = round(top1_one_count / n * 100, 2)

        med_pool_avg_rate = round(med_pool_hits_total / max(1, med_pool_size_total) * 100, 2)

        # 最新期在前展示
        rows_desc = list(reversed(rows))

        return {
            "stats": {
                "n_periods": n,
                "gold_hit_count": gold_hits,
                "gold_hit_rate": gold_hit_rate,
                "gold_lift": gold_lift,
                "silver_hit_count": silver_hits,
                "silver_hit_rate": silver_hit_rate,
                "silver_lift": silver_lift,
                "top5_avg_hits": top5_avg,
                "top5_lift": top5_lift,
                "top10_avg_hits": top10_avg,
                "top10_lift": top10_lift,
                "top1_both_count": top1_both_count,
                "top1_both_rate": top1_both_rate,
                "top1_both_lift": top1_both_lift,
                "top1_one_count": top1_one_count,
                "top1_one_rate": top1_one_rate,
                "med_pool_hit_rate": med_pool_avg_rate,
                "base_single_rate": round(BASE_SINGLE * 100, 2),
                "base_pair_rate": round(BASE_PAIR * 100, 2)
            },
            "rows": rows_desc
        }
