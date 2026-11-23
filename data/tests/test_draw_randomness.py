# -*- coding: utf-8 -*-
"""
draw_randomness 单元测试
------------------------
验证"开奖随机性体检"模块:
- 合成 i.i.d. 数据不应大量误报 (宽松阈值防 flaky);
- 人为偏置 (某号概率 0.5) 必须被检出;
- runs_test / serial_correlation 在 i.i.d. 数据上 smoke;
- run_full_report 小样本结构完整。
"""
import os
import sys

import numpy as np
import pytest

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)
_BACKEND = os.path.join(_PROJ, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.draw_randomness import (
    chi_square_sf,
    uniformity_per_number,
    pair_uniformity,
    runs_test,
    serial_correlation,
    window_drift,
    run_full_report,
    N_NUMBERS,
    DRAWS_PER_PERIOD,
)


def make_history(rng: np.random.Generator, n_draws: int,
                 biased_number: int = 0, biased_p: float = 0.0) -> list:
    """合成开奖历史: 每期从 80 号中无放回抽 20 个。

    biased_number 为 1..80 (0 表示不偏置); biased_p 为该号每期入选概率。
    返回 load_history 同构的 list[dict], 按期号降序(最新在前)。
    """
    history = []
    for t in range(n_draws):
        issue = str(3000000 + n_draws - t)  # 降序: 第一行最大
        if biased_number and rng.random() < biased_p:
            others = rng.choice([n for n in range(1, N_NUMBERS + 1)
                                 if n != biased_number],
                                size=DRAWS_PER_PERIOD - 1, replace=False)
            nums = sorted([biased_number] + [int(x) for x in others])
        else:
            nums = sorted(int(x) for x in
                          rng.choice(N_NUMBERS, size=DRAWS_PER_PERIOD,
                                     replace=False) + 1)
        history.append({'issue': issue, 'numbers': nums,
                        'draw_order': nums, 'date': '2026-01-01'})
    return history


# ---------------------------------------------------------------------
# 分布函数 sanity
# ---------------------------------------------------------------------

def test_chi_square_sf_known_values():
    # chi2_1 的 0.95 分位 ≈ 3.841 -> sf(3.841,1) ≈ 0.05
    assert abs(chi_square_sf(3.8414588, 1) - 0.05) < 0.001
    # chi2_2 是指数分布: sf(x,2) = exp(-x/2)
    assert abs(chi_square_sf(5.9914645, 2) - 0.05) < 0.001
    # 大 x -> p 趋近 0; x=0 -> p=1
    assert chi_square_sf(0.0, 5) == 1.0
    assert chi_square_sf(200.0, 79) < 1e-10
    assert 0.0 <= chi_square_sf(10.0, 3) <= 1.0


# ---------------------------------------------------------------------
# 均匀性: i.i.d. 数据不误报
# ---------------------------------------------------------------------

def test_uniformity_iid_not_significant():
    rng = np.random.default_rng(7)
    history = make_history(rng, 800)
    res = uniformity_per_number(history)
    # 合并 GOF: 800 期纯随机, p 不应极端小 (阈值放宽到 0.001 防 flaky)
    assert res['p_value'] > 0.001
    # 单号 BH 后不应有号显著 (80 个检验, alpha=0.05)
    assert res['n_significant_bh'] == 0


def test_uniformity_detects_biased_number():
    rng = np.random.default_rng(11)
    biased = 42
    history = make_history(rng, 500, biased_number=biased, biased_p=0.5)
    res = uniformity_per_number(history)
    row = next(r for r in res['per_number'] if r['number'] == biased)
    # 期望 125 次, 实际 ~250 次, 必须显著
    assert row['observed'] > 200
    assert row['p_value'] < 1e-10
    assert row['q_value'] < 0.05
    assert row['significant'] is True
    assert res['n_significant_bh'] >= 1


# ---------------------------------------------------------------------
# 共现对: smoke + 偏置数据里含偏置号的对应偏多
# ---------------------------------------------------------------------

def test_pair_uniformity_smoke():
    rng = np.random.default_rng(13)
    history = make_history(rng, 300)
    res = pair_uniformity(history, max_pairs=200, random_state=42)
    assert res['n_pairs'] == 3160
    assert res['n_sampled_pairs'] == 200
    assert 0.0 <= res['p_value'] <= 1.0
    assert len(res['sampled_pairs']) == 200
    # 抽样结果可复现
    res2 = pair_uniformity(history, max_pairs=200, random_state=42)
    assert res2['sampled_pairs'][0] == res['sampled_pairs'][0]


# ---------------------------------------------------------------------
# runs / serial: i.i.d. smoke
# ---------------------------------------------------------------------

def test_runs_test_iid_smoke():
    rng = np.random.default_rng(17)
    history = make_history(rng, 500)
    res = runs_test(history)  # 自动选最典型的号
    assert res['number'] in range(1, N_NUMBERS + 1)
    assert res['runs_observed'] > 0
    assert 0.0 <= res['p_value'] <= 1.0
    # i.i.d. 下绝大多数号应判一致; 只要不出现离谱的结构即可
    assert res['interpretation'] in (
        'consistent_with_random', 'too_few_runs_clustered',
        'too_many_runs_alternating')


def test_serial_correlation_iid_smoke():
    rng = np.random.default_rng(19)
    history = make_history(rng, 500)
    res = serial_correlation(history, number=10)
    assert -1.0 <= res['lag1_autocorr'] <= 1.0
    assert 0.0 <= res['p_value'] <= 1.0


# ---------------------------------------------------------------------
# 窗口漂移
# ---------------------------------------------------------------------

def test_window_drift_structure():
    rng = np.random.default_rng(23)
    history = make_history(rng, 400)
    res = window_drift(history, window=100)
    assert res['n_windows'] == 4
    assert len(res['windows']) == 4
    assert 'p_value' in res['homogeneity']
    assert 'p_value' in res['trend']
    # 每个窗口 top20_share 应在 0 附近合理波动 (期望 0.25)
    for wd in res['windows']:
        assert 0.15 < wd['top20_share'] < 0.35


# ---------------------------------------------------------------------
# 全量报告
# ---------------------------------------------------------------------

def test_run_full_report_small_sample(tmp_path):
    rng = np.random.default_rng(29)
    history = make_history(rng, 100)
    # write=True 会写到 storage/reports, 测试里也接受 (项目约定目录)
    report = run_full_report(history=history, write=False)
    assert report['n_draws'] == 100
    assert report['verdict'] in ('consistent_with_random', 'anomaly_detected')
    tests = report['tests']
    for key in ('uniformity_per_number', 'pair_uniformity',
                'runs_test', 'serial_correlation', 'window_drift'):
        assert key in tests
    fam = report['family_bh_fdr']
    assert len(fam['names']) == len(fam['p_values']) == len(fam['q_values'])
    assert len(fam['names']) >= 5
    # i.i.d. 小样本允许偶发 anomaly, 只要求 verdict 与显著性自洽
    if report['verdict'] == 'anomaly_detected':
        assert any(fam['significant'])


def test_run_full_report_detects_bias():
    rng = np.random.default_rng(31)
    history = make_history(rng, 400, biased_number=7, biased_p=0.6)
    report = run_full_report(history=history, write=False)
    assert report['verdict'] == 'anomaly_detected'
    assert any(report['family_bh_fdr']['significant'])


def test_chi_square_sf_monotonic():
    # sf 应随 x 递减
    xs = [0.5, 2.0, 5.0, 10.0, 20.0]
    ps = [chi_square_sf(x, 10) for x in xs]
    assert all(ps[i] > ps[i + 1] for i in range(len(ps) - 1))
    assert all(0.0 <= p <= 1.0 for p in ps)
