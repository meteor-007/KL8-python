# -*- coding: utf-8 -*-
"""
Tier 1: Feature Coverage & Subsystem Contracts (功能契约与导包完整性)
===================================================================
验证重构后系统路径解析、后端所有核心模块导包无死角、以及各个核心算法子系统的输入输出契约。
"""
import os
import sys
import unittest
import importlib
import torch

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.utils.paths import (
    get_project_root,
    get_backend_dir,
    get_frontend_dir,
    get_storage_dir,
    get_config_dir,
    data_path,
    script_path,
)

from core.spatial_points import (
    load_draws_from_file as load_spatial_draws,
    calculate_spatial_point_features,
    rank_spatial_picks,
    walk_forward_evaluate as spatial_walk_forward,
)

from core.gold_pick2 import (
    load_draws_from_file as load_gold_draws,
    calculate_gold_pick2_features,
    compute_confidence as compute_pick2_confidence,
)

from core.follow_analysis import (
    load_draws_from_history as load_follow_draws,
    repeat_analysis,
    inference_top6,
    conditional_follow,
    daily_follow_picks,
)

from core.formula_jingle.jingle_engine import (
    load_jingle_rules,
    at_least_one_baseline,
    fired_rules,
)

from models.lstm import (
    DoubleLSTM,
    LSTMService,
    load_history as load_lstm_history,
)


class TestTier1PathsAndIntegrity(unittest.TestCase):
    """路径中枢与后端模块全量导入契约测试"""

    def test_01_paths_resolution_contract(self):
        """验证统一路径中枢解析契约"""
        root = get_project_root()
        self.assertTrue(os.path.isdir(root), f"Project root {root} is not a directory")
        self.assertEqual(os.path.normpath(root), os.path.normpath(PROJ_DIR))

        b_dir = get_backend_dir()
        self.assertTrue(os.path.isdir(b_dir), f"Backend dir {b_dir} is not a directory")

        f_dir = get_frontend_dir()
        self.assertTrue(os.path.isdir(f_dir), f"Frontend dir {f_dir} is not a directory")

        s_dir = get_storage_dir()
        self.assertTrue(os.path.isdir(s_dir), f"Storage dir {s_dir} is not a directory")

        cfg_dir = get_config_dir()
        self.assertTrue(os.path.isdir(cfg_dir), f"Config dir {cfg_dir} is not a directory")

        # 核心数据文件智能寻址契约
        history_path = data_path("kl8_history_final.txt")
        self.assertTrue(os.path.exists(history_path), f"History file {history_path} does not exist")

        # 脚本寻址契约
        sp_path = script_path("run_points_daily.py")
        self.assertTrue(os.path.exists(sp_path), f"Script {sp_path} not found")

    def test_02_backend_import_modules_integrity(self):
        """验证后端 10 大子系统核心模块 100% 正常导入"""
        modules_to_test = [
            'backend.api.api_server',
            'backend.api.data_service',
            'backend.audit.v3_trinity_audit',
            'backend.audit.matrix_detailed_audit',
            'backend.audit.collinearity_detector',
            'backend.audit.kl_divergence_checker',
            'backend.config.config_loader',
            'backend.core.energy_field',
            'backend.core.feature_optimizer',
            'backend.core.pure_pool_scorer',
            'backend.core.pair_selector',
            'backend.core.score_composer',
            'backend.core.algorithm_optimizer',
            'backend.core.spatial_points.points_engine',
            'backend.core.spatial_points.points_ranker',
            'backend.core.gold_pick2.gold_pick2_engine',
            'backend.core.follow_analysis.follow_engine',
            'backend.core.formula_jingle.jingle_engine',
            'backend.core.point_suppression.suppression_engine',
            'backend.core.aggregation.consensus_engine',
            'backend.data_acquisition.fetch_kl8_history',
            'backend.data_acquisition.process_hot_numbers',
            'backend.format.apply_formats',
            'backend.learning.autonomous_learner',
            'backend.learning.paper_trading',
            'backend.recognition.simplified_env_recognition',
            'backend.utils.paths',
            'backend.utils.data_validator',
            'backend.utils.excel_lock',
            'backend.utils.json_file_lock',
        ]
        for m in modules_to_test:
            mod = importlib.import_module(m)
            self.assertIsNotNone(mod, f"Failed to import canonical backend module: {m}")


