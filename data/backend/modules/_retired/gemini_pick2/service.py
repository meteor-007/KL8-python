# -*- coding: utf-8 -*-
"""GeminiServiceMixin: methods extracted from QuantDataService"""
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


class GeminiServiceMixin:
    def get_gemini_summary(self) -> Dict[str, Any]:
        """获取最新一期的 Gemini 选2核心预测(金银铜胆、核心4码、终极5码、铁血做空区、异象雷达)"""
        out_dir = os.path.join(
            self.proj_dir, "backend", "modules", "_retired", "gemini_pick2", "output"
        )
        if os.path.exists(out_dir):
            mem_files = sorted(glob.glob(os.path.join(out_dir, "k8_quant_memory_*.json")), reverse=True)
            if mem_files:
                try:
                    with open(mem_files[0], "r", encoding="utf-8") as jf:
                        d = json.load(jf)
                    return d
                except Exception:
                    pass

        try:
            from gemini_pick2.engine import get_latest_summary
            res = get_latest_summary(self.history_file)
            return res
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_gemini_review(self, n: int = 30) -> Dict[str, Any]:
        """获取近 N 期 Gemini 选2 Walk-Forward 样本外对账流水与统计指标

        2026-10-22 性能缺陷修复 (Bug#13)：本方法每次调用都全量重跑 walk-forward，
        实测 n=100 耗时 8.19s，是 `get_hit_leaderboard`(47.65s) 的第二大热点，
        拖累前端 FDR/天梯榜页面。现加按窗口的磁盘缓存 (同一窗口 + 同一历史最新期
        才命中)，冷启动一次、后续毫秒级返回。
        """
        from backend.utils.paths import get_cache_dir
        _cache_dir = os.path.join(get_cache_dir(), "gemini_review")
        _cache_file = os.path.join(_cache_dir, "review_n%d.json" % int(n))
        try:
            latest = None
            try:
                latest = (self.load_history(limit=1) or [{}])[0].get("period")
            except Exception:
                latest = None
            if os.path.exists(_cache_file):
                with open(_cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if (latest is None
                        or str(cached.get("_latest_period")) == str(latest)):
                    return cached
        except Exception:
            pass

        try:
            from gemini_pick2.engine import get_walk_forward_review
            res = get_walk_forward_review(self.history_file, n_review=n)
            try:
                os.makedirs(_cache_dir, exist_ok=True)
                payload = dict(res)
                try:
                    payload["_latest_period"] = (self.load_history(limit=1) or [{}])[0].get("period")
                except Exception:
                    payload["_latest_period"] = None
                with open(_cache_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, default=str)
            except Exception:
                pass
            return res
        except Exception as e:
            return {"status": "error", "message": str(e), "rows": []}

    def get_gemini_history_list(self) -> List[Dict[str, Any]]:
        """获取 Gemini 选2历史每日预测研报列表"""
        out_dir = os.path.join(
            self.proj_dir, "backend", "modules", "_retired", "gemini_pick2", "output"
        )
        if not os.path.exists(out_dir):
            return []

        results = []
        for f in os.listdir(out_dir):
            if f.startswith("gemini选2预测_") and f.endswith(".txt"):
                period_match = re.search(r"gemini选2预测_(\d+)", f)
                period = period_match.group(1) if period_match else "N/A"
                fpath = os.path.join(out_dir, f)
                mtime = os.path.getmtime(fpath)
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                results.append({
                    "filename": f,
                    "period": period,
                    "title": f"第 {period} 期 Gemini 选2推演研报",
                    "mtime": mtime_str,
                    "size_bytes": os.path.getsize(fpath)
                })

        results.sort(key=lambda x: x["period"], reverse=True)
        return results

    def get_gemini_history_detail(self, filename: str) -> Dict[str, Any]:
        """读取指定 Gemini 选2预测研报内容"""
        clean_name = os.path.basename(filename)
        fpath = os.path.join(
            self.proj_dir, "backend", "modules", "_retired", "gemini_pick2", "output", clean_name
        )
        if not os.path.exists(fpath):
            raise FileNotFoundError("未找到指定的 Gemini 选2研报文件")

        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return {
            "filename": clean_name,
            "content": content
        }

