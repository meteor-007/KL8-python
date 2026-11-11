# -*- coding: utf-8 -*-
"""JingleServiceMixin: methods extracted from QuantDataService"""
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


class JingleServiceMixin:
    def get_jingle_summary(self) -> Dict[str, Any]:
        """获取顺口溜口诀最新预测、触发明细与交叉风控"""
        try:
            from core.formula_jingle.jingle_engine import load_jingle_rules, predict_jingle
            from core.formula_jingle.jingle_cross_validator import cross_validate_jingle
            
            history = self.load_history(limit=50)
            draws = []
            for h in reversed(history):
                nums = sorted(list(h["numbers"]))
                if len(nums) == 20:
                    draws.append((int(h["period"]), h.get("date", ""), nums))
            rules, meta = load_jingle_rules()
            pred = predict_jingle(draws, rules)
            cross = cross_validate_jingle(pred.get("recommended_numbers", []), target_issue=pred.get("target_issue"))
            pred["cross_validation"] = cross
            pred["meta"] = meta
            rec = pred.get("recommended_numbers", [])
            pred["top3_gold"] = rec[:3]
            return pred
        except Exception as e:
            return {"status": "error", "message": str(e), "recommended_numbers": [], "top3_gold": [], "fired_details": []}

    def get_jingle_review(self, n: int = 30) -> Dict[str, Any]:
        """获取近 N 期顺口溜口诀对账复盘流水与分层指标"""
        try:
            from core.formula_jingle.jingle_engine import load_jingle_rules
            from core.formula_jingle.jingle_reviewer import review_jingle
            
            history = self.load_history(limit=n + 15)
            draws = []
            for h in reversed(history):
                nums = sorted(list(h["numbers"]))
                if len(nums) == 20:
                    draws.append((int(h["period"]), h.get("date", ""), nums))
            rules, meta = load_jingle_rules()
            val_end = int(str(meta.get("val_end_period", "2026210")))
            rev = review_jingle(draws, rules, n=n, sel_cut=val_end)
            return rev
        except Exception as e:
            return {"status": "error", "message": str(e), "pairs": [], "metrics": {}}

    def get_jingle_rules(self, kind: Optional[str] = None, keyword: Optional[str] = None) -> Dict[str, Any]:
        """获取 90 条精英口诀规则清单与元数据"""
        try:
            from core.formula_jingle.jingle_engine import load_jingle_rules
            rules, meta = load_jingle_rules()
            filtered = rules
            if kind:
                filtered = [r for r in filtered if r.get("kind") == kind]
            if keyword:
                kw = str(keyword).strip()
                filtered = [
                    r for r in filtered 
                    if kw in str(r.get("trigger", [])) or kw in str(r.get("predict", [])) or kw in str(r.get("rule_id", ""))
                ]
            return {
                "status": "ok",
                "total_count": len(rules),
                "filtered_count": len(filtered),
                "meta": meta,
                "rules": filtered
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "rules": [], "total_count": 0}

