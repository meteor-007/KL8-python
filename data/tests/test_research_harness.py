# -*- coding: utf-8 -*-
"""预注册研究框架测试

这个框架的全部意义是「防止事后挑指标、挑样本、挑结论」，所以测试也围绕这一点：
先立规矩、再收数据、到期按规矩判，中途改不了、也提前判不了成功。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils import research_harness as R  # noqa: E402


def _spec(**over):
    base = {
        "exp_id": "exp_test",
        "title": "测试实验",
        "hypothesis": "某模块 top3 命中率 > 25%",
        "primary_metric": "top3_hit_rate",
        "target_periods": 10,
        "kill_rule": {"type": "rate_below_baseline"},
        "start_period": "2026303",
    }
    base.update(over)
    return base


class HarnessCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rh_")
        self._p0, self._l0 = R.PREREG_DIR, R.LEDGER_DIR
        R.PREREG_DIR = os.path.join(self.tmp, "prereg")
        R.LEDGER_DIR = os.path.join(self.tmp, "ledger")

    def tearDown(self):
        R.PREREG_DIR, R.LEDGER_DIR = self._p0, self._l0
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fill(self, exp_id, n, hits_per_period, picks_n=3):
        """灌入 n 期观察，每期推荐 picks_n 个号、命中 hits_per_period 个。"""
        for i in range(n):
            picks = list(range(1, 1 + picks_n))       # [1, 2, 3]
            hits = min(hits_per_period, picks_n)
            # 命中的号取 picks 里的前 hits 个，其余用 41+ 的不重合号补足 20 个
            actual = list(range(1, 1 + hits)) + list(range(41, 41 + (20 - hits)))
            R.append_observation(exp_id, str(2026303 + i), picks, actual)


class TestPreregistration(HarnessCase):
    def test_requires_fields(self):
        for field in ("title", "hypothesis", "primary_metric", "target_periods", "kill_rule"):
            spec = _spec()
            spec.pop(field)
            with self.assertRaises(ValueError, msg=f"缺少 {field} 时应报错"):
                R.create_experiment(spec)

    def test_freeze_prevents_redefinition(self):
        R.create_experiment(_spec())
        with self.assertRaises(R.ExperimentFrozenError):
            R.create_experiment(_spec(title="偷偷改个标题"))

    def test_tampering_detected(self):
        R.create_experiment(_spec())
        path = os.path.join(R.PREREG_DIR, "exp_test.json")
        data = json.load(open(path, encoding="utf-8"))
        data["target_periods"] = 3                 # 事后把样本量改小
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)

        with self.assertRaises(R.ExperimentFrozenError):
            R.load_experiment("exp_test")
        self.assertFalse(R.verify("exp_test"))

    def test_rejects_unsafe_id(self):
        with self.assertRaises(ValueError):
            R.create_experiment(_spec(exp_id="../escape"))


class TestLedger(HarnessCase):
    def setUp(self):
        super().setUp()
        R.create_experiment(_spec())

    def test_hits_computed(self):
        row = R.append_observation("exp_test", "2026303", [1, 2, 3], [2, 3, 9, 10])
        self.assertEqual(row["hits"], 2)
        self.assertEqual(row["picks_n"], 3)

    def test_no_overwrite_same_period(self):
        R.append_observation("exp_test", "2026303", [1, 2, 3], [1])
        with self.assertRaises(ValueError):
            R.append_observation("exp_test", "2026303", [4, 5, 6], [4])

    def test_ledger_is_append_only(self):
        R.append_observation("exp_test", "2026303", [1, 2, 3], [1])
        R.append_observation("exp_test", "2026304", [1, 2, 3], [2])
        rows = R.read_observations("exp_test")
        self.assertEqual([r["period"] for r in rows], ["2026303", "2026304"])


class TestVerdict(HarnessCase):
    def test_collecting_before_target(self):
        R.create_experiment(_spec(target_periods=10))
        self._fill("exp_test", 3, hits_per_period=3)     # 命中率 100%
        r = R.evaluate("exp_test")
        self.assertEqual(r["verdict"], R.VERDICT_COLLECTING)
        self.assertEqual(r["n_periods"], 3)

    def test_never_confirms_early_even_at_100_percent(self):
        """核心约束：没到目标样本量，绝不判成功 —— 哪怕现在是 100%。"""
        R.create_experiment(_spec(target_periods=100))
        self._fill("exp_test", 30, hits_per_period=3)
        self.assertEqual(R.evaluate("exp_test")["verdict"], R.VERDICT_COLLECTING)

    def test_confirmed_at_target(self):
        R.create_experiment(_spec(target_periods=40, checkpoints=[]))
        self._fill("exp_test", 40, hits_per_period=2)    # 2/3 = 66.7%，远高于 25%
        r = R.evaluate("exp_test")
        self.assertEqual(r["verdict"], R.VERDICT_CONFIRMED)
        self.assertLessEqual(r["p_value"], 0.05)

    def test_inconclusive_at_target(self):
        """命中率贴着基线时，即使收满目标期数也判不出显著性。"""
        R.create_experiment(_spec(target_periods=40, checkpoints=[]))
        # 每期推 20 码、命中 5 个 → 200/800 = 25.0%，正好等于基线
        self._fill("exp_test", 40, hits_per_period=5, picks_n=20)
        r = R.evaluate("exp_test")
        self.assertEqual(r["verdict"], R.VERDICT_INCONCLUSIVE)
        self.assertAlmostEqual(r["observed_rate"], 0.25, places=4)
        self.assertGreater(r["p_value"], 0.05)

    def test_kill_at_checkpoint(self):
        R.create_experiment(_spec(target_periods=100, checkpoints=[10]))
        self._fill("exp_test", 10, hits_per_period=0)    # 命中率 0% < 25%
        r = R.evaluate("exp_test")
        self.assertEqual(r["verdict"], R.VERDICT_REJECTED)

    def test_no_kill_outside_checkpoints(self):
        R.create_experiment(_spec(target_periods=100, checkpoints=[10]))
        self._fill("exp_test", 20, hits_per_period=0)
        self.assertEqual(R.evaluate("exp_test")["verdict"], R.VERDICT_COLLECTING)

    def test_list_experiments(self):
        R.create_experiment(_spec())
        rows = R.list_experiments()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["exp_id"], "exp_test")


class TestSyncFromForwardLedger(HarnessCase):
    def setUp(self):
        super().setUp()
        self.fwd = os.path.join(self.tmp, "paper_trading_modules.jsonl")

    def _write_fwd(self, rows):
        with open(self.fwd, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def _row(self, period, module="sixteen_hot", hits=1, actual=True):
        return {
            "period": str(period), "module": module,
            "picks": [1, 2, 3],
            "actual": ([1, 41, 42] if hits else [41, 42, 43]) if actual else None,
            "hits": hits,
        }

    def test_respects_start_period(self):
        """start_period 之前的样本已被用于调参，绝不能再算进测试集。"""
        R.create_experiment(_spec(start_period="2026310", target_periods=100))
        self._write_fwd([self._row(p) for p in range(2026300, 2026312)])
        res = R.sync_from_forward_ledger("exp_test", "sixteen_hot", self.fwd)
        self.assertEqual(res["added"], 2)                 # 2026310, 2026311
        self.assertEqual(res["skipped_before_start"], 10)

    def test_skips_unsettled_rows(self):
        R.create_experiment(_spec(start_period="2026303", target_periods=100))
        self._write_fwd([self._row(2026303, actual=True), self._row(2026304, actual=False)])
        res = R.sync_from_forward_ledger("exp_test", "sixteen_hot", self.fwd)
        self.assertEqual(res["added"], 1)
        self.assertEqual([r["period"] for r in R.read_observations("exp_test")], ["2026303"])

    def test_ignores_other_modules(self):
        R.create_experiment(_spec(start_period="2026303", target_periods=100))
        self._write_fwd([self._row(2026303, module="other_mod"), self._row(2026304)])
        res = R.sync_from_forward_ledger("exp_test", "sixteen_hot", self.fwd)
        self.assertEqual(res["added"], 1)

    def test_idempotent(self):
        R.create_experiment(_spec(start_period="2026303", target_periods=100))
        self._write_fwd([self._row(2026303), self._row(2026304)])
        R.sync_from_forward_ledger("exp_test", "sixteen_hot", self.fwd)
        second = R.sync_from_forward_ledger("exp_test", "sixteen_hot", self.fwd)
        self.assertEqual(second["added"], 0)
        self.assertEqual(len(R.read_observations("exp_test")), 2)

    def test_sync_all_uses_module_id(self):
        R.create_experiment(_spec(start_period="2026303", target_periods=100,
                                  module_id="sixteen_hot"))
        self._write_fwd([self._row(2026303)])
        rows = R.sync_all_from_forward_ledger(self.fwd)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["added"], 1)

    def test_sync_all_skips_experiments_without_module_id(self):
        R.create_experiment(_spec(start_period="2026303", target_periods=100))
        self._write_fwd([self._row(2026303)])
        self.assertEqual(R.sync_all_from_forward_ledger(self.fwd), [])


class TestStatsHelpers(HarnessCase):
    def test_upper_tail_bounds(self):
        self.assertAlmostEqual(R._binom_upper_tail(0, 10, 0.25), 1.0, places=12)
        self.assertAlmostEqual(R._binom_upper_tail(11, 10, 0.25), 0.0, places=12)
        self.assertAlmostEqual(R._binom_upper_tail(10, 10, 0.25), 0.25 ** 10, places=12)

    def test_kill_rule_variants(self):
        self.assertTrue(R._kill_triggered({"type": "rate_below_baseline"}, 0.24, 0.25))
        self.assertFalse(R._kill_triggered({"type": "rate_below_baseline"}, 0.26, 0.25))
        self.assertTrue(R._kill_triggered({"type": "rate_below", "value": 0.3}, 0.29, 0.25))
        self.assertFalse(R._kill_triggered({"type": "unknown"}, 0.1, 0.25))


if __name__ == "__main__":
    unittest.main(verbosity=2)