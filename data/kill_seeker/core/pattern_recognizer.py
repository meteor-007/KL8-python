"""
MorphoSeeker V1.0 — 引擎3: 形态识别器
拓扑特征(连通域/欧拉数/骨架/质心/填充率/投影熵) + 模板匹配 双路径
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
import numpy as np
from scipy.ndimage import label as scipy_label, binary_fill_holes
from collections import deque

from kill_seeker.core.data_loader import KL8Draw
from kill_seeker.config.model_config import PatternConfig


@dataclass
class PatternResult:
    """形态识别结果"""
    topological_features: np.ndarray  # 6维拓扑特征
    top3_templates: List[Tuple[str, float]]  # (模板名, 置信度)
    connectivity_count: int           # 连通域数
    euler_number: int                 # 欧拉数
    skeleton_length: int              # 骨架长度
    centroid_offset: float            # 质心偏移
    fill_ratio: float                 # 包围盒填充率
    projection_entropy: float         # 投影熵


# ===== 预定义形态模板特征 (V2.0扩展版) =====
# P1优化: 增加更多细分模板，提升聚团/阶梯/对角线识别精度
PATTERN_TEMPLATES = {
    # === 基础形态 ===
    "L型":     {"connectivity": (1, 2), "euler": (0, 2), "fill_ratio": (0.1, 0.4), "centroid_offset": (2.0, 5.0)},
    "J型":     {"connectivity": (1, 2), "euler": (0, 2), "fill_ratio": (0.1, 0.4), "centroid_offset": (2.0, 5.0)},
    
    # === 线性形态 (增强对角线识别) ===
    "主对角线": {"connectivity": (1, 2), "euler": (0, 1), "fill_ratio": (0.05, 0.25), "centroid_offset": (0.0, 1.5)},
    "副对角线": {"connectivity": (1, 2), "euler": (0, 1), "fill_ratio": (0.05, 0.25), "centroid_offset": (0.0, 1.5)},
    "对角线":  {"connectivity": (1, 2), "euler": (0, 1), "fill_ratio": (0.05, 0.3), "centroid_offset": (0.5, 3.0)},
    "水平带":  {"connectivity": (1, 3), "euler": (0, 2), "fill_ratio": (0.2, 0.6), "centroid_offset": (0.0, 1.5)},
    "垂直带":  {"connectivity": (1, 3), "euler": (0, 2), "fill_ratio": (0.2, 0.6), "centroid_offset": (0.0, 1.5)},
    
    # === 聚团形态 (细分增强) ===
    "单聚团":  {"connectivity": (1, 1), "euler": (0, 1), "fill_ratio": (0.5, 1.0), "centroid_offset": (0.0, 2.0)},
    "双聚团":  {"connectivity": (2, 2), "euler": (0, 2), "fill_ratio": (0.4, 0.9), "centroid_offset": (0.5, 2.5)},
    "三聚团":  {"connectivity": (3, 3), "euler": (0, 3), "fill_ratio": (0.3, 0.8), "centroid_offset": (0.5, 3.0)},
    "聚团":    {"connectivity": (1, 2), "euler": (0, 2), "fill_ratio": (0.5, 1.0), "centroid_offset": (0.0, 2.0)},
    
    # === 阶梯形态 (细分增强) ===
    "上升阶梯": {"connectivity": (1, 3), "euler": (0, 2), "fill_ratio": (0.1, 0.4), "centroid_offset": (1.0, 4.0), "skeleton_direction": "up"},
    "下降阶梯": {"connectivity": (1, 3), "euler": (0, 2), "fill_ratio": (0.1, 0.4), "centroid_offset": (1.0, 4.0), "skeleton_direction": "down"},
    "阶梯":    {"connectivity": (1, 3), "euler": (0, 2), "fill_ratio": (0.1, 0.4), "centroid_offset": (1.0, 4.0)},
    
    # === 分散形态 ===
    "散点":    {"connectivity": (4, 20), "euler": (-5, 10), "fill_ratio": (0.0, 0.2), "centroid_offset": (0.5, 3.0)},
    "均匀散":  {"connectivity": (5, 20), "euler": (-5, 10), "fill_ratio": (0.0, 0.15), "centroid_offset": (0.0, 2.0)},
    
    # === 其他形态 ===
    "十字":    {"connectivity": (1, 2), "euler": (-2, 2), "fill_ratio": (0.1, 0.4), "centroid_offset": (0.0, 1.0)},
    "三角":    {"connectivity": (1, 2), "euler": (0, 2), "fill_ratio": (0.1, 0.4), "centroid_offset": (1.0, 3.0)},
    "环形":    {"connectivity": (1, 3), "euler": (-5, 0), "fill_ratio": (0.1, 0.4), "centroid_offset": (0.0, 1.5)},
    "双团":    {"connectivity": (2, 3), "euler": (0, 2), "fill_ratio": (0.1, 0.4), "centroid_offset": (1.0, 3.5)},
    "三团":    {"connectivity": (3, 4), "euler": (0, 3), "fill_ratio": (0.1, 0.3), "centroid_offset": (1.0, 3.0)},
    "边框":    {"connectivity": (1, 4), "euler": (-3, 2), "fill_ratio": (0.1, 0.3), "centroid_offset": (0.0, 1.0)},
    "满铺":    {"connectivity": (1, 2), "euler": (-5, 5), "fill_ratio": (0.5, 1.0), "centroid_offset": (0.0, 1.0)},
    
    # === 新增形态 ===
    "波浪":    {"connectivity": (2, 4), "euler": (0, 3), "fill_ratio": (0.15, 0.4), "centroid_offset": (0.5, 3.0)},
    "V型":     {"connectivity": (1, 2), "euler": (0, 2), "fill_ratio": (0.1, 0.35), "centroid_offset": (0.5, 2.5)},
    "W型":     {"connectivity": (2, 3), "euler": (0, 2), "fill_ratio": (0.1, 0.35), "centroid_offset": (0.5, 2.5)},
    "M型":     {"connectivity": (2, 3), "euler": (0, 2), "fill_ratio": (0.1, 0.35), "centroid_offset": (0.5, 2.5)},
    "N型":     {"connectivity": (1, 2), "euler": (0, 2), "fill_ratio": (0.1, 0.35), "centroid_offset": (1.0, 3.5)},
    "Z型":     {"connectivity": (1, 2), "euler": (0, 2), "fill_ratio": (0.1, 0.35), "centroid_offset": (1.0, 3.5)},
}


class PatternRecognizer:
    """引擎3: 形态识别器"""

    def __init__(self, config: Optional[PatternConfig] = None):
        self.config = config or PatternConfig()

    def recognize(self, draw: KL8Draw) -> PatternResult:
        """
        识别开号形态

        Args:
            draw: 单期开奖数据

        Returns:
            PatternResult
        """
        matrix = draw.matrix_8x10

        # 路径A: 拓扑特征提取
        connectivity = self._compute_connectivity(matrix)
        euler = self._compute_euler_number(matrix)
        skeleton_len = self._compute_skeleton_length(matrix)
        centroid_off = self._compute_centroid_offset(matrix)
        fill_ratio = self._compute_fill_ratio(matrix)
        proj_entropy = self._compute_projection_entropy(matrix)

        topo_features = np.array([
            connectivity, euler, skeleton_len, centroid_off, fill_ratio, proj_entropy
        ], dtype=float)

        # 路径B: 模板匹配
        top3 = self._match_templates(topo_features)

        return PatternResult(
            topological_features=topo_features,
            top3_templates=top3,
            connectivity_count=connectivity,
            euler_number=euler,
            skeleton_length=skeleton_len,
            centroid_offset=centroid_off,
            fill_ratio=fill_ratio,
            projection_entropy=proj_entropy,
        )

    def _compute_connectivity(self, matrix: np.ndarray) -> int:
        """计算连通域数(4-邻域BFS)"""
        visited = np.zeros_like(matrix, dtype=bool)
        count = 0

        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                if matrix[i, j] == 1 and not visited[i, j]:
                    count += 1
                    # BFS
                    queue = deque([(i, j)])
                    visited[i, j] = True
                    while queue:
                        ci, cj = queue.popleft()
                        for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            ni, nj = ci + di, cj + dj
                            if (0 <= ni < matrix.shape[0] and
                                0 <= nj < matrix.shape[1] and
                                matrix[ni, nj] == 1 and
                                not visited[ni, nj]):
                                visited[ni, nj] = True
                                queue.append((ni, nj))
        return count

    def _compute_euler_number(self, matrix: np.ndarray) -> int:
        """计算欧拉数 = 连通域数 - 孔洞数"""
        # 使用scipy计算连通域
        labeled, num_features = scipy_label(matrix)
        # 计算孔洞数(需要填充后的差异)
        if matrix.sum() == 0:
            return 0
        filled = binary_fill_holes(matrix).astype(int)
        holes = filled.sum() - matrix.sum()
        return int(num_features - holes)

    def _compute_skeleton_length(self, matrix: np.ndarray) -> int:
        """计算骨架长度(简化版：行列方向的最大连续1的长度)"""
        max_len = 0
        # 行方向
        for i in range(matrix.shape[0]):
            current = 0
            for j in range(matrix.shape[1]):
                if matrix[i, j] == 1:
                    current += 1
                    max_len = max(max_len, current)
                else:
                    current = 0
        # 列方向
        for j in range(matrix.shape[1]):
            current = 0
            for i in range(matrix.shape[0]):
                if matrix[i, j] == 1:
                    current += 1
                    max_len = max(max_len, current)
                else:
                    current = 0
        return max_len

    def _compute_centroid_offset(self, matrix: np.ndarray) -> float:
        """计算质心偏移(距中心(3.5, 4.5)的欧氏距离)"""
        if matrix.sum() == 0:
            return 0.0
        rows, cols = np.where(matrix == 1)
        centroid_r = rows.mean()
        centroid_c = cols.mean()
        return float(np.sqrt((centroid_r - 3.5) ** 2 + (centroid_c - 4.5) ** 2))

    def _compute_fill_ratio(self, matrix: np.ndarray) -> float:
        """计算包围盒填充率"""
        if matrix.sum() == 0:
            return 0.0
        rows, cols = np.where(matrix == 1)
        box_area = (rows.max() - rows.min() + 1) * (cols.max() - cols.min() + 1)
        return float(matrix.sum() / box_area)

    def _compute_projection_entropy(self, matrix: np.ndarray) -> float:
        """计算行列投影熵(Shannon熵)"""
        # 行投影
        row_proj = matrix.sum(axis=1).astype(float)
        # 列投影
        col_proj = matrix.sum(axis=0).astype(float)

        total = row_proj.sum()
        if total == 0:
            return 0.0

        entropy = 0.0
        for proj in [row_proj, col_proj]:
            probs = proj / total
            for p in probs:
                if p > 0:
                    entropy -= p * np.log2(p)

        return float(entropy)

    def _match_templates(self, features: np.ndarray) -> List[Tuple[str, float]]:
        """模板匹配：计算与各模板的余弦相似度"""
        scores = {}
        for name, template in PATTERN_TEMPLATES.items():
            # 构建模板特征向量(取范围中值)
            template_features = np.array([
                np.mean(template["connectivity"]),
                np.mean(template["euler"]),
                5.0,  # skeleton_length中值
                np.mean(template["centroid_offset"]),
                np.mean(template["fill_ratio"]),
                3.0,  # entropy中值
            ], dtype=float)

            # 余弦相似度
            norm_f = np.linalg.norm(features)
            norm_t = np.linalg.norm(template_features)
            if norm_f > 0 and norm_t > 0:
                sim = float(np.dot(features, template_features) / (norm_f * norm_t))
            else:
                sim = 0.0

            # tanh平滑置信度
            confidence = float(np.tanh(
                self.config.tanh_smoothing_factor * (sim - self.config.tanh_center)
            ))
            scores[name] = max(0.0, confidence)

        # 排序取 TOP-N
        sorted_templates = sorted(scores.items(), key=lambda x: -x[1])
        return sorted_templates[:self.config.top_n_templates]
