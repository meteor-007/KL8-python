# -*- coding: utf-8 -*-
"""未开点位高压反弹 API"""
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
router = APIRouter(prefix="/api/suppression", tags=['suppression'])

@router.get("/summary")
def get_suppression_summary():
    """获取未开点位高压反弹最新预测、Top3金胆、弹簧压制状态与多维交叉打标"""
    return data_service.get_suppression_summary()

@router.get("/review")
def get_suppression_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期未开点位反弹 Walk-Forward 滚动样本外对账流水与置信评定"""
    return data_service.get_suppression_review(n=n)

@router.get("/patterns")
def get_suppression_patterns():
    """获取未开点位历史模式：弹簧张力回补率、能量外溢漂移与影子替身伴生对"""
    return data_service.get_suppression_patterns()

