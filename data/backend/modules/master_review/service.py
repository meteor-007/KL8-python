# -*- coding: utf-8 -*-
"""MasterReviewServiceMixin: methods extracted from QuantDataService"""
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


class MasterReviewServiceMixin:
    def get_daily_reviews_ledger(self, limit: int = 50) -> Dict[str, Any]:
        """获取全量每日自动复盘对账总账本 (47+期 reviews/review_*.json) 与全局统计"""
        reviews_dir = os.path.join(get_reviews_dir())
        if not os.path.exists(reviews_dir):
            return {"status": "ok", "total_count": 0, "records": [], "metrics": {}}
            
        review_files = sorted(glob.glob(os.path.join(reviews_dir, "review_*.json")), reverse=True)
        records = []
        top5_hits_list, top12_hits_list, top20_hits_list = [], [], []
        top5_lifts, top12_lifts = [], []
        ef_pos, rw_pos, fo_pos = 0, 0, 0
        total_valid = 0
        
        for rf in review_files:
            try:
                with open(rf, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                    p = str(data.get("period", ""))
                    hits = data.get("hit_stats", {})
                    algo = data.get("algo_contribution", {})
                    gate = data.get("gate", {})
                    weights = data.get("weights_used", {})
                    
                    t5_hit = hits.get("top5_hits", 0)
                    t12_hit = hits.get("top12_hits", 0)
                    t20_hit = hits.get("top20_hits", 0)
                    t5_lift = hits.get("top5_lift", 0.0)
                    t12_lift = hits.get("top12_lift", 0.0)
                    
                    record = {
                        "period": p,
                        "timestamp": data.get("timestamp", ""),
                        "actual_numbers": data.get("actual_numbers", []),
                        "top5_hits": t5_hit,
                        "top5_rate": hits.get("top5_rate", 0.0),
                        "top5_lift": t5_lift,
                        "top12_hits": t12_hit,
                        "top12_rate": hits.get("top12_rate", 0.0),
                        "top12_lift": t12_lift,
                        "top20_hits": t20_hit,
                        "top20_rate": hits.get("top20_rate", 0.0),
                        "top20_lift": hits.get("top20_lift", 0.0),
                        "algo_contribution": algo,
                        "weights_used": weights,
                        "optimization_decision": data.get("optimization_decision", "N/A"),
                        "learning_status": data.get("learning_status", "N/A"),
                        "gate": gate
                    }
                    records.append(record)
                    
                    if t5_hit is not None:
                        top5_hits_list.append(t5_hit)
                    if t12_hit is not None:
                        top12_hits_list.append(t12_hit)
                    if t20_hit is not None:
                        top20_hits_list.append(t20_hit)
                    if t5_lift is not None and t5_lift > 0:
                        top5_lifts.append(t5_lift)
                    if t12_lift is not None and t12_lift > 0:
                        top12_lifts.append(t12_lift)
                        
                    if algo.get("EF") == "POSITIVE": ef_pos += 1
                    if algo.get("RW") == "POSITIVE": rw_pos += 1
                    if algo.get("FO") == "POSITIVE": fo_pos += 1
                    total_valid += 1
            except Exception:
                continue
                
        # 计算全局均值
        n = max(total_valid, 1)
        avg_top5 = sum(top5_hits_list) / len(top5_hits_list) if top5_hits_list else None
        avg_top12 = sum(top12_hits_list) / len(top12_hits_list) if top12_hits_list else None
        avg_top20 = sum(top20_hits_list) / len(top20_hits_list) if top20_hits_list else None
        avg_t5_lift = sum(top5_lifts) / len(top5_lifts) if top5_lifts else (avg_top5 / 1.25 if avg_top5 is not None else None)
        avg_t12_lift = sum(top12_lifts) / len(top12_lifts) if top12_lifts else (avg_top12 / 3.0 if avg_top12 is not None else None)
        
        latest_record = records[0] if records else {}
        
        return {
            "status": "ok",
            "total_count": len(records),
            "records": records[:limit] if limit > 0 else records,
            "metrics": {
                "total_reviewed_periods": len(records),
                "avg_top5_hits": round(avg_top5, 2) if avg_top5 is not None else None,
                "avg_top5_lift": round(avg_t5_lift, 2) if avg_t5_lift is not None else None,
                "avg_top12_hits": round(avg_top12, 2) if avg_top12 is not None else None,
                "avg_top12_lift": round(avg_t12_lift, 2) if avg_t12_lift is not None else None,
                "avg_top20_hits": round(avg_top20, 2) if avg_top20 is not None else None,
                "ef_positive_rate": round(ef_pos / n * 100, 1),
                "rw_positive_rate": round(rw_pos / n * 100, 1),
                "fo_positive_rate": round(fo_pos / n * 100, 1),
                "latest_period": latest_record.get("period", "N/A"),
                "latest_learning_status": latest_record.get("learning_status"),
                "latest_weights": latest_record.get("weights_used"),
                "latest_top5_hits": latest_record.get("top5_hits", 0),
                "latest_top12_hits": latest_record.get("top12_hits", 0)
            }
        }

    def get_review_detail(self, period: str) -> Dict[str, Any]:
        """获取指定期号的详细复盘 JSON"""
        target = os.path.join(get_reviews_dir(), f"review_{period}.json")
        if not os.path.exists(target):
            raise FileNotFoundError(f"未找到第 {period} 期的复盘记录")
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_master_review_summary(self, n: int = 100) -> Dict[str, Any]:
        """获取全模块命中复盘对账总决算摘要与排行榜 (C2/C3: 默认 100 期, 小样本易被赢家诅咒误导)"""
        ledger_file = os.path.join(self.proj_dir, "storage", "reviews", "master_review_ledger.json")
        if os.path.exists(ledger_file):
            try:
                with open(ledger_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                from backend.utils.history_loader import load_history
                hist = load_history()
                latest_issue = str(hist[0].get("issue") or hist[0].get("period") or "") if hist else ""
                target_p = str(data.get("target_period") or "")
                if target_p == latest_issue and latest_issue:
                    return data
            except Exception:
                pass
        try:
            from backend.core.master_reviewer import MasterReviewEngine
            engine = MasterReviewEngine(self.proj_dir)
            return engine.run_master_review(n_review=n)
        except Exception as e:
            return {"status": "error", "message": str(e), "leaderboard": []}

