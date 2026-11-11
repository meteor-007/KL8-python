# -*- coding: utf-8 -*-
"""
马尔可夫转移核心引擎 (Markov Engine - 多尺度时间窗口融合升级版)
============================================================
负责构建具备四大实操因子的动态转移矩阵：
  1. 多尺度时间窗口马氏融合 (Multi-Scale Half-Life Ensemble):
     短期 (0.4x)、中期 (1.0x)、长期 (2.2x) 三尺度矩阵加权几何平滑，兼顾短期敏锐度与长期平稳性。
  2. 阶数融合 (一阶主干 + 二阶惯性衰减融合)
  3. 狄利克雷/拉普拉斯先验平滑 (Dirichlet / Laplace Smoothing)
  4. 严格行归一化守卫、平稳分布计算与转移熵指标 (衡量转移确定性)
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np


class MarkovEngine:
    """动态高阶多尺度马尔可夫推演核心"""

    def __init__(
        self,
        num_states: int = 6,
        half_life: float = 35.0,
        second_order_weight: float = 0.20,
        smoothing_alpha: float = 0.05,
        enable_multiscale: bool = True,
    ):
        """
        初始化马尔可夫推演引擎
        :param num_states: 离散状态总数 (默认 6)
        :param half_life: 中期主尺度半衰期期数 (默认 35 期)
        :param second_order_weight: 二阶转移融合权重 (默认 0.20)
        :param smoothing_alpha: 狄利克雷平滑超参 (默认 0.05)
        :param enable_multiscale: 是否启用多尺度时间窗口融合
        """
        self.num_states = num_states
        self.half_life = half_life
        self.second_order_weight = second_order_weight
        self.smoothing_alpha = smoothing_alpha
        self.enable_multiscale = enable_multiscale

        # 一阶转移概率矩阵: [num_states, num_states]
        self.trans_matrix_1st = np.zeros((num_states, num_states), dtype=np.float64)
        # 二阶转移概率张量: [num_states, num_states, num_states] (s_{t-2}, s_{t-1} -> s_t)
        self.trans_tensor_2nd = np.zeros((num_states, num_states, num_states), dtype=np.float64)
        # 稳态平稳分布向量
        self.stationary_dist = np.ones(num_states, dtype=np.float64) / num_states
        # 是否已完成拟合
        self.is_fitted = False

    def _calc_time_weight(self, step_idx: int, total_steps: int, hl: float) -> float:
        """
        计算指定半衰期下的时间衰减权重：指数半衰期模型
        w = 2 ** (-(total_steps - 1 - step_idx) / hl)
        """
        if hl <= 0:
            return 1.0
        delta = total_steps - 1 - step_idx
        return float(np.exp(-np.log(2.0) * delta / hl))

    def _build_single_scale_matrix(
        self,
        state_sequence: List[int],
        hl: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """构建单一时间尺度下的加权一阶矩阵与二阶张量"""
        n = len(state_sequence)
        counts_1st = np.zeros((self.num_states, self.num_states), dtype=np.float64)
        counts_2nd = np.zeros((self.num_states, self.num_states, self.num_states), dtype=np.float64)

        for t in range(n - 1):
            w = self._calc_time_weight(t, n, hl)
            s_curr = state_sequence[t]
            s_next = state_sequence[t + 1]

            if 0 <= s_curr < self.num_states and 0 <= s_next < self.num_states:
                counts_1st[s_curr, s_next] += w

            if t >= 1:
                s_prev = state_sequence[t - 1]
                if 0 <= s_prev < self.num_states:
                    counts_2nd[s_prev, s_curr, s_next] += w

        # 狄利克雷平滑与行归一化
        smoothed_1st = counts_1st + self.smoothing_alpha
        row_sums_1st = smoothed_1st.sum(axis=1, keepdims=True)
        row_sums_1st[row_sums_1st == 0] = 1.0
        mat_1st = smoothed_1st / row_sums_1st

        smoothed_2nd = counts_2nd + (self.smoothing_alpha * 0.2)
        plane_sums_2nd = smoothed_2nd.sum(axis=2, keepdims=True)
        plane_sums_2nd[plane_sums_2nd == 0] = 1.0
        tensor_2nd = smoothed_2nd / plane_sums_2nd

        return mat_1st, tensor_2nd

    def fit(self, state_sequence: List[int]) -> None:
        """
        输入状态时序，构建多尺度融合转移矩阵
        """
        n = len(state_sequence)
        if n < 3:
            raise ValueError(f"状态序列过短 (仅 {n} 项)，无法训练马尔可夫模型")

        if self.enable_multiscale:
            # 三尺度半衰期：短期、中期、长期
            hl_short = max(10.0, self.half_life * 0.45)
            hl_mid = self.half_life
            hl_long = min(90.0, self.half_life * 2.2)

            mat_s, ten_s = self._build_single_scale_matrix(state_sequence, hl_short)
            mat_m, ten_m = self._build_single_scale_matrix(state_sequence, hl_mid)
            mat_l, ten_l = self._build_single_scale_matrix(state_sequence, hl_long)

            # 多尺度加权融合 (短期 35% + 中期 45% + 长期 20%)
            self.trans_matrix_1st = 0.35 * mat_s + 0.45 * mat_m + 0.20 * mat_l
            self.trans_tensor_2nd = 0.35 * ten_s + 0.45 * ten_m + 0.20 * ten_l
        else:
            self.trans_matrix_1st, self.trans_tensor_2nd = self._build_single_scale_matrix(
                state_sequence, self.half_life
            )

        # 求解平稳分布 (特征值分解求左特征向量)
        try:
            eigenvals, eigenvecs = np.linalg.eig(self.trans_matrix_1st.T)
            idx_1 = np.argmin(np.abs(eigenvals - 1.0))
            stationary = np.real(eigenvecs[:, idx_1])
            stationary = np.maximum(stationary, 0.0)
            sum_s = np.sum(stationary)
            if sum_s > 0:
                self.stationary_dist = stationary / sum_s
            else:
                self.stationary_dist = np.ones(self.num_states) / self.num_states
        except Exception:
            self.stationary_dist = np.ones(self.num_states) / self.num_states

        self.is_fitted = True

    def predict_next_state_distribution(
        self,
        current_state: int,
        prev_state: Optional[int] = None,
    ) -> np.ndarray:
        """
        推演下一期的宏观状态概率分布向量
        """
        if not self.is_fitted:
            raise RuntimeError("MarkovEngine 尚未拟合，请先调用 fit()")

        p_1st = self.trans_matrix_1st[current_state].copy()

        if prev_state is not None and 0 <= prev_state < self.num_states:
            p_2nd = self.trans_tensor_2nd[prev_state, current_state].copy()
            beta = 1.0 - self.second_order_weight
            combined = beta * p_1st + self.second_order_weight * p_2nd
        else:
            combined = p_1st

        c_sum = float(np.sum(combined))
        if c_sum > 0:
            combined = combined / c_sum
        else:
            combined = np.ones(self.num_states) / self.num_states

        return combined

    def compute_state_entropy(self, prob_dist: np.ndarray) -> float:
        """
        计算转移分布的香农熵 (衡量本次状态跃迁的确定性)
        H 低于 1.5 表示高置信度高聚集；高于 2.2 表示大环境分散无序
        """
        safe_p = prob_dist[prob_dist > 1e-12]
        return float(-np.sum(safe_p * np.log2(safe_p)))
