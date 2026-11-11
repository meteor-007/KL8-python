# -*- coding: utf-8 -*-
"""
Loss 账本完整性回归测试（整改清单 D1/D2）

守护 2026-09-10 复检修掉的三个真缺陷：
  1. record_predictions 同期末重复追加（曾出现 30 条记录只覆盖 8 个期号）；
  2. 原始打分直接进交叉熵 → 被 np.clip 压成 1-1e-15 → 落盘 16~30 的假损失；
  3. 缺开奖号码时仍照算，产出与开奖无关的占位数值。
"""
import os
import sys
import json
import shutil
import tempfile
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import core.loss_weight_updater as L

# 均匀预测器 (每个号码 p=0.25) 的交叉熵理论基线
UNIFORM_BASELINE_LOSS = 0.5623

PRED_STUB = {
    'energy': {str(n): 1.0 for n in range(1, 81)},          # 原始打分 (>0, 未归一)
    'bayesian': {str(n): 0.25 for n in range(1, 81)},        # 近似概率
    'feature': {str(n): float(n) for n in range(1, 81)},     # 原始打分 (7/22/20 这类)
}


class TestLossLedgerIntegrity(unittest.TestCase):
    def setUp(self):
        fd, self.tmp = tempfile.mkstemp(suffix=".json", prefix="loss_ledger_")
        os.close(fd)
        json.dump({"records": []}, open(self.tmp, "w", encoding="utf-8"))
        self._orig_file = L.LOSS_HISTORY_FILE
        L.LOSS_HISTORY_FILE = self.tmp
        self.updater = L.LossBasedWeightUpdater()

    def tearDown(self):
        L.LOSS_HISTORY_FILE = self._orig_file
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def _load(self):
        return json.load(open(self.tmp, encoding="utf-8")).get("records", [])

    def test_01_record_predictions_is_idempotent_per_period(self):
        """同一期重复记录必须原地覆盖，不得重复追加。"""
        for _ in range(4):
            self.updater.record_predictions("2026241", PRED_STUB)
        recs = self._load()
        self.assertEqual(len(recs), 1, "同期重复记录被追加成了多行")
        self.assertEqual(recs[0]["period"], "2026241")

    def test_02_raw_scores_are_normalized_to_probabilities(self):
        """原始打分必须先归一化到 0.25 基线，避免 clip 出 16~30 的假损失。"""
        preds = {'feature': {str(n): float(n) for n in range(1, 81)}}
        probs = L.to_draw_probabilities(preds['feature'])
        self.assertTrue(probs)
        self.assertNotIn(0, probs)
        # ΣP 应锚定到 DRAW_BASELINE=20 → 均值 0.25，与交叉熵基线假设一致
        self.assertAlmostEqual(sum(probs.values()), L.DRAW_BASELINE, places=6)
        self.assertAlmostEqual(sum(probs.values()) / len(probs), 0.25, places=6)
        self.assertTrue(all(0 < p < 1 for p in probs.values()))

    def test_03_loss_magnitude_stays_near_baseline(self):
        """三种通道的损失都应落在均匀基线附近，而不是几十倍的 clip 伪影。"""
        self.updater.record_predictions("2026242", PRED_STUB)
        self.updater.update_with_actual("2026242", list(range(1, 21)))
        rec = self._load()[0]
        self.assertTrue(rec["losses"], "损失不应为空")
        for name, loss in rec["losses"].items():
            self.assertLess(loss, 5.0, f"{name} 损失 {loss} 仍异常偏大（clip 伪影）")
            self.assertGreater(loss, 0.0)
        # 均匀通道应精确落在理论基线上
        self.assertAlmostEqual(rec["losses"]["bayesian"], UNIFORM_BASELINE_LOSS, places=3)
        self.assertEqual(rec.get("loss_input_normalized"),
                         ["energy", "bayesian", "feature"])

    def test_04_empty_actual_is_skipped_not_scored(self):
        """缺开奖号码时必须跳过并留痕，不得产出占位数值。"""
        self.updater.record_predictions("2026243", PRED_STUB)
        self.assertEqual(self.updater.update_with_actual("2026243", []), {})
        rec = self._load()[0]
        self.assertEqual(rec["losses"], {})
        self.assertEqual(rec["weights"], {})
        self.assertEqual(rec.get("loss_skipped"), "empty_actual")
        self.assertEqual(rec.get("blocked_by"), "no_actual_numbers")

    def test_05_frozen_gate_keeps_weights_readonly_but_records_losses(self):
        """门控冻结时应落盘 Loss 但明确标记权重未改写。"""
        self.updater.record_predictions("2026244", PRED_STUB)
        self.updater.update_with_actual("2026244", list(range(1, 21)))
        rec = self._load()[0]
        if rec.get("blocked_by") == "learning_gate":
            self.assertEqual(rec["weights"], {})
            self.assertFalse(rec.get("weights_applied"))
            self.assertTrue(rec.get("weights_frozen"))
            self.assertTrue(rec["losses"], "冻结不等于不记损失")


if __name__ == "__main__":
    unittest.main(verbosity=2)
