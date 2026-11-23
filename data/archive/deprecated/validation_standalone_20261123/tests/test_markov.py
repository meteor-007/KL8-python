# -*- coding: utf-8 -*-
"""kl8/markov.py 测试（§4.5 马尔可夫链状态转移 + HMM）。

重点：
  1. 状态是「遗漏长度游程」而非「近 10 期命中数的滑动窗口」
     （§4.5 指出滑动窗口状态是恒等式，是本方案要修掉的 v1.0 缺陷）；
  2. 已知转移矩阵 → 已知 χ² 与 p（§4.5.2 的 p_k 显著性）。
"""
from __future__ import annotations

import random
from datetime import date, timedelta

import numpy as np
import pytest
from scipy.stats import binomtest, chi2_contingency

from kl8.data_io import Draw
from kl8.markov import (N_STATES, P0, STATE_LABELS, _bucket, _period_features,
                        _state_sequence, analyze)
from kl8.numerics import MIN_SAMPLE
from kl8.points import compute_base_stats


class _Thresholds:
    alpha = 0.05
    norm_method = "rank"


class _Cfg:
    thresholds = _Thresholds()
    seed = 42


def _draw(period: int, numbers) -> Draw:
    return Draw(period=period, date=date(2026, 1, 1) + timedelta(days=period % 28),
                numbers=tuple(sorted(set(numbers))))


def random_draws(T: int, seed: int = 0) -> list[Draw]:
    """i.i.d. 随机开奖（最新在前），每期 20 个不同号码。"""
    rng = random.Random(seed)
    return [_draw(2026001 + (T - 1 - i), rng.sample(range(1, 81), 20))
            for i in range(T)]


def alternating_draws(T: int = 40) -> list[Draw]:
    """完全确定：偶数下标期含 1–40，奇数下标期含 41–80（最新在前）。

    每个号码严格「命中/遗漏」交替，故各档暴露期数与命中数是已知闭式。
    """
    out = []
    for i in range(T):
        nums = range(1, 41) if i % 2 == 0 else range(41, 81)
        out.append(_draw(2026001 + (T - 1 - i), nums))
    return out


def _analyze(draws, seed=42):
    class C(_Cfg):
        pass
    C.seed = seed
    return analyze(draws, set(range(1, 41)), compute_base_stats(draws), C())


# ── 状态定义：遗漏长度分档 ────────────────────────────────────

def test_bucket_boundaries():
    assert _bucket(-1) == 0 and _bucket(0) == 0
    assert _bucket(1) == 1 and _bucket(2) == 1
    assert _bucket(3) == 2 and _bucket(5) == 2
    assert _bucket(6) == 3 and _bucket(10 ** 6) == 3


def test_state_sequence_known_pattern():
    """最旧在前：命中 → m=0 → S0；连续遗漏 m 递增并仅换档。"""
    seq = [_draw(1, [5]), _draw(2, [6]), _draw(3, [6]), _draw(4, [6]),
           _draw(5, [6]), _draw(6, [6]), _draw(7, [6]), _draw(8, [5])]
    assert _state_sequence(seq, 5) == [0, 1, 1, 2, 2, 2, 3, 0]
    # 完全未出现的号：m 自增到 T
    assert _state_sequence(seq, 80) == [1, 1, 2, 2, 2, 3, 3, 3]


def test_state_transitions_follow_run_length_recurrence():
    """游程性质：任一步要么命中落到 S0，要么遗漏 +1 进入合法档位。

    合法后继集合（由档位区间推出）：
      S0 -> {0, 1}   S1 -> {0, 1, 2}   S2 -> {0, 2, 3}   S3 -> {0, 3}
    """
    allowed = {0: {0, 1}, 1: {0, 1, 2}, 2: {0, 2, 3}, 3: {0, 3}}
    seq = random_draws(200, seed=3)
    seq = list(reversed(seq))                    # 转成最旧在前
    for n in (1, 9, 40, 41, 80):
        st = _state_sequence(seq, n)
        assert len(st) == len(seq)
        assert all(0 <= s < N_STATES for s in st)
        for a, b in zip(st, st[1:]):
            assert b in allowed[a], f"号码 {n}: {a} -> {b} 非法"


