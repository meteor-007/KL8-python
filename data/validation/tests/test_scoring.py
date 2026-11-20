# -*- coding: utf-8 -*-
"""kl8/scoring.py 测试（§5.2 H1–H7 / §5.3 Top5 多样性 / §5.4 5+2）。

同时覆盖 rank 归一的并列语义（§10.2 test_rank_normalize_ties）、
Top5 的终止条件与放宽分支（test_diversity_pool_lt_5 / test_diversity_zone_relax）。
"""
from __future__ import annotations

import pytest

from kl8.contracts import ModuleResult
from kl8.ensemble import (DIM_NAMES, MAIN_METHODS, FusionResult,
                          aggregate_dimensions, fuse)
from kl8.numerics import normalize, rank_normalize
from kl8.scoring import (Pick52, Selection, select_52, select_top5, zone_label,
                         zone_of)


# ── 测试替身 ──────────────────────────────────────────────────

class _Scoring:
    top_n = 5
    diversity_guard = True
    diversity_max_per_zone = 3
    weights = {"H1": 0.18, "H2": 0.18, "H3": 0.14, "H4": 0.14,
               "H5": 0.12, "H6": 0.12, "H7": 0.12}


class _Report:
    defensive_picks = 2


class _Cfg:
    scoring = _Scoring()
    report = _Report()


def _cfg(top_n=5, guard=True, per_zone=3, defensive=2):
    class S(_Scoring):
        pass
    S.top_n, S.diversity_guard, S.diversity_max_per_zone = top_n, guard, per_zone

    class R(_Report):
        pass
    R.defensive_picks = defensive

    class C(_Cfg):
        scoring = S
        report = R
    return C()


def _fusion(composite: dict[int, float]) -> FusionResult:
    full = {n: composite.get(n, 0.0) for n in range(1, 81)}
    return FusionResult(method_results={}, h_values={}, composite=full)


def _method_results(weights_by_method=None) -> dict[str, ModuleResult]:
    """构造覆盖 MAIN_METHODS + omission 的合法 scores（各不相同）。"""
    out: dict[str, ModuleResult] = {}
    for k, m in enumerate(MAIN_METHODS + ["omission"]):
        out[m] = ModuleResult(
            name=m, scores={n: ((n * (k + 2)) % 97) / 97.0 for n in range(1, 81)})
    if weights_by_method:
        for m, w in weights_by_method.items():
            out[m] = ModuleResult(name=m, scores={n: w for n in range(1, 81)})
    return out


# ── rank 归一（§5.2 / §10.2 test_rank_normalize_ties）───────────

def test_rank_normalize_ties_average_rank():
    assert rank_normalize([1, 2, 2, 4]) == pytest.approx([0.0, 0.5, 0.5, 1.0])
    assert rank_normalize([3, 1, 1, 3]) == pytest.approx(
        [2.5 / 3, 0.5 / 3, 0.5 / 3, 2.5 / 3])
    # 并列组落在两端：平均秩 = 0.5 / 2.5，映射后 1/6、5/6（不是 0/1）
    assert rank_normalize([7, 7, 9, 9]) == pytest.approx(
        [0.5 / 3, 0.5 / 3, 2.5 / 3, 2.5 / 3])


def test_rank_normalize_all_equal_and_single():
    assert rank_normalize([5, 5, 5]) == [0.5, 0.5, 0.5]
    assert rank_normalize([0.0]) == [0.5]
    assert rank_normalize([-1.0]) == [0.5]
    assert rank_normalize([]) == []


def test_rank_normalize_output_range_and_ordering():
    vals = [3.0, -1.0, 8.0, 0.0, 8.0]
    out = rank_normalize(vals)
    assert all(0.0 <= v <= 1.0 for v in out)
    assert out[2] == out[4] > out[0] > out[3] > out[1]
    # 最小值唯一 → 0.0；最大值并列 → 平均秩落在 0.875（不触及 1.0）
    assert min(out) == 0.0
    assert max(out) == pytest.approx(3.5 / 4)
    # 极值唯一时才能取到两端
    assert rank_normalize([1.0, 2.0, 3.0]) == pytest.approx([0.0, 0.5, 1.0])


