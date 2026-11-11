# -*- coding: utf-8 -*-
import os, sys
import numpy as np

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
from backend.audit.backtest_calculus_linalg_prototype import CalculusLinearAlgebraEngine

class CalculusAblationEngine(CalculusLinearAlgebraEngine):
    def predict_target_period_ablation(self, offset: int = 0, mode: str = "default") -> dict:
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

        if mode == "default":
            # 带 30期 衰减积分
            final_scores = 0.35 * s_norm + 0.25 * v_norm + 0.25 * i_norm + 0.15 * a_norm - morphology_penalties
        elif mode == "no_integral":
            # 彻底去掉衰减积分：纯看 冲劲 + 拐点 + 空间协同 (更敏捷、抓黑马暴发户)
            final_scores = 0.45 * s_norm + 0.35 * v_norm + 0.20 * a_norm - morphology_penalties
        elif mode == "short_momentum":
            # 短线突击积分 (只看近5期)
            short_int = np.sum(one_hot[-5:, :], axis=0)
            si_norm = norm_feat(short_int)
            final_scores = 0.40 * s_norm + 0.30 * v_norm + 0.15 * si_norm + 0.15 * a_norm - morphology_penalties

        ranked_indices = np.argsort(final_scores)[::-1]
        top5 = [int(idx + 1) for idx in ranked_indices[:5]]
        top12 = [int(idx + 1) for idx in ranked_indices[:12]]
        kill5 = [int(idx + 1) for idx in ranked_indices[-5:]]

        return {"top5": top5, "top12": top12, "kill5": kill5}

    def run_ablation_test(self, n_tests: int = 50, mode: str = "default") -> dict:
        hits_top5 = 0
        hits_top12 = 0
        kills_successful = 0
        for offset in range(n_tests - 1, -1, -1):
            target_draw = self.history[offset]
            target_nums = set(target_draw.get("numbers", []))
            pred = self.predict_target_period_ablation(offset=offset + 1, mode=mode)
            h5 = len([x for x in pred["top5"] if x in target_nums])
            h12 = len([x for x in pred["top12"] if x in target_nums])
            k_hit = len([x for x in pred["kill5"] if x in target_nums])
            hits_top5 += h5
            hits_top12 += h12
            kills_successful += (5 - k_hit)
        return {
            "mode": mode,
            "avg_h5": round(hits_top5 / float(n_tests), 2),
            "lift5": round((hits_top5 / float(n_tests) / 5.0) / 0.25, 2),
            "avg_h12": round(hits_top12 / float(n_tests), 2),
            "lift12": round((hits_top12 / float(n_tests) / 12.0) / 0.25, 2),
            "kill_rate": round((kills_successful / float(n_tests * 5)) * 100, 1)
        }

if __name__ == "__main__":
    h = load_history()
    engine = CalculusAblationEngine(h)
    print("=" * 70)
    print(f"  🧪 衰减积分 I(t) 移除/消融前后 50期与100期 样本外实测对账")
    print("=" * 70)
    for n in [50, 100]:
        print(f"\n--- 近 {n} 期实测对比 ---")
        for m in ["default", "no_integral", "short_momentum"]:
            res = engine.run_ablation_test(n_tests=n, mode=m)
            name_map = {
                "default": "方案A (保留30期衰减积分/查三代)",
                "no_integral": "方案B (彻底去掉积分/纯抓冲劲与黑马)",
                "short_momentum": "方案C (仅保留近5期超短线突击面积)"
            }
            print(f"  [{name_map[m]}]: Top5均中={res['avg_h5']} (Lift {res['lift5']}x) | Top12均中={res['avg_h12']} (Lift {res['lift12']}x) | 杀号回避率={res['kill_rate']}%")