def test_hit_always_resets_to_s0():
    """命中下一期状态必为 S0（游程定义的核心；滑动窗口定义无此性质）。"""
    seq = [_draw(1, [7])] + [_draw(2 + i, [1]) for i in range(30)] + [_draw(40, [7])]
    st = _state_sequence(seq, 7)
    for t, d in enumerate(seq):
        if 7 in d.numbers_set:
            assert st[t] == 0


def test_markov_no_sliding_window():
    """断言实现不是 v1.0 的「近 10 期命中数」滑动窗口状态。"""
    # 稀疏命中：位置 0、20、40 命中，其余遗漏
    hits_at = {0, 20, 40}
    seq = [_draw(1 + i, [7] if i in hits_at else [1]) for i in range(45)]
    st = _state_sequence(seq, 7)
    assert st[20] == 0 and st[40] == 0          # 命中 → S0

    # v1.0 的滑动窗口定义：近 10 期命中数分档（越大越"热"）
    def window_bucket(count: int) -> int:
        if count >= 5:
            return 0
        if count >= 3:
            return 1
        if count >= 1:
            return 2
        return 3

    counts = [1 if 7 in d.numbers_set else 0 for d in seq]
    win = [sum(counts[max(0, t - 9):t + 1]) for t in range(len(seq))]
    win_states = [window_bucket(c) for c in win]

    # 窗口定义在 t=20 处只看得到 1 次命中（近 10 期内），仍判为深遗漏档
    assert win[20] == 1 and win_states[20] != 0
    assert win_states[20] != st[20]
    assert win_states != st
    # 窗口定义会违反游程递推（S3 -> S1 这类"回跳"），游程定义不会
    allowed = {0: {0, 1}, 1: {0, 1, 2}, 2: {0, 2, 3}, 3: {0, 3}}
    violations = sum(1 for a, b in zip(win_states, win_states[1:]) if b not in allowed[a])
    assert violations > 0
    assert all(b in allowed[a] for a, b in zip(st, st[1:]))


def test_realized_transition_support_is_structural():
    """不看平滑矩阵：逐号原始转移计数在非法位置必须恰为 0。"""
    allowed = {0: {0, 1}, 1: {0, 1, 2}, 2: {0, 2, 3}, 3: {0, 3}}
    seq = list(reversed(random_draws(150, seed=11)))
    count = np.zeros((N_STATES, N_STATES))
    for n in range(1, 81):
        st = _state_sequence(seq, n)
        for a, b in zip(st, st[1:]):
            count[a, b] += 1
    for a in range(N_STATES):
        for b in range(N_STATES):
            if b not in allowed[a]:
                assert count[a, b] == 0.0, f"非法转移 {a}->{b} 出现 {count[a,b]} 次"
    # 每个档位都真实出现过
    assert count.sum(axis=1).min() > 0


def test_period_features():
    pairs, span, ent = _period_features(_draw(1, [1, 2, 3]))
    assert pairs == 2.0 and span == 2.0 and ent == pytest.approx(0.0)
    pairs, span, ent = _period_features(_draw(1, list(range(1, 21))))
    assert pairs == 19.0 and span == 19.0
    # 20 号均匀落在 2 个场域 → ln2/ln8
    assert ent == pytest.approx(np.log(2) / np.log(8), rel=1e-9)


# ── 已知转移矩阵 → 已知 χ² 与 p ───────────────────────────────

def test_markov_transition_chisq_on_known_matrix():
    """完全交替的数据 → 各档暴露/命中闭式已知，χ² 与 p 可精确复算。"""
    res = _analyze(alternating_draws(40))
    expo = res.metrics["state_exposure"]
    pk = res.metrics["p_k"]

    # 80 号 × 39 次转移：S0->S1 与 S1->S0 各 1560 次
    assert expo[STATE_LABELS[0]] == 1560
    assert expo[STATE_LABELS[1]] == 1560
    assert expo[STATE_LABELS[2]] == 0
    assert expo[STATE_LABELS[3]] == 0
    assert pk[STATE_LABELS[0]] == 0.0            # 该档从未命中
    assert pk[STATE_LABELS[1]] == 1.0            # 该档必然命中
    # 零暴露 → 回退 i.i.d. 先验 0.25，且检验 p 值为 1
    assert pk[STATE_LABELS[2]] == P0
    assert pk[STATE_LABELS[3]] == P0

    stats = res.diagnostics["pk_test"]
    for k in (0, 1):
        st = stats[STATE_LABELS[k]]
        e, h = st["exposure"], st["hits"]
        assert e > 0
        assert st["p_k"] == pytest.approx(h / e, abs=1e-4)
        # 权威 p 值 = 精确二项检验
        assert st["p_value"] == pytest.approx(round(binomtest(h, e, P0).pvalue, 4))
        # 筛查 p 值 = 2×2 列联表卡方
        expect_chi = chi2_contingency(
            [[h, e - h], [P0 * e, (1 - P0) * e]], correction=False)[1]
        assert st["screen_method"] == "chi2"
        assert st["screen_p"] == pytest.approx(round(float(expect_chi), 4))
        assert st["reject_025"] is True
    for k in (2, 3):
        st = stats[STATE_LABELS[k]]
        assert st["exposure"] == 0 and st["hits"] == 0
        assert st["p_value"] == 1.0 and st["reject_025"] is False
    assert res.metrics["significant_buckets"] == 2


