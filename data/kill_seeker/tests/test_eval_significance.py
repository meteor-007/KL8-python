# -*- coding: utf-8 -*-
import unittest
import sys
import os

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_KILL_DIR = os.path.dirname(_CURR_DIR)
_PROJ_DIR = os.path.dirname(_KILL_DIR)

for _p in [_PROJ_DIR, _KILL_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from kill_seeker.core import eval_significance as es
except ImportError:
    from core import eval_significance as es


class TestKillSignificance(unittest.TestCase):
    def test_random_kill_expectation(self):
        # 随机杀 25 个号，开 20 个：正确杀号期望 = 25 * (60/80) = 18.75
        mean, lo, hi = es.monte_carlo_kill_baseline(25, n_sim=2000, seed=0)
        self.assertAlmostEqual(mean, 18.75, delta=0.3)

    def test_random_kill_rate(self):
        # 正确杀号率期望 = 60/80 = 0.75
        mean, _, _ = es.monte_carlo_kill_baseline(25, n_sim=2000, seed=0)
        self.assertAlmostEqual(mean / 25, 0.75, delta=0.05)

    def test_chance_level_is_zero_skill(self):
        # 75% 正确率 = 机会水平，不算提升
        self.assertTrue(es.is_above_baseline(0.75, 25, 200, alpha=0.05) is False)


if __name__ == "__main__":
    unittest.main()