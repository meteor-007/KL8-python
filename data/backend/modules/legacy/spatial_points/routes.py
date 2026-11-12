# -*- coding: utf-8 -*-
"""空间重点点位 API (retired)"""
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
router = APIRouter(prefix="/api/spatial-points", tags=['spatial-points'])

@router.get("/summary")
def get_spatial_points_summary():
    """获取空间重点点位最新预测、核心五码、精选十码、8区覆盖与多维交叉风控"""
    return data_service.get_spatial_points_summary()

@router.get("/matrix")
def get_spatial_points_matrix():
    """获取 80 点位全盘空间特征、得分、p值显著性与 4 维雷达数据"""
    return data_service.get_spatial_points_matrix()

@router.get("/review")
def get_spatial_points_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期重点点位 Walk-Forward 滚动样本外复盘对账流水与置信评定"""
    return data_service.get_spatial_points_review(n=n)

