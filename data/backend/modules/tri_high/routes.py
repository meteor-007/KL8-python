# -*- coding: utf-8 -*-
"""三高特征 API"""
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
router = APIRouter(prefix="/api/tri-high", tags=['tri-high'])

@router.get("/summary")
def get_tri_high_summary():
    """获取三高特征与每日点位最新量化共振推演结果"""
    res = data_service.get_tri_high_summary()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@router.get("/history")
def get_tri_high_history():
    """获取三高逐期历史记录（包含开奖自动标黄与命中数统计）"""
    res = data_service.get_tri_high_history()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@router.post("/save")
def save_tri_high_record(payload: Dict[str, Any] = Body(...)):
    """录入或更新某一期的三高数据"""
    res = data_service.save_tri_high_record(payload)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.delete("/delete/{period}")
def delete_tri_high_record(period: str):
    """删除指定期的三高记录"""
    res = data_service.delete_tri_high_record(period)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

