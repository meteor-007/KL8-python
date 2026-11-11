# -*- coding: utf-8 -*-
"""
马尔可夫直线校准接口路由 (Markov Line API Routes)
=================================================
提供 RESTful API 供前端和调度服务获取最新预测、直线校准报告和回测对账。
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional

from backend.modules.markov_line.service import (
    get_latest_markov_line_data,
    run_markov_line_pipeline,
    get_markov_line_review,
)

router = APIRouter(prefix="/api/quant/markov_line", tags=["马尔可夫直线校准引擎"])


@router.get("/latest", summary="获取最新马尔可夫链与特征直线校准推演结果")
async def get_latest_data():
    try:
        data = get_latest_markov_line_data()
        return JSONResponse(content={"code": 200, "message": "success", "data": data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})


@router.get("/review", summary="获取近 N 期马尔可夫直线引擎样本外滚动对账流水与提升度")
async def get_review_data(
    n: int = Query(30, ge=5, le=100, description="回溯期数")
):
    try:
        data = get_markov_line_review(n=n)
        return JSONResponse(content={"code": 200, "message": "success", "data": data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})


@router.post("/run", summary="手动触发马尔可夫直线校准推演流水线")
async def run_pipeline_endpoint(limit: Optional[int] = Query(None, description="限制期数")):
    try:
        result = run_markov_line_pipeline(limit=limit)
        return JSONResponse(content={"code": 200, "message": "流水线执行成功", "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})
