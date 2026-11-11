# -*- coding: utf-8 -*-
"""一胆拖三盾 · 选2组合拳 FastAPI 路由接口 (@since 2026-10-22)"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.modules.spear_shield_portfolio.service import (
    get_spear_shield_history,
    get_spear_shield_review,
    rerun_spear_shield_review,
    run_spear_shield_prediction,
)

router = APIRouter(prefix="/api/spear_shield", tags=["一胆拖三盾选2组合拳"])


@router.get("/latest")
def api_spear_shield_latest():
    """获取当期一胆拖三盾票面 (攻矛/三盾/组合拳/风控, 引擎按需即算)"""
    try:
        return {"status": "ok", "data": run_spear_shield_prediction()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取一胆拖三盾票面失败: {e}")


@router.get("/review")
def api_spear_shield_review(
    n: int = Query(default=0, ge=0, le=100, description="展示期数 (0=用账本现成期数)"),
):
    """读取近 N 期样本外滚动复盘 (Walk-Forward 账本, 严格无未来信息)"""
    try:
        return {"status": "ok", "data": get_spear_shield_review(n=n or None)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取一胆拖三盾复盘失败: {e}")


@router.post("/review-rerun")
def api_spear_shield_review_rerun(
    n: int = Query(default=30, ge=5, le=100, description="回测期数"),
):
    """显式重跑样本外回测 (慢操作, 供驾驶舱按钮)"""
    try:
        return {"status": "ok", "data": rerun_spear_shield_review(n_periods=n)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重跑一胆拖三盾回测失败: {e}")


@router.get("/history")
def api_spear_shield_history():
    """历史研报 md 文件索引"""
    try:
        return {"status": "ok", "data": get_spear_shield_history()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取一胆拖三盾历史失败: {e}")
