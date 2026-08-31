# -*- coding: utf-8 -*-
import unittest
import unittest.mock
import sys, os

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from core import walk_forward_validator as wfv
except ImportError:
    from backend.core import walk_forward_validator as wfv


class TestIsFutureConsistency(unittest.TestCase):
    def test_validator_rejects_missing_is_future(self):
        # 没有显式 is_future 参数的接口应被拒绝
        with self.assertRaises(ValueError):
            wfv.assert_is_future_consistent(lambda hist, target: True, [])

    def test_validator_accepts_explicit(self):
        # 显式 is_future 参数通过
        wfv.assert_is_future_consistent(lambda hist, target, is_future: True, [])


class TestIsFutureThreading(unittest.TestCase):
    """接线级测试：history_only 强制 False，线上透传。"""

    def setUp(self):
        try:
            from core import feature_optimizer as fo
        except ImportError:
            from backend.core import feature_optimizer as fo
        self.fo = fo
        fo.clear_data_cache()

    def _patch_entry(self):
        captured = {}

        def fake_compute(hist, data1, data2, d1_stars, points, is_future=None):
            captured['is_future'] = is_future
            return {}

        return captured, fake_compute

    def test_history_only_forces_is_future_false(self):
        # history_only=True 必须强制 is_future=False（回测目标期未开奖）
        captured, fake_compute = self._patch_entry()
        self.fo._data_cache['data1'] = {}
        self.fo._data_cache['data2'] = {}
        self.fo._data_cache['d1_stars'] = {}
        self.fo._data_cache['history'] = [{'issue': '1'}]
        self.fo._data_cache['points'] = {}
        with unittest.mock.patch.object(self.fo, '_compute_layer_a_scores', fake_compute), \
                unittest.mock.patch.object(self.fo, '_filter_scoped_data',
                                           return_value=(None, None, None, None)):
            self.fo.get_all_layer_a_scores(history=[{'issue': '1'}], history_only=True,
                                           is_future=None)
        self.assertIs(captured['is_future'], False)

    def test_prod_path_passes_none_through(self):
        # 线上路径 (history_only=False, is_future=None) 透传 None → 生产推断
        captured, fake_compute = self._patch_entry()
        with unittest.mock.patch.object(self.fo, '_compute_layer_a_scores', fake_compute), \
                unittest.mock.patch.object(self.fo, 'load_all_data',
                                           return_value=({}, {}, {}, [{'issue': '1'}], {})):
            self.fo.get_all_layer_a_scores(history=[{'issue': '1'}], history_only=False,
                                           is_future=None)
        self.assertIsNone(captured['is_future'])


if __name__ == "__main__":
    unittest.main()