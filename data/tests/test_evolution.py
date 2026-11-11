# -*- coding: utf-8 -*-
"""
test_evolution.py — 快乐8 统一主脑真自进化引擎单元与集成测试套件 (Evolution Test Suite)
========================================================================================
【测试覆盖范围】：
  1. Focal Loss 焦点残差损失核心计算 (数值防下溢、单调性、加权与梯度)；
  2. 空间高斯核宽 sigma 与时序衰减率 lambda 物理残差自适应与安全边界；
  3. 90 条口诀规则库实战赛马机制 (提升度 Lift 计算、黄金激活态晋升、冷宫静音淘汰)；
  4. UnifiedBrainEvolutionEngine 全流程反向校准、代数晋升与账本持久化；
  5. 自进化参数闭环传递至统一主脑并完成四级层级化决策验证。
"""
import os
import sys
import json
import math
import tempfile
import unittest
import numpy as np

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.core.unified_brain.feature_extractors import (
    NUM_TOTAL,
    FeatureEngineeringLayer,
    DiscreteRuleExtractor
)
from backend.core.unified_brain.loss_and_backprop import (
    calculate_focal_loss,
    compute_loss_gradients,
    calculate_spatial_dispersion,
    calculate_repeat_count,
    adapt_hyperparameters
)
from backend.core.unified_brain.evolution_engine import (
    RuleRaceTracker,
    UnifiedBrainEvolutionEngine,
    EVOLUTION_STORE_FILE,
    EVOLUTION_LEDGER_FILE
)
from backend.core.unified_brain.unified_brain import UnifiedDecisionBrain


class TestFocalLossComputation(unittest.TestCase):
    """1. Focal Loss 焦点残差损失数学与物理计算测试"""

    def setUp(self):
        self.actual_draw = [3, 8, 12, 19, 23, 27, 34, 38, 42, 45, 50, 53, 58, 62, 66, 70, 72, 75, 78, 80]
        self.uniform_probs = np.full(NUM_TOTAL, 1.0 / NUM_TOTAL, dtype=np.float64)

    def test_01_focal_loss_basic_positive(self):
        """测试基础均匀分布输入下的 Focal Loss 为正数且计算稳定"""
        loss = calculate_focal_loss(self.uniform_probs, self.actual_draw, gamma=2.0)
        self.assertIsInstance(loss, float)
        self.assertGreater(loss, 0.0, "Focal Loss 必须为严格正数")
        self.assertFalse(math.isnan(loss) or math.isinf(loss), "Focal Loss 严禁出现 NaN 或 Inf")

    def test_02_focal_loss_numerical_stability_extremes(self):
        """测试极限概率输入 (0.0 与 1.0) 下 epsilon 防除零保护"""
        extreme_probs = np.zeros(NUM_TOTAL, dtype=np.float64)
        for n in self.actual_draw[:10]:
            extreme_probs[n - 1] = 1.0  # 部分完全猜对，其余全为 0

        loss = calculate_focal_loss(extreme_probs, self.actual_draw, gamma=2.0, eps=1e-7)
        self.assertGreater(loss, 0.0)
        self.assertFalse(math.isnan(loss))
        self.assertFalse(math.isinf(loss))

    def test_03_focal_loss_monotonicity(self):
        """测试单调性：对真实开奖命中号码赋更高概率时，Focal Loss 必须严格下降"""
        bad_probs = np.full(NUM_TOTAL, 1.0 / NUM_TOTAL, dtype=np.float64)
        # 故意给未中奖号码高概率
        bad_probs[:20] = 0.04
        for n in self.actual_draw:
            bad_probs[n - 1] = 0.001
        bad_probs /= np.sum(bad_probs)

        good_probs = np.full(NUM_TOTAL, 0.001, dtype=np.float64)
        # 故意给真实开奖号码高概率
        for n in self.actual_draw:
            good_probs[n - 1] = 0.049
        good_probs /= np.sum(good_probs)

        loss_bad = calculate_focal_loss(bad_probs, self.actual_draw)
        loss_good = calculate_focal_loss(good_probs, self.actual_draw)

        self.assertLess(loss_good, loss_bad, "更精准的预测其 Focal Loss 必须显著小于较差的预测")

    def test_04_focal_loss_alpha_and_gamma_hyperparams(self):
        """测试不同 gamma 与 alpha 参数调节下的响应"""
        loss_g1 = calculate_focal_loss(self.uniform_probs, self.actual_draw, gamma=1.0)
        loss_g3 = calculate_focal_loss(self.uniform_probs, self.actual_draw, gamma=3.0)
        loss_alpha = calculate_focal_loss(self.uniform_probs, self.actual_draw, gamma=2.0, alpha=0.25)

        self.assertGreater(loss_g1, 0.0)
        self.assertGreater(loss_g3, 0.0)
        self.assertGreater(loss_alpha, 0.0)

    def test_05_gradient_computation_shape_and_signs(self):
        """测试解析梯度 dL/dP 形状与方向"""
        grads = compute_loss_gradients(self.uniform_probs, self.actual_draw, gamma=2.0)
        self.assertEqual(grads.shape, (NUM_TOTAL,))
        self.assertFalse(np.isnan(grads).any())

        # 对正样本 (y=1)，提升概率可降低损失，故导数为负 (指向正确方向)
        for n in self.actual_draw:
            self.assertLess(grads[n - 1], 0.0, f"正样本号码 {n} 处的梯度必须为负数")


