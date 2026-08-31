"""
KillSeeker V2.0 — 引擎5: 马尔可夫链分析器 (找跟班/状态链)
======================================================
单号「出没」状态链的滚动估计：对每个号码 1-80，历史是 0/1 二值序列，
估计 P(下期开出 | 近 k 期出没模式)（k=1..3，Beta 收缩向经验基线），
输出对数证据 LL 与加权期望开出概率 p_combined。

信号语义与其余引擎一致（0..1，越高越像"会开出"、越不该杀）：
  signal = clip(0.5 + (p_combined − prior) × 4, 0, 1)

纯 Python 自包含原生实现，消除对外部未定义包的引用。
"""
from __future__ import annotations
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from kill_seeker.core.data_loader import KL8Draw
from kill_seeker.config.model_config import MarkovConfig


def series_from_sets(sets_asc: List[set]) -> Dict[int, List[int]]:
    """将升序排列的历史开奖集合转换为 1-80 号码各自的 0/1 历史时序。"""
    return {u: [int(u in s) for s in sets_asc] for u in range(1, 81)}


def markov_evidence(
    sets_asc: List[set],
    max_k: int = 3,
    prior: float = 0.25,
    alpha: float = 12.0,
    weights: tuple = (0.5, 0.3, 0.2)
) -> Dict[int, Dict[str, Any]]:
    """
    计算 1-80 号码的多阶马尔可夫期望开出概率与对数证据 (LL)。
    """
    series_map = series_from_sets(sets_asc)
    T = len(sets_asc)
    result = {}

    w_list = list(weights[:max_k])
    if len(w_list) < max_k:
        w_list += [1.0 / max_k] * (max_k - len(w_list))
    total_w = sum(w_list) if sum(w_list) > 0 else 1.0
    w_norm = [w / total_w for w in w_list]

    for num in range(1, 81):
        seq = series_map[num]
        k_probs = {}
        if T <= max_k:
            for k in range(1, max_k + 1):
                k_probs[k] = prior
            p_combined = prior
            ll = 0.0
        else:
            for k in range(1, max_k + 1):
                if T < k + 1:
                    k_probs[k] = prior
                    continue
                target_pat = tuple(seq[T - k: T])
                n_pat = 0
                n_next_1 = 0
                for t in range(k, T):
                    if tuple(seq[t - k: t]) == target_pat:
                        n_pat += 1
                        if seq[t] == 1:
                            n_next_1 += 1
                p_hat = (n_next_1 + alpha * prior) / (n_pat + alpha)
                k_probs[k] = p_hat

            p_combined = sum(w * k_probs.get(k + 1, prior) for k, w in enumerate(w_norm))
            p_combined = max(1e-6, min(1.0 - 1e-6, p_combined))
            ll = math.log(p_combined / prior) if prior > 0 else 0.0

        result[num] = {
            "p_combined": p_combined,
            "ll": ll,
            "k_probs": k_probs
        }
    return result


def cold_comeback_curve(series: List[int], max_omission: int = 12) -> Dict[int, Dict[str, Any]]:
    """
    计算单号在连续遗漏 L 期条件下的回归开出率曲线。
    """
    total_counts = defaultdict(int)
    hit_counts = defaultdict(int)

    curr_omiss = 0
    for val in series:
        if curr_omiss <= max_omission:
            total_counts[curr_omiss] += 1
            if val == 1:
                hit_counts[curr_omiss] += 1
        if val == 1:
            curr_omiss = 0
        else:
            curr_omiss += 1

    res = {}
    for L in range(0, max_omission + 1):
        n = total_counts[L]
        hits = hit_counts[L]
        p_hat = (hits / n) if n > 0 else 0.25
        res[L] = {"n": n, "hits": hits, "p_hat": p_hat}
    return res


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
        evidence = markov_evidence(
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
        series_map = series_from_sets(sets_asc)
        max_om = self.config.cold_curve_max_omission
        curve = []
        for L in range(0, max_om + 1):
            ps = [cold_comeback_curve(series_map[u], max_omission=L)[L]
                  for u in range(1, 81)]
            avg_p = sum(r["p_hat"] for r in ps) / 80
            avg_n = sum(r["n"] for r in ps) // 80
            curve.append({
                "L": L,
                "n": avg_n,
                "p_hat": avg_p,
                "ll": math.log(avg_p / prior) if avg_p > 0 and prior > 0 else 0.0
            })
        return curve

    def to_signal(self, result: MarkovResult) -> Dict[int, float]:
        """p_combined → 0..1 信号（0=极可能不开，1=极可能开）。"""
        scale = self.config.signal_scale / 0.25  # 归一化：p 相对基线的偏移放大
        sig = {}
        for num in range(1, 81):
            p = result.probability.get(num, self.config.prior)
            sig[num] = max(0.0, min(1.0, 0.5 + (p - self.config.prior) * scale))
        return sig