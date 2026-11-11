# -*- coding: utf-8 -*-
"""
分布图直线校准与偏离拐点捕捉器 (Line Calibrator)
================================================
本模块实现两大核心直线算法：
  1. P-P 累积分布直线拟合检验 (Probability-Probability Line Fit):
     检验马尔可夫模型预测分布与经验累积分布是否严格贴合 45 度理想直线 (y = x)。
     输出决定系数 R^2、斜率、截距与 KS 统计量。
  2. 累积残差均值回归直线分析 (Cumulative Residual Rebound Detection):
     以理论期望水平直线 (y = 0) 为基准，追踪各号码及宏观状态的历史累积残差轨迹。
     精准捕捉严重下探凹陷、处于均值回归拐点 (反弹拉回直线) 的高置信度出号信号。
"""

from typing import List, Dict, Any, Tuple
import numpy as np


class LineFitResult:
    """直线拟合校验结果"""

    def __init__(
        self,
        slope: float,
        intercept: float,
        r_squared: float,
        ks_statistic: float,
        is_straight: bool,
        curve_points: List[Dict[str, float]],
    ):
        self.slope = slope
        self.intercept = intercept
        self.r_squared = r_squared
        self.ks_statistic = ks_statistic
        self.is_straight = is_straight
        self.curve_points = curve_points

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slope": round(self.slope, 4),
            "intercept": round(self.intercept, 4),
            "r_squared": round(self.r_squared, 4),
            "ks_statistic": round(self.ks_statistic, 4),
            "is_straight": self.is_straight,
            "curve_points_sample": self.curve_points[:10],
            "total_points": len(self.curve_points),
        }


class ResidualReboundSignal:
    """残差偏离与拐点反弹信号"""

    def __init__(
        self,
        target_id: int,
        target_type: str,  # 'ball' 或 'state'
        current_cumulative_residual: float,
        z_score: float,
        is_rebounding: bool,
        rebound_strength: float,
    ):
        self.target_id = target_id
        self.target_type = target_type
        self.current_cumulative_residual = current_cumulative_residual
        self.z_score = z_score
        self.is_rebounding = is_rebounding
        self.rebound_strength = rebound_strength

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "current_residual": round(self.current_cumulative_residual, 3),
            "z_score": round(self.z_score, 3),
            "is_rebounding": self.is_rebounding,
            "rebound_strength": round(self.rebound_strength, 4),
        }


