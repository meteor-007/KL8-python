# -*- coding: utf-8 -*-
"""
KL8 每日全流程调度 PWA 后端 v3.0
==================================
v3.0 重构（一键全自动流水线，替代原 6 步手动流程）：
  1. 单一「一键执行」入口：按用户指定顺序全自动顺序执行 9 个子系统
     （data → 双层LSTM → 顺口溜 → 重点点位分析 → 定金选2-分析 →
      KillSeeker → 点位期数-追踪 → gemini选2-预测 → 数据汇总复盘），
     前一系统完成后自动启动下一系统（各系统有前序依赖链）。
  2. 每个子系统：前置命令 → 主命令 → 后置命令，执行完成后自动检测并
     记录其生成的预测结果文件（sub_outputs 事件实时推送）。
  3. 每个子系统独立日志通道（sub_log）/ 状态（sub_status）实时 SSE 推送，
     支持日志、异常、进度实时监控；一键停止（kill 当前子进程树）。
  4. 每日幂等校验集成：所有子进程注入 KL8_NON_INTERACTIVE=1（今日已执行
     默认跳过），一键执行带「强制重跑」开关时注入 KL8_FORCE_RERUN=1。
  5. 保留：SSE 实时推送、PYTHONUNBUFFERED 无缓冲、9 个预测解析器、
     跨系统共识分析、预测结果汇总一键复制/导出。
"""
import os
import sys
import json
import time
import uuid
import queue
import threading
import subprocess
import re
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, Response

# ── 项目根目录（由本文件位置推导，兼容任意盘符/目录迁移）──
BASE_DIR = Path(__file__).resolve().parent.parent

app = Flask(__name__,
            template_folder=str(Path(__file__).parent / "templates"),
            static_folder=str(Path(__file__).parent / "static"))

# ── 全局状态 ──
sessions = {}
logs_lock = threading.Lock()      # 保护日志追加（append_log / append_sub_log）
sessions_lock = threading.Lock()  # 保护 sessions 字典（创建/淘汰）
sse_lock = threading.Lock()       # 保护各会话的 sse_queues（SSE 并发读写）

# ── 会话生命周期上限 ──
MAX_SESSIONS = 50          # 会话数上限，超出后淘汰最久未使用的会话
MAX_LOG_LINES = 2000       # 每步/每子系统日志行数上限，超出丢弃最旧行

# ── 访问控制：简单共享 Token 鉴权 ──
# 配置方式：环境变量 TOKEN（推荐），或 kl8-pwa/token.txt 文件（一行内容）。
# 未配置 TOKEN 时保持完全开放（兼容旧部署）；配置后所有 /api/ 请求需携带令牌，
# 请求头 X-Api-Token 或 URL 参数 token 二选一（SSE 因 EventSource 无法自定义头，走 URL 参数）。
TOKEN = os.environ.get("TOKEN", "").strip()
if not TOKEN:
    _token_file = Path(__file__).parent / "token.txt"
    if _token_file.exists():
        TOKEN = _token_file.read_text(encoding="utf-8").strip()


class SessionState:
    """每个浏览器会话的执行状态"""
    def __init__(self, session_id):
        self.session_id = session_id
        self.created_at = datetime.now().isoformat()
        self.last_active = time.time()   # 最近访问时间戳（会话淘汰依据）
        self.current_step = 0
        self.step_status = {}          # step -> 'pending'|'running'|'done'|'error'
        self.logs = {}                 # step -> [ {ts, msg, source?}, ... ]
        self.results = {}              # step -> result summary
        self.points_input = ""
        self.gemini_input = ""
        self.subsystem_status = {}     # sub_id -> 'pending'|'running'|'done'|'error'|'skipped'
        self.subsystem_logs = {}       # sub_id -> [ {ts, msg}, ... ]
        self.step_progress = {}        # step -> {current, total, label}
        self.step_start_time = {}      # step -> timestamp
        self.sub_start_time = {}       # sub_id -> timestamp
        # v3.0 流水线状态
        self.pipeline_status = "idle"  # idle|running|done|error|stopped
        self.pipeline_start_time = None  # 流水线启动时间戳
        self.system_outputs = {}       # sub_id -> [生成的预测结果文件, ...]
        self.stop_requested = False    # 停止流水线标记（停止后当前子进程被杀、后续系统跳过）
        self.current_proc = None       # 当前正在运行的子进程（用于一键停止）
        self.force = False             # 是否强制重跑（KL8_FORCE_RERUN=1）
        # SSE 事件队列
        self.sse_queues = []           # list of queue.Queue for SSE clients

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "current_step": self.current_step,
            "step_status": self.step_status,
            "results": self.results,
            "points_input": self.points_input,
            "gemini_input": self.gemini_input[:200] if self.gemini_input else "",
            "subsystem_status": self.subsystem_status,
            "step_progress": self.step_progress,
            "pipeline_status": self.pipeline_status,
            "force": self.force,
            "system_outputs": self.system_outputs,
            "pipeline_elapsed": round(time.time() - self.pipeline_start_time, 1)
                if self.pipeline_status == "running" and self.pipeline_start_time else 0,
            "step_elapsed": {
                # 注意：step_start_time 与 step_status 的键统一为字符串（str(step)），
                # 修复原先 int/str 键不一致导致 step_status.get(int) 恒 None、计时器永远 0.0s 的问题
                str(k): round(time.time() - v, 1)
                for k, v in self.step_start_time.items()
                if self.step_status.get(str(k)) == 'running'
            },
            "sub_elapsed": {
                k: round(time.time() - v, 1)
                for k, v in self.sub_start_time.items()
                if self.subsystem_status.get(k) == 'running'
            },
            "created_at": self.created_at,
        }

    def emit_event(self, event_type, data):
        """向所有SSE客户端推送事件（sse_queues 受 sse_lock 保护，防并发 append/remove/iterate）"""
        event = {"type": event_type, "data": data, "ts": datetime.now().strftime("%H:%M:%S")}
        with sse_lock:
            for q in list(self.sse_queues):
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass


def _evict_oldest_session():
    """会话数达上限时，淘汰最久未使用的会话（防内存无限累积）"""
    if not sessions:
        return
    oldest_sid = min(sessions, key=lambda s: sessions[s].last_active)
    del sessions[oldest_sid]
    print(f"[会话管理] 会话数达上限({MAX_SESSIONS})，已淘汰最久未使用会话: {oldest_sid}")


def get_or_create_session(session_id=None):
    with sessions_lock:
        if session_id and session_id in sessions:
            sessions[session_id].last_active = time.time()
            return sessions[session_id]
        sid = session_id or str(uuid.uuid4())[:8]
        # 会话上限：超出后淘汰最久未使用的会话
        if len(sessions) >= MAX_SESSIONS:
            _evict_oldest_session()
        state = SessionState(sid)
        sessions[sid] = state
        state.last_active = time.time()
        return state


def append_log(state, step, msg, source=None):
    """线程安全地追加日志，并推送SSE事件（每步日志行数上限 MAX_LOG_LINES，超出丢弃最旧行）"""
    with logs_lock:
        if step not in state.logs:
            state.logs[step] = []
        entry = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "msg": msg,
            "source": source or ""
        }
        state.logs[step].append(entry)
        if len(state.logs[step]) > MAX_LOG_LINES:
            state.logs[step] = state.logs[step][-MAX_LOG_LINES:]
    # 推送SSE
    state.emit_event("log", {"step": step, "ts": entry["ts"], "msg": msg, "source": source or ""})


def append_sub_log(state, sub_id, msg):
    """子系统独立日志（每子系统日志行数上限 MAX_LOG_LINES，超出丢弃最旧行）"""
    with logs_lock:
        if sub_id not in state.subsystem_logs:
            state.subsystem_logs[sub_id] = []
        entry = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "msg": msg
        }
        state.subsystem_logs[sub_id].append(entry)
        if len(state.subsystem_logs[sub_id]) > MAX_LOG_LINES:
            state.subsystem_logs[sub_id] = state.subsystem_logs[sub_id][-MAX_LOG_LINES:]
    # 推送SSE
    state.emit_event("sub_log", {"sub_id": sub_id, "ts": entry["ts"], "msg": msg})


def update_step_progress(state, step, current, total, label=""):
    """更新步骤进度"""
    state.step_progress[str(step)] = {"current": current, "total": total, "label": label}
    state.emit_event("progress", {"step": step, "current": current, "total": total, "label": label})


def update_sub_status(state, sub_id, status):
    """更新子系统状态并推送（v3.0 新增 'skipped'：每日幂等校验今日已执行默认跳过）"""
    state.subsystem_status[sub_id] = status
    if status == "running":
        state.sub_start_time[sub_id] = time.time()
    elif status in ("done", "error", "skipped"):
        state.sub_start_time.pop(sub_id, None)
    state.emit_event("sub_status", {"sub_id": sub_id, "status": status})


# ═══════════════════════════════════════════════════════════
# 核心改进：无缓冲流式执行
# ═══════════════════════════════════════════════════════════

def _kill_process_tree(proc):
    """Windows 下强制结束整棵进程树。
    shell=True 时 Popen 拉起的是 cmd.exe，cmd.exe 会再拉起真正的子进程，
    只杀 cmd.exe 不够，必须用 taskkill /F /T 结束进程树。"""
    try:
        # /T 结束进程树，/F 强制结束
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _drain_stdout(state, step, proc, output_lines, source=None, sub_id=None):
    """后台线程：持续读取子进程 stdout 并转发到日志（可选同时写子系统日志）。
    关键：让主线程的 proc.wait(timeout=...) 才能真正生效——
    原先在主线程 for line in proc.stdout 会阻塞读到进程退出，超时永不触发。"""
    try:
        for line in proc.stdout:
            ls = line.rstrip()
            if ls:
                output_lines.append(ls)
                append_log(state, step, ls, source=source)
                if sub_id is not None:
                    append_sub_log(state, sub_id, ls)
    except Exception:
        pass


def _run_single_cmd(state, step, sub_id, sub_name, sub_dir, label, cmd, timeout, force=False, target_date=None):
    """执行单条命令，返回 (success, elapsed, output_lines)。
    v3.0: 统一注入 KL8_NON_INTERACTIVE=1（每日幂等校验：今日已执行默认跳过），
    force=True 时额外注入 KL8_FORCE_RERUN=1（强制重跑）；执行期间把子进程登记到
    state.current_proc，供「一键停止」结束整棵进程树。
    v3.1: target_date=YYYY-MM-DD 时注入 KL8_TARGET_DATE（PWA 批量补跑历史日期，
    让 daily_run_guard 按目标日期而非真实今天做幂等校验）。"""
    env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "KL8_NON_INTERACTIVE": "1",
    }
    if force:
        env["KL8_FORCE_RERUN"] = "1"
    if target_date:
        env["KL8_TARGET_DATE"] = target_date
    start = time.time()
    try:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=str(sub_dir),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace',
            env=env, bufsize=1,
        )
        state.current_proc = proc  # 登记当前子进程（一键停止用）
        output_lines = []
        # 读取线程转发日志；主线程 wait(timeout) 负责超时（与 run_command_streaming 同一修复策略）
        reader = threading.Thread(target=_drain_stdout,
                                  args=(state, step, proc, output_lines),
                                  kwargs={"source": sub_id, "sub_id": sub_id}, daemon=True)
        reader.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # 超时：强制结束整棵进程树，并记录超时日志
            _kill_process_tree(proc)
            reader.join(timeout=5)
            elapsed = time.time() - start
            append_sub_log(state, sub_id, f"  ⚠️ [{label}] 超时 ({timeout}s)，已强制结束进程树")
            append_log(state, step, f"⚠ [{label}] 超时({timeout}s)，已强制结束进程树 (taskkill /F /T /PID {proc.pid})", source=sub_id)
            return False, elapsed, output_lines
        elapsed = time.time() - start
        if proc.returncode == 0:
            append_sub_log(state, sub_id, f"  ✅ [{label}] 完成 ({elapsed:.1f}s)")
            return True, elapsed, output_lines
        else:
            append_sub_log(state, sub_id, f"  ⚠️ [{label}] 退出码 {proc.returncode} ({elapsed:.1f}s)")
            return False, elapsed, output_lines
    except Exception as e:
        append_sub_log(state, sub_id, f"  ⚠️ [{label}] 报错: {e}")
        return False, time.time() - start, []
    finally:
        # 命令结束（正常/超时/异常）后清除当前进程登记
        try:
            if state.current_proc is not None and state.current_proc.poll() is not None:
                state.current_proc = None
        except Exception:
            state.current_proc = None


