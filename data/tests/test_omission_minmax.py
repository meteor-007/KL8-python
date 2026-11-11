# -*- coding: utf-8 -*-
"""
纯血统遗漏层最值模块单元测试 (Unit Tests - Pure Edition)
================================================================================
测试覆盖：
1. 零点位依赖断言：完全不传/不读点位数据依然 100% 正常运行
2. 历史 285~290 期真值快照完整性
3. 290 期 OUT 2 与 OUT 3 纯数学高密饱和层识别
4. 纯内生推荐组合输出验证

@author czw
@since 2026-10-31
"""
import pytest
from backend.modules.omission_minmax.engine import PureOmissionMinMaxEngine, run_pure_omission_resonance


class TestPureOmissionMinMax:
    """单元测试套件"""

    def setup_method(self):
        self.engine = PureOmissionMinMaxEngine()

    def test_historical_records_loaded(self):
        """验证 285~290 期历史基准真值完全载入"""
        for p in ["2026285", "2026286", "2026287", "2026288", "2026289", "2026290"]:
            assert p in self.engine.HISTORICAL_RECORDS
            data = self.engine.HISTORICAL_RECORDS[p]
            assert "max_values" in data
            assert "min_values" in data
            assert len(data["max_values"]) > 0

    def test_period_290_pure_saturation_layers(self):
        """测试 290 期在零点位情况下对 OUT=2 与 OUT=3 饱和层的判定"""
        res = self.engine.analyze_pure_matrix("2026290")
        assert res["period"] == "2026290"

        # 验证 OUT=2 层候选全员带星
        out2_candidates = res["max_values"].get(2, [])
        assert out2_candidates == [64, 24, 77]
        for c in out2_candidates:
            assert c in res["star_numbers"]

        # 验证 OUT=3 层候选 4 码全员带星
        out3_candidates = res["max_values"].get(3, [])
        assert out3_candidates == [37, 30, 1, 80]
        for c in out3_candidates:
            assert c in res["star_numbers"]

        # 验证纯内生推荐
        assert res["top3_sharp"] == [64, 24, 1]
        assert len(res["top5_sharp"]) == 5
        assert len(res["pick2_pairs"]) == 4

    def test_pure_run_daily_execution(self):
        """测试纯内生每日运行落盘"""
        analysis = run_pure_omission_resonance("2026290")
        assert analysis is not None
        assert "top3_sharp" in analysis
