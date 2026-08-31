# -*- coding: utf-8 -*-
"""
K8-Quant Web Application FastAPI Server
现代化量化大屏后端 RESTful API 服务 (Modular Backend API)
"""
import os
import sys
import time
import json
import uuid
import asyncio
import subprocess
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 引入路径与服务层
from backend.utils.paths import get_project_root, get_frontend_dir, data_path, _ensure_project_path
_ensure_project_path()

try:
    from backend.api.data_service import QuantDataService
except ImportError:
    from web_app.data_service import QuantDataService

PROJ_DIR = get_project_root()

app = FastAPI(
    title="K8-Quant 智能量化决策终端 API",
    description="快乐8 极致暗黑赛博量化大屏后端 API 服务，支持全流程预测、80码全景矩阵、历史复盘与任务流式调度",
    version="5.1.0"
)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_service = QuantDataService(PROJ_DIR)

# 内存任务管理器（用于异步流水线任务与实时日志）
TASK_STORE: Dict[str, Dict[str, Any]] = {}

class ParamUpdateModel(BaseModel):
    EF: float = Field(..., ge=0.0, le=1.0, description="能量场 (蹭热度) 权重")
    RW: float = Field(..., ge=0.0, le=1.0, description="遗漏回补 (抓冷门) 权重")
    FO: float = Field(..., ge=0.0, le=1.0, description="周期特征 (找周期) 权重")

class DailyPointsSubmitModel(BaseModel):
    date: str = Field(..., description="目标日期 (YYYY-MM-DD)")
    period: str = Field(..., description="目标期号 (如 2026232)")
    points: str = Field(..., description="20个点位号码文本 (支持空格/逗号/连字符等)")
    overwrite: bool = Field(True, description="若期号已存在是否覆盖")
    auto_run: bool = Field(False, description="保存后是否自动触发下游全模块联动")


