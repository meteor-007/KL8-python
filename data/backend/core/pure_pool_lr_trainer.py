# -*- coding: utf-8 -*-
"""
纯净池 L2 逻辑回归训练器（方案1）
================================
Walk-Forward 学习特征权重 → cache/pure_pool_lr_weights.json
达标则可 active=true 切主推；否则影子模式回退旧阶跃规则。

T(n): 训窗样本行数线性；S(n): O(特征维 × 行数)
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()

from core.pure_pool_scorer import load_b_zone_data, score_pure_pool

WEIGHTS_PATH = os.path.join(_PROJ, 'cache', 'pure_pool_lr_weights.json')
FEATURE_NAMES = [
    'omission', 'log_omis', 'consecutive', 'dual_source', 'recent_hits', 'consec_ge2'
]
BASELINE_RATE = 0.25
MIN_TRAIN_ROWS = 120
DEFAULT_TRAIN_WINDOW = 50
DEFAULT_TEST_FOLDS = 80
L2_LAMBDA = 1.0
LR_ITERS = 200
LR_STEP = 0.15


def _load_history() -> List[Dict]:
    """加载历史开奖数据 (最新在前) — 委托 utils.history_loader, 保持 numbers 为 set 的行为一致"""
    from utils.history_loader import load_history as _load
    return [
        {'issue': h['issue'], 'numbers': set(h['numbers'])}
        for h in _load()
    ]


def _load_points() -> Dict[str, Set[int]]:
    path = os.path.join(_PROJ, 'daily_points.txt')
    pts: Dict[str, Set[int]] = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            mi = re.search(r'period:(\d+)', line)
            mp = re.search(r'points:([\d\s]+)', line)
            if mi and mp:
                pts[mi.group(1)] = set(int(x) for x in mp.group(1).split())
    return pts


def featurize_row(s: Dict) -> List[float]:
    omis = float(s.get('omission', 0))
    consec = float(s.get('consecutive', 0))
    dual = 1.0 if s.get('dual_source') else 0.0
    rh = float(s.get('recent_hits', 0))
    return [
        omis,
        math.log1p(omis),
        consec,
        dual,
        rh,
        1.0 if consec >= 2 else 0.0,
    ]


def _period_scored(
    period: str,
    b_zone: Dict,
    points_map: Dict[str, Set[int]],
    hist_before: List[Dict],
) -> List[Dict]:
    pts = points_map.get(period, set())
    if not pts:
        return []
    recent = [h['issue'] for h in hist_before[:50]]
    if period not in recent:
        recent.insert(0, period)
    return score_pure_pool(period, b_zone, pts, points_map, hist_before, recent)


def build_labeled_periods(
    b_zone: Dict,
    hist: List[Dict],
    points_map: Dict[str, Set[int]],
) -> List[str]:
    drawn = {h['issue'] for h in hist}
    return sorted(
        (p for p in b_zone if p.isdigit() and p in drawn and p in points_map),
        key=int,
    )


def build_xy_for_periods(
    periods: List[str],
    b_zone: Dict,
    hist: List[Dict],
    points_map: Dict[str, Set[int]],
    drawn: Dict[str, Set[int]],
) -> Tuple[np.ndarray, np.ndarray]:
    xs: List[List[float]] = []
    ys: List[float] = []
    for p in periods:
        hist_before = [h for h in hist if int(h['issue']) < int(p)]
        scored = _period_scored(p, b_zone, points_map, hist_before)
        act = drawn.get(p, set())
        for s in scored:
            xs.append(featurize_row(s))
            ys.append(1.0 if s['number'] in act else 0.0)
    if not xs:
        return np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,))
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)


def fit_l2_logistic(
    X: np.ndarray,
    y: np.ndarray,
    l2: float = L2_LAMBDA,
    iters: int = LR_ITERS,
    step: float = LR_STEP,
) -> Tuple[np.ndarray, float]:
    """纯 numpy L2-LR；返回 (weights, bias)。T(n)=O(iters·n·d)。"""
    n, d = X.shape
    if n == 0:
        return np.zeros(d), 0.0
    mu = X.mean(axis=0)
    sigma = X.std(axis=0)
    sigma = np.where(sigma < 1e-8, 1.0, sigma)
    Xn = (X - mu) / sigma

    w = np.zeros(d)
    b = 0.0
    for _ in range(iters):
        z = Xn @ w + b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        err = p - y
        grad_w = (Xn.T @ err) / n + l2 * w
        grad_b = float(err.mean())
        w -= step * grad_w
        b -= step * grad_b

    w_raw = w / sigma
    b_raw = float(b - (mu * w_raw).sum())
    return w_raw, b_raw


def predict_proba(X: np.ndarray, w: np.ndarray, b: float) -> np.ndarray:
    z = X @ w + b
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def select_picks(
    scored: List[Dict],
    w: np.ndarray,
    b: float,
    delta: float,
    top_k: int,
    soft_fallback: bool = True,
) -> List[Dict]:
    """按 P>0.25+delta 取 Top-K；若为空且 soft_fallback，则取 P>=0.25 的 Top-K。"""
    if not scored:
        return []
    X = np.asarray([featurize_row(s) for s in scored], dtype=float)
    probs = predict_proba(X, w, b)
    enriched = []
    for s, p in zip(scored, probs):
        row = dict(s)
        row['lr_prob'] = float(p)
        enriched.append(row)
    enriched.sort(key=lambda r: (-r['lr_prob'], r.get('omission', 0)))
    thr = BASELINE_RATE + delta
    picks = [r for r in enriched if r['lr_prob'] > thr][:top_k]
    if picks:
        return picks
    if soft_fallback:
        return [r for r in enriched if r['lr_prob'] >= BASELINE_RATE][:top_k]
    return []


def _lift_of_picks(picks: List[int], actual: Set[int]) -> Tuple[int, int, float]:
    if not picks:
        return 0, 0, 0.0
    hit = len(set(picks) & actual)
    rate = hit / len(picks)
    return hit, len(picks), rate / BASELINE_RATE


def walk_forward(
    periods: List[str],
    b_zone: Dict,
    hist: List[Dict],
    points_map: Dict[str, Set[int]],
    train_window: int = DEFAULT_TRAIN_WINDOW,
    max_folds: int = DEFAULT_TEST_FOLDS,
    deltas: Optional[List[float]] = None,
    top_k: int = 3,
) -> Dict:
    if deltas is None:
        deltas = [0.00, 0.01, 0.02, 0.03, 0.04, 0.05]
    drawn = {h['issue']: h['numbers'] for h in hist}
    if len(periods) < train_window + 5:
        return {'ok': False, 'reason': f'可用期数不足: {len(periods)}'}

    test_periods = periods[train_window:]
    if len(test_periods) > max_folds:
        test_periods = test_periods[-max_folds:]

    best = None
    for delta in deltas:
        lr_hit_n = 0
        lr_size_n = 0
        old_hit_n = 0
        old_size_n = 0
        fold_lifts_lr = []
        folds_used = 0

        for tp in test_periods:
            idx = periods.index(tp)
            train_ps = periods[max(0, idx - train_window):idx]
            if len(train_ps) < max(20, train_window // 2):
                continue
            X, y = build_xy_for_periods(train_ps, b_zone, hist, points_map, drawn)
            if len(y) < MIN_TRAIN_ROWS or y.sum() < 5:
                continue
            w, b = fit_l2_logistic(X, y)

            hist_before = [h for h in hist if int(h['issue']) < int(tp)]
            scored = _period_scored(tp, b_zone, points_map, hist_before)
            if not scored:
                continue
            actual = drawn[tp]

            lr_picks = [
                r['number']
                for r in select_picks(scored, w, b, delta, top_k, soft_fallback=False)
            ]
            old_picks = [s['number'] for s in scored if s['score'] >= 3]

            h1, n1, l1 = _lift_of_picks(lr_picks, actual)
            h2, n2, _ = _lift_of_picks(old_picks, actual)
            if n1 > 0:
                lr_hit_n += h1
                lr_size_n += n1
                fold_lifts_lr.append(l1)
            if n2 > 0:
                old_hit_n += h2
                old_size_n += n2
            folds_used += 1

        if lr_size_n == 0 or folds_used == 0:
            continue
        lr_rate = lr_hit_n / lr_size_n
        lr_lift = lr_rate / BASELINE_RATE
        old_lift = (old_hit_n / old_size_n / BASELINE_RATE) if old_size_n else 0.0
        avg_size = lr_size_n / max(1, len(fold_lifts_lr))
        cover_rate = len(fold_lifts_lr) / max(1, folds_used)
        # 综合分：Lift 为主，覆盖过低惩罚（避免「只出手 10 次虚高 Lift」）
        composite = lr_lift * (0.5 + 0.5 * min(1.0, cover_rate / 0.5))
        metrics = {
            'delta': delta,
            'folds': folds_used,
            'cover_rate': cover_rate,
            'lr_hit_rate': lr_rate,
            'lr_lift': lr_lift,
            'lr_avg_size': avg_size,
            'old_lift': old_lift,
            'lift_gain_vs_old': lr_lift - old_lift,
            'lr_hits': lr_hit_n,
            'lr_picks': lr_size_n,
            'composite': composite,
        }
        if best is None or metrics['composite'] > best['composite']:
            best = metrics

    if best is None:
        return {'ok': False, 'reason': '无有效 WF 折'}
    return {'ok': True, **best}


def meets_success(metrics: Dict) -> bool:
    if not metrics.get('ok'):
        return False
    lift_ok = metrics['lr_lift'] >= 1.35 or metrics['lift_gain_vs_old'] >= 0.10
    size_ok = 1.5 <= metrics['lr_avg_size'] <= 4.0
    # 覆盖≥20% 且至少累计出手30码，防止极稀疏虚高
    cover_ok = metrics.get('cover_rate', 0) >= 0.20
    sample_ok = metrics.get('lr_picks', 0) >= 30
    return bool(lift_ok and size_ok and cover_ok and sample_ok)


def train_and_save(
    train_window: int = DEFAULT_TRAIN_WINDOW,
    max_folds: int = DEFAULT_TEST_FOLDS,
    top_k: int = 3,
    force_active: Optional[bool] = None,
) -> Dict:
    print('[PurePool-LR] 加载数据...')
    hist = _load_history()
    points_map = _load_points()
    b_zone = load_b_zone_data()
    periods = build_labeled_periods(b_zone, hist, points_map)
    drawn = {h['issue']: h['numbers'] for h in hist}
    print(
        f'[PurePool-LR] 可用标注期={len(periods)} '
        f'({periods[0] if periods else "-"} ~ {periods[-1] if periods else "-"})'
    )

    print('[PurePool-LR] Walk-Forward...')
    wf = walk_forward(
        periods, b_zone, hist, points_map,
        train_window=train_window, max_folds=max_folds, top_k=top_k,
    )
    print(f'[PurePool-LR] WF: {wf}')

    final_periods = periods[-train_window:] if len(periods) >= train_window else periods
    X, y = build_xy_for_periods(final_periods, b_zone, hist, points_map, drawn)
    if len(y) < MIN_TRAIN_ROWS:
        payload = {
            'active': False,
            'feature_names': FEATURE_NAMES,
            'weights': [0.0] * len(FEATURE_NAMES),
            'bias': 0.0,
            'delta': 0.02,
            'top_k': top_k,
            'train_end_issue': periods[-1] if periods else '',
            'wf': wf,
            'reason': f'训练行数不足 ({len(y)} < {MIN_TRAIN_ROWS})',
            'updated_at': datetime.now().isoformat(timespec='seconds'),
        }
        _write_weights(payload)
        return payload

    w, b = fit_l2_logistic(X, y)
    delta = float(wf.get('delta', 0.02)) if wf.get('ok') else 0.02
    active = meets_success(wf) if force_active is None else bool(force_active)
    if force_active is None and not active:
        print('[PurePool-LR] WF 未达门槛 → active=false（影子模式）')
    elif active:
        print('[PurePool-LR] WF 达标 → active=true（主推切换）')

    payload = {
        'active': active,
        'feature_names': FEATURE_NAMES,
        'weights': [float(x) for x in w.tolist()],
        'bias': float(b),
        'delta': delta,
        'top_k': top_k,
        'train_window': train_window,
        'train_rows': int(len(y)),
        'train_positives': int(y.sum()),
        'train_start_issue': final_periods[0],
        'train_end_issue': final_periods[-1],
        'wf': wf,
        'updated_at': datetime.now().isoformat(timespec='seconds'),
    }
    _write_weights(payload)
    print(f'[PurePool-LR] 已写入 {WEIGHTS_PATH}')
    return payload


def _write_weights(payload: Dict) -> None:
    os.makedirs(os.path.dirname(WEIGHTS_PATH), exist_ok=True)
    with open(WEIGHTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_weights(path: str = WEIGHTS_PATH) -> Optional[Dict]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


if __name__ == '__main__':
    import argparse
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='纯净池 L2-LR 训练 / WF')
    parser.add_argument('--train', action='store_true', help='训练并落盘权重')
    parser.add_argument('--force-active', action='store_true')
    parser.add_argument('--force-shadow', action='store_true')
    parser.add_argument('--train-window', type=int, default=DEFAULT_TRAIN_WINDOW)
    parser.add_argument('--folds', type=int, default=DEFAULT_TEST_FOLDS)
    parser.add_argument('--top-k', type=int, default=3)
    args = parser.parse_args()
    force = True if args.force_active else (False if args.force_shadow else None)
    train_and_save(
        train_window=args.train_window,
        max_folds=args.folds,
        top_k=args.top_k,
        force_active=force,
    )
