# -*- coding: utf-8 -*-
"""
矩阵轮廓极速查重量化推演引擎 (Matrix Profile Engine V2.0 深度优化版)
=====================================================================
【业务背景与架构定位】:
K8-Quant 系统第 13 大精锐独立量化推演子系统（深度自进化版）。
三大内部数学升级：
1. 泛矩阵轮廓多分辨率查重 (Pan-Matrix Profile) —— 跨 4 期/6 期/8 期/10 期多窗口并行扫描孪生形态；
2. Z-Score 标准化波形去偏 —— 消除整体出号偏大/偏小的绝对基准位移，专注于纯几何波动形状；
3. 多分辨率 Motif 社群共振融合 —— 提取在多个窗口下均高频共现的真正核心金胆。

@author K8-Quant Matrix Profile Team
@since 2026-09-11
"""
import os
import math
import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

logger = logging.getLogger("k8quant.matrix_profile")

TOTAL_BALLS = 80
MULTI_WINDOWS = [4, 6, 8, 10]
TOP_MOTIFS_PER_WINDOW = 3


class MatrixProfileEngine:
    """矩阵轮廓极速查重引擎 (深度优化版)"""

    def __init__(self, history_data: Optional[List[Dict[str, Any]]] = None):
        self.history_data = history_data or []
        self._chrono_history: List[Dict[str, Any]] = []
        self._matrix_01: Optional[np.ndarray] = None
        self._total_draws: int = 0

        if self.history_data:
            self._prepare_matrix()

    def _prepare_matrix(self) -> None:
        self._chrono_history = sorted(
            [item for item in self.history_data if len(item.get("numbers", [])) >= 10],
            key=lambda x: str(x.get("issue", ""))
        )
        self._total_draws = len(self._chrono_history)

        if self._total_draws == 0:
            self._matrix_01 = np.zeros((0, TOTAL_BALLS), dtype=np.float64)
            return

        mat = np.zeros((self._total_draws, TOTAL_BALLS), dtype=np.float64)
        for row_idx, item in enumerate(self._chrono_history):
            for num in item.get("numbers", []):
                if 1 <= num <= TOTAL_BALLS:
                    mat[row_idx, num - 1] = 1.0
        self._matrix_01 = mat

    @staticmethod
    def _z_normalize(v: np.ndarray) -> np.ndarray:
        """Z-Score 标准化向量"""
        mu = np.mean(v)
        std = np.std(v)
        if std == 0:
            return v - mu
        return (v - mu) / std

    def run_prediction(self) -> Dict[str, Any]:
        max_w = max(MULTI_WINDOWS)
        if self._matrix_01 is None or self._total_draws < (max_w + 20):
            return {"error": "历史开奖数据不足"}

        target_issue = str(int(self.history_data[0].get("issue", "0")) + 1)
        latest_issue = self.history_data[0].get("issue", "")
        latest_numbers = self.history_data[0].get("numbers", [])

        # 步骤 1: 跨 4 个不同窗口分辨率执行 Pan-Matrix Profile 查重
        all_window_motifs = []
        accumulated_ball_scores = np.zeros(TOTAL_BALLS, dtype=np.float64)

        for w_size in MULTI_WINDOWS:
            # Query 向量与 Z-Score 标准化
            query_raw = self._matrix_01[-w_size:, :].flatten()
            query_z = self._z_normalize(query_raw)
            q_norm = np.linalg.norm(query_z) + 1e-9

            n_sub = self._total_draws - w_size - 1
            dist_profile = []

            for i in range(n_sub):
                sub_raw = self._matrix_01[i:i + w_size, :].flatten()
                sub_z = self._z_normalize(sub_raw)
                s_norm = np.linalg.norm(sub_z) + 1e-9

                # 归一化欧氏距离 (消除基准位移)
                dist = float(np.linalg.norm(query_z / q_norm - sub_z / s_norm))

                next_draw = self._chrono_history[i + w_size]
                start_iss = self._chrono_history[i].get("issue", "")
                end_iss = self._chrono_history[i + w_size - 1].get("issue", "")

                dist_profile.append({
                    "window_size": w_size,
                    "sub_idx": i,
                    "period_range": f"{start_iss} ~ {end_iss} 期",
                    "target_issue": next_draw.get("issue", ""),
                    "next_numbers": next_draw.get("numbers", []),
                    "euc_dist": dist,
                    "similarity_pct": float(round(max(0.0, 1.0 - dist / math.sqrt(2)) * 100, 2))
                })

            dist_profile.sort(key=lambda x: x["euc_dist"])
            top_w_motifs = dist_profile[:TOP_MOTIFS_PER_WINDOW]

            # 逆距离 Softmax 加权
            w_dists = np.array([m["euc_dist"] for m in top_w_motifs])
            min_wd = np.min(w_dists)
            inv_w = np.exp(-(w_dists - min_wd) * 8.0)
            softmax_w = inv_w / (np.sum(inv_w) + 1e-9)

            for idx, motif in enumerate(top_w_motifs):
                w_val = float(softmax_w[idx])
                motif["ensemble_weight"] = float(round(w_val * 100, 2))
                all_window_motifs.append(motif)
                for b in motif["next_numbers"]:
                    if 1 <= b <= TOTAL_BALLS:
                        accumulated_ball_scores[b - 1] += w_val

        # 综合全窗口得分归一化
        min_s, max_s = np.min(accumulated_ball_scores), np.max(accumulated_ball_scores)
        if max_s > min_s:
            norm_scores = (accumulated_ball_scores - min_s) / (max_s - min_s) * 100.0
        else:
            norm_scores = np.ones(TOTAL_BALLS) * 50.0

        ball_details = []
        for i in range(TOTAL_BALLS):
            ball = i + 1
            ball_details.append({
                "ball": ball,
                "ball_str": f"{ball:02d}",
                "mp_score": float(round(norm_scores[i], 2)),
                "is_recent_open": bool(ball in latest_numbers)
            })

        sorted_details = sorted(ball_details, key=lambda x: x["mp_score"], reverse=True)

        top3_gold = [item["ball"] for item in sorted_details[:3]]
        top5_gold = top3_gold  # 兼容旧字段：主推改为最优3码
        top12_elite = top3_gold  # 兼容旧字段：不再维护 Top12

        # 筛选全局最强 Top 5 Motifs
        all_window_motifs.sort(key=lambda x: x["euc_dist"])
        top_global_motifs = all_window_motifs[:5]

        for m in top_global_motifs:
            overlap = sorted(list(set(m["next_numbers"]) & set(top12_elite)))
            m["overlap_with_top12"] = overlap
            m["overlap_count"] = len(overlap)

        gold_pairs = []
        for i in range(len(sorted_details[:12])):
            for j in range(i + 1, min(i + 4, len(sorted_details[:12]))):
                b1, b2 = sorted_details[i]["ball"], sorted_details[j]["ball"]
                score = round((sorted_details[i]["mp_score"] + sorted_details[j]["mp_score"]) / 2, 1)
                gold_pairs.append({
                    "pair": f"{min(b1, b2):02d}-{max(b1, b2):02d}",
                    "affinity_score": score
                })
        gold_pairs = gold_pairs[:5]

        return {
            "module_code": "matrix_profile",
            "module_name": "13. 矩阵轮廓极速查重引擎 (V2.0 深度优化版)",
            "target_issue": target_issue,
            "latest_issue": latest_issue,
            "latest_numbers": latest_numbers,
            "total_historical_draws": self._total_draws,
            "multi_windows_used": MULTI_WINDOWS,
            "top3_gold": top3_gold,
            "top5_gold": top5_gold,
            "top12_elite": top12_elite,
            "gold_pairs": gold_pairs,
            "top_motifs": top_global_motifs,
            "ball_details": sorted_details
        }
