# -*- coding: utf-8 -*-
"""cpcv_dsr 模块单元测试."""
import math
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from core.cpcv_dsr import (
    norm_cdf, norm_ppf, cpcv_split_indices, pbo_cscv,
    deflated_sharpe, effective_n_trials, evaluate_modules,
    load_module_lift_series,
)


# ---------------------------------------------------------------------------
# norm_cdf / norm_ppf
# ---------------------------------------------------------------------------

def test_norm_cdf_known_values():
    assert abs(norm_cdf(0.0) - 0.5) < 1e-12
    assert abs(norm_cdf(1.959963984540054) - 0.975) < 1e-6
    assert abs(norm_cdf(-1.959963984540054) - 0.025) < 1e-6


def test_norm_ppf_known_value():
    assert abs(norm_ppf(0.975) - 1.959963984540054) < 1e-4


def test_norm_ppf_cdf_inverse():
    for p in [0.001, 0.01, 0.1, 0.5, 0.9, 0.99, 0.999]:
        assert abs(norm_cdf(norm_ppf(p)) - p) < 1e-6


def test_norm_ppf_edges():
    assert norm_ppf(0.0) == -math.inf
    assert norm_ppf(1.0) == math.inf


# ---------------------------------------------------------------------------
# cpcv_split_indices
# ---------------------------------------------------------------------------

def test_cpcv_split_count():
    splits = cpcv_split_indices(100, n_groups=10, k_test=2)
    assert len(splits) == 45  # C(10,2)
    for tr, te in splits:
        assert len(tr) + len(te) == 100
        assert len(set(tr.tolist()) & set(te.tolist())) == 0
        assert np.all(np.diff(tr) > 0)  # 时间升序
        assert np.all(np.diff(te) > 0)


def test_cpcv_purge():
    n, G, k, purge = 100, 10, 2, 3
    splits = cpcv_split_indices(n, n_groups=G, k_test=k, purge=purge)
    bounds = np.linspace(0, n, G + 1, dtype=int)
    group_ranges = [(int(bounds[g]), int(bounds[g + 1])) for g in range(G)]
    for tr, te in splits:
        te_set = set(te.tolist())
        for g in range(G):
            lo, hi = group_ranges[g]
            # 若该组有点在测试集, 其前后 purge 点不能在训练集
            if any(lo <= t < hi for t in te_set):
                for t in range(max(0, lo - purge), min(n, hi + purge)):
                    if not (lo <= t < hi):  # 组内点本来就在 test
                        assert t not in set(tr.tolist())


def test_cpcv_invalid_args():
    with pytest.raises(ValueError):
        cpcv_split_indices(50, n_groups=10, k_test=10)
    with pytest.raises(ValueError):
        cpcv_split_indices(50, n_groups=10, k_test=2, purge=-1)


# ---------------------------------------------------------------------------
# pbo_cscv
# ---------------------------------------------------------------------------

def _make_matrix(T, N, signal_col=None, mu=0.0, sigma=1.0, seed=0):
    rng = np.random.RandomState(seed)
    M = rng.normal(mu, sigma, size=(T, N))
    if signal_col is not None:
        M[:, signal_col] += 0.8  # 一个稳定正超额的列
    return M


def test_pbo_noise_high():
    # 纯噪声: IS 冠军在 OOS 应该约一半时间掉到中位以下 -> PBO ~ 0.5
    M = _make_matrix(160, 8, signal_col=None, seed=1)
    r = pbo_cscv(M, S=8, seed=42)
    assert 0.2 <= r['pbo'] <= 0.8
    assert r['n_splits'] == 70  # C(8,4)


def test_pbo_signal_lower_than_noise():
    rng = np.random.RandomState(7)
    # 公共时间轴上, 信号列对所有划分都稳 -> PBO 应显著低于噪声矩阵
    M_sig = _make_matrix(160, 8, signal_col=0, seed=3)
    M_noise = _make_matrix(160, 8, signal_col=None, seed=3)
    r_sig = pbo_cscv(M_sig, S=8, seed=42)
    r_noise = pbo_cscv(M_noise, S=8, seed=42)
    assert r_sig['pbo'] < r_noise['pbo']
    assert r_sig['pbo'] < 0.5


def test_pbo_max_splits_sampling():
    M = _make_matrix(160, 6, seed=5)
    r = pbo_cscv(M, S=16, max_splits=100, seed=0)
    assert r['n_splits'] == 100
    assert '随机采样' in r['note'] or 'max_splits' in r['note']


def test_pbo_invalid():
    with pytest.raises(ValueError):
        pbo_cscv(np.zeros((10, 3)), S=16)  # T < S
    with pytest.raises(ValueError):
        pbo_cscv(np.zeros((100, 1)), S=10)  # N < 2


