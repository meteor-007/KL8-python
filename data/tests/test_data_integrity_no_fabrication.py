# -*- coding: utf-8 -*-
"""
数据诚信回归测试 —— 防"假数字与硬编码误导"复发（整改清单 A 包）

守护的规则（每条都对应一次真实事故）：
  1. 上游无数据时，不得编造预测号码/统计量冒充真实产出；
  2. 聚合指标（命中率/Lift）在无可对账样本时必须为 null，不得回填 0 或中性 1.0；
  3. 无数据期不得摊入汇总分母，必须显式列入 missing_periods；
  4. 选2搭档只能是"空"或"恰好 2 个 1~80 的号码"，禁止用 0 占位凑数；
  5. 未做回测的组合不得输出 Lift 结论；权重必须标注来源。
"""
import os
import sys
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.api.data_service import QuantDataService

FAKE_PERIOD = 999999


class TestNoFabricatedNumbers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = QuantDataService(PROJ_DIR)

    def test_01_live_prediction_without_history_is_empty(self):
        """无任何历史时：搭档为空、无回测类字段为 null、无编造的雷达指标。"""
        empty = self.service._compute_live_prediction([])
        self.assertEqual(empty["golden_pair"], [])
        self.assertIsNone(empty["golden_pair_lift"])
        self.assertIsNone(empty["golden_pair_cooc"])
        self.assertIsNone(empty["golden_pair_score"])
        self.assertTrue(empty["data_missing"])
        self.assertNotIn("radar_data", empty, "编造的 radar_data 必须已移除")
        self.assertTrue(empty.get("weights_source"), "权重必须标注来源")

    def test_02_live_prediction_never_pads_pair_with_zero(self):
        """真实历史下：搭档要么为空要么恰好 2 码，绝不出现 0 占位。"""
        history = self.service.load_history(limit=0)
        if not history:
            self.skipTest("无历史数据，跳过")
        live = self.service._compute_live_prediction(history)
        pair = live["golden_pair"]
        self.assertIn(len(pair), (0, 2))
        self.assertNotIn(0, pair)
        self.assertTrue(all(1 <= n <= 80 for n in pair))

    def test_03_meta_gold_review_no_fabricated_fallback(self):
        """上游三路池全空时：不得编造 [1,2,3,4,5]，且不得计入汇总分母。"""
        svc = QuantDataService(PROJ_DIR)
        svc.load_history = lambda limit=0: [
            {"period": FAKE_PERIOD, "numbers": list(range(1, 21))}
        ]
        svc._compute_live_prediction = lambda hist, n=30: {
            "top5_gold": [], "hidden_energy_5": [], "top12_pool": []
        }

        res = svc.get_meta_gold_review(n=1)
        row = res["rows"][0]
        summary = res["summary"]

        self.assertEqual(row["meta_top5"], [], "不得编造兜底号码")
        self.assertNotEqual(row["meta_top5"], [1, 2, 3, 4, 5])
        self.assertTrue(row["data_missing"])
        self.assertIsNone(row["lift"])
        self.assertIsNone(row["hit_rate"])

        self.assertEqual(summary["missing_periods"], [FAKE_PERIOD])
        self.assertEqual(summary["total_periods"], 0, "缺失期不得摊入分母")
        self.assertIsNone(summary["overall_lift"])
        self.assertIsNone(summary["avg_top5_hits"])
        self.assertIsNone(summary["supreme_hit_rate"])

    def test_04_meta_gold_review_rows_are_self_consistent(self):
        """有产出的行必须给出真实 lift；不得出现中性 1.0 兜底或编造号码。"""
        res = self.service.get_meta_gold_review(n=30)
        self.assertEqual(res["status"], "ok")
        for row in res["rows"]:
            if row["data_missing"]:
                self.assertEqual(row["meta_top5"], [])
                self.assertIsNone(row["lift"])
                continue
            self.assertNotEqual(row["meta_top5"], [1, 2, 3, 4, 5])
            self.assertGreater(row["total_picks"], 0)
            self.assertIsNotNone(row["lift"])
            self.assertTrue(all(1 <= n <= 80 for n in row["meta_top5"]))

    def test_05_latest_prediction_has_no_radar_data_fabrication(self):
        """最新预测载荷不得再携带固定编造的 radar_data。"""
        pred = self.service.get_latest_prediction()
        self.assertNotIn("radar_data", pred)


if __name__ == "__main__":
    unittest.main(verbosity=2)
