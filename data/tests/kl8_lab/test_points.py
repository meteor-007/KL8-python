# -*- coding: utf-8 -*-
"""循环三元组扩展 `expand()`（§2.4 / §10.2 test_expand_wrap_01_80 / test_expand_no_duplicate）。"""
from __future__ import annotations

from backend.core.kl8_lab.data_io import NUM_BALLS
from backend.core.kl8_lab.points import expand


def _oracle(points) -> set:
    """独立实现（测试侧 oracle）：循环三元组。"""
    out = set()
    for p in points:
        out.add(p - 1 if p > 1 else NUM_BALLS)
        out.add(p)
        out.add(p + 1 if p < NUM_BALLS else 1)
    return out


# ── 环形边界：01 ↔ 80 ─────────────────────────────────────────

def test_expand_wrap_01_contains_80():
    assert 80 in expand([1])
    assert expand([1]) == {1, 2, 80}


def test_expand_wrap_80_contains_01():
    assert 1 in expand([80])
    assert expand([80]) == {79, 80, 1}


def test_expand_middle_point_is_plain_triple():
    assert expand([40]) == {39, 40, 41}


def test_expand_both_ends_do_not_bleed():
    """01 与 80 同时出现：既不能出现 0，也不能出现 81。"""
    got = expand([1, 80])
    assert got == {80, 1, 2, 79}
    assert 0 not in got and 81 not in got


def test_expand_adjacent_wrap_points():
    """01、02、79、80 相邻：环绕后仍无越界号。"""
    got = expand([1, 2, 79, 80])
    assert got == {80, 1, 2, 3, 78, 79}
    assert min(got) == 1 and max(got) == NUM_BALLS


def test_expand_matches_oracle_for_every_single_point():
    for p in range(1, NUM_BALLS + 1):
        assert expand([p]) == _oracle([p])


def test_expand_empty_input():
    assert expand([]) == set()
    assert expand(set()) == set()


def test_expand_accepts_any_iterable():
    assert expand((1, 80)) == expand({1, 80}) == expand([1, 80])


# ── 去重 ──────────────────────────────────────────────────────

def test_expand_shared_neighbour_is_deduplicated():
    """相邻点位 10 / 11 共享邻居：10 的 next 与 11 的 prev 是同一个 11/10 邻域。"""
    got = expand([10, 11])
    assert got == {9, 10, 11, 12}
    assert len(got) == 4                      # 若未去重会是 6 个位置


def test_expand_same_point_twice_is_deduplicated():
    assert expand([7, 7]) == expand([7]) == {6, 7, 8}


def test_expand_canonical_20_points_unique_count(canonical_points):
    """20 点位 → 40–58 唯一号（§2.4），且与独立 oracle 完全一致。"""
    got = expand(canonical_points)
    assert got == _oracle(canonical_points)
    assert set(canonical_points) <= got                   # 核心点位必在拓展集合内
    assert 40 <= len(got) <= 58, f"唯一号数量 {len(got)} 超出 40–58"
    assert len(got) == 50                                 # 本样例的确定性结果
    assert min(got) == 1 and max(got) == NUM_BALLS
    assert 80 in got and 4 in got                         # 04 的邻居 03/05 与 80 的邻居 01


def test_expand_consecutive_run_collapses():
    """连续 01..05 的拓展应折叠为 01..06（外加 80），而不是 15 个位置。"""
    got = expand(range(1, 6))
    assert got == {80, 1, 2, 3, 4, 5, 6}
    assert len(expand(range(1, 21))) == 22                # {80} ∪ 01..21
