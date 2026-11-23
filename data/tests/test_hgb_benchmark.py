# -*- coding: utf-8 -*-
"""hgb_benchmark 模块单元测试 (小样本合成数据, 不跑真实全量)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from core.hgb_benchmark import (
    _build_xy, walk_forward_eval, N_NUMBERS, FEATURE_NAMES,
)


def _synth_history(D=80, seed=0):
    """生成 D 期合成开奖历史 (期号降序), 每期随机 20/80 码."""
    rng = np.random.RandomState(seed)
    hist = []
    for i in range(D):
        nums = sorted(rng.choice(N_NUMBERS, size=20, replace=False).tolist())
        nums = [n + 1 for n in nums]  # 1..80
        hist.append({'issue': str(2026000 + D - i), 'numbers': nums})
    return hist


def test_build_xy_shape_and_labels():
    draws = list(reversed(_synth_history(30)))
    X, y = _build_xy(draws)
    assert X.shape == (30 * N_NUMBERS, len(FEATURE_NAMES))
    assert y.shape == (30 * N_NUMBERS,)
    # 每期恰好 20 个正样本
    for t in range(30):
        assert y[t * N_NUMBERS:(t + 1) * N_NUMBERS].sum() == 20


def test_build_xy_features_finite():
    draws = list(reversed(_synth_history(40)))
    X, y = _build_xy(draws)
    assert np.isfinite(X).all()
    assert set(np.unique(y).tolist()) <= {0.0, 1.0}


def test_walk_forward_insufficient_data():
    hist = _synth_history(50)
    res = walk_forward_eval(hist, n_folds=2, min_train_periods=300)
    assert res['status'] == 'error'
    assert '不足' in res['message']


def test_walk_forward_small_runs():
    """小样本走通完整流程 (min_train 调小, folds=2)."""
    pytest.importorskip('sklearn')
    hist = _synth_history(120, seed=1)
    res = walk_forward_eval(hist, n_folds=2, min_train_periods=60, seed=0)
    assert res['status'] == 'ok'
    assert res['total_picks'] == res['oos_periods'] * 20
    assert res['total_hits'] <= res['total_picks']
    assert 0.0 <= res['hit_rate'] <= 1.0
    assert len(res['folds']) == 2
    for fd in res['folds']:
        assert fd['lift'] >= 0.0


def test_sklearn_missing_graceful():
    """sklearn 缺失时应返回 error 而非崩溃 (通过 monkeypatch 模拟)."""
    import core.hgb_benchmark as hb
    orig = hb.HistGradientBoostingClassifier
    hb.HistGradientBoostingClassifier = None
    try:
        res = hb.walk_forward_eval(_synth_history(10), min_train_periods=5)
        assert res['status'] == 'error'
    finally:
        hb.HistGradientBoostingClassifier = orig
