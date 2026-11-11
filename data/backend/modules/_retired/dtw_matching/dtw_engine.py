# -*- coding: utf-8 -*-
"""
动态时间规整 DTW 量化推演核心计算引擎 (DTW Engine V2.0 深度优化版)
===================================================================
【业务背景与架构定位】:
K8-Quant 系统第 11 大精锐独立量化推演子系统（深度自进化版）。
三大内部数学升级：
1. Sakoe-Chiba 带宽限位约束 —— 限制 |i - j| <= BandWidth，防止时间轴过度畸变失真；
2. Soft-DTW 平滑多路径积分 —— 采用 log-sum-exp 软极小算子，融合所有近优规整路径提升容错率；
3. Derivative DTW 动量差分复合距离 —— 融合“号码出现位置”与“号码冷热加速度(一阶导数)”。

@author K8-Quant DTW Team
@since 2026-09-11
"""
import os
import math
import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

logger = logging.getLogger("k8quant.dtw")

TOTAL_BALLS = 80
DEFAULT_TARGET_WINDOW = 6
MIN_HIST_WINDOW = 4
MAX_HIST_WINDOW = 8
TOP_K_MATCHES = 5
SOFT_DTW_GAMMA = 0.15 # 平滑温度系数
BAND_WIDTH = 3        # Sakoe-Chiba 带宽约束


