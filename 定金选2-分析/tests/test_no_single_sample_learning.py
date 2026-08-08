# -*- coding: utf-8 -*-
import unittest
import sys, os
# 目录名含连字符「-」，Python import 语句无法直接导入，用路径加载
# 注意：autonomous_learner 内部 import learning.* / config.paths / data_loader，
# 子系统根目录必须也在 sys.path 上（仅加 learning/ 会 ModuleNotFoundError）
_LEARN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "learning")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LEARN_DIR not in sys.path:
    sys.path.insert(0, _LEARN_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import autonomous_learner as al


class TestBatchLearning(unittest.TestCase):
    def test_batch_update_requires_minimum(self):
        # 样本不足 50 时不得更新权重
        updated = al.batch_update([{"hit": True, "score": 0.8}] * 10, min_batch=50)
        self.assertFalse(updated)

    def test_batch_update_with_enough(self):
        # 50 条以上才允许更新（返回值应为 bool）
        results = [{"hit": (i % 2 == 0), "score": 0.5} for i in range(60)]
        out = al.batch_update(results, min_batch=50)
        self.assertIsInstance(out, bool)


if __name__ == "__main__":
    unittest.main()