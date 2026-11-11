# -*- coding: utf-8 -*-
"""复盘总账本 API"""
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
router = APIRouter(prefix="/api/reviews", tags=['reviews'])

@router.get("/ledger")
def get_reviews_ledger(limit: int = Query(50, ge=5, le=200, description="获取复盘期数")):
    """获取全量 47+ 期每日自学习自动复盘对账总账本与全局核心指标"""
    return data_service.get_daily_reviews_ledger(limit=limit)

@router.get("/detail/{period}")
def get_review_detail(period: str):
    """获取指定期号的详细复盘 JSON 数据"""
    try:
        return data_service.get_review_detail(period)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到第 {period} 期的复盘记录")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/master-summary")
def get_master_review_summary(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取 15 大全模块实战命中复盘总决算天梯榜"""
    return data_service.get_master_review_summary(n=n)

