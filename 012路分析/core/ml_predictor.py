from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np

from core.data_loader import KL8Draw

Road = Tuple[int, int, int]


def fix_sum20(r0: float, r1: float, r2: float) -> Road:
    vals = [max(0, int(round(r0))), max(0, int(round(r1))), max(0, int(round(r2)))]
    while sum(vals) > 20:
        i = max(range(3), key=lambda k: vals[k])
        vals[i] -= 1
    while sum(vals) < 20:
        i = min(range(3), key=lambda k: vals[k])
        vals[i] += 1
    return vals[0], vals[1], vals[2]


def _streak_at_end(values: Sequence[float], expected: float) -> float:
    if not values:
        return 0.0
    signs = []
    for v in values:
        if v > expected:
            signs.append(1)
        elif v < expected:
            signs.append(-1)
        else:
            signs.append(0)
    i = len(signs) - 1
    while i >= 0 and signs[i] == 0:
        i -= 1
    if i < 0:
        return 0.0
    direction = signs[i]
    length = 1
    i -= 1
    while i >= 0 and signs[i] == direction:
        length += 1
        i -= 1
    return float(direction * length)


class MLRoadPredictor:
    """RandomForest 多输出回归预测下一期分路比；失败时返回 None。"""

    def __init__(
        self,
        lookback_k: int = 10,
        train_periods: int = 500,
        expected: Road = (6.5, 6.75, 6.75),
        random_state: int = 42,
    ):
        self.lookback_k = lookback_k
        self.train_periods = train_periods
        self.expected = expected
        self.random_state = random_state
        self._model = None

    def _features_at(self, roads: Sequence[Road], end_idx: int) -> Optional[np.ndarray]:
        k = self.lookback_k
        if end_idx < k:
            return None
        window = roads[end_idx - k : end_idx]
        flat = [c for r in window for c in r]
        means = [sum(r[i] for r in window) / k for i in range(3)]
        devs = [means[i] - self.expected[i] for i in range(3)]
        streaks = [
            _streak_at_end([r[i] for r in window], self.expected[i]) for i in range(3)
        ]
        return np.array(flat + means + devs + streaks, dtype=np.float64)

    def fit(self, draws: Sequence[KL8Draw]) -> bool:
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.multioutput import MultiOutputRegressor
        except ImportError:
            self._model = None
            return False

        roads = [d.road for d in draws]
        use = roads[-self.train_periods :] if len(roads) > self.train_periods else roads
        X_list: List[np.ndarray] = []
        y_list: List[Road] = []
        for i in range(self.lookback_k, len(use)):
            feat = self._features_at(use, i)
            if feat is None:
                continue
            X_list.append(feat)
            y_list.append(use[i])
        if len(X_list) < 20:
            self._model = None
            return False
        try:
            X = np.vstack(X_list)
            y = np.array(y_list, dtype=np.float64)
            base = RandomForestRegressor(
                n_estimators=80,
                max_depth=8,
                random_state=self.random_state,
                n_jobs=-1,
            )
            model = MultiOutputRegressor(base)
            model.fit(X, y)
            self._model = model
            return True
        except Exception:
            self._model = None
            return False

    def predict_ratio(self, draws: Sequence[KL8Draw]) -> Optional[Road]:
        if self._model is None:
            return None
        roads = [d.road for d in draws]
        feat = self._features_at(roads, len(roads))
        if feat is None:
            return None
        try:
            pred = self._model.predict(feat.reshape(1, -1))[0]
            return fix_sum20(float(pred[0]), float(pred[1]), float(pred[2]))
        except Exception:
            return None
