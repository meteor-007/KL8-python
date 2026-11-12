# -*- coding: utf-8 -*-
"""
线性代数空间投影量化分析核心计算引擎 (Linear Algebra Engine V3.0)
========================================================================
【业务背景与架构定位】:
K8-Quant 系统第 10 大精锐独立量化推演子系统。

V3.1 口径（2026-09-13）:
1. 统一训练窗 TRAIN_WINDOW=100：四路信号只吃近 100 期，等权，不再做半衰期衰减；
2. 等权 SVD + Gavish-Donoho 自适应截断；
3. 主产品改为「两组互不重叠最优选2」：共现 + 融合球分能量 + 对称马尔可夫打分后贪心取对。

@author K8-Quant Linear Algebra Team
@since 2026-09-11
"""
import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

logger = logging.getLogger("k8quant.linear_algebra")

TOTAL_BALLS = 80
TRAIN_WINDOW = 100
DIRICHLET_ALPHA = 0.05
DEFAULT_WINDOW_SIZE = 5
DEFAULT_TOP_MATCHES = 5

# 融合权重 (等权SVD能量, 平滑马尔可夫, 余弦镜像投影, 图共现亲和)
WEIGHT_PCA = 0.30
WEIGHT_MARKOV = 0.30
WEIGHT_COSINE = 0.25
WEIGHT_COOCCURRENCE = 0.15

# 选2：冷热对冲（对齐定金选2实测口径）
PICK2_TOP_N = 2
SWEET_GAP_LO = 7
SWEET_GAP_HI = 13
SWEET_CENTER = 10.0
SWEET_SIGMA = 4.2
RECENT_FREQ_WIN = 20
CACHE_TAG_PICK2 = "p2h_t3"  # 复盘缓存后缀：主推 Top3


