# -*- coding: utf-8 -*-
"""§4.9 图网络关系挖掘（graph_net）→ H5（与 §4.7 linalg_svd 加权平均）。

号码当节点、共现 PMI 当边权：

1. **建图**：80 节点，边权 = PMI（仅保留正 PMI 且超过配置阈值的边 → 稀疏图）。
2. **中心性**：度中心性 + 特征向量中心性（幂迭代，numpy 自实现）。高中心性 = 枢纽号。
3. **社区发现**：贪心模块度最大化（Newman 2004，**自实现**，不引 networkx /
   python-louvain）。80 节点规模下 O(V³) 的朴素贪心已足够。
4. **RWR**：以拓展集合为种子，复用 §6.2 底座 `CooccurrenceBundle.rwr`
   （`r = α·p0 + (1−α)·Pᵀ·r`），得每号"亲和分"。
5. **桥接号**：Brandes betweenness（自实现），高通达度 = 连接多个社区的桥。
6. **打分**：亲和分 + 中心性（度/特征向量）+ 社区内亲和度 → 全 80 号 rank 归一。

无前视：只使用传入的 draws（调用方已裁剪到目标期之前），不读磁盘、不访问未来期。
随机性：本模块为确定性算法，不使用任何随机数（幂迭代、贪心合并均确定性）。
数值稳健：所有分数 ∈ [0,1] 且有限；退化输入（空 draws、单期历史、空图）不抛异常。

> 关于拓展集合：按 §3.5 / contracts.py，scores 覆盖**全部 1–80 号**，拓展集合只作为
> RWR 的种子与推荐阶段的遮罩输入，**不用于限制计算范围**（否则 §9.5 lift_exp 退化为恒等式）。
"""
from __future__ import annotations

import math

import numpy as np

from .contracts import ModuleResult
from .cooccurrence import build_cooccurrence
from .data_io import Draw
from .numerics import (EPS, MIN_SAMPLE, bh_fdr, clip01, finite, normalize,
                       safe_div)
from .points import NumberStats

N = 80
# 两号同期出现的理论概率：一期内 20/80 号开出 → P(两指定号同现) = C(20,2)/C(80,2)
P_BOTH = 190.0 / 3160.0
# 打分权重（亲和分 / 中心性 / 社区内亲和度）
W_AFF, W_CEN, W_COH = 0.50, 0.30, 0.20


def _cfg_get(cfg, section: str, key: str, default):
    """从 cfg 的某个 Section 读键；cfg 为 None 或缺键时返回 default。"""
    if cfg is None:
        return default
    sec = getattr(cfg, section, None)
    if sec is None:
        return default
    try:
        val = sec.get(key, None) if hasattr(sec, "get") else getattr(sec, key, None)
    except Exception:
        return default
    return default if val is None else val


# ── 自实现图算法（不依赖 networkx）─────────────────────────────

def _eigenvector_centrality(A: np.ndarray, iters: int = 200,
                            tol: float = 1e-10) -> np.ndarray:
    """幂迭代求主特征向量。非负矩阵由 Perron–Frobenius 保证主向量非负。

    退化（全 0 矩阵）→ 返回全 0，调用方经 rank 归一后为 0.5（无信息）。
    """
    n = A.shape[0]
    if n == 0:
        return np.zeros(0, dtype=float)
    x = np.ones(n, dtype=float)
    for _ in range(iters):
        nxt = A @ x
        nrm = float(np.abs(nxt).sum())
        if nrm <= EPS:
            return np.zeros(n, dtype=float)
        nxt = nxt / nrm
        if float(np.abs(nxt - x).sum()) < tol:
            x = nxt
            break
        x = nxt
    return np.maximum(x, 0.0)


