# -*- coding: utf-8 -*-
"""`kl8/numerics.py` 数值稳健性（§3.6 / §4.14 / §10.2 test_geo_mean_zero）。

全部退化输入（nan/inf/空序列/全 0/全 1/单期）必须：不抛异常、不产生 nan/inf、
输出落在声明值域内。
"""
from __future__ import annotations

import math
import warnings

import pytest

from kl8.numerics import (EPS, GEO_EPS, bh_fdr, bonferroni, clip, clip01,
                          entropy_normalized, finite, fisher_or_skip, geo_mean,
                          hypergeom_mean, hypergeom_sf, hypergeom_var,
                          mean, median, min_detectable_lift, minmax_normalize,
                          normalize, rank_normalize, safe_div, safe_log,
                          sigmoid_normalize, stdev, theoretical_std,
                          wilson_lower)

NAN = float("nan")
INF = float("inf")


def _finite_all(*values) -> None:
    for v in values:
        assert math.isfinite(v), f"出现非有限值: {v!r}"


# ── 退化输入：绝不 nan/inf ────────────────────────────────────

def test_degenerate_inputs_never_nan_or_inf():
    scalars = [NAN, INF, -INF, 0.0, -1.0, -1e308, 1e308]
    for v in scalars:
        _finite_all(safe_div(v, 0.0), safe_div(1.0, v), safe_div(v, v),
                    safe_log(v), finite(v), clip01(v), clip(v, 0.0, 1.0))
    for seq in ([], [NAN], [INF, -INF], [NAN, NAN], [0.0] * 5, [-1.0, 2.0]):
        _finite_all(*rank_normalize(seq), *minmax_normalize(seq),
                    *sigmoid_normalize(seq), median(seq), mean(seq), stdev(seq),
                    entropy_normalized(seq), wilson_lower(int(sum(1 for x in seq if x == x)), 5))
    _finite_all(theoretical_std(0), theoretical_std(-7), theoretical_std(10 ** 6),
                hypergeom_var(0), hypergeom_var(5, 80, 20), hypergeom_mean(),
                hypergeom_sf(0, 5, 80, 20), hypergeom_sf(1, 5, 80, 20),
                wilson_lower(0, 0), wilson_lower(3, 0), min_detectable_lift(277))


def test_normalize_unknown_method_raises():
    assert normalize([1.0, 2.0], "rank") == rank_normalize([1.0, 2.0])
    assert normalize([1.0, 2.0], "minmax") == minmax_normalize([1.0, 2.0])
    assert normalize([1.0, 2.0], "sigmoid") == sigmoid_normalize([1.0, 2.0])
    with pytest.raises(ValueError):
        normalize([1.0, 2.0], "no-such-method")


# ── safe_div / safe_log / finite / clip ───────────────────────

def test_safe_div_guards_zero_and_tiny_denominator():
    assert safe_div(1.0, 0.0) == 0.0
    assert safe_div(0.0, 0.0) == 0.0
    assert safe_div(1.0, 0.0, default=7.5) == 7.5
    assert safe_div(1.0, EPS / 10, 9.0) == 9.0         # 分母过小 → default
    assert safe_div(1.0, 2.0) == 0.5
    assert safe_div(-3.0, 2.0) == -1.5


def test_safe_div_guards_non_finite_operands():
    assert safe_div(NAN, 1.0) == 0.0
    assert safe_div(1.0, NAN) == 0.0
    assert safe_div(1.0, INF) == 0.0
    assert safe_div(INF, 1.0) == 0.0                   # 溢出结果也被压回 default
    assert safe_div(1e308, 1e-308, default=1.0) == 1.0


def test_safe_log_domain():
    assert safe_log(0.0) == 0.0
    assert safe_log(-1.0) == 0.0
    assert safe_log(NAN) == 0.0
    assert safe_log(INF, default=-9.0) == -9.0
    assert safe_log(1.0) == 0.0
    assert safe_log(math.e) == pytest.approx(1.0)


