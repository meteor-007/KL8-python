# -*- coding: utf-8 -*-
"""残差改错预测 FastAPI 路由接口"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from backend.modules.error_correction.service import (
    get_latest_error_correction_data,
    run_error_correction_pipeline,
    get_error_correction_review,
)

router = APIRouter(prefix="/api/error_correction", tags=["残差改错预测"])


@router.get("/latest")
def api_get_latest_error_correction():
    """获取最新一期残差改错预测与诊断结果"""
    try:
        data = get_latest_error_correction_data()
        return {"status": "ok", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取残差改错预测失败: {e}")


@router.get("/review")
def api_get_error_correction_review(
    n: int = Query(default=30, ge=5, le=100, description="回溯对账期数"),
    force_refresh: bool = Query(default=False, description="是否强制刷新对账"),
):
    """获取近 N 期严格样本外逐期滚动 Walk-Forward 实战对账复盘"""
    try:
        data = get_error_correction_review(n=n, force_refresh=force_refresh)
        return {"status": "ok", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"残差改错实战对账失败: {e}")


@router.post("/run")
def api_run_error_correction(
    limit: Optional[int] = Query(default=None, description="训练窗口期数"),
):
    """手动立即触发残差改错预测推演"""
    try:
        result = run_error_correction_pipeline(limit=limit)
        return {"status": "ok", "message": "残差改错推演成功", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"运行残差改错推演异常: {e}")
