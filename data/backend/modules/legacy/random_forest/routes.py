# -*- coding: utf-8 -*-
"""随机森林号码预测 API"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional

from backend.modules.legacy.random_forest.service import (
    get_latest_random_forest_data,
    run_random_forest_pipeline,
    get_random_forest_review,
)

router = APIRouter(prefix="/api/quant/random-forest", tags=["随机森林号码预测"])


@router.get("/latest")
async def get_latest_data():
    try:
        data = get_latest_random_forest_data()
        return JSONResponse(content={"code": 200, "message": "success", "data": data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})


@router.get("/review")
async def get_review_data(
    n: int = Query(30, ge=5, le=100),
    force_refresh: bool = Query(False),
):
    try:
        data = get_random_forest_review(n=n, force_refresh=force_refresh)
        return JSONResponse(content={"code": 200, "message": "success", "data": data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})


@router.post("/run")
async def run_pipeline_endpoint(limit: Optional[int] = Query(None)):
    try:
        result = run_random_forest_pipeline(limit=limit)
        return JSONResponse(content={"code": 200, "message": "随机森林号码预测成功", "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": str(e), "data": None})
