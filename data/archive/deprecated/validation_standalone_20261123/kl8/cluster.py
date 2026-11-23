# -*- coding: utf-8 -*-
"""连号集群行为 Cluster Dynamics（§4.1）→ H3 集群。

四步（严格对应 §4.1 算法）：

1. **连段扫描**：每期开奖号升序后扫描"相邻整数"构成的连续段，
   ``[12,13]`` 记 2 连段、``[38,39,40]`` 记 3 连段、长度 ≥4 记 4+ 连段。
2. **连段频率与显著性**：统计最近 N（=min(60,T)）期各类连段出现次数 ``f_k``
   （k=2,3,4+）。零分布（i.i.d.：每期从 80 中均匀抽 20）的均值 ``E_k`` 与
   标准差 ``σ_k`` 由 **Monte Carlo** 估计（10000 次模拟，不使用解析组合公式）。
   ``cluster_z_k = (f_k − E_k)/σ_k``，双侧检验，α 取自配置，3 档用 Bonferroni 校正。
3. **三元组场分析**：对每个形如 ``{p−1,p,p+1}``（循环回绕）的三元组统计其
   "成团命中数"——三元组中至少 2 个同期开出。
4. **打分**：把三个原始量在全 80 号上 rank 归一后加权，得每号得分：
   - 三元组近 10 期成团命中数越高 → 集群越活跃（``activity``）；
   - "未补的连号缺口"：邻居热而本号长期未补 → 回补预期（``gap``）；
   - 集群内凝聚力：与两侧邻居的共现强度 C[n][n−1]+C[n][n+1]（``cohesion``）。

无前视：只消费传入的 ``draws``（调用方已裁剪到目标期之前，最新在前）。
随机性：Monte Carlo 只用 ``np.random.default_rng(cfg.seed)``，零分布按
(N, iters, seed) 缓存，保证全档案回测可复现且不重复计算。
"""
from __future__ import annotations

import math

import numpy as np

from .contracts import ModuleResult
from .cooccurrence import build_cooccurrence
from .data_io import Draw
from .numerics import (EPS, MIN_SAMPLE, bonferroni, clip01, finite, mean,
                       normalize, safe_div, stdev)
from .points import NumberStats

N_BALLS = 80
WINDOW_MAX = 60          # 连段频率窗口上限（§4.1 的 N=30/60）
MC_ITERS_DEFAULT = 10000  # §4.1 指定的 Monte Carlo 次数
_TRIPLE_MIN = 2          # 三元组"成团"门槛：至少 2 个同期开出

# 三类连段（k=2,3,4+）
KS = (2, 3, 4)

# 零分布缓存：key=(window, iters, seed) -> {k: (mean, std)}。只读、确定性。
_NULL_CACHE: dict[tuple[int, int, int], dict[int, tuple[float, float]]] = {}


# ── 一、连段扫描 ──────────────────────────────────────────────

def _scan_runs(numbers) -> list[int]:
    """扫描升序号码中的连续段，返回每段长度（仅长度 ≥2 的段）。"""
    nums = sorted(numbers)
    runs: list[int] = []
    if not nums:
        return runs
    cur = 1
    for i in range(1, len(nums)):
        if nums[i] == nums[i - 1] + 1:
            cur += 1
        else:
            if cur >= 2:
                runs.append(cur)
            cur = 1
    if cur >= 2:
        runs.append(cur)
    return runs


def _count_runs_window(draws: list[Draw]) -> tuple[dict[int, int], int]:
    """统计窗口内各类连段次数 f_k 与总"连边"数（相邻对）。"""
    f = {k: 0 for k in KS}
    edges = 0
    for d in draws:
        for L in _scan_runs(d.numbers):
            if L >= 4:
                f[4] += 1
            else:
                f[L] += 1
            edges += L - 1
    return f, edges


# ── 二、零分布的 Monte Carlo 估计 ─────────────────────────────

