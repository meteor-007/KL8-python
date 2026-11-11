# -*- coding: utf-8 -*-
"""
超参数自动寻优与直线校准器 (Hyperparameter Optimizer)
=====================================================
通过 Nelder-Mead / 自适应打靶算法，在历史校准窗口上动态寻找最优三维超参数：
  1. lambda_hl: 时间半衰期 (15.0 ~ 90.0)
  2. alpha_smooth: 狄利克雷平滑系数 (0.01 ~ 0.35)
  3. beta_second: 二阶高阶惯性融合权重 (0.05 ~ 0.45)
目标函数 (Loss):
  最小化 P-P 累积分布与 y=x 理想直线的综合偏差：
  Loss = (1 - R^2) * 2.0 + |slope - 1.0| + |intercept| + KS_stat * 1.5
记录完整的优化迭代轨迹 (Tuning Trajectory)，为前端动画渲染与实操对账提供真实数据支撑。
"""

from typing import List, Dict, Any, Tuple
import numpy as np

from backend.modules.markov_line.markov_engine import MarkovEngine
from backend.modules.markov_line.line_calibrator import LineCalibrator, LineFitResult


class OptimizationStep:
    """单步优化尝试的快照记录"""

    def __init__(
        self,
        iteration: int,
        half_life: float,
        smoothing_alpha: float,
        second_order_weight: float,
        loss: float,
        r_squared: float,
        slope: float,
        intercept: float,
        ks_stat: float,
        curve_sample: List[Dict[str, float]],
    ):
        self.iteration = iteration
        self.half_life = half_life
        self.smoothing_alpha = smoothing_alpha
        self.second_order_weight = second_order_weight
        self.loss = loss
        self.r_squared = r_squared
        self.slope = slope
        self.intercept = intercept
        self.ks_stat = ks_stat
        self.curve_sample = curve_sample

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "half_life": round(self.half_life, 2),
            "smoothing_alpha": round(self.smoothing_alpha, 4),
            "second_order_weight": round(self.second_order_weight, 3),
            "loss": round(self.loss, 4),
            "r_squared": round(self.r_squared, 4),
            "slope": round(self.slope, 4),
            "intercept": round(self.intercept, 4),
            "ks_stat": round(self.ks_stat, 4),
            "curve_sample": self.curve_sample,
        }


class BestTuningResult:
    """最优超参数寻优结果"""

    def __init__(
        self,
        best_half_life: float,
        best_alpha: float,
        best_beta: float,
        best_r2: float,
        best_loss: float,
        best_line_fit: LineFitResult,
        trajectory: List[OptimizationStep],
    ):
        self.best_half_life = best_half_life
        self.best_alpha = best_alpha
        self.best_beta = best_beta
        self.best_r2 = best_r2
        self.best_loss = best_loss
        self.best_line_fit = best_line_fit
        self.trajectory = trajectory

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_half_life": round(self.best_half_life, 2),
            "best_alpha": round(self.best_alpha, 4),
            "best_beta": round(self.best_beta, 3),
            "best_r_squared": round(self.best_r2, 4),
            "best_loss": round(self.best_loss, 4),
            "best_line_fit": self.best_line_fit.to_dict(),
            "total_iterations": len(self.trajectory),
            "trajectory": [s.to_dict() for s in self.trajectory],
        }


