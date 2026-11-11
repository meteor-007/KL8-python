# -*- coding: utf-8 -*-
"""PointOmissionServiceMixin: methods extracted from QuantDataService"""
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


class PointOmissionServiceMixin:
    def get_point_omission_summary(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取点位+遗漏号深度推演最新数据概要
        包含最优 3 码核心推荐、防御性两码、13大子算法权重、8大场域能量分布与80码细分维度分
        """
        summary_file = os.path.join(self.proj_dir, "storage", "point_omission", "latest_summary.json")
        try:
            if not force_refresh and os.path.exists(summary_file):
                with open(summary_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        t3 = data.get("top3_gold") or data.get("top5_picks") or data.get("top5") or []
                        data["top3_gold"] = [p.get("ball") if isinstance(p, dict) else (p.get("number") if isinstance(p, dict) else int(p)) for p in t3[:3]]
                    return {"status": "ok", "data": data}

            # 若未缓存或强制刷新，动态执行一次轻量分析
            from backend.modules._retired.point_omission.run_daily import run_point_omission_pipeline
            res = run_point_omission_pipeline(allow_fetch=False, do_backtest=False, verbose=False)
            if isinstance(res, dict):
                t3 = res.get("top3_gold") or res.get("top5_picks") or res.get("top5") or []
                res["top3_gold"] = [p.get("ball") if isinstance(p, dict) else (p.get("number") if isinstance(p, dict) else int(p)) for p in t3[:3]]
            return {"status": "ok", "data": res}
        except Exception as e:
            logger.error(f"获取点位+遗漏概要失败: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"获取点位+遗漏分析数据失败: {str(e)}"
            }

    def get_point_omission_report(self) -> Dict[str, Any]:
        """
        获取点位+遗漏号深度分析最新 Markdown 格式研报全文
        """
        po_out = os.path.join(get_outputs_dir(), "point_omission")
        candidate_paths = [
            os.path.join(get_outputs_dir(), "reports", "point_omission_report_latest.md"),
            os.path.join(po_out, "daily_report.md"),
        ]
        # 按日期目录：storage/outputs/point_omission/<date>/daily_report.md
        out_pattern = os.path.join(po_out, "*", "daily_report.md")
        found = glob.glob(out_pattern)
        if found:
            found.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            candidate_paths.insert(0, found[0])
        # 兼容旧根目录 output/（若尚未清干净）
        legacy_pattern = os.path.join(self.proj_dir, "output", "*", "daily_report.md")
        legacy = glob.glob(legacy_pattern)
        if legacy:
            legacy.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            candidate_paths.append(legacy[0])

        for path in candidate_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    return {
                        "status": "ok",
                        "content": content,
                        "path": path,
                        "filename": os.path.basename(path)
                    }
                except Exception as e:
                    logger.error(f"读取点位+遗漏研报失败 ({path}): {e}")

        return {
            "status": "error",
            "message": "尚未生成点位+遗漏号分析研报，请先点击「一键量化推演」",
            "content": ""
        }

    def get_point_omission_backtest(self) -> Dict[str, Any]:
        """
        获取点位+遗漏号深度分析系统的滚动外样本回测台账 (T=277 全样本实战对账)
        """
        bt_file = os.path.join(self.proj_dir, "storage", "point_omission", "backtest_latest.json")
        if os.path.exists(bt_file):
            try:
                with open(bt_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {"status": "ok", "backtest": data}
            except Exception as e:
                logger.error(f"读取点位+遗漏回测数据失败: {e}")
                return {"status": "error", "message": str(e)}

        return {
            "status": "error",
            "message": "暂无外样本回测台账数据"
        }

    def get_point_omission_hit_ledger(self, n: int = 40) -> Dict[str, Any]:
        """逐期 Top5 命中复盘台账（开奖后结算 / 回测灌入）"""
        try:
            from backend.modules._retired.point_omission.hit_ledger import get_hit_ledger
            return get_hit_ledger(self.proj_dir, n=int(n or 40))
        except Exception as e:
            logger.error(f"读取点位+遗漏逐期命中台账失败: {e}", exc_info=True)
            return {"status": "error", "message": str(e), "rows": []}

    def seed_point_omission_hit_ledger(self, n: int = 40) -> Dict[str, Any]:
        """用近 n 期严格回测灌入逐期命中台账"""
        try:
            from backend.modules._retired.point_omission.hit_ledger import seed_ledger_from_backtest
            return seed_ledger_from_backtest(self.proj_dir, n=int(n or 40), verbose=False)
        except Exception as e:
            logger.error(f"灌入点位+遗漏逐期命中台账失败: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