def test_finite_and_clip_families():
    assert finite(NAN) == 0.0 and finite(INF) == 0.0 and finite(-INF) == 0.0
    assert finite("abc") == 0.0 and finite(None) == 0.0
    assert finite(3) == 3.0 and finite(NAN, -1.0) == -1.0
    assert clip01(NAN) == 0.0 and clip01(1.5) == 1.0 and clip01(-0.5) == 0.0
    assert clip01(0.25) == 0.25
    assert clip(5.0, 0.0, 1.0) == 1.0 and clip(-5.0, 0.0, 1.0) == 0.0
    assert clip(NAN, 0.3, 0.7) == 0.3


# ── 归一化 ────────────────────────────────────────────────────

def test_rank_normalize_ties_and_degenerate():
    """§5.2 / §10.2：并列取平均秩；全等 → 全 0.5；单元素 → 0.5。"""
    assert rank_normalize([]) == []
    assert rank_normalize([42.0]) == [0.5]
    assert rank_normalize([5.0, 5.0, 5.0]) == [0.5, 0.5, 0.5]
    assert rank_normalize([10.0, 20.0, 20.0, 30.0]) == [0.0, 0.5, 0.5, 1.0]
    got = rank_normalize([7.0, 7.0, 1.0, 9.0])
    assert got == [0.5, 0.5, 0.0, 1.0]
    for v in got:
        assert 0.0 <= v <= 1.0


def test_rank_normalize_is_monotone_and_finite_with_nan():
    vals = [3.0, NAN, 1.0, 2.0]
    got = rank_normalize(vals)
    assert got == [1.0, 0.0, 0.0 + 1.0 / 3, 2.0 / 3]  # nan 被压为 0 后参与排序
    _finite_all(*got)
    assert all(0.0 <= v <= 1.0 for v in got)


def test_minmax_normalize_degenerate():
    assert minmax_normalize([]) == []
    assert minmax_normalize([3.0, 3.0]) == [0.5, 0.5]
    assert minmax_normalize([2.0, 4.0, 6.0]) == [0.0, 0.5, 1.0]
    assert all(0.0 <= v <= 1.0 for v in minmax_normalize([NAN, INF, 1.0]))


def test_sigmoid_normalize_degenerate():
    assert sigmoid_normalize([]) == []
    assert sigmoid_normalize([1.0, 1.0, 1.0]) == [0.5, 0.5, 0.5]   # mad=0 → 中位数
    got = sigmoid_normalize([1.0, 2.0, 3.0, 1e12])
    assert all(0.0 < v < 1.0 for v in got)             # 极端值被压缩，不溢出


def test_median_mean_stdev_degenerate():
    assert median([]) == 0.0 and mean([]) == 0.0 and stdev([]) == 0.0
    assert median([3.0]) == 3.0
    assert median([1.0, 2.0, 3.0, 4.0]) == 2.5
    assert mean([1.0, 2.0, 3.0]) == 2.0
    assert stdev([1.0, 2.0, 3.0], ddof=1) == pytest.approx(1.0)
    assert stdev([5.0]) == 0.0                         # n - ddof <= 0
    assert stdev([NAN, NAN], ddof=0) == 0.0
    _finite_all(median([NAN, INF]), mean([NAN, INF]), stdev([NAN, INF]))


# ── 几何平均（§4.14）──────────────────────────────────────────

def test_geo_mean_epsilon_keeps_zero_from_collapsing():
    """ε 的真实作用：任一子项为 0 时整体不塌陷为 0（§4.14，已修复）。

    实现为 sqrt(a·b + ε²)，故退化输入的下界恰好是 ε 本身。
    """
    assert GEO_EPS > 0
    assert geo_mean(0.0, 0.5) > 0.0
    assert geo_mean(0.5, 0.0) > 0.0
    assert geo_mean(0.0, 1.0) > 0.0
    # sqrt(0·0.5 + ε²) == ε
    assert geo_mean(0.0, 0.5) == pytest.approx(GEO_EPS, rel=1e-9)
    assert geo_mean(0.5, 0.0) == pytest.approx(GEO_EPS, rel=1e-9)
    # 非退化输入 ≈ sqrt(a·b)
    assert geo_mean(0.5, 0.5) == pytest.approx(math.sqrt(0.25 + GEO_EPS ** 2), rel=1e-12)
    assert geo_mean(0.5, 0.5) == pytest.approx(0.5, abs=1e-5)
    assert geo_mean(0.2, 0.8) == pytest.approx(math.sqrt(0.16 + GEO_EPS ** 2), rel=1e-12)