class TestSpatialAndTemporalAdaptation(unittest.TestCase):
    """2. 空间核宽 sigma 与时序衰减 lambda 自适应物理规律测试"""

    def test_01_spatial_dispersion_calculation(self):
        """测试空间相邻跨度平均值计算"""
        # 高度扎堆号码 (1..20，平均跨度 1.0)
        clustered_draw = list(range(1, 21))
        disp_clustered = calculate_spatial_dispersion(clustered_draw)
        self.assertAlmostEqual(disp_clustered, 1.0, places=2)

        # 极端扩散号码 (4, 8, 12, ..., 80，平均跨度 4.0)
        uniform_draw = [4 * i for i in range(1, 21)]
        disp_uniform = calculate_spatial_dispersion(uniform_draw)
        self.assertAlmostEqual(disp_uniform, 4.0, places=2)

    def test_02_repeat_count_calculation(self):
        """测试跨期重号统计"""
        cur_nums = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        prev_nums = [1, 2, 3, 4, 5, 6, 7, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33]
        r = calculate_repeat_count(cur_nums, prev_nums)
        self.assertEqual(r, 7)

    def test_03_sigma_adaptation_tightens_on_cluster(self):
        """测试号码扎堆时 sigma 自适应收紧"""
        clustered_draw = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
        cur_params = {"sigma": 2.50, "lambda_decay": 0.95}
        new_params, rationales = adapt_hyperparameters(cur_params, clustered_draw)

        self.assertLess(new_params["sigma"], 2.50, "扎堆开奖时空间核宽必须自适应收紧")
        self.assertTrue(any("收紧" in r for r in rationales))

    def test_04_sigma_adaptation_broadens_on_dispersion(self):
        """测试号码全盘分散时 sigma 自适应展宽"""
        dispersed_draw = [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45, 49, 53, 57, 61, 65, 69, 73, 79]
        cur_params = {"sigma": 2.50, "lambda_decay": 0.95}
        new_params, rationales = adapt_hyperparameters(cur_params, dispersed_draw)

        self.assertGreater(new_params["sigma"], 2.50, "分散开奖时空间核宽必须自适应展宽")
        self.assertTrue(any("展宽" in r for r in rationales))

    def test_05_sigma_boundary_safety_clamping(self):
        """测试空间核宽在多次极端更新下不突破安全边界 [1.50, 3.50]"""
        clustered_draw = list(range(1, 21))
        p = {"sigma": 1.52, "lambda_decay": 0.95}
        for _ in range(5):
            p, _ = adapt_hyperparameters(p, clustered_draw, sigma_bounds=(1.50, 3.50))
        self.assertGreaterEqual(p["sigma"], 1.50, "核宽不得低于安全下限 1.50")

        dispersed_draw = [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45, 49, 53, 57, 61, 65, 69, 73, 79]
        p = {"sigma": 3.48, "lambda_decay": 0.95}
        for _ in range(5):
            p, _ = adapt_hyperparameters(p, dispersed_draw, sigma_bounds=(1.50, 3.50))
        self.assertLessEqual(p["sigma"], 3.50, "核宽不得超过安全上限 3.50")

    def test_06_lambda_adaptation_high_repeats(self):
        """测试重号爆发 (>= 6) 时时序衰减记忆增强"""
        cur_draw = list(range(1, 21))
        prev_draw = list(range(1, 10)) + list(range(25, 36))  # 9 个重号
        cur_params = {"sigma": 2.50, "lambda_decay": 0.93}
        new_params, rationales = adapt_hyperparameters(cur_params, cur_draw, prev_nums=prev_draw)

        self.assertGreater(new_params["lambda_decay"], 0.93, "重号爆发时时序半衰记忆率必须调高")
        self.assertTrue(any("调高" in r for r in rationales))

    def test_07_lambda_adaptation_low_repeats(self):
        """测试重号极少 (<= 3) 时时序衰减记忆降低"""
        cur_draw = list(range(1, 21))
        prev_draw = list(range(21, 41))  # 0 个重号
        cur_params = {"sigma": 2.50, "lambda_decay": 0.95}
        new_params, rationales = adapt_hyperparameters(cur_params, cur_draw, prev_nums=prev_draw)

        self.assertLess(new_params["lambda_decay"], 0.95, "跳空变盘时时序记忆率必须调低")
        self.assertTrue(any("调低" in r for r in rationales))

    def test_08_lambda_boundary_safety_clamping(self):
        """测试时序衰减率在安全边界 [0.85, 0.98] 之间平稳受控"""
        cur_draw = list(range(1, 21))
        prev_draw = list(range(21, 41))
        p = {"sigma": 2.50, "lambda_decay": 0.86}
        for _ in range(5):
            p, _ = adapt_hyperparameters(p, cur_draw, prev_nums=prev_draw, lambda_bounds=(0.85, 0.98))
        self.assertGreaterEqual(p["lambda_decay"], 0.85, "时序衰减率不得低于 0.85")


