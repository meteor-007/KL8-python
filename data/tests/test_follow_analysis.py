# -*- coding: utf-8 -*-
"""
跟随分析 (重复号追踪与多窗条件跟随) 单元测试套件
================================================
"""
import os
import sys
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

from core.follow_analysis import (
    load_draws_from_history,
    bayesian_smooth,
    calculate_history_repeat_avg,
    repeat_analysis,
    inference_top6,
    conditional_follow,
    daily_follow_picks,
    walk_forward_evaluate,
    evaluate_confidence,
    cross_validate_follow_picks,
    BASE_RATE,
    BASELINE_REPEAT_TOP5,
    BASELINE_INFERENCE_TOP6,
    BASELINE_FOLLOW_TOP8
)


class TestFollowAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history_file = os.path.join(PROJ_DIR, "kl8_history_final.txt")
        if not os.path.exists(cls.history_file):
            cls.history_file = os.path.join(PROJ_DIR, "storage", "raw", "kl8_history_final.txt")
        cls.draws = load_draws_from_history(cls.history_file)

    def test_01_load_history(self):
        """测试历史数据加载与格式完整性"""
        self.assertTrue(len(self.draws) >= 100, f"历史期数过少: {len(self.draws)}")
        latest = self.draws[-1]
        self.assertEqual(len(latest["nums"]), 20)
        self.assertEqual(len(latest["num_list"]), 20)
        self.assertIn("period", latest)
        self.assertIn("date", latest)
        print(f"[PASS] 01_load_history: Loaded {len(self.draws)} draws, Latest {latest['period']}")

    def test_02_bayesian_smooth(self):
        """测试贝叶斯平滑概率与基准"""
        self.assertAlmostEqual(bayesian_smooth(0, 0, base=0.25, alpha=2.0), 0.25)
        self.assertGreater(bayesian_smooth(10, 20, base=0.25, alpha=2.0), 0.25)
        self.assertLess(bayesian_smooth(1, 20, base=0.25, alpha=2.0), 0.25)
        print("[PASS] 02_bayesian_smooth: Bayesian smoothing verified")

    def test_03_repeat_analysis(self):
        """测试重复号分析 (Top 5 连庄追踪)"""
        rep = repeat_analysis(self.draws)
        self.assertEqual(len(rep["top5"]), 5)
        self.assertTrue(all(1 <= x <= 80 for x in rep["top5"]))
        self.assertTrue(rep["hist_avg_repeat"] > 3.0)
        self.assertIn("last_repeat", rep)
        self.assertEqual(len(rep["details"]), 20)
        # 验证 Top 5 来自上一期的开奖号码
        last_draw_set = self.draws[-1]["nums"]
        for num in rep["top5"]:
            self.assertIn(num, last_draw_set)
        print(f"[PASS] 03_repeat_analysis: Repeat Top5 {rep['top5']}, HistAvgRepeat {rep['hist_avg_repeat']}")

    def test_04_inference_top6(self):
        """测试综合推演 (Top 6 伙伴跟随并严格排除上期已开号码)"""
        inf = inference_top6(self.draws)
        self.assertEqual(len(inf["top6"]), 6)
        last_draw_set = self.draws[-1]["nums"]
        # 严格排除当期已开号码
        for num in inf["top6"]:
            self.assertNotIn(num, last_draw_set)
            self.assertTrue(1 <= num <= 80)
        print(f"[PASS] 04_inference_top6: Inference Top6 {inf['top6']} (All excluded last draw)")

    def test_05_conditional_follow(self):
        """测试条件跟随 (多窗交集与 RRF 软融合)"""
        cf = conditional_follow(self.draws)
        self.assertEqual(len(cf["top8"]), 8)
        self.assertEqual(len(cf["cond_info"]), 5)
        for ci in cf["cond_info"]:
            self.assertEqual(len(ci["pair"]), 2)
            self.assertTrue(ci["historical_occ"] > 0)
            self.assertEqual(len(ci["windows_detail"]), 4)
        print(f"[PASS] 05_conditional_follow: Top8 {cf['top8']}, 5 Conditions Verified")

    def test_06_daily_follow_picks(self):
        """测试跟随分析综合决策包与共振交集"""
        picks = daily_follow_picks(self.draws)
        self.assertIsNotNone(picks)
        self.assertEqual(picks["target_period"], self.draws[-1]["period"] + 1)
        self.assertEqual(len(picks["repeat"]["top5"]), 5)
        self.assertEqual(len(picks["inference"]["top6"]), 6)
        self.assertEqual(len(picks["conditional"]["top8"]), 8)
        self.assertIsInstance(picks["resonance_intersection"], list)
        print(f"[PASS] 06_daily_follow_picks: Target {picks['target_period']}, Resonance {picks['resonance_intersection']}")

    def test_07_walk_forward_evaluation(self):
        """测试 Walk-Forward 滚动无未来函数样本外评估与对账流水"""
        wf = walk_forward_evaluate(self.draws, n_periods=20)
        self.assertEqual(wf["n_count"], 20)
        self.assertEqual(len(wf["rows"]), 20)
        self.assertTrue(wf["rep_lift"] > 0.5)
        self.assertTrue(wf["inf_lift"] > 0.5)
        self.assertTrue(wf["cf_lift"] > 0.5)
        self.assertIn("confidence", wf)
        self.assertIn("badge", wf["confidence"])
        print(f"[PASS] 07_walk_forward_evaluation: 20-period RepLift {wf['rep_lift']}x, InfLift {wf['inf_lift']}x, CfLift {wf['cf_lift']}x")

    def test_08_cross_validation(self):
        """测试跨系统多维交叉风控与共振提纯"""
        picks = daily_follow_picks(self.draws)
        cross_res = cross_validate_follow_picks(PROJ_DIR, picks)
        self.assertIn("kill_conflicts", cross_res)
        self.assertIn("resonance_numbers", cross_res)
        self.assertIn("detailed_tags", cross_res)
        print(f"[PASS] 08_cross_validation: Conflicts {cross_res['kill_conflicts']}, Resonance {cross_res['resonance_numbers']}")


if __name__ == "__main__":
    unittest.main()
