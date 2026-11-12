# -*- coding: utf-8 -*-
"""LSTM API (retired)"""
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
router = APIRouter(prefix="/api/lstm", tags=['lstm'])

@router.get("/summary")
def get_lstm_summary():
    """获取双层LSTM深度学习最新预测、金银铜胆、Top10及近期实战对账"""
    return data_service.get_lstm_summary()

@router.get("/review")
def get_lstm_review(n: int = Query(15, ge=5, le=50, description="复盘期数")):
    """获取近 N 期双层LSTM历史实测复盘与对账明细"""
    return data_service.get_lstm_review(n=n)

@router.get("/reports")
def get_lstm_reports():
    """获取双层LSTM深度时序历史研报与预测文件列表"""
    return data_service.get_lstm_reports_list()

@router.get("/report-detail/{filename}")
def get_lstm_report_detail(filename: str):
    """获取指定双层LSTM研报或预测单的内容"""
    try:
        return data_service.get_lstm_report_detail(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到指定的 LSTM 研报文件")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

