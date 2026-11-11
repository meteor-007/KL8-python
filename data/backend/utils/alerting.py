# -*- coding: utf-8 -*-
"""统一告警通道 (Alerting) — 多通道投递 + 去重冷却 + 失败降级。

设计原则
--------
1. **零配置可用**：不配置任何外部通道时，告警仍然落盘 (storage/alerts/) 并写日志，
   同时暴露给 Web API 供前端轮询。绝不因为"没配 webhook"就静默丢失告警。
2. **多通道可扩展**：环境变量配置即启用，未配置的通道自动跳过，互不影响。
   - ALERT_WEBHOOK_URL      通用 Webhook (钉钉/飞书/企微机器人均可，自动识别格式)
   - ALERT_WEBHOOK_SECRET   钉钉加签密钥 (可选)
   - ALERT_SMTP_HOST/PORT/USER/PASS/TO   邮件通道 (可选)
3. **去重冷却**：同一 fingerprint 在冷却窗口内只投递一次，避免计划任务重试刷屏。
4. **绝不阻断主流程**：任何通道异常都被吞掉并记日志 —— 告警系统自身的故障不能
   连带弄挂业务流水线。

用法
----
    from backend.utils.alerting import send_alert
    send_alert("nightly_failed", "夜间流水线失败", "详情...", level="error")
"""

from __future__ import annotations

import hashlib
import json
import os
import smtplib
import ssl
import traceback
import urllib.request
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from backend.utils.paths import get_cache_dir, get_storage_dir, get_project_root

# ── 存储位置 ──────────────────────────────────────────────
ALERT_DIR = os.path.join(get_storage_dir(), "alerts")
ALERT_LOG_FILE = os.path.join(ALERT_DIR, "alerts.jsonl")
ALERT_STATE_FILE = os.path.join(get_cache_dir(), "alert_state.json")

# ── 冷却窗口：同一指纹在该小时数内不重复投递 ──
DEFAULT_COOLDOWN_HOURS = 6

# ── 等级 ──
LEVEL_INFO = "info"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"
LEVEL_CRITICAL = "critical"

_LEVEL_ICON = {
    LEVEL_INFO: "ℹ️",
    LEVEL_WARN: "⚠️",
    LEVEL_ERROR: "🔴",
    LEVEL_CRITICAL: "🚨",
}


def _ensure_dirs() -> None:
    try:
        os.makedirs(ALERT_DIR, exist_ok=True)
    except Exception:
        pass


def _load_state() -> Dict[str, Any]:
    try:
        if os.path.exists(ALERT_STATE_FILE):
            with open(ALERT_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {"fingerprints": {}}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(ALERT_STATE_FILE), exist_ok=True)
        tmp = ALERT_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ALERT_STATE_FILE)
    except Exception:
        pass


def _fingerprint(key: str, title: str) -> str:
    raw = f"{key}|{title}".encode("utf-8", "replace")
    return hashlib.sha1(raw).hexdigest()[:16]


def _in_cooldown(fp: str, cooldown_hours: float) -> bool:
    """判断该指纹是否仍在冷却窗口内。"""
    state = _load_state()
    rec = (state.get("fingerprints") or {}).get(fp)
    if not rec:
        return False
    try:
        last = datetime.fromisoformat(rec.get("last_sent_at", ""))
    except Exception:
        return False
    return datetime.now() - last < timedelta(hours=cooldown_hours)


def _mark_sent(fp: str, key: str, title: str, channels: List[str]) -> None:
    state = _load_state()
    fps = state.setdefault("fingerprints", {})
    prev = fps.get(fp) or {}
    fps[fp] = {
        "key": key,
        "title": title,
        "last_sent_at": datetime.now().isoformat(),
        "send_count": int(prev.get("send_count", 0)) + 1,
        "last_channels": channels,
    }
    # 只保留最近 200 条指纹，防止文件无限膨胀
    if len(fps) > 200:
        ordered = sorted(fps.items(), key=lambda kv: kv[1].get("last_sent_at", ""), reverse=True)[:200]
        state["fingerprints"] = dict(ordered)
    _save_state(state)


# ──────────────────────────────────────────────────────────
#  通道实现
# ──────────────────────────────────────────────────────────

def _build_markdown(title: str, content: str, level: str) -> str:
    icon = _LEVEL_ICON.get(level, "ℹ️")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"### {icon} {title}\n\n"
        f"{content}\n\n"
        f"> 时间：{ts} ｜ 等级：**{level}** ｜ 主机：{os.environ.get('COMPUTERNAME', 'unknown')}"
    )


def _send_webhook(title: str, content: str, level: str) -> Optional[str]:
    """通用 Webhook。自动适配钉钉/飞书/企业微信/通用 JSON。"""
    url = (os.environ.get("ALERT_WEBHOOK_URL") or "").strip()
    if not url:
        return None

    md = _build_markdown(title, content, level)
    icon = _LEVEL_ICON.get(level, "ℹ️")

    # 按 URL 特征选择载荷格式，避免用户还要记一堆参数
    if "oapi.dingtalk.com" in url:
        payload = {"msgtype": "markdown", "markdown": {"title": f"{icon} {title}", "text": md}}
        # 钉钉加签
        secret = (os.environ.get("ALERT_WEBHOOK_SECRET") or "").strip()
        if secret:
            import base64
            import hashlib as _hl
            import hmac
            import time as _t
            import urllib.parse
            ts = str(round(_t.time() * 1000))
            sign_raw = f"{ts}\n{secret}".encode("utf-8")
            digest = hmac.new(secret.encode("utf-8"), sign_raw, digestmod=_hl.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(digest))
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}timestamp={ts}&sign={sign}"
    elif "open.feishu.cn" in url:
        payload = {"msg_type": "text", "content": {"text": md}}
    elif "qyapi.weixin.qq.com" in url:
        payload = {"msgtype": "markdown", "markdown": {"content": md}}
    else:
        payload = {"title": title, "content": content, "level": level,
                   "text": md, "timestamp": datetime.now().isoformat()}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return f"webhook:{r.status}"
    except Exception as e:
        return f"webhook:ERR {str(e)[:80]}"


