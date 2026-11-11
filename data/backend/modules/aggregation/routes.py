# -*- coding: utf-8 -*-
"""终审汇总复盘 API"""
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
router = APIRouter(prefix="/api/aggregation", tags=['aggregation'])

@router.get("/cockpit")
def get_aggregation_cockpit():
    """获取终审数据汇总复盘大屏数据"""
    try:
        return data_service.get_aggregation_cockpit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取终审复盘驾驶舱数据失败: {e}")

@router.get("/history")
def get_aggregation_history():
    """获取历史汇总复盘报告列表"""
    try:
        return data_service.get_aggregation_history_list()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取汇总复盘历史失败: {e}")

@router.get("/history/{filename}")
def get_aggregation_history_detail(filename: str):
    """读取指定汇总复盘报告内容"""
    try:
        return data_service.get_aggregation_history_detail(filename)
    except FileNotFoundError as fe:
        raise HTTPException(status_code=404, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取汇总复盘详情失败: {e}")

@router.post("/run")
def trigger_aggregation_run(background_tasks: BackgroundTasks, force: bool = Query(True)):
    """一键触发后台执行终审数据汇总复盘"""
    task_id = f"task_agg_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "终审共识与数据汇总复盘 (7路多维共振 + 8区空间平衡)",
        "script": "run_aggregation_daily.py",
        "status": "QUEUED",
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 任务已加入执行队列..."]
    }
    args = ["--force"] if force else []
    background_tasks.add_task(run_script_task, task_id, "run_aggregation_daily.py", args)
    return {"task_id": task_id, "status": "QUEUED", "message": "终审数据汇总复盘任务已成功派发！"}

