# -*- coding: utf-8 -*-
"""
快乐8 决策树驱动 012路 × 质合特征推演与智能缩水系统单元测试
================================================================================
测试目标：
1. 80 码六维正交子池物理完备性（无交集、无遗漏、总和严格为 80 码）；
2. 特征工程维度守恒与数值安全性（13 维特征，无 NaN，无除零）；
3. 决策树与随机森林海选团预测概率边界正常；
4. 正交剪枝大底数量恒等于 30 码，质合与 012 路配比符合大数定律守卫线；
5. Top3、Top5 与黄金选2搭档格式与业务契约 100% 保真。

@author Antigravity Quant Team
@since 2026-10-23
"""

import pytest
import numpy as np
from backend.modules.road_prime_shrink.tree_engine import (
    TreeRoadPrimeShrinkEngine,
    ALL_POOLS,
    PRIMES_SET,
    FEATURE_COLUMNS,
    TOTAL_BALLS,
)


@pytest.fixture
def mock_history_data():
    """构造包含 40 期的模拟真实开奖数据"""
    history = []
    np.random.seed(20261023)
    for i in range(1, 45):
        # 模拟每期从 1~80 中不重复抽取 20 码
        draw = sorted(np.random.choice(range(1, 81), size=20, replace=False).tolist())
        history.append({
            "period": f"2026{i:03d}",
            "numbers": draw,
        })
    return history


class TestTreeRoadPrimeShrink:

    def test_orthogonal_pools_integrity(self):
        """测试 1: 验证六大正交子池完备性与互斥性"""
        all_balls_collected = []
        for name, balls in ALL_POOLS.items():
            assert len(balls) > 0, f"子池 {name} 不能为空"
            all_balls_collected.extend(balls)

        # 验证总数严格为 80 码
        assert len(all_balls_collected) == TOTAL_BALLS, f"所有子池球数总和必须为 80，实际为 {len(all_balls_collected)}"
        # 验证无任何重复号码
        assert len(set(all_balls_collected)) == TOTAL_BALLS, "各个正交子池之间绝对不能有重合号码"
        # 验证 1~80 号码全覆盖
        assert set(all_balls_collected) == set(range(1, 81)), "子池必须 100% 覆盖 1~80 号码"

        # 特别验证 0路质数仅包含 03
        assert ALL_POOLS["0路质数"] == [3], "0路质数在 1~80 范围内有且仅有 03"

    def test_feature_engineering_and_inference(self, mock_history_data):
        """测试 2: 验证特征工程矩阵抽取与决策树全链路推演"""
        engine = TreeRoadPrimeShrinkEngine(mock_history_data, train_window=30)
        res = engine.execute_inference()

        # 验证基础返回结构
        assert "meta" in res
        assert "feature_ranking" in res
        assert "top3_gold" in res
        assert "top5_gold" in res
        assert "top30_large_base" in res
        assert "pick2_pairs" in res
        assert "all_80_scores" in res

        # 验证特征重要性列表包含所有 13 个特征
        assert len(res["feature_ranking"]) == len(FEATURE_COLUMNS)
        total_importance = sum(item["importance"] for item in res["feature_ranking"])
        assert 0.95 <= total_importance <= 1.05, f"特征重要性总和应接近 1.0，实际为 {total_importance}"

        # 验证全盘 80 码评分
        scores = res["all_80_scores"]
        assert len(scores) == 80
        for s in scores:
            assert 0.0 <= s["prob"] <= 1.0, f"号码 {s['ball']} 预测概率超出 [0, 1] 范围: {s['prob']}"

    def test_shrink_large_base_guards(self, mock_history_data):
        """测试 3: 验证 30 码、25 码与 20 码实战大底的守恒与剪枝约束"""
        engine = TreeRoadPrimeShrinkEngine(mock_history_data, train_window=30)
        res = engine.execute_inference()

        top30 = res["top30_large_base"]
        top25 = res["top25_mid_base"]
        top20 = res["top20_core_base"]

        # 大底数量恒为 30 码、25 码、20 码且升序不重复
        assert len(top30) == 30 and len(set(top30)) == 30 and top30 == sorted(top30)
        assert len(top25) == 25 and len(set(top25)) == 25 and top25 == sorted(top25)
        assert len(top20) == 20 and len(set(top20)) == 20 and top20 == sorted(top20)

        # 质数数量约束
        prime_count30 = sum(1 for b in top30 if b in PRIMES_SET)
        assert 4 <= prime_count30 <= 8, f"30 码大底质数异常: {prime_count30}"
        prime_count25 = sum(1 for b in top25 if b in PRIMES_SET)
        assert 3 <= prime_count25 <= 7, f"25 码大底质数异常: {prime_count25}"
        prime_count20 = sum(1 for b in top20 if b in PRIMES_SET)
        assert 2 <= prime_count20 <= 6, f"20 码大底质数异常: {prime_count20}"

        # 012路均衡约束 (每一路均不能被饿死)
        for name, basket in [("30码", top30), ("25码", top25), ("20码", top20)]:
            r0 = sum(1 for b in basket if b % 3 == 0)
            r1 = sum(1 for b in basket if b % 3 == 1)
            r2 = sum(1 for b in basket if b % 3 == 2)
            assert r0 >= 3, f"{name} 0路过少: {r0}"
            assert r1 >= 3, f"{name} 1路过少: {r1}"
            assert r2 >= 3, f"{name} 2路过少: {r2}"

    def test_pick2_and_top_picks_contract(self, mock_history_data):
        """测试 4: 验证核心 Top3、Top5 与选 2 搭档的契约有效性"""
        engine = TreeRoadPrimeShrinkEngine(mock_history_data, train_window=30)
        res = engine.execute_inference()

        top3 = res["top3_gold"]
        top5 = res["top5_gold"]
        pairs = res["pick2_pairs"]

        assert len(top3) == 3
        assert len(set(top3)) == 3
        assert len(top5) == 5
        assert len(set(top5)) == 5
        # Top3 必须全部包含在 Top5 中
        assert set(top3).issubset(set(top5))

        # 选 2 搭档必须为 3 组
        assert len(pairs) == 3
        for p in pairs:
            p_nums = p["pair"]
            assert len(p_nums) == 2
            assert p_nums[0] != p_nums[1]
            assert 1 <= p_nums[0] <= 80
            assert 1 <= p_nums[1] <= 80
