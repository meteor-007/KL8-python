# kl8_stats/tests/test_baselines.py
# -*- coding: utf-8 -*-
import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl8_stats import baselines


class TestBaselines(unittest.TestCase):
    def test_hypergeom_expect(self):
        # 随机选 10 个号，开 20 个，期望命中 = 10*20/80 = 2.5
        self.assertAlmostEqual(baselines.hypergeom_expect(10), 2.5)
        self.assertAlmostEqual(baselines.hypergeom_expect(5), 1.25)
        self.assertAlmostEqual(baselines.hypergeom_expect(20), 5.0)

    def test_at_least_one(self):
        # 选 2 个号至少一中：1 - C(60,2)/C(80,2) = 1 - 1770/3160 ≈ 0.4399
        p = baselines.hit_rate_at_least_one(2)
        self.assertAlmostEqual(p, 1 - 1770 / 3160, places=4)
        # 选 1 个号 = 0.25
        self.assertAlmostEqual(baselines.hit_rate_at_least_one(1), 0.25)

    def test_random_topk_ci(self):
        mean, lo, hi = baselines.random_topk_hit_ci(10)
        self.assertAlmostEqual(mean, 2.5)
        self.assertTrue(lo < mean < hi)


if __name__ == "__main__":
    unittest.main()