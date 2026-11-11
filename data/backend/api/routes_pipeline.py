# -*- coding: utf-8 -*-
"""流水线任务触发与日志 API"""
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
router = APIRouter(prefix="/api/pipeline", tags=['pipeline'])

@router.post("/run")
def trigger_pipeline(background_tasks: BackgroundTasks):
    """一键触发每日量化全流程计算 (pipeline/run_full_pipeline.py)"""
    for tid, tinfo in TASK_STORE.items():
        if tinfo.get("status") == "RUNNING" and tinfo.get("name") == "run_full_pipeline":
            return {"task_id": tid, "status": "ALREADY_RUNNING", "message": "已有全流程预测任务正在执行中..."}

    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_full_pipeline",
        "title": "⚡ 全流程量化预测流水线",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 启动全流程量化预测任务..."]
    }
    script = os.path.join("pipeline", "run_full_pipeline.py")
    threading.Thread(target=run_script_task, args=(task_id, script), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "全流程计算任务已启动！"}

@router.post("/sync-data")
def trigger_sync_data():
    """触发历史数据抓取与同步"""
    for tid, tinfo in TASK_STORE.items():
        if tinfo.get("status") == "RUNNING" and tinfo.get("name") == "sync_data":
            return {"task_id": tid, "status": "ALREADY_RUNNING", "message": "数据同步任务正在执行中..."}

    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "sync_data",
        "title": "🔄 历史开奖数据同步任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 开始拉取最新开奖数据..."]
    }
    script = os.path.join("data_acquisition", "fetch_kl8_history.py")
    threading.Thread(target=run_script_task, args=(task_id, script), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "开奖数据同步任务已在后台启动！"}

@router.post("/run-jingle")
def trigger_jingle_pipeline():
    """异步触发顺口溜每日全流程口诀分析脚本"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_jingle",
        "title": "📜 顺口溜口诀全流程推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 📜 正在启动顺口溜口诀分析引擎..."]
    }
    script = "run_jingle_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["30"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "顺口溜分析任务已在后台启动！"}

@router.post("/run-spatial-points")
def trigger_spatial_points_pipeline():
    """异步触发空间重点点位每日全流程分析推演"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_spatial_points",
        "title": "🔮 空间重点点位全流程推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🔮 正在启动空间重点点位分析引擎..."]
    }
    script = "run_points_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["30"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "重点点位分析任务已在后台启动！"}

@router.post("/run-lstm")
def trigger_lstm_pipeline():
    """异步触发双层LSTM每日量化深度学习推演任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_lstm",
        "title": "🧠 双层LSTM深度学习推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 正在启动双层LSTM深度学习时序建模引擎..."]
    }
    script = "run_lstm_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["10"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "双层LSTM分析任务已在后台启动！"}

@router.post("/run-psychological-game")
def trigger_psychological_game_pipeline():
    """异步触发心理博弈与逆向均值回归每日全流程推演任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_psychological_game",
        "title": "🧠 心理博弈与逆向均值回归推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 正在启动心理博弈与逆向均值回归推演引擎..."]
    }
    script = "run_psychological_game_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "心理博弈推演任务已在后台启动！"}

@router.post("/run-psychological-game-backtest")
def trigger_psychological_game_backtest_pipeline():
    """异步触发心理博弈与逆向均值回归严格样本外滚动回测审计任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_psychological_game_backtest",
        "title": "📊 心理博弈样本外滚动回测审计任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 📊 正在启动心理博弈严格样本外滚动回测审计引擎..."]
    }
    script = "backend/audit/backtest_psychological_game_theory.py"
    threading.Thread(target=run_script_task, args=(task_id, script, []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "心理博弈回测审计任务已在后台启动！"}

@router.post("/run-prime-composite")
def trigger_prime_composite_pipeline():
    """异步触发质合数与尾数香农熵每日全流程推演任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_prime_composite",
        "title": "🧬 质合数与尾数香农熵推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🧬 正在启动质合数与尾数香农熵推演引擎..."]
    }
    script = "run_prime_composite_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "质合数推演任务已在后台启动！"}