class LinearAlgebraEngine:
    """线性代数空间投影推演计算引擎 (近100期等权版)"""

    def __init__(self, history_data: Optional[List[Dict[str, Any]]] = None):
        self.history_data = history_data or []
        self._chrono_history: List[Dict[str, Any]] = []
        self._matrix_01: Optional[np.ndarray] = None
        self._total_draws: int = 0
        self._raw_draws_loaded: int = 0

        if self.history_data:
            self._prepare_matrix()

    def _prepare_matrix(self) -> None:
        """步骤 1: 历史 → 时间正序 0-1 矩阵，再截取近 TRAIN_WINDOW 期。"""
        chrono = sorted(
            [item for item in self.history_data if len(item.get("numbers", [])) >= 10],
            key=lambda x: str(x.get("issue", x.get("period", "")))
        )
        self._raw_draws_loaded = len(chrono)

        if self._raw_draws_loaded == 0:
            self._chrono_history = []
            self._total_draws = 0
            self._matrix_01 = np.zeros((0, TOTAL_BALLS), dtype=np.float64)
            return

        if len(chrono) > TRAIN_WINDOW:
            chrono = chrono[-TRAIN_WINDOW:]

        self._chrono_history = chrono
        self._total_draws = len(chrono)

        mat = np.zeros((self._total_draws, TOTAL_BALLS), dtype=np.float64)
        for row_idx, item in enumerate(self._chrono_history):
            for num in item.get("numbers", []):
                if 1 <= num <= TOTAL_BALLS:
                    mat[row_idx, num - 1] = 1.0
        self._matrix_01 = mat

    def compute_pca_subspace_projection(self) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        步骤 2: 近窗等权中心化 + 自适应奇异值截断 SVD。
        不做时间衰减加权；训练矩阵已是 ≤100 期。
        """
        if self._matrix_01 is None or self._total_draws < 20:
            return np.ones(TOTAL_BALLS) / TOTAL_BALLS, {"variance_ratio": []}

        train_mat = self._matrix_01  # (n, 80), n <= TRAIN_WINDOW
        n_rows = train_mat.shape[0]

        mean_vec = np.mean(train_mat, axis=0)
        centered = train_mat - mean_vec

        try:
            _u, s, vt = np.linalg.svd(centered, full_matrices=False)
            total_var = np.sum(s ** 2)
            explained_var = (s ** 2) / (total_var + 1e-9)

            beta = TOTAL_BALLS / max(n_rows, 1)
            omega = 0.56 * (beta ** 3) - 0.95 * (beta ** 2) + 1.82 * beta + 1.43
            median_s = np.median(s)
            threshold = omega * median_s
            adaptive_k = int(max(4, min(16, np.sum(s > threshold))))

            v_k = vt[:adaptive_k, :].T  # (80, k)

            latest_draw_vec = train_mat[-1, :] - mean_vec
            subspace_coords = np.dot(latest_draw_vec, v_k)
            reconstructed = np.dot(subspace_coords, v_k.T) + mean_vec

            min_val, max_val = np.min(reconstructed), np.max(reconstructed)
            if max_val > min_val:
                norm_pca = (reconstructed - min_val) / (max_val - min_val)
            else:
                norm_pca = np.ones(TOTAL_BALLS) * 0.5

            pca_meta = {
                "top_explained_variance_ratio": [float(round(r * 100, 2)) for r in explained_var[:adaptive_k]],
                "cumulative_variance_ratio": float(round(np.sum(explained_var[:adaptive_k]) * 100, 2)),
                "n_components_used": int(adaptive_k),
                "gavish_donoho_threshold": float(round(threshold, 4)),
                "train_window": int(TRAIN_WINDOW),
                "history_used": int(n_rows),
                "equal_weight": True,
            }
            return norm_pca, pca_meta

        except Exception as e:
            logger.warning("等权 PCA SVD 计算异常: %s", e)
            return np.ones(TOTAL_BALLS) * 0.5, {"variance_ratio": [], "train_window": TRAIN_WINDOW}

    def compute_dirichlet_markov_transition(self) -> Tuple[np.ndarray, np.ndarray]:
        """Dirichlet 平滑马尔可夫（在近窗矩阵上）。"""
        if self._matrix_01 is None or self._total_draws < 2:
            return np.ones(TOTAL_BALLS) * 0.5, np.zeros((TOTAL_BALLS, TOTAL_BALLS))

        x_prev = self._matrix_01[:-1, :]
        x_next = self._matrix_01[1:, :]

        counts = np.dot(x_prev.T, x_next)
        row_totals = np.sum(x_prev, axis=0, keepdims=True).T

        smooth_transition = (counts + DIRICHLET_ALPHA) / (row_totals + TOTAL_BALLS * DIRICHLET_ALPHA)
        smooth_transition_2 = np.dot(smooth_transition, smooth_transition)

        latest_vec = self._matrix_01[-1, :]
        markov_1 = np.dot(latest_vec, smooth_transition)
        markov_2 = np.dot(latest_vec, smooth_transition_2)
        raw_markov = 0.70 * markov_1 + 0.30 * markov_2

        min_v, max_v = np.min(raw_markov), np.max(raw_markov)
        if max_v > min_v:
            norm_markov = (raw_markov - min_v) / (max_v - min_v)
        else:
            norm_markov = np.ones(TOTAL_BALLS) * 0.5

        return norm_markov, smooth_transition

    def compute_cosine_historical_reflection(
        self, window_size: int = DEFAULT_WINDOW_SIZE, top_k: int = DEFAULT_TOP_MATCHES
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """近窗内滑动余弦镜像投影（候选只在 TRAIN_WINDOW 内）。"""
        if self._matrix_01 is None or self._total_draws < (window_size + 5):
            return np.ones(TOTAL_BALLS) * 0.5, []

        target_window = self._matrix_01[-window_size:, :].flatten()
        target_norm = np.linalg.norm(target_window) + 1e-9

        max_start = self._total_draws - window_size - 1
        similarities = []

        for start_idx in range(max_start):
            end_idx = start_idx + window_size
            hist_window = self._matrix_01[start_idx:end_idx, :].flatten()
            hist_norm = np.linalg.norm(hist_window) + 1e-9
            cos_sim = float(np.dot(target_window, hist_window) / (target_norm * hist_norm))

            next_issue_data = self._chrono_history[end_idx]
            match_start_issue = self._chrono_history[start_idx].get("issue", self._chrono_history[start_idx].get("period", ""))
            match_end_issue = self._chrono_history[end_idx - 1].get("issue", self._chrono_history[end_idx - 1].get("period", ""))

            similarities.append({
                "start_idx": start_idx,
                "end_idx": end_idx,
                "period_range": f"{match_start_issue} ~ {match_end_issue} 期",
                "target_issue": next_issue_data.get("issue", next_issue_data.get("period", "")),
                "target_date": next_issue_data.get("date", ""),
                "next_numbers": next_issue_data.get("numbers", []),
                "similarity": cos_sim,
                "similarity_pct": round(cos_sim * 100, 2)
            })

        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        top_matches = similarities[:top_k]

        if not top_matches:
            return np.ones(TOTAL_BALLS) * 0.5, []

        sim_scores = np.array([m["similarity"] for m in top_matches])
        exp_weights = np.exp((sim_scores - np.max(sim_scores)) * 6.0)
        softmax_weights = exp_weights / (np.sum(exp_weights) + 1e-9)

        projected_vector = np.zeros(TOTAL_BALLS, dtype=np.float64)
        for idx, match in enumerate(top_matches):
            weight = softmax_weights[idx]
            match["ensemble_weight"] = float(round(weight * 100, 2))
            for num in match["next_numbers"]:
                if 1 <= num <= TOTAL_BALLS:
                    projected_vector[num - 1] += weight

        min_p, max_p = np.min(projected_vector), np.max(projected_vector)
        if max_p > min_p:
            norm_cosine = (projected_vector - min_p) / (max_p - min_p)
        else:
            norm_cosine = np.ones(TOTAL_BALLS) * 0.5

        return norm_cosine, top_matches

    def compute_graph_laplacian_cooccurrence(self) -> Tuple[np.ndarray, np.ndarray]:
        """近窗共现矩阵 + 度中心性球分（供融合用，不再用上期回看亲和做选2）。"""
        if self._matrix_01 is None or self._total_draws < 20:
            return np.ones(TOTAL_BALLS) * 0.5, np.zeros((TOTAL_BALLS, TOTAL_BALLS))

        cooccur_matrix = np.dot(self._matrix_01.T, self._matrix_01)
        np.fill_diagonal(cooccur_matrix, 0.0)

        degree = np.sum(cooccur_matrix, axis=1)
        min_a, max_a = np.min(degree), np.max(degree)
        if max_a > min_a:
            norm_cooccur = (degree - min_a) / (max_a - min_a)
        else:
            norm_cooccur = np.ones(TOTAL_BALLS) * 0.5

        return norm_cooccur, cooccur_matrix

    @staticmethod
    def _minmax(arr: np.ndarray) -> np.ndarray:
        lo, hi = float(np.min(arr)), float(np.max(arr))
        if hi > lo:
            return (arr - lo) / (hi - lo)
        return np.zeros_like(arr)

    def compute_omission_and_recent(self) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """近窗遗漏期数、近 RECENT_FREQ_WIN 频次、上期开出列表。"""
        gaps = np.full(TOTAL_BALLS, float(self._total_draws), dtype=np.float64)
        recent_freq = np.zeros(TOTAL_BALLS, dtype=np.float64)
        last_draw: List[int] = []

        if self._matrix_01 is None or self._total_draws < 1:
            return gaps, recent_freq, last_draw

        mat = self._matrix_01
        n = self._total_draws
        last_row = mat[-1, :]
        last_draw = [i + 1 for i in range(TOTAL_BALLS) if last_row[i] > 0.5]

        # 遗漏：距最近一次开出的行距
        for b in range(TOTAL_BALLS):
            hits = np.where(mat[:, b] > 0.5)[0]
            if hits.size == 0:
                gaps[b] = float(n)
            else:
                gaps[b] = float(n - 1 - int(hits[-1]))

        win = min(RECENT_FREQ_WIN, n)
        recent_freq = np.sum(mat[-win:, :], axis=0)
        return gaps, recent_freq, last_draw

    def select_optimal_pick2_pairs(
        self,
        final_scores: np.ndarray,
        markov_transition: np.ndarray,
        cooccur_matrix: np.ndarray,
        top_n: int = PICK2_TOP_N,
    ) -> List[Dict[str, Any]]:
        """
        冷热对冲两组选2（借鉴定金选2实测结构）：
        - 动能热胆：上期开出中近窗活跃度适中、融合分最高
        - 甜区温号：遗漏 7~13 期（高斯中心 10）中融合分最高
        - 第1组：热胆 + 最佳甜区温号
        - 第2组：次席热胆 + 次席甜区（与第1组互不重叠）
        共现 / 马尔可夫仅作轻量加分。
        """
        gaps, recent_freq, last_draw = self.compute_omission_and_recent()
        if self._total_draws < 20:
            return []

        # 高斯甜区分（极冷 >=16 打折）
        sweet_raw = np.exp(-((gaps - SWEET_CENTER) ** 2) / (2.0 * SWEET_SIGMA ** 2))
        sweet_raw = np.where(gaps >= 16.0, sweet_raw * 0.6, sweet_raw)
        sweet_n = self._minmax(sweet_raw)
        fuse_n = self._minmax(np.asarray(final_scores, dtype=np.float64))
        # 球综合分：融合能量 + 甜区
        ball_score = 0.55 * fuse_n + 0.45 * sweet_n

        warm = [n for n in range(1, TOTAL_BALLS + 1) if SWEET_GAP_LO <= gaps[n - 1] <= SWEET_GAP_HI]
        if len(warm) < 3:
            warm = sorted(range(1, TOTAL_BALLS + 1), key=lambda n: abs(gaps[n - 1] - SWEET_CENTER))[:12]

        # 动能热胆池
        active = [n for n in last_draw if 2 <= recent_freq[n - 1] <= 5]
        pool_hot = active or list(last_draw) or list(range(1, TOTAL_BALLS + 1))

        # 甜区金胆（兜底用）
        golden = max(warm, key=lambda n: float(ball_score[n - 1]))

        def co_cnt(a: int, b: int) -> int:
            if cooccur_matrix is None or cooccur_matrix.size == 0:
                return 0
            i, j = a - 1, b - 1
            return int(cooccur_matrix[i, j])

        def mk_sym(a: int, b: int) -> float:
            if markov_transition is None or markov_transition.size == 0:
                return 0.0
            i, j = a - 1, b - 1
            return float(markov_transition[i, j] + markov_transition[j, i])

        def pair_item(a: int, b: int, desc: str, rank: int) -> Dict[str, Any]:
            aa, bb = (a, b) if a < b else (b, a)
            energy = float(np.sqrt(max(fuse_n[aa - 1], 0.0) * max(fuse_n[bb - 1], 0.0)))
            base = 0.5 * (float(ball_score[aa - 1]) + float(ball_score[bb - 1]))
            bonus = 0.15 * min(co_cnt(aa, bb) / 20.0, 1.0) + 0.10 * min(mk_sym(aa, bb) * 40.0, 1.0)
            hedge = 0.0
            ga, gb = gaps[aa - 1], gaps[bb - 1]
            if (ga <= 1 and SWEET_GAP_LO <= gb <= SWEET_GAP_HI) or (gb <= 1 and SWEET_GAP_LO <= ga <= SWEET_GAP_HI):
                hedge = 0.12
            score = base + bonus + hedge
            return {
                "pair": f"{aa:02d}-{bb:02d}",
                "balls": [aa, bb],
                "cooccur_count": co_cnt(aa, bb),
                "pair_score": round(score * 100, 1),
                "affinity_score": round(score * 100, 1),
                "energy_score": round(energy * 100, 1),
                "markov_score": round(min(mk_sym(aa, bb) * 40.0, 1.0) * 100, 1),
                "co_score": round(min(co_cnt(aa, bb) / 20.0, 1.0) * 100, 1),
                "gap_a": int(gaps[aa - 1]),
                "gap_b": int(gaps[bb - 1]),
                "desc": desc,
                "rank": rank,
            }

        picks: List[Dict[str, Any]] = []
        used: set = set()

        def try_add(a: int, b: int, desc: str) -> bool:
            if a == b or a in used or b in used:
                return False
            picks.append(pair_item(a, b, desc, len(picks) + 1))
            used.add(a)
            used.add(b)
            return True

        # 热胆池 / 甜区池按球分排序
        hot_ranked = sorted(list(dict.fromkeys(pool_hot)), key=lambda n: float(ball_score[n - 1]), reverse=True)
        warm_ranked = sorted([c for c in warm], key=lambda c: float(ball_score[c - 1]), reverse=True)

        # 两组均走「热×甜」冷热对冲，优先互不重叠
        for hi, hot_ball in enumerate(hot_ranked):
            if len(picks) >= top_n:
                break
            for warm_ball in warm_ranked:
                if warm_ball == hot_ball:
                    continue
                label = "动能热胆 + 黄金甜区温号（冷热对冲主推）" if not picks else "次席热胆 + 次席甜区（冷热对冲）"
                if try_add(hot_ball, warm_ball, label):
                    break

        # 仍不足：甜区金胆 + 剩余热/甜
        if len(picks) < top_n and golden not in used:
            for partner, desc in (
                [(h, "甜区金胆 + 上期热码") for h in hot_ranked]
                + [(c, "甜区金胆 + 次席甜区") for c in warm_ranked]
                + [(int(n) + 1, "甜区金胆 + 融合高分") for n in np.argsort(-ball_score)]
            ):
                if try_add(golden, partner, desc):
                    break

        # 兜底：融合贪心
        if len(picks) < top_n:
            order = list(np.argsort(-ball_score))
            for i in order:
                if len(picks) >= top_n:
                    break
                a = int(i) + 1
                if a in used:
                    continue
                for j in order:
                    b = int(j) + 1
                    if b == a or b in used:
                        continue
                    try_add(a, b, "融合高分兜底配对")
                    break

        return picks[:top_n]

    def run_prediction(self) -> Dict[str, Any]:
        """全链路近窗线性代数推演；主产品为两组冷热对冲选2。"""
        if not self.history_data:
            return {"error": "无历史开奖数据"}

        latest_issue = self.history_data[0].get("issue", self.history_data[0].get("period", ""))
        try:
            target_issue = str(int(latest_issue) + 1)
        except (TypeError, ValueError):
            target_issue = str(latest_issue)
        latest_numbers = self.history_data[0].get("numbers", [])

        pca_scores, pca_meta = self.compute_pca_subspace_projection()
        markov_scores, markov_transition = self.compute_dirichlet_markov_transition()
        cosine_scores, top_matches = self.compute_cosine_historical_reflection()
        cooccur_scores, cooccur_matrix = self.compute_graph_laplacian_cooccurrence()

        final_scores = (
            WEIGHT_PCA * pca_scores +
            WEIGHT_MARKOV * markov_scores +
            WEIGHT_COSINE * cosine_scores +
            WEIGHT_COOCCURRENCE * cooccur_scores
        )

        gold_pairs = self.select_optimal_pick2_pairs(
            final_scores=final_scores,
            markov_transition=markov_transition,
            cooccur_matrix=cooccur_matrix,
            top_n=PICK2_TOP_N,
        )

        ball_details = []
        for i in range(TOTAL_BALLS):
            ball = i + 1
            ball_details.append({
                "ball": ball,
                "ball_str": f"{ball:02d}",
                "final_score": float(round(final_scores[i] * 100, 2)),
                "pca_score": float(round(pca_scores[i] * 100, 2)),
                "markov_score": float(round(markov_scores[i] * 100, 2)),
                "cosine_score": float(round(cosine_scores[i] * 100, 2)),
                "cooccur_score": float(round(cooccur_scores[i] * 100, 2)),
                "is_recent_open": bool(ball in latest_numbers)
            })

        sorted_by_score = sorted(ball_details, key=lambda x: x["final_score"], reverse=True)
        top3_gold = [item["ball"] for item in sorted_by_score[:3]]
        top5_gold = top3_gold  # 兼容旧字段：主推改为最优3码
        top12_elite = top3_gold  # 兼容旧字段：不再维护 Top12

        for match in top_matches:
            overlap = sorted(list(set(match["next_numbers"]) & set(top12_elite)))
            match["overlap_with_top12"] = overlap
            match["overlap_count"] = len(overlap)

        return {
            "module_code": "linear_algebra",
            "module_name": "10. 线性代数空间投影量化引擎 (V3.2 冷热对冲选2)",
            "prediction_mode": "dual_pick2_hedge",
            "target_issue": target_issue,
            "latest_issue": latest_issue,
            "latest_numbers": latest_numbers,
            "train_window": TRAIN_WINDOW,
            "history_used": self._total_draws,
            "raw_draws_loaded": self._raw_draws_loaded,
            "weighting": "equal",
            "total_historical_draws": self._total_draws,
            "top3_gold": top3_gold,
            "top5_gold": top5_gold,
            "top12_elite": top12_elite,
            "gold_pairs": gold_pairs,
            "top_historical_matches": top_matches,
            "pca_meta": pca_meta,
            "ball_details": sorted_by_score,
            "matrix_weights": {
                "equal_weight_svd": WEIGHT_PCA,
                "dirichlet_markov": WEIGHT_MARKOV,
                "cosine_mirror": WEIGHT_COSINE,
                "laplacian_cooccurrence": WEIGHT_COOCCURRENCE
            },
            "pair_strategy": {
                "mode": "hot_sweet_hedge",
                "sweet_gap": [SWEET_GAP_LO, SWEET_GAP_HI],
                "sweet_center": SWEET_CENTER,
            },
        }
