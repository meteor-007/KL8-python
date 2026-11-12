# -*- coding: utf-8 -*-
"""统一决策主脑 / 进化 / 调度 API"""
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
router = APIRouter(tags=['unified-brain'])

@router.get("/api/quant/unified-brain")
def get_unified_brain_latest():
    """获取全栈统一决策主脑最新推演结果 (尖刀金胆、黄金选2、最优3码)"""
    try:
        res = data_service.get_unified_brain_latest()
        if res.get("status") == "error":
            logger.warning(f"统一决策主脑接口返回警告: {res.get('message')}")
            return JSONResponse(status_code=200, content={"status": "error", "message": res.get("message"), "data": None})
        return res
    except Exception as e:
        logger.error(f"统一决策主脑接口未捕获异常: {e}", exc_info=True)
        return JSONResponse(status_code=200, content={"status": "error", "message": str(e), "data": None})

@router.get("/api/evolution/status")
def get_evolution_status():
    """获取元学习自动进化模型当前代数、各模块元权重与三维参数"""
    return data_service.get_evolution_status()

@router.get("/api/evolution/history")
def get_evolution_history():
    """获取自动进化总账本历史演进记录"""
    return data_service.get_evolution_history()

@router.get("/api/scheduler/status")
def get_scheduler_status():
    """获取每天 22:00 夜间全自动调度器实时状态与下次触发倒计时"""
    return data_service.get_scheduler_status()

@router.post("/api/scheduler/trigger-now")
def trigger_scheduler_now():
    """手动立即触发一次 22:00 夜间全自动流水线"""
    try:
        from backend.scheduler.nightly_scheduler import scheduler_instance
        res = scheduler_instance.trigger_now(async_mode=True)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

