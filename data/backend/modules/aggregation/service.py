# -*- coding: utf-8 -*-
"""AggregationServiceMixin: methods extracted from QuantDataService"""
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


class AggregationServiceMixin:
    def get_aggregation_cockpit(self) -> Dict[str, Any]:
        """获取终审共识与数据汇总复盘驾驶舱数据"""
        out_dir = os.path.join(get_outputs_dir(), "aggregation")
        if os.path.exists(out_dir):
            agg_files = sorted(glob.glob(os.path.join(out_dir, "aggregation_*.json")), reverse=True)
            if agg_files:
                try:
                    with open(agg_files[0], "r", encoding="utf-8") as jf:
                        return json.load(jf)
                except Exception:
                    pass

        try:
            from backend.core.aggregation.consensus_engine import ConsensusEngine
            engine = ConsensusEngine(self.proj_dir)
            return engine.run_aggregation(n_review=30)
        except Exception as e:
            return {"status": "error", "message": f"终审汇总引擎计算失败: {e}"}

    def get_aggregation_history_list(self) -> List[Dict[str, Any]]:
        """获取历史汇总复盘战报列表"""
        out_dir = os.path.join(get_outputs_dir(), "aggregation")
        if not os.path.exists(out_dir):
            return []

        results = []
        for f in os.listdir(out_dir):
            if f.startswith("汇总复盘_") and f.endswith(".txt"):
                period_match = re.search(r"汇总复盘_(\d+)", f)
                period = period_match.group(1) if period_match else "N/A"
                fpath = os.path.join(out_dir, f)
                mtime = os.path.getmtime(fpath)
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                results.append({
                    "filename": f,
                    "period": period,
                    "title": f"第 {period} 期 终审数据汇总复盘战报",
                    "mtime": mtime_str,
                    "size_bytes": os.path.getsize(fpath)
                })

        results.sort(key=lambda x: int(x["period"]) if x["period"].isdigit() else 0, reverse=True)
        return results

    def get_aggregation_history_detail(self, filename: str) -> Dict[str, Any]:
        """读取指定汇总复盘报告内容"""
        clean_name = os.path.basename(filename)
        fpath = os.path.join(get_outputs_dir(), "aggregation", clean_name)
        if not os.path.exists(fpath):
            raise FileNotFoundError("未找到指定的汇总复盘战报文件")

        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return {
            "filename": clean_name,
            "content": content
        }

