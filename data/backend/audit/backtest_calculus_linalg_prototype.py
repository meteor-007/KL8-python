# -*- coding: utf-8 -*-
"""
Calculus & Linear Algebra (微积分 + 线性代数) 快乐8实验验证引擎原型
===================================================================
"""
import os
import sys
import numpy as np
from typing import List, Dict, Any, Tuple

_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = os.path.dirname(_DIR)
_ROOT_DIR = os.path.dirname(_PROJ_DIR)
for p in [_ROOT_DIR, _PROJ_DIR, _DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.utils.history_loader import load_history


class CalculusLinearAlgebraEngine:
    """微积分 + 线性代数 融合量化推演引擎原型"""

    def __init__(self, history: List[Dict[str, Any]]):
        self.history = history
        self.total_draws = len(history)

    def extract_one_hot_matrix(self, n_periods: int = 60, offset: int = 0) -> np.ndarray:
        sub_history = self.history[offset : offset + n_periods]
        mat = np.zeros((len(sub_history), 80), dtype=float)
        for t, draw in enumerate(sub_history):
            nums = draw.get("numbers", [])
            for num in nums:
                if 1 <= num <= 80:
                    mat[t, num - 1] = 1.0
        return mat[::-1]

    def compute_calculus_features(self, one_hot_mat: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        T, N = one_hot_mat.shape
        kernel = np.array([0.061, 0.242, 0.383, 0.242, 0.061])
        kernel = kernel / np.sum(kernel)

        smoothed = np.zeros_like(one_hot_mat)
        for n in range(N):
            smoothed[:, n] = np.convolve(one_hot_mat[:, n], kernel, mode="same")

        velocity = smoothed[-1, :] - smoothed[-2, :]
        acceleration = (smoothed[-1, :] - 2 * smoothed[-2, :] + smoothed[-3, :])
        decay_weights = np.exp(-0.05 * np.arange(T)[::-1])
        integral = np.sum(smoothed * decay_weights[:, np.newaxis], axis=0)

        return velocity, acceleration, integral

    def compute_linear_algebra_features(self, one_hot_mat: np.ndarray, k_components: int = 3) -> np.ndarray:
        T, N = one_hot_mat.shape
        time_weights = np.exp(np.linspace(-1.5, 0, T))
        weighted_mat = one_hot_mat * np.sqrt(time_weights)[:, np.newaxis]

        mean_vec = np.mean(weighted_mat, axis=0)
        centered = weighted_mat - mean_vec
        cov_mat = np.dot(centered.T, centered) / (T - 1)

        U, S, Vt = np.linalg.svd(cov_mat)
        top_bases = U[:, :k_components]
        singular_energies = S[:k_components] / np.sum(S)

        recent_activation = one_hot_mat[-1, :] * 0.6 + one_hot_mat[-2, :] * 0.4 - mean_vec
        projection_weights = np.dot(recent_activation, top_bases)

        spatial_gravity = np.zeros(N)
        for comp_idx in range(k_components):
            spatial_gravity += projection_weights[comp_idx] * top_bases[:, comp_idx] * singular_energies[comp_idx]

        return spatial_gravity

    def predict_target_period(self, offset: int = 0) -> Dict[str, Any]:
        one_hot = self.extract_one_hot_matrix(n_periods=60, offset=offset)
        velocity, acceleration, integral = self.compute_calculus_features(one_hot)
        spatial_gravity = self.compute_linear_algebra_features(one_hot, k_components=3)

        def norm_feat(f: np.ndarray) -> np.ndarray:
            f_min, f_max = np.min(f), np.max(f)
            if f_max - f_min < 1e-6:
                return np.zeros_like(f)
            return (f - f_min) / (f_max - f_min)

        v_norm = norm_feat(velocity)
        a_norm = norm_feat(acceleration)
        i_norm = norm_feat(integral)
        s_norm = norm_feat(spatial_gravity)

        latest_draw_vector = one_hot[-1, :]
        morphology_penalties = np.zeros(80)
        for num in range(1, 81):
            idx = num - 1
            if latest_draw_vector[idx] > 0.5:
                has_adj = False
                if idx > 0 and latest_draw_vector[idx - 1] > 0.5:
                    has_adj = True
                if idx < 79 and latest_draw_vector[idx + 1] > 0.5:
                    has_adj = True
                if has_adj:
                    morphology_penalties[idx] = 0.45
                else:
                    morphology_penalties[idx] = 0.15

        final_scores = (
            0.35 * s_norm
            + 0.25 * v_norm
            + 0.25 * i_norm
            + 0.15 * a_norm
            - morphology_penalties
        )

        ranked_indices = np.argsort(final_scores)[::-1]
        top5 = [int(idx + 1) for idx in ranked_indices[:5]]
        top12 = [int(idx + 1) for idx in ranked_indices[:12]]
        kill5 = [int(idx + 1) for idx in ranked_indices[-5:]]

        return {
            "top5": top5,
            "top12": top12,
            "kill5": kill5,
            "scores": final_scores
        }

    def run_walk_forward_backtest(self, n_tests: int = 50) -> Dict[str, Any]:
        if len(self.history) < n_tests + 65:
            n_tests = len(self.history) - 65

        hits_top5 = 0
        hits_top12 = 0
        kills_successful = 0
        records = []

        for offset in range(n_tests - 1, -1, -1):
            target_draw = self.history[offset]
            target_nums = set(target_draw.get("numbers", []))
            issue = str(target_draw.get("issue") or target_draw.get("period") or "")

            pred = self.predict_target_period(offset=offset + 1)
            t5 = pred["top5"]
            t12 = pred["top12"]
            k5 = pred["kill5"]

            h5 = len([x for x in t5 if x in target_nums])
            h12 = len([x for x in t12 if x in target_nums])
            k_hit = len([x for x in k5 if x in target_nums])
            k_avoid = 5 - k_hit

            hits_top5 += h5
            hits_top12 += h12
            kills_successful += k_avoid

            records.append({
                "issue": issue,
                "hit5": h5,
                "hit12": h12,
                "kill_avoid": k_avoid
            })

        avg_h5 = hits_top5 / float(n_tests)
        avg_h12 = hits_top12 / float(n_tests)
        rate5 = (avg_h5 / 5.0) * 100
        rate12 = (avg_h12 / 12.0) * 100
        lift5 = (avg_h5 / 5.0) / 0.25
        lift12 = (avg_h12 / 12.0) / 0.25
        kill_avoid_rate = (kills_successful / float(n_tests * 5)) * 100

        return {
            "n_tests": n_tests,
            "avg_h5": round(avg_h5, 2),
            "avg_h12": round(avg_h12, 2),
            "rate5_pct": round(rate5, 2),
            "rate12_pct": round(rate12, 2),
            "lift5": round(lift5, 2),
            "lift12": round(lift12, 2),
            "kill_avoid_rate_pct": round(kill_avoid_rate, 2),
            "records": records
        }


if __name__ == "__main__":
    h = load_history()
    engine = CalculusLinearAlgebraEngine(h)
    print(f"载入全量开奖数据 {len(h)} 期，开始运行微积分+线性代数原型回测...")
    for n in [30, 50, 100]:
        res = engine.run_walk_forward_backtest(n_tests=n)
        print("\n" + "=" * 60)
        print(f"  📊 微积分 + 线性代数 (时空双轮模型) 近 {n} 期样本外实测战果")
        print("=" * 60)
        print(f"  ■ Top 5 均中: {res['avg_h5']} 个 / 5码 | 命中率: {res['rate5_pct']}% | 提升度 Lift: {res['lift5']}x")
        print(f"  ■ Top 12 均中: {res['avg_h12']} 个 / 12码 | 命中率: {res['rate12_pct']}% | 提升度 Lift: {res['lift12']}x")
        print(f"  ■ 杀号防守回避率: {res['kill_avoid_rate_pct']}% (防守基线 75.0%)")
        print("=" * 60)
