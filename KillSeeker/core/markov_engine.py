"""
KillSeeker V2.0 — 引擎5: 马尔可夫链分析器

单号「出没」状态链的滚动估计：对每个号码 1-80，历史是 0/1 二值序列，
估计 P(下期开出 | 近 k 期出没模式)（k=1..3，Beta 收缩向经验基线），
输出对数证据 LL 与加权期望开出概率 p_combined。

信号语义与其余引擎一致（0..1，越高越像"会开出"、越不该杀）：
  signal = clip(0.5 + (p_combined − prior) × 4, 0, 1)

设计依据（kl8_stats/markov.py 滚动 OOS 验证，200 期）：
  - 马尔可夫 LL 杀 25 码：杀对率 76.0% vs 随机基线 75.0%（z=+1.67，方向性被反向对照证实）
  - 冷号回归假设被证伪：P(下期出 | 连续遗漏 L 期) 在 L=0..12 维持 0.25~0.259 平坦
  → 信号诚实但微弱，作低权重副引擎并入加权评分，不单独决策。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.data_loader import KL8Draw
from config.model_config import MarkovConfig
import kl8_stats.markov as _mk


@dataclass
class MarkovResult:
    """马尔可夫分析结果（参与评分）"""
    probability: Dict[int, float]   # 号码 -> 加权期望开出概率 p_combined
    ll: Dict[int, float]            # 号码 -> 加权对数证据 LL
    k_probs: Dict[int, Dict[int, float]]  # 号码 -> {k: p_hat_k}（诊断用）
    cold_curve: List[Dict]          # 冷号回归曲线（诊断用，未接入评分）


class MarkovEngine:
    """引擎5: 马尔可夫链分析器"""

    def __init__(self, config: Optional[MarkovConfig] = None):
        self.config = config or MarkovConfig()

    def analyze(self, history: List[KL8Draw]) -> MarkovResult:
        """
        马尔可夫分析

        Args:
            history: 历史开奖数据(≤T)，降序（最新在前）

        Returns:
            MarkovResult
        """
        # KL8Draw 是降序 → 升序集合列表
        sets_asc = [d.number_set for d in reversed(history)]
        prior = self.config.prior
        evidence = _mk.markov_evidence(
            sets_asc, max_k=self.config.max_k, prior=prior,
            alpha=self.config.alpha, weights=self.config.weights)

        probability = {}
        ll = {}
        k_probs = {}
        for num, ev in evidence.items():
            probability[num] = ev["p_combined"]
            ll[num] = ev["ll"]
            k_probs[num] = ev["k_probs"]

        cold_curve = self._cold_curve(sets_asc, prior)
        return MarkovResult(
            probability=probability, ll=ll, k_probs=k_probs,
            cold_curve=cold_curve)

    def _cold_curve(self, sets_asc: List[set], prior: float) -> List[Dict]:
        """冷号回归曲线：80 号平均的 P(出 | 连续遗漏 L 期)。"""
        series_map = _mk.series_from_sets(sets_asc)
        max_om = self.config.cold_curve_max_omission
        curve = []
        for L in range(0, max_om + 1):
            ps = [_mk.cold_comeback_curve(series_map[u], max_omission=L)[L]
                  for u in range(1, 81)]
            avg_p = sum(r["p_hat"] for r in ps) / 80
            avg_n = sum(r["n"] for r in ps) // 80
            curve.append({"L": L, "n": avg_n, "p_hat": avg_p,
                          "ll": _mk.math_log(avg_p / prior) if avg_p > 0 else 0.0})
        return curve

    def to_signal(self, result: MarkovResult) -> Dict[int, float]:
        """p_combined → 0..1 信号（0=极可能不开，1=极可能开）。"""
        scale = self.config.signal_scale / 0.25  # 归一化：p 相对基线的偏移放大
        sig = {}
        for num in range(1, 81):
            p = result.probability.get(num, self.config.prior)
            sig[num] = max(0.0, min(1.0, 0.5 + (p - self.config.prior) * scale))
        return sig