def _send_email(title: str, content: str, level: str) -> Optional[str]:
    host = (os.environ.get("ALERT_SMTP_HOST") or "").strip()
    to_addr = (os.environ.get("ALERT_SMTP_TO") or "").strip()
    if not host or not to_addr:
        return None

    port = int((os.environ.get("ALERT_SMTP_PORT") or "465").strip() or 465)
    user = (os.environ.get("ALERT_SMTP_USER") or "").strip()
    pwd = (os.environ.get("ALERT_SMTP_PASS") or "").strip()
    icon = _LEVEL_ICON.get(level, "ℹ️")

    msg = MIMEText(_build_markdown(title, content, level), "plain", "utf-8")
    msg["Subject"] = f"{icon} [K8-QUANT] {title}"
    msg["From"] = user or "k8quant@localhost"
    msg["To"] = to_addr

    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=ctx) as s:
                if user:
                    s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.starttls(context=ctx)
                if user:
                    s.login(user, pwd)
                s.send_message(msg)
        return "email:ok"
    except Exception as e:
        return f"email:ERR {str(e)[:80]}"


def _write_file(title: str, content: str, level: str, key: str) -> str:
    """落盘：一天一个 JSONL 附录 + 最新一条独立文件（供 API 快速读取）。"""
    _ensure_dirs()
    rec = {
        "at": datetime.now().isoformat(),
        "key": key,
        "level": level,
        "title": title,
        "content": content,
    }
    try:
        with open(ALERT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        with open(os.path.join(ALERT_DIR, "latest_alert.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return "file:ok"


# ──────────────────────────────────────────────────────────
#  对外主入口
# ──────────────────────────────────────────────────────────

def send_alert(
    key: str,
    title: str,
    content: str = "",
    level: str = LEVEL_ERROR,
    cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
    force: bool = False,
) -> Dict[str, Any]:
    """发送一条告警。

    参数:
        key:   业务标识 (如 "nightly_failed")，与 title 一起构成去重指纹
        title: 标题
        content: 正文 (纯文本/Markdown)
        level: info / warn / error / critical
        cooldown_hours: 同指纹冷却窗口；0 表示不去重
        force: 为 True 时忽略冷却强制投递

    返回:
        {"sent": bool, "skipped": reason?, "channels": [...]}
    """
    fp = _fingerprint(key, title)

    if not force and cooldown_hours > 0 and _in_cooldown(fp, cooldown_hours):
        return {"sent": False, "skipped": "cooldown", "channels": [], "fingerprint": fp}

    channels: List[str] = []
    errors: List[str] = []

    # 1) 落盘（永远执行，作为兜底档案 + 前端数据源）
    try:
        channels.append(_write_file(title, content, level, key))
    except Exception as e:
        errors.append(f"file:{e}")

    # 2) Webhook（配置才发）
    try:
        r = _send_webhook(title, content, level)
        if r:
            channels.append(r)
            if "ERR" in r:
                errors.append(r)
    except Exception as e:
        errors.append(f"webhook:{e}")

    # 3) 邮件（配置才发）
    try:
        r = _send_email(title, content, level)
        if r:
            channels.append(r)
            if "ERR" in r:
                errors.append(r)
    except Exception as e:
        errors.append(f"email:{e}")

    # 4) 写标准日志
    icon = _LEVEL_ICON.get(level, "ℹ️")
    print(f"{icon} [告警] {title} ｜ 通道: {', '.join(channels) or '无'}")

    _mark_sent(fp, key, title, channels)

    return {
        "sent": True,
        "channels": channels,
        "errors": errors,
        "fingerprint": fp,
        "level": level,
    }


def read_recent_alerts(limit: int = 20, level: Optional[str] = None) -> List[Dict[str, Any]]:
    """读取最近的告警记录（供 API / 前端展示）。"""
    _ensure_dirs()
    out: List[Dict[str, Any]] = []
    if not os.path.exists(ALERT_LOG_FILE):
        return out
    try:
        with open(ALERT_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return out

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if level and rec.get("level") != level:
            continue
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def resolve_alert(key: str) -> None:
    """标记某类告警已恢复：清掉其去重指纹，使下次再发生时能重新投递。"""
    state = _load_state()
    fps = state.get("fingerprints") or {}
    removed = [fp for fp, rec in fps.items() if rec.get("key") == key]
    for fp in removed:
        fps.pop(fp, None)
    if removed:
        _save_state(state)


def format_diagnostic() -> str:
    """自检：返回当前告警通道配置情况（不含敏感值）。"""
    def _has(k: str) -> str:
        return "已配置" if (os.environ.get(k) or "").strip() else "未配置"

    lines = [
        "告警通道自检:",
        f"  · 本地落盘    : 始终启用  ({ALERT_DIR})",
        f"  · Webhook     : {_has('ALERT_WEBHOOK_URL')}",
        f"  · 钉钉加签    : {_has('ALERT_WEBHOOK_SECRET')}",
        f"  · 邮件 SMTP   : {_has('ALERT_SMTP_HOST')} / {_has('ALERT_SMTP_TO')}",
    ]
    state = _load_state()
    lines.append(f"  · 已记录指纹  : {len(state.get('fingerprints') or {})} 条")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_diagnostic())
