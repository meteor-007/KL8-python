# -*- coding: utf-8 -*-
"""
随机森林号码预测引擎 (Random Forest Number Engine)
==================================================
近 TRAIN_WINDOW 期表格特征 → 球级开出概率 → Top5 / Top12 / Kill20。
不做选2。

@author K8-Quant RF Team
@since 2026-09-13
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("k8quant.random_forest")

TOTAL_BALLS = 80
TRAIN_WINDOW = 100
RECENT_FREQ_WIN = 20
SWEET_CENTER = 10.0
SWEET_SIGMA = 4.2
CACHE_TAG_RF = "rf_num_v2_top3"

# 质数集合（1-80）
_PRIMES = {
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
    53, 59, 61, 67, 71, 73, 79,
}

FEATURE_NAMES = [
    "gap",
    "sweet_om",
    "freq_recent",
    "freq_8",
    "markov_self",
    "in_last",
    "zone",
    "road",
    "is_prime",
    "is_odd",
    "co_affinity",
    "ball_id",
]


def _zone(n: int) -> int:
    return (n - 1) // 10 + 1


def _road(n: int) -> int:
    return n % 3


class RandomForestEngine:
    """随机森林球概率 → 常规号码预测 (Top5/Top12/Kill20)"""

    def __init__(self, history_data: Optional[List[Dict[str, Any]]] = None):
        self.history_data = history_data or []
        self._chrono: List[Dict[str, Any]] = []
        self._matrix: Optional[np.ndarray] = None
        self._total = 0
        self._raw_loaded = 0
        if self.history_data:
            self._prepare()

    def _prepare(self) -> None:
        chrono = sorted(
            [h for h in self.history_data if len(h.get("numbers", [])) >= 10],
            key=lambda x: str(x.get("issue", x.get("period", ""))),
        )
        self._raw_loaded = len(chrono)
        if not chrono:
            self._chrono = []
            self._total = 0
            self._matrix = np.zeros((0, TOTAL_BALLS), dtype=np.float64)
            return
        if len(chrono) > TRAIN_WINDOW:
            chrono = chrono[-TRAIN_WINDOW:]
        self._chrono = chrono
        self._total = len(chrono)
        mat = np.zeros((self._total, TOTAL_BALLS), dtype=np.float64)
        for i, item in enumerate(self._chrono):
            for n in item.get("numbers", []):
                if 1 <= n <= TOTAL_BALLS:
                    mat[i, n - 1] = 1.0
        self._matrix = mat

    def _gaps_at(self, end_idx: int) -> np.ndarray:
        """截至 end_idx（含）的遗漏；end_idx 为矩阵行下标。"""
        gaps = np.full(TOTAL_BALLS, float(end_idx + 1), dtype=np.float64)
        mat = self._matrix[: end_idx + 1, :]
        for b in range(TOTAL_BALLS):
            hits = np.where(mat[:, b] > 0.5)[0]
            if hits.size:
                gaps[b] = float(end_idx - int(hits[-1]))
        return gaps

    def _features_at(self, end_idx: int) -> np.ndarray:
        """(80, F) 特征矩阵，基于 [0..end_idx] 可见历史。"""
        assert self._matrix is not None
        mat = self._matrix
        gaps = self._gaps_at(end_idx)
        sweet = np.exp(-((gaps - SWEET_CENTER) ** 2) / (2.0 * SWEET_SIGMA ** 2))
        sweet = np.where(gaps >= 16.0, sweet * 0.6, sweet)

        win_r = min(RECENT_FREQ_WIN, end_idx + 1)
        freq_r = np.sum(mat[end_idx + 1 - win_r : end_idx + 1, :], axis=0)
        win_8 = min(8, end_idx + 1)
        freq_8 = np.sum(mat[end_idx + 1 - win_8 : end_idx + 1, :], axis=0)

        # 马尔可夫自转移：上期开→本期再开
        markov = np.zeros(TOTAL_BALLS, dtype=np.float64)
        if end_idx >= 1:
            starts = np.sum(mat[:end_idx, :], axis=0)
            both = np.sum(mat[:end_idx, :] * mat[1 : end_idx + 1, :], axis=0)
            markov = both / np.maximum(starts, 1.0)

        last = mat[end_idx, :]
        in_last = last.copy()

        # 与上期开出码的共现亲和（近窗）
        co = np.dot(mat[: end_idx + 1, :].T, mat[: end_idx + 1, :])
        np.fill_diagonal(co, 0.0)
        co_aff = np.dot(last, co)

        feats = np.zeros((TOTAL_BALLS, len(FEATURE_NAMES)), dtype=np.float64)
        for b in range(TOTAL_BALLS):
            n = b + 1
            feats[b, 0] = gaps[b]
            feats[b, 1] = sweet[b]
            feats[b, 2] = freq_r[b]
            feats[b, 3] = freq_8[b]
            feats[b, 4] = markov[b]
            feats[b, 5] = in_last[b]
            feats[b, 6] = _zone(n)
            feats[b, 7] = _road(n)
            feats[b, 8] = 1.0 if n in _PRIMES else 0.0
            feats[b, 9] = 1.0 if n % 2 else 0.0
            feats[b, 10] = co_aff[b]
            feats[b, 11] = float(n)
        return feats

    def _build_train_xy(self) -> Tuple[np.ndarray, np.ndarray]:
        """用近窗内 t → t+1 构造训练样本。"""
        if self._matrix is None or self._total < 25:
            return np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,))
        xs: List[np.ndarray] = []
        ys: List[np.ndarray] = []
        # 至少留 12 期起步，后面每期做监督
        start = max(12, self._total - TRAIN_WINDOW)
        for t in range(start, self._total - 1):
            x = self._features_at(t)
            y = self._matrix[t + 1, :]
            xs.append(x)
            ys.append(y)
        if not xs:
            return np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,))
        X = np.vstack(xs)
        y = np.concatenate(ys)
        return X, y

    def _fit_predict_proba(self) -> Tuple[np.ndarray, Dict[str, float], Dict[str, Any]]:
        from sklearn.ensemble import RandomForestClassifier

        X, y = self._build_train_xy()
        meta: Dict[str, Any] = {
            "n_train_rows": int(X.shape[0]),
            "n_features": len(FEATURE_NAMES),
            "feature_names": FEATURE_NAMES,
        }
        if X.shape[0] < 200 or len(np.unique(y)) < 2:
            # 退化：用甜区+近频近似
            feats = self._features_at(self._total - 1)
            scores = 0.5 * feats[:, 1] + 0.3 * (feats[:, 2] / max(feats[:, 2].max(), 1.0)) + 0.2 * feats[:, 4]
            lo, hi = float(scores.min()), float(scores.max())
            if hi > lo:
                scores = (scores - lo) / (hi - lo)
            return scores, {}, {**meta, "fallback": True}

        clf = RandomForestClassifier(
            n_estimators=80,
            max_depth=8,
            min_samples_leaf=4,
            max_features="sqrt",
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )
        clf.fit(X, y)
        x_live = self._features_at(self._total - 1)
        proba = clf.predict_proba(x_live)
        # 取正类列
        if proba.shape[1] == 1:
            p_pos = proba[:, 0] * 0.0
        else:
            classes = list(clf.classes_)
            pos_idx = classes.index(1.0) if 1.0 in classes else classes.index(1)
            p_pos = proba[:, pos_idx]

        imp = clf.feature_importances_
        importance = {
            FEATURE_NAMES[i]: float(round(imp[i] * 100, 2))
            for i in np.argsort(-imp)[:8]
        }
        meta.update({
            "fallback": False,
            "n_estimators": 80,
            "max_depth": 8,
            "oob_not_used": True,
        })
        return p_pos.astype(np.float64), importance, meta

    @staticmethod
    def _minmax(arr: np.ndarray) -> np.ndarray:
        lo, hi = float(np.min(arr)), float(np.max(arr))
        if hi > lo:
            return (arr - lo) / (hi - lo)
        return np.zeros_like(arr)

    def run_prediction(self) -> Dict[str, Any]:
        if not self.history_data or self._total < 20:
            return {"error": "历史不足，无法训练随机森林"}

        latest = self.history_data[0]
        latest_issue = latest.get("issue", latest.get("period", ""))
        try:
            target_issue = str(int(latest_issue) + 1)
        except (TypeError, ValueError):
            target_issue = str(latest_issue)
        latest_numbers = latest.get("numbers", [])

        proba, importance, rf_meta = self._fit_predict_proba()
        gaps = self._gaps_at(self._total - 1)
        sweet = np.exp(-((gaps - SWEET_CENTER) ** 2) / (2.0 * SWEET_SIGMA ** 2))
        sweet = np.where(gaps >= 16.0, sweet * 0.6, sweet)
        # 综合分：RF 概率为主，甜区轻量辅助（防纯噪音排序）
        final_score = 0.85 * self._minmax(proba) + 0.15 * self._minmax(sweet)

        ball_details = []
        for i in range(TOTAL_BALLS):
            ball = i + 1
            ball_details.append({
                "ball": ball,
                "ball_str": f"{ball:02d}",
                "proba": float(round(proba[i] * 100, 2)),
                "final_score": float(round(final_score[i] * 100, 2)),
                "gap": int(gaps[i]),
                "is_recent_open": bool(ball in latest_numbers),
            })
        sorted_balls = sorted(ball_details, key=lambda x: x["final_score"], reverse=True)
        top3_gold = [x["ball"] for x in sorted_balls[:3]]
        top5_gold = top3_gold  # 兼容旧字段：主推改为最优3码
        top12_elite = top3_gold  # 兼容旧字段：不再维护 Top12

        return {
            "module_code": "random_forest",
            "module_name": "随机森林号码预测引擎 (V2.0)",
            "prediction_mode": "number_rank_rf",
            "target_issue": target_issue,
            "latest_issue": latest_issue,
            "latest_numbers": latest_numbers,
            "train_window": TRAIN_WINDOW,
            "history_used": self._total,
            "raw_draws_loaded": self._raw_loaded,
            "weighting": "equal",
            "total_historical_draws": self._total,
            "top3_gold": top3_gold,
            "top5_gold": top5_gold,
            "top12_elite": top12_elite,
            "gold_pairs": [],
            "ball_details": sorted_balls,
            "ball_proba_top20": [
                {"ball": x["ball"], "proba": x["proba"], "final_score": x["final_score"]}
                for x in sorted_balls[:20]
            ],
            "feature_importance": importance,
            "rf_meta": rf_meta,
        }
