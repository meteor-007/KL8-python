# kl8_stats/tests/test_ci.py
# -*- coding: utf-8 -*-
import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl8_stats import ci


class TestCI(unittest.TestCase):
    def test_wilson_centered(self):
        # 100 次中 50 次，CI 应包含 0.5
        lo, hi = ci.wilson_ci(50, 100)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)

    def test_wilson_zero_n(self):
        lo, hi = ci.wilson_ci(0, 0)
        self.assertEqual((lo, hi), (0.0, 0.0))

    def test_wilson_extreme(self):
        lo, hi = ci.wilson_ci(0, 10)
        self.assertEqual(lo, 0.0)


if __name__ == "__main__":
    unittest.main()