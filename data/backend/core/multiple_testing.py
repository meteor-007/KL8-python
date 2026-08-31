# -*- coding: utf-8 -*-
"""
多重检验校正 — BH-FDR / Bonferroni
====================================
多重发现(多通道/多特征/多号码)时, 纯随机也会出现若干"看上去显著"的假阳性。
任何"发现"都应先过此校正, 否则会被噪声钓鱼。
"""
from typing import List, Sequence, Tuple


def bh_fdr(p_values: Sequence[float], alpha: float = 0.05) -> Tuple[List[bool], List[float]]:
    """Benjamini-Hochberg FDR.

    返回 (significant_mask, q_values)。q_value 为 BH 校正后的最小 FDR。
    """
    m = int(len(p_values))
    if m == 0:
        return [], []
    ps = [float(p) for p in p_values]
    indexed = sorted(enumerate(ps), key=lambda x: x[1])
    # q-value: p[i] * m / rank, 再从大到小单调化
    q = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        idx, p = indexed[rank - 1]
        running = min(running, p * m / rank)
        q[idx] = running
    significant = [q[i] <= alpha for i in range(m)]
    return significant, q


def bonferroni(p_values: Sequence[float], alpha: float = 0.05) -> Tuple[List[bool], List[float]]:
    """Bonferroni: 最保守, q = p * m (截断到 1)。"""
    m = int(len(p_values))
    if m == 0:
        return [], []
    q = [min(1.0, float(p) * m) for p in p_values]
    significant = [q[i] <= alpha for i in range(m)]
    return significant, q


def apply_fdr(p_values: Sequence[float], alpha: float = 0.05,
              method: str = 'bh') -> Tuple[List[bool], List[float]]:
    """按 method ('bh' | 'bonferroni') 做多重检验校正。"""
    method = (method or 'bh').strip().lower()
    if method == 'bonferroni':
        return bonferroni(p_values, alpha)
    return bh_fdr(p_values, alpha)