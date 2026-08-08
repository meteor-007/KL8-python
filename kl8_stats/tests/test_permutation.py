# kl8_stats/tests/test_permutation.py
# -*- coding: utf-8 -*-
import unittest
import random
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl8_stats import permutation


class TestPermutation(unittest.TestCase):
    def test_permutation_of_noise_is_not_significant(self):
        # 用随机预测函数（无信号），置换检验 p 值应 > 0.05
        random.seed(42)
        draws = []
        for _ in range(200):
            numbers = random.sample(range(1, 81), 20)
            draws.append(f"date:2026-01-01,period:2026001,numbers:" + "-".join(f"{n:02d}" for n in numbers))
        # 修正期号：walk-forward 需要真实期号递增
        draws = []
        for i in range(200):
            numbers = random.sample(range(1, 81), 20)
            draws.append(f"date:2026-01-01,period:{2026000 + i + 1:07d},numbers:" + "-".join(f"{n:02d}" for n in numbers))

        def random_predict(history):
            return random.sample(range(1, 81), 10)

        res = permutation.evaluate_lifts(random_predict, draws, history_len=30, n_perm=50, seed=1)
        # 随机预测的 lift 应接近 1.0，p 值不显著
        self.assertGreater(res["p_value"], 0.05)
        self.assertAlmostEqual(res["lift"], 1.0, delta=0.3)

    def test_permutation_detects_null(self):
        # 空指针：pred_fn 返回固定集合，也应在置换下不显著
        draws = []
        for i in range(200):
            numbers = random.sample(range(1, 81), 20)
            draws.append(f"date:2026-01-01,period:{2026000 + i + 1:07d},numbers:" + "-".join(f"{n:02d}" for n in numbers))

        def fixed_predict(history):
            return list(range(1, 11))

        res = permutation.evaluate_lifts(fixed_predict, draws, history_len=30, n_perm=50, seed=2)
        self.assertGreater(res["p_value"], 0.05)


if __name__ == "__main__":
    unittest.main()