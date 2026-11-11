# -*- coding: utf-8 -*-
"""
单元测试：快乐8循环黄金分割交集系统 (GoldenSplitEngine)
"""
import pytest
from backend.modules.golden_split.golden_split import GoldenSplitEngine


def test_combination_generation():
    engine = GoldenSplitEngine()
    numbers = [10, 14, 20, 28, 47, 56, 58, 65, 71, 75]
    combos = engine.generate_all_combinations(numbers, k=5)
    # C(10, 5) = 252
    assert len(combos) == 252
    # 每个组合必须是 5 码递增元组
    for c in combos:
        assert len(c) == 5
        assert list(c) == sorted(list(c))


def test_partition_disjoint_and_complete():
    engine = GoldenSplitEngine(seed=42)
    numbers = [10, 14, 20, 28, 47, 56, 58, 65, 71, 75]
    combos = engine.generate_all_combinations(numbers, k=5)
    blocks = engine.partition_into_blocks(combos, m_blocks=10, shuffle=True)

    assert len(blocks) == 10
    total_in_blocks = sum(len(b) for b in blocks)
    assert total_in_blocks == 252

    # 验证互斥性：所有块之间交集为空
    seen = set()
    for b in blocks:
        for c in b:
            assert c not in seen, f"重复单式: {c}"
            seen.add(c)
    assert seen == set(combos)


def test_invariant_m_minus_1_strictly():
    """
    核心恒等式测试：
    当大底命中恰好 5 个号码时，在 M 个挖块大底中，
    必然有且仅有 1 个大底挂掉，其余 M-1 个大底全部命中！
    """
    engine = GoldenSplitEngine(seed=42)
    numbers = [10, 14, 20, 28, 47, 56, 58, 65, 71, 75]
    combos = engine.generate_all_combinations(numbers, k=5)
    blocks = engine.partition_into_blocks(combos, m_blocks=10, shuffle=True)
    dug_bases = engine.build_dug_bases(blocks)

    # 模拟任意 5 个号码中奖 (例如: 10, 20, 47, 58, 71)
    simulated_draw = [10, 20, 47, 58, 71, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 15, 16, 17]
    res = engine.verify_invariant(numbers, simulated_draw, blocks, dug_bases)

    assert res["m_hits"] == 5
    assert res["winning_combos_count"] == 1
    assert res["hit_bases_count"] == 9
    assert res["miss_bases_count"] == 1
    assert len(res["missed_base_ids"]) == 1


def test_invariant_ge_6_hits():
    """
    当大底命中 ≥ 6 个号码时，中奖单式有 C(6, 5) = 6 注。
    挂底数 ≤ 1 恒成立（绝大多数甚至全中 10 个大底）。
    """
    engine = GoldenSplitEngine(seed=42)
    numbers = [10, 14, 20, 28, 47, 56, 58, 65, 71, 75]
    combos = engine.generate_all_combinations(numbers, k=5)
    blocks = engine.partition_into_blocks(combos, m_blocks=10, shuffle=True)
    dug_bases = engine.build_dug_bases(blocks)

    # 模拟命中 6 个号码: 10, 14, 20, 28, 47, 56
    simulated_draw = [10, 14, 20, 28, 47, 56, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 15, 16]
    res = engine.verify_invariant(numbers, simulated_draw, blocks, dug_bases)

    assert res["m_hits"] == 6
    assert res["winning_combos_count"] == 6
    assert res["miss_bases_count"] <= 1
    assert res["hit_bases_count"] >= 9