def test_markov_chisq_on_iid_null():
    """i.i.d. p=0.25 数据：p_k ≈ 0.25，四个档位均无显著偏离。

    逐步用模块自己报告的转移计数复算 χ² 与精确 p，验证检验实现。
    """
    res = _analyze(random_draws(120, seed=2024))
    pk = res.metrics["p_k"]
    expo = res.metrics["state_exposure"]
    stats = res.diagnostics["pk_test"]

    for k in range(N_STATES):
        assert expo[STATE_LABELS[k]] > 0
        assert pk[STATE_LABELS[k]] == pytest.approx(P0, abs=0.05)

    for k in range(N_STATES):
        st = stats[STATE_LABELS[k]]
        e, h = st["exposure"], st["hits"]
        assert st["p_k"] == pytest.approx(h / e, abs=1e-4)
        assert st["p_value"] == pytest.approx(round(binomtest(h, e, P0).pvalue, 4))
        expect_chi = chi2_contingency(
            [[h, e - h], [P0 * e, (1 - P0) * e]], correction=False)[1]
        assert st["screen_p"] == pytest.approx(round(float(expect_chi), 4))

    # 各档命中率与 0.25 无显著差异 → 报告必须明说"未检出"
    assert res.metrics["significant_buckets"] == 0
    assert res.diagnostics["rebound_effect"] == "not_detected"
    assert any("未检出" in b.text for b in res.narrative)


def test_pooled_transition_matrix_rows_sum_to_one():
    res = _analyze(random_draws(120, seed=5))
    P = np.asarray(res.diagnostics["transition_matrix_pooled"], dtype=float)
    assert P.shape == (N_STATES, N_STATES)
    # 诊断里的矩阵保留 4 位小数，故容差取 1e-3
    assert np.allclose(P.sum(axis=1), 1.0, atol=1e-3)
    assert np.all(P > 0.0)                       # 拉普拉斯平滑，无零行
    # 结构性零位置远小于允许位置
    assert P[0, 2] < 0.01 * P[0, 1]
    assert P[0, 3] < 0.01 * P[0, 1]
    assert P[3, 1] < 0.01 * P[3, 3]
    assert P[3, 2] < 0.01 * P[3, 3]


# ── 契约 ─────────────────────────────────────────────────────

def test_analyze_degrades_below_min_sample():
    res = _analyze(random_draws(MIN_SAMPLE - 1, seed=6))
    assert res.name == "markov"
    assert res.sufficient is False
    assert res.diagnostics["reason"] == "insufficient_history"
    assert set(res.scores) == set(range(1, 81))
    assert all(v == 0.0 for v in res.scores.values())


def test_analyze_scores_contract():
    res = _analyze(random_draws(120, seed=7))
    assert res.name == "markov"
    assert set(res.scores) == set(range(1, 81))
    assert all(0.0 <= v <= 1.0 for v in res.scores.values())
    assert len(set(round(v, 6) for v in res.scores.values())) > 1
    assert res.metrics["T"] == 120
    assert sum(res.metrics["state_now"].values()) == 80
    assert set(res.metrics["p_k"]) == set(STATE_LABELS)
    assert res.diagnostics["hmm_backend"] in ("builtin_baum_welch", "unavailable")
    # HMM 失败必须显式降级并给出原因
    if res.diagnostics["hmm_backend"] == "unavailable":
        assert res.sufficient is False
        assert "degraded" in res.diagnostics
    assert any(b.section in ("macro", "risk") for b in res.narrative)
