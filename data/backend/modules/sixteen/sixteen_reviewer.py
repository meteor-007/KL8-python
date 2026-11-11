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
- 跃迁梯队 Top5 / 破冰 / 黄金冲刺 / 跨梯队选2（与全景页红框同口径）
"""
import os
import sys
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

from .sixteen_engine import SixteenPeriodEngine, load_draws_from_file, WINDOW_SIZE, BASE_SINGLE, BASE_PAIR


class SixteenPeriodReviewer:
    def __init__(self, draws: Optional[List[Dict[str, Any]]] = None):
        self.draws = draws if draws is not None else load_draws_from_file()
        self.engine = SixteenPeriodEngine(self.draws)

    def run_walk_forward_review(self, n_periods: int = 30) -> Dict[str, Any]:
        """
        严格屏蔽未来数据：
        对目标期 draws[idx]，仅调用 analyze_at_index(idx-1)，
        窗口止于上一期开奖，绝不读入目标期及之后数据。
        """
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
        ops5_hit_total = 0
        ops12_hit_total = 0
        tip3_hit_total = 0
        tip3_v3_hit_total = 0
        ops5_v3_hit_total = 0
        tip3_v3_eval = 0
        ops5_v3_eval = 0
        top1_both_count = 0
        top1_one_count = 0
        top1_pair_missing = 0
        med_pool_hits_total = 0
        med_pool_size_total = 0

        trans_top5_hit_total = 0
        trans_pair_eval = 0
        trans_pair_both_count = 0
        trans_pair_one_count = 0
        ice_hit_total = 0
        ice_pick_total = 0
        gold_rush_hit_total = 0
        gold_rush_pick_total = 0
        edge4_hit_total = 0
        edge4_pick_total = 0
        edge4_conc_hit_total = 0
        edge4_conc_pick_total = 0
        edge4_conc_periods = 0
        mid4_hit_total = 0
        mid4_pick_total = 0

        for idx in range(start_idx, total_draws):
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
            brief = pred_res.get("daily_ops_brief") or {}
            ops5 = brief.get("top5") or pred_res.get("ops_top5") or top5
            ops12 = brief.get("top12") or pred_res.get("ops_top12") or top10
            tip3 = brief.get("tip3") or ops5[:3]
            ops_gold = (brief.get("rebound") or {}).get("gold") or gold
            v3 = ((brief.get("scoring_contrast") or {}).get("raw_v3_contrast") or {})
            tip3_v3 = v3.get("tip3") or []
            top5_v3 = v3.get("top5") or []
            board = pred_res.get("bucket_dimension_board") or brief.get("bucket_dimension_board") or {}
            fa = board.get("forward_audit") or {}
            edge4_nums = fa.get("edge_nums") or (board.get("freq4_edge_cohort") or {}).get("nums") or []
            mid4_nums = fa.get("midhot_picks") or (board.get("freq4_edge_cohort") or {}).get("midhot_picks") or []
            edge4_hits = int(fa.get("edge_hit_n") if fa.get("edge_hit_n") is not None else sum(1 for x in edge4_nums if x in actual_nums))
            mid4_hits = int(fa.get("midhot_hit_n") if fa.get("midhot_hit_n") is not None else sum(1 for x in mid4_nums if x in actual_nums))
            edge4_n = len(edge4_nums)
            mid4_n = len(mid4_nums)
            top1_pair = pred_res["top5_pairs"][0]["pair"] if pred_res["top5_pairs"] else []
            top1_str = pred_res["top5_pairs"][0]["pair_str"] if pred_res["top5_pairs"] else "数据缺失"
            pair_available = len(top1_pair) == 2

            gold_hit = (gold in actual_nums)
            silver_hit = (silver in actual_nums)
            top5_hits = sum(1 for x in top5 if x in actual_nums)
            top10_hits = sum(1 for x in top10 if x in actual_nums)
            ops5_hits = sum(1 for x in ops5 if x in actual_nums)
            ops12_hits = sum(1 for x in ops12 if x in actual_nums)
            tip3_hits = sum(1 for x in tip3 if x in actual_nums)
            ops_gold_hit = (ops_gold in actual_nums)
            if tip3_v3:
                tip3_v3_hit_total += sum(1 for x in tip3_v3 if x in actual_nums)
                tip3_v3_eval += 1
            if top5_v3:
                ops5_v3_hit_total += sum(1 for x in top5_v3 if x in actual_nums)
                ops5_v3_eval += 1

            if pair_available:
                p1_hit = (top1_pair[0] in actual_nums)
                p2_hit = (top1_pair[1] in actual_nums)
                top1_both = (p1_hit and p2_hit)
                top1_one = (p1_hit or p2_hit)
            else:
                top1_both = False
                top1_one = False
                top1_pair_missing += 1

            med_cands = [c["number"] for c in pred_res["scored_candidates"]]
            med_hits = sum(1 for x in med_cands if x in actual_nums)

            if gold_hit:
                gold_hits += 1
            if silver_hit:
                silver_hits += 1
            top5_hit_total += top5_hits
            top10_hit_total += top10_hits
            ops5_hit_total += ops5_hits
            ops12_hit_total += ops12_hits
            tip3_hit_total += tip3_hits
            edge4_hit_total += edge4_hits
            edge4_pick_total += edge4_n
            mid4_hit_total += mid4_hits
            mid4_pick_total += mid4_n
            if edge4_n >= 5:
                edge4_conc_periods += 1
                edge4_conc_hit_total += edge4_hits
                edge4_conc_pick_total += edge4_n
            if top1_both:
                top1_both_count += 1
            if top1_one:
                top1_one_count += 1
            med_pool_hits_total += med_hits
            med_pool_size_total += len(med_cands)

            ta = pred_res.get("transition_analysis") or {}
            ladders = ta.get("ladders") or {}
            trans_top5 = ta.get("transition_top5_picks") or top5
            ice_picks = (ladders.get("ladder_ice_break") or {}).get("top_picks") or []
            gold_rush_picks = (ladders.get("ladder_gold_rush") or {}).get("top_picks") or []
            trans_pairs = ta.get("transition_pairs") or []
            trans_pair = (trans_pairs[0].get("pair") if trans_pairs else []) or []
            trans_pair_str = (trans_pairs[0].get("pair_str") if trans_pairs else "") or "—"
            trans_pair_ok = len(trans_pair) == 2
            if trans_pair_ok:
                tp_both = (trans_pair[0] in actual_nums and trans_pair[1] in actual_nums)
                tp_one = (trans_pair[0] in actual_nums or trans_pair[1] in actual_nums)
                trans_pair_eval += 1
                if tp_both:
                    trans_pair_both_count += 1
                if tp_one:
                    trans_pair_one_count += 1
            else:
                tp_both = False
                tp_one = False

            trans_top5_hits = sum(1 for x in trans_top5 if x in actual_nums)
            ice_hits = sum(1 for x in ice_picks if x in actual_nums)
            gold_rush_hits = sum(1 for x in gold_rush_picks if x in actual_nums)
            trans_top5_hit_total += trans_top5_hits
            ice_hit_total += ice_hits
            ice_pick_total += len(ice_picks)
            gold_rush_hit_total += gold_rush_hits
            gold_rush_pick_total += len(gold_rush_picks)

            rows.append({
                "period": actual_period,
                "target_period": actual_period,
                "anchor_period": pred_res.get("latest_period"),
                "date": actual_draw["date"],
                "gold": gold,
                "gold_hit": gold_hit,
                "silver": silver,
                "silver_hit": silver_hit,
                "top5": top5,
                "top5_hits": top5_hits,
                "ops_top5": ops5,
                "ops_top5_hits": ops5_hits,
                "ops_top12": ops12,
                "ops_top12_hits": ops12_hits,
                "ops_tip3": tip3,
                "ops_tip3_hits": tip3_hits,
                "ops_gold": ops_gold,
                "ops_gold_hit": ops_gold_hit,
                "top10": top10,
                "top10_hits": top10_hits,
                "top1_str": top1_str,
                "top1_both": top1_both,
                "top1_one": top1_one,
                "transition_top5": trans_top5,
                "transition_top5_hits": trans_top5_hits,
                "ice_picks": ice_picks,
                "ice_hits": ice_hits,
                "gold_rush_picks": gold_rush_picks,
                "gold_rush_hits": gold_rush_hits,
                "transition_pair_str": trans_pair_str,
                "transition_pair": trans_pair,
                "transition_pair_both": tp_both,
                "transition_pair_one": tp_one,
                "med_pool_hits": med_hits,
                "med_pool_size": len(med_cands),
                "freq4_edge_nums": edge4_nums,
                "freq4_edge_hits": edge4_hits,
                "freq4_edge_n": edge4_n,
                "freq4_midhot_nums": mid4_nums,
                "freq4_midhot_hits": mid4_hits,
                "freq4_midhot_n": mid4_n,
                "actual_nums": actual_sorted,
                "no_lookahead": True,
            })

        gold_hit_rate = round(gold_hits / n * 100, 2)
        gold_lift = round(gold_hit_rate / (BASE_SINGLE * 100), 2)

        silver_hit_rate = round(silver_hits / n * 100, 2)
        silver_lift = round(silver_hit_rate / (BASE_SINGLE * 100), 2)

        top5_avg = round(top5_hit_total / n, 2)
        top5_lift = round(top5_avg / 1.25, 2)

        top10_avg = round(top10_hit_total / n, 2)
        top10_lift = round(top10_avg / 2.50, 2)

        top1_eval = n - top1_pair_missing
        top1_both_rate = round(top1_both_count / top1_eval * 100, 2) if top1_eval else None
        top1_both_lift = (round(top1_both_rate / (BASE_PAIR * 100), 2)
                          if top1_both_rate is not None else None)
        top1_one_rate = round(top1_one_count / top1_eval * 100, 2) if top1_eval else None

        med_pool_avg_rate = round(med_pool_hits_total / max(1, med_pool_size_total) * 100, 2)

        trans_top5_avg = round(trans_top5_hit_total / n, 2)
        trans_top5_lift = round(trans_top5_avg / 1.25, 2)
        trans_pair_both_rate = (
            round(trans_pair_both_count / trans_pair_eval * 100, 2) if trans_pair_eval else None
        )
        trans_pair_both_lift = (
            round(trans_pair_both_rate / (BASE_PAIR * 100), 2)
            if trans_pair_both_rate is not None else None
        )
        trans_pair_one_rate = (
            round(trans_pair_one_count / trans_pair_eval * 100, 2) if trans_pair_eval else None
        )
        ice_rate = round(ice_hit_total / max(1, ice_pick_total) * 100, 2) if ice_pick_total else None
        gold_rush_rate = (
            round(gold_rush_hit_total / max(1, gold_rush_pick_total) * 100, 2)
            if gold_rush_pick_total else None
        )

        rows_desc = list(reversed(rows))

        return {
            "no_lookahead": True,
            "latest_period": int(self.draws[-1]["period"]) if self.draws else None,
            "evidence_note": (
                "Walk-Forward：目标期 T 仅使用截止 T-1 的 16 期滑动窗推演梯队/选2/操盘简报，"
                "再与 T 真实开奖对账；绝不读取 T 及之后数据。"
                "操盘轨 ops_pts_v4：×1.15仅频3~5∩点位且非刚开；tip3优先点位∩精选；"
                "Kill达标仅边缘缩水。附带 raw_v3_contrast 便于消融对照。"
                "频4双轨：出窗同源 vs 动量精选（同源作结构旁证，count≥5 才激活）。"
            ),
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
                "ops_top5_avg_hits": round(ops5_hit_total / n, 2),
                "ops_top5_lift": round((ops5_hit_total / n) / 1.25, 2),
                "ops_top12_avg_hits": round(ops12_hit_total / n, 2),
                "ops_top12_lift": round((ops12_hit_total / n) / 3.0, 2),
                "ops_tip3_avg_hits": round(tip3_hit_total / n, 2),
                "ops_tip3_lift": round((tip3_hit_total / n) / 0.75, 2),
                "ops_pts_v3_contrast": {
                    "tip3_avg_hits": round(tip3_v3_hit_total / tip3_v3_eval, 2) if tip3_v3_eval else None,
                    "top5_avg_hits": round(ops5_v3_hit_total / ops5_v3_eval, 2) if ops5_v3_eval else None,
                    "n": tip3_v3_eval,
                    "note": "近窗 v3 vs v4 tip3/top5 均命中对照（来自 scoring_contrast.raw_v3_contrast）",
                },
                "freq4_edge_avg_hits": round(edge4_hit_total / n, 2),
                "freq4_edge_hit_rate": round(edge4_hit_total / max(1, edge4_pick_total) * 100, 2),
                "freq4_midhot_avg_hits": round(mid4_hit_total / n, 2),
                "freq4_midhot_hit_rate": round(mid4_hit_total / max(1, mid4_pick_total) * 100, 2),
                "freq4_edge_conc_periods": edge4_conc_periods,
                "freq4_edge_conc_avg_hits": (
                    round(edge4_conc_hit_total / edge4_conc_periods, 2) if edge4_conc_periods else None
                ),
                "freq4_edge_conc_hit_rate": (
                    round(edge4_conc_hit_total / max(1, edge4_conc_pick_total) * 100, 2)
                    if edge4_conc_periods else None
                ),
                "top10_avg_hits": top10_avg,
                "top10_lift": top10_lift,
                "top1_both_count": top1_both_count,
                "top1_both_rate": top1_both_rate,
                "top1_both_lift": top1_both_lift,
                "top1_one_count": top1_one_count,
                "top1_one_rate": top1_one_rate,
                "top1_pair_eval_periods": top1_eval,
                "top1_pair_missing_periods": top1_pair_missing,
                "med_pool_hit_rate": med_pool_avg_rate,
                "transition_top5_avg_hits": trans_top5_avg,
                "transition_top5_lift": trans_top5_lift,
                "transition_pair_both_rate": trans_pair_both_rate,
                "transition_pair_both_lift": trans_pair_both_lift,
                "transition_pair_one_rate": trans_pair_one_rate,
                "transition_pair_eval_periods": trans_pair_eval,
                "ice_pick_hit_rate": ice_rate,
                "gold_rush_pick_hit_rate": gold_rush_rate,
                "base_single_rate": round(BASE_SINGLE * 100, 2),
                "base_pair_rate": round(BASE_PAIR * 100, 2),
            },
            "rows": rows_desc,
        }
