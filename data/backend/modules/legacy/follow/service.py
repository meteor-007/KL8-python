# -*- coding: utf-8 -*-
"""FollowServiceMixin: methods extracted from QuantDataService"""
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


class FollowServiceMixin:
    def get_follow_summary(self) -> Dict[str, Any]:
        """获取跟随分析最新推演决策包、三路选号、交集确认与跨系统风控打标"""
        cache_f = os.path.join(get_outputs_dir(), "follow_analysis", "follow_latest.json")
        if os.path.exists(cache_f):
            try:
                with open(cache_f, "r", encoding="utf-8") as jf:
                    d = json.load(jf)
                wf = d.get("walk_forward", {})
                return {
                    "status": "ok",
                    "latest_period": d.get("latest_period"),
                    "latest_date": d.get("latest_date"),
                    "target_period": d.get("target_period"),
                    "confidence": d.get("confidence"),
                    "rep_lift": wf.get("rep_lift"),
                    "inf_lift": wf.get("inf_lift"),
                    "cf_lift": wf.get("cf_lift"),
                    "picks": d.get("picks", {}),
                    "walk_forward_summary": wf,
                    "cross_validation": d.get("cross_validation", {})
                }
            except Exception:
                pass

        try:
            from core.follow_analysis import (
                load_draws_from_history,
                daily_follow_picks,
                walk_forward_evaluate,
                cross_validate_follow_picks
            )
            draws = load_draws_from_history(self.history_file)
            if not draws:
                return {"status": "error", "message": "无法加载开奖历史"}
            
            picks = daily_follow_picks(draws)
            if not picks:
                return {"status": "error", "message": "跟随分析推演未返回有效结果"}
            
            wf_eval = walk_forward_evaluate(draws, n_periods=30)
            cross_res = cross_validate_follow_picks(self.proj_dir, picks)
            
            return {
                "status": "ok",
                "latest_period": picks["latest_period"],
                "latest_date": picks["latest_date"],
                "target_period": picks["target_period"],
                "confidence": wf_eval["confidence"],
                "rep_lift": wf_eval["rep_lift"],
                "inf_lift": wf_eval["inf_lift"],
                "cf_lift": wf_eval["cf_lift"],
                "picks": picks,
                "walk_forward_summary": {
                    "avg_rep_hits": wf_eval["avg_rep_hits"],
                    "avg_inf_hits": wf_eval["avg_inf_hits"],
                    "avg_cf_hits": wf_eval["avg_cf_hits"],
                    "n_count": wf_eval["n_count"]
                },
                "cross_validation": cross_res
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_follow_review(self, n: int = 30) -> Dict[str, Any]:
        """获取近 N 期跟随分析 Walk-Forward 滚动无未来函数样本外对账流水

        2026-10-22 性能缺陷修复 (Bug#14)：本方法每次调用都重新加载全量开奖历史并
        全量重跑 walk-forward，实测 n=100 耗时 7.24s，是 `get_hit_leaderboard`
        的第三大热点。现加按窗口的磁盘缓存 (同窗口 + 同历史最新期才命中)。
        """
        from backend.utils.paths import get_cache_dir
        _cache_dir = os.path.join(get_cache_dir(), "follow_review")
        _cache_file = os.path.join(_cache_dir, "review_n%d.json" % int(n))
        _latest = None
        try:
            _h = self.load_history(limit=1)
            _latest = _h[0].get("period") if _h else None
        except Exception:
            _latest = None
        try:
            if os.path.exists(_cache_file):
                with open(_cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if _latest is None or str(cached.get("_latest_period")) == str(_latest):
                    return cached
        except Exception:
            pass

        try:
            from core.follow_analysis import (
                load_draws_from_history,
                walk_forward_evaluate
            )
            draws = load_draws_from_history(self.history_file)
            if not draws:
                return {"status": "error", "message": "无法加载开奖历史", "rows": []}

            res = walk_forward_evaluate(draws, n_periods=n)
            res["status"] = "ok"
            try:
                os.makedirs(_cache_dir, exist_ok=True)
                payload = dict(res)
                payload["_latest_period"] = _latest
                with open(_cache_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, default=str)
            except Exception:
                pass
            return res
        except Exception as e:
            return {"status": "error", "message": str(e), "rows": []}

    def get_follow_conditions(self) -> Dict[str, Any]:
        """获取最新上期 Top 5 黄金条件对、多时间窗口跟随明细与 >= 3 窗交集"""
        try:
            from core.follow_analysis import (
                load_draws_from_history,
                conditional_follow
            )
            draws = load_draws_from_history(self.history_file)
            if not draws:
                return {"status": "error", "message": "无法加载开奖历史", "cond_info": []}
            
            cf = conditional_follow(draws)
            return {
                "status": "ok",
                "latest_period": draws[-1]["period"],
                "target_period": draws[-1]["period"] + 1,
                "top8": cf["top8"],
                "top8_str": cf["top8_str"],
                "cross_scores": cf["cross_scores"],
                "cond_info": cf["cond_info"]
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "cond_info": []}

