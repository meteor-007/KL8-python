# kl8_stats/fdr.py
# -*- coding: utf-8 -*-
"""Benjamini-Hochberg FDR 校正。"""


def bh_fdr(pvals, q=0.05):
    """对 p 值列表做 BH-FDR 校正，返回各 p 值是否显著（True=显著）。"""
    n = len(pvals)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: pvals[i])
    sig = [False] * n
    max_k = 0
    for rank, idx in enumerate(order, start=1):
        if pvals[idx] <= q * rank / n:
            max_k = rank
    for rank, idx in enumerate(order, start=1):
        if rank <= max_k:
            sig[idx] = True
    return sig


def bh_threshold(pvals, q=0.05):
    """返回 BH 校正后的全局 p 值阈值（小于该值才显著）。"""
    n = len(pvals)
    if n == 0:
        return None
    sorted_p = sorted(pvals)
    for rank, p in enumerate(sorted_p, start=1):
        if p > q * rank / n:
            return q * rank / n
    return q * n / n if n else None