def _betweenness(adj: np.ndarray) -> np.ndarray:
    """Brandes 无权 betweenness（O(V·E)，80 节点可接受）。

    adj 为 0/1 邻接矩阵（0-based）。返回已归一化到 [0,1] 的中心性。
    """
    n = adj.shape[0]
    bc = np.zeros(n, dtype=float)
    if n < 3:
        return bc
    nbrs = [np.nonzero(adj[v])[0].tolist() for v in range(n)]
    for s in range(n):
        stack: list[int] = []
        pred: list[list[int]] = [[] for _ in range(n)]
        sigma = np.zeros(n, dtype=float)
        sigma[s] = 1.0
        dist = np.full(n, -1, dtype=int)
        dist[s] = 0
        queue = [s]
        qi = 0
        while qi < len(queue):
            v = queue[qi]
            qi += 1
            stack.append(v)
            for w in nbrs[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = np.zeros(n, dtype=float)
        for v in reversed(stack):
            for w in pred[v]:
                delta[w] += safe_div(sigma[w], sigma[v], 0.0) * (1.0 + delta[v])
            if v != s:
                bc[v] += delta[v]
    bc = bc / 2.0                       # 无向图每条最短路被两端各计一次
    norm = (n - 1) * (n - 2) / 2.0
    if norm > 0:
        bc = bc / norm
    return bc


def _greedy_communities(W: np.ndarray) -> tuple[dict[int, int], float, int]:
    """Newman 贪心模块度最大化（自实现）。

    输入 W 为 **1-based** 对称非负权矩阵（下标 0 不用）。
    返回 (号码→社区号 的映射, 最优模块度 Q, 社区数)。

    约定：并入时取 Q 严格更大的快照；并列 ΔQ 取 (i,j) 最小的一对，保证确定性。
    孤立节点（度 0）永不与它人合并（ΔQ ≤ 0），保持单元素社区。
    """
    n = W.shape[0] - 1
    comm_singleton = {i + 1: i for i in range(n)}
    A = np.array(W[1:, 1:], dtype=float)
    np.fill_diagonal(A, 0.0)
    A = (A + A.T) / 2.0
    m = 0.5 * float(A.sum())
    if n == 0 or m <= EPS:
        return comm_singleton, 0.0, n

    deg = A.sum(axis=1)
    E = A.tolist()                      # 社区间权重（初始为单元素社区）
    a = deg.tolist()                    # 社区加权度
    comm_of = list(range(n))
    members = [[i] for i in range(n)]
    active = [True] * n
    twom = 2.0 * m

    Q = -float(np.sum((deg / twom) ** 2))       # 单元素社区的初始 Q
    best_Q = Q
    best_comm = list(comm_of)

    for _ in range(n - 1):
        best_dq = None
        bi = bj = -1
        idx = [i for i in range(n) if active[i]]
        for ii in range(len(idx)):
            i = idx[ii]
            ei = E[i]
            ai = a[i]
            for jj in range(ii + 1, len(idx)):
                j = idx[jj]
                # ΔQ = e_ij/m − a_i·a_j/(2m²)
                dq = ei[j] / m - (ai * a[j]) / (twom * m)
                if best_dq is None or dq > best_dq:
                    best_dq, bi, bj = dq, i, j
        if bi < 0:
            break
        Q += best_dq
        # 把 bj 并入 bi
        for k in range(n):
            if active[k] and k != bi and k != bj:
                E[bi][k] += E[bj][k]
                E[k][bi] = E[bi][k]
        a[bi] += a[bj]
        active[bj] = False
        E[bi][bj] = E[bj][bi] = 0.0
        for node in members[bj]:
            comm_of[node] = bi
            members[bi].append(node)
        members[bj] = []
        if Q > best_Q + 1e-12:
            best_Q = Q
            best_comm = list(comm_of)

    # 压缩社区标号并重算精确模块度
    uniq = sorted(set(best_comm))
    remap = {c: k for k, c in enumerate(uniq)}
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(best_comm[i], []).append(i)
    Qf = 0.0
    for g in groups.values():
        internal = float(A[np.ix_(g, g)].sum())
        ac = float(deg[g].sum())
        Qf += internal / twom - (ac / twom) ** 2
    comm = {i + 1: remap[best_comm[i]] for i in range(n)}
    return comm, finite(Qf, 0.0), len(uniq)


def _edge_significance(W: np.ndarray, C: np.ndarray, T: int, q: float
                       ) -> tuple[int, int, str]:
    """对保留边做二项显著性检验（H0：i.i.d. 均匀抽号下共现次数 ~ Bin(T, P_BOTH)）。

    返回 (检验边数, FDR 拒绝数, 方法名)。scipy 缺失时降级为跳过。
    """
    ii, jj = np.triu_indices(N + 1, k=1)
    keep = W[ii, jj] > 0
    ii, jj = ii[keep], jj[keep]
    n_edges = int(ii.size)
    if n_edges == 0 or T <= 0:
        return n_edges, 0, "skipped"
    try:
        from scipy.stats import binom
    except Exception:
        return n_edges, 0, "skipped"
    counts = C[ii, jj].astype(float)
    pvals = binom.sf(counts - 1.0, T, P_BOTH)      # 向量化，避免逐边调用开销
    _, rejects = bh_fdr([float(p) for p in np.atleast_1d(pvals)], q)
    return n_edges, int(sum(rejects)), "binomial+bh_fdr"


# ── 主入口（§3.5 统一签名）────────────────────────────────────

def analyze(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg) -> ModuleResult:
    """图网络关系挖掘（§4.9）。draws 必须最新在前且已裁剪到目标期之前。"""
    res = ModuleResult(name="graph_net", scores={})
    T = len(draws)
    ns = list(range(1, N + 1))

    # ── 降级 1：历史不足 ──
    if T < MIN_SAMPLE:
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期")
        res.metrics = {"T": T}
        res.add("risk", f"- 图网络：历史仅 {T} 期，数据不足（< {MIN_SAMPLE}），已跳过。",
                order=40)
        return res

    # ── 建图（复用 §6.2 底座，只算一次）──
    bundle = build_cooccurrence(draws, cfg=cfg)
    pmi = np.array(bundle.PMI, dtype=float)          # (81,81) 1-based
    C = np.array(bundle.C, dtype=float)
    thr = float(_cfg_get(cfg, "thresholds", "graph_pmi_threshold", 0.0))
    W = np.maximum(pmi - 0.0, 0.0)
    W = np.where((pmi > thr) & (pmi > 0.0), pmi, 0.0)  # 仅保留正 PMI 且 > 阈值
    np.fill_diagonal(W, 0.0)
    W = np.maximum(W, W.T)                             # 对称化（PMI 本已对称）
    m = 0.5 * float(W.sum())
    deg = W.sum(axis=1)                                # 加权度中心性

    # 无任何边 → 图退化，按 §3.6 降级
    if m <= EPS or float(np.count_nonzero(W)) == 0:
        res.degrade("共现图为空（无任何 PMI>阈值 的边）")
        res.metrics = {"T": T, "pmi_threshold": round(thr, 4), "n_edges": 0}
        res.add("risk", "- 图网络：历史共现中不存在超过阈值的正 PMI 边，图退化，已跳过。",
                order=40)
        return res

    # ── 中心性 ──
    A = W[1:, 1:]                                       # 0-based 邻接（带权）
    eig = _eigenvector_centrality(A)
    btw = _betweenness((A > 0).astype(float))

    # ── 社区发现 + 社区内亲和度 ──
    comm, modularity, n_comm = _greedy_communities(W)
    coh = np.zeros(N + 1, dtype=float)
    for n in ns:
        cn = comm.get(n)
        if cn is None:
            continue
        coh[n] = sum(W[n][j] for j in ns if j != n and comm.get(j) == cn)

    # ── RWR：以拓展集合为种子（复用 §6.2 底座）──
    alpha = float(_cfg_get(cfg, "thresholds", "graph_rwr_alpha", 0.15))
    seeds = {int(s) for s in (expanded_set or set()) if 1 <= int(s) <= N}
    aff = np.array(bundle.rwr(seeds, alpha=alpha, weight="PMI"), dtype=float)

    # ── 归一化并合成（全 80 号 rank 归一，不限制在拓展集合内）──
    method = _cfg_get(cfg, "thresholds", "norm_method", "rank") or "rank"
    aff_r = normalize([float(aff[n]) for n in ns], method)
    deg_r = normalize([float(deg[n]) for n in ns], method)
    eig_r = normalize([float(eig[n - 1]) for n in ns], method)
    coh_r = normalize([float(coh[n]) for n in ns], method)
    cen_r = [0.5 * (deg_r[i] + eig_r[i]) for i in range(N)]

    scores: dict[int, float] = {}
    for i, n in enumerate(ns):
        scores[n] = clip01(W_AFF * aff_r[i] + W_CEN * cen_r[i] + W_COH * coh_r[i])
    res.scores = scores

    # ── 显著性诊断 ──
    alpha_sig = float(_cfg_get(cfg, "thresholds", "alpha", 0.05))
    n_edges = int(np.count_nonzero(np.triu(W, 1) > 0))
    n_tested, n_sig, sig_method = _edge_significance(W, C, T, alpha_sig)

    # ── 可解释指标 ──
    hub = sorted(ns, key=lambda n: (-deg[n], n))[:5]
    aff_top = sorted(ns, key=lambda n: (-aff[n], n))[:5]
    bridge = sorted(ns, key=lambda n: (-btw[n - 1], n))[:5]
    coh_top = sorted(ns, key=lambda n: (-coh[n], n))[:5]
    sizes: dict[int, int] = {}
    for n in ns:
        sizes[comm.get(n, -1)] = sizes.get(comm.get(n, -1), 0) + 1
    largest_comm = max(sizes.values()) if sizes else 0

    hot_hubs = 0
    if base_stats:
        hot_hubs = sum(1 for n in hub if base_stats.get(n) is not None
                       and base_stats[n].z_score > 0)

    res.metrics = {
        "T": T,
        "pmi_threshold": round(thr, 4),
        "rwr_alpha": round(alpha, 3),
        "n_edges": n_edges,
        "density": round(safe_div(n_edges, N * (N - 1) / 2.0, 0.0), 4),
        "mean_degree": round(safe_div(2.0 * n_edges, N, 0.0), 2),
        "modularity": round(modularity, 4),
        "n_communities": n_comm,
        "largest_community": largest_comm,
        "top_hubs": [(int(n), round(float(deg[n]), 3)) for n in hub],
        "top_affinity": [(int(n), round(float(aff[n]), 5)) for n in aff_top],
        "top_bridge": [(int(n), round(float(btw[n - 1]), 4)) for n in bridge],
        "top_community_cohesion": [(int(n), round(float(coh[n]), 3)) for n in coh_top],
        "sig_edges": n_sig,
        "sig_tested": n_tested,
        "sig_ratio": round(safe_div(n_sig, n_tested, 0.0), 3),
    }
    res.diagnostics = {
        "samples": T,
        "n_edges": n_edges,
        "modularity": round(modularity, 4),
        "n_communities": n_comm,
        "significance_method": sig_method,
        "significant_edges": n_sig,
        "edges_tested": n_tested,
        "window": "expanded_seeds_empty" if not seeds else "ok",
        "groups": {str(k): v for k, v in sorted(sizes.items(), key=lambda kv: -kv[1])[:8]},
    }

    # ── narrative（真实数值，来自上面的 metrics）──
    res.add("macro",
            f"- **枢纽号**（PMI 加权度中心性）："
            f"{'、'.join(f'{n:02d}({deg[n]:.2f})' for n in hub)}；"
            f"图中保留 {n_edges} 条正 PMI 边，模块度 Q={modularity:.3f}，"
            f"识别出 {n_comm} 个社区（最大社区 {largest_comm} 号）。",
            order=22)
    if seeds:
        res.add("macro",
                f"- **图亲和度**（以 {len(seeds)} 个点位为种子的 RWR）："
                f"{'、'.join(f'{n:02d}({aff[n]:.4f})' for n in aff_top)}。",
                order=23)
    res.add("macro",
            f"- **桥接号**（betweenness，连接多社区）："
            f"{'、'.join(f'{n:02d}({btw[n - 1]:.3f})' for n in bridge)}；"
            f"社区内亲和度最高："
            f"{'、'.join(f'{n:02d}' for n in coh_top)}。",
            order=24)
    if not seeds:
        res.add("risk", "- 图网络：拓展集合为空，RWR 亲和分无有效种子，"
                        "本次以中心性/社区结构为主。", order=41)
    if n_tested > 0 and n_sig == 0:
        res.add("risk", f"- 图网络：{n_tested} 条保留边经 BH-FDR 校正后**无**边显著"
                        f"（α={alpha_sig}），图示关系与随机共现难以区分，结论仅供参照。",
                order=42)
    elif n_tested > 0:
        res.add("risk", f"- 图网络显著性：{n_tested} 条边中 {n_sig} 条通过 BH-FDR "
                        f"（α={alpha_sig}，{sig_method}）。", order=42)

    return res
