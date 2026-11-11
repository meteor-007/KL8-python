# -*- coding: utf-8 -*-
"""定金选2 API"""
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
router = APIRouter(prefix="/api/gold-pick2", tags=['gold-pick2'])

@router.get("/summary")
def get_gold_pick2_summary():
    """获取定金选2最新核心预测(双重金胆、Top5黄金搭档配对、温号池、置信等级与交叉风控)"""
    res = data_service.get_gold_pick2_summary()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@router.get("/review")
def get_gold_pick2_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期定金选2 Walk-Forward 样本外对账流水与统计指标"""
    return data_service.get_gold_pick2_review(n=n)

@router.get("/matrix")
def get_gold_pick2_matrix():
    """获取定金选2 80 码 7 维特征打分与雷达态势数据"""
    return data_service.get_gold_pick2_matrix()

@router.get("/logs")
def get_gold_pick2_logs():
    """获取定金选2历史研报清单"""
    return data_service.get_gold_pick2_history_list()

@router.get("/log-detail/{filename}")
def get_gold_pick2_log_detail(filename: str):
    """获取指定定金选2预测研报内容"""
    try:
        return data_service.get_gold_pick2_history_detail(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到指定的定金选2研报")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

