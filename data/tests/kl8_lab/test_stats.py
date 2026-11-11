# -*- coding: utf-8 -*-
"""`compute_base_stats()` 基础统计口径（§2.5 / §10.2）。

口径：hit10 近 10 期、hit3 近 3 期、miss 连失、freq_full 全样本、
exp_hit = 0.25T、std = √(T·p·(1−p)) 理论二项、z = (freq_full − exp_hit)/std。
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from backend.core.kl8_lab.numerics import theoretical_std
from backend.core.kl8_lab.points import P_HIT, compute_base_stats, expand, stats_for

T_MAIN = 15


@pytest.fixture
def history(make_history):
    """15 期确定性历史：最新 3 期开 01–20，其余 12 期开 21–40。"""
    rows = []
    for i in range(T_MAIN):
        nums = range(1, 21) if i >= 12 else range(21, 41)
        rows.append((2026001 + i, date(2026, 1, 1) + timedelta(days=i), list(nums)))
    return make_history(rows)                       # 最新在前


@pytest.fixture
def stats(history):
    return compute_base_stats(history, expand([1] * 20))


# ── 覆盖范围与 T ──────────────────────────────────────────────

def test_history_is_newest_first(history):
    assert [d.period for d in history][:3] == [2026015, 2026014, 2026013]
    assert history[0].date == date(2026, 1, 15)


def test_covers_all_80_numbers(stats):
    assert len(stats) == 80
    assert set(stats) == set(range(1, 81))
    for n in range(1, 81):
        assert stats[n].n == n
        assert stats[n].T == T_MAIN


def test_expanded_set_does_not_restrict_range(history):
    """§3.5：模块必须对全 80 号打分，expanded 只作上下文。"""
    stats = compute_base_stats(history, {1, 2, 3})
    assert len(stats) == 80
    assert stats[80].T == T_MAIN
    assert stats[80].freq_full == 0                 # 80 在历史中确未出现，但仍被统计


# ── 具体数值口径 ──────────────────────────────────────────────

def test_hit10_hit3_miss_freq_for_representative_numbers(stats):
    # 01–20：出现在最新 3 期（2026013/14/15）
    s = stats[1]
    assert (s.hit3, s.hit10, s.miss, s.freq_full) == (3, 3, 0, 3)

    # 21–40：出现在更早的 12 期；最新 3 期未出现
    s = stats[21]
    assert s.hit3 == 0
    assert s.hit10 == 7                              # 近 10 期 = 第 6..15 期，其中 7 期命中
    assert s.miss == 3                               # 连失最近 3 期
    assert s.freq_full == 12

    # 41：全样本从未出现
    s = stats[41]
    assert (s.hit3, s.hit10, s.freq_full, s.miss) == (0, 0, 0, T_MAIN)


def test_miss_is_zero_when_latest_draw_hits(stats):
    """最新一期命中 → miss = 0（哪怕更早连续未开）。"""
    assert stats[1].miss == 0
    assert stats[20].miss == 0


def test_exp_hit_and_std_use_theoretical_formula(stats):
    for n in (1, 21, 41, 80):
        s = stats[n]
        assert s.exp_hit == pytest.approx(T_MAIN * 0.25)          # 3.75
        assert s.exp_hit == pytest.approx(T_MAIN * P_HIT)
        assert s.std == pytest.approx(theoretical_std(T_MAIN, P_HIT))
        assert s.std == pytest.approx(math.sqrt(T_MAIN * 0.25 * 0.75))
        assert s.std == pytest.approx(1.6770509831248424, rel=1e-12)


def test_z_score_matches_definition(stats):
    assert stats[1].z_score == pytest.approx((3 - 3.75) / stats[1].std)
    assert stats[1].z_score == pytest.approx(-0.4472135954999579, rel=1e-9)
    assert stats[21].z_score == pytest.approx((12 - 3.75) / stats[21].std)
    assert stats[21].z_score == pytest.approx(4.919349550499537, rel=1e-9)
    assert stats[41].z_score == pytest.approx((0 - 3.75) / stats[41].std)
    assert stats[41].z_score == pytest.approx(-2.23606797749979, rel=1e-9)


def test_z_score_uses_single_shared_std_not_cross_number_empirical_std(stats):
    """§2.5：std 必须是理论值；跨号经验 std 会让 z 爆炸。"""
    stds = {round(s.std, 12) for s in stats.values()}
    assert stds == {round(theoretical_std(T_MAIN, P_HIT), 12)}     # 所有号同一个 std
    # 跨号经验 std 事实上远小于理论值（本构造下为 0），若误用则 z 会失控
    freqs = sorted(s.freq_full for s in stats.values())
    assert freqs[0] == 0 and freqs[-1] == 12


def test_all_stat_fields_bounded_and_finite(stats):
    for n, s in stats.items():
        assert 0 <= s.hit10 <= min(10, T_MAIN)
        assert 0 <= s.hit3 <= min(3, T_MAIN)
        assert 0 <= s.freq_full <= T_MAIN
        assert 0 <= s.miss <= T_MAIN
        assert math.isfinite(s.z_score) and math.isfinite(s.std)
        assert abs(s.z_score) <= 5.0
    # hit10/hit3 与 freq_full 的一致性：近 10 期命中不可能超过全样本命中
    for s in stats.values():
        assert s.hit10 <= s.freq_full
        assert s.hit3 <= s.hit10


def test_hit_window_truncates_to_available_draws(history):
    """T < 10 时 hit10 只能统计已有的期数；T < 3 时 hit3 同理。"""
    s10 = compute_base_stats(history[:10], None)[1]
    assert s10.T == 10
    assert (s10.hit10, s10.hit3, s10.freq_full) == (3, 3, 3)
    assert s10.exp_hit == pytest.approx(2.5)

    s3 = compute_base_stats(history[:3], None)[1]
    assert s3.T == 3
    assert (s3.hit10, s3.hit3, s3.freq_full, s3.miss) == (3, 3, 3, 0)
    assert s3.exp_hit == pytest.approx(0.75)


def test_truncated_history_is_respected_no_lookahead(history):
    """只喂 P 之前的历史（§9.2 严格小于）→ 统计量只反映那一段。"""
    s = compute_base_stats(history[:10], None)[21]
    assert s.T == 10
    assert s.freq_full == 7                          # 21–40 在后 7 期
    assert s.hit10 == 7
    assert s.miss == 3
    assert s.z_score == pytest.approx((7 - 2.5) / theoretical_std(10, P_HIT))


def test_miss_counts_gap_until_first_hit(make_history):
    """中间有间隔时，miss 只数到最近一次命中为止。"""
    rows = [
        (2026010, date(2026, 1, 10), [5]),           # 最新一期含 05 → miss 0
        (2026009, date(2026, 1, 9), [1]),
        (2026008, date(2026, 1, 8), [1]),
        (2026007, date(2026, 1, 7), [5]),            # 上一次命中
        (2026006, date(2026, 1, 6), [1]),
    ]
    st = compute_base_stats(make_history(rows), None)
    assert st[5].miss == 0
    assert st[1].miss == 1                           # 仅最新一期未开
    assert st[2].miss == 5                           # 全 5 期均未开


def test_empty_history_is_degenerate_but_finite():
    st = compute_base_stats([], None)
    assert len(st) == 80
    for s in st.values():
        assert s.T == 0
        assert (s.hit3, s.hit10, s.freq_full, s.miss) == (0, 0, 0, 0)
        assert s.exp_hit == 0.0
        assert s.std == 0.0
        assert s.z_score == 0.0                      # safe_div 兜底，绝不为 nan/inf


# ── stats_for ─────────────────────────────────────────────────

def test_stats_for_lookup(stats):
    assert stats_for(stats, 1).n == 1
    assert stats_for(stats, 80).n == 80
    assert stats_for(stats, 0) is None
    assert stats_for(stats, 81) is None
    assert stats_for(stats, -1) is None
