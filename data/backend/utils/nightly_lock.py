# -*- coding: utf-8 -*-
"""夜间流水线跨进程运行锁。

Windows 计划任务（run_nightly_daily.py）和 Web 后端内置调度器
（nightly_scheduler.py）都会在 22:00 触发同一条流水线。没有锁时两者会并发
改写开奖账本、Excel 与 scheduler_config.json。本模块用 O_EXCL 创建锁文件
实现原子抢占；超过 stale_hours 的锁视为崩溃残留，允许接管。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from backend.utils.paths import get_cache_dir

LOCK_FILE = os.path.join(get_cache_dir(), "nightly_run.lock")
DEFAULT_STALE_HOURS = 2.0


def _read_lock() -> dict:
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _is_fresh(info: dict, stale_hours: float) -> bool:
    started = info.get("started_at")
    if not started:
        return False
    try:
        dt = datetime.fromisoformat(str(started))
    except ValueError:
        return False
    return datetime.now() - dt < timedelta(hours=stale_hours)


def acquire_nightly_lock(owner: str, stale_hours: float = DEFAULT_STALE_HOURS) -> tuple:
    """返回 (是否抢到锁, 说明)。已被其他实例持有时返回 False。"""
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    payload = {
        "owner": owner,
        "pid": os.getpid(),
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    for _ in range(2):
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True, "acquired"
        except FileExistsError:
            info = _read_lock()
            if _is_fresh(info, stale_hours):
                return False, (
                    f"已有夜间流水线在运行 (owner={info.get('owner')}, "
                    f"pid={info.get('pid')}, started={info.get('started_at')})"
                )
            try:
                os.remove(LOCK_FILE)
            except FileNotFoundError:
                pass
            except OSError:
                return False, "残留锁无法清除，放弃本次执行"
    return False, "无法获取夜间流水线运行锁"


def release_nightly_lock(owner: str) -> None:
    info = _read_lock()
    if info.get("owner") != owner:
        return
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass
    except OSError:
        pass