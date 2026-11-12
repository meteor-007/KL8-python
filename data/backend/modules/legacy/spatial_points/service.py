# -*- coding: utf-8 -*-
"""SpatialPointsServiceMixin: methods extracted from QuantDataService"""
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


class SpatialPointsServiceMixin:
    def get_spatial_points_summary(self) -> Dict[str, Any]:
        """获取空间重点点位最新预测、核心五码、精选十码、8区覆盖与交叉风控"""
        try:
            from core.spatial_points import (
                load_draws_from_file,
                calculate_spatial_point_features,
                rank_spatial_picks,
                walk_forward_evaluate,
                cross_validate_spatial_picks
            )
            from backend.data_acquisition.daily_points_manager import (
                load_daily_points,
                get_latest_points_entry
            )
            draws = load_draws_from_file(self.history_file)
            if not draws:
                return {"status": "error", "message": "无法加载开奖历史"}

            m = len(draws)
            latest_draw = draws[-1]
            target_period = latest_draw["period"] + 1

            # 今日 20 点位作精排候选池，历史点位供 Walk-Forward 口径对齐
            all_pts = load_daily_points(self.points_file)
            today_pool = None
            if all_pts:
                target_entry = all_pts.get(str(target_period))
                if target_entry:
                    today_pool = target_entry["points"]
                else:
                    latest_entry = get_latest_points_entry(self.points_file)
                    today_pool = latest_entry["points"] if latest_entry else None
            pools = {int(k): v["points"] for k, v in all_pts.items()}

            pts_data = calculate_spatial_point_features(draws, cutoff_idx=m)
            picks = rank_spatial_picks(pts_data, candidate_points=today_pool)
            wf_eval = walk_forward_evaluate(draws, n_periods=30, candidate_pools=pools)
            cross_res = cross_validate_spatial_picks(self.proj_dir, picks)

            return {
                "status": "ok",
                "latest_period": latest_draw["period"],
                "latest_date": latest_draw["date"],
                "target_period": target_period,
                "confidence": wf_eval["confidence"],
                "oof_lift": wf_eval["oof_lift"],
                "core5_lift": wf_eval["core5_lift"],
                "region_lift": wf_eval["region_lift"],
                "picks": picks,
                "cross_validation": cross_res,
                "wf_summary": {
                    "avg_ten_hits": wf_eval["avg_ten_hits"],
                    "avg_core5_hits": wf_eval["avg_core5_hits"],
                    "avg_region_rate": wf_eval["avg_region_rate"],
                    "n_count": wf_eval["n_count"]
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_spatial_points_matrix(self) -> Dict[str, Any]:
        """获取 80 点位全盘空间特征、得分、p值显著性与 4 维雷达数据"""
        try:
            from core.spatial_points import (
                load_draws_from_file,
                calculate_spatial_point_features,
                rank_spatial_picks
            )
            from backend.data_acquisition.daily_points_manager import (
                load_daily_points,
                get_latest_points_entry
            )
            draws = load_draws_from_file(self.history_file)
            if not draws:
                return {"status": "error", "message": "无法加载开奖历史", "matrix": []}

            m = len(draws)
            target_period = draws[-1]["period"] + 1

            # 与今日推荐口径一致：tier 标注基于今日 20 点位候选池
            all_pts = load_daily_points(self.points_file)
            today_pool = None
            if all_pts:
                target_entry = all_pts.get(str(target_period))
                if target_entry:
                    today_pool = target_entry["points"]
                else:
                    latest_entry = get_latest_points_entry(self.points_file)
                    today_pool = latest_entry["points"] if latest_entry else None

            pts_data = calculate_spatial_point_features(draws, cutoff_idx=m)
            picks = rank_spatial_picks(pts_data, candidate_points=today_pool)

            matrix_list = []
            for n in range(1, 81):
                p_item = pts_data[n]
                is_core5 = n in picks["core5"]
                is_ten = n in picks["ten"]
                is_ext15 = n in picks["ext15"]
                matrix_list.append({
                    "ball": n,
                    "score": p_item["score"],
                    "p_value": p_item["p_value"],
                    "is_significant": p_item["is_significant"],
                    "region": p_item["region"],
                    "raw_z": p_item["raw_z"],
                    "features": p_item["features"],
                    "tier": "Core5" if is_core5 else ("Top10" if is_ten else ("Ext15" if is_ext15 else "Normal"))
                })

            return {
                "status": "ok",
                "total_balls": 80,
                "latest_period": draws[-1]["period"],
                "target_period": draws[-1]["period"] + 1,
                "matrix": matrix_list,
                "ranked_top10": picks["top10_points"]
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "matrix": []}

    def get_spatial_points_review(self, n: int = 30) -> Dict[str, Any]:
        """获取近 N 期重点点位 Walk-Forward 滚动样本外复盘对账流水"""
        try:
            from core.spatial_points import (
                load_draws_from_file,
                walk_forward_evaluate
            )
            from backend.data_acquisition.daily_points_manager import load_daily_points
            draws = load_draws_from_file(self.history_file)
            if not draws:
                return {"status": "error", "message": "无法加载开奖历史", "rows": []}

            all_pts = load_daily_points(self.points_file)
            pools = {int(k): v["points"] for k, v in all_pts.items()}

            res = walk_forward_evaluate(draws, n_periods=n, candidate_pools=pools)
            res["status"] = "ok"
            return res
        except Exception as e:
            return {"status": "error", "message": str(e), "rows": []}

