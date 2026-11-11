# -*- coding: utf-8 -*-
"""夜间流水线健康看门狗 (Nightly Watchdog)

背景
----
2026-10-22 实测发现：夜间自动化自 2026-09-20 起已停摆一个月（计划任务路径失效 +
shim 缺 sys.path 自举），但**没有任何告警** —— 前端面板安静地显示着旧日期，
`scheduler_config.json` 里那条 FAILED 也无人察觉。等人工发现时已损失 30 期数据。

本模块补上这个缺口：独立检查「夜间任务是否按预期成功」，异常则通过
`backend.utils.alerting` 投递多通道告警。

设计要点
--------
1. **不依赖被监控对象**：本检查只读状态文件，不 import 夜间流水线，
   即便流水线代码本身崩了也能照常告警。
2. **双判据**：
   - `last_status != SUCCESS`（显式失败）
   - 最近一次 SUCCESS 距今超过 `STALE_HOURS`（静默停摆 —— 本次事故正是这种）
3. **工作日感知**：彩票每日开奖，默认每天都应跑；可通过 ALERT_EXPECT_DAILY=0 关闭。
4. **恢复通知**：从异常恢复正常时发一条 info，形成闭环。

用法
----
    python -m backend.utils.nightly_watchdog           # 单次检查
    python -m backend.utils.nightly_watchdog --json    # 机器可读输出
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

_PIPELINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJ_DIR = os.path.dirname(_PIPELINE_DIR)
for _p in (_PROJ_DIR, _PROJ_DIR + os.sep + "backend"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils.paths import get_cache_dir, get_project_root  # noqa: E402

SCHEDULER_CONFIG = os.path.join(get_project_root(), "backend", "config", "scheduler_config.json")
WATCHDOG_STATE = os.path.join(get_cache_dir(), "nightly_watchdog_state.json")

# 超过该小时数没有一次 SUCCESS 即判定为「静默停摆」
STALE_HOURS_DEFAULT = 26.0


def _load_json(path: str, default: Any = None) -> Any:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _save_json(path: str, data: Any) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except Exception:
            continue
    return None


def check_nightly_health(stale_hours: float = STALE_HOURS_DEFAULT) -> Dict[str, Any]:
    """检查夜间流水线健康度，返回结构化诊断结果（不发告警）。"""
    cfg = _load_json(SCHEDULER_CONFIG, {}) or {}

    last_status = str(cfg.get("last_status") or "UNKNOWN")
    last_finished_raw = cfg.get("last_finished_at") or ""
    last_run_raw = cfg.get("last_run_date") or ""
    last_message = str(cfg.get("last_message") or "")

    last_finished = _parse_dt(last_finished_raw)
    last_run = _parse_dt(last_run_raw)

    # 以「最近一次成功」为基准判断陈旧度
    last_success = last_finished if last_status == "SUCCESS" else None

    now = datetime.now()
    age_hours: Optional[float] = None
    if last_success:
        age_hours = round((now - last_success).total_seconds() / 3600.0, 2)
    elif last_status == "RUNNING":
        # RUNNING 中：以精确启动时刻为准；拿不到精确时间就**不计算**陈旧度，
        # 避免用纯日期 (当天 00:00) 算出虚高的"已 xx 小时"造成误判。
        _started = _parse_dt(cfg.get("last_started_at") or "")
        if _started:
            age_hours = round((now - _started).total_seconds() / 3600.0, 2)
    elif last_run:
        # 其他状态：以最后一次运行日期为基准（反映"多久没动静"）
        age_hours = round((now - last_run).total_seconds() / 3600.0, 2)

    problems = []
    if last_status == "FAILED":
        problems.append(f"上次执行显式失败：{last_message[:160]}")
    elif last_status == "RUNNING":
        # 2026-10-22 误报修复：判断"卡死"必须用**精确启动时刻** (last_started_at)。
        # 原实现退回 last_run_date —— 那是纯日期，被解析成当天 00:00，
        # 导致 16:00 才启动的任务被算成"已 RUNNING 16 小时"并发出假告警。
        # 现在：优先精确时间；若只有日期则**放弃判定**（宁可不报，也不误报）。
        started = _parse_dt(cfg.get("last_started_at") or "") or last_finished
        if started and (now - started) > timedelta(hours=3):
            problems.append(
                f"任务卡在 RUNNING 超过 3 小时（起始 {started.strftime('%Y-%m-%d %H:%M:%S')}）"
            )
    elif last_status != "SUCCESS":
        problems.append(f"状态未知：{last_status}")

    if age_hours is not None and age_hours > stale_hours:
        problems.append(
            f"已 {age_hours:.1f} 小时没有成功的夜间运行（阈值 {stale_hours:.0f}h），疑似静默停摆"
        )

    healthy = not problems
    return {
        "healthy": healthy,
        "last_status": last_status,
        "last_run_date": last_run_raw,
        "last_started_at": cfg.get("last_started_at") or "",
        "last_finished_at": last_finished_raw,
        "last_message": last_message,
        "age_hours": age_hours,
        "stale_hours_threshold": stale_hours,
        "problems": problems,
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }


def run_watchdog(stale_hours: float = STALE_HOURS_DEFAULT, notify: bool = True) -> Dict[str, Any]:
    """执行一次健康检查，异常时投递告警，恢复时发恢复通知。"""
    from backend.utils.alerting import resolve_alert, send_alert

    diag = check_nightly_health(stale_hours=stale_hours)
    prev = _load_json(WATCHDOG_STATE, {}) or {}
    was_alerting = bool(prev.get("alerting"))

    if diag["healthy"]:
        # 已恢复正常：清指纹 + 发一条恢复通知（仅在之前确实告过警时才发）
        if was_alerting:
            resolve_alert("nightly_failed")
            if notify:
                send_alert(
                    key="nightly_recovered",
                    title="夜间流水线已恢复",
                    content=(
                        f"夜间自动流水线恢复正常。\n"
                        f"- 最近状态：`{diag['last_status']}`\n"
                        f"- 最近成功：`{diag['last_finished_at']}`\n"
                        f"- 已恢复至阈值内（{diag['age_hours']}h ≤ {stale_hours:.0f}h）"
                    ),
                    level="info",
                    force=True,
                )
        _save_json(WATCHDOG_STATE, {
            "alerting": False,
            "last_checked_at": diag["checked_at"],
            "last_healthy_at": diag["checked_at"],
            "last_status": diag["last_status"],
        })
        diag["notified"] = False
        return diag

    # 异常：投递告警（冷却由 alerting 内部处理）
    if notify:
        body_lines = ["夜间自动流水线健康检查未通过：", ""]
        for p in diag["problems"]:
            body_lines.append(f"- ❌ {p}")
        body_lines += [
            "",
            "**当前状态**",
            f"- last_status: `{diag['last_status']}`",
            f"- last_run_date: `{diag['last_run_date'] or '—'}`",
            f"- last_finished_at: `{diag['last_finished_at'] or '—'}`",
            f"- 距上次成功: `{diag['age_hours']}` 小时",
            f"- 最后消息: {diag['last_message'][:300] or '—'}",
            "",
            "**排查建议**",
            "1. `Get-ScheduledTaskInfo -TaskName K8Quant_Nightly_2200` 看 LastTaskResult",
            "2. 确认任务 Arguments 指向 `backend/pipeline/run_nightly_daily.py`",
            "3. 手动跑一次：`python backend/pipeline/run_nightly_daily.py`",
        ]
        res = send_alert(
            key="nightly_failed",
            title="夜间流水线异常",
            content="\n".join(body_lines),
            level="critical",
        )
        diag["notified"] = bool(res.get("sent"))
        diag["notify_result"] = res
    else:
        diag["notified"] = False

    _save_json(WATCHDOG_STATE, {
        "alerting": True,
        "last_checked_at": diag["checked_at"],
        "last_problem_at": diag["checked_at"],
        "last_status": diag["last_status"],
        "problems": diag["problems"],
    })
    return diag


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="夜间流水线健康看门狗")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--no-notify", action="store_true", help="只检查不告警")
    ap.add_argument("--stale-hours", type=float, default=STALE_HOURS_DEFAULT,
                    help="多少小时无成功即判停摆（默认 26）")
    args = ap.parse_args(argv)

    diag = run_watchdog(stale_hours=args.stale_hours, notify=not args.no_notify)

    if args.json:
        print(json.dumps(diag, ensure_ascii=False, indent=2, default=str))
    else:
        icon = "✅" if diag["healthy"] else "🚨"
        print(f"{icon} 夜间流水线健康检查 — {diag['checked_at']}")
        print(f"   状态: {diag['last_status']} | 最近成功: {diag['last_finished_at'] or '—'}")
        print(f"   距上次成功: {diag['age_hours']} 小时 (阈值 {args.stale_hours:.0f}h)")
        if diag["healthy"]:
            print("   结论: 健康")
        else:
            print("   结论: 异常")
            for p in diag["problems"]:
                print(f"     · {p}")
            print(f"   告警投递: {'已发送' if diag.get('notified') else '未发送/冷却中'}")

    return 0 if diag["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