def find_script(script_subpath: str) -> str:
    """寻找待执行脚本路径，兼容 backend 子目录与根目录"""
    candidates = [
        os.path.join(PROJ_DIR, "backend", script_subpath),
        os.path.join(PROJ_DIR, script_subpath),
        os.path.join(PROJ_DIR, os.path.basename(script_subpath)),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return os.path.join(PROJ_DIR, script_subpath)


def run_script_task(task_id: str, script_relative: str, args: List[str] = None):
    """后台运行 Python 脚本并捕获实时日志"""
    TASK_STORE[task_id]["status"] = "RUNNING"
    TASK_STORE[task_id]["start_time"] = datetime.now().isoformat()
    script_path = find_script(script_relative)
    cmd = [sys.executable, script_path] + (args or [])
    
    try:
        proc = subprocess.Popen(
            cmd, cwd=PROJ_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace"
        )
        for line in iter(proc.stdout.readline, ''):
            clean_line = line.rstrip()
            if clean_line:
                timestamp = datetime.now().strftime("%H:%M:%S")
                TASK_STORE[task_id]["logs"].append(f"[{timestamp}] {clean_line}")
                if len(TASK_STORE[task_id]["logs"]) > 2000:
                    TASK_STORE[task_id]["logs"].pop(0)

        proc.stdout.close()
        return_code = proc.wait()
        TASK_STORE[task_id]["end_time"] = datetime.now().isoformat()
        if return_code == 0:
            TASK_STORE[task_id]["status"] = "SUCCESS"
            TASK_STORE[task_id]["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 任务执行成功并圆满完成！")
        else:
            TASK_STORE[task_id]["status"] = "FAILED"
            TASK_STORE[task_id]["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 任务执行异常结束，返回码: {return_code}")
    except Exception as e:
        TASK_STORE[task_id]["status"] = "ERROR"
        TASK_STORE[task_id]["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 捕获运行时异常: {str(e)}")


# ──────────────── API 路由 ────────────────

@app.get("/api/system/status")
def get_system_status():
    """获取系统健康度、版本与最新开奖信息"""
    return data_service.get_system_status()

@app.get("/api/quant/latest-prediction")
def get_latest_prediction():
    """获取最新一期的核心量化预测 (Top 5 / 12, 黄金搭档, 能量场, 雷达图)"""
    return data_service.get_latest_prediction()

@app.get("/api/quant/matrix-80")
def get_matrix_80():
    """获取 1-80 号码全景态势数据、热力图、尾数分布与分区占比"""
    return data_service.get_matrix_80_stats()

@app.get("/api/quant/number/{num}")
def get_number_detail(num: int):
    """获取单个号码近 30 期详细走势与搭档关联"""
    res = data_service.get_number_detail(num)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@app.get("/api/quant/history-trends")
def get_history_trends(limit: int = Query(30, ge=5, le=100)):
    """获取历史走势与模型命中率复盘曲线"""
    return data_service.get_history_trends(limit=limit)

@app.get("/api/quant/lottery-trends")
def get_lottery_trends(limit: int = Query(100, ge=5, le=1000, description="展示的历史期数，默认100期")):
    """获取开奖号码80码全景走势图数据 (按开奖日期升序排列)"""
    return data_service.get_lottery_trends(limit=limit)

@app.get("/api/quant/history-table")
def get_history_table(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    q: str = Query("", description="期号或日期检索")
):
    """获取历史开奖总库分页数据"""
    return data_service.get_history_paginated(page=page, page_size=page_size, period_query=q)

@app.get("/api/reports/list")
def get_reports_list():
    """获取历史每日研判报告列表"""
    return data_service.get_report_list()

@app.get("/api/reports/detail/{date_or_filename}")
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

@app.post("/api/pipeline/run")
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

@app.post("/api/pipeline/sync-data")
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


@app.get("/api/jingle/summary")
def get_jingle_summary():
    """获取顺口溜口诀最新预测、触发口诀明细与交叉风控打标"""
    return data_service.get_jingle_summary()

@app.get("/api/jingle/review")
def get_jingle_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期顺口溜口诀对账复盘流水与真·样本外分层指标"""
    return data_service.get_jingle_review(n=n)

@app.get("/api/jingle/rules")
def get_jingle_rules(
    kind: Optional[str] = Query(None, description="规则类型 (pair_pair/triple_single)"),
    keyword: Optional[str] = Query(None, description="号码或ID搜索关键字")
):
    """获取 90 条精英口诀规则清单与元数据"""
    return data_service.get_jingle_rules(kind=kind, keyword=keyword)

@app.post("/api/pipeline/run-jingle")
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

@app.get("/api/spatial-points/summary")
def get_spatial_points_summary():
    """获取空间重点点位最新预测、核心五码、精选十码、8区覆盖与多维交叉风控"""
    return data_service.get_spatial_points_summary()

@app.get("/api/spatial-points/matrix")
def get_spatial_points_matrix():
    """获取 80 点位全盘空间特征、得分、p值显著性与 4 维雷达数据"""
    return data_service.get_spatial_points_matrix()

@app.get("/api/spatial-points/review")
def get_spatial_points_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期重点点位 Walk-Forward 滚动样本外复盘对账流水与置信评定"""
    return data_service.get_spatial_points_review(n=n)

@app.post("/api/pipeline/run-spatial-points")
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


# ──────────────── 每日点位数据录入与管理 API ────────────────
@app.get("/api/daily-points/info")
def get_daily_points_info():
    """获取点位库当前状态、最新录入点位与推荐目标期信息"""
    return data_service.get_daily_points_info()

@app.get("/api/daily-points/history")
def get_daily_points_history(limit: int = Query(30, ge=5, le=100, description="获取记录条数")):
    """获取最近 N 期点位记录与历史开奖命中对账"""
    return data_service.get_daily_points_history(limit=limit)

@app.post("/api/daily-points/submit")
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
        from backend.data_acquisition.daily_points_manager import run_all_points_downstream
        threading.Thread(target=run_all_points_downstream, kwargs={"verbose": False}, daemon=True).start()

    return {
        "status": "ok",
        "message": f"期号 {payload.period} 点位已成功落盘！",
        "task_id": task_id,
        "data": res
    }

@app.post("/api/daily-points/sync-all")
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
    from backend.data_acquisition.daily_points_manager import run_all_points_downstream
    threading.Thread(target=run_all_points_downstream, kwargs={"verbose": False}, daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "点位全模块联动任务已在后台启动！"}



@app.get("/api/lstm/summary")
def get_lstm_summary():
    """获取双层LSTM深度学习最新预测、金银铜胆、Top10及近期实战对账"""
    return data_service.get_lstm_summary()

@app.get("/api/lstm/review")
def get_lstm_review(n: int = Query(15, ge=5, le=50, description="复盘期数")):
    """获取近 N 期双层LSTM历史实测复盘与对账明细"""
    return data_service.get_lstm_review(n=n)

@app.post("/api/pipeline/run-lstm")
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

@app.get("/api/lstm/reports")
def get_lstm_reports():
    """获取双层LSTM深度时序历史研报与预测文件列表"""
    return data_service.get_lstm_reports_list()

@app.get("/api/lstm/report-detail/{filename}")
def get_lstm_report_detail(filename: str):
    """获取指定双层LSTM研报或预测单的内容"""
    try:
        return data_service.get_lstm_report_detail(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到指定的 LSTM 研报文件")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/follow/summary")
def get_follow_summary():
    """获取跟随分析最新预测、重复号Top5、推演Top6、条件跟随Top8、共振交集与多维交叉打标"""
    return data_service.get_follow_summary()

@app.get("/api/follow/review")
def get_follow_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期跟随分析 Walk-Forward 滚动样本外对账流水与三路 Lift 指标"""
    return data_service.get_follow_review(n=n)

@app.get("/api/follow/conditions")
def get_follow_conditions():
    """获取最新上期 Top 5 黄金条件对、多时间窗口跟随明细与 >= 3 窗交集"""
    return data_service.get_follow_conditions()

@app.post("/api/pipeline/run-follow")
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

@app.get("/api/suppression/summary")
def get_suppression_summary():
    """获取未开点位高压反弹最新预测、Top3金胆、弹簧压制状态与多维交叉打标"""
    return data_service.get_suppression_summary()

@app.get("/api/suppression/review")
def get_suppression_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期未开点位反弹 Walk-Forward 滚动样本外对账流水与置信评定"""
    return data_service.get_suppression_review(n=n)

@app.get("/api/suppression/patterns")
def get_suppression_patterns():
    """获取未开点位历史模式：弹簧张力回补率、能量外溢漂移与影子替身伴生对"""
    return data_service.get_suppression_patterns()

@app.post("/api/pipeline/run-suppression")
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


# ──────────────── KillSeeker 杀号决策 API ────────────────

@app.get("/api/kill/summary")
def get_kill_summary():
    """获取 KillSeeker 最新一期核心杀号(高/中/低置信25码)、安全保留号、5大引擎贡献度及80码杀号态势"""
    res = data_service.get_kill_summary()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@app.get("/api/kill/review")
def get_kill_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期 KillSeeker 杀号 Walk-Forward 真实对账流水与统计指标"""
    return data_service.get_kill_review(n=n)

@app.get("/api/kill/logs")
def get_kill_logs():
    """获取 KillSeeker 历史控制面板研报清单"""
    return data_service.get_kill_logs_list()

@app.get("/api/kill/log-detail/{filename}")
def get_kill_log_detail(filename: str):
    """获取指定 KillSeeker 控制面板 Markdown 内容"""
    try:
        return data_service.get_kill_log_detail(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到指定的杀号研报")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pipeline/run-kill")
def trigger_kill_pipeline():
    """异步触发 KillSeeker 每日全流程杀号推演任务"""
    task_id = str(uuid.uuid4())[:8]
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "run_killseeker",
        "title": "⚔️ KillSeeker 杀号决策全流程推演任务",
        "status": "QUEUED",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] ⚔️ 正在启动 KillSeeker 低分杀号与五维反哺分析引擎..."]
    }
    script = "run_killseeker_daily.py"
    threading.Thread(target=run_script_task, args=(task_id, script, ["--full"]), daemon=True).start()
    return {"task_id": task_id, "status": "QUEUED", "message": "KillSeeker 杀号分析任务已在后台启动！"}


# ──────────────── Gemini 选2预测 API ────────────────

@app.get("/api/gemini/summary")
def get_gemini_summary():
    """获取 Gemini 选2最新核心预测(金银铜胆、核心4码、终极5码、铁血做空区、异象雷达)"""
    res = data_service.get_gemini_summary()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@app.get("/api/gemini/review")
def get_gemini_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期 Gemini 选2 Walk-Forward 样本外对账流水与统计指标"""
    return data_service.get_gemini_review(n=n)

@app.get("/api/gemini/history")
def get_gemini_history():
    """获取 Gemini 选2历史预测研报列表"""
    return data_service.get_gemini_history_list()

@app.get("/api/gemini/history-detail/{filename}")
def get_gemini_history_detail(filename: str):
    """获取指定 Gemini 选2预测研报内容"""
    try:
        return data_service.get_gemini_history_detail(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到指定的预测研报")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pipeline/run-gemini")
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


# ──────────────── 定金选2决策 API ────────────────

@app.get("/api/gold-pick2/summary")
def get_gold_pick2_summary():
    """获取定金选2最新核心预测(双重金胆、Top5黄金搭档配对、温号池、置信等级与交叉风控)"""
    res = data_service.get_gold_pick2_summary()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@app.get("/api/gold-pick2/review")
def get_gold_pick2_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期定金选2 Walk-Forward 样本外对账流水与统计指标"""
    return data_service.get_gold_pick2_review(n=n)

@app.get("/api/gold-pick2/matrix")
def get_gold_pick2_matrix():
    """获取定金选2 80 码 7 维特征打分与雷达态势数据"""
    return data_service.get_gold_pick2_matrix()

@app.get("/api/gold-pick2/logs")
def get_gold_pick2_logs():
    """获取定金选2历史研报清单"""
    return data_service.get_gold_pick2_history_list()

@app.get("/api/gold-pick2/log-detail/{filename}")
def get_gold_pick2_log_detail(filename: str):
    """获取指定定金选2预测研报内容"""
    try:
        return data_service.get_gold_pick2_history_detail(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到指定的定金选2研报")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pipeline/run-gold-pick2")
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


# ──────────────── 16期中热频次推演与组合决策 API ────────────────

@app.get("/api/sixteen/summary")
def get_sixteen_summary():
    """获取 16 期中热频次推演最新核心大屏数据 (核心指标、金银铜胆、Top 5 选2/选3组合、80码态势、1~8+分桶)"""
    res = data_service.get_sixteen_summary()
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res

@app.get("/api/sixteen/review")
def get_sixteen_review(n: int = Query(30, ge=5, le=100, description="复盘期数")):
    """获取近 N 期 16 期中热推演 Walk-Forward 滚动样本外对账流水与统计指标"""
    return data_service.get_sixteen_review(n=n)

@app.get("/api/sixteen/history")
def get_sixteen_history():
    """获取 16 期中热推演历史研报列表"""
    return data_service.get_sixteen_history_list()

@app.get("/api/sixteen/history-detail/{filename}")
def get_sixteen_history_detail(filename: str):
    """获取指定 16 期中热推演研报内容"""
    try:
        return data_service.get_sixteen_history_detail(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到指定的研报文件")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pipeline/run-sixteen")
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





@app.get("/api/pipeline/logs/{task_id}")
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

@app.get("/api/config/params")
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

@app.post("/api/config/params")
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

# ══════════════════════════════════════════════════════════
# 数据汇总复盘 (终审共识与8区平衡) 路由
# ══════════════════════════════════════════════════════════
@app.get("/api/aggregation/cockpit")
def get_aggregation_cockpit():
    """获取终审数据汇总复盘大屏数据"""
    try:
        return data_service.get_aggregation_cockpit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取终审复盘驾驶舱数据失败: {e}")

@app.get("/api/aggregation/history")
def get_aggregation_history():
    """获取历史汇总复盘报告列表"""
    try:
        return data_service.get_aggregation_history_list()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取汇总复盘历史失败: {e}")

@app.get("/api/aggregation/history/{filename}")
def get_aggregation_history_detail(filename: str):
    """读取指定汇总复盘报告内容"""
    try:
        return data_service.get_aggregation_history_detail(filename)
    except FileNotFoundError as fe:
        raise HTTPException(status_code=404, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取汇总复盘详情失败: {e}")

@app.post("/api/aggregation/run")
def trigger_aggregation_run(background_tasks: BackgroundTasks, force: bool = Query(True)):
    """一键触发后台执行终审数据汇总复盘"""
    task_id = f"task_agg_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    TASK_STORE[task_id] = {
        "id": task_id,
        "name": "终审共识与数据汇总复盘 (7路多维共振 + 8区空间平衡)",
        "script": "run_aggregation_daily.py",
        "status": "QUEUED",
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 任务已加入执行队列..."]
    }
    args = ["--force"] if force else []
    background_tasks.add_task(run_script_task, task_id, "run_aggregation_daily.py", args)
    return {"task_id": task_id, "status": "QUEUED", "message": "终审数据汇总复盘任务已成功派发！"}

# ══════════════════════════════════════════════════════════
# 每日自学习自动复盘总账本 & 全模块预测总览 API
# ══════════════════════════════════════════════════════════
@app.get("/api/reviews/ledger")
def get_reviews_ledger(limit: int = Query(50, ge=5, le=200, description="获取复盘期数")):
    """获取全量 47+ 期每日自学习自动复盘对账总账本与全局核心指标"""
    return data_service.get_daily_reviews_ledger(limit=limit)

@app.get("/api/reviews/detail/{period}")
def get_review_detail(period: str):
    """获取指定期号的详细复盘 JSON 数据"""
    try:
        return data_service.get_review_detail(period)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到第 {period} 期的复盘记录")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/quant/modules-overview")
def get_modules_prediction_overview():
    """获取最新一期 10 大子模块预测大盘全景快照"""
    return data_service.get_all_modules_prediction_overview()

@app.get("/favicon.ico")
def get_favicon():

    from fastapi import Response
    return Response(status_code=204)


# 挂载前端静态文件 (优先从 frontend/static 寻找)
STATIC_DIR = os.path.join(get_frontend_dir(), "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(PROJ_DIR, "web_app", "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    """提供 Web 端应用首页"""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>K8-Quant Web 正在初始化中...</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.api_server:app", host="127.0.0.1", port=8000, reload=True)
