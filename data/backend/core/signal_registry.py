# -*- coding: utf-8 -*-
"""
信号通道注册表 — 主信号 vs 对照组
==================================
基于 Walk-Forward 单通道 Lift + FDR 校正，选出 1-2 个主信号，
其余通道仅作对照追踪，不参与 ScoreComposer 融合。
"""
import os
import json
import math
import contextlib
import io
from typing import Dict, List, Tuple, Optional

import numpy as np

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
VALIDATION_CACHE = os.path.join(_PROJ, 'cache', 'signal_validation.json')

CORE_CHANNELS = ('EF', 'RW', 'FO')
AUX_CHANNELS = ('MK', 'EO', 'BAYES', 'MC')
ALL_CHANNELS = CORE_CHANNELS + AUX_CHANNELS


def _load_config() -> dict:
    try:
        from config import get_config
        section = get_config().section('signals') or {}
        return {
            'max_primary': int(section.get('max_primary', 2)),
            'fdr_alpha': float(section.get('fdr_alpha', 0.05)),
            'fdr_method': section.get('fdr_method', 'bh'),
            'validation_window': int(section.get('validation_window', 60)),
            'min_history': int(section.get('min_history', 80)),
        }
    except Exception:
        return {'max_primary': 2, 'fdr_alpha': 0.05, 'fdr_method': 'bh',
                'validation_window': 60, 'min_history': 80}


def _binom_pvalue(hits: int, trials: int, p_null: float = 0.25) -> float:
    """二项检验 p 值 (双尾近似)"""
    if trials <= 0:
        return 1.0
    try:
        from scipy.stats import binomtest
        return float(binomtest(hits, trials, p_null, alternative='two-sided').pvalue)
    except Exception:
        # 无 scipy 时用正态近似
        obs = hits / trials
        se = math.sqrt(p_null * (1 - p_null) / trials)
        if se < 1e-12:
            return 1.0
        z = abs(obs - p_null) / se
        return 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))


def _bh_fdr(p_values: List[float], alpha: float) -> List[bool]:
    """Benjamini-Hochberg FDR (兼容旧调用, 转发到共享模块)"""
    from core.multiple_testing import bh_fdr
    mask, _ = bh_fdr(p_values, alpha)
    return mask


def _channel_score_fn(channel: str, history_only: bool = False):
    """返回单通道评分函数 (train_data 降序)

    history_only: 仅 FO 通道使用, True 时限定在训练窗口期号内取 Excel/点位切片,
                  避免 Walk-Forward / 周度监控在全量数据上化验通道造成前瞻偏差.
                  (signal_registry._evaluate_channel 与 baseline 周度监控统一传 True)
    """
    def score(train_data):
        if channel == 'EF':
            from core.energy_field import calc_energy_field
            return calc_energy_field(train_data)
        if channel == 'RW':
            from core.energy_field import calc_omission_sigmoid
            return calc_omission_sigmoid(train_data)
        if channel == 'FO':
            from core.feature_optimizer import get_all_layer_a_scores
            return get_all_layer_a_scores(train_data, history_only=history_only) or {n: 0.0 for n in range(1, 81)}
        if channel == 'MK':
            from core.algorithm_optimizer import plan7_markov_integration
            r = plan7_markov_integration(train_data) or {}
            return r.get('probs', {})
        if channel == 'EO':
            from core.entropy_optimizer import get_number_entropy_scores
            hist_fmt = [h['numbers'] for h in train_data]
            return get_number_entropy_scores(hist_fmt)
        if channel == 'BAYES':
            from core.algorithm_optimizer import plan9_bayesian_update
            r = plan9_bayesian_update(train_data) or {}
            if not isinstance(r, dict):
                return {}
            # 修复: plan9 返回键为 bayes_top20/posteriors/credible_intervals, 无 'probs'
            # 分数向量 = posteriors (80 维后验概率); 缺失时退回 bayes_top20 构造 1..80 分数 dict
            scores = r.get('posteriors')
            if isinstance(scores, dict):
                return scores
            return {n: (1.0 if n in r.get('bayes_top20', []) else 0.0) for n in range(1, 81)}
        if channel == 'MC':
            from core.algorithm_optimizer import plan10_monte_carlo
            r = plan10_monte_carlo(train_data) or {}
            if not isinstance(r, dict):
                return {}
            # 修复: plan10 返回键为 mc_top20/sim_freq, 无 'probs'
            # 分数向量 = sim_freq (蒙特卡洛模拟出现频率); 缺失时退回 mc_top20 构造 1..80 分数 dict
            scores = r.get('sim_freq')
            if isinstance(scores, dict):
                return scores
            return {n: (1.0 if n in r.get('mc_top20', []) else 0.0) for n in range(1, 81)}
        return {n: 0.0 for n in range(1, 81)}
    return score