def test_geo_mean_bounded_and_finite_for_degenerate_inputs():
    for a, b in [(0, 0), (0, 1), (1, 0), (1, 1), (-5, 3), (2, 2),
                 (NAN, 0.5), (INF, 1.0), (-INF, NAN)]:
        v = geo_mean(a, b)
        _finite_all(v)
        assert 0.0 <= v <= 1.0
    # 双零 → ε（ε² 落在乘积内，故不归零）
    assert geo_mean(0.0, 0.0) == pytest.approx(GEO_EPS, rel=1e-9)
    assert geo_mean(1.0, 0.0) == pytest.approx(geo_mean(0.0, 1.0))   # 对称
    assert geo_mean(1.0, 1.0) > geo_mean(0.0, 1.0)


def test_geo_mean_zero_and_one_spec_contract():
    """§10.2 契约（已修复）：geo(1,1) == 1.0 且 geo(0,0) == ε ≠ 0。"""
    assert geo_mean(1.0, 1.0) == 1.0
    assert geo_mean(0.0, 0.0) != 0.0
    assert geo_mean(0.0, 0.0) == pytest.approx(GEO_EPS, rel=1e-9)


# ── 熵 / 显著性 / 校正 ────────────────────────────────────────

def test_entropy_normalized_contract():
    assert entropy_normalized([]) == 0.0
    assert entropy_normalized([0.0, 0.0]) == 0.0       # 总数为 0 → 0
    assert entropy_normalized([1.0, 0.0, 0.0, 0.0]) == 0.0   # 集中于 1 类
    assert entropy_normalized([5.0]) == 0.0            # k <= 1
    assert entropy_normalized([1.0] * 4) == pytest.approx(1.0)   # 均匀 → 1
    assert entropy_normalized([1.0, 1.0, 2.0]) == pytest.approx(0.946394630357186,
                                                                rel=1e-9)
    for counts in ([NAN, 1.0], [-1.0, 2.0, 3.0], [0, 0, 0]):
        v = entropy_normalized(counts)
        _finite_all(v)
        assert 0.0 <= v <= 1.0


def test_theoretical_std_is_binomial_not_empirical():
    assert theoretical_std(0) == 0.0
    assert theoretical_std(-5) == 0.0
    assert theoretical_std(100, 0.25) == pytest.approx(4.330127018922194, rel=1e-12)
    assert theoretical_std(2063, 0.25) == pytest.approx(19.667549415216936, rel=1e-12)
    assert theoretical_std(2063, 0.25) == pytest.approx(math.sqrt(2063 * 0.25 * 0.75))
    # 样本越大 std 越大
    assert theoretical_std(400, 0.25) > theoretical_std(100, 0.25)


def test_hypergeom_helpers():
    assert hypergeom_mean() == pytest.approx(1.25)
    assert hypergeom_mean(5, 80, 20) == pytest.approx(5 * 20 / 80)
    assert hypergeom_var() == pytest.approx(0.8900316455696202, rel=1e-12)
    assert hypergeom_var(5, 1, 20) == 0.0              # N <= 1 退化
    # 超几何方差 < 二项方差（有限总体修正）
    assert hypergeom_var(5) < 5 * 0.25 * 0.75
    assert hypergeom_sf(0, 5, 80, 20) == 1.0           # P(X >= 0) = 1
    assert hypergeom_sf(-3, 5, 80, 20) == 1.0
    p5 = hypergeom_sf(5, 5, 80, 20)
    _finite_all(p5)
    assert 0.0 < p5 < 0.01
    assert p5 == pytest.approx(0.000644924695557607, rel=1e-9)
    assert hypergeom_sf(5, 5, 80, 20) < hypergeom_sf(4, 5, 80, 20)