def test_normalize_dispatch_and_unknown_method():
    assert normalize([1, 2, 3], "rank") == rank_normalize([1, 2, 3])
    assert normalize([1, 2, 3], "minmax") == pytest.approx([0.0, 0.5, 1.0])
    mm = normalize([1.0, 1.0, 1.0], "minmax")
    assert mm == [0.5, 0.5, 0.5]
    sig = normalize([1.0, 2.0, 3.0, 4.0], "sigmoid")
    assert all(0.0 <= v <= 1.0 for v in sig)
    with pytest.raises(ValueError):
        normalize([1, 2], "no_such_method")


# ── 场域工具 ──────────────────────────────────────────────────

def test_zone_of_and_label():
    assert zone_of(1) == 0 and zone_of(10) == 0
    assert zone_of(11) == 1 and zone_of(20) == 1
    assert zone_of(80) == 7
    assert zone_label(1) == "01-10"
    assert zone_label(11) == "11-20"
    assert zone_label(80) == "71-80"


# ── H1–H7 归一化 ──────────────────────────────────────────────

def test_aggregate_dimensions_covers_h1_to_h7_in_unit_range():
    results = _method_results()
    h, skipped = aggregate_dimensions(
        results, {m: 1.0 for m in MAIN_METHODS}, None)
    assert skipped == []
    assert set(h) == set(DIM_NAMES) == set(["H1", "H2", "H3", "H4",
                                           "H5", "H6", "H7"])
    for dim, vec in h.items():
        assert set(vec) == set(range(1, 81)), dim
        assert all(0.0 <= v <= 1.0 for v in vec.values()), dim
        assert len(set(vec.values())) > 1, dim


def test_aggregate_dimensions_skips_missing_inputs():
    results = {"entropy": ModuleResult(name="entropy",
                                       scores={n: 0.5 for n in range(1, 81)})}
    h, skipped = aggregate_dimensions(results, {m: 1.0 for m in MAIN_METHODS}, None)
    assert set(h) == {"H7"}
    assert set(skipped) == {"H1", "H2", "H3", "H4", "H5", "H6"}


def test_fuse_weights_sum_to_one_and_redistribute_skipped_dims():
    results = _method_results()
    f = fuse(results, _Cfg())
    assert f.skipped_dims == []
    assert sum(f.dim_weights.values()) == pytest.approx(1.0)
    assert all(0.0 <= v <= 100.0 for v in f.composite.values())
    assert sum(1 for v in f.composite.values() if v > 0.0) > 1

    # 只有一个维度生效时，其余维度权重先置 0，再按比例分摊给生效维度（已修复）
    only_h7 = fuse({"entropy": ModuleResult(
        name="entropy", scores={n: 0.5 for n in range(1, 81)})}, _Cfg())
    assert len(only_h7.skipped_dims) == 6
    # 生效维度的权重被补到 1.0，综合分只由 H7 贡献
    assert only_h7.dim_weights["H7"] == pytest.approx(1.0)
    for n in range(1, 81):
        assert only_h7.composite[n] == pytest.approx(50.0, abs=1e-6)
    # 未生效维度权重置 0（不保留原权重），Σw 严格 == 1.0（§5.1）
    for dim in ("H1", "H2", "H3", "H4", "H5", "H6"):
        assert only_h7.dim_weights[dim] == pytest.approx(0.0)
    assert sum(only_h7.dim_weights.values()) == pytest.approx(1.0)


def test_fusion_ranked_and_dominant_dim():
    results = _method_results()
    f = fuse(results, _Cfg())
    ranked = f.ranked()
    assert len(ranked) == 80
    comps = [f.composite[n] for n in ranked]
    assert comps == sorted(comps, reverse=True)
    restricted = f.ranked(restrict_to={1, 2, 3})
    assert sorted(restricted) == [1, 2, 3]
    dim, val = f.dominant_dim(10)
    assert dim in DIM_NAMES
    assert 0.0 <= val <= 1.0
    assert val == max(vec.get(10, 0.0) for vec in f.h_values.values())


