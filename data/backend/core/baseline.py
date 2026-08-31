# -*- coding: utf-8 -*-
"""
极简 Baseline 系统 — FO 单通道
==========================================
Daily 默认输出；其余通道仅 weekly 监控。
"""
import json
import os
from typing import Dict, List, Tuple, Optional

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
WEEKLY_MONITOR_FILE = os.path.join(_PROJ, 'cache', 'weekly_channel_monitor.json')

PRIMARY_CHANNEL = 'FO'


def load_baseline_config() -> dict:
    try:
        from config import get_config
        section = get_config().section('baseline') or {}
        return {
            'mode': section.get('mode', 'fo_only'),
            'primary_channel': section.get('primary_channel', 'FO'),
            'weekly_monitor_channels': section.get(
                'weekly_monitor_channels',
                ['EF', 'RW', 'MK', 'EO', 'BAYES', 'MC'],
            ),
        }
    except Exception:
        return {
            'mode': 'fo_only',
            'primary_channel': 'FO',
            'weekly_monitor_channels': ['EF', 'RW', 'MK', 'EO', 'BAYES', 'MC'],
        }


def compute_fo_scores(history: List[Dict], history_only: bool = False) -> Dict[int, float]:
    from core.feature_optimizer import get_all_layer_a_scores
    raw = get_all_layer_a_scores(history, history_only=history_only) or {}
    return {int(n): float(v) for n, v in raw.items() if 1 <= int(n) <= 80}





def rank_from_scores(scores: Dict[int, float], top_k: int = 20,
                     golden_k: int = 5, silver_k: int = 10) -> Dict:
    top = sorted(scores, key=lambda n: (-scores.get(n, 0), n))[:top_k]
    return {
        'golden': top[:golden_k],
        'silver': top[golden_k:silver_k],
        f'top{top_k}': top,
        'final_scores': scores,
    }


def compute_advisory(gate: Dict) -> Dict:
    """将门控/WF 证据翻译为"是否值得下注"的一等输出。

    - ACTIVE_SIGNAL: 多折 95%CI 下界 > 1.0 (可复现优势) → 高置信, 建议使用
    - NO_EDGE:       有 WF 但 CI 下界未超基线 → 低置信, 建议观望/不调参
    - UNKNOWN:       尚无 WF 证据 → 低置信, 提示先跑回测
    """
    ci_lo = gate.get('wf_ci_lift_lower')
    lift = gate.get('last_wf_lift')
    if ci_lo is None:
        return {
            'verdict': 'UNKNOWN',
            'confidence': 'LOW',
            'ci_lift_lower': None,
            'point_lift': lift,
            'recommendation': '尚无 Walk-Forward 证据, 请先运行回测建立基线后再作判断',
        }
    if ci_lo > 1.0:
        return {
            'verdict': 'ACTIVE_SIGNAL',
            'confidence': 'HIGH',
            'ci_lift_lower': ci_lo,
            'point_lift': lift,
            'recommendation': '存在可复现优势 (CI 下界>1.0), 可放心使用本推荐',
        }
    return {
        'verdict': 'NO_EDGE',
        'confidence': 'LOW',
        'ci_lift_lower': ci_lo,
        'point_lift': lift,
        'recommendation': '当前无可复现优势 (CI 下界≤1.0), 输出仅供研究参考, 建议观望不追号',
    }


def run_daily_baseline(history: List[Dict], top_k: int = 20) -> Dict:
    """Daily 极简管线: FO 主推荐"""
    cfg = load_baseline_config()
    fo_scores = compute_fo_scores(history, history_only=False)
    fo_rank = rank_from_scores(fo_scores, top_k=top_k)

    try:
        from core.learning_gate import gate_status
        gate = gate_status()
    except Exception:
        gate = {}

    try:
        from recognition.simplified_env_recognition import recognize_environment
        _, env_name, _, _ = recognize_environment(history)
    except Exception:
        env_name = 'balanced'

    advisory = compute_advisory(gate)

    return {
        'mode': 'fo_baseline',
        'target_period': str(int(history[0]['issue']) + 1) if history else 'N/A',
        'primary_channels': [cfg.get('primary_channel', PRIMARY_CHANNEL)],
        'control_channels': cfg.get('weekly_monitor_channels', []),
        'environment': env_name,
        'golden': fo_rank['golden'],
        'silver': fo_rank['silver'],
        f'top{top_k}': fo_rank[f'top{top_k}'],
        'final_scores': fo_rank['final_scores'],
        'fo_only': fo_rank,
        'all_raw_scores': {'FO': fo_scores},
        'learning_gate': gate,
        'advisory': advisory,
        'confidence': {
            'level': advisory['confidence'],
            'verdict': advisory['verdict'],
            'description': 'FO 单通道 baseline',
        },
    }


def run_weekly_monitor(history: List[Dict], top_k: int = 20) -> Dict:
    """Weekly: 全通道 Lift 监控，不参与 daily 融合"""
    from core.signal_registry import validate_channels, ALL_CHANNELS, _channel_score_fn

    cfg = load_baseline_config()
    meta = validate_channels(history, force=True)

    channel_tops = {}
    for ch in ALL_CHANNELS:
        if ch not in cfg.get('weekly_monitor_channels', []):
            continue
        try:
            # FO 通道 history_only=True, 与 signal_registry._evaluate_channel 一致,
            # 避免周度监控在全量数据上化验通道 (前瞻偏差)
            scores = _channel_score_fn(ch, history_only=True)(history)
            if scores:
                top = sorted(scores, key=lambda n: (-scores.get(n, 0), n))[:top_k]
                channel_tops[ch] = top
        except Exception:
            channel_tops[ch] = []

    report = {
        'generated_at': __import__('datetime').datetime.now().isoformat(),
        'n_history': len(history),
        'daily_mode': cfg.get('mode', 'fo_only'),
        'daily_primary': cfg.get('primary_channel', 'FO'),
        'channel_validation': meta,
        'channel_top20': channel_tops,
        'note': 'Weekly 监控专用，Daily 不引用此输出',
    }

    os.makedirs(os.path.dirname(WEEKLY_MONITOR_FILE), exist_ok=True)
    with open(WEEKLY_MONITOR_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report
