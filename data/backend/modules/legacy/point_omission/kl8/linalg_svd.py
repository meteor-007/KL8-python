# -*- coding: utf-8 -*-
"""线性代数与矩阵分析（§4.7）→ H5 共现/图（与 §4.9 在维度内聚合）。

四件套：
  1. 共现矩阵 C — 复用 §6.2 的 CooccurrenceBundle（**不重复计算**，§4.7 第 1 条）
  2. Jaccard J 与 PMI — 由 bundle 惰性提供
  3. 列中心化命中矩阵 X[T×80] 的 SVD（结构分析）与协方差矩阵 Σ
  4. 条件概率 P(B|A) = C[A][B] / f_A（"跟随"筛选）

打分（§4.7 v2.0，修正 v1.0 的量纲错误）::

    raw[n] = PMI_norm(n) · Σ_{j≤k} |V[n, j]|

其中
  - ``Σ_{j≤k} |V[n, j]|`` 是前 k 个右奇异向量在该号上的**载荷幅度**（有界），
  - ``PMI_norm(n) = normalize( Σ_{m ∈ 拓展集合, PMI(n,m) > 0} PMI(n,m) ) ∈ [0,1]``。

v1.0 的 ``载荷 × 邻居数`` 中"邻居数是计数"会支配"载荷无量纲"，量纲不一致；v2.0
两项均为有界量，量纲一致。raw 再按 §4.0 在**全 80 号**上归一化（默认 rank）到 [0,1]。

关于 §4.7 第 5 条的 v1.0 矛盾：v2.0 明确**保留列中心化用于结构分析，但不再声称
第一主成分是热度因子**（热度已由 H1 单独承担）。本模块不输出任何"热度因子"解释。

关于 §4.0 / §3.5：模块对**全 80 号**给出判断，拓展集合只用于定义 PMI 邻域
（**不用于限制计算范围**）；融合阶段才由 ensemble 调 ``masked_scores()`` 遮罩集合外号码。

无前视：仅使用传入的 draws（调用方已裁剪到目标期之前）。SVD 为性能热点，
按 draws 的期号序列缓存（同一次运行内多个调用方复用同一对象）。
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np

from .contracts import ModuleResult
from .cooccurrence import build_cooccurrence
from .data_io import NUM_BALLS, Draw
from .numerics import (EPS, MIN_SAMPLE, bh_fdr, bonferroni, clip01, finite,
                       normalize)
from .points import NumberStats

# 参与载荷累加的右奇异向量个数（§4.7 的 k）。配置缺省项，可用
# thresholds.svd_components 覆盖，但会按数值秩降阶。
DEFAULT_COMPONENTS = 10
CACHE_SIZE = 4

# draws → (bundle, Xc, U, S, Vt) 的小型 LRU，键为期号序列（确定性、无前视）。
_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()


# ── 配置读取（cfg 可为 None，全部带兜底）────────────────────────
def _norm_method(cfg) -> str:
    try:
        m = cfg.thresholds.norm_method
    except Exception:
        m = None
    return m or "rank"


def _alpha(cfg, default: float = 0.05) -> float:
    try:
        a = cfg.thresholds.alpha
    except Exception:
        a = None
    try:
        return float(a) if a is not None else default
    except (TypeError, ValueError):
        return default


def _fdr_method(cfg) -> str:
    try:
        m = cfg.thresholds.fdr_method
    except Exception:
        m = None
    return m or "bh"


def _n_components(cfg, rank: int) -> int:
    try:
        v = cfg.thresholds.get("svd_components", DEFAULT_COMPONENTS)
    except Exception:
        v = DEFAULT_COMPONENTS
    try:
        k = int(v)
    except (TypeError, ValueError):
        k = DEFAULT_COMPONENTS
    return max(1, min(k, rank)) if rank > 0 else 0


# ── 矩阵构造与分解 ────────────────────────────────────────────
def _hit_matrix(draws: list[Draw]) -> np.ndarray:
    """命中矩阵 X[T×80]，行=期（顺序不影响列结构），列=号 1..80。"""
    T = len(draws)
    X = np.zeros((T, NUM_BALLS), dtype=float)
    for t, d in enumerate(draws):
        for n in d.numbers:
            if 1 <= n <= NUM_BALLS:
                X[t, n - 1] = 1.0
    return X


def _centered_svd(X: np.ndarray):
    """列中心化后做 SVD，返回 (Xc, U, S, Vt)。

    符号固定（§4.7 第 5 条）：每个右奇异向量的**绝对值最大分量为正**，
    保证跨实现可复现。秩亏 / 分解失败时降阶返回，不抛异常（§3.6）。
    """
    T, m = X.shape
    col_mean = X.mean(axis=0) if T > 0 else np.zeros(m)
    Xc = X - col_mean
    if T == 0 or m == 0:
        return Xc, np.zeros((T, 0)), np.zeros(0), np.zeros((0, m))
    try:
        U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    except np.linalg.LinAlgError:
        return Xc, np.zeros((T, 0)), np.zeros(0), np.zeros((0, m))
    for j in range(Vt.shape[0]):
        if Vt.shape[1] == 0:
            break
        idx = int(np.argmax(np.abs(Vt[j])))
        if Vt[j, idx] < 0.0:
            Vt[j] = -Vt[j]
            if j < U.shape[1]:
                U[:, j] = -U[:, j]
    return Xc, U, S, Vt


def _cached(draws: list[Draw], cfg) -> dict:
    key = tuple(d.period for d in draws)
    entry = _CACHE.get(key)
    if entry is not None:
        _CACHE.move_to_end(key)
        return entry
    bundle = build_cooccurrence(draws, cfg)
    X = _hit_matrix(draws)
    Xc, U, S, Vt = _centered_svd(X)
    entry = {"bundle": bundle, "X": X, "Xc": Xc, "U": U, "S": S, "Vt": Vt}
    _CACHE[key] = entry
    while len(_CACHE) > CACHE_SIZE:
        _CACHE.popitem(last=False)
    return entry


def _covariance(Xc: np.ndarray, T: int) -> np.ndarray:
    """Σ = Cov(X)（样本协方差，除以 T−1）。主对角为方差，非对角为协同波动。"""
    if T <= 1:
        return np.zeros((NUM_BALLS, NUM_BALLS))
    return (Xc.T @ Xc) / float(T - 1)


def _top_pairs(mat, topn: int = 5, absolute: bool = False) -> list[tuple[int, int, float]]:
    """取上三角中数值最大的 topn 对（返回 1-based 号对）。"""
    arr = np.asarray(mat, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        return []
    if arr.shape[0] == NUM_BALLS + 1:
        arr = arr[1:, 1:]
    N = arr.shape[0]
    if N < 2:
        return []
    iu = np.triu_indices(N, 1)
    vals = np.abs(arr[iu]) if absolute else arr[iu]
    if vals.size == 0:
        return []
    k = min(topn, vals.size)
    idx = np.argsort(-vals, kind="stable")[:k]
    return [(int(iu[0][t]) + 1, int(iu[1][t]) + 1, finite(vals[t], 0.0))
            for t in idx]


def _pair_association(bundle, alpha: float, fdr_method: str) -> dict:
    """成对关联的显著性诊断（§3.6：期望频数 < 5 的成对跳过）。

    2×2 表 n11 = C[i][j]，E[n11] = f_i·f_j / T，
    Var[n11] = f_i f_j (T−f_i)(T−f_j) / (T²(T−1))。正态近似求 z / 双侧 p，再 BH-FDR。
    """
    N = NUM_BALLS
    T = int(bundle.T)
    out = {"pairs_tested": 0, "pairs_skipped_low_expected": 0,
           "pairs_skipped_degenerate": 0, "sig_raw": 0, "sig_fdr": 0,
           "method": fdr_method}
    if T <= 1:
        return out

    f = bundle.count[1:]
    C = bundle.C[1:, 1:]
    iu = np.triu_indices(N, 1)
    c = C[iu]
    fi, fj = f[iu[0]], f[iu[1]]
    e = fi * fj / float(T)
    var = fi * fj * (T - fi) * (T - fj) / float(T * T * (T - 1))

    valid = (var > EPS) & (e >= 5.0)
    out["pairs_skipped_low_expected"] = int(((e < 5.0) & (var > EPS)).sum())
    out["pairs_skipped_degenerate"] = int((var <= EPS).sum())
    if not bool(valid.any()):
        return out

    z = np.zeros_like(c)
    z[valid] = (c[valid] - e[valid]) / np.sqrt(var[valid])
    # 双侧 p 值：用 math.erfc 逐元素计算，避免引入重量级的 scipy.stats 导入。
    plist = [finite(math.erfc(abs(v) / math.sqrt(2.0)), 1.0)
             for v in z[valid].tolist()]

    out["pairs_tested"] = int(valid.sum())
    out["sig_raw"] = int((np.abs(z[valid]) >= 3.0).sum())
    if fdr_method == "bonferroni":
        _, rej = bonferroni(plist, alpha)
    else:
        _, rej = bh_fdr(plist, alpha)
    out["sig_fdr"] = int(sum(1 for r in rej if r))
    return out


# ── 主入口 ────────────────────────────────────────────────────
def analyze(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg) -> ModuleResult:
    """§4.7 线性代数与矩阵分析。draws 最新在前且已裁剪到目标期之前（无前视）。

    base_stats 保留以符合 §3.5 统一签名；本模块不消费它。
    """
    res = ModuleResult(name="linalg_svd", scores={})
    T = len(draws)
    if T < MIN_SAMPLE:
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期，SVD/协方差不可靠")
        res.add("risk",
                f"- 线性代数分析：历史仅 {T} 期，样本不足（< {MIN_SAMPLE}），"
                f"已跳过并归零（§3.6）。", order=50)
        return res

    method = _norm_method(cfg)
    alpha = _alpha(cfg)
    fdr_method = _fdr_method(cfg)

    entry = _cached(draws, cfg)
    bundle = entry["bundle"]
    Vt = entry["Vt"]
    S = entry["S"]
    Xc = entry["Xc"]

    rank = int(Vt.shape[0])
    k = _n_components(cfg, rank)

    # ── 1) PMI_norm(n)：拓展集合邻域内的正 PMI 之和，再归一化到 [0,1] ──
    seeds = sorted({m for m in expanded_set if 1 <= m <= NUM_BALLS})
    PMI = bundle.PMI
    if seeds:
        sub = PMI[np.ix_(range(1, NUM_BALLS + 1), seeds)]     # 80×|seeds|
        pmi_raw = np.maximum(sub, 0.0).sum(axis=1)            # 对角 PMI[n][n]=0
    else:
        pmi_raw = np.zeros(NUM_BALLS)
    pmi_norm = normalize(pmi_raw.tolist(), method)

    # ── 2) 载荷幅度 Σ_{j≤k} |V[n, j]|（有界，≤√k）──
    if k > 0:
        load = np.abs(Vt[:k]).sum(axis=0)
    else:
        load = np.zeros(NUM_BALLS)

    # ── 3) raw = PMI_norm · 载荷，再在**全 80 号**上归一化（§4.0）──
    raw = [finite(pmi_norm[i], 0.0) * finite(float(load[i]), 0.0)
           for i in range(NUM_BALLS)]
    score_list = normalize(raw, method)
    res.scores = {n: clip01(score_list[n - 1]) for n in range(1, NUM_BALLS + 1)}

    # ── 派生矩阵与诊断量 ──
    cov = _covariance(Xc, T)
    S2 = S ** 2 if S.size else np.zeros(0)
    total_energy = float(S2.sum())
    if k > 0 and total_energy > EPS:
        energy_k = float(S2[:k].sum() / total_energy)
        evr = [round(float(v / total_energy), 4) for v in S2[:5]]
    else:
        energy_k, evr = 0.0, []

    diag = np.diag(cov)
    sigma2 = float(diag.mean()) if diag.size else 0.0
    gamma = float(NUM_BALLS) / float(T - 1) if T > 1 else 0.0
    mp_edge = sigma2 * (1.0 + math.sqrt(gamma)) ** 2 if gamma > 0 else 0.0
    eig_max = float(S2[0]) / float(T - 1) if (T > 1 and S2.size) else 0.0
    structure_sig = bool(mp_edge > EPS and eig_max > mp_edge)

    # 条件概率 P(B|A) = C[A][B] / f_A（行归一，分母为 0 的行保持 0）
    CP = np.zeros((NUM_BALLS + 1, NUM_BALLS + 1))
    f = bundle.count
    nz = f > EPS
    if bool(nz.any()):
        CP[nz, :] = bundle.C[nz, :] / f[nz][:, None]

    cov_abs = np.abs(cov)
    np.fill_diagonal(cov_abs, 0.0)

    assoc = _pair_association(bundle, alpha, fdr_method)
    zero_count = int((f[1:] <= 0).sum())
    pmi_zero_pairs = int((np.triu(bundle.C[1:, 1:], 1) == 0).sum())

    top_pmi = _top_pairs(bundle.PMI, 5)
    top_jac = _top_pairs(bundle.J, 5)
    top_follow = _top_pairs(CP, 5)
    top_cov = _top_pairs(cov_abs, 3)

    top_scores = sorted(range(1, NUM_BALLS + 1),
                        key=lambda n: (-res.scores[n], n))[:5]

    res.metrics = {
        "T": T,
        "components_used": k,
        "rank": rank,
        "top_singular_values": [round(float(s), 3) for s in S[:5]],
        "explained_variance_ratio": evr,
        "energy_top_k": round(energy_k, 4),
        "eig_max": round(eig_max, 4),
        "mp_upper_edge": round(mp_edge, 4),
        "structure_significant": structure_sig,
        "top_pmi_pairs": [(i, j, round(v, 3)) for i, j, v in top_pmi],
        "top_jaccard_pairs": [(i, j, round(v, 3)) for i, j, v in top_jac],
        "top_follow_pairs": [(i, j, round(v, 3)) for i, j, v in top_follow],
        "top_covariance_pairs": [(i, j, round(v, 4)) for i, j, v in top_cov],
        "top_numbers": [(n, round(res.scores[n], 3)) for n in top_scores],
    }
    res.diagnostics = {
        "T": T,
        "components_used": k,
        "rank": rank,
        "expanded_neighbourhood": len(seeds),
        "n_zero_count": zero_count,
        "pmi_zero_pairs": pmi_zero_pairs,
        "sig_pairs_tested": assoc["pairs_tested"],
        "sig_pairs_raw_p001": assoc["sig_raw"],
        "sig_pairs_fdr": assoc["sig_fdr"],
        "pairs_skipped_low_expected": assoc["pairs_skipped_low_expected"],
        "pairs_skipped_degenerate": assoc["pairs_skipped_degenerate"],
        "eig_max": round(eig_max, 4),
        "mp_upper_edge": round(mp_edge, 4),
        "structure_significant": structure_sig,
        "alpha": alpha,
        "fdr_method": fdr_method,
    }

    # ── narrative（数值全部来自上面的 metrics）──
    verdict = "显著超越随机阵" if structure_sig else "未超越随机阵上界"
    res.add("macro",
            f"- **结构谱**：列中心化命中矩阵的前 {k} 个奇异值解释 "
            f"{energy_k:.0%} 方差；最大特征值 {eig_max:.4f} vs 随机阵上界 "
            f"{mp_edge:.4f}（{verdict}）。", order=20)
    if top_follow:
        res.add("macro",
                "- **跟随关系**（条件概率 P(B|A)，A→B）："
                + "、".join(f"{a:02d}→{b:02d}({v:.2f})" for a, b, v in top_follow[:3])
                + "。", order=21)
    if top_pmi:
        res.add("macro",
                "- **共现强度**（PMI 最高）："
                + "、".join(f"{i:02d}-{j:02d}({v:.2f})" for i, j, v in top_pmi[:3])
                + f"；BH-FDR 校正后 {assoc['sig_fdr']} 对关联显著"
                  f"（检验 {assoc['pairs_tested']} 对，α={alpha}）。", order=22)

    if not structure_sig:
        res.add("risk",
                f"- 线性代数分析：未检出超越随机矩阵的共现结构"
                f"（最大特征值 {eig_max:.4f} ≤ 上界 {mp_edge:.4f}），"
                f"H5 结论仅供参考。", order=51)
    if zero_count > 0:
        res.add("risk",
                f"- 线性代数分析：窗口内 {zero_count} 个号码从未开出，其载荷恒为 0，"
                f"得分置 0。", order=52)

    return res
