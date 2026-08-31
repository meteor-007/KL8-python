# -*- coding: utf-8 -*-
"""
自学习冻结门控
==============
Walk-Forward 全局 Lift 未超过阈值前，禁止一切参数/权重自动微调。
"""
import os
import json
from typing import Dict, Optional

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
WF_RESULTS_FILE = os.path.join(_PROJ, 'cache', 'walk_forward_results.json')
PARAM_STORE_FILE = data_path('param_store.json')
GATE_STATE_FILE = os.path.join(_PROJ, 'cache', 'learning_gate_state.json')

DEFAULT_LIFT_THRESHOLD = 1.0  # 语义: Lift 多折 95%CI 下界 > 1.0 才视为可复现优势
BASELINE_LIFT = 1.0            # 随机基线 Lift = 1.0


def _load_gate_config() -> dict:
    try:
        from config import get_config
        cfg = get_config()
        section = cfg.section('learning_gate') or {}
        return {
            'enabled': section.get('freeze_until_lift', True),
            'lift_threshold': float(section.get('lift_threshold', DEFAULT_LIFT_THRESHOLD)),
        }
    except Exception:
        return {'enabled': True, 'lift_threshold': DEFAULT_LIFT_THRESHOLD}


def get_last_wf_report() -> Optional[Dict]:
    if not os.path.exists(WF_RESULTS_FILE):
        return None
    try:
        with open(WF_RESULTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if data.get('status') == 'OK' else None
    except Exception:
        return None


def get_last_wf_lift() -> Optional[float]:
    report = get_last_wf_report()
    if not report:
        return None
    return float(report.get('global_avg_lift', 0))


def _fold_lifts(report: Dict) -> list:
    """从报告中提取各折 Lift（优先用报告级 CI，否则从 per_fold_summary 现算下界）。"""
    if report.get('per_fold_summary'):
        return [float(f.get('avg_lift', 0)) for f in report['per_fold_summary']]
    return []


def get_wf_ci_lift_lower(z: float = 1.96) -> Optional[float]:
    """多折 Lift 的 95%CI 下界（门控解锁依据）。

    - 报告自带 ci_lift_lo 则直接使用；
    - 否则从 per_fold_summary 现算 mean - z*SE；
    - 无双折样本返回 None。
    """
    report = get_last_wf_report()
    if not report:
        return None
    # 单折(或报告级已判定无有效多折CI)一律冻结, 不玩开
    if report.get('n_folds_used', report.get('n_folds', 0)) < 2:
        return None
    if report.get('ci_lift_lo') is not None:
        return float(report['ci_lift_lo'])
    lifts = _fold_lifts(report)
    if len(lifts) < 2:
        return None
    import math
    mean = sum(lifts) / len(lifts)
    std = math.sqrt(sum((x - mean) ** 2 for x in lifts) / (len(lifts) - 1))
    return mean - z * std / math.sqrt(len(lifts))


def is_learning_enabled() -> bool:
    cfg = _load_gate_config()
    if not cfg.get('enabled', True):
        return True
    ci_lo = get_wf_ci_lift_lower()
    if ci_lo is None:
        return False
    return ci_lo > cfg['lift_threshold']


def learning_frozen_message() -> str:
    cfg = _load_gate_config()
    ci_lo = get_wf_ci_lift_lower()
    point = get_last_wf_lift()
    threshold = cfg['lift_threshold']
    if ci_lo is None:
        return (f'自学习已冻结: 无有效多折 CI 样本 '
                f'(需 Lift 多折 95%CI 下界 > {threshold}, 先跑 python main_v2.py --backtest)')
    return (f'自学习已冻结: Lift 多折 95%CI 下界={ci_lo:.4f} 未达阈值 {threshold} '
            f'(点估 lift={point if point is not None else "N/A"} 即使>阈值也不解冻, '
            f'须以 CI 下界为准; 先跑 python main_v2.py --backtest)')


def record_wf_report(report: Dict) -> Dict:
    """回测完成后更新门控状态（基于多折 CI 下界判定）。"""
    os.makedirs(os.path.dirname(GATE_STATE_FILE), exist_ok=True)
    cfg = _load_gate_config()
    if report.get('status') == 'OK':
        ci_lo = report.get('ci_lift_lo')
        if ci_lo is None:
            lifts = _fold_lifts(report)
            if len(lifts) >= 2:
                import math
                mean = sum(lifts) / len(lifts)
                std = math.sqrt(sum((x - mean) ** 2 for x in lifts) / (len(lifts) - 1))
                ci_lo = mean - 1.96 * std / math.sqrt(len(lifts))
        lift = float(report.get('global_avg_lift', 0)) if report.get('status') == 'OK' else None
        enabled = ci_lo is not None and ci_lo > cfg['lift_threshold']
    else:
        lift = None
        ci_lo = None
        enabled = False
    state = {
        'last_wf_lift': lift,
        'wf_ci_lift_lower': ci_lo,
        'lift_threshold': cfg['lift_threshold'],
        'learning_enabled': enabled,
        'pipeline_mode': report.get('pipeline_mode', 'full'),
        'n_folds': report.get('n_folds'),
    }
    with open(GATE_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return state


def gate_status() -> Dict:
    cfg = _load_gate_config()
    ci_lo = get_wf_ci_lift_lower()
    lift = get_last_wf_lift()
    return {
        'learning_enabled': is_learning_enabled(),
        'last_wf_lift': lift,
        'wf_ci_lift_lower': ci_lo,
        'lift_threshold': cfg['lift_threshold'],
        'message': learning_frozen_message() if not is_learning_enabled() else '自学习已解锁',
    }


def update_param_store(key: str, new_value, reason: str = '') -> bool:
    """
    param_store.json 唯一写入入口 — 受门控保护。
    返回 True 表示已写入, False 表示被冻结拒绝。
    """
    if not is_learning_enabled():
        return False

    store = {'params': {}, 'audit_log': []}
    if os.path.exists(PARAM_STORE_FILE):
        try:
            with open(PARAM_STORE_FILE, 'r', encoding='utf-8') as f:
                store = json.load(f)
        except Exception:
            pass

    params = store.setdefault('params', {})
    old_value = params.get(key)
    if old_value == new_value:
        return True

    import datetime
    params[key] = new_value
    store.setdefault('audit_log', []).append({
        'timestamp': datetime.datetime.now().isoformat(),
        'key': key,
        'old_value': old_value,
        'new_value': new_value,
        'reason': reason or 'auto_tune',
    })
    store['audit_log'] = store['audit_log'][-100:]

    with open(PARAM_STORE_FILE, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    return True
