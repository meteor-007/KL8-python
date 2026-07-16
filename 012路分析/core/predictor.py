from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from config.model_config import ModelConfig
from core.data_loader import KL8Draw
from core.ml_predictor import MLRoadPredictor, fix_sum20
from core.transition import TransitionModel

Road = Tuple[int, int, int]


def _entropy_confidence(dist: Dict[Road, float]) -> float:
    if not dist:
        return 0.0
    probs = list(dist.values())
    n = len(probs)
    if n <= 1:
        return 1.0
    ent = -sum(p * math.log(p + 1e-12) for p in probs)
    max_ent = math.log(n)
    return float(max(0.0, min(1.0, 1.0 - ent / max_ent)))


class RoadPredictor:
    """马尔可夫 + 回归 + ML 融合预测下一期分路比。"""

    def __init__(self, draws: Sequence[KL8Draw], cfg: ModelConfig):
        self.draws = list(draws)
        self.cfg = cfg
        self.transition = TransitionModel(self.draws)
        self.ml = MLRoadPredictor(
            lookback_k=cfg.lookback_k,
            train_periods=cfg.ml_train_periods,
            expected=cfg.expected_road,
            random_state=cfg.random_state,
        )
        self._ml_ok = False
        if cfg.use_ml and len(self.draws) >= cfg.lookback_k + 20:
            self._ml_ok = self.ml.fit(self.draws)

    def predict(self) -> dict:
        if not self.draws:
            best = fix_sum20(*self.cfg.expected_road)
            return {
                "best": best,
                "top3": [best],
                "confidence": 0.0,
                "ml_used": False,
                "components": {},
            }

        last = self.draws[-1].road
        expected = self.cfg.expected_road
        markov_dist = self.transition.next_distribution(last)

        # Markov vector: probability-weighted average of top states
        top_states = sorted(markov_dist.items(), key=lambda x: -x[1])[:8]
        weight_sum = sum(p for _, p in top_states) or 1.0
        m = [0.0, 0.0, 0.0]
        for state, p in top_states:
            for i in range(3):
                m[i] += state[i] * (p / weight_sum)

        # Regression toward expected
        regress = [
            0.5 * last[i] + 0.5 * expected[i] for i in range(3)
        ]

        w_m, w_r, w_ml = self.cfg.w_markov, self.cfg.w_regress, self.cfg.w_ml
        ml_vec: Optional[List[float]] = None
        ml_used = False
        if self.cfg.use_ml and self._ml_ok:
            ml_ratio = self.ml.predict_ratio(self.draws)
            if ml_ratio is not None:
                ml_vec = list(ml_ratio)
                ml_used = True

        if not ml_used:
            total = w_m + w_r
            w_m, w_r, w_ml = w_m / total, w_r / total, 0.0
            ml_vec = [0.0, 0.0, 0.0]

        blend = [
            w_m * m[i] + w_r * regress[i] + w_ml * ml_vec[i] for i in range(3)
        ]
        best = fix_sum20(blend[0], blend[1], blend[2])

        # Top3 candidates
        candidates: Dict[Road, float] = {}
        for state, p in top_states[:5]:
            candidates[state] = candidates.get(state, 0.0) + p
        candidates[best] = candidates.get(best, 0.0) + 1.0
        # neighbors of blend
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                r0 = best[0] + di
                r1 = best[1] + dj
                r2 = 20 - r0 - r1
                if r0 < 0 or r1 < 0 or r2 < 0:
                    continue
                cand = (r0, r1, r2)
                # score by L1 closeness to blend
                dist = sum(abs(cand[i] - blend[i]) for i in range(3))
                candidates[cand] = candidates.get(cand, 0.0) + 1.0 / (1.0 + dist)

        top3 = [s for s, _ in sorted(candidates.items(), key=lambda x: -x[1])[:3]]
        if len(top3) < 3:
            for s, _ in top_states:
                if s not in top3:
                    top3.append(s)
                if len(top3) >= 3:
                    break
        while len(top3) < 3:
            top3.append(best)

        conf = _entropy_confidence(markov_dist)
        if ml_used:
            conf = min(1.0, conf * 0.7 + 0.3)

        return {
            "best": best,
            "top3": top3[:3],
            "confidence": conf,
            "ml_used": ml_used,
            "components": {
                "markov": tuple(m),
                "regress": tuple(regress),
                "ml": tuple(ml_vec) if ml_used else None,
                "blend": tuple(blend),
            },
            "number_proba": None,
        }
