# -*- coding: utf-8 -*-
import unittest
import random
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from 数据汇总复盘 import eval_stable_window as esw


class TestStableWindow(unittest.TestCase):
    def test_walk_forward_no_lookahead(self):
        random.seed(7)
        draws = []
        for i in range(300):
            nums = random.sample(range(1, 81), 20)
            draws.append(set(nums))
        # 对每个 t，用 draws[t-20:t] 选 stable 号，评估 draws[t] 命中
        res = esw.walk_forward_stable(draws, window=20, top_n=5)
        # 随机数据下 stable 命中率应≈随机 Top5 期望 1.25
        self.assertAlmostEqual(res["mean_hits_per_period"], 1.25, delta=0.8)

    def test_lookahead_detector(self):
        # 索引越界即视为前视
        self.assertTrue(esw.is_lookahead_free(100, 20, 300))
        self.assertFalse(esw.is_lookahead_free(300, 20, 300))  # 越界


if __name__ == "__main__":
    unittest.main()