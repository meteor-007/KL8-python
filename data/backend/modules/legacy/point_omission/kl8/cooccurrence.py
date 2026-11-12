# -*- coding: utf-8 -*-
"""底座：共现与图关系（§6.2）。

供 §4.7（线性代数）与 §4.9（图网络）共享，**只算一次**。
全档案回测中不得每期重算——提供增量 add/remove（§12.2），
等价性由 test_incremental_equivalence 保证。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .data_io import Draw
from .numerics import EPS, clip01, finite, safe_div, safe_log

N = 80


@dataclass
class CooccurrenceBundle:
    """共现矩阵及其派生量。矩阵用 1-based 索引：下标 0 不用，n 对应 [n]。"""
    C: np.ndarray = field(default_factory=lambda: np.zeros((N + 1, N + 1), dtype=float))
    count: np.ndarray = field(default_factory=lambda: np.zeros(N + 1, dtype=float))
    T: int = 0
    _J: np.ndarray | None = None
    _PMI: np.ndarray | None = None

    # ── 增量维护 ──────────────────────────────────────────────
    def add(self, draw: Draw) -> None:
        self._accumulate(draw, +1.0)

    def remove(self, draw: Draw) -> None:
        self._accumulate(draw, -1.0)

    def _accumulate(self, draw: Draw, sign: float) -> None:
        """向量化累加/回退一期。号码升序去重，故 (i,j) 对无重复，可直接花式索引。"""
        nums = np.array(sorted(draw.numbers), dtype=np.intp)
        if nums.size >= 2:
            i, j = np.triu_indices(nums.size, k=1)
            ii, jj = nums[i], nums[j]
            self.C[ii, jj] += sign
            self.C[jj, ii] += sign
        if nums.size:
            self.count[nums] += sign
        self.T += int(sign)
        self._J = self._PMI = None

    # ── 派生矩阵（惰性计算并缓存）─────────────────────────────
    @property
    def J(self) -> np.ndarray:
        """Jaccard 系数 J[i][j] = C / (c_i + c_j − C)。"""
        if self._J is None:
            J = np.zeros_like(self.C)
            for i in range(1, N + 1):
                for j in range(i + 1, N + 1):
                    union = self.count[i] + self.count[j] - self.C[i][j]
                    val = safe_div(self.C[i][j], union, 0.0)
                    J[i][j] = J[j][i] = val
            self._J = J
        return self._J

    @property
    def PMI(self) -> np.ndarray:
        """点互信息 PMI = log( P(i,j) / (P(i)P(j)) )，C=0 处为 0。"""
        if self._PMI is None:
            pmi = np.zeros_like(self.C)
            if self.T > 0:
                for i in range(1, N + 1):
                    pi = self.count[i] / self.T
                    if pi <= EPS:
                        continue
                    for j in range(i + 1, N + 1):
                        if self.C[i][j] <= 0:
                            continue
                        pj = self.count[j] / self.T
                        if pj <= EPS:
                            continue
                        pij = self.C[i][j] / self.T
                        val = safe_log(safe_div(pij, pi * pj, 0.0), 0.0)
                        pmi[i][j] = pmi[j][i] = val
            self._PMI = pmi
        return self._PMI

    # ── 图扩散 ────────────────────────────────────────────────
    def rwr(self, seed_set, alpha: float = 0.15, iters: int = 50,
            tol: float = 1e-8, weight: str = "C") -> np.ndarray:
        """重启随机游走。返回长度 81 的亲和向量（下标 0 恒为 0）。

        r = alpha·p0 + (1−alpha)·Pᵀ·r
        种子集为拓展集合，alpha 为重启概率（越大越贴近种子）。
        """
        W = {"C": self.C, "J": self.J, "PMI": self.PMI}.get(weight, self.C)
        W = np.maximum(W, 0.0)
        deg = W.sum(axis=1)
        P = np.zeros_like(W)
        for i in range(1, N + 1):
            if deg[i] > EPS:
                P[i] = W[i] / deg[i]

        p0 = np.zeros(N + 1)
        seeds = [s for s in seed_set if 1 <= s <= N]
        if not seeds:
            return p0
        p0[seeds] = 1.0 / len(seeds)

        r = p0.copy()
        for _ in range(iters):
            nxt = alpha * p0 + (1.0 - alpha) * (P.T @ r)
            if np.abs(nxt - r).sum() < tol:
                r = nxt
                break
            r = nxt
        r[0] = 0.0
        return r

    def neighbours(self, n: int, top_k: int = 10, weight: str = "PMI"
                   ) -> list[tuple[int, float]]:
        W = {"C": self.C, "J": self.J, "PMI": self.PMI}.get(weight, self.PMI)
        row = [(m, float(W[n][m])) for m in range(1, N + 1) if m != n]
        row.sort(key=lambda t: (-t[1], t[0]))
        return row[:top_k]


def build_cooccurrence(draws: list[Draw], cfg=None,
                       bundle: CooccurrenceBundle | None = None) -> CooccurrenceBundle:
    """从零构建，或在已有 bundle 上增量推进。"""
    if bundle is None:
        bundle = CooccurrenceBundle()
    for d in draws:
        bundle.add(d)
    return bundle


def slide_window(bundle: CooccurrenceBundle, drop: Draw | None,
                 add: Draw | None) -> CooccurrenceBundle:
    """滑动窗口的一步：减去滑出期、加上新期（§12.2）。"""
    if drop is not None:
        bundle.remove(drop)
    if add is not None:
        bundle.add(add)
    return bundle
