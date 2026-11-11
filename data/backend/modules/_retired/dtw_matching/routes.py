# -*- coding: utf-8 -*-
"""DTW API Routes"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional

from backend.modules._retired.dtw_matching.service import (
    get_latest_dtw_data,
    run_dtw_pipeline,
    get_dtw_review
)

router = APIRouter(prefix="/api/quant/dtw", tags=["动态时间规整DTW模块"])


@router.get("/latest", summary="获取最新DTW推演结果")
async def get_latest_data():
    try:
        data = get_latest_dtw_data()
        return JSONResponse(content={"code": 200, "message": "success", "data": data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})


@router.get("/review", summary="获取近 N 期 DTW 弹性走势推演 Walk-Forward 样本外对账流水与命中详情")
async def get_review_data(
    n: int = Query(30, ge=5, le=100, description="回溯期数"),
    force_refresh: bool = Query(False, description="是否强制重新计算")
):
    try:
        data = get_dtw_review(n=n, force_refresh=force_refresh)
        return JSONResponse(content={"code": 200, "message": "success", "data": data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})


@router.post("/run", summary="手动触发DTW推演流水线")
async def run_pipeline_endpoint(limit: Optional[int] = Query(None)):
    try:
        result = run_dtw_pipeline(limit=limit)
        return JSONResponse(content={"code": 200, "message": "DTW流水线执行成功", "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})

