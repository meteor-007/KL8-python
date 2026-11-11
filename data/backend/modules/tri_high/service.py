# -*- coding: utf-8 -*-
"""TriHighServiceMixin: methods extracted from QuantDataService"""
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


class TriHighServiceMixin:
    def get_tri_high_summary(self) -> Dict[str, Any]:
        """
        获取三高特征与每日点位最新量化共振推演结果
        """
        try:
            from backend.core.tri_high_engine import TriHighResonanceEngine
            engine = TriHighResonanceEngine(self.proj_dir)
            analysis = engine.run_tri_high_analysis()
            if isinstance(analysis, dict) and "recommendations" in analysis:
                analysis["top3_gold"] = analysis["recommendations"].get("top3_gold", [])
            return {
                "status": "ok",
                "data": analysis
            }
        except Exception as e:
            logger.error(f"获取三高量化推演结果失败: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"获取三高量化推演失败: {str(e)}"
            }

    def get_tri_high_history(self) -> Dict[str, Any]:
        """
        获取三高逐期历史手账记录（包含开奖自动标黄与命中率统计）
        """
        try:
            from backend.core.tri_high_engine import TriHighResonanceEngine
            engine = TriHighResonanceEngine(self.proj_dir)
            rows = engine.get_history_with_wins()
            return {
                "status": "ok",
                "total": len(rows),
                "rows": rows
            }
        except Exception as e:
            logger.error(f"获取三高历史手账记录失败: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"获取三高历史手账失败: {str(e)}"
            }

    def save_tri_high_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        录入或更新某一期的三高数据，并触发最新量化共振推演
        """
        try:
            from backend.core.tri_high_engine import TriHighResonanceEngine
            engine = TriHighResonanceEngine(self.proj_dir)
            saved = engine.save_record(payload)
            analysis = engine.run_tri_high_analysis()
            return {
                "status": "ok",
                "saved_record": saved,
                "analysis": analysis
            }
        except Exception as e:
            logger.error(f"保存三高数据失败: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"保存三高数据失败: {str(e)}"
            }

    def delete_tri_high_record(self, period: str) -> Dict[str, Any]:
        """
        删除指定期的三高手账记录
        """
        try:
            from backend.core.tri_high_engine import TriHighResonanceEngine
            engine = TriHighResonanceEngine(self.proj_dir)
            ok = engine.delete_record(period)
            if ok:
                return {"status": "ok", "message": f"期号 {period} 三高数据已删除"}
            else:
                return {"status": "error", "message": f"期号 {period} 不存在或删除失败"}
        except Exception as e:
            logger.error(f"删除三高数据失败 ({period}): {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"删除三高数据失败: {str(e)}"
            }

