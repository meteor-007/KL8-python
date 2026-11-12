# -*- coding: utf-8 -*-
"""跟随分析 API (retired)"""
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
router = APIRouter(prefix="/api/follow", tags=['follow'])

@router.get("/summary")
def get_follow_summary():
    """获取跟随分析最新预测、重复号Top5、推演Top6、条件跟随Top8、共振交集与多维交叉打标"""
    return data_service.get_follow_summary()

@router.get("/review")
def get_follow_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期跟随分析 Walk-Forward 滚动样本外对账流水与三路 Lift 指标"""
    return data_service.get_follow_review(n=n)

@router.get("/conditions")
def get_follow_conditions():
    """获取最新上期 Top 5 黄金条件对、多时间窗口跟随明细与 >= 3 窗交集"""
    return data_service.get_follow_conditions()