# ---------------------------------------------------------------------------
# deflated_sharpe
# ---------------------------------------------------------------------------

def test_dsr_single_trial():
    # N=1: 没有"挑最优"偏差, sr0=0, dsr 应等于 psr
    r = deflated_sharpe(0.1, 100, [0.1])
    assert r['n_trials'] == 1
    assert abs(r['dsr'] - r['psr']) < 1e-9


def test_dsr_decreases_with_trial_variance():
    base = [0.05] * 20
    tight = deflated_sharpe(0.1, 100, base)
    spread = base + [0.5, -0.3, 0.2]
    loose = deflated_sharpe(0.1, 100, spread)
    assert loose['sr0'] > tight['sr0']
    assert loose['dsr'] < tight['dsr']


def test_dsr_range():
    r = deflated_sharpe(0.05, 50, [0.01, 0.02, -0.01, 0.03])
    for k in ('psr', 'sr0', 'dsr'):
        assert 0.0 <= r[k] <= 1.0 if k != 'sr0' else True


# ---------------------------------------------------------------------------
# effective_n_trials / evaluate_modules
# ---------------------------------------------------------------------------

def test_effective_n_independent():
    rng = np.random.RandomState(0)
    d = {f"m{i}": rng.randn(200) for i in range(6)}
    n_eff = effective_n_trials(d)
    assert n_eff > 4.0  # 接近 6


def test_effective_n_correlated():
    rng = np.random.RandomState(1)
    base = rng.randn(200)
    d = {f"m{i}": base + 0.01 * rng.randn(200) for i in range(6)}
    n_eff = effective_n_trials(d)
    assert n_eff < 2.5  # 高度相关 -> 远小于 6


def test_evaluate_modules_structure():
    rng = np.random.RandomState(2)
    series = {
        "a": 1.0 + 0.05 * rng.randn(60),
        "b": 1.0 - 0.02 * rng.randn(60),
        "c": np.array([1.0, 1.0, 1.0]),  # std=0 -> 跳过
    }
    out = evaluate_modules(series)
    assert "_meta" in out
    assert "a" in out and "b" in out and "c" not in out
    assert out["_meta"]["n_trials"] == 2
    dsrs = [out["a"]["dsr"], out["b"]["dsr"]]
    # 返回按 dsr 降序
    keys = [k for k in out if k != "_meta"]
    assert out[keys[0]]["dsr"] >= out[keys[1]]["dsr"]


# ---------------------------------------------------------------------------
# load_module_lift_series (真实账本结构 smoke)
# ---------------------------------------------------------------------------

def test_load_module_lift_series_missing(tmp_path):
    with pytest.raises((FileNotFoundError, OSError)):
        load_module_lift_series(str(tmp_path / "nope.jsonl"))


def test_load_module_lift_series_synthetic(tmp_path):
    path = tmp_path / "ledger.jsonl"
    rows = [
        {"period": "2026001", "module": "m1", "picks": [1, 2], "actual": [1, 5], "hits": 1},
        {"period": "2026002", "module": "m1", "picks": [3], "actual": [3], "hits": 1},
        {"period": "2026001", "module": "m2", "picks": [9], "actual": None, "hits": None},
        {"period": "2026002", "module": "m1", "picks": [3], "actual": [3], "hits": 1},  # 重复期覆盖
    ]
    import json
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = load_module_lift_series(str(path))
    assert set(out.keys()) == {"m1"}  # m2 actual=None 被跳过
    # m1: period 2026001 hits=1 picks=2 -> rate=0.5 lift=2.0; 2026002 重复取最后一行 hits=1 picks=1 -> lift=4.0
    assert len(out["m1"]) == 2
    assert out["m1"][0] == pytest.approx(2.0)
    assert out["m1"][1] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# 真实数据冒烟 (可选, 账本存在才跑)
# ---------------------------------------------------------------------------

def test_real_ledger_smoke():
    import os
    root = os.path.join(os.path.dirname(__file__), '..')
    p = os.path.join(root, 'storage', 'cache', 'paper_trading_modules.jsonl')
    if not os.path.exists(p):
        pytest.skip("无真实账本")
    series = load_module_lift_series(p)
    if not series:
        pytest.skip("账本无有效数据")
    out = evaluate_modules(series)
    assert "_meta" in out
    assert out["_meta"]["n_trials"] >= 1
    # PBO 矩阵冒烟
    keys = [k for k in series if len(series[k]) >= 16]
    if len(keys) >= 2:
        min_len = min(len(series[k]) for k in keys)
        mat = np.column_stack([series[k][:min_len] - 1.0 for k in keys])
        S = min(16, min_len // 4 * 4)
        if S >= 8:
            r = pbo_cscv(mat, S=S, max_splits=500, seed=42)
            assert 0.0 <= r['pbo'] <= 1.0
            assert r['n_splits'] > 0
