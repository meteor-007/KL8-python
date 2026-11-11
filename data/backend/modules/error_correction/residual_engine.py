# -*- coding: utf-8 -*-
"""
残差改错预测引擎 (Residual Error-Correction Engine)
==================================================
【业务背景与架构定位】:
本模块属于高精智能战区，基于 GBDT / LightGBM 梯度提升算法构建“残差改错裁判”。
其核心逻辑不是从零猜号码，而是充当“第二棒改错接力队”：
第一棒由基准统计模型给出底仓先验估计 P_base，第二棒由 LightGBM 残差改错树死磕历史错题，
学习打脸误差残差 R = Y_实际 - P_base，从而在实战中精准“拔除虚火诱多雷号（假阳性）”并“提拔极限回补黑马（假阴性）”。

【技术指标与输出契约】:
- 输入: 近 TRAIN_WINDOW 期开奖历史（默认 100 期）
- 输出: 纠偏后 80 码胜率排序、Top5 金胆、Top12 精选、Kill20 杀号、虚火诱多避坑清单与黑马提拔清单。

@author K8-Quant Error Correction Team
@since 2026-09-15
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("k8quant.error_correction")

TOTAL_BALLS = 80
TRAIN_WINDOW = 100
RECENT_FREQ_WIN = 20
SHORT_FREQ_WIN = 5
SWEET_CENTER = 10.0
SWEET_SIGMA = 4.2
CORRECTION_LAMBDA = 0.35  # 残差纠偏调节灵敏度 (步长控制，防学过头)
CACHE_TAG_EC = "ec_residual_v2_top3"

# 质数集合（1-80）
_PRIMES = {
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
    53, 59, 61, 67, 71, 73, 79,
}

FEATURE_NAMES = [
    "base_score",         # 基准模型给出的先验概率 (P_base)
    "gap",                # 当前遗漏期数
    "gap_ratio",          # 遗漏比率 (当前遗漏 / 历史平均遗漏，识别弹簧压制)
    "freq_recent_20",     # 近 20 期出号总频次
    "freq_short_5",       # 近 5 期出号短线频次
    "momentum_slope",     # 短线势头斜率 (近 5 期频次 vs 前 5 期频次差)
    "in_last",            # 上期是否开出 (1.0 / 0.0)
    "consecutive_streak", # 连开或连漏计数 (正数为连开期数，负数为连漏期数)
    "zone_density",       # 同 10 码区间出号拥挤度 (防扎堆诱多)
    "co_affinity",        # 与上期开出号的共现亲和力
    "road",               # 012 路归属 (0, 1, 2)
    "is_prime",           # 是否质数 (1.0 / 0.0)
    "ball_id",            # 球号编号 (1 ~ 80)
]


def _zone(n: int) -> int:
    """计算球号所在十进制区间 (1~8)"""
    return (n - 1) // 10 + 1


def _road(n: int) -> int:
    """计算 012 路 (模 3 余数)"""
    return n % 3


class ResidualCorrectionEngine:
    """
    残差改错预测引擎核心类 (Residual Error-Correction Engine)
    
    采用两阶段残差学习架构：
    1. 第一阶段：由先验模型计算每个球的基础开出概率估计 P_base；
    2. 第二阶段：计算真实开出监督值与基准的残差 R = Y - P_base，训练 LightGBM 改错回归树；
    3. 第三阶段：预测目标期残差 Delta_R，输出修正打分 P_final = clip(P_base + lambda * Delta_R, 0, 1)。
    """

    def __init__(self, history_data: Optional[List[Dict[str, Any]]] = None):
        """
        初始化残差改错预测引擎
        @param history_data 历史开奖期数据列表
        """
        self.history_data = history_data or []
        self._chrono: List[Dict[str, Any]] = []
        self._matrix: Optional[np.ndarray] = None
        self._total = 0
        self._raw_loaded = 0
        if self.history_data:
            self._prepare()

    def _prepare(self) -> None:
        """解析并对齐按时间正序排列的 0/1 历史开奖矩阵"""
        # 步骤 1: 筛选有效开奖数据并按期号正序排序
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

        # 步骤 2: 限制分析窗口为近 TRAIN_WINDOW 期
        if len(chrono) > TRAIN_WINDOW:
            chrono = chrono[-TRAIN_WINDOW:]
        self._chrono = chrono
        self._total = len(chrono)

        # 步骤 3: 构建二值开奖状态矩阵 (总期数, 80 球)
        mat = np.zeros((self._total, TOTAL_BALLS), dtype=np.float64)
        for i, item in enumerate(self._chrono):
            for n in item.get("numbers", []):
                if 1 <= n <= TOTAL_BALLS:
                    mat[i, n - 1] = 1.0
        self._matrix = mat

    def _gaps_at(self, end_idx: int) -> np.ndarray:
        """计算截至 end_idx 期（含）时 80 球的当前遗漏期数"""
        gaps = np.full(TOTAL_BALLS, float(end_idx + 1), dtype=np.float64)
        mat = self._matrix[: end_idx + 1, :]
        for b in range(TOTAL_BALLS):
            hits = np.where(mat[:, b] > 0.5)[0]
            if hits.size:
                gaps[b] = float(end_idx - int(hits[-1]))
        return gaps

    def _avg_gaps_at(self, end_idx: int) -> np.ndarray:
        """计算截至 end_idx 期（含）时 80 球的历史平均遗漏期数"""
        avg_gaps = np.full(TOTAL_BALLS, 4.0, dtype=np.float64)  # 理论平均遗漏为 (80-20)/20 = 3~4 期
        mat = self._matrix[: end_idx + 1, :]
        for b in range(TOTAL_BALLS):
            hits = np.where(mat[:, b] > 0.5)[0]
            if hits.size >= 2:
                diffs = np.diff(hits)
                avg_gaps[b] = max(1.0, float(np.mean(diffs)))
        return avg_gaps

    def _streaks_at(self, end_idx: int) -> np.ndarray:
        """计算截至 end_idx 期（含）时 80 球的连续连击数 (正为连开，负为连漏)"""
        streaks = np.zeros(TOTAL_BALLS, dtype=np.float64)
        mat = self._matrix[: end_idx + 1, :]
        for b in range(TOTAL_BALLS):
            col = mat[:, b]
            curr_state = col[-1]
            count = 0
            for val in reversed(col):
                if val == curr_state:
                    count += 1
                else:
                    break
            streaks[b] = float(count) if curr_state > 0.5 else -float(count)
        return streaks

    def _compute_base_prior(self, end_idx: int) -> np.ndarray:
        """
        第一阶段：构建第一棒基准模型的先验概率估计 P_base
        基于近窗移动频次、甜区遗漏回补衰减与马尔可夫转移自相关性构建平滑基线
        """
        assert self._matrix is not None
        mat = self._matrix

        # 1. 近窗频次基准 (20 期)
        win_r = min(RECENT_FREQ_WIN, end_idx + 1)
        freq_r = np.sum(mat[end_idx + 1 - win_r : end_idx + 1, :], axis=0) / float(win_r)

        # 2. 甜区回补先验
        gaps = self._gaps_at(end_idx)
        sweet = np.exp(-((gaps - SWEET_CENTER) ** 2) / (2.0 * SWEET_SIGMA ** 2))
        sweet = np.where(gaps >= 16.0, sweet * 0.5, sweet)

        # 3. 上期状态与马尔可夫自转移
        markov = np.full(TOTAL_BALLS, 0.25, dtype=np.float64)
        if end_idx >= 1:
            starts = np.sum(mat[:end_idx, :], axis=0)
            both = np.sum(mat[:end_idx, :] * mat[1 : end_idx + 1, :], axis=0)
            markov = both / np.maximum(starts, 1.0)

        # 4. 加权融合为基线概率 P_base
        p_base = 0.50 * freq_r + 0.30 * sweet + 0.20 * markov
        lo, hi = float(p_base.min()), float(p_base.max())
        if hi > lo:
            p_base = (p_base - lo) / (hi - lo)
        # 缩放到合理的概率先验区间 [0.05, 0.85]
        return 0.05 + 0.80 * p_base

    def _features_at(self, end_idx: int) -> np.ndarray:
        """
        构建截至 end_idx 期可见历史的 (80, F) 特征矩阵
        特征重点挖掘基准模型易发生“虚火诱多”或“漏判黑马”的上下文环境
        """
        assert self._matrix is not None
        mat = self._matrix
        p_base = self._compute_base_prior(end_idx)
        gaps = self._gaps_at(end_idx)
        avg_gaps = self._avg_gaps_at(end_idx)
        gap_ratio = gaps / np.maximum(avg_gaps, 1.0)
        streaks = self._streaks_at(end_idx)

        # 近 20 期与近 5 期频次
        win_20 = min(RECENT_FREQ_WIN, end_idx + 1)
        freq_20 = np.sum(mat[end_idx + 1 - win_20 : end_idx + 1, :], axis=0)
        win_5 = min(SHORT_FREQ_WIN, end_idx + 1)
        freq_5 = np.sum(mat[end_idx + 1 - win_5 : end_idx + 1, :], axis=0)

        # 动能斜率：近 5 期频次 vs 前 5 期频次
        if end_idx >= 9:
            freq_prev5 = np.sum(mat[end_idx - 9 : end_idx - 4, :], axis=0)
            momentum_slope = (freq_5 - freq_prev5) / 5.0
        else:
            momentum_slope = np.zeros(TOTAL_BALLS, dtype=np.float64)

        # 上期开出状态
        last_draw = mat[end_idx, :]

        # 分区出号拥挤度 (同一区间内上期开出多少个号，防过度集中爆雷)
        zone_counts = np.zeros(9, dtype=np.float64)
        for b in range(TOTAL_BALLS):
            if last_draw[b] > 0.5:
                zone_counts[_zone(b + 1)] += 1.0

        # 与上期开出号的共现亲和度
        co = np.dot(mat[: end_idx + 1, :].T, mat[: end_idx + 1, :])
        np.fill_diagonal(co, 0.0)
        co_affinity = np.dot(last_draw, co)

        feats = np.zeros((TOTAL_BALLS, len(FEATURE_NAMES)), dtype=np.float64)
        for b in range(TOTAL_BALLS):
            ball = b + 1
            z = _zone(ball)
            feats[b, 0] = p_base[b]
            feats[b, 1] = gaps[b]
            feats[b, 2] = gap_ratio[b]
            feats[b, 3] = freq_20[b]
            feats[b, 4] = freq_5[b]
            feats[b, 5] = momentum_slope[b]
            feats[b, 6] = last_draw[b]
            feats[b, 7] = streaks[b]
            feats[b, 8] = zone_counts[z]
            feats[b, 9] = co_affinity[b]
            feats[b, 10] = float(_road(ball))
            feats[b, 11] = 1.0 if ball in _PRIMES else 0.0
            feats[b, 12] = float(ball)
        return feats

    def _build_train_xy(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        用历史滚动时序构造残差训练集 (X, Residual)
        输入: 特征 X(t)
        监督目标: 残差 R(t+1) = Y(t+1) - P_base(t)
        """
        if self._matrix is None or self._total < 25:
            return np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,))
        xs: List[np.ndarray] = []
        rs: List[np.ndarray] = []

        start = max(12, self._total - TRAIN_WINDOW)
        for t in range(start, self._total - 1):
            x = self._features_at(t)
            p_base = self._compute_base_prior(t)
            y_actual = self._matrix[t + 1, :]
            # 关键：计算预测残差打脸值 (真实 1/0 减去 先验基准)
            residual = y_actual - p_base
            xs.append(x)
            rs.append(residual)

        if not xs:
            return np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,))
        X = np.vstack(xs)
        Residuals = np.concatenate(rs)
        return X, Residuals

    def _fit_predict_residuals(self) -> Tuple[np.ndarray, Dict[str, float], Dict[str, Any]]:
        """
        第二阶段：训练 GBDT / LightGBM 回归树，预测目标期 80 球的残差修正值 Delta_R
        """
        X, Residuals = self._build_train_xy()
        meta: Dict[str, Any] = {
            "n_train_rows": int(X.shape[0]),
            "n_features": len(FEATURE_NAMES),
            "feature_names": FEATURE_NAMES,
            "engine_backend": "lightgbm",
        }

        # 防御性降级：若样本过少，使用平滑统计残差回补
        if X.shape[0] < 200:
            logger.warning("样本量不足 (%d)，触发基于历史动能与反弹的启发式改错降级", X.shape[0])
            live_feats = self._features_at(self._total - 1)
            # 简易改错：高遗漏加分，过热动能衰竭扣分
            heur_res = 0.20 * (live_feats[:, 2] > 2.0) - 0.20 * (live_feats[:, 4] >= 4)
            return heur_res.astype(np.float64), {}, {**meta, "fallback": True}

        try:
            import lightgbm as lgb
            model = lgb.LGBMRegressor(
                n_estimators=80,
                learning_rate=0.03,
                max_depth=4,
                num_leaves=15,
                min_child_samples=8,
                subsample=0.85,
                colsample_bytree=0.85,
                random_state=42,
                n_jobs=-1,
                verbose=-1,
            )
            model.fit(X, Residuals)
            live_x = self._features_at(self._total - 1)
            pred_residuals = model.predict(live_x)

            imp = model.feature_importances_
            total_imp = max(float(np.sum(imp)), 1e-6)
            importance = {
                FEATURE_NAMES[i]: float(round(imp[i] / total_imp * 100, 2))
                for i in np.argsort(-imp)[:8]
            }
            meta.update({
                "fallback": False,
                "n_estimators": 80,
                "max_depth": 4,
                "learning_rate": 0.03,
            })
            return pred_residuals.astype(np.float64), importance, meta

        except Exception as exc:
            logger.warning("LightGBM 执行异常，尝试使用 sklearn GradientBoosting 兜底: %s", exc)
            from sklearn.ensemble import GradientBoostingRegressor
            gb = GradientBoostingRegressor(
                n_estimators=50,
                learning_rate=0.04,
                max_depth=3,
                random_state=42,
            )
            gb.fit(X, Residuals)
            live_x = self._features_at(self._total - 1)
            pred_residuals = gb.predict(live_x)
            imp = gb.feature_importances_
            importance = {
                FEATURE_NAMES[i]: float(round(imp[i] * 100, 2))
                for i in np.argsort(-imp)[:8]
            }
            meta.update({
                "engine_backend": "sklearn_gbr",
                "fallback": False,
                "n_estimators": 50,
                "max_depth": 3,
            })
            return pred_residuals.astype(np.float64), importance, meta

    def run_prediction(self) -> Dict[str, Any]:
        """
        主执行入口：产出残差改错预测报告数据
        符合系统通用 Standard JSON 契约，可无缝对接 AI 对账引擎与前端大屏
        """
        if not self.history_data or self._total < 20:
            return {"error": "历史开奖数据不足，无法启动残差改错训练"}

        latest = self.history_data[0]
        latest_issue = str(latest.get("issue", latest.get("period", "")))
        try:
            target_issue = str(int(latest_issue) + 1)
        except (TypeError, ValueError):
            target_issue = str(latest_issue)
        latest_numbers = latest.get("numbers", [])

        # 步骤 1: 获取实时基线打分 P_base 与 改错模型预测残差 Delta_R
        p_base = self._compute_base_prior(self._total - 1)
        delta_r, importance, ec_meta = self._fit_predict_residuals()

        # 步骤 2: 执行动态纠偏融合公式 P_final = clip(P_base + lambda * Delta_R, 0, 1)
        p_final = np.clip(p_base + CORRECTION_LAMBDA * delta_r, 0.0, 1.0)

        # 步骤 3: 提取关键风控信标（拔除诱多虚火号 与 提拔黑马回补号）
        gaps = self._gaps_at(self._total - 1)
        false_positive_traps = []  # 诱多虚火避坑 (P_base 偏高但 Delta_R 极负)
        false_negative_rebounds = []  # 漏网黑马提拔 (P_base 偏低但 Delta_R 极正)

        ball_details = []
        for i in range(TOTAL_BALLS):
            ball = i + 1
            b_base = float(p_base[i])
            b_res = float(delta_r[i])
            b_fin = float(p_final[i])
            b_gap = int(gaps[i])

            # 诊断标签
            tag = "平稳"
            if b_base >= 0.50 and b_res <= -0.15:
                tag = "虚火诱多"
                false_positive_traps.append({
                    "ball": ball,
                    "ball_str": f"{ball:02d}",
                    "base_score": round(b_base * 100, 1),
                    "residual_penalty": round(b_res * 100, 1),
                    "final_score": round(b_fin * 100, 1),
                    "reason": f"基准分高达{round(b_base*100,1)}但改错裁判扣除{round(abs(b_res)*100,1)}分，谨防扎堆踩踏",
                })
            elif b_base <= 0.35 and b_res >= 0.18:
                tag = "黑马反弹"
                false_negative_rebounds.append({
                    "ball": ball,
                    "ball_str": f"{ball:02d}",
                    "base_score": round(b_base * 100, 1),
                    "residual_bonus": round(b_res * 100, 1),
                    "final_score": round(b_fin * 100, 1),
                    "gap": b_gap,
                    "reason": f"遗漏{b_gap}期憋到极限，改错裁判强烈补给{round(b_res*100,1)}分，重点防回补",
                })

            ball_details.append({
                "ball": ball,
                "ball_str": f"{ball:02d}",
                "base_score": float(round(b_base * 100, 2)),
                "residual_correction": float(round(b_res * 100, 2)),
                "final_score": float(round(b_fin * 100, 2)),
                "gap": b_gap,
                "tag": tag,
                "is_recent_open": bool(ball in latest_numbers),
            })

        # 步骤 4: 优胜劣汰排序
        sorted_balls = sorted(ball_details, key=lambda x: x["final_score"], reverse=True)
        top3_gold = [x["ball"] for x in sorted_balls[:3]]
        top5_gold = top3_gold  # 兼容旧字段：主推改为最优3码
        top12_elite = top3_gold  # 兼容旧字段：不再维护 Top12

        # 步骤 5: 在纠偏 Top5 中基于近窗共现亲和矩阵选拔 1 组【改错黄金选2搭档】
        gold_pairs = []
        if len(top5_gold) >= 2 and self._matrix is not None:
            co = np.dot(self._matrix.T, self._matrix)
            best_pair = None
            best_co = -1
            for idx_a in range(len(top5_gold)):
                for idx_b in range(idx_a + 1, len(top5_gold)):
                    b1, b2 = top5_gold[idx_a], top5_gold[idx_b]
                    co_score = co[b1 - 1, b2 - 1]
                    if co_score > best_co:
                        best_co = co_score
                        best_pair = (min(b1, b2), max(b1, b2))
            if best_pair:
                gold_pairs.append({
                    "pair": f"{best_pair[0]:02d}+{best_pair[1]:02d}",
                    "balls": [best_pair[0], best_pair[1]],
                    "co_score": float(best_co),
                    "desc": "改错纠偏金胆共现最强组合",
                })

        return {
            "module_code": "error_correction",
            "module_name": "残差改错预测引擎 (V1.0)",
            "prediction_mode": "residual_boosting_gbdt",
            "target_issue": target_issue,
            "latest_issue": latest_issue,
            "latest_numbers": latest_numbers,
            "train_window": TRAIN_WINDOW,
            "history_used": self._total,
            "raw_draws_loaded": self._raw_loaded,
            "correction_lambda": CORRECTION_LAMBDA,
            "total_historical_draws": self._total,
            "top3_gold": top3_gold,
            "top5_gold": top5_gold,
            "top12_elite": top12_elite,
            "gold_pairs": gold_pairs,
            "traps_avoided": false_positive_traps,       # 拔除的虚火诱多雷号
            "rebounds_promoted": false_negative_rebounds, # 提拔的黑马回补号
            "ball_details": sorted_balls,
            "ball_proba_top20": [
                {
                    "ball": x["ball"],
                    "base_score": x["base_score"],
                    "residual_correction": x["residual_correction"],
                    "final_score": x["final_score"],
                    "tag": x["tag"],
                }
                for x in sorted_balls[:20]
            ],
            "feature_importance": importance,
            "engine_meta": ec_meta,
        }
