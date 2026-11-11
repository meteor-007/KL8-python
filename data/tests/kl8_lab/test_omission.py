# -*- coding: utf-8 -*-
"""kl8/omission.py 测试（§6.1 → H2 遗漏反弹）。

覆盖：连失游程提取、Weibull 危险率拟合 / 经验危险率回退、Z 反弹分、
以及 analyze_omission 的契约（全 80 号、[0,1]、样本不足降级）。
"""
from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from backend.core.kl8_lab.data_io import Draw
from backend.core.kl8_lab.omission import (WEIBULL_MIN_SAMPLES, OmissionProfile, _gap_series,
                          _hazard, analyze_omission, profile_number)
from backend.core.kl8_lab.numerics import MIN_SAMPLE

N = 5  # 被测号码


def _draw(period: int, numbers) -> Draw:
    return Draw(period=period, date=date(2026, 1, 1) + timedelta(days=period % 28),
                numbers=tuple(sorted(set(numbers))))


def make_draws(T: int, hit_at=None, n: int = N, seed: int = 0) -> list[Draw]:
    """构造 T 期、**最新在前** 的开奖序列。

    hit_at 为 0-based 下标集合（0 = 最新一期），仅在这些期让号码 n 出现。
    每期恰好 20 个不同号码，保证 Draw 结构真实。
    """
    hit_at = set(hit_at or ())
    rng = random.Random(seed)
    pool = [x for x in range(1, 81) if x != n]
    out: list[Draw] = []
    for i in range(T):
        nums = rng.sample(pool, 19) + [n] if i in hit_at else rng.sample(pool, 20)
        out.append(_draw(2026001 + (T - 1 - i), nums))
    return out


# ── 连失游程 ──────────────────────────────────────────────────

def test_gap_series_newest_first():
    """索引 0 为最新期：current = 最近一次命中的下标，gaps = 相邻命中下标差 − 1。"""
    draws = make_draws(40, hit_at={0, 10, 20})
    current, gaps = _gap_series(draws, N)
    assert current == 0
    assert gaps == [10 - 0 - 1, 20 - 10 - 1] == [9, 9]

    draws = make_draws(40, hit_at={3, 20, 30})
    current, gaps = _gap_series(draws, N)
    assert current == 3
    assert gaps == [16, 9]


def test_gap_series_no_hits():
    draws = make_draws(25, hit_at=set())
    current, gaps = _gap_series(draws, N)
    assert current == 25 and gaps == []


def test_profile_no_hits_is_zero():
    draws = make_draws(40, hit_at=set())
    prof = profile_number(draws, N)
    assert isinstance(prof, OmissionProfile)
    assert prof.current_miss == 40
    assert prof.gaps == []
    assert prof.hazard == 0.0 and prof.z_rebound == 0.0
    assert prof.fitted is False


# ── 危险率 ────────────────────────────────────────────────────

def test_empirical_hazard_fallback():
    """样本 < WEIBULL_MIN_SAMPLES(30) 时回退经验危险率 hits/T * max(m,1)。"""
    draws = make_draws(40, hit_at={0, 10, 20})
    prof = profile_number(draws, N)
    assert prof.fitted is False
    assert prof.k == 0.0 and prof.lam == 1.0
    # hits = len(gaps) + 1 = 3；T = 40；current = 0 → max(m,1) = 1
    assert prof.hazard == pytest.approx(3 / 40 * 1.0)
    assert 0.0 <= prof.hazard <= 1.0


def test_weibull_fit_and_hazard_formula():
    """连失长度 ≥ 30 且非常数时 fitted=True，hazard 走 Weibull 公式。"""
    gap_pattern = [i % 5 for i in range(40)]
    assert len(gap_pattern) >= WEIBULL_MIN_SAMPLES
    idx, pos = [], 0
    for g in gap_pattern:
        idx.append(pos)
        pos += g + 1
    T = idx[-1] + 8
    draws = make_draws(T, hit_at=set(idx))

    prof = profile_number(draws, N)
    assert prof.fitted is True
    assert prof.k > 0 and prof.lam > 0
    assert prof.hazard > 0.0
    assert prof.hazard == pytest.approx(_hazard(prof.k, prof.lam, prof.current_miss))

    # k > 1 → 危险率随 m 单调递增
    assert _hazard(prof.k, prof.lam, 1.0) < _hazard(prof.k, prof.lam, 6.0)


