# data/tests/test_is_future_consistency.py
# -*- coding: utf-8 -*-
import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.core import walk_forward_validator as wfv


class TestIsFutureConsistency(unittest.TestCase):
    def test_validator_rejects_missing_is_future(self):
        # 没有显式 is_future 参数的接口应被拒绝
        with self.assertRaises(ValueError):
            wfv.assert_is_future_consistent(lambda hist, target: True, [])

    def test_validator_accepts_explicit(self):
        # 显式 is_future 参数通过
        wfv.assert_is_future_consistent(lambda hist, target, is_future: True, [])


if __name__ == "__main__":
    unittest.main()