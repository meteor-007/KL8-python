# -*- coding: utf-8 -*-
"""Gemini pick2 API (retired)"""
from __future__ import annotations

import os
import json
import time
import uuid
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Body
from fastapi.responses import JSONResponse

from backend.api.deps import (
    data_service,
    TASK_STORE,
    find_script,
    run_script_task,
    run_points_downstream_task,
    ParamUpdateModel,
    DailyPointsSubmitModel,
    PROJ_DIR,
    data_path,
)

logger = logging.getLogger("k8quant.api")
router = APIRouter(prefix="/api/gemini", tags=['gemini'])

@router.get("/summary")
def get_gemini_summary():
    """获取 Gemini 选2最新核心预测(金银铜胆、核心4码、终极5码、铁血做空区、异象雷达)"""
    res = data_service.get_gemini_summary()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@router.get("/review")
def get_gemini_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期 Gemini 选2 Walk-Forward 样本外对账流水与统计指标"""
    return data_service.get_gemini_review(n=n)

@router.get("/history")
def get_gemini_history():
    """获取 Gemini 选2历史预测研报列表"""
    return data_service.get_gemini_history_list()

@router.get("/history-detail/{filename}")
def get_gemini_history_detail(filename: str):
    """获取指定 Gemini 选2预测研报内容"""
    try:
        return data_service.get_gemini_history_detail(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到指定的预测研报")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

