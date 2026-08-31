# -*- coding: utf-8 -*-
"""
Tier 2: Boundary Value Analysis & Fault Tolerance (极端边界与容错自愈)
===================================================================
验证在空数据、超短历史、极端数值、文件锁竞争/残留、跨年期号跳跃等恶劣边界下，系统的自愈与防御能力。
"""
import os
import sys
import tempfile
import unittest
import numpy as np

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.utils.paths import data_path
from backend.utils.excel_lock import excel_lock, ExcelFileLock
from backend.utils.json_file_lock import json_file_lock
from core.spatial_points import (
    load_draws_from_file as load_spatial_draws,
    calculate_spatial_point_features,
    walk_forward_evaluate as spatial_walk_forward,
)
from core.gold_pick2 import (
    load_draws_from_file as load_gold_draws,
    calculate_gold_pick2_features,
    compute_confidence as compute_pick2_confidence,
    walk_forward_evaluate_pick2,
)
from core.follow_analysis import (
    load_draws_from_history as load_follow_draws,
    bayesian_smooth,
    repeat_analysis,
    inference_top6,
)
from core.formula_jingle.jingle_engine import (
    at_least_one_baseline,
    compute_target_issue,
)
from models.lstm import (
    load_history as load_lstm_history,
    build_dataset,
    next_period,
    parse_period,
)


class TestTier2HistoryBoundaries(unittest.TestCase):
    """历史开奖数据极值边界与容错测试"""

    def test_01_empty_history_graceful_handling(self):
        """验证输入空开奖历史时，各算法优雅处理或返回安全兜底，禁止未捕获异常崩溃"""
        empty_draws = []

        # 1. 空间点位算法在空输入下具备 epsilon 防护并返回 80 码默认结构
        feats = calculate_spatial_point_features(empty_draws)
        self.assertIsInstance(feats, dict)
        self.assertEqual(len(feats), 80)

        # 2. 定金选2 Walk-Forward 在空输入下安全返回错误提示字典而非崩溃
        wf_res = walk_forward_evaluate_pick2(empty_draws)
        self.assertIn("error", wf_res)
        self.assertEqual(len(wf_res["rows"]), 0)

        # 3. 缺失文件加载安全返回空列表
        fake_file = os.path.join(tempfile.gettempdir(), "non_existent_history_file.txt")
        res = load_spatial_draws(fake_file)
        self.assertEqual(res, [])

    def test_02_short_history_adaptation(self):
        """验证输入短历史场景下系统平稳回退与窗口自适应"""
        full_draws = load_spatial_draws(data_path("kl8_history_final.txt"))
        self.assertGreater(len(full_draws), 40)

        # 场景 A: 样本少于 30 期，Walk-Forward 触发安全门控
        short_draws = full_draws[-15:]
        wf_short = walk_forward_evaluate_pick2(short_draws, n_review=3)
        self.assertIn("error", wf_short)
        self.assertEqual(len(wf_short["rows"]), 0)

        # 场景 B: 样本充足 (35 期)，验证滚动样本外 3 期对账
        warm_draws = full_draws[-35:]
        wf_warm = walk_forward_evaluate_pick2(warm_draws, n_review=3)
        self.assertIn("stats", wf_warm)
        self.assertEqual(len(wf_warm["rows"]), 3)

    def test_03_malformed_history_lines_tolerance(self):
        """验证开奖数据文本中存在坏行、空行或乱码时，加载器能自动跳过坏行并提取合法行"""
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
            tmp.write("garbage header\n")
            tmp.write("date:2026-08-01,period:2026201,numbers:01-02-03-04-05-06-07-08-09-10-11-12-13-14-15-16-17-18-19-20\n")
            tmp.write("invalid line without colons\n")
            tmp.write("date:2026-08-02,period:2026202,numbers:01-02-03\n")  # 号码不足 20 个
            tmp.write("date:2026-08-03,period:2026203,numbers:02-03-04-05-06-07-08-09-10-11-12-13-14-15-16-17-18-19-20-21\n")
            tmp_path = tmp.name

        try:
            draws = load_follow_draws(tmp_path)
            self.assertEqual(len(draws), 2, "Should skip corrupted/incomplete lines and load exactly 2 valid draws")
            self.assertEqual(draws[0]["period"], 2026201)
            self.assertEqual(draws[1]["period"], 2026203)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestTier2NumericalStability(unittest.TestCase):
    """数值稳定性、除零保护与极值数学防御测试"""

    def test_01_bayesian_smoothing_extremes(self):
        """验证贝叶斯平滑在 0/0 与极端频次下不产生 ZeroDivisionError 或 NaN"""
        # 0 次开奖 0 次命中
        val_zero = bayesian_smooth(0, 0, base=0.25, alpha=2.0)
        self.assertEqual(val_zero, 0.25)
        self.assertFalse(np.isnan(val_zero))
        self.assertFalse(np.isinf(val_zero))

        # 0 次命中 1000 次开奖 (趋近但大于 0)
        val_cold = bayesian_smooth(0, 1000, base=0.25, alpha=2.0)
        self.assertGreater(val_cold, 0.0)
        self.assertLess(val_cold, 0.01)

        # 1000 次命中 1000 次开奖 (趋近但小于 1)
        val_hot = bayesian_smooth(1000, 1000, base=0.25, alpha=2.0)
        self.assertGreater(val_hot, 0.99)
        self.assertLessEqual(val_hot, 1.0)

    def test_02_hypergeometric_baseline_extremes(self):
        """验证超几何概率基线在边界和典型值下的精确计算与保护"""
        self.assertEqual(at_least_one_baseline(-5), 0.0)
        self.assertEqual(at_least_one_baseline(0), 0.0)
        self.assertAlmostEqual(at_least_one_baseline(1), 0.25, places=4)
        self.assertGreater(at_least_one_baseline(12), 0.95)
        self.assertGreater(at_least_one_baseline(20), 0.998)

    def test_03_confidence_grading_robustness(self):
        """验证置信度评定在 0 样本、极端胜率下的容错性"""
        c_zero = compute_pick2_confidence(0.0, 0)
        self.assertIn("level", c_zero)
        self.assertEqual(c_zero["level"], 3)

        c_extreme = compute_pick2_confidence(1.0, 100)
        self.assertEqual(c_extreme["level"], 1)


