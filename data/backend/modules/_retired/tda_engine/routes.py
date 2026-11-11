# -*- coding: utf-8 -*-
"""TDA API Routes"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional

from backend.modules._retired.tda_engine.service import (
    get_latest_tda_data,
    run_tda_pipeline,
    get_tda_review
)

router = APIRouter(prefix="/api/quant/tda", tags=["拓扑数据分析TDA模块"])


@router.get("/latest", summary="获取最新TDA拓扑推演结果")
async def get_latest_data():
    try:
        data = get_latest_tda_data()
        return JSONResponse(content={"code": 200, "message": "success", "data": data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})


@router.get("/review", summary="获取近 N 期 TDA 持续同调 Walk-Forward 样本外对账流水与命中详情")
async def get_review_data(
    n: int = Query(30, ge=5, le=100, description="回溯期数"),
    force_refresh: bool = Query(False, description="是否强制重新计算")
):
    try:
        data = get_tda_review(n=n, force_refresh=force_refresh)
        return JSONResponse(content={"code": 200, "message": "success", "data": data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})


@router.post("/run", summary="手动触发TDA拓扑推演流水线")
async def run_pipeline_endpoint(limit: Optional[int] = Query(None)):
    try:
        result = run_tda_pipeline(limit=limit)
        return JSONResponse(content={"code": 200, "message": "TDA流水线执行成功", "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})

