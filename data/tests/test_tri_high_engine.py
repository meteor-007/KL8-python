# -*- coding: utf-8 -*-
"""
三高特征量化推演与录入管理系统单元测试 (Unit Tests for Tri-Category Points System)
"""
import os
import sys
import unittest

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.core.tri_high_engine import TriHighResonanceEngine
from backend.api.data_service import QuantDataService


class TestTriHighSystem(unittest.TestCase):
    def setUp(self):
        self.engine = TriHighResonanceEngine(_PROJ_DIR)
        self.ds = QuantDataService(_PROJ_DIR)

    def test_load_records(self):
        """测试历史手账数据加载"""
        records = self.engine.load_tri_high_records()
        self.assertTrue(len(records) >= 17, "历史手账数据应至少包含 17 期 (221~238期)")
        first = records[0]
        self.assertIn("period", first)
        self.assertIn("repeat_high", first)
        self.assertIn("edge_high_left", first)
        self.assertIn("edge_high_right", first)
        self.assertIn("cold_high", first)
        print(f"✅ 历史手账数据加载成功: 包含 {len(records)} 期，最新期: {first['period']}")

    def test_auto_wins_and_stats(self):
        """测试开奖自动比对与标黄统计"""
        rows = self.engine.get_history_with_wins()
        self.assertTrue(len(rows) >= 17)
        # 验证中奖标黄状态字段
        for row in rows[:5]:
            self.assertTrue("has_draw" in row)
            for cell in row["repeat_high"]:
                self.assertIn("is_win", cell)
            for cell in row["edge_high_left"]:
                self.assertIn("is_win", cell)
            for cell in row["cold_high"]:
                self.assertIn("is_win", cell)
        
        # 抽样检查 238 期
        row_238 = next((r for r in rows if r["period"] == "2026238"), None)
        self.assertIsNotNone(row_238)
        self.assertTrue(row_238["stats"]["union_count"] > 0)
        print(f"✅ 开奖自动标黄与统计核验成功: 238 期三高总覆盖 {row_238['stats']['union_count']} 码, 命中 {row_238['stats']['union_hits']} 码 (命中率 {row_238['stats']['union_hit_rate']*100:.1f}%)")

    def test_resonance_analysis(self):
        """测试三高×点位深度共振推演与推荐"""
        res = self.engine.run_tri_high_analysis()
        self.assertEqual(res.get("status"), "ok")
        rec = res.get("recommendations", {})
        self.assertIn("resonance_gold_single", rec)
        self.assertIn("gold_pair", rec)
        self.assertEqual(len(rec.get("gold_pair", [])), 2)
        self.assertEqual(len(rec.get("top5", [])), 5)
        self.assertEqual(len(rec.get("top12", [])), 12)
        print(f"✅ 三高×点位共振推演通过: 尖刀金胆【{rec['resonance_gold_single']:02d}】, 黄金选2 [{rec['gold_pair'][0]:02d}-{rec['gold_pair'][1]:02d}]")

    def test_data_service_api(self):
        """测试 QuantDataService 接口封装"""
        hist_res = self.ds.get_tri_high_history()
        self.assertEqual(hist_res.get("status"), "ok")
        self.assertTrue(hist_res.get("total", 0) >= 17)

        sum_res = self.ds.get_tri_high_summary()
        self.assertEqual(sum_res.get("status"), "ok")
        print("✅ QuantDataService 三高 API 接口调用成功")


if __name__ == "__main__":
    unittest.main()
