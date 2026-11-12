# -*- coding: utf-8 -*-
"""kl8/cooccurrence.py 测试（§6.2 共现与图关系）。

覆盖：80×80 共现矩阵（1-based 索引）、Jaccard、PMI、RWR 图扩散、
以及 §12.2 的**增量维护等价性**（test_incremental_equivalence）。
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta

import numpy as np
import pytest

from kl8.cooccurrence import (N, CooccurrenceBundle, build_cooccurrence,
                              slide_window)
from kl8.data_io import Draw

ATOL = 1e-9


def _draw(period: int, numbers) -> Draw:
    return Draw(period=period, date=date(2026, 1, 1) + timedelta(days=period % 28),
                numbers=tuple(sorted(set(numbers))))


def random_draws(T: int, seed: int = 0) -> list[Draw]:
    """T 期随机开奖，每期 20 个不同号码（最新在前）。"""
    rng = random.Random(seed)
    return [_draw(2026001 + (T - 1 - i), rng.sample(range(1, 81), 20))
            for i in range(T)]


def bundle_of(draws) -> CooccurrenceBundle:
    b = CooccurrenceBundle()
    for d in draws:
        b.add(d)
    return b


# ── 共现矩阵 ──────────────────────────────────────────────────

def test_matrix_is_symmetric_with_zero_diagonal():
    draws = random_draws(40, seed=1)
    b = bundle_of(draws)
    assert b.T == 40
    assert b.C.shape == (N + 1, N + 1)
    assert np.allclose(b.C, b.C.T, atol=ATOL)
    assert np.allclose(np.diag(b.C), 0.0, atol=ATOL)
    # 下标 0 不使用
    assert np.allclose(b.C[0], 0.0) and np.allclose(b.C[:, 0], 0.0)
    assert np.allclose(b.count[0], 0.0)
    # count[n] == 含 n 的期数；每期 20 号 → 每期贡献 20
    assert b.count.sum() == pytest.approx(40 * 20)
    for d in draws:
        for n in d.numbers:
            assert b.count[n] >= 1.0


def test_matrix_counts_exact_cooccurrence():
    a = _draw(1, list(range(1, 21)))
    b_ = _draw(2, list(range(1, 21)))
    b = bundle_of([a, b_])
    # 1..20 两期都在 → 任意两号共现 2 次
    assert b.C[1][2] == 2.0
    assert b.C[20][19] == 2.0
    assert b.count[1] == 2.0
    # 只在一期出现的号共现 1 次
    assert b.C[1][21] == 0.0


def test_build_cooccurrence_with_existing_bundle_accumulates():
    """传入已有 bundle 时 build_cooccurrence 真正增量累加 draws（已修复）。

    等价性要求（§12.2）：build_cooccurrence([d2], bundle=b1) 的计数
    必须等于全量 build_cooccurrence([d1, d2])。
    """
    draws = random_draws(30, seed=2)
    prefix, suffix = draws[:10], draws[10:20]
    b = build_cooccurrence(prefix)
    assert b.T == 10

    same = build_cooccurrence(suffix, bundle=b)
    assert same is b
    assert b.T == 10 + len(suffix)            # draws 已被消费，T 推进

    full = build_cooccurrence(prefix + suffix)
    assert b.T == full.T == 20
    assert np.allclose(b.C, full.C, atol=ATOL)
    assert np.allclose(b.count, full.count, atol=ATOL)
    # 派生惰性缓存同样等价
    assert np.allclose(b.J, full.J, atol=ATOL)
    assert np.allclose(b.PMI, full.PMI, atol=ATOL)


# ── Jaccard ───────────────────────────────────────────────────

def test_jaccard_known_value():
    # 两期都含 1..20，且都含 21、22；1 与 2 的并集 = 2 + 2 − 2 = 2 → J = 1
    b = bundle_of([_draw(1, list(range(1, 21))),
                   _draw(2, list(range(1, 21)))])
    assert b.J[1][2] == pytest.approx(1.0)
    # 从未共现 → 0
    assert b.J[1][40] == pytest.approx(0.0)
    assert b.J[40][41] == pytest.approx(0.0)


def test_jaccard_matches_formula():
    draws = random_draws(50, seed=3)
    b = bundle_of(draws)
    J = b.J
    for i, j in [(1, 2), (7, 33), (11, 79), (20, 60)]:
        expected = b.C[i][j] / (b.count[i] + b.count[j] - b.C[i][j])
        assert J[i][j] == pytest.approx(expected, abs=1e-12)
        assert J[j][i] == pytest.approx(expected, abs=1e-12)
    assert np.allclose(J, J.T, atol=ATOL)
    assert J.min() >= 0.0 and J.max() <= 1.0 + 1e-12


# ── PMI ───────────────────────────────────────────────────────

def test_pmi_matches_formula_and_zero_when_absent():
    draws = random_draws(60, seed=4)
    b = bundle_of(draws)
    P = b.PMI
    for i, j in [(1, 2), (10, 70), (33, 44)]:
        if b.C[i][j] > 0:
            pi = b.count[i] / b.T
            pj = b.count[j] / b.T
            pij = b.C[i][j] / b.T
            assert P[i][j] == pytest.approx(math.log(pij / (pi * pj)), abs=1e-12)
        else:
            assert P[i][j] == 0.0
    # C = 0 处恒为 0（避免 log(0)）
    for i in range(1, N + 1):
        for j in range(1, N + 1):
            if b.C[i][j] <= 0:
                assert P[i][j] == 0.0
    assert np.all(np.isfinite(P))


def test_pmi_high_for_always_cooccurring_pair():
    # 两期完全相同 → 任意两号的 P(i,j)=2/2=1, P(i)=P(j)=1 → PMI = 0
    b = bundle_of([_draw(1, list(range(1, 21))),
                   _draw(2, list(range(1, 21)))])
    assert b.PMI[1][2] == pytest.approx(0.0)
    # 只有一个号出现的退化情形不产生 nan
    b2 = bundle_of([_draw(1, [5])])
    assert b2.PMI[5][5] == 0.0
    assert np.all(np.isfinite(b2.PMI))


# ── RWR 图扩散 ────────────────────────────────────────────────

def test_rwr_returns_probability_vector():
    b = bundle_of(random_draws(60, seed=5))
    r = b.rwr({1, 2, 3}, alpha=0.15)
    assert r.shape == (N + 1,)
    assert r[0] == 0.0
    assert np.all(r >= 0.0)
    assert r.sum() == pytest.approx(1.0, abs=1e-9)
    # 种子号必须非零
    for s in (1, 2, 3):
        assert r[s] > 0.0


def test_rwr_empty_seeds_is_zero():
    b = bundle_of(random_draws(20, seed=6))
    r = b.rwr(set())
    assert np.allclose(r, 0.0)
    assert r.sum() == 0.0


def test_rwr_alpha_controls_seed_concentration():
    b = bundle_of(random_draws(60, seed=7))
    low = b.rwr({1}, alpha=0.01)
    high = b.rwr({1}, alpha=0.99)
    assert high[1] > low[1]
    assert high.sum() == pytest.approx(1.0, abs=1e-9)
    assert low.sum() == pytest.approx(1.0, abs=1e-9)


def test_rwr_all_weight_variants_and_zero_graph():
    b = bundle_of(random_draws(40, seed=8))
    for w in ("C", "J", "PMI"):
        r = b.rwr({10}, alpha=0.2, weight=w)
        assert np.all(np.isfinite(r))
        assert 0.0 <= r.sum() <= 1.0 + 1e-9
    # PMI 全零的退化图（两期完全相同 → PMI ≡ 0）→ 只剩重启项
    b0 = bundle_of([_draw(1, list(range(1, 21))),
                    _draw(2, list(range(1, 21)))])
    r0 = b0.rwr({1}, alpha=0.15, weight="PMI")
    assert r0.sum() == pytest.approx(0.15, abs=1e-9)
    assert r0[1] == pytest.approx(0.15, abs=1e-9)


def test_rwr_unknown_weight_falls_back_to_C():
    b = bundle_of(random_draws(30, seed=9))
    assert np.allclose(b.rwr({1}, weight="nope"), b.rwr({1}, weight="C"))


def test_neighbours_ordering_and_exclusion():
    b = bundle_of(random_draws(60, seed=10))
    for w in ("C", "J", "PMI"):
        got = b.neighbours(5, top_k=8, weight=w)
        assert len(got) == 8
        assert all(n != 5 for n, _ in got)
        vals = [v for _, v in got]
        assert vals == sorted(vals, reverse=True)
    # top_k 限制生效
    assert len(b.neighbours(5, top_k=3)) == 3


# ── 增量维护等价性（§10.2 test_incremental_equivalence）────────

def test_incremental_equivalence():
    """增量 add/remove 结果 == 全量重算，容差 1e-9（随机抽 20 期比对）。"""
    draws = random_draws(120, seed=42)
    window = draws[40:]                      # 目标窗口 = 第 40..119 期
    full = bundle_of(window)

    inc = CooccurrenceBundle()
    for d in draws[:100]:                    # 先把窗口外的历史喂进去
        inc.add(d)
    for d in draws[:40]:                     # 再逐期滑出
        inc = slide_window(inc, d, None)
    for d in draws[100:]:                    # 再逐期滑入
        inc = slide_window(inc, None, d)

    assert inc.T == full.T == 80
    assert np.allclose(inc.C, full.C, atol=ATOL)
    assert np.allclose(inc.count, full.count, atol=ATOL)

    # 派生量（惰性缓存）也必须等价
    diff_j = np.abs(inc.J - full.J)
    diff_p = np.abs(inc.PMI - full.PMI)
    assert diff_j.max() < ATOL
    assert diff_p.max() < ATOL
    row, col = np.unravel_index(np.argmax(diff_j), diff_j.shape)
    assert diff_j[row][col] < ATOL


def test_incremental_remove_all_zeroes_state():
    draws = random_draws(20, seed=11)
    b = bundle_of(draws)
    for d in draws:
        b.remove(d)
    assert b.T == 0
    assert np.allclose(b.C, 0.0)
    assert np.allclose(b.count, 0.0)
    assert np.allclose(b.PMI, 0.0)
    assert np.allclose(b.J, 0.0)


def test_cache_invalidated_after_mutation():
    """J/PMI 是惰性缓存，任何 add/remove 后必须重算。"""
    b = bundle_of([_draw(1, [1, 2])])
    first = b.J[1][2]
    assert first == pytest.approx(1.0)
    b.add(_draw(2, [2]))                     # 2 单独出现一次 → 并集变大
    assert b.J[1][2] < first
    cached = b.J[1][2]
    assert cached == pytest.approx(0.5)
    b.remove(_draw(2, [2]))
    assert b.J[1][2] == pytest.approx(first, abs=ATOL)
    assert cached != pytest.approx(b.J[1][2])