def _count_runs_matrix(B: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """对 0/1 矩阵（每行一期）向量化统计 f_2 / f_3 / f_4+ 每期计数。

    连段长度（球数）= 连边数 + 1；连边 E[i] = B[i] & B[i+1]。
    对每行取 E 上"连续 True 段"的终点，其前向游程长度 FRL 即连边数，
    于是 FRL==1→2 连段、FRL==2→3 连段、FRL>=3→4+ 连段。
    """
    R, W = B.shape
    E = B[:, :-1] & B[:, 1:]                       # (R, W-1) 连边
    pos = np.arange(W - 1, dtype=np.int64)[None, :]
    # 每行最后一个 False 的位置（无则 -1），用于求前向 True 游程
    lastzero = np.maximum.accumulate(np.where(E, -1, pos), axis=1)
    frl = np.where(E, pos - lastzero, 0)
    # 连段终点：E 为 True 且右侧 E 为 False（行尾视为 False）
    shifted = np.concatenate([E[:, 1:], np.zeros((R, 1), dtype=bool)], axis=1)
    ends = E & ~shifted
    f2 = (ends & (frl == 1)).sum(axis=1)
    f3 = (ends & (frl == 2)).sum(axis=1)
    f4 = (ends & (frl >= 3)).sum(axis=1)
    return f2.astype(float), f3.astype(float), f4.astype(float)


def _null_distribution(window: int, iters: int, seed: int) -> dict[int, tuple[float, float]]:
    """Monte Carlo 估计 f_k 的零分布 (均值, 标准差)。

    零假设：每期从 80 中均匀独立抽 20。模拟 ``iters`` 个"window 期"数据集，
    统计每个数据集内各类连段总数。结果按 (window, iters, seed) 缓存。
    """
    key = (int(window), int(iters), int(seed))
    cached = _NULL_CACHE.get(key)
    if cached is not None:
        return cached

    rng = np.random.default_rng(int(seed))
    total = int(iters) * int(window)
    acc = np.empty((total, 3), dtype=float)
    chunk = 20000
    done = 0
    while done < total:
        c = min(chunk, total - done)
        rnd = rng.random((c, N_BALLS))
        idx = np.argpartition(rnd, 19, axis=1)[:, :20]   # 每行恰好 20 个
        B = np.zeros((c, N_BALLS), dtype=bool)
        B[np.arange(c)[:, None], idx] = True
        f2, f3, f4 = _count_runs_matrix(B)
        acc[done:done + c, 0] = f2
        acc[done:done + c, 1] = f3
        acc[done:done + c, 2] = f4
        done += c

    # 每个"数据集"= window 期之和
    per_sim = acc.reshape(int(iters), int(window), 3).sum(axis=1)
    out: dict[int, tuple[float, float]] = {}
    for j, k in enumerate(KS):
        col = per_sim[:, j].tolist()
        out[k] = (mean(col), stdev(col))
    _NULL_CACHE[key] = out
    return out


def _two_sided_p(z: float) -> float:
    """双侧正态 p 值 = erfc(|z|/√2)。"""
    z = finite(z, 0.0)
    return clip01(math.erfc(abs(z) / math.sqrt(2.0)))


# ── 三、三元组场 ──────────────────────────────────────────────

def _triple(n: int) -> tuple[int, int, int]:
    """循环三元组 {p−1, p, p+1}（01↔80 回绕，与 points.expand 一致）。"""
    prev = n - 1 if n > 1 else N_BALLS
    nxt = n + 1 if n < N_BALLS else 1
    return prev, n, nxt


def _current_miss(draws: list[Draw], n: int) -> int:
    for i, d in enumerate(draws):
        if n in d.numbers_set:
            return i
    return len(draws)


# ── 主入口 ────────────────────────────────────────────────────

def analyze(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg) -> ModuleResult:
    """§4.1 连号集群行为。签名严格遵循 §3.5。

    draws 必须按时序降序（最新在前）且已裁剪到目标期之前（无前视）。
    scores 覆盖全 80 号；expanded_set 只在解读/诊断中引用，不限制计算范围。
    """
    res = ModuleResult(name="cluster", scores={})
    T = len(draws)
    if T < MIN_SAMPLE:
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期，连段频率无统计意义")
        res.add("risk",
                f"- 连号集群分析：历史仅 {T} 期（<{MIN_SAMPLE}），数据不足，已跳过。",
                order=40)
        return res

    # 配置
    alpha = 0.05
    n_sims = MC_ITERS_DEFAULT
    norm_method = "rank"
    if cfg is not None:
        a = cfg.thresholds.get("alpha")
        if isinstance(a, (int, float)) and 0 < a < 1:
            alpha = float(a)
        v = cfg.thresholds.get("cluster_mc_iters")
        if isinstance(v, int) and v > 0:
            n_sims = int(v)
        nm = cfg.thresholds.get("norm_method")
        if isinstance(nm, str) and nm:
            norm_method = nm
    seed = int(cfg.seed) if cfg is not None else 42

    window = min(WINDOW_MAX, T)
    recent = draws[:window]
    recent10 = draws[:10]

    # ── 一/二：连段频率 + 显著性 ──
    f_obs, edges_win = _count_runs_window(recent)
    null = _null_distribution(window, n_sims, seed)
    z_scores: dict[int, float] = {}
    p_raw: dict[int, float] = {}
    e_k: dict[int, float] = {}
    s_k: dict[int, float] = {}
    for k in KS:
        mu, sd = null.get(k, (0.0, 0.0))
        e_k[k] = finite(mu, 0.0)
        s_k[k] = finite(sd, 0.0)
        z = safe_div(f_obs[k] - e_k[k], s_k[k], 0.0)
        z_scores[k] = finite(z, 0.0)
        p_raw[k] = _two_sided_p(z)
    pvals = [p_raw[k] for k in KS]
    adj, rejects = bonferroni(pvals, alpha)
    p_adj = {k: adj[i] for i, k in enumerate(KS)}
    sig = {k: bool(rejects[i]) for i, k in enumerate(KS)}

    # ── 三/四：三元组场 + 逐号打分 ──
    bundle = build_cooccurrence(recent, cfg=cfg)
    C = bundle.C
    ns = list(range(1, N_BALLS + 1))

    activity_raw: dict[int, float] = {}
    gap_raw: dict[int, float] = {}
    cohesion_raw: dict[int, float] = {}
    miss_map: dict[int, int] = {}
    nb_recent_map: dict[int, int] = {}

    for n in ns:
        prev, _, nxt = _triple(n)
        tri = frozenset((prev, n, nxt))
        nbs = frozenset((prev, nxt))
        # 近 10 期三元组成团命中数
        act = 0
        nb = 0
        for d in recent10:
            s = d.numbers_set
            if len(s & tri) >= _TRIPLE_MIN:
                act += 1
            if s & nbs:
                nb += 1
        activity_raw[n] = float(act)
        nb_recent_map[n] = nb

        st = base_stats.get(n) if base_stats else None
        if st is not None and isinstance(getattr(st, "miss", None), int):
            miss = int(st.miss)
        else:
            miss = _current_miss(draws, n)
        miss_map[n] = miss

        # 未补的连号缺口：邻居热（近 10 期有出现）而本号连失越久 → 回补预期越强
        gap_raw[n] = float(nb) * float(miss)

        # 集群内凝聚力：与两侧邻居的共现强度（循环）
        cohesion_raw[n] = float(C[n][prev] + C[n][nxt])

    act_n = normalize([activity_raw[n] for n in ns], norm_method)
    gap_n = normalize([gap_raw[n] for n in ns], norm_method)
    coh_n = normalize([cohesion_raw[n] for n in ns], norm_method)

    scores: dict[int, float] = {}
    for i, n in enumerate(ns):
        scores[n] = clip01(0.45 * act_n[i] + 0.35 * gap_n[i] + 0.20 * coh_n[i])
    res.scores = scores

    # ── 诊断 ──
    # 全 80 号秩归一：拓展集合仅用于解读，不限制计算范围（§3.5 契约）。
    hot_cut = sorted(range(80), key=lambda i: -act_n[i])  # 0-based 名次
    hot_top20 = {ns[i] for i in hot_cut[:16]}             # 前 20%
    expanded_in_hot = len(set(expanded_set) & hot_top20)

    full_f, full_edges = _count_runs_window(draws)
    pair_rate_recent = safe_div(edges_win, window, 0.0)
    pair_rate_full = safe_div(full_edges, T, 0.0)

    top_active = sorted(ns, key=lambda n: (-activity_raw[n], n))[:5]
    top_gap = sorted(ns, key=lambda n: (-gap_raw[n], n))[:5]
    top_coh = sorted(ns, key=lambda n: (-cohesion_raw[n], n))[:5]

    res.metrics = {
        "T": T,
        "window": window,
        "f_obs": {str(k): f_obs[k] for k in KS},
        "E_null": {str(k): round(e_k[k], 3) for k in KS},
        "sigma_null": {str(k): round(s_k[k], 3) for k in KS},
        "cluster_z": {str(k): round(z_scores[k], 3) for k in KS},
        "pair_rate_recent": round(pair_rate_recent, 3),
        "pair_rate_full": round(pair_rate_full, 3),
        "top_active": [(n, int(activity_raw[n])) for n in top_active],
        "top_gap": [(n, int(gap_raw[n]), miss_map[n]) for n in top_gap],
        "top_cohesion": [(n, int(cohesion_raw[n])) for n in top_coh],
        "top_scores": res.top(10),
    }
    res.diagnostics = {
        "mc_iters": n_sims,
        "window": window,
        "alpha": alpha,
        "p_raw": {str(k): round(p_raw[k], 4) for k in KS},
        "p_bonferroni": {str(k): round(p_adj[k], 4) for k in KS},
        "significant": {str(k): sig[k] for k in KS},
        "expanded_size": len(expanded_set),
        "expanded_in_hot_quintile": expanded_in_hot,
        "signal_strong": float(cfg.thresholds.signal_strong) if cfg is not None
        and isinstance(cfg.thresholds.signal_strong, (int, float)) else 0.70,
    }

    # ── narrative（真实数值取自 metrics）──
    z_txt = "、".join(f"{k}连段 z={z_scores[k]:+.2f}(f={f_obs[k]},E={e_k[k]:.1f})"
                      for k in KS)
    res.add("macro",
            f"- **连段结构**（近 {window} 期）：{z_txt}；"
            f"平均每期连边 {pair_rate_recent:.2f}（全样本 {pair_rate_full:.2f}）。",
            order=20)
    sig_txt = "、".join(f"{k}连段" for k in KS if sig[k]) or "无"
    res.add("macro",
            f"- **成团最活跃三元组**："
            f"{'、'.join(f'{n:02d}（近10期成团{int(activity_raw[n])}次）' for n in top_active)}；"
            f"Bonferroni 校正后显著偏离零假设的档位：{sig_txt}（α={alpha}）。",
            order=21)
    res.add("macro",
            f"- **未补连号缺口**（邻居热、本号久缺）："
            f"{'、'.join(f'{n:02d}(缺{miss_map[n]}期)' for n in top_gap)}；"
            f"凝聚力最高（与两侧邻居共现最强）的号码："
            f"{'、'.join(f'{n:02d}(C={int(cohesion_raw[n])})' for n in top_coh)}。",
            order=22)

    if not any(sig.values()):
        res.add("risk",
                f"- 连号集群：近 {window} 期各档连段频率均未显著偏离 i.i.d. 零假设"
                f"（最小校正 p={min(p_adj.values()):.3f}≥α={alpha}），"
                f"H3 集群信号按噪声对待。", order=40)
    if expanded_in_hot == 0 and expanded_set:
        res.add("risk",
                "- 连号集群：拓展集合内无号码落入十期成团活跃度前 20%，"
                "本模块对该点位不提供集群侧支持。", order=41)

    return res
