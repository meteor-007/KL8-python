# -*- coding: utf-8 -*-
"""顺口溜口诀 API"""
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
router = APIRouter(prefix="/api/jingle", tags=['jingle'])

@router.get("/summary")
def get_jingle_summary():
    """获取顺口溜口诀最新预测、触发口诀明细与交叉风控打标"""
    return data_service.get_jingle_summary()

@router.get("/review")
def get_jingle_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期顺口溜口诀对账复盘流水与真·样本外分层指标"""
    return data_service.get_jingle_review(n=n)

@router.get("/rules")
def get_jingle_rules(
    kind: Optional[str] = Query(None, description="规则类型 (pair_pair/triple_single)"),
    keyword: Optional[str] = Query(None, description="号码或ID搜索关键字")
):
    """获取 90 条精英口诀规则清单与元数据"""
    return data_service.get_jingle_rules(kind=kind, keyword=keyword)

