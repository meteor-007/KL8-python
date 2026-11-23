# -*- coding: utf-8 -*-
"""kl8/entropy.py 与 numerics.entropy_normalized 测试（§4.12 熵/均衡 → H7）。

核心口径（v2.0 修正）：p_i = freq_i / Σfreq，H* = H_num / ln 80 ∈ [0,1]。
均匀分布 → H* = 1；全部集中在 1 个号 → H* = 0。
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from kl8.data_io import Draw
from kl8.entropy import (N_ZONES, NUM_BALLS, WINDOW, _counts, _kl, _quantile,
                         _zone_counts, _zone_of, analyze)
from kl8.numerics import MIN_SAMPLE, entropy_normalized
from kl8.points import compute_base_stats

LOG80 = math.log(NUM_BALLS)


class _Thresholds:
    entropy_low_quantile = 0.10


class _Cfg:
    thresholds = _Thresholds()


def _draw(period: int, numbers) -> Draw:
    return Draw(period=period, date=date(2026, 1, 1) + timedelta(days=period % 28),
                numbers=tuple(sorted(set(numbers))))


# ── 归一化熵口径 ──────────────────────────────────────────────

def test_entropy_normalized_uniform_is_one():
    assert entropy_normalized([1] * NUM_BALLS) == pytest.approx(1.0, abs=1e-9)
    assert entropy_normalized([7] * NUM_BALLS) == pytest.approx(1.0, abs=1e-9)
    assert entropy_normalized([3, 3, 3, 3]) == pytest.approx(1.0, abs=1e-9)


def test_entropy_normalized_concentrated_is_zero():
    # 全部质量集中在 1 号（第 0 个类别）
    counts = [1] + [0] * (NUM_BALLS - 1)
    assert entropy_normalized(counts) == 0.0
    assert entropy_normalized([0] * (NUM_BALLS - 1) + [1]) == 0.0
    assert entropy_normalized([5, 0, 0]) == 0.0


def test_entropy_normalized_degenerate_inputs():
    assert entropy_normalized([]) == 0.0
    assert entropy_normalized([0] * NUM_BALLS) == 0.0     # 总量为 0
    assert entropy_normalized([3]) == 0.0                 # 单类别
    assert entropy_normalized([-1, 2]) == 0.0             # 负值被夹到 0


def test_entropy_normalized_range():
    for counts in ([1, 2, 3, 4, 5], [0, 1, 1, 1, 1], [100, 1, 1, 1]):
        h = entropy_normalized(counts)
        assert 0.0 <= h <= 1.0

    # 二类别等量 → H* = 1
    assert entropy_normalized([4, 4]) == pytest.approx(1.0)
    # 二类别 1:3 → H_num/ln2 = 0.8113
    expect = -(0.25 * math.log(0.25) + 0.75 * math.log(0.75)) / math.log(2)
    assert entropy_normalized([1, 3]) == pytest.approx(expect, rel=1e-9)


# ── 小工具 ────────────────────────────────────────────────────

def test_zone_of_and_zone_counts():
    assert _zone_of(1) == 0 and _zone_of(10) == 0
    assert _zone_of(11) == 1 and _zone_of(80) == N_ZONES - 1
    freq = [0] * (NUM_BALLS + 1)
    for n in range(1, NUM_BALLS + 1):
        freq[n] = n
    zc = _zone_counts(freq)
    assert len(zc) == N_ZONES
    assert zc[0] == sum(range(1, 11))
    assert sum(zc) == sum(range(1, NUM_BALLS + 1))


def test_counts_helper():
    draws = [_draw(1, [1, 2, 3]), _draw(2, [1, 80])]
    c = _counts(draws)
    assert len(c) == NUM_BALLS + 1
    assert c[0] == 0 and c[1] == 2 and c[2] == 1 and c[80] == 1
    assert sum(c) == 5


def test_quantile_linear_interpolation():
    assert _quantile([], 0.5) == 0.0
    assert _quantile([4.0], 0.3) == 4.0
    assert _quantile([0.0, 10.0], 0.0) == 0.0
    assert _quantile([0.0, 10.0], 1.0) == 10.0
    assert _quantile([0.0, 10.0], 0.5) == pytest.approx(5.0)
    assert _quantile([0.0, 1.0, 2.0, 3.0], 1 / 3) == pytest.approx(1.0)


def test_kl_divergence_identical_is_zero():
    draws = [_draw(1, list(range(1, 21))), _draw(2, list(range(21, 41)))]
    c = _counts(draws)
    assert _kl(c, c) == pytest.approx(0.0, abs=1e-12)
    assert _kl([0] * (NUM_BALLS + 1), c) == 0.0


# ── 模块：均匀 / 集中 ─────────────────────────────────────────

def uniform_draws(T: int = 32) -> list[Draw]:
    """T 期 4 组轮转（每组 20 号）→ 每号恰好 T/4 次，全样本分布严格均匀。"""
    groups = [list(range(1 + 20 * k, 21 + 20 * k)) for k in range(4)]
    return [_draw(2026001 + (T - 1 - i), groups[i % 4]) for i in range(T)]


def test_module_uniform_distribution_gives_entropy_one():
    draws = uniform_draws(32)
    res = analyze(draws, set(range(1, 21)), compute_base_stats(draws), _Cfg())
    assert res.name == "entropy"
    assert res.sufficient is True
    assert res.metrics["H_star"] == pytest.approx(1.0, abs=1e-9)
    # H_num 指标保留 4 位小数
    assert res.metrics["H_num"] == pytest.approx(LOG80, abs=5e-4)
    assert res.metrics["zone_entropy"] == pytest.approx(1.0, abs=1e-9)
    assert res.metrics["zone_share"] == [pytest.approx(1 / 8)] * N_ZONES
    assert res.metrics["never_drawn_numbers"] == 0
    # 全部号等频 → rank 归一全 0.5 → 分数恒为 0.5
    assert set(res.scores) == set(range(1, NUM_BALLS + 1))
    assert all(v == pytest.approx(0.5) for v in res.scores.values())


def test_module_concentrated_gives_entropy_zero():
    """所有期只开 1 号 → 分布完全集中 → H* = 0，其余 79 号从未开出。"""
    T = 40
    draws = [_draw(2026001 + (T - 1 - i), [1]) for i in range(T)]
    res = analyze(draws, {1}, compute_base_stats(draws), _Cfg())
    assert res.metrics["H_star"] == 0.0
    assert res.metrics["H_num"] == 0.0
    assert res.metrics["zone_entropy"] == 0.0
    assert res.metrics["never_drawn_numbers"] == NUM_BALLS - 1
    assert res.metrics["hottest_zone"] == "[1-10]"
    # 从未开出的号有风险提示
    assert any("从未开出" in b.text for b in res.narrative)


def test_module_degrades_below_min_sample():
    draws = uniform_draws(32)[:MIN_SAMPLE - 1]
    res = analyze(draws, set(), {}, _Cfg())
    assert res.name == "entropy"
    assert res.sufficient is False
    assert "degraded" in res.diagnostics
    assert set(res.scores) == set(range(1, NUM_BALLS + 1))
    assert all(v == 0.0 for v in res.scores.values())


def test_module_low_entropy_alert_and_regime():
    """最近一个滑窗高度集中 → 触发低熵告警，延续权重上升。"""
    T = 60
    recent = list(range(1, 21))
    groups = [list(range(1 + 20 * k, 21 + 20 * k)) for k in range(4)]
    draws = ([_draw(2026001 + (T - 1 - i), recent) for i in range(WINDOW)]
             + [_draw(2026001 + (T - 1 - (WINDOW + i)), groups[i % 4])
                for i in range(T - WINDOW)])
    res = analyze(draws, set(), compute_base_stats(draws), _Cfg())
    assert res.metrics["window"] == WINDOW
    assert res.metrics["low_entropy_alert"] == 1
    assert res.metrics["h_short"] < res.metrics["entropy_low_threshold"]
    assert res.metrics["regime"] in ("有序/延续", "均衡/回补", "中性")
    assert 0.0 <= res.metrics["regime_continuation_weight"] <= 1.0
    assert any("低熵" in b.text for b in res.narrative)


def test_module_metrics_and_scores_contract():
    draws = uniform_draws(40)
    res = analyze(draws, set(range(1, 41)), compute_base_stats(draws), _Cfg())
    assert set(res.metrics) >= {
        "T", "window", "H_num", "H_star", "zone_entropy", "h_short", "h_long",
        "h_series_std", "entropy_low_threshold", "regime", "kl_divergence",
        "low_entropy_alert", "kl_alert", "zone_share", "hottest_zone",
        "never_drawn_numbers", "top_continuation", "top_rebound", "sub_scores",
    }
    assert res.metrics["T"] == 40
    assert res.metrics["h_series_std"] >= 0.0
    assert res.metrics["kl_divergence"] >= 0.0
    assert len(res.metrics["zone_share"]) == N_ZONES
    assert len(res.metrics["top_continuation"]) == 5
    assert len(res.metrics["top_rebound"]) == 5
    assert res.metrics["low_entropy_alert"] in (0, 1)
    assert res.metrics["kl_alert"] in (0, 1)
    assert set(res.metrics["sub_scores"]) == {"continuation", "rebound"}
    assert len(res.metrics["sub_scores"]["continuation"]) == NUM_BALLS

    assert set(res.scores) == set(range(1, NUM_BALLS + 1))
    assert all(0.0 <= v <= 1.0 for v in res.scores.values())
    assert res.diagnostics["entropy_series_len"] == 40 - WINDOW + 1
    assert res.diagnostics["base_stats_provided"] is True
    assert any(b.section == "macro" for b in res.narrative)