class TestTier1SpatialPoints(unittest.TestCase):
    """空间重点点位分析 (Spatial Points) 算法契约测试"""

    @classmethod
    def setUpClass(cls):
        cls.history_file = data_path("kl8_history_final.txt")
        cls.draws = load_spatial_draws(cls.history_file)

    def test_01_spatial_point_features_contract(self):
        """验证 80 码 4 维空间特征计算契约"""
        self.assertGreater(len(self.draws), 100)
        pts_data = calculate_spatial_point_features(self.draws)
        self.assertIsInstance(pts_data, dict)
        self.assertEqual(len(pts_data), 80, "Must calculate features for all 80 numbers")
        for num in range(1, 81):
            self.assertIn(num, pts_data)
            feat = pts_data[num]
            self.assertIn("score", feat)
            self.assertIn("p_value", feat)
            self.assertIn("features", feat)
            self.assertIn("region", feat)
            sub_feats = feat["features"]
            self.assertIn("gap", sub_feats)
            self.assertIn("freq", sub_feats)
            self.assertIn("reg_heat", sub_feats)
            self.assertIn("neb_heat", sub_feats)
            self.assertGreaterEqual(feat["score"], 0.0)

    def test_02_spatial_ranking_contract(self):
        """验证空间点位 Core5 / Top10 / Ext15 分层精排契约"""
        pts_data = calculate_spatial_point_features(self.draws)
        picks = rank_spatial_picks(pts_data)
        self.assertIn("core5", picks)
        self.assertIn("ten", picks)
        self.assertIn("ext15", picks)
        self.assertEqual(len(picks["core5"]), 5)
        self.assertEqual(len(picks["ten"]), 10)
        self.assertEqual(len(picks["ext15"]), 15)
        self.assertTrue(set(picks["core5"]).issubset(set(picks["ten"])))
        self.assertTrue(set(picks["ten"]).issubset(set(picks["ext15"])))

    def test_03_spatial_walk_forward_contract(self):
        """验证空间点位 Walk-Forward 样本外评估契约"""
        wf = spatial_walk_forward(self.draws, n_periods=10)
        self.assertIn("confidence", wf)
        self.assertIn("oof_lift", wf)
        self.assertIn("rows", wf)
        self.assertEqual(len(wf["rows"]), 10)
        self.assertGreater(wf["oof_lift"], 0.0)


class TestTier1GoldPick2(unittest.TestCase):
    """定金选2决策推演 (Gold Pick2) 算法契约测试"""

    @classmethod
    def setUpClass(cls):
        cls.draws = load_gold_draws()

    def test_01_gold_pick2_features_contract(self):
        """验证定金选2核心金胆与 Top5 组合契约"""
        res = calculate_gold_pick2_features(self.draws)
        self.assertIn("golden", res)
        self.assertIn("hot", res)
        self.assertIn("top5_golden", res)
        self.assertIn("top5_hot", res)
        self.assertTrue(1 <= res["golden"] <= 80)
        self.assertTrue(1 <= res["hot"] <= 80)
        self.assertEqual(len(res["top5_golden"]), 5)
        self.assertEqual(len(res["top5_hot"]), 5)
        # Top 1 组合必须包含核心金胆
        top1_pair = res["top5_golden"][0]["pair"]
        self.assertIn(res["golden"], top1_pair)

    def test_02_gold_pick2_confidence_contract(self):
        """验证定金选2置信度分级契约"""
        c1 = compute_pick2_confidence(0.40, 30)
        self.assertEqual(c1["level"], 1)
        self.assertIn("Level 1", c1["badge"])

        c3 = compute_pick2_confidence(0.10, 30)
        self.assertEqual(c3["level"], 3)