class LineCalibrator:
    """直线校准与偏离反弹分析器"""

    def __init__(self, r2_threshold: float = 0.92, ks_threshold: float = 0.15):
        """
        :param r2_threshold: 直线拟合判定门槛 (R^2 >= 0.92 视为合格直线)
        :param ks_threshold: KS 统计量上限 (KS <= 0.15 视为贴合良好)
        """
        self.r2_threshold = r2_threshold
        self.ks_threshold = ks_threshold

    def calibrate_pp_straight_line(
        self,
        predicted_probs: np.ndarray,
        empirical_frequencies: np.ndarray,
    ) -> LineFitResult:
        """
        1. P-P 累积分布直线拟合检验
        将理论预测累积分布 (CDF_pred) 作为 X 轴，实际发生经验累积频率 (CDF_emp) 作为 Y 轴。
        无偏理想状态应为 y = x (斜率 1.0, 截距 0.0, R^2 = 1.0)。
        """
        # 排序以形成单调递增的累积分布
        sort_idx = np.argsort(predicted_probs)
        sorted_p = predicted_probs[sort_idx]
        sorted_emp = empirical_frequencies[sort_idx]

        # 累积分布归一化
        sum_p = np.sum(sorted_p)
        sum_emp = np.sum(sorted_emp)
        cdf_x = np.cumsum(sorted_p) / (sum_p if sum_p > 0 else 1.0)
        cdf_y = np.cumsum(sorted_emp) / (sum_emp if sum_emp > 0 else 1.0)

        # 最小二乘线性拟合: y = slope * x + intercept
        n_points = len(cdf_x)
        if n_points < 2:
            return LineFitResult(1.0, 0.0, 1.0, 0.0, True, [])

        x_mean = np.mean(cdf_x)
        y_mean = np.mean(cdf_y)
        numerator = np.sum((cdf_x - x_mean) * (cdf_y - y_mean))
        denominator = np.sum((cdf_x - x_mean) ** 2)

        if denominator > 1e-12:
            slope = float(numerator / denominator)
            intercept = float(y_mean - slope * x_mean)
        else:
            slope = 1.0
            intercept = 0.0

        # 计算决定系数 R^2
        y_pred = slope * cdf_x + intercept
        ss_res = np.sum((cdf_y - y_pred) ** 2)
        ss_tot = np.sum((cdf_y - y_mean) ** 2)
        r_squared = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-12 else 1.0
        r_squared = max(0.0, min(1.0, r_squared))

        # 计算柯尔莫哥洛夫-斯米尔诺夫 (KS) 最大绝对距离
        ks_stat = float(np.max(np.abs(cdf_y - cdf_x)))

        # 判定是否成一条直线
        is_straight = bool(r_squared >= self.r2_threshold and ks_stat <= self.ks_threshold)

        # 采样点位供图表渲染
        curve_points = [
            {"x": float(cdf_x[i]), "y": float(cdf_y[i]), "y_ideal": float(cdf_x[i])}
            for i in range(n_points)
        ]

        return LineFitResult(
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            ks_statistic=ks_stat,
            is_straight=is_straight,
            curve_points=curve_points,
        )

    def detect_residual_rebound_signals(
        self,
        history_draws_asc: List[List[int]],
        window_size: int = 60,
        total_balls: int = 80,
    ) -> List[ResidualReboundSignal]:
        """
        2. 累积残差均值回归直线分析与拐点捕捉 (针对 1~80 号球)
        基准线：理论水平直线 (每期各号出号概率期望 p = 20 / 80 = 0.25)。
        累积残差 CumRes(t) = Sum( actual_hit - 0.25 )。
        当曲线下探严重 (Z-Score < -1.5) 且最近 1~2 期斜率拐头向上时，判定为强反弹信号。
        """
        recent_draws = history_draws_asc[-window_size:] if len(history_draws_asc) > window_size else history_draws_asc
        n_draws = len(recent_draws)
        if n_draws < 10:
            return []

        expected_rate = 20.0 / float(total_balls)  # 0.25
        signals: List[ResidualReboundSignal] = []

        for ball in range(1, total_balls + 1):
            # 统计该球在时间轴上的出现序列
            hits = np.array([1.0 if ball in draw else 0.0 for draw in recent_draws], dtype=np.float64)
            # 计算每一步偏离理论水平基准线的残差
            step_residuals = hits - expected_rate
            # 累积残差时序
            cum_res = np.cumsum(step_residuals)

            current_val = cum_res[-1]
            prev_val = cum_res[-2] if n_draws >= 2 else current_val
            min_val = np.min(cum_res)
            mean_res = np.mean(cum_res)
            std_res = np.std(cum_res)
            std_res = std_res if std_res > 1e-6 else 1.0

            z_score = float((current_val - mean_res) / std_res)

            # 拐点反弹判定条件：
            # 1. 深度负偏离：当前位于负偏离低谷 (z_score <= -0.8 且 current_val <= 0)
            # 2. 动能拐头：最新一步或近两步残差回升，未再创出新低
            is_rebounding = False
            rebound_strength = 0.0

            if current_val < -1.5:  # 深度落后理论水平线
                momentum = current_val - prev_val
                if momentum >= 0:
                    is_rebounding = True
                    # 反弹强度由下探深度与向上拉力共同决定
                    rebound_strength = float(abs(z_score) * (1.0 + momentum))
                else:
                    # 仍在下探探底，但超卖蓄势
                    rebound_strength = float(abs(z_score) * 0.5)
            elif z_score <= -1.0 and (current_val - min_val) > 0.5:
                # 已经走出谷底开始向上回归水平线
                is_rebounding = True
                rebound_strength = float(abs(z_score) * 0.8)

            signals.append(
                ResidualReboundSignal(
                    target_id=ball,
                    target_type="ball",
                    current_cumulative_residual=float(current_val),
                    z_score=z_score,
                    is_rebounding=is_rebounding,
                    rebound_strength=rebound_strength,
                )
            )

        # 按反弹强度由大到小排序
        signals.sort(key=lambda s: s.rebound_strength, reverse=True)
        return signals
