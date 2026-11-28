# -*- coding: utf-8 -*-
"""表10「同数值」影子观察 API 路由"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.modules.table10_shadow.service import (
    get_period_detail,
    get_shadow_summary,
)

router = APIRouter(prefix="/api/table10-shadow", tags=["table10_shadow"])


@router.get("/summary")
def api_table10_shadow_summary():
    """获取表10「同数值」影子观察汇总、转正进度与逐期对账流水。"""
    return get_shadow_summary()


@router.get("/period/{period}")
def api_table10_shadow_period(period: int):
    """获取指定期号的表10遗漏分层明细矩阵。"""
    res = get_period_detail(period)
    if res.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"未找到期号 {period} 的表10录入记录")
    return res
