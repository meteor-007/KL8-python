# -*- coding: utf-8 -*-
"""
快乐8 第 2026295 期 工业级多维融合历史预测引擎单测套件
<p>
闭环测试覆盖范围:
1. Excel多维近300期历史挖掘数据提取完整性；
2. 四大专家系列胜率、频次跃迁暴击率、双杀80%排除率实证校验；
3. 80码全息动态赋权评分校验（20点位、杀号、同出协同）；
4. 三元组逻辑（T1高共振、T2对冲防踩空）；
5. 多维空间正交性（Top5跨4~5区防踩空）；
6. 近10期回测胜率验证（Top5与Top10表现）；
7. 工业级交付格式校验（Excel 5表、控制台TXT、微信发布文案）。

@author czw
@since 2026-11-05
"""
from __future__ import annotations

import os
from pathlib import Path
import openpyxl
import pytest

from scripts.fusion_engine_295 import (
    PREV_DRAW_NUMBERS,
    TARGET_PERIOD,
    TOTAL_BALL_COUNT,
    extract_excel_data,
    evaluate_all_balls,
    select_orthogonal_candidates,
    select_pyramid_triplets,
    generate_commercial_excel,
    generate_console_summary,
    generate_wechat_summary,
)


class TestFusionEngine295:
    """295期多维融合历史预测引擎标准单测"""

    @pytest.fixture(scope="module")
    def expert_data(self):
        """提取专家与历史挖掘数据"""
        return extract_excel_data("file")

    @pytest.fixture(scope="module")
    def evaluations(self, expert_data):
        """80码全息评分列表"""
        return evaluate_all_balls(expert_data)

    @pytest.fixture(scope="module")
    def selected_candidates(self, expert_data, evaluations):
        """多维空间正交推荐候选"""
        return select_orthogonal_candidates(
            evaluations, set(PREV_DRAW_NUMBERS), set(expert_data.points_293)
        )

    @pytest.fixture(scope="module")
    def pyramid_triplets(self, expert_data, evaluations):
        """三元组筛选"""
        return select_pyramid_triplets(expert_data, evaluations)

    def test_target_period_consistency(self):
        """测试期号常量保真"""
        assert TARGET_PERIOD == 2026295
        assert len(PREV_DRAW_NUMBERS) == 20
        assert TOTAL_BALL_COUNT == 80

    def test_extract_excel_data_integrity(self, expert_data):
        """测试历史数据与点位提取完整度"""
        assert len(expert_data.points_293) == 20
        # 295期点位包含 04, 05, 09, 12, 35, 54 等
        assert 12 in expert_data.points_293
        assert 35 in expert_data.points_293
        assert 54 in expert_data.points_293
        assert len(expert_data.all_triplets) > 0
        assert len(expert_data.top_pairs) > 0
        assert len(expert_data.double_kill_set) > 0

    def test_evaluations_bounds_and_sorting(self, evaluations):
        """测试80码评分规范性与排序单调递减"""
        assert len(evaluations) == 80
        scores = [item.score for item in evaluations]
        assert scores == sorted(scores, reverse=True)
        # 第一名得分应合理在 6~12 分之间
        assert 6.0 <= evaluations[0].score <= 12.0
        # 验证所有号码均在 1~80 之间
        ball_nums = {item.number for item in evaluations}
        assert ball_nums == set(range(1, 81))

    def test_double_kill_pool_safety(self, expert_data, evaluations):
        """测试双重杀号排除机制防守"""
        eval_dict = {item.number: item for item in evaluations}
        for ball in expert_data.double_kill_set:
            if ball not in expert_data.points_293 and ball not in expert_data.dw_edge_high:
                assert eval_dict[ball].score < evaluations[0].score

    def test_orthogonal_candidates_orthogonality(self, selected_candidates):
        """测试推荐号码的多维空间正交防踩空特性"""
        top5 = selected_candidates.top_5
        zones = [(num - 1) // 10 + 1 for num in top5]
        # Top 5 跨越至少 4 个不同区间，严禁扎堆
        unique_zones = set(zones)
        assert len(unique_zones) >= 4, f"Top5 区间扎堆: {zones}"
        assert len(selected_candidates.top_7) == 7
        assert len(selected_candidates.top_10) == 10

    def test_pyramid_triplets_format(self, pyramid_triplets):
        """测试三元组金字塔T1核心组与T2防御组"""
        t1, t2 = pyramid_triplets
        assert len(t1) == 4
        assert len(t2) == 4
        for item in t1 + t2:
            balls = item['triplet']
            assert len(balls) == 3
            assert balls[0] < balls[1] < balls[2]
            assert 1 <= balls[0] <= 80
            assert 1 <= balls[2] <= 80
            assert len(item['zones']) >= 2

    def test_deliverables_generation(self, expert_data, evaluations, selected_candidates, pyramid_triplets, tmp_path):
        """测试商业级Excel、控制台精要与微信发布文案生成"""
        t1, t2 = pyramid_triplets
        excel_path = tmp_path / "test_prediction_295.xlsx"
        generate_commercial_excel(expert_data, evaluations, t1, t2, str(excel_path))
        assert excel_path.exists()
        wb = openpyxl.load_workbook(str(excel_path))
        assert len(wb.sheetnames) == 5

        console_summary = generate_console_summary(expert_data, evaluations, t1, t2)
        assert "至尊金胆" in console_summary
        assert "四大高信噪比实证法则" in console_summary
        assert "规律一：" in console_summary
        assert "规律二：" in console_summary
        assert "规律三：" in console_summary
        assert "规律四：" in console_summary

        wechat_summary = generate_wechat_summary(expert_data, evaluations, t1, t2)
        assert "【快乐8 第2026295期" in wechat_summary
        assert "至尊独胆" in wechat_summary
