# -*- coding: utf-8 -*-
"""
心理博弈论与逆向均值回归量化引擎单元测试 (Unit Tests for Psychological Game Engine)
"""
from backend.utils.paths import get_outputs_dir, get_project_root
import os
import sys
import unittest

# 不要用 dirname(dirname(__file__)) 推项目根：本文件在 tests/legacy/ 下，
# 推两次得到的是 tests/ 而不是项目根，产物断言会永远指向不存在的路径。
_PROJ_DIR = get_project_root()
if _PROJ_DIR not in sys.path:
    sys.path.insert(0, _PROJ_DIR)

from backend.core.psychological_game_engine import PsychologicalGameEngine, run_psychological_game_pipeline


class TestPsychologicalGameEngine(unittest.TestCase):
    """心理博弈引擎单元测试用例"""

    def setUp(self):
        self.engine = PsychologicalGameEngine()

    def test_engine_initialization(self):
        """测试引擎初始化与历史开奖加载"""
        self.assertGreater(self.engine.total_periods, 1000, "历史开奖期数应大于1000期")

    def test_macro_pendulum_analysis(self):
        """测试大小比钟摆与四分区拥挤度分析"""
        macro = self.engine.analyze_macro_pendulum(lookback=5)
        self.assertIn("last_size_ratio", macro)
        self.assertIn("zone_shares", macro)
        self.assertEqual(len(macro["zone_shares"]), 4)
        self.assertIn("target_size_bias", macro)

    def test_contrarian_cold_spring(self):
        """测试逆向弹性冷号突击与极热扣分"""
        cold_res = self.engine.analyze_contrarian_cold_spring(lookback=30)
        self.assertIn("spring_cold_candidates", cold_res)
        self.assertIn("deep_dead_cold", cold_res)
        self.assertIn("crowd_hot_penalties", cold_res)

    def test_healthy_repeats_and_clusters(self):
        """测试单点健康重号与连号截断过滤"""
        repeat_res = self.engine.analyze_healthy_repeats_and_clusters()
        self.assertIn("healthy_repeats", repeat_res)
        self.assertIn("truncated_repeats", repeat_res)
        self.assertIn("cluster_bias_desc", repeat_res)

    def test_compute_full_prediction(self):
        """测试全局 80 球博弈预测与契约完整性"""
        res = self.engine.compute_full_prediction()
        self.assertEqual(len(res["top3_gold"]), 3, "主口径最优 3 码")
        self.assertEqual(len(res["top5_assault"]), 3, "top5_assault 为 top3 兼容别名")
        self.assertEqual(len(res["top12_balanced"]), 3, "top12_balanced 为 top3 兼容别名")
        self.assertEqual(res["top5_assault"], res["top3_gold"])
        self.assertEqual(res["top12_balanced"], res["top3_gold"])
        self.assertGreater(len(res["top_cold_spring"]), 0, "弹性冷号推荐不为空")
        self.assertGreater(len(res["top_healthy_repeats"]), 0, "健康重号推荐不为空")

    def test_pipeline_execution_and_artifacts(self):
        """测试一键流水线执行与物理资产落盘"""
        res = run_psychological_game_pipeline()
        self.assertIsNotNone(res)
        
        json_path = os.path.join(_PROJ_DIR, "storage", "stats", "psychological_game_analysis.json")
        self.assertTrue(os.path.exists(json_path), "JSON账本文件应存在")
        
        report_path = os.path.join(get_outputs_dir(), "reports", "psychological_game_report_latest.md")
        self.assertTrue(os.path.exists(report_path), "研报文件应存在")


if __name__ == "__main__":
    unittest.main()