# ═══════════════════════════════════════════════════════════
# v3.0 全自动流水线：9 个子系统按用户指定顺序执行
# ═══════════════════════════════════════════════════════════
def read_latest_daily_points():
    dp_file = BASE_DIR / "data" / "daily_points.txt"
    if not dp_file.exists():
        return {"error": "daily_points.txt 不存在"}
    try:
        with open(dp_file, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        if not first_line:
            return {"error": "daily_points.txt 为空"}
        return {"raw": first_line, "parsed": parse_daily_points_line(first_line)}
    except Exception as e:
        return {"error": str(e)}


def parse_daily_points_line(line):
    parts = {}
    for seg in line.split(','):
        if ':' in seg:
            k, v = seg.split(':', 1)
            parts[k.strip()] = v.strip()
    return {
        "date": parts.get("date", ""),
        "period": parts.get("period", ""),
        "points": parts.get("points", "")
    }


# ═══════════════════════════════════════════════════════════
# v3.0 全自动流水线：9 个子系统按用户指定顺序执行
# ═══════════════════════════════════════════════════════════
# 每个子系统：前置命令(pre_cmds) → 主命令(cmd) → 后置命令(post_cmds)；
# 主命令执行完成后自动检测 outputs（glob 模式，相对项目根）并记录生成的预测结果文件。
# 所有子进程统一注入 KL8_NON_INTERACTIVE=1（每日幂等校验：今日已执行默认跳过），
# 一键执行带「强制重跑」开关时额外注入 KL8_FORCE_RERUN=1。
PIPELINE = [
    {
        "id": "data", "name": "data", "dir": "data", "timeout": 600,
        "icon": "📂", "color": "#6c5ce7",
        "pre_cmds": [
            ("开奖数据抓取更新", "python -u -X utf8 data_acquisition/fetch_kl8_history.py", 120),
            ("数据一致性校验", "python -u -X utf8 utils/data_validator.py --auto-fix", 120),
            ("热码统计生成", "python -u -X utf8 data_acquisition/generate_hot_excel.py", 120),
            ("热码同步至跟随表", "python -u -X utf8 data_acquisition/process_hot_numbers.py --sync-all-missing", 120),
            ("点位底色同步", "python -u -X utf8 format/apply_formats.py", 120),
        ],
        "cmd": "python -u -X utf8 main_v2.py --top 20",
        "post_cmds": [
            ("规则选号器", "python -u -X utf8 scratch/rule_picker.py --top 12", 60),
            ("内部提纯面板", "python -u -X utf8 scratch/today_console_panel.py", 60),
        ],
        "outputs": ["data/reports/daily_analysis_report_*.md", "data/kl8_history_final.txt"],
    },
    {
        "id": "lstm", "name": "双层LSTM", "dir": "双层LSTM", "timeout": 600,
        "icon": "🧠", "color": "#9b59b6",
        "pre_cmds": [("数据预检", "python -u -X utf8 precheck.py", 60)],
        "cmd": "python -u -X utf8 main.py full",
        "post_cmds": [("跨系统提纯", "python -u -X utf8 scratch/purify_cross_validate.py", 120)],
        "outputs": ["双层LSTM/outputs/predictions/prediction_*.txt", "双层LSTM/outputs/reports/purify_*.txt"],
    },
    {
        "id": "abc", "name": "顺口溜", "dir": "顺口溜", "timeout": 500,
        "icon": "📝", "color": "#f39c12",
        "pre_cmds": [],
        "cmd": "python -u -X utf8 daily_predict.py --with-c",
        "post_cmds": [],
        "outputs": ["顺口溜/output/latest_predict.txt", "顺口溜/output/c/latest_c_predict.txt"],
    },
    {
        "id": "points", "name": "重点点位分析", "dir": "重点点位分析", "timeout": 400,
        "icon": "📍", "color": "#3498db",
        "pre_cmds": [
            ("数据预检+系统诊断", "python -u -X utf8 diagnose.py", 60),
            ("深度复盘+闭环学习", "python -u -X utf8 trigger_review.py", 120),
        ],
        "cmd": "python -u -X utf8 main_predictor.py",
        "post_cmds": [("前序系统提纯报告", "python -u -X utf8 daily_report.py", 300)],
        "outputs": ["重点点位分析/logs/prediction_logs.txt"],
    },
    {
        "id": "dan2", "name": "定金选2-分析", "dir": "定金选2-分析", "timeout": 400,
        "icon": "💰", "color": "#1abc9c",
        "pre_cmds": [("环境预检+系统诊断", "python -u -X utf8 precheck.py", 60)],
        "cmd": "python -u -X utf8 main_predictor.py --no-interactive",
        "post_cmds": [],
        "outputs": ["定金选2-分析/logs/prediction_logs.txt"],
    },
    {
        "id": "killseeker", "name": "KillSeeker", "dir": "KillSeeker", "timeout": 400,
        "icon": "🎯", "color": "#e74c3c",
        "pre_cmds": [("环境诊断", "python -u -X utf8 main.py --diagnose", 60)],
        "cmd": "python -u -X utf8 main.py --full",
        "post_cmds": [],
        "outputs": ["KillSeeker/logs/kill_report.txt"],
    },
    {
        "id": "pointtrack", "name": "点位期数-追踪", "dir": "点位期数-追踪", "timeout": 300,
        "icon": "〽️", "color": "#16a085",
        "pre_cmds": [],
        "cmd": "python -u -X utf8 main.py --excel",
        "post_cmds": [],
        "outputs": ["点位期数-追踪/output/点位每日分析_*_T*.md", "点位期数-追踪/output/点位追踪_*.xlsx"],
    },
    {
        "id": "gemini", "name": "gemini选2-预测", "dir": "gemini选2-预测", "timeout": 600,
        "icon": "♊", "color": "#34495e",
        "pre_cmds": [
            ("开奖数据抓取更新", "python -u -X utf8 ../data/data_acquisition/fetch_kl8_history.py", 120),
            ("数据缺口检测", "python -u -X utf8 daily_run.py --detect-gap", 60),
        ],
        "cmd": "python -u -X utf8 daily_run.py",
        "post_cmds": [],
        "outputs": ["数据汇总复盘/gemini金银铜数据分析-汇总.txt"],
    },
    {
        "id": "aggregate", "name": "数据汇总复盘", "dir": "数据汇总复盘", "timeout": 600,
        "icon": "🏆", "color": "#2ecc71",
        "pre_cmds": [("数据预检", "python -u -X utf8 precheck.py", 60)],
        "cmd": "python -u -X utf8 aggregate_v18.py",
        "post_cmds": [],
        "outputs": ["数据汇总复盘/logs/分区深度聚合推荐_*.txt"],
    },
    {
        "id": "summary", "name": "预测结果汇总", "dir": "kl8-pwa", "timeout": 90,
        "icon": "📋", "color": "#6c5ce7",
        "pre_cmds": [],
        "cmd": "python -u -X utf8 summary_report.py",
        "post_cmds": [],
        "outputs": ["kl8-pwa/预测结果汇总_*.txt"],
    },
]


def _detect_outputs(sub, limit=5):
    """子系统主命令完成后，检测其生成的预测结果文件（outputs 为相对项目根的 glob 模式）。
    按修改时间倒序取最新 limit 个，返回相对路径列表。"""
    found = []
    for pattern in sub.get("outputs", []):
        try:
            for p in sorted(BASE_DIR.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True):
                if p.is_file():
                    rel = str(p.relative_to(BASE_DIR))
                    if rel not in found:
                        found.append(rel)
        except Exception:
            continue
        if len(found) >= limit:
            break
    return found[:limit]


def _is_fetch_cmd(pre_cmd):
    """判断前置命令是否为开奖数据抓取（补跑模式需跳过，防止最新开奖进入时间旅行数据）"""
    label, cmd, _ = pre_cmd
    return ("抓取" in label) or ("fetch" in cmd.lower())


def run_pipeline_subsystem(state, sub, force=False, target_date=None, skip_fetch=False):
    """按顺序执行单个子系统：前置命令 → 主命令 → 后置命令。
    返回 (success, skipped)；skipped=True 表示每日幂等校验判定今日已执行、默认跳过
    （主命令输出中检测 guard 的「每日校验 + 跳过」标记）。
    target_date=YYYY-MM-DD 时注入 KL8_TARGET_DATE（补跑历史）；skip_fetch=True 时
    跳过「开奖数据抓取更新」类前置命令。"""
    sub_id = sub["id"]
    sub_name = sub["name"]
    sub_dir = BASE_DIR / sub["dir"]
    step = "pipeline"

    append_log(state, step, f"▶ [{sub_name}] 启动...", source=sub_id)
    append_sub_log(state, sub_id, f"▶ 启动: {sub_name}")
    append_sub_log(state, sub_id, f"  路径: {sub_dir}")
    update_sub_status(state, sub_id, "running")

    total_start = time.time()
    main_success = True
    skipped = False

    # 1. 前置命令（失败不阻断主流程）
    pre_cmds = sub.get("pre_cmds", [])
    if skip_fetch:
        pre_cmds = [c for c in pre_cmds if not _is_fetch_cmd(c)]
    if pre_cmds:
        append_sub_log(state, sub_id, f"── 前置步骤 ({len(pre_cmds)}个) ──")
    for label, cmd, timeout in pre_cmds:
        append_sub_log(state, sub_id, f"  [{label}] {cmd}")
        _run_single_cmd(state, step, sub_id, sub_name, sub_dir, label, cmd, timeout, force=force, target_date=target_date)

    # 2. 主命令（核心步骤）
    append_sub_log(state, sub_id, "── 主步骤 ──")
    append_sub_log(state, sub_id, f"  [{sub_name}] {sub['cmd']}")
    main_success, _, main_output = _run_single_cmd(
        state, step, sub_id, sub_name, sub_dir, sub_name, sub["cmd"], sub["timeout"], force=force, target_date=target_date)
    # 每日幂等校验跳过检测：guard 打印「⏭️ [每日校验] ... 跳过」即今日已执行
    # 兼容同行 与 相邻行 两种排版，避免换行导致漏判
    if main_success:
        for i, ln in enumerate(main_output):
            if "每日校验" not in ln:
                continue
            if "跳过" in ln:
                skipped = True
                break
            for nxt in main_output[i + 1:i + 3]:
                if "跳过" in nxt:
                    skipped = True
                    break
            if skipped:
                break

    # 3. 后置命令（失败不影响最终完成状态）
    post_cmds = sub.get("post_cmds", [])
    if post_cmds:
        append_sub_log(state, sub_id, f"── 后置步骤 ({len(post_cmds)}个) ──")
    for label, cmd, timeout in post_cmds:
        append_sub_log(state, sub_id, f"  [{label}] {cmd}")
        _run_single_cmd(state, step, sub_id, sub_name, sub_dir, label, cmd, timeout, force=force, target_date=target_date)

    # 汇总
    total_elapsed = time.time() - total_start
    done_label = (f"{target_date}（补跑）" if target_date else "今日")
    if skipped:
        append_sub_log(state, sub_id, f"⏭️ [{sub_name}] {done_label}已执行过，默认跳过 ({total_elapsed:.1f}s)")
        append_log(state, step, f"⏭️ [{sub_name}] {done_label}已执行过，默认跳过 ({total_elapsed:.1f}s)", source=sub_id)
        update_sub_status(state, sub_id, "skipped")
    elif main_success:
        append_sub_log(state, sub_id, f"✅ [{sub_name}] 全部完成 ({total_elapsed:.1f}s)")
        append_log(state, step, f"✅ [{sub_name}] 全部完成 ({total_elapsed:.1f}s)", source=sub_id)
        update_sub_status(state, sub_id, "done")
    else:
        append_sub_log(state, sub_id, f"❌ [{sub_name}] 主步骤失败 ({total_elapsed:.1f}s)")
        append_log(state, step, f"❌ [{sub_name}] 主步骤失败 ({total_elapsed:.1f}s)", source=sub_id)
        update_sub_status(state, sub_id, "error")
    return main_success and not skipped, skipped


def execute_pipeline(state, force=False):
    """v3.0 一键全自动流水线：按用户指定顺序顺序执行 9 个子系统。
    前一系统完成后自动启动下一系统；每个子系统执行结束即检测并记录其生成的
    预测结果文件（sub_outputs 事件）。所有子进程注入 KL8_NON_INTERACTIVE=1，
    force=True 时注入 KL8_FORCE_RERUN=1 强制重跑今日已执行的系统。"""
    step = "pipeline"
    state.force = force
    state.stop_requested = False
    state.system_outputs = {}
    state.pipeline_status = "running"
    state.pipeline_start_time = time.time()
    state.emit_event("pipeline_status", {"status": "running", "force": force})

    append_log(state, step, "═══ 🚀 一键全自动流水线启动 ═══")
    append_log(state, step, "执行顺序: " + " → ".join(s["name"] for s in PIPELINE))
    if force:
        append_log(state, step, "♻️ 强制重跑模式（KL8_FORCE_RERUN=1）：今日已执行的子系统也会重新执行")
    else:
        append_log(state, step, "⏭️ 幂等模式：今日已执行的子系统将自动跳过（需重跑请勾选「强制重跑」）")

    # 初始化所有子系统为 pending
    for sub in PIPELINE:
        state.subsystem_status[sub["id"]] = "pending"
        state.emit_event("sub_status", {"sub_id": sub["id"], "status": "pending"})

    done_count = error_count = skip_count = 0
    stopped = False

    for i, sub in enumerate(PIPELINE):
        if state.stop_requested:
            stopped = True
            append_log(state, step, "⏹ 已收到停止请求，流水线中断")
            break
        seq = i + 1
        update_step_progress(state, step, i, len(PIPELINE), f"执行 {sub['name']} ({seq}/{len(PIPELINE)})")
        append_log(state, step, f"── 第 {seq}/{len(PIPELINE)} 个: {sub['name']} ──")
        success, skipped = run_pipeline_subsystem(state, sub, force=force)

        # 记录该子系统生成的预测结果文件
        outputs = _detect_outputs(sub)
        state.system_outputs[sub["id"]] = outputs
        state.emit_event("sub_outputs", {"sub_id": sub["id"], "outputs": outputs})
        if outputs:
            append_sub_log(state, sub["id"], f"  📄 生成预测结果文件: {len(outputs)} 个")
            for o in outputs:
                append_sub_log(state, sub["id"], f"     {o}")

        if skipped:
            skip_count += 1
        elif success:
            done_count += 1
        else:
            error_count += 1

    update_step_progress(state, step, len(PIPELINE), len(PIPELINE), "完成")
    elapsed_total = time.time() - state.pipeline_start_time
    summary = f"成功 {done_count} / 失败 {error_count} / 跳过 {skip_count}" + ("（已停止 ⏹）" if stopped else "")
    state.results[step] = summary
    append_log(state, step, f"══ {'═' * 40} ══")
    append_log(state, step, f"🏁 流水线结束: {summary} | 总耗时 {elapsed_total:.1f}s")
    # 部分失败也视为「完成」（用户可查看汇总/重跑失败系统），仅停止请求时置 stopped
    state.pipeline_status = "stopped" if stopped else "done"
    state.emit_event("pipeline_status", {
        "status": state.pipeline_status, "summary": summary,
        "elapsed": round(elapsed_total, 1),
        "done": done_count, "error": error_count, "skipped": skip_count,
        "stopped": stopped,
    })


# ═══════════════════════════════════════════════════════════
# v3.1 PWA 批量补跑历史日期（网页选日期范围 → 时间旅行逐日循环）
# ═══════════════════════════════════════════════════════════
# 补跑流程：增量抓取补齐断档开奖 → 快照关键文件 → 对每个目标日「截断历史数据
# 模拟当天」跑一轮 9 子系统 → 结束后还原关键文件（保证「今日最新预测」不被污染）。
# daily_run_guard 通过 KL8_TARGET_DATE 感知目标日期，幂等记录写入目标日期当日。

# 补跑涉及的关键文件：数据文件 + 固定名"最新"文件（结束还原）
BACKFILL_DATA_FILES = [
    BASE_DIR / "data" / "kl8_history_final.txt",
    BASE_DIR / "data" / "daily_points.txt",
]
BACKFILL_OVERWRITE_FILES = [
    BASE_DIR / "顺口溜" / "output" / "latest_predict.txt",
    BASE_DIR / "顺口溜" / "output" / "c" / "latest_c_predict.txt",
    BASE_DIR / "KillSeeker" / "logs" / "kill_report.txt",
]
BACKFILL_SNAPSHOT_FILES = BACKFILL_DATA_FILES + BACKFILL_OVERWRITE_FILES
BACKFILL_MAX_DAYS = 31  # 补跑天数上限，防误触发超长任务
# 补跑结果统一存档根目录：每天每子系统的产物副本都落在 outputs/backfill/<日期>/<子系统>/，
# 避免「覆盖面式最新文件」补跑结束被还原导致当日报告丢失。
BACKFILL_ARCHIVE_DIR = BASE_DIR / "outputs" / "backfill"


def _archive_day_outputs(state, day_iso, sub, outputs):
    """把目标日该子系统生成的产物文件复制到统一存档目录（防固定名文件被还原覆盖）"""
    import shutil
    archived = []
    try:
        dest_dir = BACKFILL_ARCHIVE_DIR / day_iso / sub["id"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        for rel in outputs:
            src = BASE_DIR / rel
            if src.is_file():
                dst = dest_dir / src.name
                shutil.copy2(src, dst)
                archived.append(str(dst))
    except OSError as e:
        append_log(state, "pipeline", f"  ⚠️ 存档 {day_iso}/{sub['id']} 失败: {e}")
    if archived:
        append_log(state, "pipeline", f"  🗂 已存档 {day_iso}/{sub['id']} → outputs/backfill/{day_iso}/{sub['id']}/")
    return archived


def _snapshot_files(paths):
    """把文件内容读入内存快照（缺失文件记为 None）"""
    snap = {}
    for p in paths:
        try:
            snap[p] = p.read_text(encoding="utf-8", errors="replace") if p.exists() else None
        except OSError:
            snap[p] = None
    return snap


def _restore_files(snap):
    """把快照写回（None = 补跑前该文件不存在，删除之）"""
    for p, content in snap.items():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            if content is None:
                if p.exists():
                    p.unlink()
            else:
                p.write_text(content, encoding="utf-8")
        except OSError:
            pass


def _truncate_data_to(date_iso):
    """截断开奖/点位文件模拟目标日前的已知状态。

    - kl8_history_final.txt（已开奖结果）：仅保留 date < 目标日，目标日开奖视为不可见。
    - daily_points.txt（目标点位）：保留 date ≤ 目标日——点位是「待预测期」的预测输入，
      重点点位分析以 daily_points 最新期作为预测目标，若截掉目标日点位会报「无可预测目标期」。
    """
    for p in BACKFILL_DATA_FILES:
        if not p.exists():
            continue
        is_points = p.name == "daily_points.txt"
        keep = []
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.search(r'date:(\d{4}-\d{2}-\d{2})', line)
            if not m:
                keep.append(line)
                continue
            if is_points:
                if m.group(1) <= date_iso:
                    keep.append(line)
            else:
                if m.group(1) < date_iso:
                    keep.append(line)
        p.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")


def _archive_data_report(state, day_iso):
    """data 子系统每日报告文件名取真实今天，补跑时归档为「目标日」文件名避免互相覆盖。

    取名自 reports 目录 mtime 最新的 daily_analysis_report_*.md（当日子系统刚写完），
    复制一份到 daily_analysis_report_<目标日>.md 供历史查证。"""
    import shutil
    reports_dir = BASE_DIR / "data" / "reports"
    try:
        rpt = sorted(reports_dir.glob("daily_analysis_report_*.md"),
                     key=lambda f: f.stat().st_mtime, reverse=True)
        if not rpt:
            return
        latest = rpt[0]
        target_file = reports_dir / ("daily_analysis_report_" + day_iso.replace("-", "") + ".md")
        if latest.resolve() == target_file.resolve():
            return
        shutil.copy2(latest, target_file)
        append_log(state, "pipeline", f"  🗂 [{day_iso}] data 报告已归档: {target_file.name}")
    except OSError:
        pass


def _backfill_fetch_history(state):
    """补跑开始前增量抓取一次：把断档期开奖补齐到 history/daily_points"""
    step = "pipeline"
    append_log(state, step, "────────── 增量抓取开奖数据（补齐断档期） ──────────")
    cmd = "python -u -X utf8 data_acquisition/fetch_kl8_history.py"
    ok, _, _ = _run_single_cmd(
        state, step, "data", "开奖数据抓取", BASE_DIR / "data",
        "增量抓取", cmd, 300, target_date=None)
    if not ok:
        append_log(state, step, "⚠️ [数据抓取] 失败，补跑目标期号可能偏离（请留意各子系统日志中的最新期号）")


def execute_backfill(state, date_start, date_end, force=False):
    """PWA 批量补跑：按 [date_start, date_end] 逐日截断历史模拟当天，跑一轮流水线。

    date_start/date_end: datetime.date。每轮注入 KL8_TARGET_DATE=<day> 供 guard
    幂等校验；跳过「开奖数据抓取」命令与 summary 子系统；结束后还原关键文件。
    """
    step = "pipeline"
    state.force = force
    state.stop_requested = False
    state.system_outputs = {}
    state.pipeline_status = "running"
    state.pipeline_start_time = time.time()
    state.emit_event("pipeline_status", {"status": "running", "force": force, "backfill": True})

    append_log(state, step, "═══ 📅 PWA 批量补跑启动 ═══")
    append_log(state, step, f"补跑范围: {date_start} → {date_end}"
               + ("（♻️ 强制重跑）" if force else "（幂等模式：目标日已补过的子系统自动跳过）"))

    # 1) 增量抓取补齐断档期开奖（需在快照前执行，快照保留的是抓取后的完整数据）
    _backfill_fetch_history(state)

    # 2) 快照关键文件（结束后还原，保证今日最新预测不被污染）
    snap = _snapshot_files(BACKFILL_SNAPSHOT_FILES)

    # 初始化所有子系统为 pending
    for sub in PIPELINE:
        state.subsystem_status[sub["id"]] = "pending"
        state.emit_event("sub_status", {"sub_id": sub["id"], "status": "pending"})

    # summary 产出「今日汇总」且无日期参数，补跑跳过
    subs = [s for s in PIPELINE if s["id"] != "summary"]
    days = [date_start + timedelta(days=i) for i in range((date_end - date_start).days + 1)]
    total_steps = len(days) * len(subs)
    done_days, error_days = [], []
    stopped = False

    try:
        for di, day in enumerate(days):
            if state.stop_requested:
                stopped = True
                break
            day_iso = day.isoformat()
            append_log(state, step, f"\n{'━' * 46}")
            append_log(state, step, f"📅 补跑第 {di + 1}/{len(days)} 天：{day_iso}")
            append_log(state, step, f"{'━' * 46}")

            # 3) 恢复完整数据并截断至该日前，模拟该时点已知的开奖/点位
            _restore_files(snap)
            _truncate_data_to(day_iso)

            day_success = day_error = day_skip = 0
            interrupted = False
            for j, sub in enumerate(subs):
                if state.stop_requested:
                    stopped = True
                    interrupted = True
                    break
                seq = di * len(subs) + j + 1
                update_step_progress(state, step, seq, total_steps,
                                     f"补跑 {day_iso} · {sub['name']}（第{di + 1}/{len(days)}天）")
                append_log(state, step, f"── [{day_iso}] {sub['name']} ──")
                # 数据汇总复盘的报告文件名取 --date 或真实今天；补跑必须注入目标日才按日命名
                sub_run = sub
                if sub["id"] == "aggregate":
                    sub_run = {**sub, "cmd": sub["cmd"] + f" --date {day_iso.replace('-', '')}"}
                success, skipped = run_pipeline_subsystem(
                    state, sub_run, force=force, target_date=day_iso, skip_fetch=True)

                outputs = _detect_outputs(sub)
                state.system_outputs[f"{day_iso}|{sub['id']}"] = outputs
                state.emit_event("sub_outputs", {"sub_id": sub["id"], "day": day_iso, "outputs": outputs})
                if outputs:
                    append_sub_log(state, sub["id"], f"  📄 生成预测结果文件: {len(outputs)} 个")
                    for o in outputs:
                        append_sub_log(state, sub["id"], f"     {o}")
                # 目标日产物统一归档留档（固定名文件后面会被还原，靠副本保留当日报告）
                _archive_day_outputs(state, day_iso, sub, outputs)

                if skipped:
                    day_skip += 1
                elif success:
                    day_success += 1
                else:
                    day_error += 1

            if not interrupted:
                if day_error:
                    error_days.append(day_iso)
                elif day_skip == len(subs):
                    append_log(state, step, f"⏭️ {day_iso} 各子系统均命中「已执行」，整体跳过（重复补跑或当日已标记）")
                else:
                    done_days.append(day_iso)
                append_log(state, step, f"📅 {day_iso} 汇总：成功 {day_success} / 失败 {day_error} / 跳过 {day_skip}")
                # data 子系统报告文件名用真实今天，补跑时归档为「目标日」文件名
                _archive_data_report(state, day_iso)
    finally:
        # 4) 结束后还原关键文件（数据回到补跑前完整状态；append 历史文件保留补跑记录）
        _restore_files(snap)

    elapsed = time.time() - state.pipeline_start_time
    summary = f"补跑完成: 成功 {len(done_days)} 天 / 异常 {len(error_days)} 天" + ("（已停止 ⏹）" if stopped else "")
    state.results[step] = summary
    append_log(state, step, f"\n══ {'═' * 40} ══")
    append_log(state, step, f"⟹ {summary} | 总耗时 {elapsed:.1f}s")
    if error_days:
        append_log(state, step, "⚠️ 存在异常的日期: " + ", ".join(error_days) + "（可勾选「强制重跑」对失败系统重试）")
    append_log(state, step, "⟹ 数据文件与「今日最新预测」已还原；append 型历史文件保留了本次补跑记录。")
    append_log(state, step, f"🗂 补跑结果存档目录: {BACKFILL_ARCHIVE_DIR}（每个目标日/子系统一份副本，共 {len(days)} 天）")
    state.pipeline_status = "stopped" if stopped else "done"
    state.emit_event("pipeline_status", {
        "status": state.pipeline_status, "summary": summary,
        "elapsed": round(elapsed, 1), "backfill": True,
        "done_days": len(done_days), "error_days": error_days,
        "stopped": stopped,
    })


# ═══════════════════════════════════════════════════════════
# gemini 汇总文件只读预览（Step 4 手动输入已移除，v3.0 gemini 子系统自动生成）
# ═══════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════
def read_gemini_file():
    gf = BASE_DIR / "数据汇总复盘" / "gemini金银铜数据分析-汇总.txt"
    if not gf.exists():
        return {"error": "文件不存在", "content": ""}
    try:
        with open(gf, 'r', encoding='utf-8') as f:
            content = f.read()
        lines = content.strip().split('\n')
        latest_date = lines[0].rstrip(':') if lines else ""
        return {
            "file_path": str(gf),
            "latest_date": latest_date,
            "total_lines": len(lines),
            "preview": content[:3000]
        }
    except Exception as e:
        return {"error": str(e), "content": ""}


# ═══════════════════════════════════════════════════════════
# 预测结果解析模块
# ═══════════════════════════════════════════════════════════

import re as _re
from pathlib import Path as _Path

def _read_file_safe(filepath):
    """多编码安全读取文件（utf-8-sig 排在 utf-8 前，避免带 BOM 的 UTF-8 文件残留 \\ufeff）"""
    if not filepath.exists():
        return ""
    for enc in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    # 混合编码回退：UTF-8 with replace（保留ASCII/数字部分正确）
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except (UnicodeDecodeError, UnicodeError, OSError):
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                return f.read()
        except OSError:
            return ""


def _extract_nums(raw_text):
    """从文本中提取1-80的号码"""
    # 先清除 np.int64() 等包装
    cleaned = _re.sub(r'np\.int\d+\((\d+)\)', r'\1', raw_text)
    return [int(n) for n in _re.findall(r'\d+', cleaned) if 1 <= int(n) <= 80]


def _get_latest_draw():
    """获取最新一期开奖结果（文件倒序，最新在第一行）"""
    history_file = BASE_DIR / "data" / "kl8_history_final.txt"
    if not history_file.exists():
        return None, None
    content = _read_file_safe(history_file)
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    if not lines:
        return None, None
    first_line = lines[0]
    m = _re.search(r'period:(\d+)', first_line)
    period = m.group(1) if m else ""
    m = _re.search(r'numbers:([\d-]+)', first_line)
    if m:
        nums = [int(x) for x in m.group(1).split('-') if x.isdigit() and 1 <= int(x) <= 80]
        if len(nums) >= 20:
            return period, set(nums[:20])
    return None, None


def _get_prev_draw():
    """获取上一期开奖结果（文件倒序，上期在第二行）"""
    history_file = BASE_DIR / "data" / "kl8_history_final.txt"
    if not history_file.exists():
        return None, None
    content = _read_file_safe(history_file)
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    if len(lines) < 2:
        return None, None
    prev_line = lines[1]  # 第二行是上一期
    m = _re.search(r'period:(\d+)', prev_line)
    period = m.group(1) if m else ""
    m = _re.search(r'numbers:([\d-]+)', prev_line)
    if m:
        nums = [int(x) for x in m.group(1).split('-') if x.isdigit() and 1 <= int(x) <= 80]
        if len(nums) >= 20:
            return period, set(nums[:20])
    return None, None


def _compute_review(pred_nums, actual_nums, top_n=None):
    """计算预测命中情况"""
    if not pred_nums or not actual_nums:
        return None
    pred_set = set(pred_nums[:top_n]) if top_n else set(pred_nums)
    hits = pred_set & actual_nums
    total = len(pred_set)
    hit_count = len(hits)
    lift = round(hit_count / total / 0.25, 2) if total > 0 else 0
    return {
        "hits": f"{hit_count}/{total}",
        "lift": f"{lift}x" if lift > 0 else "0.00x",
        "hit_nums": sorted(hits),
        "miss_nums": sorted(pred_set - actual_nums),
    }


def parse_data_subsystem():
    """解析 data 子系统的最新分析报告（完整版）"""
    reports_dir = BASE_DIR / "data" / "reports"
    files = sorted(reports_dir.glob("daily_analysis_report_*.md"), reverse=True)
    if not files:
        return {"error": "无报告文件", "name": "Data分析引擎"}
    content = _read_file_safe(files[0])
    result = {"name": "Data分析引擎", "file": files[0].name}
    # 目标期号
    m = _re.search(r'目标期号[：:]\s*\**\s*(\d+)', content)
    result["target_period"] = m.group(1) if m else ""
    # 三维融合
    m = _re.search(r'极秘 Top 5.*?\[([^\]]+)\]', content)
    result["trinity_top5"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'极秘 Top 12.*?\[([^\]]+)\]', content)
    result["trinity_top12"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'动态模型赋权.*?`([^`]+)`', content)
    result["trinity_weights"] = m.group(1) if m else ""
    # 传统AI
    m = _re.search(r'Top 5 置信度精选.*?\[([^\]]+)\]', content)
    result["ai_top5"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'Top 12 综合拦截.*?\[([^\]]+)\]', content)
    result["ai_top12"] = _extract_nums(m.group(1)) if m else []
    # Golden Core
    m = _re.search(r'高频共振集群.*?\[([^\]]+)\]', content)
    result["golden_core"] = _extract_nums(m.group(1)) if m else []
    # mRMR
    m = _re.search(r'mRMR Top 12.*?\[([^\]]+)\]', content)
    result["mrmr_top12"] = _extract_nums(m.group(1)) if m else []
    # Hidden Energy 5
    m = _re.search(r'最终推荐.*?5.*?码.*?\[([^\]]+)\]', content)
    result["he5"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'B3质量分.*?`([\d.]+)`', content)
    result["he5_b3_quality"] = m.group(1) if m else ""
    # HE5 每码EF/RW/FO明细
    he5_detail = []
    for m in _re.finditer(r'号码\s*`(\d+)`.*?EF\s*`([\d.]+)`.*?RW\s*`([\d.]+)`.*?FO\s*`([\d.]+)`.*?动能\s*`([\d.]+)`', content):
        he5_detail.append({"num": int(m.group(1)), "ef": m.group(2), "rw": m.group(3), "fo": m.group(4), "score": m.group(5)})
    result["he5_detail"] = he5_detail[:5]
    # 纯净池
    m = _re.search(r'纯净池号码.*?\[([^\]]+)\]', content)
    result["pure_pool"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'高置信定胆.*?评分.*?3.*?\[([^\]]+)\]', content)
    result["pure_pool_high"] = _extract_nums(m.group(1)) if m else []
    # FO Baseline
    m = _re.search(r'FO.*?金胆 Top5.*?\[([^\]]+)\]', content)
    result["fo_top5"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'FO.*?综合 Top12.*?\[([^\]]+)\]', content)
    result["fo_top12"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'FO.*?Top20.*?\[([^\]]+)\]', content)
    result["fo_top20"] = _extract_nums(m.group(1)) if m else []
    # 对冲方案
    m = _re.search(r'主攻方案.*?\[([^\]]+)\]', content)
    result["hedge_main"] = _extract_nums(m.group(1))[:12] if m else []
    m = _re.search(r'对冲方案 A.*?\[([^\]]+)\]', content)
    result["hedge_a"] = _extract_nums(m.group(1))[:10] if m else []
    m = _re.search(r'对冲方案 B.*?\[([^\]]+)\]', content)
    result["hedge_b"] = _extract_nums(m.group(1))[:10] if m else []
    # 环境识别
    m = _re.search(r'环境识别[：:]\s*`([^`]+)`', content)
    result["environment"] = m.group(1) if m else ""
    # 统计置信度状态
    m = _re.search(r'Level\s*(\d).*?置信度输出系数[：:]\s*`([\d.]+x`)', content)
    result["confidence_level"] = f"Level {m.group(1)}" if m else ""
    result["confidence_coeff"] = m.group(2) if m else ""
    # 物理熔断 KL散度
    m = _re.search(r'KL\s*散度.*?([\d.]+).*?Z-Score.*?([-\d.]+)\s*Sigma', content)
    result["kl_divergence"] = m.group(1) if m else ""
    result["kl_zscore"] = m.group(2) if m else ""
    # 闭环学习状态
    m = _re.search(r'闭环学习决策[：:]\s*`([^`]+)`', content)
    result["learning_decision"] = m.group(1) if m else ""
    m = _re.search(r'策略模式[：:]\s*`([^`]+)`', content)
    result["strategy_mode"] = m.group(1) if m else ""
    m = _re.search(r'权重变更[：:]\s*`([^`]+)`', content)
    result["weight_change"] = m.group(1) if m else ""
    m = _re.search(r'WF Lift.*?`([\d.]+)`', content)
    result["wf_lift"] = m.group(1) if m else ""
    # === 上期复盘 ===
    m = _re.search(r'开奖号码.*?\s([\d-]+)', content)
    result["review_actual"] = m.group(1) if m else ""
    m = _re.search(r'三维融合.*?Top5 命中\s*`(\d+/\d+)`', content)
    result["last_review_trinity"] = m.group(1) if m else ""
    m = _re.search(r'三维融合.*?Top12 命中\s*`(\d+/\d+)`', content)
    result["last_review_trinity12"] = m.group(1) if m else ""
    m = _re.search(r'传统AI.*?Top5 命中\s*`(\d+/\d+)`', content)
    result["last_review_ai"] = m.group(1) if m else ""
    m = _re.search(r'传统AI.*?Top12 命中\s*`(\d+/\d+)`', content)
    result["last_review_ai12"] = m.group(1) if m else ""
    m = _re.search(r'熵控优化.*?mRMR.*?命中\s*`?(\d+/\d+)`?', content)
    result["last_review_mrmr"] = m.group(1) if m else ""
    m = _re.search(r'Hidden Energy 5.*?命中\s*`?(\d+/\d+)`?', content)
    result["last_review_he5"] = m.group(1) if m else ""
    m = _re.search(r'纯净池定胆.*?命中\s*`?(\d+/\d+)`?', content)
    result["last_review_pure"] = m.group(1) if m else ""
    return result


def parse_killseeker():
    """解析 KillSeeker 最新杀号报告"""
    report_file = BASE_DIR / "KillSeeker" / "logs" / "kill_report.txt"
    content = _read_file_safe(report_file)
    if not content:
        return {"error": "无杀号报告", "name": "KillSeeker杀号"}
    result = {"name": "KillSeeker杀号"}
    m = _re.search(r'(\d{7})期\s*杀号推荐', content)
    result["target_period"] = m.group(1) if m else ""
    m = _re.search(r'综合把握:\s*([\d.]+%)', content)
    result["confidence"] = m.group(1) if m else ""
    m = _re.search(r'高置信杀号.*?:\s*\n\s*([\d\s]+)', content)
    result["high_kill"] = [int(x) for x in m.group(1).split()] if m else []
    m = _re.search(r'中置信杀号.*?:\s*\n\s*([\d\s]+)', content)
    result["medium_kill"] = [int(x) for x in m.group(1).split()] if m else []
    m = _re.search(r'观察区杀号.*?:\s*\n\s*([\d\s]+)', content)
    result["watch_kill"] = [int(x) for x in m.group(1).split()] if m else []
    # 保留号 - 精确匹配“保留号 (NN个”后面的号码行
    m = _re.search(r'保留号 \(\d+个[^\n]*\):\s*\n\s*([\d\s]+)', content)
    if not m:
        m = _re.search(r'保留号.*?\(\d+个[^\n]*\):\s*\n\s*([\d\s]+)', content)
    if m:
        result["keep_numbers"] = [int(x) for x in m.group(1).split() if x.isdigit() and 1 <= int(x) <= 80]
    else:
        result["keep_numbers"] = []
    m = _re.search(r'高置信杀号:\s*\d+/\d+\s*=\s*([\d.]+%)', content)
    result["avg_high_kill"] = m.group(1) if m else ""
    m = _re.search(r'全部杀号:\s*\d+/\d+\s*=\s*([\d.]+%)', content)
    result["avg_total_kill"] = m.group(1) if m else ""
    # === 上期复盘 ===
    m = _re.search(r'(\d{7})期.*?复盘', content)
    result["review_period"] = m.group(1) if m else ""
    m = _re.search(r'实际开奖.*?[：:]\s*\[([^\]]+)\]', content)
    result["review_actual"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'高置信杀号.*?(\d+/\d+)\s*=\s*[\d.]+%', content)
    result["last_review_high"] = m.group(1) if m else ""
    m = _re.search(r'中置信杀号.*?(\d+/\d+)\s*=\s*[\d.]+%', content)
    result["last_review_medium"] = m.group(1) if m else ""
    m = _re.search(r'全部杀号.*?(\d+/\d+)\s*=\s*[\d.]+%', content)
    result["last_review_total"] = m.group(1) if m else ""
    m = _re.search(r'保留号.*?(\d+/\d+)\s*=\s*[\d.]+%', content)
    result["last_review_keep"] = m.group(1) if m else ""
    return result


def parse_points():
    """解析 重点点位分析 最新预测"""
    log_file = BASE_DIR / "重点点位分析" / "logs" / "prediction_logs.txt"
    content = _read_file_safe(log_file)
    if not content:
        return {"error": "无预测日志", "name": "重点点位分析"}
    entries = content.split('-' * 40)
    last_entry = entries[-2] if len(entries) >= 2 else content
    if len(last_entry.strip()) < 20:
        non_empty = [e for e in entries if len(e.strip()) > 20]
        last_entry = non_empty[-1] if non_empty else content
    result = {"name": "重点点位分析"}
    m = _re.search(r'目标期数:\s*(\S+)', last_entry)
    result["target_period"] = m.group(1) if m else ""
    m = _re.search(r'置信等级:\s*(.+?)(?:\||\n)', last_entry)
    result["confidence_level"] = m.group(1).strip() if m else ""
    m = _re.search(r'OOF AUC:\s*([\d.]+)', last_entry)
    result["oof_auc"] = m.group(1) if m else ""
    m = _re.search(r'OOF Lift:\s*([\d.]+)', last_entry)
    result["oof_lift"] = m.group(1) if m else ""
    m = _re.search(r'精选十码:\s*\[([^\]]+)\]', last_entry)
    result["top10"] = _extract_nums(m.group(1)) if m else []
    top5 = []
    for m in _re.finditer(r'#\d+\s+点位\[\d+\].*?最佳号码:\[(\d+)\]', last_entry):
        top5.append(int(m.group(1)))
    result["core5"] = top5[:5]
    points_detail = []
    for m in _re.finditer(r'#(\d+)\s+点位\[(\d+)\]\s+区域\[([^\]]+)\]\s+得分:([\d.]+)\s+p:([\d.]+)', last_entry):
        points_detail.append({"rank": int(m.group(1)), "point": int(m.group(2)), "zone": m.group(3), "score": m.group(4), "p_value": m.group(5)})
    result["points_detail"] = points_detail[:10]
    # 扩展十五码
    m = _re.search(r'扩展十五码.*?\[([^\]]+)\]', last_entry)
    result["top15"] = _extract_nums(m.group(1)) if m else []
    # 引擎共识
    m = _re.search(r'引擎共识.*?(\d+/\d+)', last_entry)
    result["engine_consensus"] = m.group(1) if m else ""
    # 空间均衡
    m = _re.search(r'空间均衡.*?(\S+)', last_entry)
    result["space_balance"] = m.group(1) if m else ""
    # === 上期复盘 ===
    m = _re.search(r'一级.*?命中率.*?(\d+/\d+).*?([\d.]+x)', last_entry)
    result["last_review_zone"] = m.group(1) if m else ""
    result["last_review_zone_lift"] = m.group(2) if m else ""
    m = _re.search(r'二级.*?命中率.*?(\d+/\d+).*?([\d.]+x)', last_entry)
    result["last_review_top10"] = m.group(1) if m else ""
    result["last_review_top10_lift"] = m.group(2) if m else ""
    m = _re.search(r'核心五码.*?(\d+/\d+).*?([\d.]+x)', last_entry)
    result["last_review_core5"] = m.group(1) if m else ""
    result["last_review_core5_lift"] = m.group(2) if m else ""
    m = _re.search(r'实际开奖.*?[：:]\s*\[([^\]]+)\]', last_entry)
    result["review_actual"] = _extract_nums(m.group(1)) if m else []
    return result


def parse_lstm():
    """解析 双层LSTM 最新预测"""
    pred_dir = BASE_DIR / "双层LSTM" / "outputs" / "predictions"
    files = sorted(pred_dir.glob("prediction_*.txt"), reverse=True)
    if not files:
        return {"error": "无预测文件", "name": "双层LSTM"}
    content = _read_file_safe(files[0])
    result = {"name": "双层LSTM", "file": files[0].name}
    m = _re.search(r'预测期号[:：]\s*(\d+)', content)
    result["target_period"] = m.group(1) if m else ""
    m = _re.search(r'金胆[:：]\s*(\d+)', content)
    result["gold"] = int(m.group(1)) if m else None
    m = _re.search(r'银胆[:：]\s*(\d+)', content)
    result["silver"] = int(m.group(1)) if m else None
    m = _re.search(r'铜胆[:：]\s*(\d+)', content)
    result["bronze"] = int(m.group(1)) if m else None
    m = _re.search(r'Top10[:：]\s*([\d-]+)', content)
    result["top10"] = [int(x) for x in m.group(1).split('-') if x.isdigit()] if m else []
    m = _re.search(r'一致性评分[:：]\s*([\d.]+)\s*\[([^\]]+)\]', content)
    result["consistency"] = m.group(1) if m else ""
    result["consistency_level"] = m.group(2) if m else ""
    m = _re.search(r'验证Loss[:：]\s*([\d.]+)', content)
    result["val_loss"] = m.group(1) if m else ""
    zones = {}
    for m in _re.finditer(r'(\d头\(\d+-\d+\))[:：]\s*预测\s*(\d+)\s*个', content):
        zones[m.group(1)] = int(m.group(2))
    result["zone_prediction"] = zones
    top20 = []
    for m in _re.finditer(r'^\s*\d+\s+(\d+)\s+[\d.]+', content, _re.MULTILINE):
        num = int(m.group(1))
        if 1 <= num <= 80 and num not in top20:
            top20.append(num)
    result["top20"] = top20[:20]
    m = _re.search(r'训练种子[:：]\s*(\d+)', content)
    result["train_seed"] = m.group(1) if m else ""
    m = _re.search(r'训练轮次.*?(\d+).*?最佳.*?(\d+)', content)
    result["total_epochs"] = m.group(1) if m else ""
    result["best_epoch"] = m.group(2) if m else ""
    # === 上期复盘 ===
    m = _re.search(r'复盘.*?Top10.*?(\d+/\d+).*?Lift.*?([\d.]+x)', content)
    result["last_review_top10"] = m.group(1) if m else ""
    result["last_review_top10_lift"] = m.group(2) if m else ""
    m = _re.search(r'金胆.*?(✅|❌)', content)
    result["last_review_gold"] = m.group(1) if m else ""
    m = _re.search(r'银胆.*?(✅|❌)', content)
    result["last_review_silver"] = m.group(1) if m else ""
    m = _re.search(r'铜胆.*?(✅|❌)', content)
    result["last_review_bronze"] = m.group(1) if m else ""
    return result


def parse_abc():
    """解析顺口溜最新预测（传统顺口溜 + C 数据挖掘）；兼容聚合层旧 key=abc。"""
    sk_dir = BASE_DIR / "顺口溜"
    main_report = sk_dir / "output" / "latest_predict.txt"
    c_report = sk_dir / "output" / "c" / "latest_c_predict.txt"
    if not main_report.exists():
        return {"error": "无顺口溜报告", "name": "顺口溜"}
    content = _read_file_safe(main_report)
    result = {"name": "顺口溜", "file": main_report.name}
    m = _re.search(r'目标期号\s*→\s*(\d+)', content) or _re.search(r'下一期\s+(\d+)', content)
    result["target_period"] = m.group(1) if m else ""
    m = _re.search(r'核心推荐 Top10[:：]\s*([0-9 ]+)', content)
    top10 = _extract_nums(m.group(1)) if m else []
    result["engine_a_top10"] = top10
    result["version_a_top10"] = top10
    m = _re.search(r'★ 强推[^:]*[:：]\s*([^\n]+)', content)
    strong = _extract_nums(m.group(1)) if m else []
    result["engine_a_top5"] = strong[:5] if strong else top10[:5]
    result["version_a_gold"] = result["engine_a_top5"]
    result["version_b_top10"] = []
    result["version_b_gold"] = []
    result["ab_intersection"] = []
    result["abc_intersection"] = []
    result["combined_pool"] = top10
    m = _re.search(r'号码命中率\s+([\d.]+)%（随机', content)
    result["last_lift"] = m.group(1) if m else ""
    # C 版
    c_content = _read_file_safe(c_report) if c_report.exists() else ""
    m = _re.search(r'选十推荐[:：]\s*\[([^\]]*)\]', c_content)
    result["version_c_top10"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'选五胆码[:：]\s*\[([^\]]*)\]', c_content)
    result["version_c_gold"] = _extract_nums(m.group(1)) if m else []
    # === 上期复盘（顺口溜控制面板【二】）===
    m = _re.search(r'推荐\s+(\d+)\s*个\s*\|\s*命中\s+(\d+)\s*个', content)
    if m:
        result["last_review_a"] = f"{m.group(2)}/{m.group(1)}"
        result["last_review_a_lift"] = ""
    else:
        result["last_review_a"] = ""
        result["last_review_a_lift"] = ""
    result["last_review_b"] = ""
    result["last_review_b_lift"] = ""
    m = _re.search(r'C版.*?Top10.*?(\d+/\d+).*?Lift.*?([\d.]+x)', content)
    result["last_review_c"] = m.group(1) if m else ""
    result["last_review_c_lift"] = m.group(2) if m else ""
    return result


def parse_dan2():
    """解析 定金选2-分析 最新预测"""
    log_file = BASE_DIR / "定金选2-分析" / "logs" / "prediction_logs.txt"
    content = _read_file_safe(log_file)
    if not content:
        return {"error": "无预测日志", "name": "定金选2-分析"}
    result = {"name": "定金选2-分析"}
    period_positions = [m.start() for m in _re.finditer(r'预测期号[:：]\s*\d+', content)]
    if period_positions:
        last_section = content[period_positions[-1]:period_positions[-1] + 3000]
    else:
        last_section = content[-3000:]
    m = _re.search(r'预测期号[:：]\s*(\d+)', last_section)
    result["target_period"] = m.group(1) if m else ""
    m = _re.search(r'动态金胆[:：]\s*(\d+)', last_section)
    result["gold"] = int(m.group(1)) if m else None
    m = _re.search(r'热号金胆\s*\[(\d+)\]', last_section)
    result["hot_gold"] = int(m.group(1)) if m else None
    m = _re.search(r'市场相位[:：]\s*(.+?)(?:\(|\n)', last_section)
    result["market_phase"] = m.group(1).strip() if m else ""
    m = _re.search(r'降级等级[:：]\s*(.+?)(?:\n|$)', last_section)
    result["level"] = m.group(1).strip() if m else ""
    top3 = []
    for m in _re.finditer(r'Top\s*(\d+)\s*推荐组合\s*[:：]\s*\[(\d+)-(\d+)\].*?综合评分[:：]\s*([\d.]+)', last_section):
        top3.append({"rank": int(m.group(1)), "pair": f"{m.group(2)}-{m.group(3)}", "score": m.group(4)})
    result["top3_combos"] = top3[:3]
    hot_top3 = []
    for m in _re.finditer(r'热-Top\s*(\d+)\s*推荐组合\s*[:：]\s*\[(\d+)-(\d+)\].*?综合评分[:：]\s*([\d.]+)', last_section):
        hot_top3.append({"rank": int(m.group(1)), "pair": f"{m.group(2)}-{m.group(3)}", "score": m.group(4)})
    result["hot_top3_combos"] = hot_top3[:3]
    m = _re.search(r'温号池规模[:：]\s*(\d+)', last_section)
    result["warm_pool_size"] = int(m.group(1)) if m else 0
    m = _re.search(r'备选金胆[:：]\s*(\d+)号', last_section)
    result["alt_gold"] = int(m.group(1)) if m else None
    # === 上期复盘 ===
    m = _re.search(r'金胆.*(\d+).*(命中|未命中)', last_section)
    result["last_review_gold"] = m.group(2) if m else ""
    m = _re.search(r'热号金胆.*(\d+).*(命中|未命中)', last_section)
    result["last_review_hot_gold"] = m.group(2) if m else ""
    m = _re.search(r'组合中2.*?(\d+组)', last_section)
    result["last_review_combo"] = m.group(1) if m else ""
    m = _re.search(r'温号池.*?(\d+/\d+)', last_section)
    result["last_review_warm"] = m.group(1) if m else ""
    return result


def parse_gemini():
    """解析 gemini选2-预测 最新预测（K8-Quant 双算法：算法1 峡谷/香农 + 算法2 齿缝/真空）"""
    summary_file = BASE_DIR / "数据汇总复盘" / "gemini金银铜数据分析-汇总.txt"
    if not summary_file.exists():
        return {"error": "无gemini汇总文件", "name": "gemini选2-预测"}
    content = _read_file_safe(summary_file)
    if not content:
        return {"error": "gemini汇总文件为空", "name": "gemini选2-预测"}
    result = {"name": "gemini选2-预测", "file": summary_file.name}
    # 最新日期键（文件头部第一个 YYYYMMDD：）
    m = _re.search(r'(?m)^(\d{8})：', content)
    date_key = m.group(1) if m else ""
    result["target_period"] = date_key
    # 取最新日期键所在块
    block = content
    if m:
        start = m.start()
        nxt = _re.search(r'(?m)^\d{8}：', content[start + 10:])
        block = content[start:start + 10 + (nxt.start() if nxt else len(content) - start - 10)]
    # 算法1
    m = _re.search(r'首席金胆：(\d+)', block)
    result["algo1_gold"] = int(m.group(1)) if m else None
    m = _re.search(r'次席银胆：(\d+)', block)
    result["algo1_silver"] = int(m.group(1)) if m else None
    m = _re.search(r'强力铜胆：(\d+)', block)
    result["algo1_copper"] = int(m.group(1)) if m else None
    m = _re.search(r'核心 4 码主推组：([\d, ]+)', block)
    result["algo1_core4"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'终极 5 码防线组：([\d, ]+)', block)
    result["algo1_defense5"] = _extract_nums(m.group(1)) if m else []
    # 算法2
    m = _re.search(r'首席金胆 Top 1 ：\s*(\d+)', block)
    result["algo2_gold"] = int(m.group(1)) if m else None
    m = _re.search(r'次席银胆 Top 2 ：\s*(\d+)', block)
    result["algo2_silver"] = int(m.group(1)) if m else None
    m = _re.search(r'强力铜胆 Top 3 ：\s*(\d+)', block)
    result["algo2_copper"] = int(m.group(1)) if m else None
    m = _re.search(r'核心 4 码主推组 ：\s*([\d, ]+)', block)
    result["algo2_core4"] = _extract_nums(m.group(1)) if m else []
    m = _re.search(r'终极 5 码防线组 ：\s*([\d, ]+)', block)
    result["algo2_defense5"] = _extract_nums(m.group(1)) if m else []
    # 铁血纪律区（做空）
    m = _re.search(r'铁血纪律区(?: \(坚决做空\))?[：:]\s*([^\n。]*)', block)
    result["kill_zones"] = _extract_nums(m.group(1)) if m else []
    # 上期复盘（从 JSON 记忆补算，见 _enrich_with_dynamic_review）
    return result


def parse_pointtrack():
    """解析 点位期数-追踪 最新预测（读取 output/点位每日分析_*.md 可复制选号）"""
    out_dir = BASE_DIR / "点位期数-追踪" / "output"
    result = {"name": "点位期数-追踪"}
    if not out_dir.exists():
        return {"error": "无输出目录", "name": "点位期数-追踪"}
    md_files = sorted(out_dir.glob("点位每日分析_*_T*.md"), key=lambda p: p.stat().st_mtime)
    if not md_files:
        return {"error": "无 Markdown 报告", "name": "点位期数-追踪"}
    content = _read_file_safe(md_files[-1])
    # 目标期
    m = _re.search(r'目标期 T\s*\|\s*(\d+)', content) or _re.search(r'目标期 (\d+)', content)
    result["target_period"] = m.group(1) if m else ""
    # 强共振点位
    m = _re.search(r'★ 强共振点位（≥3路信号，最可能开出，优先级最高）\n([^\n]+)', content)
    result["strong_points"] = _extract_nums(m.group(1)) if m else []
    # 综合评估点位（按共振度降序）
    m = _re.search(r'★ 综合评估点位（≥1路信号，按共振度降序）\n([^\n]+)', content)
    result["eval_points"] = _extract_nums(m.group(1)) if m else []
    # 共振度分级
    m = _re.search(r'强共振点位\(≥3路\)\*\*[：:]\s*(\d+)\s*个', content)
    result["strong_count"] = int(m.group(1)) if m else None
    # 上期复盘区分力（若报告含复盘节）
    m = _re.search(r'强共振区分力指数\s*=\s*([\d.]+x)', content)
    result["last_review_discrim"] = m.group(1) if m else ""
    return result


def parse_aggregate():
    """解析 数据汇总复盘 最新聚合推荐"""
    agg_dir = BASE_DIR / "数据汇总复盘" / "logs"
    files = sorted(agg_dir.glob("分区深度聚合推荐_*.txt"), reverse=True)
    if not files:
        return {"error": "无聚合报告", "name": "数据汇总复盘"}
    content = _read_file_safe(files[0])[:3000]
    result = {"name": "数据汇总复盘", "file": files[0].name}
    m = _re.search(r'今日目标期\s*(\d+)', content)
    result["target_period"] = m.group(1) if m else ""
    m = _re.search(r'核心定胆主推\(\d+码\)[:：]\s*([\d\s]+)', content)
    result["core_dans"] = [int(x) for x in m.group(1).split()] if m else []
    m = _re.search(r'分区主推号码\(\d+码\)[:：]\s*([\d\s]+)', content)
    result["zone_picks"] = [int(x) for x in m.group(1).split()] if m else []
    m = _re.search(r'防守号码\(\d+码\)[:：]\s*([\d\s]*)', content)
    result["defense"] = [int(x) for x in m.group(1).split()] if m else []
    m = _re.search(r'关注号码\(\d+码\)[:：]\s*([\d\s]+)', content)
    result["watch"] = [int(x) for x in m.group(1).split()] if m else []
    m = _re.search(r'历史稳定命中号.*?[:：]\s*([\d\s]+)', content)
    result["stable_hits"] = [int(x) for x in m.group(1).split()] if m else []
    m = _re.search(r'绝对胆码.*?[:：]\s*([\d\s]+)', content)
    result["matrix_bankers"] = [int(x) for x in m.group(1).split()] if m else []
    m = _re.search(r'优质拖码.*?[:：]\s*([\d\s]+)', content)
    result["matrix_runners"] = [int(x) for x in m.group(1).split()] if m else []
    m = _re.search(r'市场状态.*?[:：]\s*(\S+)', content)
    result["market_state"] = m.group(1) if m else ""
    # === 上期复盘 ===
    m = _re.search(r'核心定胆.*?(\d+/\d+).*?Lift.*?([\d.]+x)', content)
    result["last_review_core"] = m.group(1) if m else ""
    result["last_review_core_lift"] = m.group(2) if m else ""
    m = _re.search(r'分区主推.*?(\d+/\d+).*?Lift.*?([\d.]+x)', content)
    result["last_review_zone"] = m.group(1) if m else ""
    result["last_review_zone_lift"] = m.group(2) if m else ""
    m = _re.search(r'综合.*?(\d+/\d+).*?Lift.*?([\d.]+x)', content)
    result["last_review_total"] = m.group(1) if m else ""
    result["last_review_total_lift"] = m.group(2) if m else ""
    m = _re.search(r'Evolution.*?FDR.*?[:：=]\s*([\d.]+)', content)
    result["evolution_fdr"] = m.group(1) if m else ""
    m = _re.search(r'连败.*?(\d+)', content)
    result["evolution_fail"] = m.group(1) if m else ""
    return result


def _get_sub_nums(sub_result, key):
    """获取子系统的推荐号码集合"""
    if "error" in sub_result:
        return set()
    if key == "data":
        return set(sub_result.get("trinity_top5", []) + sub_result.get("golden_core", []))
    elif key == "killseeker":
        return set(sub_result.get("keep_numbers", []))
    elif key == "points":
        return set(sub_result.get("top10", []) + sub_result.get("core5", []))
    elif key == "lstm":
        s = set(sub_result.get("top10", []))
        if sub_result.get("gold"): s.add(sub_result["gold"])
        return s
    elif key == "abc":
        return set(sub_result.get("combined_pool", [])[:10])
    elif key == "dan2":
        s = set()
        if sub_result.get("gold"): s.add(sub_result["gold"])
        if sub_result.get("hot_gold"): s.add(sub_result["hot_gold"])
        return s
    elif key == "gemini":
        s = set(sub_result.get("algo1_core4", []) + sub_result.get("algo1_defense5", [])
                + sub_result.get("algo2_core4", []) + sub_result.get("algo2_defense5", []))
        for k in ("algo1_gold", "algo1_silver", "algo1_copper", "algo2_gold", "algo2_silver", "algo2_copper"):
            if sub_result.get(k): s.add(sub_result[k])
        return s
    elif key == "pointtrack":
        # 点位追踪：强共振点位(≥3路)为核心信号，综合评估点位(≥1路)为参考
        return set(sub_result.get("strong_points", []) + sub_result.get("eval_points", [])[:10])
    return set()


def _enrich_with_dynamic_review(results):
    """为复盘数据为空的子系统动态计算命中情况"""
    prev_period, prev_draw = _get_prev_draw()
    if not prev_draw:
        return results

    # ── Points: 从 prediction_logs.txt 读取上期预测 ──
    pts = results.get("points", {})
    if isinstance(pts, dict) and "error" not in pts:
        if not pts.get("last_review_zone"):
            log_file = BASE_DIR / "重点点位分析" / "logs" / "prediction_logs.txt"
            content = _read_file_safe(log_file)
            if content:
                entries = content.split('-' * 40)
                non_empty = [e for e in entries if len(e.strip()) > 20]
                # 找到倒数第二个有效条目（上期预测）
                if len(non_empty) >= 2:
                    prev_entry = non_empty[-2]
                    prev_top10 = []
                    m = _re.search(r'精选十码:\s*\[([^\]]+)\]', prev_entry)
                    if m:
                        prev_top10 = _extract_nums(m.group(1))
                    prev_core5 = []
                    for m in _re.finditer(r'#\d+\s+点位\[\d+\].*?最佳号码:\[(\d+)\]', prev_entry):
                        prev_core5.append(int(m.group(1)))
                    prev_core5 = prev_core5[:5]
                    if prev_top10:
                        r = _compute_review(prev_top10, prev_draw)
                        if r:
                            pts["last_review_top10"] = r["hits"]
                            pts["last_review_top10_lift"] = r["lift"]
                    if prev_core5:
                        r = _compute_review(prev_core5, prev_draw)
                        if r:
                            pts["last_review_core5"] = r["hits"]
                            pts["last_review_core5_lift"] = r["lift"]
                    pts["review_actual"] = sorted(prev_draw)

    # ── LSTM: 从上期预测文件读取 ──
    lst = results.get("lstm", {})
    if isinstance(lst, dict) and "error" not in lst:
        if not lst.get("last_review_top10"):
            pred_dir = BASE_DIR / "双层LSTM" / "outputs" / "predictions"
            # 找到上期预测文件
            if prev_period:
                prev_file = pred_dir / f"prediction_{prev_period}.txt"
                if not prev_file.exists():
                    files = sorted(pred_dir.glob("prediction_*.txt"), reverse=True)
                    if len(files) >= 2:
                        prev_file = files[1]
                    else:
                        prev_file = None
                if prev_file and prev_file.exists():
                    content = _read_file_safe(prev_file)
                    m = _re.search(r'Top10[:：]\s*([\d-]+)', content)
                    prev_top10 = [int(x) for x in m.group(1).split('-') if x.isdigit()] if m else []
                    m = _re.search(r'金胆[:：]\s*(\d+)', content)
                    prev_gold = int(m.group(1)) if m else None
                    m = _re.search(r'银胆[:：]\s*(\d+)', content)
                    prev_silver = int(m.group(1)) if m else None
                    m = _re.search(r'铜胆[:：]\s*(\d+)', content)
                    prev_bronze = int(m.group(1)) if m else None
                    if prev_top10:
                        r = _compute_review(prev_top10, prev_draw)
                        if r:
                            lst["last_review_top10"] = r["hits"]
                            lst["last_review_top10_lift"] = r["lift"]
                    if prev_gold is not None:
                        lst["last_review_gold"] = "✅" if prev_gold in prev_draw else "❌"
                    if prev_silver is not None:
                        lst["last_review_silver"] = "✅" if prev_silver in prev_draw else "❌"
                    if prev_bronze is not None:
                        lst["last_review_bronze"] = "✅" if prev_bronze in prev_draw else "❌"

    # ── 顺口溜(原abc位): 复盘已在 parse_abc / latest_predict 中给出 ──
    abc = results.get("abc", {})
    if isinstance(abc, dict) and "error" not in abc:
        # 若主报告无复盘段落，可用 C 报告选十对上期开奖补算
        if not abc.get("last_review_c") and abc.get("version_c_top10"):
            r = _compute_review(abc["version_c_top10"], prev_draw)
            if r:
                abc["last_review_c"] = r["hits"]
                abc["last_review_c_lift"] = r["lift"]

    # ── Dan2: 从 prediction_logs.txt 读取上期预测 ──
    dn2 = results.get("dan2", {})
    if isinstance(dn2, dict) and "error" not in dn2:
        if not dn2.get("last_review_gold"):
            log_file = BASE_DIR / "定金选2-分析" / "logs" / "prediction_logs.txt"
            content = _read_file_safe(log_file)
            if content:
                period_positions = [m.start() for m in _re.finditer(r'预测期号[:：]\s*\d+', content)]
                if len(period_positions) >= 2:
                    prev_section = content[period_positions[-2]:period_positions[-2] + 3000]
                    m = _re.search(r'动态金胆[:：]\s*(\d+)', prev_section)
                    prev_gold = int(m.group(1)) if m else None
                    m = _re.search(r'热号金胆\s*\[(\d+)\]', prev_section)
                    prev_hot_gold = int(m.group(1)) if m else None
                    if prev_gold is not None:
                        dn2["last_review_gold"] = "命中" if prev_gold in prev_draw else "未命中"
                    if prev_hot_gold is not None:
                        dn2["last_review_hot_gold"] = "命中" if prev_hot_gold in prev_draw else "未命中"
                    # 检查组合中2
                    combo_hits = 0
                    for m in _re.finditer(r'推荐组合\s*[:：]\s*\[(\d+)-(\d+)\]', prev_section):
                        a, b = int(m.group(1)), int(m.group(2))
                        if a in prev_draw and b in prev_draw:
                            combo_hits += 1
                    dn2["last_review_combo"] = f"{combo_hits}组"

    # ── Gemini: 从上期汇总块读取预测，对照上期开奖 ──
    gmi = results.get("gemini", {})
    if isinstance(gmi, dict) and "error" not in gmi:
        if not gmi.get("last_review_gold"):
            summary_file = BASE_DIR / "数据汇总复盘" / "gemini金银铜数据分析-汇总.txt"
            content2 = _read_file_safe(summary_file)
            if content2:
                date_keys = [m.start() for m in _re.finditer(r'(?m)^(\d{8})：', content2)]
                if len(date_keys) >= 2:
                    prev_start = date_keys[1]
                    prev_block = content2[prev_start:prev_start + 2000]
                    prev_gold = None
                    m = _re.search(r'首席金胆[^\n]*?[：:]\s*(\d+)', prev_block)
                    if m:
                        prev_gold = int(m.group(1))
                    prev_core4 = []
                    m = _re.search(r'核心 4 码主推组[^：:]*[：:]?\s*([\d, ]+)', prev_block)
                    if not m:
                        m = _re.search(r'核心 4 码主推组 ：\s*([\d, ]+)', prev_block)
                    if m:
                        prev_core4 = _extract_nums(m.group(1))
                    if prev_gold is not None:
                        gmi["last_review_gold"] = "命中" if prev_gold in prev_draw else "未命中"
                    if prev_core4:
                        r = _compute_review(prev_core4, prev_draw)
                        if r:
                            gmi["last_review_core4"] = r["hits"]
                            gmi["last_review_core4_lift"] = r["lift"]
                    gmi["review_actual"] = sorted(prev_draw)

    return results


def collect_all_predictions():
    """收集所有子系统的最新预测结果"""
    parsers = [
        ("data", parse_data_subsystem),
        ("killseeker", parse_killseeker),
        ("points", parse_points),
        ("lstm", parse_lstm),
        ("abc", parse_abc),
        ("dan2", parse_dan2),
        ("pointtrack", parse_pointtrack),
        ("gemini", parse_gemini),
        ("aggregate", parse_aggregate),
    ]
    results = {}
    for key, parser in parsers:
        try:
            results[key] = parser()
        except Exception as e:
            results[key] = {"error": str(e), "name": key}
    # 动态复盘补全
    results = _enrich_with_dynamic_review(results)
    # 跨系统共识分析
    all_top_nums = {}
    for key in ["data", "killseeker", "points", "lstm", "abc", "dan2", "pointtrack", "gemini"]:
        nums = _get_sub_nums(results.get(key, {}), key)
        for n in nums:
            if 1 <= n <= 80:
                all_top_nums[n] = all_top_nums.get(n, 0) + 1
    consensus = sorted(all_top_nums.items(), key=lambda x: (-x[1], x[0]))
    results["_consensus"] = [
        {"number": n, "count": c, "systems": [k for k in ["data","killseeker","points","lstm","abc","dan2","pointtrack","gemini"] if n in _get_sub_nums(results.get(k, {}), k)]}
        for n, c in consensus if c >= 2
    ][:20]
    return results


# ═══════════════════════════════════════════════════════════
# Flask 路由
# ═══════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/help')
def help_page():
    return render_template('help.html')


@app.route('/manifest.json')
def manifest():
    # 使用 application/manifest+json MIME（PWA 规范推荐的正确类型）
    manifest_data = {
        "name": "KL8 每日全流程调度",
        "short_name": "KL8调度",
        "description": "快乐8每日6子系统全流程调度PWA",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f0f1a",
        "theme_color": "#6c5ce7",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }
    return Response(json.dumps(manifest_data, ensure_ascii=False, indent=2),
                    mimetype='application/manifest+json')


# ── 访问控制：共享 Token 鉴权（P1-5） ──
# 仅保护 /api/ 接口（重型任务触发、文件覆盖都走 API）；页面/静态资源放行。
# 若未配置 TOKEN 则完全开放，兼容旧部署。
@app.before_request
def _guard_api_token():
    if not TOKEN:
        return None
    if not request.path.startswith("/api/"):
        return None
    provided = request.headers.get("X-Api-Token", "") or request.args.get("token", "")
    if provided == TOKEN:
        return None
    return jsonify({"error": "未授权：缺少或错误的访问令牌（TOKEN）"}), 401


@app.route('/sw.js')
def service_worker():
    return send_from_directory('static/js', 'sw.js', mimetype='application/javascript')


# ── SSE: 实时事件流 ──
@app.route('/api/stream/<session_id>')
def sse_stream(session_id):
    """Server-Sent Events 端点 — 真正的实时推送"""
    state = sessions.get(session_id)
    if not state:
        return jsonify({"error": "会话不存在"}), 404

    q = queue.Queue(maxsize=2000)
    with sse_lock:
        state.sse_queues.append(q)

    def generate():
        # 先发送当前状态快照
        snapshot = {
            "type": "snapshot",
            "data": state.to_dict(),
            "ts": datetime.now().strftime("%H:%M:%S")
        }
        yield f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"

        try:
            while True:
                try:
                    event = q.get(timeout=30)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    # 心跳保活
                    yield f"data: {json.dumps({'type': 'heartbeat', 'ts': datetime.now().strftime('%H:%M:%S')})}\n\n"
        except GeneratorExit:
            pass
        finally:
            with sse_lock:
                if q in state.sse_queues:
                    state.sse_queues.remove(q)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


# ── API: 会话管理 ──
@app.route('/api/session', methods=['POST'])
def create_session():
    data = request.get_json(silent=True) or {}
    state = get_or_create_session(data.get("session_id"))
    return jsonify(state.to_dict())


@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    state = sessions.get(session_id)
    if not state:
        return jsonify({"error": "会话不存在"}), 404
    return jsonify(state.to_dict())


# ── API: 今日点位（只读展示，v3.0 全自动流程无需手动确认） ──
@app.route('/api/daily-points', methods=['GET'])
def get_daily_points():
    return jsonify(read_latest_daily_points())


# ── API: 一键全自动流水线（v3.0 核心） ──
@app.route('/api/execute/pipeline', methods=['POST'])
def execute_pipeline_api():
    """一键流水线：每日模式或批量补跑历史日期。

    body: {session_id, force?, date_start?, date_end?}
     - 不传日期 → 每日模式（今日 9 子系统，行为不变）
     - date_start/date_end（YYYY-MM-DD，均需提供，≤31 天）→ 批量补跑
       （逐日截断历史数据模拟当天跑一轮，注入 KL8_TARGET_DATE，跳过数据抓取与汇总）"""
    data = request.get_json(silent=True) or {}
    state = get_or_create_session(data.get("session_id", ""))
    if state.pipeline_status == "running":
        return jsonify({"error": "流水线已在执行中，请等待完成或先停止"}), 409
    force = bool(data.get("force", False))
    date_start = (data.get("date_start") or "").strip()
    date_end = (data.get("date_end") or "").strip()

    if date_start or date_end:
        # 补跑模式：需同时提供起止日期
        if not (date_start and date_end):
            return jsonify({"error": "补跑需同时提供起始与结束日期（都留空则跑今日）"}), 400
        try:
            ds = datetime.strptime(date_start, "%Y-%m-%d").date()
            de = datetime.strptime(date_end, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "日期格式应为 YYYY-MM-DD"}), 400
        if de < ds:
            return jsonify({"error": "结束日期不能早于起始日期"}), 400
        days = (de - ds).days + 1
        if days > BACKFILL_MAX_DAYS:
            return jsonify({"error": f"补跑范围最多 {BACKFILL_MAX_DAYS} 天（当前 {days} 天）"}), 400
        t = threading.Thread(target=execute_backfill, args=(state, ds, de, force))
        t.daemon = True
        t.start()
        return jsonify({"success": True, "session_id": state.session_id, "force": force,
                        "backfill": True, "date_start": date_start, "date_end": date_end, "days": days})

    t = threading.Thread(target=execute_pipeline, args=(state, force))
    t.daemon = True
    t.start()
    return jsonify({"success": True, "session_id": state.session_id, "force": force})


# ── API: 停止流水线（结束当前子进程树，后续系统不再启动） ──
@app.route('/api/pipeline/stop', methods=['POST'])
def stop_pipeline_api():
    data = request.get_json(silent=True) or {}
    state = get_or_create_session(data.get("session_id", ""))
    if state.pipeline_status != "running":
        return jsonify({"error": "流水线未在运行"}), 400
    state.stop_requested = True
    proc = state.current_proc
    if proc is not None:
        _kill_process_tree(proc)
        append_log(state, "pipeline", f"⏹ 已结束当前子进程 (taskkill /F /T /PID {proc.pid})")
    else:
        append_log(state, "pipeline", "⏹ 已请求停止流水线（将在当前子系统结束后中断）")
    return jsonify({"success": True})


# ── API: gemini 汇总文件只读预览 ──
@app.route('/api/gemini', methods=['GET'])
def get_gemini():
    return jsonify(read_gemini_file())


# ── API: 预测结果汇总 ──
@app.route('/api/predictions', methods=['GET'])
def get_predictions():
    """获取所有子系统的最新预测结果"""
    try:
        results = collect_all_predictions()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/predictions/export', methods=['GET'])
def export_predictions():
    """导出预测结果为纯文本。
    注意：前端「导出文件」按钮使用客户端 Blob 生成，此端点当前无调用，保留备用。"""
    try:
        results = collect_all_predictions()
        lines = []
        lines.append("=" * 60)
        lines.append("  KL8 预测结果汇总 — 导出时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("=" * 60)
        # 共识号码
        consensus = results.get("_consensus", [])
        if consensus:
            lines.append("\n🔥 跨系统共识号码 (≥2系统推荐)")
            lines.append("-" * 40)
            for c in consensus:
                lines.append(f"  {c['number']:02d} | {c['count']}系统 | {', '.join(c['systems'])}")
        # 各子系统
        sub_names = {
            "data": "Data分析引擎", "killseeker": "KillSeeker杀号",
            "points": "重点点位分析",
            "lstm": "双层LSTM", "abc": "顺口溜",
            "dan2": "定金选2-分析", "pointtrack": "点位期数-追踪",
            "gemini": "gemini选2-预测",
            "aggregate": "数据汇总复盘"
        }
        for key in ["data", "killseeker", "points", "lstm", "abc", "dan2", "pointtrack", "gemini", "aggregate"]:
            d = results.get(key, {})
            if not d or "error" in d:
                continue
            lines.append(f"\n{'─' * 40}")
            lines.append(f"  {sub_names.get(key, key)} — 第{d.get('target_period','?')}期")
            lines.append(f"{'─' * 40}")
            # 提取所有数字型字段
            for k, v in d.items():
                if k.startswith("_") or k in ("name", "file", "target_period", "error"):
                    continue
                if isinstance(v, list):
                    if v and isinstance(v[0], int):
                        lines.append(f"  {k}: {v}")
                    elif v and isinstance(v[0], dict):
                        for item in v:
                            lines.append(f"  {k}: {item}")
                elif isinstance(v, dict):
                    for dk, dv in v.items():
                        lines.append(f"  {k}.{dk}: {dv}")
                elif v:
                    lines.append(f"  {k}: {v}")
        text = "\n".join(lines)
        return Response(text, mimetype='text/plain',
                       headers={'Content-Disposition': 'attachment; filename=predictions_export.txt'})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/summary', methods=['GET'])
def get_summary():
    """预测结果汇总（10段可复制格式），供前端 一键复制/导出"""
    try:
        import summary_report
        target = None
        d = summary_report.sec_data()
        if isinstance(d, tuple) and len(d) > 2:
            target = d[2]
        return jsonify({"text": summary_report.build(target)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: 获取日志（兼容旧接口） ──
# 注意：前端日志走 SSE 实时推送，此轮询接口当前无调用，保留备用。
@app.route('/api/logs/<session_id>/<int:step>', methods=['GET'])
def get_logs(session_id, step):
    state = sessions.get(session_id)
    if not state:
        return jsonify({"error": "会话不存在"}), 404
    logs = state.logs.get(step, [])
    after = int(request.args.get("after", 0))
    return jsonify({"step": step, "count": len(logs), "logs": logs[after:]})


# ── API: 获取子系统日志 ──
# 注意：前端日志走 SSE 实时推送，此轮询接口当前无调用，保留备用。
@app.route('/api/sub-logs/<session_id>/<sub_id>', methods=['GET'])
def get_sub_logs(session_id, sub_id):
    state = sessions.get(session_id)
    if not state:
        return jsonify({"error": "会话不存在"}), 404
    logs = state.subsystem_logs.get(sub_id, [])
    after = int(request.args.get("after", 0))
    return jsonify({"sub_id": sub_id, "count": len(logs), "logs": logs[after:]})


# ── API: 流水线配置 ──
# 注意：前端子系统列表为静态常量 PIPELINE（与后端一致），此接口当前无调用，保留备用。
@app.route('/api/subsystems', methods=['GET'])
def get_subsystems():
    return jsonify(PIPELINE)


# ── API: 重置 ──
# 注意：前端通过「清空本地会话/刷新」机制处理，此接口当前无调用，保留备用。
@app.route('/api/session/<session_id>/reset', methods=['POST'])
def reset_session(session_id):
    if session_id in sessions:
        del sessions[session_id]
    return jsonify({"success": True})


if __name__ == '__main__':
    print("=" * 60)
    print("  KL8 每日全流程调度 PWA v3.0 (一键全自动流水线 + SSE实时推送)")
    print("  10子系统顺序: data → 双层LSTM → 顺口溜 → 重点点位分析 → 定金选2-分析")
    print("               → KillSeeker → 点位期数-追踪 → gemini选2-预测 → 数据汇总复盘 → 预测结果汇总")
    print("  http://localhost:5888")
    print("=" * 60)
    # debug=False 防止热重载丢失会话
    app.run(host='0.0.0.0', port=5888, debug=False, threaded=True, use_reloader=False)
