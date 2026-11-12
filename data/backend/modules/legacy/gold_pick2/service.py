# -*- coding: utf-8 -*-
"""GoldPick2ServiceMixin: methods extracted from QuantDataService"""
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


class GoldPick2ServiceMixin:
    def get_gold_pick2_summary(self) -> Dict[str, Any]:
        """获取定金选2最新量化研判、加权Z金胆、热号金胆、Top5黄金配对与交叉风控"""
        json_file = os.path.join(get_outputs_dir(), "gold_pick2", "gold_pick2_latest.json")
        if os.path.exists(json_file):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # 实时推演
        try:
            from run_pick2_daily import run_pick2_pipeline
            res = run_pick2_pipeline(n_review=30, verbose=False)
            return res
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_gold_pick2_review(self, n: int = 30) -> Dict[str, Any]:
        """获取近 N 期定金选2 Walk-Forward 样本外对账流水与统计指标"""
        try:
            from core.gold_pick2 import load_draws_from_file, walk_forward_evaluate_pick2
            draws = load_draws_from_file(self.history_file)
            res = walk_forward_evaluate_pick2(draws, n_review=n)
            return res
        except Exception as e:
            return {"status": "error", "message": str(e), "rows": [], "stats": {}}

    def get_gold_pick2_matrix(self) -> Dict[str, Any]:
        """获取定金选2 80 码 7 维特征分布与雷达数据"""
        try:
            from core.gold_pick2 import load_draws_from_file, calculate_gold_pick2_features
            draws = load_draws_from_file(self.history_file)
            data = calculate_gold_pick2_features(draws)
            return {
                "features_80": data.get("features_80", {}),
                "cand_scores": data.get("cand_scores", {}),
                "warm_pool": data.get("warm", []),
                "golden": data.get("golden", 0),
                "hot": data.get("hot", 0)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_gold_pick2_history_list(self) -> List[Dict[str, Any]]:
        """获取定金选2历史每日预测研报列表"""
        out_dir = os.path.join(get_outputs_dir(), "gold_pick2")
        if not os.path.exists(out_dir):
            return []

        results = []
        for f in os.listdir(out_dir):
            if f.startswith("定金选2预测_") and f.endswith(".txt") and not f.endswith("_最新.txt"):
                period_match = re.search(r"定金选2预测_(\d+)", f)
                period = period_match.group(1) if period_match else "N/A"
                fpath = os.path.join(out_dir, f)
                mtime = os.path.getmtime(fpath)
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                results.append({
                    "filename": f,
                    "period": period,
                    "title": f"第 {period} 期 定金选2推演研报",
                    "mtime": mtime_str,
                    "size_bytes": os.path.getsize(fpath)
                })

        results.sort(key=lambda x: int(x["period"]) if x["period"].isdigit() else 0, reverse=True)
        return results

    def get_gold_pick2_history_detail(self, filename: str) -> Dict[str, Any]:
        """读取指定定金选2预测研报内容"""
        clean_name = os.path.basename(filename)
        fpath = os.path.join(get_outputs_dir(), "gold_pick2", clean_name)
        if not os.path.exists(fpath):
            raise FileNotFoundError("未找到指定的定金选2研报文件")

        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return {
            "filename": clean_name,
            "content": content
        }

