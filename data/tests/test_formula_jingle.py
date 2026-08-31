# -*- coding: utf-8 -*-
"""
顺口溜口诀规律与组合带出系统 单元测试套件
==========================================
"""
import os
import unittest
import tempfile
import shutil

import sys
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)

from core.formula_jingle.jingle_engine import (
    load_jingle_rules,
    fired_rules,
    at_least_one_baseline,
    predict_jingle,
    save_jingle_prediction,
    compute_target_issue,
    BASELINE_PAIR,
    BASELINE_TRIPLE,
)
from core.formula_jingle.jingle_reviewer import review_jingle
from core.formula_jingle.jingle_cross_validator import cross_validate_jingle


class TestFormulaJingle(unittest.TestCase):
    def setUp(self):
        self.rules, self.meta = load_jingle_rules()
        self.dummy_draws = [
            (2026201, "2026-07-30", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]),
            (2026202, "2026-07-31", [3, 8, 24, 33, 50, 57, 71, 72, 78, 10, 20, 30, 40, 50, 60, 70, 80, 22, 23, 25]),
            (2026203, "2026-08-01", [2, 3, 38, 39, 46, 53, 57, 60, 69, 71, 72, 1, 4, 5, 6, 7, 8, 9, 11, 12]),
        ]

    def test_load_rules_count(self):
        """测试90条精英口诀是否完整加载"""
        self.assertEqual(len(self.rules), 90)
        self.assertIn("val_end_period", self.meta)
        pair_rules = [r for r in self.rules if r["kind"] == "pair_pair"]
        triple_rules = [r for r in self.rules if r["kind"] == "triple_single"]
        self.assertEqual(len(pair_rules) + len(triple_rules), 90)
        self.assertEqual(len(pair_rules), 74)
        self.assertEqual(len(triple_rules), 16)

    def test_hypergeometric_baseline(self):
        """测试超几何无放回精密基线计算"""
        self.assertEqual(at_least_one_baseline(0), 0.0)
        # 选1个号至少中1个 = 20/80 = 0.25
        self.assertAlmostEqual(at_least_one_baseline(1), 0.25, places=4)
        # 选2个号至少中1个 = 1 - C(60,2)/C(80,2) = 1 - 1770/3160 = 0.43987
        self.assertAlmostEqual(at_least_one_baseline(2), 1 - 1770 / 3160, places=4)
        # 选5个号
        self.assertGreater(at_least_one_baseline(5), 0.70)
        # 选12个号
        self.assertGreater(at_least_one_baseline(12), 0.95)

    def test_target_issue_calculation(self):
        """测试期号递增推算"""
        self.assertEqual(compute_target_issue(2026230), "2026231")
        self.assertEqual(compute_target_issue("2026099"), "2026100")

    def test_fired_rules(self):
        """测试开奖号码触发口诀匹配"""
        draw_nums = [3, 33, 8, 50, 10, 20, 30, 40, 50, 60, 70, 80, 1, 2, 4, 5, 6, 7, 9, 11]
        fired = fired_rules(self.rules, draw_nums)
        self.assertIsInstance(fired, list)
        self.assertGreater(len(fired), 0)
        for r, pred, w in fired:
            self.assertTrue(set(r["trigger"]).issubset(set(draw_nums)))
            self.assertEqual(pred, r["predict"])
            self.assertGreater(w, 0.0)

    def test_predict_jingle(self):
        """测试每日口诀预测生成"""
        res = predict_jingle(self.dummy_draws, self.rules)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["latest_issue"], "2026203")
        self.assertEqual(res["target_issue"], "2026204")
        self.assertIn("recommended_numbers", res)
        self.assertIn("fired_details", res)
        self.assertIn("at_least_one_baseline", res)

    def test_review_jingle(self):
        """测试对账复盘逻辑"""
        rev = review_jingle(self.dummy_draws, self.rules, n=2, sel_cut=2026210)
        self.assertEqual(rev["status"], "ok")
        self.assertIn("pairs", rev)
        self.assertIn("metrics", rev)
        self.assertIn("segments", rev["metrics"])

    def test_cross_validate_jingle(self):
        """测试交叉风控审计与打标"""
        rec_nums = [3, 38, 57, 72]
        custom_kill = {3}
        cross = cross_validate_jingle(rec_nums, custom_kill_set=custom_kill)
        self.assertIn(3, cross["clash_numbers"])
        self.assertNotIn(38, cross["clash_numbers"])
        self.assertEqual(len(cross["detailed_tags"]), 4)

    def test_save_prediction(self):
        """测试预测产物文件落盘"""
        tmp_dir = tempfile.mkdtemp()
        try:
            pred_res = predict_jingle(self.dummy_draws, self.rules)
            saved = save_jingle_prediction(pred_res, custom_dir=tmp_dir)
            self.assertTrue(len(saved) >= 1)
            self.assertTrue(os.path.exists(saved[0]))
            with open(saved[0], "r", encoding="utf-8") as f:
                txt = f.read()
            self.assertIn("顺口溜口诀预测报告", txt)
            self.assertIn(pred_res["target_issue"], txt)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