def test_fuse_uses_config_dimension_weights():
    results = _method_results()
    f = fuse(results, _Cfg())
    base = f.h_values["H1"][1]
    # 只有 H1 有权重时，composite 就是 H1*100
    class S(_Scoring):
        weights = {"H1": 1.0, "H2": 0.0, "H3": 0.0, "H4": 0.0,
                   "H5": 0.0, "H6": 0.0, "H7": 0.0}

    class C(_Cfg):
        scoring = S

    f2 = fuse(results, C())
    assert f2.composite[1] == pytest.approx(round(base, 6) * 100, abs=1e-3)


# ── Top5 多样性（§5.3）────────────────────────────────────────

def test_select_top5_pool_less_than_five():
    """候选池 3 个 → 输出 3 个并置 short flag。"""
    f = _fusion({1: 90.0, 2: 80.0, 3: 70.0})
    sel = select_top5(f, [1, 2, 3], _cfg())
    assert isinstance(sel, Selection)
    assert sel.core == [1, 2, 3]
    assert sel.short is True
    assert sel.relaxed is False


def test_select_top5_diversity_zone_relax():
    """约束过紧（同段候选过多）→ 放宽后取满 5，并置 relaxed flag。"""
    f = _fusion({n: float(100 - n) for n in range(1, 8)})   # 1..7 全在 01-10 段
    sel = select_top5(f, list(range(1, 8)), _cfg())
    assert len(sel.core) == 5
    assert sel.relaxed is True
    assert sel.short is False
    assert any("放宽" in note for note in sel.notes)
    assert sel.core == [1, 2, 3, 4, 5]


def test_select_top5_zone_cap_not_exceeded_when_avoidable():
    """候选池足够分散 → 不触发放宽，且每段计数不超过上限。"""
    f = _fusion({1: 99.0, 2: 98.0, 3: 97.0, 4: 96.0, 5: 95.0,
                 11: 60.0, 21: 59.0, 31: 58.0, 41: 57.0})
    sel = select_top5(f, [1, 2, 3, 4, 5, 11, 21, 31, 41], _cfg())
    assert sel.relaxed is False
    assert sel.short is False
    assert sel.core == [1, 2, 3, 11, 21]
    counts: dict[int, int] = {}
    for n in sel.core:
        counts[zone_of(n)] = counts.get(zone_of(n), 0) + 1
    assert max(counts.values()) <= 3


def test_select_top5_no_duplicates_and_ordering_by_composite():
    f = _fusion({n: float(n) for n in range(1, 81)})
    sel = select_top5(f, list(range(1, 81)), _cfg())
    assert len(sel.core) == 5
    assert len(set(sel.core)) == 5
    assert sel.core[0] == 80
    comps = [f.composite[n] for n in sel.core]
    assert comps == sorted(comps, reverse=True)


def test_select_top5_guard_disabled():
    f = _fusion({n: float(100 - n) for n in range(1, 8)})
    sel = select_top5(f, list(range(1, 8)), _cfg(guard=False))
    assert sel.core == [1, 2, 3, 4, 5]
    assert sel.relaxed is False
    assert any("已关闭" in note for note in sel.notes)


def test_select_top5_dedupes_candidates_and_handles_empty():
    f = _fusion({1: 5.0, 2: 4.0})
    sel = select_top5(f, [1, 1, 2, 1], _cfg())
    assert sel.core == [1, 2]
    assert sel.short is True
    empty = select_top5(f, [], _cfg())
    assert empty.core == [] and empty.short is True


def test_select_top5_top_n_from_config():
    f = _fusion({n: float(n) for n in range(1, 81)})
    sel = select_top5(f, list(range(1, 81)), _cfg(top_n=3))
    assert len(sel.core) == 3
    sel = select_top5(f, list(range(1, 81)), _cfg(top_n=8, per_zone=1))
    assert len(sel.core) == 8


# ── 5+2（§5.4）────────────────────────────────────────────────

def test_select_52_excludes_core_and_orders_by_omission():
    f = _fusion({})
    ct = ModuleResult(name="contrarian",
                      scores={n: 0.4 for n in range(1, 81)},
                      metrics={"gate_passed": [9, 7, 60, 8]})
    omission = {9: 0.2, 7: 0.9, 60: 0.5, 8: 0.1}
    picks = select_52(f, [7, 60], set(range(1, 81)), {"contrarian": ct},
                      omission, ct, _cfg())
    assert isinstance(picks, Pick52)
    assert picks.core == [7, 60]
    # 7 与 60 在核心内被剔除；剩 9(0.2)、8(0.1) → 取前 2
    assert picks.defensive == [9, 8]
    assert picks.short_defensive is False


