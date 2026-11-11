# -*- coding: utf-8 -*-
"""Shared dependencies for FastAPI route modules."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import Dict, List, Any

from pydantic import BaseModel, Field

from backend.utils.paths import (
    get_project_root,
    get_python_runner,
    find_module_script,
    data_path,
    _ensure_project_path,
)

_ensure_project_path()

try:
    from backend.api.data_service import QuantDataService
except ImportError:
    from web_app.data_service import QuantDataService

PROJ_DIR = get_project_root()

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
    """寻找待执行脚本：优先 backend/modules/*/run_daily.py，兼容旧根目录路径。"""
    return find_module_script(script_subpath)


def run_script_task(task_id: str, script_relative: str, args: List[str] = None):
    """后台运行 Python 脚本并捕获实时日志"""
    TASK_STORE[task_id]["status"] = "RUNNING"
    TASK_STORE[task_id]["start_time"] = datetime.now().isoformat()
    script_path = find_script(script_relative)
    python_runner = get_python_runner()
    cmd = [python_runner, "-u", script_path] + (args or [])

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # 子进程直接执行 backend/... 脚本时，保证项目根在 import 路径上
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = PROJ_DIR + (os.pathsep + prev if prev else "")

    try:
        proc = subprocess.Popen(
            cmd, cwd=PROJ_DIR, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1
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
            TASK_STORE[task_id]["logs"].append(
                f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 任务执行成功并圆满完成！"
            )
        else:
            TASK_STORE[task_id]["status"] = "FAILED"
            TASK_STORE[task_id]["logs"].append(
                f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 任务执行异常结束，返回码: {return_code}"
            )
    except Exception as e:
        TASK_STORE[task_id]["status"] = "ERROR"
        TASK_STORE[task_id]["logs"].append(
            f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 捕获运行时异常: {str(e)}"
        )


def run_points_downstream_task(task_id: str):
    """
    顺序执行点位依赖下游模块，实时流式输出执行进度与详细控制台日志
    1. 热码统计生成 (generate_hot_excel.py)
    2. 热码写入跟随号码统计 (process_hot_numbers.py)  ← 数据源矩阵期号真源
    3. Excel点位格式同步 (apply_formats.py)
    4. 空间重点点位分析 (run_points_daily.py 30)
    5. 未开点位高压反弹 (run_suppression_daily.py 30)
    6. 点位+遗漏深度推演 (run_point_omission_daily.py)
    7. 16期中热操盘简报 (run_sixteen_daily.py)
    """
    TASK_STORE[task_id]["status"] = "RUNNING"
    TASK_STORE[task_id]["start_time"] = datetime.now().isoformat()
    python_runner = get_python_runner()

    steps = [
        ("【1/7】🔥 热码统计表生成 (generate_hot_excel.py)", "data_acquisition/generate_hot_excel.py", []),
        ("【2/7】🧬 热码写入跟随号码统计 (process_hot_numbers.py)", "data_acquisition/process_hot_numbers.py", ["--sync-all-missing"]),
        ("【3/7】📊 Excel 点位底色与中奖边框同步 (apply_formats.py)", "format/apply_formats.py", []),
        ("【4/7】🔮 空间重点点位分析与精排 (run_points_daily.py)", "run_points_daily.py", ["30"]),
        ("【5/7】🪞 未开点位高压反弹与影子替身 (run_suppression_daily.py)", "run_suppression_daily.py", ["30"]),
        ("【6/7】🎯 点位+遗漏号深度推演与5+2策略 (run_point_omission_daily.py)", "run_point_omission_daily.py", ["--no-fetch", "--no-backtest"]),
        ("【7/7】🔥 16期中热操盘简报 (run_sixteen_daily.py)", "run_sixteen_daily.py", ["--quiet"]),
    ]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = PROJ_DIR + (os.pathsep + prev if prev else "")

    overall_success = True

    for idx, (title, script_rel, args) in enumerate(steps, 1):
        ts = datetime.now().strftime("%H:%M:%S")
        TASK_STORE[task_id]["logs"].append(f"[{ts}] ----------------------------------------------------")
        TASK_STORE[task_id]["logs"].append(f"[{ts}] 🚀 正在执行进度 ({idx}/7): {title} ...")

        script_path = find_script(script_rel)
        if not os.path.exists(script_path):
            TASK_STORE[task_id]["logs"].append(f"[{ts}] ⚠️ 脚本文件未找到: {script_path}，跳过此步")
            continue

        cmd = [python_runner, "-u", script_path] + args
        try:
            proc = subprocess.Popen(
                cmd, cwd=PROJ_DIR, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1
            )
            for line in iter(proc.stdout.readline, ''):
                clean_line = line.rstrip()
                if clean_line:
                    now_ts = datetime.now().strftime("%H:%M:%S")
                    TASK_STORE[task_id]["logs"].append(f"[{now_ts}] {clean_line}")
                    if len(TASK_STORE[task_id]["logs"]) > 2500:
                        TASK_STORE[task_id]["logs"].pop(0)

            proc.stdout.close()
            return_code = proc.wait()
            end_ts = datetime.now().strftime("%H:%M:%S")
            if return_code == 0:
                TASK_STORE[task_id]["logs"].append(f"[{end_ts}] ✅ {title} 执行成功！")
            else:
                TASK_STORE[task_id]["logs"].append(f"[{end_ts}] ⚠️ {title} 执行退出 (返回码: {return_code})")
                overall_success = False
        except Exception as e:
            overall_success = False
            now_ts = datetime.now().strftime("%H:%M:%S")
            TASK_STORE[task_id]["logs"].append(f"[{now_ts}] ❌ {title} 运行时异常: {e}")

    TASK_STORE[task_id]["end_time"] = datetime.now().isoformat()
    final_ts = datetime.now().strftime("%H:%M:%S")
    TASK_STORE[task_id]["logs"].append(f"[{final_ts}] ====================================================")
    TASK_STORE[task_id]["status"] = "SUCCESS"
    if overall_success:
        TASK_STORE[task_id]["logs"].append(
            f"[{final_ts}] 🎉 点位下游全模块联动计算圆满完成！数据已实时生效并刷新。"
        )
    else:
        TASK_STORE[task_id]["logs"].append(
            f"[{final_ts}] ⚠️ 点位下游全模块联动计算已结束（部分步骤有警告），请查看上方日志。"
        )