@router.post("/run-follow")
def trigger_follow_pipeline():
    """异步触发跟随分析每日全流程推演任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_follow",
        "title": "🔗 跟随分析全流程推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🔗 正在启动跟随分析(重复号与多窗条件跟随)推演引擎..."]
    }
    script = "run_follow_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["30"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "跟随分析任务已在后台启动！"}

@router.post("/run-suppression")
def trigger_suppression_pipeline():
    """异步触发未开点位反弹追踪每日全流程推演任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_suppression",
        "title": "🪞 未开点位反弹追踪全流程推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🪞 正在启动未开点位高压反弹与影子替身推演引擎..."]
    }
    script = "run_suppression_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["30"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "未开点位反弹追踪任务已在后台启动！"}

@router.post("/run-point-omission")
def trigger_point_omission_pipeline():
    """异步触发点位+遗漏号每日全流程推演任务 (run_point_omission_daily.py)"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_point_omission",
        "title": "🎯 点位+遗漏号深度推演全套流水线",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🎯 正在启动点位+遗漏号深度分析推演引擎..."]
    }
    script = "run_point_omission_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["--no-fetch"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "点位+遗漏深度推演任务已在后台启动！"}



@router.post("/run-gemini")
def trigger_gemini_pipeline():
    """异步触发 Gemini 选2每日全流程推演分析"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_gemini",
        "title": "💎 Gemini 选2全流程推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 💎 正在启动 Gemini 选2 (5大算子与金银铜胆) 推演引擎..."]
    }
    script = "run_geminixuan2_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["30"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "Gemini 选2分析任务已在后台启动！"}

@router.post("/run-gold-pick2")
def trigger_gold_pick2_pipeline():
    """异步触发定金选2每日全流程推演任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_gold_pick2",
        "title": "💎 定金选2决策全流程推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 💎 正在启动定金选2 (双重金胆+7维评分+条件共现) 推演引擎..."]
    }
    script = "run_pick2_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["30"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "定金选2分析任务已在后台启动！"}

@router.post("/run-sixteen")
def trigger_sixteen_pipeline():
    """异步触发 16 期中热频次推演每日全流程推演任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_sixteen",
        "title": "🔥 16期中热频次推演全流程任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 正在启动 16 期大盘光谱与中热号出窗进窗推演引擎..."]
    }
    script = "run_sixteen_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["30"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "16期中热频次推演任务已在后台启动！"}

@router.post("/run-datasource")
def trigger_datasource_pipeline():
    """异步触发数据源1×2深层关联每日全流程推演任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_datasource",
        "title": "🧬 数据源1×2深层关联全流程推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🧬 正在启动数据源1×2深层关联推演引擎..."]
    }
    script = "run_datasource_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["30"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "数据源1×2深层关联分析任务已在后台启动！"}

@router.post("/run-tri-high")
def trigger_tri_high_pipeline():
    """异步触发三高×点位联动量化推演任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_tri_high",
        "title": "🧬 三高特征×每日点位深度共振推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🧬 正在启动三高特征×每日点位量化引擎..."]
    }
    script = "run_tri_high_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "三高×点位量化推演任务已在后台启动！"}

@router.get("/logs/{task_id}")
def get_pipeline_logs(task_id: str):
    """获取指定任务的实时日志与当前状态"""
    if task_id not in TASK_STORE:
        raise HTTPException(status_code=404, detail="未找到指定的任务")
    
    task_info = TASK_STORE[task_id]
    return {
        "task_id": task_id,
        "name": task_info.get("name"),
        "title": task_info.get("title"),
        "status": task_info.get("status"),
        "logs": task_info.get("logs", []),
        "start_time": task_info.get("start_time"),
        "end_time": task_info.get("end_time")
    }

@router.post("/run-master-review")
def trigger_master_review_pipeline(background_tasks: BackgroundTasks, n: int = Query(30, ge=5, le=100)):
    """异步触发全模块实战命中复盘对账任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "master_review",
        "title": "🏆 全模块多维实战命中复盘总决算任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🏆 正在启动全模块实战命中复盘对账引擎..."]
    }
    background_tasks.add_task(run_script_task, task_id, "run_master_review_daily.py", [str(n)])
    return {"task_id": task_id, "status": "QUEUED", "message": "全模块实战命中复盘任务已在后台启动！"}

@router.post("/run-evolution")
def trigger_evolution_pipeline(background_tasks: BackgroundTasks, n: int = Query(30, ge=5, le=100)):
    """异步触发跨模块元学习自动进化模型迭代"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "meta_evolution",
        "title": "🧬 跨模块元学习自动进化模型迭代任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🧬 正在启动元学习自动进化引擎..."]
    }
    background_tasks.add_task(run_script_task, task_id, "run_evolution_daily.py", [str(n)])
    return {"task_id": task_id, "status": "QUEUED", "message": "自动进化模型迭代任务已在后台启动！"}

