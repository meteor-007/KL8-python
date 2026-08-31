"""
MorphoSeeker V1.0 — 引擎1: 相似走势匹配器
多尺度DTW + 自适应加权 + 4维度复合距离
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
import numpy as np
from scipy.spatial.distance import cosine
from scipy.signal import correlate

from kill_seeker.core.data_loader import KL8Draw
from kill_seeker.config.model_config import SimilarityConfig


@dataclass
class SimilarityResult:
    """相似走势匹配结果"""
    top_k_periods: List[Tuple[str, float]]  # (期号, 相似度)
    optimal_window: int                       # 最优匹配窗口长度
    dimension_contributions: Dict[str, float] # 各维度贡献
    subsequent_freq: Dict[int, float]         # 后续号码频率 (1-80)
    consistency_score: float                  # 后续走势一致性


class SimilarityMatcher:
    """引擎1: 相似走势匹配器"""

    def __init__(self, config: Optional[SimilarityConfig] = None):
        self.config = config or SimilarityConfig()
        self.weights = dict(self.config.initial_weights)

    def find_similar(
        self,
        current_draws: List[KL8Draw],
        history: List[KL8Draw],
    ) -> SimilarityResult:
        """
        在历史中寻找与当前走势最相似的期段

        Args:
            current_draws: 近N期开奖数据
            history: 全量历史数据（必须 ≤T）

        Returns:
            SimilarityResult
        """
        # Step 1: 自适应窗口选择
        optimal_window = self._select_optimal_window(current_draws)
        window_draws = current_draws[:optimal_window]

        # Step 2: 遍历历史，计算4维度距离 (排除当前窗口及后续期以防数据泄漏)
        raw_candidates = []
        start_idx = optimal_window + self.config.subsequent_periods
        for i in range(start_idx, len(history) - optimal_window):
            hist_window = history[i:i + optimal_window]
            distances = self._compute_multi_dimension_distance(window_draws, hist_window)
            raw_candidates.append((history[i].period, distances))

        # Step 2.5: 跨候选 min-max 归一化后计算复合距离
        # 修复: trend_curve 原始欧氏距离量级远大于[0,1]，
        # 旧实现 min(val,1.0) 使其恒为1.0，丧失区分力
        candidates = []
        if raw_candidates:
            dim_keys = list(self.weights.keys())
            dim_vals = {k: [d[k] for _, d in raw_candidates] for k in dim_keys}
            dim_min = {k: min(v) for k, v in dim_vals.items()}
            dim_max = {k: max(v) for k, v in dim_vals.items()}
            for period, distances in raw_candidates:
                normalized = {}
                for k in dim_keys:
                    rng = dim_max[k] - dim_min[k]
                    normalized[k] = (distances[k] - dim_min[k]) / rng if rng > 1e-12 else 0.0
                composite = sum(self.weights.get(k, 0.25) * normalized.get(k, 0.0)
                               for k in self.weights)
                candidates.append((period, composite, distances))

        # Step 3: 排序取 Top-K
        candidates.sort(key=lambda x: x[1])
        top_k = candidates[:self.config.top_k]

        # Step 4: 提取后续走势
        subsequent_freq = self._extract_subsequent_frequency(top_k, history)
        consistency = self._compute_consistency(top_k, history)

        # 各维度贡献
        contributions = self._compute_dimension_contributions(top_k)

        return SimilarityResult(
            top_k_periods=[(p, d) for p, d, _ in top_k],
            optimal_window=optimal_window,
            dimension_contributions=contributions,
            subsequent_freq=subsequent_freq,
            consistency_score=consistency,
        )

    def _select_optimal_window(self, draws: List[KL8Draw]) -> int:
        """基于ACF选择最优匹配窗口长度"""
        if len(draws) < 3:
            return min(self.config.default_window, len(draws))

        # 计算和值序列的ACF
        sum_series = np.array([d.sum_value for d in draws])
        best_lag = self.config.default_window
        best_acf = 0.0

        for lag in self.config.window_candidates:
            if lag >= len(draws):
                continue
            acf_val = self._compute_acf(sum_series, lag)
            if acf_val > best_acf:
                best_acf = acf_val
                best_lag = lag

        return best_lag

    @staticmethod
    def _compute_acf(series: np.ndarray, lag: int) -> float:
        """计算自相关函数"""
        if len(series) <= lag:
            return 0.0
        mean = series.mean()
        var = np.sum((series - mean) ** 2)
        if var == 0:
            return 0.0
        acf = np.sum((series[:len(series) - lag] - mean) * (series[lag:] - mean)) / var
        return float(acf)

    def _compute_multi_dimension_distance(
        self, current: List[KL8Draw], historical: List[KL8Draw]
    ) -> Dict[str, float]:
        """计算4维度距离"""
        distances = {}

        # 维度1: 号码重叠 (Jaccard距离)
        current_nums = set()
        hist_nums = set()
        for d in current:
            current_nums |= d.number_set
        for d in historical:
            hist_nums |= d.number_set
        intersection = current_nums & hist_nums
        union = current_nums | hist_nums
        distances["number_overlap"] = 1.0 - len(intersection) / max(len(union), 1)

        # 维度2: 区间分布 (余弦距离)
        current_zones = np.array([d.zone_counts for d in current]).sum(axis=0).astype(float)
        hist_zones = np.array([d.zone_counts for d in historical]).sum(axis=0).astype(float)
        norm_c = np.linalg.norm(current_zones)
        norm_h = np.linalg.norm(hist_zones)
        if norm_c > 0 and norm_h > 0:
            distances["zone_distribution"] = float(
                1.0 - np.dot(current_zones, hist_zones) / (norm_c * norm_h)
            )
        else:
            distances["zone_distribution"] = 1.0

        # 维度3: 走势曲线 (简化DTW — 欧氏距离近似)
        current_sums = np.array([d.sum_value for d in current], dtype=float)
        hist_sums = np.array([d.sum_value for d in historical], dtype=float)
        distances["trend_curve"] = float(np.linalg.norm(current_sums - hist_sums))

        # 维度4: 矩阵形态 (简化SSIM — 矩阵差异)
        current_matrix = sum(d.matrix_8x10 for d in current)
        hist_matrix = sum(d.matrix_8x10 for d in historical)
        current_matrix = current_matrix / max(current_matrix.max(), 1)
        hist_matrix = hist_matrix / max(hist_matrix.max(), 1)
        distances["matrix_shape"] = float(np.mean((current_matrix - hist_matrix) ** 2))

        return distances

    def _extract_subsequent_frequency(
        self, top_k: List, history: List[KL8Draw]
    ) -> Dict[int, float]:
        """提取相似期后续号码频率

        history按期号降序排列（history[0]=最新, history[-1]=最旧）。
        相似期history[idx]的"后续"=期号更大的期=在列表中索引更小的位置(idx-j)。
        例如：相似期2025061(idx=500)，其后续2025062在idx-1位置。
        """
        freq = {i: 0.0 for i in range(1, 81)}
        total_periods = 0

        for period, _, _ in top_k:
            # 找到该期在历史中的位置
            for idx, draw in enumerate(history):
                if draw.period == period:
                    # 后续期 = 期号更大的期 = 在降序列表中索引更小的位置
                    for j in range(1, self.config.subsequent_periods + 1):
                        if idx - j >= 0:
                            for num in history[idx - j].numbers:
                                freq[num] += 1.0
                            total_periods += 1
                    break

        if total_periods > 0:
            freq = {k: v / total_periods for k, v in freq.items()}

        return freq

    def _compute_consistency(self, top_k: List, history: List[KL8Draw]) -> float:
        """计算后续走势一致性

        后续期 = 降序列表中索引更小的位置(idx-j)
        """
        if len(top_k) < 2:
            return 1.0

        subsequent_zones = []
        for period, _, _ in top_k:
            for idx, draw in enumerate(history):
                if draw.period == period:
                    zones_list = []
                    for j in range(1, self.config.subsequent_periods + 1):
                        if idx - j >= 0:
                            zones_list.append(history[idx - j].zone_counts)
                    if zones_list:
                        subsequent_zones.append(np.mean(zones_list, axis=0))
                    break

        if len(subsequent_zones) < 2:
            return 1.0

        # 一致性 = 1 - 变异系数
        arr = np.array(subsequent_zones)
        mean = arr.mean(axis=0)
        std = arr.std(axis=0)
        cv = np.mean(std / (mean + 1e-8))
        return float(max(0.0, 1.0 - cv))

    def _compute_dimension_contributions(self, top_k: List) -> Dict[str, float]:
        """计算各维度贡献"""
        total = sum(self.weights.values())
        if total == 0:
            return {k: 0.25 for k in self.weights}
        return {k: v / total for k, v in self.weights.items()}
