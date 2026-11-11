# -*- coding: utf-8 -*-
"""点位+遗漏 API"""
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
router = APIRouter(prefix="/api/point-omission", tags=['point-omission'])

@router.get("/summary")
def get_point_omission_summary(refresh: bool = Query(False, description="是否强制重新计算")):
    """获取点位+遗漏号深度分析最新预测、Top5推荐、防御两码、Exp3权重与80码维度分"""
    res = data_service.get_point_omission_summary(force_refresh=refresh)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message", "获取点位+遗漏分析失败"))
    return res

@router.get("/report")
def get_point_omission_report():
    """获取点位+遗漏号深度分析最新 Markdown 格式研报全文"""
    res = data_service.get_point_omission_report()
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail=res.get("message", "研报未找到"))
    return res

@router.get("/backtest")
def get_point_omission_backtest():
    """获取点位+遗漏号深度分析系统 T=277 期滚动外样本回测天梯与各算法实战战报"""
    res = data_service.get_point_omission_backtest()
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail=res.get("message", "回测台账未找到"))
    return res


@router.get("/hit-ledger")
def get_point_omission_hit_ledger(n: int = Query(40, ge=1, le=300, description="返回最近 N 期")):
    """逐期命中复盘详细列表（期号 / Top5 / 实中球 / 命中数）"""
    res = data_service.get_point_omission_hit_ledger(n=n)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message", "读取逐期命中台账失败"))
    return res


@router.post("/hit-ledger/seed")
def seed_point_omission_hit_ledger(n: int = Query(40, ge=5, le=120, description="回测灌入近 N 期")):
    """用近 N 期严格无前视回测灌入逐期命中台账（首次落地或补洞）"""
    res = data_service.seed_point_omission_hit_ledger(n=n)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message", "灌入逐期命中台账失败"))
    return res