class DTWEngine:
    """动态时间规整推演引擎 (深度优化版)"""

    def __init__(self, history_data: Optional[List[Dict[str, Any]]] = None):
        self.history_data = history_data or []
        self._chrono_history: List[Dict[str, Any]] = []
        self._matrix_01: Optional[np.ndarray] = None
        self._diff_matrix: Optional[np.ndarray] = None
        self._total_draws: int = 0

        if self.history_data:
            self._prepare_matrix()

    def _prepare_matrix(self) -> None:
        """步骤 1: 构建 0-1 开奖矩阵与一阶时序动量导数矩阵"""
        self._chrono_history = sorted(
            [item for item in self.history_data if len(item.get("numbers", [])) >= 10],
            key=lambda x: str(x.get("issue", ""))
        )
        self._total_draws = len(self._chrono_history)

        if self._total_draws == 0:
            self._matrix_01 = np.zeros((0, TOTAL_BALLS), dtype=np.float64)
            self._diff_matrix = np.zeros((0, TOTAL_BALLS), dtype=np.float64)
            return

        mat = np.zeros((self._total_draws, TOTAL_BALLS), dtype=np.float64)
        for row_idx, item in enumerate(self._chrono_history):
            for num in item.get("numbers", []):
                if 1 <= num <= TOTAL_BALLS:
                    mat[row_idx, num - 1] = 1.0
        self._matrix_01 = mat

        # 计算一阶差分动量矩阵 (Derivative Momentum)
        diff_mat = np.zeros_like(mat)
        if self._total_draws > 1:
            diff_mat[1:, :] = mat[1:, :] - mat[:-1, :]
        self._diff_matrix = diff_mat

    @staticmethod
    def _composite_dist(v1: np.ndarray, v2: np.ndarray, d1: np.ndarray, d2: np.ndarray) -> float:
        """计算融合状态与动量导数的复合距离"""
        # 1. 静态余弦距离
        norm1, norm2 = np.linalg.norm(v1), np.linalg.norm(v2)
        sim_pos = float(np.dot(v1, v2) / (norm1 * norm2 + 1e-9))
        dist_pos = max(0.0, 1.0 - sim_pos)

        # 2. 一阶差分动量余弦距离
        norm_d1, norm_d2 = np.linalg.norm(d1), np.linalg.norm(d2)
        if norm_d1 > 0 and norm_d2 > 0:
            sim_der = float(np.dot(d1, d2) / (norm_d1 * norm_d2 + 1e-9))
            dist_der = max(0.0, 1.0 - sim_der)
        else:
            dist_der = dist_pos

        return 0.70 * dist_pos + 0.30 * dist_der

    @staticmethod
    def _soft_min(a: float, b: float, c: float, gamma: float = SOFT_DTW_GAMMA) -> float:
        """Soft-Min 算子: -gamma * log(exp(-a/gamma) + exp(-b/gamma) + exp(-c/gamma))"""
        m = min(a, b, c)
        if math.isinf(m):
            return np.inf
        # 防止数值溢出
        return float(m - gamma * math.log(
            math.exp(-(a - m) / gamma) +
            math.exp(-(b - m) / gamma) +
            math.exp(-(c - m) / gamma)
        ))

    def _compute_soft_dtw_with_band(
        self,
        seq_t: np.ndarray, diff_t: np.ndarray,
        seq_h: np.ndarray, diff_h: np.ndarray
    ) -> float:
        """
        步骤 2: 结合 Sakoe-Chiba 带宽与 Soft-DTW 的平滑规整距离计算
        """
        n, m = len(seq_t), len(seq_h)
        dtw_mat = np.full((n + 1, m + 1), np.inf, dtype=np.float64)
        dtw_mat[0, 0] = 0.0

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                # Sakoe-Chiba 带宽约束
                if abs(i - j) > BAND_WIDTH:
                    continue

                cost = self._composite_dist(seq_t[i - 1], seq_h[j - 1], diff_t[i - 1], diff_h[j - 1])
                dtw_mat[i, j] = cost + self._soft_min(
                    dtw_mat[i - 1, j],
                    dtw_mat[i, j - 1],
                    dtw_mat[i - 1, j - 1]
                )

        norm_dist = float(dtw_mat[n, m] / math.sqrt(n * m))
        return norm_dist

    def run_prediction(self) -> Dict[str, Any]:
        """步骤 3: 扫描全量历史执行优化版 DTW 弹性走势推演"""
        if self._matrix_01 is None or self._total_draws < (MAX_HIST_WINDOW + 10):
            return {"error": "历史开奖数据不足"}

        target_issue = str(int(self.history_data[0].get("issue", "0")) + 1)
        latest_issue = self.history_data[0].get("issue", "")
        latest_numbers = self.history_data[0].get("numbers", [])

        target_seq = self._matrix_01[-DEFAULT_TARGET_WINDOW:, :]
        target_diff = self._diff_matrix[-DEFAULT_TARGET_WINDOW:, :]

        matches = []
        max_start = self._total_draws - MAX_HIST_WINDOW - 2

        for l in range(MIN_HIST_WINDOW, MAX_HIST_WINDOW + 1):
            for start_idx in range(max_start):
                end_idx = start_idx + l
                hist_seq = self._matrix_01[start_idx:end_idx, :]
                hist_diff = self._diff_matrix[start_idx:end_idx, :]

                dist = self._compute_soft_dtw_with_band(target_seq, target_diff, hist_seq, hist_diff)
                if math.isinf(dist) or math.isnan(dist):
                    continue

                next_issue_data = self._chrono_history[end_idx]

                matches.append({
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "span_len": l,
                    "period_range": f"{self._chrono_history[start_idx].get('issue', '')} ~ {self._chrono_history[end_idx - 1].get('issue', '')} 期",
                    "target_issue": next_issue_data.get("issue", ""),
                    "next_numbers": next_issue_data.get("numbers", []),
                    "dtw_dist": float(round(dist, 4)),
                    "elastic_similarity_pct": float(round(max(0.0, 1.0 - dist) * 100, 2))
                })

        matches.sort(key=lambda x: x["dtw_dist"])
        top_matches = matches[:TOP_K_MATCHES]

        # Softmax 逆距离加权投影
        dists = np.array([m["dtw_dist"] for m in top_matches])
        min_d = np.min(dists)
        inv_weights = np.exp(-(dists - min_d) * 10.0)
        softmax_weights = inv_weights / (np.sum(inv_weights) + 1e-9)

        ball_scores = np.zeros(TOTAL_BALLS, dtype=np.float64)
        for idx, match in enumerate(top_matches):
            w = float(softmax_weights[idx])
            match["ensemble_weight"] = float(round(w * 100, 2))
            for b in match["next_numbers"]:
                if 1 <= b <= TOTAL_BALLS:
                    ball_scores[b - 1] += w

        min_s, max_s = np.min(ball_scores), np.max(ball_scores)
        if max_s > min_s:
            norm_scores = (ball_scores - min_s) / (max_s - min_s) * 100.0
        else:
            norm_scores = np.ones(TOTAL_BALLS) * 50.0

        ball_details = []
        for i in range(TOTAL_BALLS):
            ball = i + 1
            ball_details.append({
                "ball": ball,
                "ball_str": f"{ball:02d}",
                "dtw_score": float(round(norm_scores[i], 2)),
                "is_recent_open": bool(ball in latest_numbers)
            })

        sorted_details = sorted(ball_details, key=lambda x: x["dtw_score"], reverse=True)

        top3_gold = [item["ball"] for item in sorted_details[:3]]
        top5_gold = top3_gold  # 兼容旧字段：主推改为最优3码
        top12_elite = top3_gold  # 兼容旧字段：不再维护 Top12

        for m in top_matches:
            overlap = sorted(list(set(m["next_numbers"]) & set(top12_elite)))
            m["overlap_with_top12"] = overlap
            m["overlap_count"] = len(overlap)

        gold_pairs = []
        for i in range(len(sorted_details[:12])):
            for j in range(i + 1, min(i + 4, len(sorted_details[:12]))):
                b1, b2 = sorted_details[i]["ball"], sorted_details[j]["ball"]
                score = round((sorted_details[i]["dtw_score"] + sorted_details[j]["dtw_score"]) / 2, 1)
                gold_pairs.append({
                    "pair": f"{min(b1, b2):02d}-{max(b1, b2):02d}",
                    "affinity_score": score
                })
        gold_pairs = gold_pairs[:5]

        return {
            "module_code": "dtw_matching",
            "module_name": "11. 动态时间规整DTW推演引擎 (V2.0 深度优化版)",
            "target_issue": target_issue,
            "latest_issue": latest_issue,
            "latest_numbers": latest_numbers,
            "total_historical_draws": self._total_draws,
            "target_window_size": DEFAULT_TARGET_WINDOW,
            "top3_gold": top3_gold,
            "top5_gold": top5_gold,
            "top12_elite": top12_elite,
            "gold_pairs": gold_pairs,
            "top_historical_matches": top_matches,
            "ball_details": sorted_details
        }
