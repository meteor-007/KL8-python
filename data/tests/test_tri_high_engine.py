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
        """测试历史手账数据加载与字段结构。

        不断言固定期数：手账是人工逐期录入的，期数随使用自然增减，
        写死「≥17 期」只会让测试在数据变少时误报，却掩盖真正该验的结构问题。
        """
        records = self.engine.load_tri_high_records()
        self.assertGreater(len(records), 0, "历史手账为空 —— 要么文件丢失，要么录入从未落库")
        for rec in records:
            for key in ("period", "repeat_high", "edge_high_left", "edge_high_right", "cold_high"):
                self.assertIn(key, rec, f"{rec.get('period')} 缺少字段 {key}")
        periods = [str(r["period"]) for r in records]
        self.assertEqual(len(periods), len(set(periods)), "手账存在重复期号")
        print(f"✅ 历史手账数据加载成功: 包含 {len(records)} 期，范围 {min(periods)} ~ {max(periods)}")

    def test_auto_wins_and_stats(self):
        """测试开奖自动比对与标黄统计。

        样本期不写死：优先挑「最近一个有开奖号码、且三高确有覆盖」的期做核验，
        而不是绑定某个具体期号 —— 那期数据被清理后测试就会假失败。
        """
        rows = self.engine.get_history_with_wins()
        self.assertGreater(len(rows), 0, "开奖比对结果为空")

        for row in rows:
            self.assertIn("has_draw", row)
            for field in ("repeat_high", "edge_high_left", "cold_high"):
                for cell in row[field]:
                    self.assertIn("is_win", cell, f"{row['period']} 的 {field} 单元格缺少 is_win 标记")

        sample = next((r for r in rows if r.get("has_draw") and r["stats"]["union_count"] > 0), None)
        if sample is None:
            self.skipTest("当前手账尚无「已有开奖且三高有覆盖」的样本期，无法核验命中统计")
        self.assertGreaterEqual(sample["stats"]["union_hits"], 0)
        self.assertLessEqual(sample["stats"]["union_hits"], sample["stats"]["union_count"])
        print(f"✅ 开奖自动标黄与统计核验成功: {sample['period']} 期三高总覆盖 "
              f"{sample['stats']['union_count']} 码, 命中 {sample['stats']['union_hits']} 码 "
              f"(命中率 {sample['stats']['union_hit_rate']*100:.1f}%)")

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
        """测试 QuantDataService 接口封装。

        total 与手账实际期数比对，而不是写死下限：接口该保证的是
        「返回的条数 == 文件里真实存在的条数」，不是「条数足够多」。
        """
        hist_res = self.ds.get_tri_high_history()
        self.assertEqual(hist_res.get("status"), "ok")
        actual = len(self.engine.load_tri_high_records())
        self.assertEqual(hist_res.get("total", 0), actual,
                         f"接口返回 total={hist_res.get('total')}，手账实际 {actual} 期")

        sum_res = self.ds.get_tri_high_summary()
        self.assertEqual(sum_res.get("status"), "ok")
        print(f"✅ QuantDataService 三高 API 接口调用成功 (手账 {actual} 期)")


if __name__ == "__main__":
    unittest.main()
