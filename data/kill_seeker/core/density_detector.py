"""
MorphoSeeker V1.0 — 引擎2: 密集区域探测器
核密度估计 + 冷寂区检测
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional
import numpy as np
from scipy.stats import gaussian_kde

from kill_seeker.core.data_loader import KL8Draw
from kill_seeker.config.model_config import DensityConfig


@dataclass
class DensityResult:
    """密集区域检测结果"""
    clusters: List[Dict]          # 保持接口兼容 (留空)
    density_map: np.ndarray       # 8×10 密度热力图（参与评分，kill_predictor 读取）
    cold_zones: List[int]         # 冷寂区号码列表（仅 main.py 展示用，未接入评分）
    hot_centers: List[int]        # 密集中心号码列表 (留空)
    coverage_ratio: float         # 空间覆盖率（未接入评分）


class DensityDetector:
    """引擎2: 密集区域探测器"""

    def __init__(self, config: Optional[DensityConfig] = None):
        self.config = config or DensityConfig()

    def detect(self, draws: List[KL8Draw]) -> DensityResult:
        """
        检测密集区域

        Args:
            draws: 近N期开奖数据

        Returns:
            DensityResult
        """
        # Step 1: 号码嵌入到2D坐标
        coords, weights = self._embed_numbers(draws)

        if len(coords) == 0:
            return DensityResult(
                clusters=[], density_map=np.zeros((8, 10)),
                cold_zones=list(range(1, 81)), hot_centers=[],
                coverage_ratio=0.0,
            )

        # Step 2: KDE密度热力图
        density_map = self._compute_kde(coords, weights)

        # Step 3: 冷寂区检测（仅展示用，未接入杀号评分）
        cold_zones = self._detect_cold_zones(density_map)

        # 空间覆盖率
        coverage = float(np.sum(density_map > 0.01) / 80.0)

        return DensityResult(
            clusters=[],
            density_map=density_map,
            cold_zones=cold_zones,
            hot_centers=[],
            coverage_ratio=coverage,
        )

    def _embed_numbers(
        self, draws: List[KL8Draw]
    ) -> tuple:
        """号码嵌入到2D坐标"""
        freq = {}
        for draw in draws:
            for num in draw.numbers:
                freq[num] = freq.get(num, 0) + 1

        coords = []
        weights = []
        for num, count in freq.items():
            x = (num - 1) // 10  # 行 0-7
            y = (num - 1) % 10   # 列 0-9
            coords.append([x, y])
            weights.append(count)

        return np.array(coords, dtype=float), np.array(weights, dtype=float)

    def _compute_kde(self, coords: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """核密度估计生成8×10密度热力图"""
        if len(coords) < 2:
            # 不知足2个点无法做KDE
            density_map = np.zeros((8, 10))
            for i, (x, y) in enumerate(coords):
                density_map[int(x), int(y)] = weights[i]
            return density_map / max(density_map.max(), 1)

        try:
            weighted_coords = np.repeat(coords, weights.astype(int), axis=0)
            kde = gaussian_kde(weighted_coords.T, bw_method=self.config.kde_bandwidth)

            # 在8×10网格上评估
            grid_x, grid_y = np.meshgrid(np.arange(8), np.arange(10), indexing='ij')
            grid_points = np.vstack([grid_x.ravel(), grid_y.ravel()])
            density_values = kde(grid_points).reshape(8, 10)

            # 归一化到[0,1]
            dmax = density_values.max()
            if dmax > 0:
                density_values /= dmax

            return density_values

        except Exception:
            density_map = np.zeros((8, 10))
            for i, (x, y) in enumerate(coords):
                density_map[int(x), int(y)] = weights[i]
            return density_map / max(density_map.max(), 1)

    def _detect_cold_zones(self, density_map: np.ndarray) -> List[int]:
        """检测冷寂区"""
        threshold = np.percentile(density_map, self.config.cold_zone_percentile * 100)
        cold_zones = []
        for row in range(8):
            for col in range(10):
                if density_map[row, col] <= threshold:
                    num = row * 10 + col + 1
                    cold_zones.append(num)
        return cold_zones
