# -*- coding: utf-8 -*-
"""选二 K 线形态与反向排雷 API 路由"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.modules.kline_pick2.kline_engine import (
    get_kline_summary,
    get_pair_kline_chart,
)

router = APIRouter(prefix="/api/kline-pick2", tags=["kline_pick2"])


@router.get("/summary")
def api_kline_summary(oos_window: int = Query(200, ge=30, le=500)):
    """获取全盘 3160 对选二 K 线健康度 Top10、反向避坑警示与 200 期样本外对比。"""
    return get_kline_summary(oos_window=oos_window)


@router.get("/chart/{a}/{b}")
def api_kline_chart(a: int, b: int, candles: int = Query(60, ge=15, le=120)):
    """获取指定选二组合 (a, b) 的 5 期蜡烛 K 线序列与信号明细。"""
    res = get_pair_kline_chart(a, b, num_candles=candles)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message", "参数错误"))
    return res
