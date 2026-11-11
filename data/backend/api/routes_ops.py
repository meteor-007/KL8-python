# -*- coding: utf-8 -*-
"""运维与跨切面 API"""
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
router = APIRouter(tags=['ops'])

@router.get("/api/system/status")
def get_system_status():
    """获取系统健康度、版本与最新开奖信息"""
    return data_service.get_system_status()

@router.get("/api/reports/list")
def get_reports_list():
    """获取历史每日研判报告列表"""
    return data_service.get_report_list()

@router.get("/api/reports/detail/{date_or_filename}")
def get_report_detail(date_or_filename: str):
    """获取指定日期的分析报告全文"""
    reports = data_service.get_report_list()
    target_report = None
    for r in reports:
        if r["raw_date"] == date_or_filename or r["filename"] == date_or_filename or r["date"] == date_or_filename:
            target_report = r
            break
    
    if not target_report or not os.path.exists(target_report["path"]):
        raise HTTPException(status_code=404, detail="未找到对应的分析报告")
    
    with open(target_report["path"], "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    return {
        "date": target_report["date"],
        "period": target_report["period"],
        "filename": target_report["filename"],
        "content": content
    }

@router.get("/api/daily-points/info")
def get_daily_points_info():
    """获取点位库当前状态、最新录入点位与推荐目标期信息"""
    return data_service.get_daily_points_info()

@router.get("/api/daily-points/history")
def get_daily_points_history(limit: int = Query(30, ge=5, le=100, description="获取记录条数")):
    """获取最近 N 期点位记录与历史开奖命中对账"""
    return data_service.get_daily_points_history(limit=limit)

@router.post("/api/daily-points/submit")
def submit_daily_points(payload: DailyPointsSubmitModel, background_tasks: BackgroundTasks):
    """提交录入今日 20 个点位数据并执行全量特征画像，可选自动触发下游全模块联动"""
    res = data_service.submit_daily_points(
        date_str=payload.date,
        period_str=payload.period,
        raw_points=payload.points,
        overwrite=payload.overwrite
    )
    if res.get("status") != "ok":
        raise HTTPException(status_code=400, detail=res.get("message", "点位录入校验失败"))
        
    task_id = None
    if payload.auto_run:
        task_id = str(uuid.uuid4())[:8]
        TASK_STORE[task_id] = {
            "id": task_id,
            "name": "daily_points_sync",
            "title": f"🚀 目标期 {payload.period} 点位联动全模块计算",
            "status": "QUEUED",
            "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 点位落盘成功，正在启动下游全模块联动计算..."]
        }
        threading.Thread(target=run_points_downstream_task, args=(task_id,), daemon=True).start()

    return {
        "status": "ok",
        "message": f"期号 {payload.period} 点位已成功落盘！",
        "task_id": task_id,
        "data": res
    }

@router.post("/api/daily-points/sync-all")
def trigger_daily_points_sync():
    """异步触发点位下游全模块联动 (热码加权 + 格式上色 + 空间点位 + 未开反弹)"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "daily_points_sync",
        "title": "🚀 点位下游全模块联动任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 正在启动下游全模块联动计算..."]
    }
    threading.Thread(target=run_points_downstream_task, args=(task_id,), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "点位全模块联动任务已在后台启动！"}

@router.get("/api/config/params")
def get_config_params():
    """读取当前量化模型的参数与权重配置"""
    param_file = data_path("param_store.json")
    default_params = {
        "weights": {"EF": 0.40, "RW": 0.30, "FO": 0.30},
        "description": "EF (蹭热度: 0.40) + RW (抓冷门: 0.30) + FO (找周期: 0.30)",
        "circuit_breaker_kl_threshold": 0.15,
        "beacon_warning_threshold": 0.50,
        "last_updated": datetime.now().isoformat()
    }
    if os.path.exists(param_file):
        try:
            with open(param_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            return default_params
    return default_params

@router.post("/api/config/params")
def update_config_params(payload: ParamUpdateModel):
    """动态更新模型权重参数"""
    total = payload.EF + payload.RW + payload.FO
    if not (0.95 <= total <= 1.05):
        raise HTTPException(status_code=400, detail=f"三维权重之和必须约为 1.0 (当前总和: {total:.3f})")

    param_file = data_path("param_store.json")
    data = {
        "weights": {"EF": round(payload.EF, 3), "RW": round(payload.RW, 3), "FO": round(payload.FO, 3)},
        "description": f"EF (蹭热度: {payload.EF:.2f}) + RW (抓冷门: {payload.RW:.2f}) + FO (找周期: {payload.FO:.2f})",
        "circuit_breaker_kl_threshold": 0.15,
        "beacon_warning_threshold": 0.50,
        "last_updated": datetime.now().isoformat()
    }
    try:
        with open(param_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"status": "SUCCESS", "message": "权重参数已成功保存并生效！", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入参数文件失败: {e}")

@router.get("/api/modules/registry")
def get_modules_registry():
    """模块投票权登记册 (B包): 谁有投票权/谁在观察/谁已退役, 及各自权重与理由"""
    return data_service.get_module_gate_registry()

@router.get("/api/health/freshness")
def get_health_freshness():
    """数据新鲜度探针 (E5): 各关键产出最新到哪一期、落后几期、是停更还是人为退役"""
    return data_service.get_data_freshness()

@router.get("/api/advisor/weekly")
def get_weekly_advice():
    """每周权重调整建议 (C4): 只出建议不改参数, 需要人工 --apply 才生效"""
    try:
        from core.weekly_advisor import build_weekly_advice
        return build_weekly_advice(data_service.proj_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/unified-audit/latest")
def get_unified_audit_latest():
    """统一对账最新快照（只读）"""
    try:
        from backend.modules.unified_audit.ledger import load_latest
        row = load_latest(PROJ_DIR)
        if not row:
            return {"status": "empty", "row": None}
        return {"status": "ok", "row": row}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/unified-audit/ledger")
def get_unified_audit_ledger(limit: int = Query(30, ge=1, le=200)):
    """统一对账账本最近 N 条（只读）"""
    try:
        from backend.modules.unified_audit.ledger import load_all
        rows = load_all(PROJ_DIR)
        return {"status": "ok", "n": len(rows), "rows": rows[-limit:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