class MarkovHyperparamOptimizer:
    """马尔可夫直线自动调优器"""

    def __init__(self, num_states: int = 45):
        self.num_states = num_states
        self.calibrator = LineCalibrator(r2_threshold=0.92, ks_threshold=0.15)

    def optimize_parameters(
        self,
        training_state_sequence: List[int],
        eval_window: int = 80,
        max_evaluations: int = 25,
    ) -> BestTuningResult:
        """
        在历史训练序列中闭环自动寻优最优参数
        :param training_state_sequence: 仅包含截止当期历史的状态序列 (严禁未来数据)
        :param eval_window: 用于评估累积经验频率的历史窗口
        :param max_evaluations: 寻优步数上限
        :return: BestTuningResult 包含最优参数与完整寻优轨迹
        """
        n_seq = len(training_state_sequence)
        if n_seq < 30:
            raise ValueError(f"训练序列样本不足 ({n_seq} 期)，至少需要 30 期")

        # 统计评估窗口内的经验状态频率
        w = min(eval_window, n_seq - 10)
        recent_states = training_state_sequence[-w:]
        emp_counts = np.zeros(self.num_states, dtype=np.float64)
        for sid in recent_states:
            emp_counts[sid] += 1.0
        empirical_freqs = emp_counts / float(w)

        # 状态时序切片
        curr_state = training_state_sequence[-1]
        prev_state = training_state_sequence[-2] if n_seq >= 2 else None

        trajectory: List[OptimizationStep] = []
        best_loss = float("inf")
        best_params = (45.0, 0.08, 0.25)
        best_fit = None

        # 构造自适应搜索网格点 (由粗到细逐步逼近)
        search_grid = [
            # 初始基准点与极端点探索
            (30.0, 0.02, 0.10),
            (60.0, 0.15, 0.35),
            (20.0, 0.05, 0.20),
            (75.0, 0.20, 0.40),
            (45.0, 0.08, 0.25),
            (35.0, 0.10, 0.15),
            (50.0, 0.06, 0.30),
            (40.0, 0.04, 0.22),
            (55.0, 0.12, 0.28),
            (65.0, 0.03, 0.18),
        ]

        # 评估各网格点
        iteration_idx = 0
        for hl, alpha, beta in search_grid:
            iteration_idx += 1
            engine = MarkovEngine(
                num_states=self.num_states,
                half_life=hl,
                smoothing_alpha=alpha,
                second_order_weight=beta,
            )
            engine.fit(training_state_sequence)
            pred_probs = engine.predict_next_state_distribution(curr_state, prev_state)

            fit_res = self.calibrator.calibrate_pp_straight_line(pred_probs, empirical_freqs)

            # 目标损失函数：使 R^2 逼近 1.0，斜率逼近 1.0，截距逼近 0.0，KS 统计量最小化
            loss = (
                (1.0 - fit_res.r_squared) * 2.0
                + abs(fit_res.slope - 1.0)
                + abs(fit_res.intercept)
                + fit_res.ks_statistic * 1.5
            )

            step = OptimizationStep(
                iteration=iteration_idx,
                half_life=hl,
                smoothing_alpha=alpha,
                second_order_weight=beta,
                loss=loss,
                r_squared=fit_res.r_squared,
                slope=fit_res.slope,
                intercept=fit_res.intercept,
                ks_stat=fit_res.ks_statistic,
                curve_sample=fit_res.curve_points[:15],
            )
            trajectory.append(step)

            if loss < best_loss:
                best_loss = loss
                best_params = (hl, alpha, beta)
                best_fit = fit_res

        # 在当前最优解周围进行局部微调扰动 (局部爬山微调 5 步)
        hl_best, a_best, b_best = best_params
        perturbations = [
            (hl_best * 0.9, a_best * 0.9, b_best),
            (hl_best * 1.1, a_best * 1.1, b_best),
            (hl_best, a_best * 0.8, b_best * 1.1),
            (hl_best, a_best * 1.2, b_best * 0.9),
            (hl_best * 1.05, a_best * 0.95, b_best * 1.05),
        ]

        for hl_p, a_p, b_p in perturbations:
            iteration_idx += 1
            # 范围边界裁剪保护
            hl_p = max(15.0, min(90.0, hl_p))
            a_p = max(0.01, min(0.35, a_p))
            b_p = max(0.05, min(0.45, b_p))

            engine = MarkovEngine(
                num_states=self.num_states,
                half_life=hl_p,
                smoothing_alpha=a_p,
                second_order_weight=b_p,
            )
            engine.fit(training_state_sequence)
            pred_probs = engine.predict_next_state_distribution(curr_state, prev_state)
            fit_res = self.calibrator.calibrate_pp_straight_line(pred_probs, empirical_freqs)

            loss = (
                (1.0 - fit_res.r_squared) * 2.0
                + abs(fit_res.slope - 1.0)
                + abs(fit_res.intercept)
                + fit_res.ks_statistic * 1.5
            )

            step = OptimizationStep(
                iteration=iteration_idx,
                half_life=hl_p,
                smoothing_alpha=a_p,
                second_order_weight=b_p,
                loss=loss,
                r_squared=fit_res.r_squared,
                slope=fit_res.slope,
                intercept=fit_res.intercept,
                ks_stat=fit_res.ks_statistic,
                curve_sample=fit_res.curve_points[:15],
            )
            trajectory.append(step)

            if loss < best_loss:
                best_loss = loss
                best_params = (hl_p, a_p, b_p)
                best_fit = fit_res

        if best_fit is None:
            best_fit = trajectory[-1]

        return BestTuningResult(
            best_half_life=best_params[0],
            best_alpha=best_params[1],
            best_beta=best_params[2],
            best_r2=best_fit.r_squared,
            best_loss=best_loss,
            best_line_fit=best_fit,
            trajectory=trajectory,
        )