class TestRuleRaceMechanisms(unittest.TestCase):
    """3. 90 条口诀规则库动态赛马机制测试"""

    def setUp(self):
        self.tracker = RuleRaceTracker()

    def test_01_rule_race_tracker_loads_rules(self):
        """测试 90 条口诀规则库加载与合法性"""
        self.assertGreater(len(self.tracker.rules), 0, "必须成功加载口诀规则表")
        self.assertIn("1", self.tracker.rules)
        first_rule = self.tracker.rules["1"]
        self.assertIn("trigger", first_rule)
        self.assertIn("predict", first_rule)

    def test_02_rule_race_evaluates_on_history(self):
        """测试基于历史开奖评估口诀规则输出权重与统计结构"""
        brain = UnifiedDecisionBrain(PROJ_DIR)
        draws = brain.feature_layer.draws
        target_period = (draws[-1]["period"] + 1) if draws else 2026234

        weights, stats, logs = self.tracker.evaluate_rules(draws, target_period, window=30)
        self.assertIsInstance(weights, dict)
        self.assertIsInstance(stats, dict)
        self.assertIsInstance(logs, list)

        self.assertIn("total_rules", stats)
        self.assertIn("promoted_count", stats)
        self.assertIn("active_count", stats)
        self.assertIn("demoted_count", stats)
        self.assertIn("muted_count", stats)

        # 检查权重值域
        for rid, w in weights.items():
            self.assertTrue(0.0 <= w <= 2.0, f"规则 #{rid} 权重必须在 [0.0, 2.0] 区间")

    def test_03_discrete_extractor_accepts_dynamic_weights(self):
        """测试 DiscreteRuleExtractor 能够直接接收赛马动态权重并生成有效激活特征"""
        extractor = DiscreteRuleExtractor()
        brain = UnifiedDecisionBrain(PROJ_DIR)
        draws = brain.feature_layer.draws
        target_period = (draws[-1]["period"] + 1) if draws else 2026234

        # 构造自定义赛马权重
        custom_weights = {"1": 1.5, "2": 0.0, "3": 1.2}
        f_rule = extractor.extract(draws, target_period, rule_weights=custom_weights)

        self.assertEqual(f_rule.shape, (NUM_TOTAL,))
        self.assertTrue(np.all(f_rule >= 0.0) and np.all(f_rule <= 1.0))


