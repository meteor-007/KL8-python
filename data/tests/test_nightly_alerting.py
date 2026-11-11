# -*- coding: utf-8 -*-
"""告警通道与夜间看门狗单元测试。

覆盖 2026-10-22 事故（夜间流水线停摆一个月无人知晓）的补救逻辑：
  · 告警必须落盘（即使没配任何外部通道）
  · 同一指纹在冷却窗口内不得重复投递
  · 显式失败 / 静默停摆 都必须被 watchdog 判为异常
  · 恢复正常后必须清除指纹并发出恢复通知
"""
import json
import os
import shutil
import sys
from datetime import datetime, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, 'backend')):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.utils import alerting, nightly_watchdog as wd
from backend.utils.paths import get_project_root


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """把告警/看门狗状态重定向到临时目录，避免污染真实 storage。"""
    monkeypatch.setattr(alerting, 'ALERT_DIR', str(tmp_path / 'alerts'))
    monkeypatch.setattr(alerting, 'ALERT_LOG_FILE', str(tmp_path / 'alerts' / 'alerts.jsonl'))
    monkeypatch.setattr(alerting, 'ALERT_STATE_FILE', str(tmp_path / 'alert_state.json'))
    monkeypatch.setattr(wd, 'WATCHDOG_STATE', str(tmp_path / 'watchdog_state.json'))
    monkeypatch.setattr(wd, 'SCHEDULER_CONFIG', str(tmp_path / 'scheduler_config.json'))
    return tmp_path


def _write_cfg(tmp_path, **kw):
    cfg = {
        'enabled': True, 'target_time': '22:00',
        'last_run_date': datetime.now().strftime('%Y-%m-%d'),
        'last_status': 'SUCCESS',
        'last_message': '✅ ok',
        'last_finished_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    cfg.update(kw)
    with open(tmp_path / 'scheduler_config.json', 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False)
    return cfg


def test_alert_persists_to_disk_without_any_channel(isolated):
    """零配置下告警仍必须落盘 —— 绝不能因为没配 webhook 就静默丢失。"""
    res = alerting.send_alert('unit_test', '测试告警', '正文内容', level='critical')
    assert res['sent'] is True
    assert any(c.startswith('file:') for c in res['channels'])

    items = alerting.read_recent_alerts(limit=10)
    assert len(items) == 1
    assert items[0]['key'] == 'unit_test'
    assert items[0]['level'] == 'critical'


def test_alert_dedup_cooldown(isolated):
    """同一指纹在冷却窗口内只投递一次，避免计划任务重试刷屏。"""
    r1 = alerting.send_alert('dup', '重复标题', 'x', cooldown_hours=6)
    assert r1['sent'] is True

    r2 = alerting.send_alert('dup', '重复标题', 'x', cooldown_hours=6)
    assert r2['sent'] is False
    assert r2['skipped'] == 'cooldown'

    # force=True 可强制穿透冷却
    r3 = alerting.send_alert('dup', '重复标题', 'x', cooldown_hours=6, force=True)
    assert r3['sent'] is True


def test_alert_level_filter(isolated):
    alerting.send_alert('a', '信息', level='info', cooldown_hours=0)
    alerting.send_alert('b', '错误', level='error', cooldown_hours=0)
    assert len(alerting.read_recent_alerts(level='error')) == 1
    assert len(alerting.read_recent_alerts()) == 2


def test_watchdog_healthy(isolated):
    _write_cfg(isolated)
    diag = wd.check_nightly_health()
    assert diag['healthy'] is True
    assert diag['problems'] == []


def test_watchdog_detects_failure(isolated):
    """显式失败必须被判为异常。"""
    _write_cfg(isolated, last_status='FAILED',
               last_message="❌ 夜间流水线执行异常: 'NoneType' object has no attribute 'get'")
    diag = wd.check_nightly_health()
    assert diag['healthy'] is False
    assert any('显式失败' in p for p in diag['problems'])


def test_watchdog_detects_silent_stall(isolated):
    """静默停摆（状态是 SUCCESS 但时间陈旧）—— 这正是 9-20 事故的真实形态。"""
    old = datetime.now() - timedelta(days=30)
    _write_cfg(isolated,
               last_run_date=old.strftime('%Y-%m-%d'),
               last_finished_at=old.strftime('%Y-%m-%d %H:%M:%S'))
    diag = wd.check_nightly_health(stale_hours=26)
    assert diag['healthy'] is False
    assert diag['age_hours'] > 26
    assert any('静默停摆' in p for p in diag['problems'])


def test_watchdog_no_false_alarm_on_fresh_run(isolated):
    """回归：刚刚启动的 RUNNING 任务不得被判为卡死。

    2026-10-22 实测误报：任务 16:00 启动，watchdog 用 last_run_date（纯日期，
    解析成当天 00:00）算作"已 RUNNING 16 小时"并发出 critical 假告警。
    修复后：有精确 last_started_at 时按它算；只有日期时放弃卡死判定。
    """
    # (a) 刚启动 1 分钟 → 必须健康，不得告警
    _write_cfg(isolated, last_status='RUNNING',
               last_started_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    diag = wd.check_nightly_health()
    assert diag['healthy'] is True, f"误报: {diag['problems']}"

    # (b) RUNNING 但只有日期、没有精确启动时刻 → 放弃判定（宁可不报也不误报）
    cfg = _write_cfg(isolated, last_status='RUNNING')
    cfg.pop('last_started_at', None)
    with open(isolated / 'scheduler_config.json', 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False)
    diag2 = wd.check_nightly_health()
    assert not any('卡在 RUNNING' in p for p in diag2['problems']), \
        f"仅有日期时不应判定卡死: {diag2['problems']}"

    # (c) 真卡死 5 小时（有精确时间）→ 必须告警
    old = datetime.now() - timedelta(hours=5)
    _write_cfg(isolated, last_status='RUNNING',
               last_started_at=old.strftime('%Y-%m-%d %H:%M:%S'))
    diag3 = wd.check_nightly_health()
    assert diag3['healthy'] is False
    assert any('卡在 RUNNING' in p for p in diag3['problems'])


def test_watchdog_alert_then_recover(isolated):
    """异常→告警；恢复→发恢复通知并清除失败指纹。"""
    # 1) 注入失败态
    _write_cfg(isolated, last_status='FAILED', last_message='boom')
    d1 = wd.run_watchdog(notify=True)
    assert d1['healthy'] is False
    assert d1.get('notified') is True

    keys = {r['key'] for r in alerting.read_recent_alerts(limit=20)}
    assert 'nightly_failed' in keys

    # 2) 恢复
    _write_cfg(isolated)
    d2 = wd.run_watchdog(notify=True)
    assert d2['healthy'] is True

    keys2 = {r['key'] for r in alerting.read_recent_alerts(limit=20)}
    assert 'nightly_recovered' in keys2

    st = alerting._load_state()
    fps = st.get('fingerprints') or {}
    assert not any(v.get('key') == 'nightly_failed' for v in fps.values()), \
        '恢复后 nightly_failed 指纹应被清除，使下次故障能重新告警'


def test_webhook_payload_format(monkeypatch):
    """Webhook 未配置时必须返回 None（不发起任何请求）。"""
    monkeypatch.delenv('ALERT_WEBHOOK_URL', raising=False)
    assert alerting._send_webhook('t', 'c', 'error') is None


def test_email_skipped_when_unconfigured(monkeypatch):
    monkeypatch.delenv('ALERT_SMTP_HOST', raising=False)
    monkeypatch.delenv('ALERT_SMTP_TO', raising=False)
    assert alerting._send_email('t', 'c', 'error') is None
