# -*- coding: utf-8 -*-
"""快乐8 概率引擎（诚实口径）

规则事实：80 个号码中开出 20 个，每码被开出的概率恒为 25%，各期相互独立。

对**任意固定**的 k 个号码，命中数 X 服从超几何分布：
    X ~ Hypergeometric(N=80, K=20, n=k)

由此得到一件必须说清楚的事：**选哪 k 个号码不改变这个分布**。
任何选号算法（频次、遗漏、共振、神经网络……）都无法改变下面任何一个数字。
本模块存在的意义就是把这件事算准、说准，让报告直接引用，
而不是各处手抄一个容易抄错的"理论基线 6.0%"。

本模块**不含任何历史数据**，纯组合数学，结果可被独立验算。
奖金金额不在此写死 —— 玩法与返奖率会调整，硬编码等于伪造数据；
需要期望回报时由调用方传入当期奖金表。
"""
from __future__ import annotations

from math import comb
from typing import Dict, List

N_TOTAL = 80      # 号码总数
N_DRAWN = 20      # 每期开出个数
BASE_RATE = N_DRAWN / N_TOTAL   # 单码命中率 0.25


def _valid_k(k: int) -> int:
    if not isinstance(k, int) or isinstance(k, bool):
        raise TypeError(f"k 必须是整数，收到 {type(k).__name__}")
    if not 1 <= k <= N_TOTAL:
        raise ValueError(f"选号个数 k 必须在 1~{N_TOTAL} 之间，收到 {k}")
    return k


def prob_exact(k: int, j: int) -> float:
    """恰好命中 j 个的概率 P(X = j)。"""
    _valid_k(k)
    lo, hi = max(0, k - (N_TOTAL - N_DRAWN)), min(k, N_DRAWN)
    if j < lo or j > hi:
        return 0.0
    return comb(N_DRAWN, j) * comb(N_TOTAL - N_DRAWN, k - j) / comb(N_TOTAL, k)


def prob_at_least(k: int, j: int) -> float:
    """至少命中 j 个的概率 P(X >= j)。"""
    _valid_k(k)
    if j <= 0:
        return 1.0
    return sum(prob_exact(k, i) for i in range(j, min(k, N_DRAWN) + 1))


def prob_at_most(k: int, j: int) -> float:
    """最多命中 j 个的概率 P(X <= j)。"""
    _valid_k(k)
    return sum(prob_exact(k, i) for i in range(max(0, k - (N_TOTAL - N_DRAWN)), j + 1))


def hit_distribution(k: int) -> List[float]:
    """返回命中 0..k 个的概率列表（索引即命中数，长度 k+1）。

    列表之和恒为 1.0（受浮点误差影响，可能差 1e-15 量级）。
    """
    _valid_k(k)
    return [prob_exact(k, j) for j in range(k + 1)]


def expected_hits(k: int) -> float:
    """期望命中个数 = k * 20/80 = k * 0.25。"""
    _valid_k(k)
    return k * BASE_RATE


def all_match_prob(k: int) -> float:
    """选 k 全中（k 个号全部出现在开出的 20 码中）的概率。

    选1 = 25%，选2 ≈ 6.01%，选3 ≈ 1.39%，与日报里长期沿用的口径一致。
    """
    _valid_k(k)
    return prob_exact(k, k)


def expected_value(k: int, cost: float, prize_by_hits: Dict[int, float]) -> Dict[str, float]:
    """按给定奖金表算期望回报。

    Args:
        k: 选号个数
        cost: 单注成本（元）
        prize_by_hits: {命中个数: 该档奖金}。未列出的命中档视为 0 元。
                       必须是调用方提供的**当期真实**奖金表 —— 本模块不内置，
                       因为玩法与返奖率会调整，写死就是伪造数据。

    Returns:
        {'expected_payout', 'expected_net', 'expected_return_rate', 'prob_any_prize'}
    """
    _valid_k(k)
    if cost < 0:
        raise ValueError("cost 不能为负")
    pmf = hit_distribution(k)
    payout = 0.0
    prob_any = 0.0
    for hits, prize in prize_by_hits.items():
        if not 0 <= hits <= k:
            continue
        p = pmf[hits]
        payout += p * float(prize)
        if prize > 0:
            prob_any += p
    net = payout - cost
    return {
        "expected_payout": payout,
        "expected_net": net,
        "expected_return_rate": (payout / cost) if cost else 0.0,
        "prob_any_prize": prob_any,
    }


def summary(k: int) -> Dict[str, float]:
    """给报告用的一行摘要：买 k 个号，理论上的全部关键数字。"""
    _valid_k(k)
    return {
        "k": k,
        "expected_hits": expected_hits(k),
        "all_match_prob": all_match_prob(k),
        "prob_at_least_half": prob_at_least(k, (k + 1) // 2),
    }