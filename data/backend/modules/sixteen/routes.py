# -*- coding: utf-8 -*-
"""16期中热 API"""
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
router = APIRouter(prefix="/api/sixteen", tags=['sixteen'])

@router.get("/summary")
def get_sixteen_summary(force: bool = Query(False, description="强制重算（点位/杀号变更后）")):
    """获取 16 期中热频次推演最新核心大屏数据 (含每日操盘简报)"""
    res = data_service.get_sixteen_summary(force_refresh=force)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@router.get("/review")
def get_sixteen_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期 16 期中热推演 Walk-Forward 滚动样本外对账流水与统计指标"""
    return data_service.get_sixteen_review(n=n)

@router.get("/history")
def get_sixteen_history():
    """获取 16 期中热推演历史研报列表"""
    return data_service.get_sixteen_history_list()

@router.get("/history-detail/{filename}")
def get_sixteen_history_detail(filename: str):
    """获取指定 16 期中热推演研报内容"""
    try:
        return data_service.get_sixteen_history_detail(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到指定的研报文件")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bucket-sort-compare")
def get_sixteen_bucket_sort_compare(n: int = Query(20, ge=5, le=60, description="近N个已开目标期")):
    """对比各桶内排序的精选命中，标出样本最优（不改配置）"""
    try:
        res = data_service.get_sixteen_bucket_sort_compare(n=n)
        if res.get("status") == "error":
            raise HTTPException(status_code=400, detail=res.get("message"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bucket-lookback")
def get_sixteen_bucket_lookback(offset: int = Query(1, ge=1, le=30, description="回看第几期已开目标（1=上一目标期）")):
    """回看已开目标期的频次桶精选/剩余命中（不改写最新大屏缓存）"""
    try:
        res = data_service.get_sixteen_bucket_lookback(offset=offset)
        if res.get("status") == "error":
            raise HTTPException(status_code=400, detail=res.get("message"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bucket-config")
def update_sixteen_bucket_config(payload: Dict[str, Any] = Body(default={})):
    """更新频次桶精选/剩余规则（mode/sort_by/quotas…）并重算大屏"""
    try:
        return data_service.update_sixteen_bucket_config(payload or {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/excel-window")
def get_sixteen_excel_window(persist: bool = Query(True, description="是否落盘 xlsx/md/json")):
    """Excel 同款 16 期开奖矩阵：1头=10-19（≠一区01-10），含 COUNTIFS/连冷统计"""
    try:
        res = data_service.get_sixteen_excel_window(persist=persist)
        if res.get("status") == "error":
            raise HTTPException(status_code=400, detail=res.get("message"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/folk-summary")
def get_folk_sixteen_summary(
    target_period: Optional[int] = Query(None, description="目标期号，默认预测下一期"),
    persist: bool = Query(True, description="是否自动生成 txt 和 xlsx 资产")
):
    """获取 16 期窗口「新方法」高保真全景分析大盘与实战选号数据"""
    try:
        return data_service.get_folk_sixteen_analysis(target_period=target_period, persist=persist)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dimension-cross")
def get_dimension_cross(
    target_period: Optional[int] = Query(None, description="目标期号，默认预测下一期")
):
    """16 期窗口维度交叉研究：出现次数×剩余次数矩阵 + 尾数/012路/质合画像 + 约束优化选号"""
    try:
        from backend.modules.sixteen.sixteen_engine import load_draws_from_file
        from backend.modules.sixteen.dimension_cross import analyze_dimension_cross
        draws = load_draws_from_file()
        if target_period is not None:
            idx = next(
                (i for i, d in enumerate(draws) if int(d["period"]) == int(target_period)),
                None,
            )
            if idx is None:
                raise HTTPException(status_code=404, detail=f"未找到期号 {target_period}")
            return analyze_dimension_cross(draws, target_idx=idx)
        return analyze_dimension_cross(draws)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dimension-arbitrage")
def get_dimension_arbitrage(
    n: int = Query(200, ge=30, le=1000, description="回测期数"),
    size: int = Query(20, ge=1, le=20, description="选号口径"),
    restarts: int = Query(25, ge=5, le=120, description="约束优化重启次数")
):
    """三轨样本外仲裁：纯动量 vs 动量+维度约束 vs 遗漏甜区回补（含显著性检验）"""
    try:
        from backend.modules.sixteen.sixteen_engine import load_draws_from_file
        from backend.modules.sixteen.dimension_cross import run_dimension_arbitrage
        draws = load_draws_from_file()
        return run_dimension_arbitrage(draws, n_periods=n, pick_size=size, restarts=restarts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


