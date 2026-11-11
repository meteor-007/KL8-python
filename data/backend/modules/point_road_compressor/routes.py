# -*- coding: utf-8 -*-
"""点位012偏态压缩器 FastAPI 路由接口 (@since 2026-10-22)"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.modules.point_road_compressor.service import (
    get_point_road_history,
    get_point_road_prediction,
    get_point_road_review,
)

router = APIRouter(prefix="/api/point_road", tags=["点位012偏态压缩器"])


@router.get("/latest")
def api_point_road_latest(period: Optional[str] = Query(default=None, description="指定期号 (默认自动推断下一期)")):
    """获取当期压缩票面 (金胆/最优3/精选5/十全防线/跨路选2/剪枝/012大盘偏态)"""
    try:
        return {"status": "ok", "data": get_point_road_prediction(target_period=period)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取点位012压缩票面失败: {e}")


@router.get("/review")
def api_point_road_review(n: int = Query(default=30, ge=5, le=100, description="回测期数")):
    """样本外滚动对账 (逐期仅用当日前历史, 30期约 0.05s)"""
    try:
        data = get_point_road_review(n_periods=n)
        if data.get("status") == "error":
            raise HTTPException(status_code=500, detail=data.get("message", "复盘失败"))
        return {"status": "ok", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"点位012压缩复盘失败: {e}")


@router.get("/history")
def api_point_road_history():
    """历史期号 JSON 产物索引"""
    try:
        return {"status": "ok", "data": get_point_road_history()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取点位012历史失败: {e}")
