# -*- coding: utf-8 -*-
"""数据源1x2 API"""
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
router = APIRouter(prefix="/api/datasource", tags=['datasource'])

@router.get("/summary")
def get_datasource_summary():
    """获取数据源1×2最新深层关联预测(精选爆发Top5、跨规则共识金胆、黄金连体婴选2、D2外部杀号池)"""
    res = data_service.get_datasource_summary()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@router.get("/review")
def get_datasource_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期数据源1×2 Walk-Forward 样本外对账流水与命中指标"""
    res = data_service.get_datasource_review(n=n)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@router.get("/history")
def get_datasource_history():
    """获取数据源1×2深层关联历史预测列表"""
    return data_service.get_datasource_history_list()

@router.get("/matrix")
def get_datasource_matrix(period: Optional[str] = Query(None, description="指定期号，默认最新期")):
    """获取指定期号《跟随+点位+开奖数据.xlsx》数据源1与数据源2高保真 4x4 板块阵列与状态标记"""
    res = data_service.get_datasource_matrix_by_period(period=period)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

