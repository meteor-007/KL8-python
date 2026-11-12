# -*- coding: utf-8 -*-
"""日志、数据新鲜度与运行心跳（§11.4）。"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date as _date
from datetime import datetime
from pathlib import Path

_LOGGER_NAME = "kl8"
_configured = False


def setup(log_dir: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    """初始化日志：文件 + stdout。保留 90 天由 rotate() 负责。"""
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    stream.setLevel(level)
    logger.addHandler(stream)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(
            log_dir / f"kl8_{datetime.now():%Y%m%d}.log", encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(level)
        logger.addHandler(fh)

    _configured = True
    return logger


def log() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        return setup()
    return logger


def info(msg: str) -> None:
    log().info(msg)


def warn(msg: str) -> None:
    log().warning(msg)


def error(msg: str) -> None:
    log().error(msg)


def rotate(log_dir: Path, keep_days: int = 90) -> int:
    """删除超过保留期的日志文件，返回删除数量。"""
    if not log_dir.exists():
        return 0
    cutoff = datetime.now().timestamp() - keep_days * 86400
    removed = 0
    for f in log_dir.glob("kl8_*.log"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            continue
    return removed


# ── 数据新鲜度 ────────────────────────────────────────────────

def staleness(latest_date: _date | None, cfg) -> tuple[str, str]:
    """返回 (级别, 说明)。级别 ∈ ok | warn | critical | unknown。"""
    if latest_date is None:
        return "unknown", "无开奖数据"
    days = (_date.today() - latest_date).days
    warn_d = int(cfg.thresholds.staleness_days_warn or 2)
    crit_d = int(cfg.thresholds.staleness_days_critical or 4)
    if days >= crit_d:
        return "critical", f"最新开奖 {latest_date} 距今日 {days} 天，数据严重滞后"
    if days >= warn_d:
        return "warn", f"最新开奖 {latest_date} 距今日 {days} 天（可能为休市期）"
    return "ok", f"最新开奖 {latest_date}（{days} 天前）"


# ── 运行心跳 ──────────────────────────────────────────────────

def write_heartbeat(state_dir: Path, payload: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "last_run.json"
    payload = dict(payload)
    payload["written_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    except OSError as exc:
        warn(f"写入运行心跳失败: {exc}")


def read_heartbeat(state_dir: Path) -> dict:
    path = state_dir / "last_run.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def reconcile(state_dir: Path, key: str, current: int) -> str:
    """§8.5 对账：共享档案期数比上次运行**减少** → 疑似被外部覆盖。

    返回告警文案（供报告顶部展示）；无异常返回空串。
    """
    prev = read_heartbeat(state_dir).get(key)
    if isinstance(prev, int) and current < prev:
        msg = f"共享档案期数由 {prev} 减至 {current}，疑似被外部覆盖（§8.5）"
        warn(msg)
        return msg
    return ""