def _evaluate_channel(history: List[Dict], channel: str, window: int, top_k: int = 20) -> Dict:
    """在最近 window 期上评估单通道 Top-K 命中率"""
    if len(history) < window + 10:
        return {'channel': channel, 'lift': 1.0, 'hit_rate': 0.25, 'p_value': 1.0, 'n': 0}

    # FO 通道限定训练窗口期号 (history_only=True), 与 baseline 周度监控一致
    score_fn = _channel_score_fn(channel, history_only=True)
    total_hits = 0
    total_trials = 0
    baseline = 20 / 80

    for i in range(window):
        # history[0] 最新; 预测 history[i+1] 用 history[i+1:]
        train = history[i + 1:]
        target = history[i]
        if len(train) < 30:
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                scores = score_fn(train)
            if not scores:
                continue
            top = sorted(scores, key=lambda n: (-scores.get(n, 0), n))[:top_k]
            hits = len(set(top) & set(target.get('numbers', [])))
            total_hits += hits
            total_trials += top_k
        except Exception:
            continue

    if total_trials == 0:
        return {'channel': channel, 'lift': 1.0, 'hit_rate': 0.25, 'p_value': 1.0, 'n': 0}

    hit_rate = total_hits / total_trials
    lift = hit_rate / baseline if baseline > 0 else 1.0
    p_value = _binom_pvalue(total_hits, total_trials, baseline)

    return {
        'channel': channel,
        'lift': round(lift, 4),
        'hit_rate': round(hit_rate, 4),
        'p_value': round(p_value, 6),
        'n': total_trials,
    }


def validate_channels(history: List[Dict], force: bool = False) -> Dict:
    """
    评估 CORE_CHANNELS, FDR 校正后选出主信号 (最多 2 个)。
    结果缓存到 cache/signal_validation.json。
    """
    cfg = _load_config()

    if not force and os.path.exists(VALIDATION_CACHE):
        try:
            with open(VALIDATION_CACHE, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            if cached.get('n_history') == len(history):
                return cached
        except Exception:
            pass

    stats = []
    for ch in CORE_CHANNELS:
        stats.append(_evaluate_channel(history, ch, cfg['validation_window']))

    p_values = [s['p_value'] for s in stats]
    from core.multiple_testing import apply_fdr
    fdr_sig, q_values = apply_fdr(p_values, cfg['fdr_alpha'], cfg['fdr_method'])

    for s, q in zip(stats, q_values):
        s['q_value'] = round(q, 6)
    for s, sig in zip(stats, fdr_sig):
        s['significant_fdr'] = sig

    significant = [s for s in stats if s['significant_fdr']]
    significant.sort(key=lambda x: (-x['lift'], x['p_value']))

    if significant:
        primary = [s['channel'] for s in significant[:cfg['max_primary']]]
    else:
        # 无 FDR 显著通道: 取得分最高的 1 个作 exploratory primary
        stats.sort(key=lambda x: (-x['lift'], x['p_value']))
        primary = [stats[0]['channel']] if stats else ['EF']

    control = [ch for ch in CORE_CHANNELS if ch not in primary]
    control.extend(AUX_CHANNELS)

    result = {
        'primary_channels': primary,
        'control_channels': control,
        'channel_stats': stats,
        'n_history': len(history),
        'config': cfg,
        'note': 'FDR显著' if significant else '无FDR显著通道, 使用Lift最高者作exploratory primary',
    }

    os.makedirs(os.path.dirname(VALIDATION_CACHE), exist_ok=True)
    with open(VALIDATION_CACHE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def _load_baseline_config() -> dict:
    try:
        from core.baseline import load_baseline_config
        return load_baseline_config()
    except Exception:
        return {'mode': 'fo_only', 'primary_channel': 'FO', 'include_random_control': True}


def get_active_config(history: Optional[List[Dict]] = None,
                      mode: str = 'daily') -> Tuple[List[str], List[str], Dict]:
    """
    返回 (primary, control, validation_meta)

    mode:
      daily   — FO 单通道 + RANDOM 对照 (不跑 FDR 选通道)
      weekly  — 全通道 FDR 评估 + weekly 监控列表
      backtest — 同 daily (FO-only WF 门控)
    """
    baseline = _load_baseline_config()
    primary_ch = baseline.get('primary_channel', 'FO')

    if mode in ('daily', 'backtest'):
        weekly = baseline.get('weekly_monitor_channels', list(AUX_CHANNELS + ('EF', 'RW')))
        control = [c for c in weekly if c != primary_ch]
        if baseline.get('include_random_control', True):
            control = ['RANDOM'] + control
        meta = {
            'primary_channels': [primary_ch],
            'control_channels': control,
            'mode': 'fo_baseline',
            'note': 'Daily 固定 FO 单通道 baseline，其余通道仅 weekly 监控',
        }
        return [primary_ch], control, meta

    # weekly / full validation
    if history is None:
        if os.path.exists(VALIDATION_CACHE):
            with open(VALIDATION_CACHE, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            return (
                cached.get('primary_channels', [primary_ch]),
                cached.get('control_channels', list(CORE_CHANNELS) + list(AUX_CHANNELS)),
                cached,
            )
        return [primary_ch], list(CORE_CHANNELS) + list(AUX_CHANNELS), {}

    meta = validate_channels(history)
    return meta['primary_channels'], meta['control_channels'], meta