def test_select_52_short_when_candidates_insufficient():
    f = _fusion({})
    ct = ModuleResult(name="contrarian", scores={}, metrics={"gate_passed": [9]})
    picks = select_52(f, [1, 2], {9}, {}, None, ct, _cfg())
    assert picks.defensive == [9]
    assert picks.short_defensive is True
    assert any("不足" in note for note in picks.notes)


def test_select_52_empty_when_no_gate_passed():
    f = _fusion({})
    ct = ModuleResult(name="contrarian", scores={}, sufficient=False)
    picks = select_52(f, [], {1, 2, 3}, {}, None, ct, _cfg())
    assert picks.defensive == []
    assert picks.short_defensive is True
    assert any("为空" in note for note in picks.notes)


def test_select_52_uses_heatmap_rebound_candidates():
    """heatmap 低能量(<=0.5) 且 omission 高(>=0.5) 的号进入备防候选。"""
    f = _fusion({})
    heatmap = ModuleResult(name="heatmap",
                           scores={n: 0.2 for n in range(1, 81)})
    ct = ModuleResult(name="contrarian", scores={}, metrics={"gate_passed": []})
    omission = {11: 0.8, 12: 0.4, 21: 0.9}
    picks = select_52(f, [1, 2, 3], {1, 2, 3, 11, 12, 21},
                      {"heatmap": heatmap, "contrarian": ct}, omission, ct, _cfg())
    assert picks.defensive == [21, 11]          # omission 降序
    assert picks.short_defensive is False
    # omission 低的 12 号不入选
    assert 12 not in picks.defensive


def test_select_52_heatmap_insufficient_ignored():
    f = _fusion({})
    heatmap = ModuleResult(name="heatmap", scores={}, sufficient=False)
    ct = ModuleResult(name="contrarian", scores={}, metrics={"gate_passed": [5]})
    picks = select_52(f, [], {5, 6}, {"heatmap": heatmap},
                      {5: 0.9, 6: 0.9}, ct, _cfg())
    assert picks.defensive == [5]               # 5 < 6，omission 并排时按号升序


def test_select_52_filters_candidates_outside_pool():
    f = _fusion({})
    ct = ModuleResult(name="contrarian", scores={},
                      metrics={"gate_passed": [9, 50, 70]})
    picks = select_52(f, [], {9, 50}, {9: 0.9, 50: 0.5, 70: 1.0}, None, ct, _cfg())
    assert picks.defensive == [9, 50]            # 70 不在候选池
    assert 70 not in picks.defensive


def test_select_52_defensive_picks_from_config():
    f = _fusion({})
    ct = ModuleResult(name="contrarian", scores={},
                      metrics={"gate_passed": [9, 8, 7, 6, 5]})
    omission = {9: 0.1, 8: 0.2, 7: 0.3, 6: 0.4, 5: 0.5}
    picks = select_52(f, [], set(range(1, 81)), {}, omission, ct,
                      _cfg(defensive=3))
    assert picks.defensive == [5, 6, 7]
    assert picks.short_defensive is False


def test_select_52_falls_back_to_contrarian_top_when_no_gate_list():
    f = _fusion({})
    ct = ModuleResult(name="contrarian",
                      scores={n: n / 100.0 for n in range(1, 81)})
    picks = select_52(f, [], set(range(1, 81)), {}, {}, ct, _cfg())
    # metrics 里没有 gate_passed → 回退 contrarian.top(want*4) = top8（73..80），
    # 再按 omission（全 0）→ 号升序取前 2
    assert picks.defensive == [73, 74]


def test_module_result_top_clips_scores_to_unit_range():
    """ModuleResult 构造时把 scores 夹到 [0,1]，故 top() 的次序由夹取后的值决定。"""
    raw = ModuleResult(name="x", scores={n: float(n) for n in range(1, 81)})
    assert all(v == 1.0 for v in raw.scores.values())
    assert raw.top(3) == [1, 2, 3]
    scaled = ModuleResult(name="y", scores={n: n / 80.0 for n in range(1, 81)})
    assert scaled.top(3) == [80, 79, 78]
