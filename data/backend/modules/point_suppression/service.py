# -*- coding: utf-8 -*-
"""SuppressionServiceMixin: methods extracted from QuantDataService"""
from __future__ import annotations

import os
import sys
import re
import json
import glob
import math
import logging
import collections
from datetime import datetime
from typing import Dict, List, Any, Optional

from backend.utils.paths import (
    get_cache_dir, get_outputs_dir, get_reports_dir, get_reviews_dir,
    get_project_root, data_path, get_storage_dir, _ensure_project_path,
)

logger = logging.getLogger("k8quant.service")


class SuppressionServiceMixin:
    def get_suppression_summary(self) -> Dict[str, Any]:
        """获取未开点位高压反弹最新推演决策包、Top3金胆、弹簧压制状态与跨系统交叉风控打标"""
        try:
            from core.point_suppression import (
                PointSuppressionAnalyzer,
                load_draws_from_file,
                get_active_suppression_state,
                evaluate_suppression_walk_forward,
                cross_validate_suppression_picks
            )
            draws = load_draws_from_file(self.history_file)
            if not draws:
                return {"status": "error", "message": "无法加载开奖历史"}
            
            m = len(draws)
            latest_draw = draws[-1]
            target_period = latest_draw["period"] + 1

            analyzer = PointSuppressionAnalyzer(draws)
            patterns = analyzer.analyze_historical_patterns(train_len=m)
            active_supp = get_active_suppression_state(draws, cutoff_idx=m)
            candidates = analyzer.score_unhit_candidates(draws, active_supp, patterns)
            wf_eval = evaluate_suppression_walk_forward(draws, test_window=30)
            cross_res = cross_validate_suppression_picks(self.proj_dir, candidates)

            top3 = candidates[:3]
            top1 = candidates[0] if candidates else None
            top3_gold = [c["num"] for c in top3]

            return {
                "status": "ok",
                "latest_period": latest_draw["period"],
                "latest_date": latest_draw["date"],
                "target_period": target_period,
                "confidence": wf_eval["confidence"],
                "top1": top1,
                "top3": top3,
                "top3_gold": top3_gold,
                "candidates": candidates[:10],
                "total_candidates": len(candidates),
                "wf_summary": {
                    "top1_single_rate": wf_eval["top1_single_rate"],
                    "top1_single_lift": wf_eval["top1_single_lift"],
                    "top1_region_rate": wf_eval["top1_region_rate"],
                    "top1_region_lift": wf_eval["top1_region_lift"],
                    "avg_top3_hits": wf_eval["avg_top3_hits"],
                    "n_periods": wf_eval["n_periods"],
                    "z_score": wf_eval["z_score"]
                },
                "cross_validation": cross_res
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_suppression_review(self, n: int = 30) -> Dict[str, Any]:
        """获取近 N 期未开点位反弹 Walk-Forward 滚动无未来函数样本外对账流水"""
        try:
            from core.point_suppression import (
                load_draws_from_file,
                evaluate_suppression_walk_forward
            )
            draws = load_draws_from_file(self.history_file)
            if not draws:
                return {"status": "error", "message": "无法加载开奖历史", "period_logs": []}
            
            res = evaluate_suppression_walk_forward(draws, test_window=n)
            res["status"] = "ok"
            return res
        except Exception as e:
            return {"status": "error", "message": str(e), "period_logs": []}

    def get_suppression_patterns(self) -> Dict[str, Any]:
        """获取未开点位历史模式：弹簧张力回补率、能量外溢漂移率与影子替身伴生矩阵"""
        try:
            from core.point_suppression import (
                PointSuppressionAnalyzer,
                load_draws_from_file,
                get_active_suppression_state
            )
            draws = load_draws_from_file(self.history_file)
            if not draws:
                return {"status": "error", "message": "无法加载开奖历史"}
            
            m = len(draws)
            analyzer = PointSuppressionAnalyzer(draws)
            patterns = analyzer.analyze_historical_patterns(train_len=m)
            active_supp = get_active_suppression_state(draws, cutoff_idx=m)

            # 整理当前激活落空号码的替身清单
            active_supp_items = []
            for n, k in active_supp.items():
                if k > 0:
                    surr_list = patterns["surrogate_map"].get(n, [])
                    active_supp_items.append({
                        "num": n,
                        "k_suppression": k,
                        "surrogates": [{"surrogate_num": s[0], "prob": round(s[1], 3), "lift": round(s[2], 2), "cnt": s[3]} for s in surr_list]
                    })
            active_supp_items.sort(key=lambda x: -x["k_suppression"])

            return {
                "status": "ok",
                "latest_period": draws[-1]["period"],
                "target_period": draws[-1]["period"] + 1,
                "spring_stats": patterns["spring_stats"],
                "spill_stats": patterns["spill_stats"],
                "active_supp_count": len(active_supp_items),
                "active_supp_items": active_supp_items
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

