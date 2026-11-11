# -*- coding: utf-8 -*-
"""
16 期中热滑动窗口位置解剖引擎单元测试 (Test Sixteen Deep Inspector)
================================================================================
测试目标：
1. 80 码物理守恒测试：出窗 20 码 + 留窗 60 码 = 80 码严格守恒且无重叠；
2. 历史期开奖位置解剖准确性测试：出窗命中 + 留窗命中 = 20 码开奖；
3. 频次分桶全覆盖测试：80 个号码被完全划分至频次分桶；
4. 报告生成与非空校验。

@author czw
@since 2026-11-03
"""
import pytest
from backend.modules.sixteen.sixteen_deep_inspector import SixteenDeepInspector


class TestSixteenDeepInspector:
    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.inspector = SixteenDeepInspector()

    def test_80_balls_conservation(self):
        """测试 80 码出留窗绝对守恒"""
        insp = self.inspector.inspect_period_locations(2026292)
        out_nums = set(insp["out_window_nums"])
        in_nums = set(insp["in_window_nums"])

        assert len(out_nums) == 20, f"出窗码数量应为 20，实际为 {len(out_nums)}"
        assert len(in_nums) == 60, f"留窗码数量应为 60，实际为 {len(in_nums)}"
        assert len(out_nums.intersection(in_nums)) == 0, "出窗区与留窗区严禁交叠！"
        assert len(out_nums.union(in_nums)) == 80, "出窗与留窗并集必须等于 80 码！"

    def test_actual_draw_location_audit(self):
        """测试当期实开 20 码位置对账精确无遗漏"""
        insp = self.inspector.inspect_period_locations(2026292)
        audit = insp["actual_audit"]
        assert audit, "第 2026292 期包含真实开奖，必须生成 audit 结果"

        out_count = audit["out_hit_count"]
        in_count = audit["in_hit_count"]
        total_hits = out_count + in_count
        assert total_hits == 20, f"出窗命中({out_count})与留窗命中({in_count})之和必须恒等于当期开出 20 码！"

    def test_historical_review_stats(self):
        """测试近 30 期历史位置复盘统计"""
        stats = self.inspector.review_historical_positions(n_periods=30)
        assert stats["evaluated_periods"] == 30
        assert 3.5 <= stats["avg_out_window_hits"] <= 6.0, "出窗均期命中应在 3.5~6.0 码之间"
        assert 14.0 <= stats["avg_in_window_hits"] <= 16.5, "留窗均期命中应在 14.0~16.5 码之间"

    def test_markdown_summary_generation(self):
        """测试操盘手大白话报告生成"""
        summary = self.inspector.generate_plain_analysis_summary(2026293)
        assert isinstance(summary, str) and len(summary) > 200
        assert "出留窗守恒定律" in summary
        assert "核心产粮区定律" in summary