@router.post("/run-nightly")
def trigger_nightly_pipeline(background_tasks: BackgroundTasks):
    """异步触发 22:00 夜间全自动流水线 (同步+复盘+进化+推演+研报)"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "nightly_pipeline",
        "title": "🌙 每天 22:00 夜间全自动闭环推演与自学习进化流水线",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🌙 正在启动夜间全自动流水线..."]
    }
    background_tasks.add_task(run_script_task, task_id, "run_nightly_daily.py", [])
    return {"task_id": task_id, "status": "QUEUED", "message": "夜间全自动闭环流水线已在后台启动！"}

@router.post("/run-unified-brain")
def trigger_unified_brain(background_tasks: BackgroundTasks):
    """异步触发全栈统一决策主脑解算"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "unified_brain",
        "title": "🧬 全栈统一决策主脑解算任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🧬 正在启动全栈统一决策主脑推演解算..."]
    }
    background_tasks.add_task(run_script_task, task_id, "run_unified_brain_daily.py", [])
    return {"task_id": task_id, "status": "QUEUED", "message": "全栈统一决策主脑推演已在后台启动！"}

@router.post("/run-linear-algebra")
def trigger_linear_algebra_pipeline():
    """异步触发第10战区 线性代数空间投影推演"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "linear_algebra",
        "title": "📐 线性代数空间投影量化推演",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 📐 正在启动线性代数空间投影量化推演任务..."]
    }
    threading.Thread(target=run_script_task, args=(task_id, "run_linear_algebra_daily.py", []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "线性代数推演已在后台启动！"}

@router.post("/run-random-forest")
def trigger_random_forest_pipeline():
    """异步触发随机森林号码预测推演"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "random_forest",
        "title": "🌲 随机森林号码预测推演",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🌲 正在启动随机森林号码预测任务..."]
    }
    threading.Thread(target=run_script_task, args=(task_id, "run_random_forest_daily.py", []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "随机森林号码预测已在后台启动！"}

@router.post("/run-dtw")
def trigger_dtw_pipeline():
    """异步触发第11战区 动态时间规整DTW推演"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "dtw_matching",
        "title": "🌊 动态时间规整 DTW 弹性走势推演",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🌊 正在启动 DTW 弹性走势推演任务..."]
    }
    threading.Thread(target=run_script_task, args=(task_id, "run_dtw_daily.py", []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "DTW推演已在后台启动！"}

@router.post("/run-transformer")
def trigger_transformer_pipeline():
    """异步触发第12战区 Transformer全局注意力推演"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "transformer_attention",
        "title": "🤖 Transformer 全局自注意力推演",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 正在启动 Transformer 全局注意力推演任务..."]
    }
    threading.Thread(target=run_script_task, args=(task_id, "run_transformer_daily.py", []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "Transformer推演已在后台启动！"}

@router.post("/run-matrix-profile")
def trigger_matrix_profile_pipeline():
    """异步触发第13战区 矩阵轮廓极速查重推演"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "matrix_profile",
        "title": "⚡ 矩阵轮廓 Matrix Profile 极速查重推演",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ 正在启动矩阵轮廓极速查重推演任务..."]
    }
    threading.Thread(target=run_script_task, args=(task_id, "run_matrix_profile_daily.py", []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "矩阵轮廓查重推演已在后台启动！"}

@router.post("/run-tda")
def trigger_tda_pipeline():
    """异步触发第14战区 拓扑数据分析TDA推演"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "tda_engine",
        "title": "🍩 拓扑数据分析 TDA 持续同调推演",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🍩 正在启动拓扑数据分析 TDA 推演任务..."]
    }
    threading.Thread(target=run_script_task, args=(task_id, "run_tda_daily.py", []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "TDA拓扑推演已在后台启动！"}

@router.post("/run-error-correction")
def trigger_error_correction_pipeline():
    """异步触发残差改错预测推演 (LightGBM 错题本纠偏)"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "error_correction",
        "title": "🧬 残差改错预测推演 (错题本纠偏)",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 🧬 正在启动残差改错预测任务..."]
    }
    threading.Thread(target=run_script_task, args=(task_id, "run_error_correction_daily.py", []), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "残差改错预测已在后台启动！"}





# 启动后台 22:00 定时调度线程

