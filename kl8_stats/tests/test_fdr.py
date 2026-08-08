# kl8_stats/tests/test_fdr.py
# -*- coding: utf-8 -*-
import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl8_stats import fdr


class TestFDR(unittest.TestCase):
    def test_bh_known_example(self):
        # 经典示例：p=[0.01, 0.02, 0.03, 0.04]，q=0.05 全显著
        sig = fdr.bh_fdr([0.01, 0.02, 0.03, 0.04], q=0.05)
        self.assertEqual(sig, [True, True, True, True])

    def test_bh_filters_high(self):
        sig = fdr.bh_fdr([0.01, 0.20, 0.30, 0.40], q=0.05)
        self.assertEqual(sig, [True, False, False, False])

    def test_empty(self):
        self.assertEqual(fdr.bh_fdr([], q=0.05), [])


if __name__ == "__main__":
    unittest.main()