def test_bh_fdr_and_bonferroni():
    assert bh_fdr([]) == ([], [])
    assert bonferroni([]) == ([], [])

    qvals, rejected = bh_fdr([0.001] * 10)
    assert all(q == pytest.approx(0.001) for q in qvals)     # 单调化到同一 q
    assert rejected == [True] * 10
    assert all(0.0 <= q <= 1.0 for q in qvals)

    q2, rej2 = bh_fdr([0.9, 0.9, 0.9])
    assert rej2 == [False] * 3
    assert all(q == pytest.approx(0.9) for q in q2)          # 已 >= q 阈值 → 不拒绝

    adj, rej = bonferroni([0.01] * 5, alpha=0.05)
    assert all(a == pytest.approx(0.05) for a in adj)
    assert rej == [False] * 5
    adj6, rej6 = bonferroni([0.01] * 5, alpha=0.06)
    assert rej6 == [True] * 5
    assert bonferroni([NAN, 0.001])[0][1] == pytest.approx(0.002)


def test_wilson_lower_bounds():
    assert wilson_lower(0, 0) == 0.0
    assert wilson_lower(3, 0) == 0.0
    assert wilson_lower(0, 10) == 0.0
    assert wilson_lower(5, 10) == pytest.approx(0.2365895936154873, rel=1e-9)
    assert 0.0 <= wilson_lower(10, 10) <= 1.0
    assert wilson_lower(5, 10) < 0.5                   # 下界必然低于点估计
    _finite_all(wilson_lower(10, 10), wilson_lower(0, 1), wilson_lower(1, 1))


def test_wilson_lower_out_of_support_is_clamped():
    """越界 hits 被夹到 [0, trials]，不抛异常（§3.6，已修复）。"""
    for hits, trials in [(-1, 10), (3, 2), (11, 10)]:
        v = wilson_lower(hits, trials)
        _finite_all(v)
        assert 0.0 <= v <= 1.0
    # hits < 0 → 等价于 hits = 0
    assert wilson_lower(-1, 10) == 0.0
    assert wilson_lower(-1, 10) == pytest.approx(wilson_lower(0, 10))
    # hits > trials → 等价于 hits = trials
    assert wilson_lower(3, 2) == pytest.approx(wilson_lower(2, 2))
    assert wilson_lower(11, 10) == pytest.approx(wilson_lower(10, 10))
    # 夹取后按 hits == trials 计算，有限样本下下界 < 1
    assert wilson_lower(11, 10) == pytest.approx(0.7224598312333834, rel=1e-12)
    assert wilson_lower(11, 10) < 1.0


def test_min_detectable_lift_degenerate():
    assert min_detectable_lift(0) == INF               # 文档化的「不可用」哨兵
    assert min_detectable_lift(1) == INF
    mde_277 = min_detectable_lift(277)
    _finite_all(mde_277)
    assert mde_277 == pytest.approx(0.11275642302389895, rel=1e-9)
    assert min_detectable_lift(1000) < mde_277         # 样本越大越灵敏


def test_fisher_or_skip_dispatch():
    chi2, p, method = fisher_or_skip([[30, 20], [25, 35]])
    assert method == "chi2"
    _finite_all(chi2, p)
    assert chi2 == pytest.approx(3.666666666666667, rel=1e-9)
    assert 0.0 <= p <= 1.0

    stat, p2, method2 = fisher_or_skip([[1, 0], [0, 1]])       # 期望频数不足 → Fisher
    assert method2 == "fisher"
    assert stat is None and p2 == pytest.approx(1.0)

    stat3, p3, method3 = fisher_or_skip([[1, 0], [0, 1], [1, 1]])   # 非 2x2 → skipped
    assert (stat3, p3, method3) == (None, None, "skipped")


def test_fisher_or_skip_all_zero_table_stays_finite():
    """全 0 表 → 直接返回 ("degenerate")，不产生 nan/inf、不发 RuntimeWarning。"""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        stat, p, method = fisher_or_skip([[0, 0], [0, 0]])
    runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert runtime_warnings == []
    assert (stat, p, method) == (None, None, "degenerate")
