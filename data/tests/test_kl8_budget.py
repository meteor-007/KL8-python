# -*- coding: utf-8 -*-
"""预算与方差引擎测试

奖金表用**虚构的测试表**，不是任何真实玩法规则 —— 本测试只验证算法，
不提供、也不校验真实奖金。真实表由使用者在 backend/config/kl8_payout.json 填写。
"""
import os
import sys
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils import kl8_budget as B  # noqa: E402
from backend.utils import kl8_probability as P  # noqa: E402


def _table():
    """虚构测试表：选5 单注 2 元，命中 5 个赔 1000，命中 4 个赔 20。"""
    return {
        "configured": True,
        "source": "TEST-ONLY",
        "plays": {
            "选5": {"stake": 2, "prizes": {"5": 1000, "4": 20}},
            "选2": {"stake": 2, "prizes": {"2": 8}},
        },
    }


class TestConfigGate(unittest.TestCase):
    def test_unconfigured_refuses_to_compute(self):
        """未配置奖金表时必须明确拒绝，而不是拿默认值瞎算。"""
        for t in ({"configured": False, "plays": {}},
                  {"configured": True, "plays": {}},
                  {"configured": True, "plays": {"选5": {"stake": 0, "prizes": {"5": 10}}}}):
            self.assertFalse(B.is_configured(t))
            r = B.play_metrics("选5", 1, t)
            self.assertEqual(r["status"], "not_configured")
            self.assertIn("未配置", r["message"])

    def test_missing_file_is_unconfigured(self):
        t = B.load_payout_table(os.path.join(PROJ_DIR, "no_such_payout.json"))
        self.assertFalse(B.is_configured(t))

    def test_shipped_config_is_unconfigured(self):
        """仓库自带的配置模板必须是未配置状态 —— 不能悄悄带着一组假数字。"""
        self.assertFalse(B.is_configured(B.load_payout_table()),
                         "仓库模板被填了数？那等于内置了来源不明的奖金表")


class TestPlayMetrics(unittest.TestCase):
    def setUp(self):
        self.t = _table()

    def test_expected_payout(self):
        m = B.play_metrics("选5", 1, self.t)
        expect = P.all_match_prob(5) * 1000 + P.prob_exact(5, 4) * 20
        self.assertAlmostEqual(m["expected_payout"], expect, places=10)

    def test_expected_net_and_rate(self):
        m = B.play_metrics("选5", 1, self.t)
        self.assertAlmostEqual(m["expected_net"], m["expected_payout"] - 2.0, places=10)
        self.assertAlmostEqual(m["return_rate"], m["expected_payout"] / 2.0, places=10)

    def test_prob_any_prize(self):
        m = B.play_metrics("选5", 1, self.t)
        expect = P.prob_exact(5, 5) + P.prob_exact(5, 4)
        self.assertAlmostEqual(m["prob_any_prize"], expect, places=12)

    def test_tickets_scale_linearly_and_std_by_sqrt(self):
        one = B.play_metrics("选5", 1, self.t)
        four = B.play_metrics("选5", 4, self.t)
        self.assertAlmostEqual(four["expected_payout"], one["expected_payout"] * 4, places=9)
        self.assertAlmostEqual(four["payout_std"], one["payout_std"] * 2, places=9)
        self.assertAlmostEqual(four["total_cost"], 8.0, places=12)

    def test_total_loss_probability(self):
        one = B.play_metrics("选5", 1, self.t)
        three = B.play_metrics("选5", 3, self.t)
        self.assertAlmostEqual(three["prob_total_loss"], (1 - one["prob_any_prize"]) ** 3, places=12)

    def test_std_is_non_negative(self):
        for play in ("选5", "选2"):
            self.assertGreaterEqual(B.play_metrics(play, 1, self.t)["payout_std"], 0.0)


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.t = _table()

    def test_unknown_play(self):
        self.assertEqual(B.play_metrics("选9", 1, self.t)["status"], "unknown_play")

    def test_play_size_parsing(self):
        self.assertEqual(B.play_size("选1"), 1)
        self.assertEqual(B.play_size("选10"), 10)
        with self.assertRaises(ValueError):
            B.play_size("大乐透")

    def test_rejects_impossible_play(self):
        t = {"configured": True, "plays": {"选25": {"stake": 2, "prizes": {"25": 10}}}}
        with self.assertRaises(ValueError):
            B.play_metrics("选25", 1, t)

    def test_rejects_negative_tickets(self):
        with self.assertRaises(ValueError):
            B.play_metrics("选5", 0, self.t)


class TestBudgetReport(unittest.TestCase):
    def test_aggregates(self):
        r = B.budget_report([("选5", 2), ("选2", 1)], _table())
        self.assertEqual(r["status"], "ok")
        self.assertAlmostEqual(r["total_cost"], 6.0, places=12)
        self.assertAlmostEqual(
            r["expected_payout"],
            sum(i["expected_payout"] for i in r["items"]), places=10)
        self.assertAlmostEqual(r["expected_net"], r["expected_payout"] - 6.0, places=10)

    def test_skips_unknown_play(self):
        r = B.budget_report([("选5", 1), ("选9", 1)], _table())
        self.assertEqual(len(r["items"]), 1)
        self.assertEqual(len(r["skipped"]), 1)

    def test_unconfigured_report(self):
        r = B.budget_report([("选5", 1)], {"configured": False, "plays": {}})
        self.assertEqual(r["status"], "not_configured")
        self.assertEqual(r["items"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)