from __future__ import annotations
# -*- coding: utf-8 -*-
"""Nightly daily entry — delegates to run_nightly_pipeline.

2026-10-22 缺陷修复 (Bug#11)：原实现直接 ``runpy.run_module("backend.pipeline...")``，
一旦按**文件路径**被调用（`python backend/pipeline/run_nightly_daily.py`，这正是
Windows 计划任务 `K8Quant_Nightly_2200` 的调用方式），sys.path[0] 会变成
``backend/pipeline``，项目根不在搜索路径上 → `ModuleNotFoundError: No module named 'backend'`。
实测计划任务 LastTaskResult=2 (ERROR_FILE_NOT_FOUND)、调度器配置停在
``last_status=FAILED / last_run_date=2026-09-20``，即夜间自动化已停摆一个月。

现先自举项目根与 backend 目录进 sys.path，再直接调用流水线函数；
流水线返回的 ``status`` 反映各模块真实成败，失败时本进程以非零码退出并写回 FAILED。

2026-10-22 状态回写修复 (Bug#15)：计划任务直接调本脚本，**绕过了** NightlyScheduler，
导致 ``backend/config/scheduler_config.json`` 的 last_run_date / last_status 永远停在
2026-09-20 的失败态 —— 前端的"夜间调度器"面板据此显示"失败/一个月前"，与真实执行情况
严重不符（实测 10-22 15:34 计划任务已 LastTaskResult=0 成功跑完整条流水线）。
现于进程内成对写入开始/结束状态，使前端面板与 Windows 计划任务真实执行情况一致。
"""
import json
import os
import sys
from datetime import datetime

_PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = os.path.dirname(os.path.dirname(_PIPELINE_DIR))   # backend/pipeline -> 项目根
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")

for _p in (_PROJ_DIR, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SCHED_CFG = os.path.join(_BACKEND_DIR, "config", "scheduler_config.json")


def _update_scheduler_state(status: str, message: str, finished: bool = False) -> None:
    """把本次真实执行结果回写到 scheduler_config.json（失败静默，绝不阻断主流程）。"""
    try:
        data = {}
        if os.path.exists(_SCHED_CFG):
            with open(_SCHED_CFG, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        data.setdefault("enabled", True)
        data.setdefault("target_time", "22:00")
        data["last_status"] = status
        data["last_message"] = message
        data["last_run_date"] = datetime.now().strftime("%Y-%m-%d")
        data["last_trigger"] = "windows_scheduled_task"
        # 2026-10-22 修复：必须记录**精确启动时刻**，否则 watchdog 只能拿 last_run_date
        # (纯日期, 解析成当天 00:00) 去判断 RUNNING 时长 —— 下午启动的任务会被
        # 误判成"已卡死十几小时"而发出假告警（实测 16:00 启动触发过一次误报）。
        if status == "RUNNING":
            data["last_started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if finished:
            data["last_finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(_SCHED_CFG), exist_ok=True)
        with open(_SCHED_CFG, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _alert_on_failure(exc: Exception) -> None:
    """流水线自身抛异常时**立即**告警（不必等 watchdog 轮询）。

    2026-10-22 告警闭环：本次事故（夜间停摆一个月）的教训是"失败必须有人知道"。
    进程内失败即时告警 + watchdog 兜底扫描陈旧态，两者互补：
    前者抓住"跑了但崩了"，后者抓住"根本没跑"。失败静默，绝不影响退出码语义。
    """
    try:
        from backend.utils.alerting import send_alert
        import traceback as _tb
        send_alert(
            key="nightly_failed",
            title="夜间流水线执行失败",
            content=(
                "夜间全自动流水线在执行中抛出异常。\n\n"
                f"**异常类型**：`{type(exc).__name__}`\n"
                f"**异常信息**：{str(exc)[:500]}\n\n"
                "**调用栈尾部**\n```\n"
                + "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))[-1200:]
                + "\n```"
            ),
            level="critical",
        )
    except Exception:
        pass


def _load_scheduler_config() -> dict:
    try:
        if os.path.exists(_SCHED_CFG):
            with open(_SCHED_CFG, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


class _TeeStream:
    """把输出同时写到控制台与日志文件；无控制台（计划任务）时仅落盘。"""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, text):
        for st in self._streams:
            try:
                st.write(text)
            except Exception:
                pass
        return len(text)

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass

    def isatty(self):
        return False

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def reconfigure(self, **kwargs):
        for st in self._streams:
            if hasattr(st, "reconfigure"):
                try:
                    st.reconfigure(**kwargs)
                except Exception:
                    pass

    @property
    def encoding(self):
        return getattr(self._streams[0], "encoding", "utf-8")

    @property
    def errors(self):
        return getattr(self._streams[0], "errors", "strict")


def _setup_run_log():
    """把本次运行的全部输出追加到 storage/logs/nightly_YYYYMMDD.log。"""
    log_dir = os.path.join(_PROJ_DIR, "storage", "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"nightly_{datetime.now():%Y%m%d}.log")
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = _TeeStream(sys.stdout, log_file)
        sys.stderr = _TeeStream(sys.stderr, log_file)
        print(f"\n===== nightly run start {datetime.now():%Y-%m-%d %H:%M:%S} =====")
        return log_path
    except Exception:
        return None


if __name__ == "__main__":
    _setup_run_log()
    _force = "--force" in sys.argv[1:]
    _cfg = _load_scheduler_config()
    if _cfg.get("enabled", True) is False and not _force:
        print("[SKIP] scheduler_config.enabled=false，本次夜间任务不执行（--force 可强制）。")
        sys.exit(0)

    from backend.utils.nightly_lock import acquire_nightly_lock, release_nightly_lock

    _owner = "windows_task"
    _locked, _lock_msg = acquire_nightly_lock(_owner)
    if not _locked:
        print(f"[SKIP] {_lock_msg}")
        sys.exit(0)

    try:
        _update_scheduler_state("RUNNING", "Windows 计划任务已触发，夜间全自动流水线执行中...")
        _t0 = datetime.now()
        try:
            from backend.pipeline.run_nightly_pipeline import run_nightly_pipeline
            _res = run_nightly_pipeline(
                verbose=True,
                with_research="--with-research" in sys.argv[1:],
            )
            if str(_res.get("status", "")).upper() != "SUCCESS":
                _errs = _res.get("errors") or []
                _detail = "; ".join(
                    f"{e.get('label')}: {str(e.get('error'))[:120]}" for e in _errs[:5]
                ) or "未知模块失败"
                raise RuntimeError(f"流水线内 {len(_errs)} 个模块执行失败（{_detail}）")
        except Exception as _e:
            _update_scheduler_state("FAILED", f"❌ 夜间流水线执行异常: {_e}", finished=True)
            _alert_on_failure(_e)
            sys.exit(1)
        _secs = (datetime.now() - _t0).total_seconds()
        _update_scheduler_state("SUCCESS", f"✅ 夜间流水线执行圆满成功 (耗时: {_secs:.0f}s)", finished=True)
        # 成功后跑一次健康检查：若之前处于告警态，这里会发出"已恢复"闭环通知
        try:
            from backend.utils.nightly_watchdog import run_watchdog
            run_watchdog(notify=True)
        except Exception:
            pass
    finally:
        release_nightly_lock(_owner)


