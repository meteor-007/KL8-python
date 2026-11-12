# -*- coding: utf-8 -*-
"""
遗传算法推演 API 路由 (Genetic Algorithm Routes)
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from backend.api.deps import data_service

logger = logging.getLogger("k8quant.api")
router = APIRouter(prefix="/api/genetic", tags=["genetic"])


class GeneticEvolutionRequest(BaseModel):
    pop_size: int = Field(40, ge=10, le=100, description="种群大小")
    generations: int = Field(25, ge=10, le=60, description="进化代数")
    eval_periods: int = Field(15, ge=5, le=30, description="评估期数")


@router.get("/summary")
def get_genetic_summary(force_refresh: bool = Query(False, description="是否强制刷新重新进化")):
    """获取遗传算法最新期推演大屏数据 (尖刀金胆、黄金选2、Top5、Top12、杀号、收敛曲线与最优特征权重)"""
    res = data_service.get_genetic_summary(force_refresh=force_refresh)
    if isinstance(res, dict) and res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res


@router.get("/review")
def get_genetic_review(n: int = Query(30, ge=5, le=100, description="样本外滚动复盘期数")):
    """获取近 N 期遗传算法 Walk-Forward 滚动样本外对账流水与命中指标"""
    res = data_service.get_genetic_review(n=n)
    if isinstance(res, dict) and res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res


@router.post("/run")
def run_genetic_online(req: Optional[GeneticEvolutionRequest] = Body(None)):
    """在线手动触发遗传算法高精寻优并更新最新大屏推演"""
    pop = req.pop_size if req else 40
    gen = req.generations if req else 25
    eval_p = req.eval_periods if req else 15
    res = data_service.run_genetic_online(pop_size=pop, generations=gen, eval_periods=eval_p)
    if isinstance(res, dict) and res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res