class TestTier1FollowAnalysis(unittest.TestCase):
    """跟随分析 (Follow Analysis) 算法契约测试"""

    @classmethod
    def setUpClass(cls):
        cls.history_file = data_path("kl8_history_final.txt")
        cls.draws = load_follow_draws(cls.history_file)

    def test_01_repeat_analysis_contract(self):
        """验证连庄重复号 Top5 契约 (必须在上期开奖集合内)"""
        rep = repeat_analysis(self.draws)
        self.assertEqual(len(rep["top5"]), 5)
        self.assertTrue(rep["hist_avg_repeat"] > 3.0)
        last_nums = self.draws[-1]["nums"]
        for n in rep["top5"]:
            self.assertIn(n, last_nums)

    def test_02_inference_top6_contract(self):
        """验证综合推演 Top6 契约 (严格排除上期已开号码)"""
        inf = inference_top6(self.draws)
        self.assertEqual(len(inf["top6"]), 6)
        last_nums = self.draws[-1]["nums"]
        for n in inf["top6"]:
            self.assertNotIn(n, last_nums)
            self.assertTrue(1 <= n <= 80)

    def test_03_conditional_follow_and_daily_picks_contract(self):
        """验证条件跟随 Top8 与综合决策包契约"""
        cf = conditional_follow(self.draws)
        self.assertEqual(len(cf["top8"]), 8)
        self.assertEqual(len(cf["cond_info"]), 5)

        picks = daily_follow_picks(self.draws)
        self.assertIn("target_period", picks)
        self.assertEqual(picks["target_period"], self.draws[-1]["period"] + 1)
        self.assertEqual(len(picks["repeat"]["top5"]), 5)
        self.assertEqual(len(picks["inference"]["top6"]), 6)
        self.assertEqual(len(picks["conditional"]["top8"]), 8)


class TestTier1FormulaJingle(unittest.TestCase):
    """顺口溜口诀规则 (Formula Jingle) 算法契约测试"""

    def test_01_jingle_rules_loading_contract(self):
        """验证 90 条精英口诀规则加载契约"""
        rules, meta = load_jingle_rules()
        self.assertEqual(len(rules), 90)
        self.assertIn("val_end_period", meta)
        pair_rules = [r for r in rules if r["kind"] == "pair_pair"]
        triple_rules = [r for r in rules if r["kind"] == "triple_single"]
        self.assertEqual(len(pair_rules), 74)
        self.assertEqual(len(triple_rules), 16)

    def test_02_hypergeometric_baseline_contract(self):
        """验证超几何无放回精密基线计算契约"""
        self.assertEqual(at_least_one_baseline(0), 0.0)
        self.assertAlmostEqual(at_least_one_baseline(1), 0.25, places=4)
        self.assertAlmostEqual(at_least_one_baseline(2), 1 - 1770 / 3160, places=4)
        self.assertGreater(at_least_one_baseline(5), 0.70)
        self.assertGreater(at_least_one_baseline(12), 0.95)

    def test_03_fired_rules_contract(self):
        """验证口诀触发与带出预测契约"""
        rules, _ = load_jingle_rules()
        test_draw = [3, 33, 8, 50, 10, 20, 30, 40, 50, 60, 70, 80, 1, 2, 4, 5, 6, 7, 9, 11]
        fired = fired_rules(rules, test_draw)
        self.assertIsInstance(fired, list)
        self.assertGreater(len(fired), 0)
        for r, pred, w in fired:
            self.assertTrue(set(r["trigger"]).issubset(set(test_draw)))
            self.assertEqual(pred, r["predict"])
            self.assertGreater(w, 0.0)


class TestTier1LSTMService(unittest.TestCase):
    """双层 LSTM 时序建模子系统契约测试"""

    def test_01_lstm_service_precheck_contract(self):
        """验证 LSTMService.precheck 接口契约"""
        pc = LSTMService.precheck()
        self.assertIsInstance(pc, dict)
        self.assertIn("latest_period", pc)
        self.assertIn("target", pc)
        self.assertIn("total_draws", pc)
        self.assertGreater(pc["total_draws"], 100)

    def test_02_double_lstm_forward_contract(self):
        """验证 DoubleLSTM 模型前向多头推理与概率区间 [0, 1] 契约"""
        batch_size = 2
        seq_len = 10
        model = DoubleLSTM(n_in=80, hidden=16, layers=2, dropout=0.1)
        dummy_input = torch.randn(batch_size, seq_len, 80)
        ball, zone, tail = model(dummy_input)
        self.assertEqual(ball.shape, (batch_size, 80))
        self.assertEqual(zone.shape, (batch_size, 8))
        self.assertEqual(tail.shape, (batch_size, 10))
        self.assertTrue((ball >= 0).all() and (ball <= 1).all())
        self.assertTrue((zone >= 0).all() and (zone <= 1).all())
        self.assertTrue((tail >= 0).all() and (tail <= 1).all())


if __name__ == "__main__":
    unittest.main()
