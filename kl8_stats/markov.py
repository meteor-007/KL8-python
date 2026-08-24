# kl8_stats/markov.py
# -*- coding: utf-8 -*-
"""马尔可夫链估计器 — 号码/点位「出没」状态链的统计证据。

对每个单位（号码 1-80 或点位 1-80），历史是一串 0/1 二值序列（本期是否开出）。
估计 P(下期开出 | 近 k 期出没模式)，k 阶马尔可夫，Beta 收缩向基线，
输出对数证据 LL = Σ_k w_k · log(p_hat_k / prior)。

设计原则：
  - 状态空间 = 80 单位 × 2^k 模式（k≤3），参数稀疏、样本充足（4000 期 → 每上下文数百样本）
  - Beta 收缩：低样本上下文向基线收缩，天然防过拟合（无需 FDR/OOF 门槛）
  - 输出与 顺口溜 confidence 系同构：LL > 0 偏建议（出），LL < 0 偏回避（杀）
  - 单位间无相关建模（80 选 20 的联合相关是 3.5×10^18 状态，不可行），只做边际自回归
"""
from __future__ import annotations

from typing import Dict, List, Sequence

N_UNITS = 80
DEFAULT_PRIOR = 0.25          # 单号随机开出概率 = 20/80
DEFAULT_ALPHA = 12.0          # Beta 先验强度（伪计数）
DEFAULT_WEIGHTS = (0.5, 0.3, 0.2)  # k=1,2,3 证据权重（低阶优先，高阶噪声大）


def series_from_sets(sets_ascending: Sequence[Sequence], unit_range=range(1, N_UNITS + 1)) -> Dict[int, List[int]]:
    """由时间升序的每期开出集合列表，构建每个单位的 0/1 序列。

    sets_ascending[t] = 第 t 期（时间升序）开出的单位集合。
    返回 {unit: [0/1, ...]}，长度 = len(sets_ascending)。
    """
    out = {u: [] for u in unit_range}
    for opened in sets_ascending:
        s = set(opened)
        for u in unit_range:
            out[u].append(1 if u in s else 0)
    return out


def _beta_p_shrunk(hits: int, n: int, prior: float, alpha: float) -> float:
    """Beta(hits + prior·α, n − hits + (1−prior)·α) 后验均值。n=0 时返回先验。"""
    if n <= 0:
        return prior
    a = prior * alpha
    b = (1.0 - prior) * alpha
    return (hits + a) / (n + a + b)


def transitions(series: Sequence[int], k: int) -> Dict[int, Dict[int, int]]:
    """k 阶转移计数：context_int(近 k 期模式) -> {next: n}。

    context_int = Σ_{i=0}^{k-1} series[t-1-i] << i（最近期在最低位）。
    仅统计连续 k 期上下文完整的转移。
    """
    counts: Dict[int, Dict[int, int]] = {}
    if len(series) <= k:
        return counts
    for t in range(k, len(series)):
        ctx = 0
        for i in range(k):
            ctx |= series[t - 1 - i] << i
        nxt = series[t]
        d = counts.setdefault(ctx, {})
        d[nxt] = d.get(nxt, 0) + 1
    return counts


def cond_probs(series: Sequence[int], k: int, prior: float = DEFAULT_PRIOR,
               alpha: float = DEFAULT_ALPHA) -> Dict[int, float]:
    """每上下文 Beta 收缩的 P(下期开出 | 上下文)。返回 {context_int: p_hat}。"""
    counts = transitions(series, k)
    out = {}
    for ctx, nxt in counts.items():
        n = nxt.get(1, 0) + nxt.get(0, 0)
        out[ctx] = _beta_p_shrunk(nxt.get(1, 0), n, prior, alpha)
    return out


def context_int(series: Sequence[int], k: int, end_exclusive: int) -> int:
    """位置 end_exclusive 之前 k 期的模式 int（最近期在最低位）。"""
    ctx = 0
    for i in range(k):
        t = end_exclusive - 1 - i
        if t < 0:
            return None
        ctx |= series[t] << i
    return ctx


def markov_ll_for_unit(series: Sequence[int], max_k: int = 3, prior: float = DEFAULT_PRIOR,
                       alpha: float = DEFAULT_ALPHA, weights: Sequence[float] = DEFAULT_WEIGHTS,
                       top_ctx: int = 1) -> Dict:
    """单位级马尔可夫证据：加权合并 k=1..max_k 的条件概率 LL。

    返回 {ll, p_combined, k_probs: {k: p_hat}, k_ctx: {k: context_int}}。
      ll = Σ_k w_k · log(p_hat_k / prior)，全部中性时 = 0
      p_combined = Σ_k w_k · p_hat_k（加权期望开出概率）
    """
    ws = list(weights[:max_k])
    s = sum(ws)
    ws = [w / s for w in ws]
    ll = 0.0
    p_comb = 0.0
    k_probs = {}
    k_ctx = {}
    for k in range(1, max_k + 1):
        probs = cond_probs(series, k, prior, alpha)
        ctx = context_int(series, k, len(series))
        if ctx is None or ctx not in probs:
            p = prior
        else:
            p = probs[ctx]
        k_probs[k] = p
        k_ctx[k] = ctx
        ll += ws[k - 1] * (math_log(p / prior) if p > 0 else 0.0)
        p_comb += ws[k - 1] * p
    return {"ll": ll, "p_combined": p_comb, "k_probs": k_probs, "k_ctx": k_ctx}


def markov_evidence(sets_ascending: Sequence[Sequence], max_k: int = 3,
                    prior: float = DEFAULT_PRIOR, alpha: float = DEFAULT_ALPHA,
                    weights: Sequence[float] = DEFAULT_WEIGHTS) -> Dict[int, Dict]:
    """批量：对全部单位计算马尔可夫证据。返回 {unit: {ll, p_combined, k_probs}}。"""
    series_map = series_from_sets(sets_ascending)
    out = {}
    for u, s in series_map.items():
        out[u] = markov_ll_for_unit(s, max_k, prior, alpha, weights)
    return out


def cold_comeback_curve(series: Sequence[int], max_omission: int = 15,
                        prior: float = DEFAULT_PRIOR, alpha: float = DEFAULT_ALPHA) -> List[Dict]:
    """冷号回归曲线：P(下期开出 | 已连续遗漏 L 期)，L=0..max_omission。

    直接检验「冷号该回归」假设：若条件概率随 L 单调上升且显著 > 基线，假设成立；
    否则为迷信。返回 [{L, n, hits, p_hat, ll}]。
    """
    out = []
    for L in range(0, max_omission + 1):
        # 连续遗漏 L 期：位置 t 满足 series[t-L-1..t-1] 全 0 且 t-L-1≥0（L 期前必须曾出，
        # 否则无法区分"从未出"），观察 series[t]。
        hits = 0
        n = 0
        for t in range(L + 1, len(series)):
            if all(series[t - 1 - i] == 0 for i in range(L)):
                n += 1
                hits += series[t]
        p = _beta_p_shrunk(hits, n, prior, alpha)
        out.append({
            "L": L, "n": n, "hits": hits, "p_hat": p,
            "ll": math_log(p / prior) if p > 0 else 0.0,
        })
    return out


def binary_sets_from_draws(records_ascending, key="numbers") -> List[set]:
    """从时间升序的记录列表提取每期开出集合（兼容 dict 或带 .numbers 的对象）。"""
    sets = []
    for r in records_ascending:
        nums = r[key] if isinstance(r, dict) else getattr(r, key)
        sets.append(set(nums))
    return sets


def math_log(x: float) -> float:
    import math
    return math.log(x) if x > 0 else 0.0