# 顺口溜/tests/test_eval_ool.py
# -*- coding: utf-8 -*-
import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from 顺口溜 import eval_ool


class TestEvalOOL(unittest.TestCase):
    def test_correct_baseline_for_two_choice(self):
        # 二选一规则至少一中基线 = 1-(0.75)^2
        self.assertAlmostEqual(eval_ool.at_least_one_baseline(2), 1 - 0.75 ** 2)

    def test_parse_history(self):
        lines = [
            "date:2026-08-07,period:2026209,numbers:18-51-37-52-67-16-23-47-02-10-35-59-32-45-14-75-80-53-04-11",
            "date:2026-08-06,period:2026208,numbers:48-77-11-28-15-16-12-73-70-25-43-45-38-37-23-13-14-58-08-34",
        ]
        sets = eval_ool.parse_numbers(lines)
        self.assertEqual(len(sets), 2)
        self.assertEqual(len(sets[0]), 20)
        self.assertIn(18, sets[0])
        self.assertNotIn(1, sets[0])


if __name__ == "__main__":
    unittest.main()