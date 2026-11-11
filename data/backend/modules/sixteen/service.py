# -*- coding: utf-8 -*-
"""SixteenServiceMixin: methods extracted from QuantDataService"""
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


class SixteenServiceMixin:
    def get_sixteen_summary(self, force_refresh: bool = False) -> Dict[str, Any]:
        """获取 16 期中热号频次动态推演最新核心大屏数据"""
        history = self.load_history(limit=1)
        curr_latest_period = int(history[0]["period"]) if history and str(history[0]["period"]).isdigit() else None

        def _current_points_tuple(target_period: Any) -> Optional[tuple]:
            if target_period is None:
                return None
            try:
                from backend.data_acquisition.daily_points_manager import load_daily_points
                entry = load_daily_points().get(str(int(target_period)))
                if not entry:
                    return None
                return tuple(int(x) for x in (entry.get("points") or []))
            except Exception:
                return None

        cache_file = os.path.join(get_cache_dir(), "sixteen_period", "latest_summary.json")
        if (not force_refresh) and os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                period_ok = curr_latest_period is None or data.get("latest_period") == curr_latest_period
                has_brief = bool(data.get("daily_ops_brief"))
                brief = data.get("daily_ops_brief") or {}
                scoring_ok = brief.get("scoring_version") == "ops_pts_v4"
                has_dim = bool(brief.get("bucket_dimension_board") or data.get("bucket_dimension_board"))
                brief_pts = tuple(
                    int(x) for x in (brief.get("points") or {}).get("points") or []
                )
                live_pts = _current_points_tuple(data.get("target_period"))
                brief_matched = bool((brief.get("points") or {}).get("matched"))
                brief_applied = (brief.get("points") or {}).get("points_applied")
                # 点位已录入/变更但缓存未跟上；或仍缺 points_applied 字段 → 强制重算
                points_stale = False
                if live_pts is not None and (not brief_matched or brief_pts != live_pts):
                    points_stale = True
                if brief_applied is None:
                    points_stale = True
                # 无目标期点位时，缓存却仍把回落点位当已加权 → 重算
                if live_pts is None and brief_applied is True:
                    points_stale = True
                if period_ok and has_brief and scoring_ok and has_dim and not points_stale:
                    return data
            except Exception:
                pass

        try:
            from backend.core.sixteen_period.sixteen_engine import run_single_period_analysis
            return run_single_period_analysis()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_sixteen_review(self, n: int = 30) -> Dict[str, Any]:
        """获取近 N 期 16 期中热决策 Walk-Forward 滚动样本外对账流水

        2026-10-22 性能缺陷修复 (Bug#12)：
        原实现把缓存命中条件写死成 `n == 30` —— 只要调用方传别的窗口 (例如 FDR 审计
        接口 `/api/quant/fdr-audit` 默认 n=100)，缓存就**必然失效**并触发全量重算。
        实测冷启动下 `run_walk_forward_review(n_periods=100)` 耗时 26.85s，是整个
        `get_hit_leaderboard`(47.65s) 的最大热点，导致前端 FDR 页面请求超时。
        现改为按窗口缓存：每个窗口各存一份 `latest_review_n{N}.json`，
        并复用同一套「评分口径 + 最新期号」双重校验，避免拿旧口径结果冒充。
        """
        history = self.load_history(limit=1)
        curr_latest_period = int(history[0]["period"]) if history and str(history[0]["period"]).isdigit() else None

        _cache_dir = os.path.join(get_cache_dir(), "sixteen_period")
        # n=30 沿用既有文件名 (向后兼容旧缓存)，其余窗口按 n 分文件
        _fname = "latest_review.json" if n == 30 else f"latest_review_n{int(n)}.json"
        cache_file = os.path.join(_cache_dir, _fname)

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                note = str(data.get("evidence_note") or "")
                scoring_ok = "ops_pts_v4" in note and "频4双轨" in note
                if (
                    scoring_ok
                    and data.get("stats", {}).get("n_periods") == n
                    and data.get("stats", {}).get("freq4_edge_avg_hits") is not None
                    and (curr_latest_period is None or data.get("latest_period") == curr_latest_period)
                ):
                    return data
            except Exception:
                pass

        try:
            from backend.core.sixteen_period.sixteen_reviewer import SixteenPeriodReviewer
            reviewer = SixteenPeriodReviewer()
            result = reviewer.run_walk_forward_review(n_periods=n)
            # 写入按窗口命名的缓存，供后续同窗口调用直接命中 (失败不阻断主流程)
            try:
                os.makedirs(_cache_dir, exist_ok=True)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, default=str)
            except Exception:
                pass
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_sixteen_history_list(self) -> List[Dict[str, Any]]:
        """获取 16 期中热推演历史研报列表"""
        out_dirs = [
            os.path.join(get_reports_dir()),
            os.path.join(get_outputs_dir(), "reports")
        ]
        results = []
        seen = set()
        for d in out_dirs:
            if not os.path.exists(d):
                continue
            for f in os.listdir(d):
                if f.startswith("sixteen_analysis_report_") and f.endswith(".md") and f not in seen:
                    seen.add(f)
                    period_match = re.search(r"sixteen_analysis_report_(\d+)", f)
                    period = period_match.group(1) if period_match else "N/A"
                    fpath = os.path.join(d, f)
                    mtime = os.path.getmtime(fpath)
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                    results.append({
                        "filename": f,
                        "period": period,
                        "title": f"第 {period} 期 16期中热频次动态推演研报",
                        "mtime": mtime_str,
                        "size_bytes": os.path.getsize(fpath),
                        "path": fpath
                    })

        results.sort(key=lambda x: int(x["period"]) if x["period"].isdigit() else 0, reverse=True)
        return results

    def get_sixteen_history_detail(self, filename: str) -> Dict[str, Any]:
        """读取指定 16 期中热推演研报内容"""
        clean_name = os.path.basename(filename)
        candidates = [
            os.path.join(get_reports_dir(), clean_name),
            os.path.join(get_outputs_dir(), "reports", clean_name)
        ]
        for fpath in candidates:
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                return {
                    "filename": clean_name,
                    "content": content
                }

        raise FileNotFoundError("未找到指定的 16 期中热推演研报文件")

    def get_sixteen_bucket_lookback(self, offset: int = 1) -> Dict[str, Any]:
        """回看已开目标期的频次桶精选/剩余（含命中标注）。offset=1 即上一目标期。"""
        from backend.modules.sixteen.sixteen_engine import (
            SixteenPeriodEngine,
            load_draws_from_file,
        )
        offset = max(1, min(int(offset or 1), 30))
        draws = load_draws_from_file()
        if not draws or len(draws) < offset + 1:
            return {"status": "error", "message": "历史不足，无法回看"}
        # analyze_at_index(i) 的目标期 = draws[i].period+1；要回看已开目标期 draws[-offset]
        # 即 i = len(draws) - 1 - offset
        idx = len(draws) - 1 - offset
        if idx < 0:
            return {"status": "error", "message": "回看偏移超出范围"}
        engine = SixteenPeriodEngine(draws)
        result = engine.analyze_at_index(idx)
        fbp = result.get("freq_bucket_picks") or {}
        return {
            "status": "ok",
            "offset": offset,
            "target_period": result.get("target_period"),
            "latest_period": result.get("latest_period"),
            "outgoing_period": result.get("outgoing_period"),
            "has_actual": bool(fbp.get("has_actual")),
            "medium_top5": result.get("medium_top5"),
            "gold_dan": result.get("gold_dan"),
            "silver_dan": result.get("silver_dan"),
            "bronze_dan": result.get("bronze_dan"),
            "freq_bucket_picks": fbp,
        }

    def get_sixteen_bucket_sort_compare(self, n: int = 20) -> Dict[str, Any]:
        """近 N 期对比各桶内排序的精选命中，返回样本最优。"""
        from backend.modules.sixteen.sixteen_engine import compare_bucket_sort_methods
        return compare_bucket_sort_methods(n_periods=n)

    def update_sixteen_bucket_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新频次桶精选配置并立即重算大屏缓存。"""
        from backend.modules.sixteen.sixteen_engine import (
            save_bucket_pick_config,
            SixteenPeriodEngine,
            load_draws_from_file,
        )
        cfg = save_bucket_pick_config(updates or {})
        draws = load_draws_from_file()
        if not draws:
            return {"status": "error", "message": "无开奖历史，无法重算"}
        engine = SixteenPeriodEngine(draws)
        result = engine.analyze_at_index(len(draws) - 1)
        cache_dir = os.path.join(get_cache_dir(), "sixteen_period")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, "latest_summary.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return {
            "status": "ok",
            "config": (result.get("freq_bucket_picks") or {}).get("config") or cfg,
            "summary": result,
        }

    def get_sixteen_excel_window(self, persist: bool = True) -> Dict[str, Any]:
        """Excel 同款 16 期开奖矩阵（1头=10-19，≠一区）。"""
        from backend.modules.sixteen.excel_window_table import run_excel_window_from_draws
        from backend.modules.sixteen.sixteen_engine import load_draws_from_file

        draws = load_draws_from_file()
        if not draws:
            return {"status": "error", "message": "无开奖历史"}
        target_period = int(draws[-1]["period"]) + 1
        return run_excel_window_from_draws(draws, target_period=target_period, persist=persist)

    def get_folk_sixteen_analysis(self, target_period: Optional[int] = None, persist: bool = True) -> Dict[str, Any]:
        """
        获取 16 期窗口「新方法」高保真全景分析大盘与实战选号数据
        :param target_period: 待分析期号 (默认下一期)
        :param persist: 是否持久化 txt 和 xlsx
        :return: 包含 20码大底、12码精选、5金胆、分桶明细、复盘对账的完整字典
        """
        from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine
        from backend.modules.sixteen.folk_excel_builder import FolkExcelBuilder

        engine = FolkSixteenEngine()
        analysis_result = engine.analyze_window(target_period=target_period)

        if persist:
            txt_path, latest_txt = engine.save_plain_text_summary(analysis_result)
            builder = FolkExcelBuilder()
            xlsx_path = builder.export_excel(analysis_result)
            analysis_result["txt_path"] = txt_path
            analysis_result["xlsx_path"] = xlsx_path

            # 缓存最新 JSON 视图
            cache_dir = os.path.join(get_cache_dir(), "sixteen_period")
            os.makedirs(cache_dir, exist_ok=True)
            cache_json = os.path.join(cache_dir, "folk_sixteen_latest.json")
            try:
                # 剔除无法 json 序列化的 set (已被 engine 转为 list)
                with open(cache_json, "w", encoding="utf-8") as f:
                    json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"保存 folk_sixteen_latest.json 失败: {e}")

        return analysis_result