class TestUnifiedBrainEvolutionEngineFullLoop(unittest.TestCase):
    """4. 统一主脑自进化引擎全流程反向校准与系统集成测试"""

    def setUp(self):
        self.engine = UnifiedBrainEvolutionEngine(PROJ_DIR)

    def test_01_nightly_calibration_contract_and_values(self):
        """测试夜间自进化反向校准标准契约与落盘"""
        draws = self.engine.brain.feature_layer.draws
        target_period = (draws[-1]["period"] + 1) if draws else 2026234

        res = self.engine.run_nightly_calibration(target_period=target_period, window=30)

        self.assertIsInstance(res, dict)
        self.assertIn("generation", res)
        self.assertIn("focal_loss", res)
        self.assertIn("sigma", res)
        self.assertIn("lambda_decay", res)
        self.assertIn("old_params", res)
        self.assertIn("new_params", res)
        self.assertIn("rule_stats", res)
        self.assertIn("rationales", res)
        self.assertIn("calibrated_at", res)

        # 检查参数合理性
        self.assertGreater(res["focal_loss"], 0.0)
        self.assertTrue(1.50 <= res["sigma"] <= 3.50)
        self.assertTrue(0.85 <= res["lambda_decay"] <= 0.98)
        self.assertGreater(len(res["rationales"]), 0)

        # 物理检查持久化参数文件与总账本
        self.assertTrue(os.path.exists(EVOLUTION_STORE_FILE))
        self.assertTrue(os.path.exists(EVOLUTION_LEDGER_FILE))

        with open(EVOLUTION_STORE_FILE, "r", encoding="utf-8") as f:
            params_on_disk = json.load(f)
        self.assertEqual(params_on_disk["generation"], res["generation"])
        self.assertEqual(params_on_disk["sigma"], res["sigma"])
        self.assertEqual(params_on_disk["lambda_decay"], res["lambda_decay"])

    def test_02_rolling_evolution_multi_generation(self):
        """测试多代滚动自进化压力测试"""
        results = self.engine.run_rolling_evolution(n_periods=3, window=20)
        self.assertEqual(len(results), 3, "滚动 3 期进化应返回 3 个演进记录")
        for rec in results:
            self.assertIn("focal_loss", rec)
            self.assertGreater(rec["generation"], 0)

    def test_03_evolved_parameters_feed_into_unified_brain(self):
        """测试自进化参数直接驱动统一主脑解算四级决策"""
        draws = self.engine.brain.feature_layer.draws
        target_period = (draws[-1]["period"] + 1) if draws else 2026234

        # 1. 运行自进化获得最新参数
        calib_res = self.engine.run_nightly_calibration(target_period=target_period)
        new_sigma = calib_res["sigma"]
        new_lambda = calib_res["lambda_decay"]
        rule_weights = self.engine.params.get("rule_weights")

        # 2. 使用自进化参数推演统一主脑
        decision = self.engine.brain.solve_period(
            target_period=target_period,
            sigma=new_sigma,
            lambda_decay=new_lambda,
            rule_weights=rule_weights
        )

        self.assertIn("gold_single", decision)
        self.assertIn("gold_pair", decision)
        self.assertIn("top5", decision)
        self.assertIn("top12_balanced", decision)
        self.assertEqual(len(decision["top5"]), 5)
        self.assertEqual(len(decision["top12_balanced"]), 12)
        self.assertEqual(len(decision["probabilities"]), NUM_TOTAL)


if __name__ == "__main__":
    unittest.main()