class TestTier2FileLockContention(unittest.TestCase):
    """文件锁竞争、生命周期管理与残留自愈测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.test_excel = os.path.join(self.tmp_dir, "test_data.xlsx")
        self.test_json = os.path.join(self.tmp_dir, "test_state.json")
        with open(self.test_excel, "w") as f:
            f.write("mock excel")
        with open(self.test_json, "w") as f:
            f.write("{}")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_excel_lock_lifecycle_and_cleanup(self):
        """验证 ExcelFileLock 上下文管理器获取与退出时 100% 清理锁文件"""
        lock_file = self.test_excel + ".excel_lock"
        self.assertFalse(os.path.exists(lock_file))

        with excel_lock(self.test_excel):
            self.assertTrue(os.path.exists(lock_file), "Lock file must exist during context")

        self.assertFalse(os.path.exists(lock_file), "Lock file must be removed after context exit")

    def test_02_excel_lock_reentrancy(self):
        """验证 Excel 锁支持同进程多层可重入，绝不死锁"""
        with excel_lock(self.test_excel):
            with excel_lock(self.test_excel):
                with excel_lock(self.test_excel):
                    pass
        lock_file = self.test_excel + ".excel_lock"
        self.assertFalse(os.path.exists(lock_file), "All reentrant locks must release cleanly")

    def test_03_json_file_lock_lifecycle_and_reentrancy(self):
        """验证 JSON 锁上下文管理器及可重入性"""
        lock_file = self.test_json + ".json_lock"
        self.assertFalse(os.path.exists(lock_file))

        with json_file_lock(self.test_json):
            self.assertTrue(os.path.exists(lock_file))
            with json_file_lock(self.test_json):
                pass
            self.assertTrue(os.path.exists(lock_file))

        self.assertFalse(os.path.exists(lock_file))

    def test_04_stale_lock_recovery(self):
        """验证存在过期残留锁文件时，锁机制能检测死亡 PID 并自动恢复获取"""
        lock_file = self.test_excel + ".excel_lock"
        # 写入一个不存在的死进程 PID 锁文件
        with open(lock_file, "w") as f:
            f.write("999999\nstale-uuid-12345\n1000000.0\n")

        with ExcelFileLock(self.test_excel, timeout=5.0, poll=0.1):
            self.assertTrue(os.path.exists(lock_file))

        self.assertFalse(os.path.exists(lock_file))


class TestTier2PeriodRollover(unittest.TestCase):
    """跨期、跨年与期号解析边界测试"""

    def test_01_target_issue_increment(self):
        """验证期号自增与字符串格式化"""
        self.assertEqual(compute_target_issue(2025350), "2025351")
        self.assertEqual(compute_target_issue("2026099"), "2026100")
        self.assertEqual(compute_target_issue("2026001"), "2026002")

    def test_02_lstm_period_rollover(self):
        """验证 LSTM 时序期号解析与递增"""
        y, n = parse_period("2026230")
        self.assertEqual(y, 2026)
        self.assertEqual(n, 230)

        nxt = next_period("2026230")
        self.assertEqual(nxt, "2026231")


if __name__ == "__main__":
    unittest.main()
