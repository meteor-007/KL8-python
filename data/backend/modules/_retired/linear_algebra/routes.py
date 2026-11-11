# -*- coding: utf-8 -*-
"""
线性代数空间投影 API 路由 (Linear Algebra Routes)
===================================================
【业务背景与架构定位】:
提供量化大屏前端获取最新线性代数预测结果、触发计算、获取历史镜像详情的 RESTful 接口。

@author K8-Quant Linear Algebra Team
@since 2026-09-11
"""
from fastapi import APIRouter, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional

from backend.modules._retired.linear_algebra.service import (
    get_latest_linear_algebra_data,
    run_linear_algebra_pipeline,
    get_linear_algebra_review
)

router = APIRouter(prefix="/api/quant/linear-algebra", tags=["线性代数空间投影量化模块"])


@router.get("/latest", summary="获取最新的线性代数空间投影推演结果")
async def get_latest_data():
    """
    返回包含 Top5金胆、Top12优选、黄金搭档选2、80码全景打分、历史镜像Top3匹配及SVD方差占比等完整数据。
    """
    try:
        data = get_latest_linear_algebra_data()
        return JSONResponse(content={"code": 200, "message": "success", "data": data})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"获取线性代数推演数据失败: {str(e)}", "data": None}
        )


@router.get("/review", summary="获取近 N 期线性代数空间投影 Walk-Forward 样本外对账流水与命中详情")
async def get_review_data(
    n: int = Query(30, ge=5, le=100, description="回溯期数"),
    force_refresh: bool = Query(False, description="是否强制重新计算")
):
    """
    返回包含 Top5/Top12/金胆/选2/杀号的近 N 期逐期实测命中明细与提升度 Lift 指标。
    """
    try:
        data = get_linear_algebra_review(n=n, force_refresh=force_refresh)
        return JSONResponse(content={"code": 200, "message": "success", "data": data})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"获取线性代数对账失败: {str(e)}", "data": None}
        )


@router.post("/run", summary="手动触发一次线性代数空间投影计算流水线")
async def run_pipeline_endpoint(limit: Optional[int] = Query(None, description="限制历史期数")):
    """
    手动执行全量矩阵计算并刷新落盘缓存。
    """
    try:
        result = run_linear_algebra_pipeline(limit=limit)
        return JSONResponse(content={"code": 200, "message": "线性代数推演流水线执行成功", "data": result})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"执行推演流水线异常: {str(e)}", "data": None}
        )