def test_hazard_invalid_params_and_floor():
    assert _hazard(0.0, 2.0, 5.0) == 0.0
    assert _hazard(2.0, 0.0, 5.0) == 0.0
    # m = 0 时 h(m) 用 m_eff = 1，不与 h(1) 冲突
    assert _hazard(2.0, 3.0, 0.0) == pytest.approx(_hazard(2.0, 3.0, 1.0))


# ── Z 反弹分 ──────────────────────────────────────────────────

def test_z_rebound_uses_gap_distribution():
    """z = (current − mean(gaps)) / stdev(gaps, ddof=1)。"""
    draws = make_draws(40, hit_at={10, 12, 16})
    prof = profile_number(draws, N)
    assert prof.current_miss == 10
    assert prof.gaps == [1, 3]
    # mean=2, stdev=sqrt(((1-2)^2+(3-2)^2)/1)=sqrt(2)
    assert prof.z_rebound == pytest.approx((10 - 2) / (2 ** 0.5), rel=1e-9)


def test_z_rebound_zero_variance_guard():
    """gaps 全相等 → stdev 为 0，safe_div 回退 0.0（不得出现 inf/nan）。"""
    draws = make_draws(40, hit_at={5, 15})
    prof = profile_number(draws, N)
    assert prof.current_miss == 5
    assert prof.gaps == [9]
    assert prof.z_rebound == 0.0


def test_z_rebound_negative_when_recent_hit():
    """刚命中（current 很小）→ z 为负，代表反弹压力低。"""
    draws = make_draws(60, hit_at={0, 12, 20})
    prof = profile_number(draws, N)
    assert prof.current_miss == 0
    assert prof.gaps == [11, 7]
    assert prof.z_rebound < 0


# ── analyze_omission 契约 ─────────────────────────────────────

def test_analyze_degrades_below_min_sample():
    draws = make_draws(MIN_SAMPLE - 1, hit_at={0})
    res, z = analyze_omission(draws, set(range(1, 21)), None, None)
    assert res.name == "omission"
    assert res.sufficient is False
    assert "degraded" in res.diagnostics
    assert set(res.scores) == set(range(1, 81))
    assert all(v == 0.0 for v in res.scores.values())
    assert set(z) == set(range(1, 81))
    assert all(v == 0.0 for v in z.values())


def test_analyze_scores_contract_and_metrics():
    draws = make_draws(60, hit_at={0, 10, 20, 30})
    res, z = analyze_omission(draws, set(range(1, 21)), None, None)
    assert res.name == "omission"
    # scores 覆盖全部 1–80，且落在 [0,1]
    assert set(res.scores) == set(range(1, 81))
    assert all(0.0 <= v <= 1.0 for v in res.scores.values())
    assert set(res.metrics) >= {"T", "weibull_fit_ratio", "top_miss",
                                "top_rebound", "median_miss"}
    assert res.metrics["T"] == 60
    assert len(res.metrics["top_miss"]) == 5
    assert len(res.metrics["top_rebound"]) == 5
    # top_miss 按当前连失降序
    miss_values = [m for _, m in res.metrics["top_miss"]]
    assert miss_values == sorted(miss_values, reverse=True)
    # z_rebound 导出给 §4.4 门控，覆盖全 80 号
    assert set(z) == set(range(1, 81))
    assert all(v == v and abs(v) != float("inf") for v in z.values())
    # narrative 投递到合法章节
    assert any(b.section == "macro" for b in res.narrative)


def test_analyze_insufficient_when_weibull_mostly_fails():
    """全部号码连失样本 < 30 → 拟合率 0 → sufficient=False（结论降级不归零）。"""
    draws = make_draws(60, hit_at={0, 10, 20})
    res, z = analyze_omission(draws, set(range(1, 21)), None, None)
    assert res.diagnostics["weibull_fitted"] == 0
    assert res.diagnostics["empirical_fallback"] >= 1
    assert res.diagnostics["n_numbers_with_gaps"] >= 1
    assert res.sufficient is False
    assert "degraded" in res.diagnostics
    # 危险率仍由经验回退给出 → 分数不全为 0
    assert res.metrics["weibull_fit_ratio"] == 0.0
    assert max(res.scores.values()) > 0.0
    assert all(abs(v) != float("inf") for v in z.values())
