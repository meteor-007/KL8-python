# -*- coding: utf-8 -*-
"""快乐8 概率引擎测试（纯数学，可独立验算）

这些断言不依赖任何历史数据，也不需要跑流水线：
80 码开 20 码的超几何分布是确定的，算错了就是算错了。
"""
import os
import sys
import unittest
from math import comb

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils import kl8_probability as P  # noqa: E402


class TestDistribution(unittest.TestCase):
    def test_pmf_sums_to_one(self):
        for k in range(1, 81):
            self.assertAlmostEqual(sum(P.hit_distribution(k)), 1.0, places=12,
                                   msg=f"k={k} 的概率分布之和不为 1")

    def test_distribution_length(self):
        self.assertEqual(len(P.hit_distribution(5)), 6)
        self.assertEqual(len(P.hit_distribution(80)), 81)

    def test_expected_hits_is_quarter(self):
        for k in range(1, 81):
            self.assertAlmostEqual(P.expected_hits(k), k * 0.25, places=12)

    def test_expected_hits_matches_distribution(self):
        """期望值必须与分布自洽，防止两处口径漂移。"""
        for k in (1, 2, 5, 10, 20, 30, 50, 80):
            pmf = P.hit_distribution(k)
            ev = sum(j * p for j, p in enumerate(pmf))
            self.assertAlmostEqual(ev, P.expected_hits(k), places=10, msg=f"k={k}")


class TestAllMatch(unittest.TestCase):
    """选 N 全中概率 —— 与旧报告长期沿用的口径必须一致。"""

    def test_xuan1(self):
        self.assertAlmostEqual(P.all_match_prob(1), 0.25, places=12)

    def test_xuan2(self):
        self.assertAlmostEqual(P.all_match_prob(2), 0.060126582, places=8)

    def test_xuan3(self):
        self.assertAlmostEqual(P.all_match_prob(3), 0.013875, places=5)

    def test_matches_combination_formula(self):
        for k in (1, 2, 3, 5, 10, 20):
            self.assertAlmostEqual(
                P.all_match_prob(k), comb(20, k) / comb(80, k), places=12, msg=f"k={k}")

    def test_all_match_impossible_beyond_draw_size(self):
        """一期只开 20 个，选超过 20 个时「全中」在玩法上不可能，概率必须是 0。"""
        for k in (21, 30, 80):
            self.assertEqual(P.all_match_prob(k), 0.0, msg=f"k={k}")

    def test_pick_all_80_hits_exactly_20(self):
        """买满 80 码必中 20 个 —— 这是「命中数」而非「全中」。"""
        self.assertAlmostEqual(P.prob_exact(80, 20), 1.0, places=12)
        self.assertAlmostEqual(P.expected_hits(80), 20.0, places=12)


class TestTails(unittest.TestCase):
    def test_at_least_zero_is_one(self):
        for k in (1, 5, 30):
            self.assertAlmostEqual(P.prob_at_least(k, 0), 1.0, places=12)

    def test_at_least_beyond_max_is_zero(self):
        self.assertEqual(P.prob_at_least(5, 6), 0.0)
        self.assertEqual(P.prob_at_least(30, 21), 0.0)

    def test_at_least_monotone(self):
        prev = 2.0
        for j in range(0, 13):
            cur = P.prob_at_least(30, j)
            self.assertLessEqual(cur, prev, f"P(X>={j}) 应随 j 递减")
            prev = cur

    def test_thirty_ball_baseline(self):
        """30 码大底的 ≥11 码基线 5.60%，报告里长期引用这个数。"""
        self.assertAlmostEqual(P.prob_at_least(30, 11), 0.0560, places=3)

    def test_tail_complementary(self):
        """P(X>=j) + P(X<=j-1) 必须为 1。"""
        for k, j in ((5, 2), (30, 10), (20, 5)):
            self.assertAlmostEqual(
                P.prob_at_least(k, j) + P.prob_at_most(k, j - 1), 1.0, places=12)


class TestValidation(unittest.TestCase):
    def test_rejects_out_of_range(self):
        for bad in (0, -1, 81, 100):
            with self.assertRaises(ValueError):
                P.prob_exact(bad, 0)

    def test_rejects_non_integer(self):
        with self.assertRaises(TypeError):
            P.prob_exact(5.0, 0)
        with self.assertRaises(TypeError):
            P.prob_exact(True, 0)


class TestExpectedValue(unittest.TestCase):
    def test_all_miss_pays_nothing(self):
        ev = P.expected_value(5, cost=2.0, prize_by_hits={})
        self.assertEqual(ev["expected_payout"], 0.0)
        self.assertEqual(ev["expected_net"], -2.0)
        self.assertEqual(ev["expected_return_rate"], 0.0)

    def test_payout_and_net(self):
        # 假设命中 5 个赔 1000 元（示例奖金表，非真实玩法）
        ev = P.expected_value(5, cost=2.0, prize_by_hits={5: 1000.0})
        self.assertAlmostEqual(ev["expected_payout"], 1000.0 * P.all_match_prob(5), places=10)
        self.assertAlmostEqual(ev["expected_net"], ev["expected_payout"] - 2.0, places=10)
        self.assertAlmostEqual(ev["prob_any_prize"], P.all_match_prob(5), places=12)

    def test_ignores_out_of_range_hit_tier(self):
        ev = P.expected_value(3, cost=1.0, prize_by_hits={99: 1e9})
        self.assertEqual(ev["expected_payout"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)