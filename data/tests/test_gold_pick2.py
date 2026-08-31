# -*- coding: utf-8 -*-
"""
定金选2 快乐8 综合单元测试与回归测试套件 (Test Suite)
"""
import os
import sys
import unittest
from fastapi.testclient import TestClient

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.gold_pick2 import (
    load_draws_from_file,
    calculate_gold_pick2_features,
    cross_validate_pick2_picks,
    walk_forward_evaluate_pick2,
    compute_confidence,
    GoldPick2Learner,
    batch_update,
    BASE_SINGLE,
    BASE_PAIR
)
from backend.api.api_server import app


class TestGoldPick2Engine(unittest.TestCase):
    """核心算法与特征计算测试"""

    @classmethod
    def setUpClass(cls):
        cls.draws = load_draws_from_file()

    def test_history_loading(self):
        self.assertTrue(len(self.draws) > 100, f"历史开奖期数应大于100，实际: {len(self.draws)}")
        latest = self.draws[-1]
        self.assertEqual(len(latest["nums"]), 20)
        self.assertTrue(latest["period"] > 2026000)

    def test_feature_calculation_and_picks(self):
        res = calculate_gold_pick2_features(self.draws)
        self.assertIn("golden", res)
        self.assertIn("hot", res)
        self.assertIn("top5_golden", res)
        self.assertIn("top5_hot", res)
        self.assertIn("warm", res)

        golden = res["golden"]
        hot = res["hot"]
        self.assertTrue(1 <= golden <= 80)
        self.assertTrue(1 <= hot <= 80)
        self.assertEqual(len(res["top5_golden"]), 5)
        self.assertEqual(len(res["top5_hot"]), 5)

        # 检查 Top1 组合包含金胆
        top1_pair = res["top5_golden"][0]["pair"]
        self.assertTrue(golden in top1_pair)

    def test_walk_forward_no_leakage(self):
        wf = walk_forward_evaluate_pick2(self.draws, n_review=15)
        self.assertIn("rows", wf)
        self.assertIn("stats", wf)
        self.assertEqual(len(wf["rows"]), 15)

        stats = wf["stats"]
        self.assertIn("golden_hit_rate", stats)
        self.assertIn("golden_lift", stats)
        self.assertIn("top1_both_rate", stats)
        self.assertIn("confidence", stats)

    def test_confidence_grading(self):
        # 高胜率
        c_high = compute_confidence(0.40, 30)
        self.assertEqual(c_high["level"], 1)
        self.assertIn("Level 1", c_high["badge"])

        # 中胜率
        c_mid = compute_confidence(0.26, 30)
        self.assertIn(c_mid["level"], [2, 3])

        # 极低胜率
        c_low = compute_confidence(0.10, 30)
        self.assertEqual(c_low["level"], 3)

    def test_cross_validation(self):
        flags = cross_validate_pick2_picks(PROJ_DIR, golden=10, hot=21, top5_pairs=[])
        self.assertIn("safety_audit", flags)
        self.assertIn("golden_killed_by_killseeker", flags)


class TestGoldPick2LearnerSafety(unittest.TestCase):
    """自学习约束与防过拟合熔断测试"""

    def test_batch_update_requires_minimum_50(self):
        # 样本不足 50 时禁止批量更新
        updated = batch_update([{"hit": True, "score": 0.8}] * 20, min_batch=50)
        self.assertFalse(updated)

    def test_batch_update_with_sufficient_samples(self):
        # 样本 >= 50 时允许安全调优
        results = [{"hit": (i % 3 == 0), "score": 0.6} for i in range(60)]
        out = batch_update(results, min_batch=50)
        self.assertTrue(out)

    def test_learner_step_limits(self):
        learner = GoldPick2Learner()
        # Level 3 下冻结参数
        res = learner.update_weights_from_review(level=3, failure_modes=["GOLDEN_MISS"])
        self.assertEqual(res["status"], "SKIPPED")


class TestGoldPick2API(unittest.TestCase):
    """Web API 接口集成测试"""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_api_summary(self):
        response = self.client.get("/api/gold-pick2/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("golden", data)
        self.assertIn("hot", data)
        self.assertIn("top5_golden", data)

    def test_api_review(self):
        response = self.client.get("/api/gold-pick2/review?n=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("rows", data)
        self.assertIn("stats", data)
        self.assertEqual(len(data["rows"]), 10)

    def test_api_matrix(self):
        response = self.client.get("/api/gold-pick2/matrix")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("features_80", data)
        self.assertIn("warm_pool", data)

    def test_api_logs(self):
        response = self.client.get("/api/gold-pick2/logs")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
