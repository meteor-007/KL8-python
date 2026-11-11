# -*- coding: utf-8 -*-
"""量化核心 /api/quant API"""
from __future__ import annotations

import os
import json
import time
import uuid
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Body
from fastapi.responses import JSONResponse

from backend.api.deps import (
    data_service,
    TASK_STORE,
    find_script,
    run_script_task,
    run_points_downstream_task,
    ParamUpdateModel,
    DailyPointsSubmitModel,
    PROJ_DIR,
    data_path,
)

logger = logging.getLogger("k8quant.api")
router = APIRouter(prefix="/api/quant", tags=['quant'])

@router.get("/latest-prediction")
def get_latest_prediction():
    """获取最新一期的核心量化预测 (Top 5 / 12, 黄金搭档, 能量场, 雷达图)"""
    return data_service.get_latest_prediction()

@router.get("/matrix-80")
def get_matrix_80():
    """获取 1-80 号码全景态势数据、热力图、尾数分布与分区占比"""
    return data_service.get_matrix_80_stats()

@router.get("/hit-leaderboard")
def get_hit_leaderboard(n: int = Query(10, ge=5, le=40, description="回看的已开奖期数")):
    """获取跨模块每日命中热力榜：各预测模块 Walk-Forward 命中率，按命中率排序"""
    return data_service.get_hit_leaderboard(n=n)

@router.get("/number/{num}")
def get_number_detail(num: int):
    """获取单个号码近 30 期详细走势与搭档关联"""
    res = data_service.get_number_detail(num)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.get("/history-trends")
def get_history_trends(limit: int = Query(30, ge=5, le=100)):
    """获取历史走势与模型命中率复盘曲线"""
    return data_service.get_history_trends(limit=limit)

@router.get("/lottery-trends")
def get_lottery_trends(limit: int = Query(100, ge=5, le=1000, description="展示的历史期数，默认100期")):
    """获取开奖号码80码全景走势图数据 (按开奖日期升序排列)"""
    return data_service.get_lottery_trends(limit=limit)

@router.get("/history-table")
def get_history_table(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    q: str = Query("", description="期号或日期检索")
):
    """获取历史开奖总库分页数据"""
    return data_service.get_history_paginated(page=page, page_size=page_size, period_query=q)

@router.get("/prime-composite-analysis")
def get_prime_composite_analysis(refresh: bool = Query(False, description="是否强制重新计算")):
    """获取质数合数与尾数香农熵量化推演数据 (方案二、三、四三合一)"""
    return data_service.get_prime_composite_analysis(force_refresh=refresh)

@router.get("/psychological-game-analysis")
def get_psychological_game_analysis(refresh: bool = Query(False, description="是否强制重新计算")):
    """获取心理博弈论与逆向均值回归量化推演数据 (四支柱融合)"""
    return data_service.get_psychological_game_analysis(force_refresh=refresh)

@router.get("/psychological-game-backtest")
def get_psychological_game_backtest(refresh: bool = Query(False, description="是否强制重新回测")):
    """获取心理博弈论与逆向均值回归严格样本外滚动回测数据 (多周期汇总与近100期明细)"""
    return data_service.get_psychological_game_backtest(force_refresh=refresh)

@router.get("/modules-overview")
def get_modules_prediction_overview():
    """获取最新一期 10 大子模块预测大盘全景快照"""
    return data_service.get_all_modules_prediction_overview()

@router.get("/ai-math-consensus/review")
@router.get("/modules-overview/review")
def get_ai_math_consensus_review(n: int = Query(30, ge=5, le=100, description="复盘期数"), force_refresh: bool = False):
    """获取六大前沿数学与AI模型超级共识近 N 期样本外逐期实测复盘明细与命中对账"""
    from backend.modules.common_ai_review import compute_consensus_rolling_review
    res = compute_consensus_rolling_review(n=n, force_refresh=force_refresh)
    if isinstance(res, dict) and res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res


@router.get("/meta-gold")
def get_meta_gold():
    """获取 Meta-Gold 至尊金胆超级共识熔炉数据"""
    res = data_service.get_meta_gold_summary()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@router.get("/meta-gold/review")
def get_meta_gold_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取 Meta-Gold 近 N 期样本外逐期实测复盘明细与提升度对账"""
    return data_service.get_meta_gold_review(n=n)

@router.get("/funnel-pipeline")
def get_funnel_pipeline():
    """获取三级漏斗全链路清洗流水线 (25码海选 ➔ 18码纯净池 ➔ 5码精选 ➔ 2码黄金配对)"""
    return data_service.get_funnel_pipeline_summary()

@router.get("/funnel-pipeline/review")
def get_funnel_pipeline_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取三级漏斗全链路近 N 期样本外逐期实测清洗与命中对账总账"""
    return data_service.get_funnel_pipeline_review(n=n)

@router.get("/environment-regime")
def get_environment_regime():
    """获取宏观大环境与变盘监控雷达数据 (5类市场态势识别与 KL 散度漂移)"""
    return data_service.get_environment_regime_summary()

@router.get("/fdr-audit")
def get_fdr_audit(n: int = Query(100, ge=5, le=200, description="审计期数 (C3: 默认100期, 30期样本不足)")):
    """获取严谨统计信标与 FDR-BH 多重检验显著性审计总表"""
    return data_service.get_fdr_audit_summary(n=n)

@router.get("/paper-trading")
def get_paper_trading(rolling: int = Query(30, ge=5, le=100, description="滚动期数")):
    """获取模拟盘实战资金净值走势、累计 ROI 与逐期对账台账"""
    res = data_service.get_paper_trading_summary(rolling=rolling)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res


@router.get("/alerts")
def get_alerts(limit: int = Query(20, ge=1, le=200, description="返回条数"),
               level: str = Query(None, description="按等级过滤: info/warn/error/critical")):
    """获取系统告警记录 (2026-10-22 新增: 夜间流水线停摆一个月无人知晓的补救)。

    数据源为 storage/alerts/alerts.jsonl，由 backend.utils.alerting 统一写入。
    """
    try:
        from backend.utils.alerting import read_recent_alerts, format_diagnostic
        return {
            "status": "ok",
            "total_returned": limit,
            "level_filter": level,
            "channels": format_diagnostic(),
            "items": read_recent_alerts(limit=limit, level=level),
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "items": []}


@router.get("/nightly-health")
def get_nightly_health(stale_hours: float = Query(26.0, ge=1, le=720,
                                                  description="多少小时无成功即判停摆")):
    """夜间流水线健康度体检 (只读诊断，不触发告警)。"""
    try:
        from backend.utils.nightly_watchdog import check_nightly_health
        return {"status": "ok", **check_nightly_health(stale_hours=stale_hours)}
    except Exception as e:
        return {"status": "error", "message": str(e), "healthy": None}


@router.get("/module-consensus")
def get_module_consensus():
    """全模块当期预测票共识叠加数据 (开奖走势图按模块上色用, 2026-10-22 新增)。

    返回目标期各现役模块真实录入的号码 + 每模块历史前瞻账水位 (Lift/CI/p/BH-q)，
    数据与「全模块看板」同源 (前瞻账 paper_trading_modules.jsonl)。
    """
    try:
        return data_service.get_module_consensus_overlay()
    except Exception as e:
        logger.exception("获取全模块共识叠加数据失败")
        return {"status": "error", "message": str(e), "modules": [], "consensus": {}}

