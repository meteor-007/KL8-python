# -*- coding: utf-8 -*-
"""马尔可夫链状态转移 + 隐马尔可夫（§4.5）→ H6。

状态定义（§4.5.1，**遗漏长度游程**，不是滑动窗口）：

    S0 : m = 0         （上期命中）
    S1 : m ∈ [1, 2]
    S2 : m ∈ [3, 5]
    S3 : m ∈ [6, +∞)   （长遗漏）

上一期命中 → 本期 m = 0；未命中 → m 自增。这是一条真正的**首达过程**：
从任意状态要么命中落到 S0，要么遗漏 +1 进入下一档（长遗漏留在 S3）。
v1.0 用"近 10 期命中数"定义状态会退化成滑动窗口的确定性副作用，本模块不使用。

三个产出：
  1. **各档命中率 p_k** = 该档命中次数 / 该档暴露期数，用比例检验比较是否显著
     偏离 i.i.d. 零假设的 0.25（§4.5.2 的核心检验对象）。
  2. **转移矩阵 P_n**：逐号按结构直接估计（行和恒为 1），对样本稀疏的行做
     拉普拉斯平滑（S3 行样本最少，受益最大）。
  3. **HMM 市场状态**：隐状态 = 冷静/活跃/动荡，观测 = 每期全场特征
     （连号对数、跨度、场域熵）。自实现前向-后向 + Baum-Welch（EM 随机初始化
     用 np.random.default_rng(cfg.seed)），据此对冷热偏好做状态条件调整。

打分：`raw[n] = ½·P_{t+1}(S2∪S3) + ½·P_{t+1|regime}(S2∪S3)`，全 80 号 rank 归一。
拓展集合**不用于限制计算范围**（§3.5），只在融合/推荐阶段由 ensemble 遮罩。
"""
from __future__ import annotations

import math

import numpy as np

from .contracts import ModuleResult
from .data_io import Draw
from .numerics import (EPS, MIN_SAMPLE, bh_fdr, clip01, entropy_normalized,
                       finite, fisher_or_skip, normalize, safe_div)
from .points import NumberStats

# ── 常量 ──────────────────────────────────────────────────────
N_STATES = 4
STATE_LABELS = ("S0(m=0)", "S1(m=1-2)", "S2(m=3-5)", "S3(m>=6)")
P0 = 0.25                     # i.i.d. 零假设下的单号单期命中率
SMOOTH_ALPHA = 1.0            # 转移矩阵拉普拉斯平滑强度（S3 行样本最少）
N_ZONES = 8                   # 场域数（§4.3 的 8 段切分）

HMM_STATES = 3                # 冷静 / 活跃 / 动荡
HMM_ITERS = 30
HMM_TOL = 1e-4
HMM_VAR_FLOOR = 1e-4
REGIME_PRIOR = 5.0            # 状态条件命中率向池化 p_k 收缩的强度
REGIME_NAMES = ("冷静", "活跃", "动荡")


# ── 状态与序列 ────────────────────────────────────────────────

def _bucket(m: int) -> int:
    """遗漏长度 m 的分档（§4.5.1）。"""
    if m <= 0:
        return 0
    if m <= 2:
        return 1
    if m <= 5:
        return 2
    return 3


def _state_sequence(seq: list[Draw], n: int) -> list[int]:
    """号码 n 在 seq（**按期号升序、最旧在前**）上的状态序列。

    第 t 个元素 = 第 t 期开完后的当前遗漏档位。
    """
    m = 0
    out: list[int] = []
    for d in seq:
        if n in d.numbers_set:
            m = 0
        else:
            m += 1
        out.append(_bucket(m))
    return out


# ── HMM：自实现高斯 HMM（前向-后向 + Baum-Welch） ─────────────

def _period_features(d: Draw) -> tuple[float, float, float]:
    """单期全场特征：连号对数、跨度、场域熵。"""
    nums = d.numbers
    if len(nums) >= 2:
        npairs = float(sum(1 for i in range(len(nums) - 1)
                           if nums[i + 1] - nums[i] == 1))
        span = float(nums[-1] - nums[0])
    else:
        npairs = 0.0
        span = 0.0
    zones = [0] * N_ZONES
    for x in nums:
        z = min(N_ZONES - 1, max(0, (x - 1) // 10))
        zones[z] += 1
    return npairs, span, entropy_normalized(zones)


def _forward_backward(O: np.ndarray, pi: np.ndarray, A: np.ndarray,
                      mu: np.ndarray, var: np.ndarray):
    """带缩放的前向-后向。返回 (gamma, xi_sum, loglik) 或 None。

    ξ_t(i,j) = α_t(i)·A_ij·b_j(o_{t+1})·β_{t+1}(j) / c_{t+1}，
    满足 Σ_j ξ_t(i,j) = γ_t(i)，是 Baum-Welch 的 M 步所需量。
    """
    T, _ = O.shape
    K = len(pi)
    # 对数发射概率
    logB = np.zeros((T, K))
    for k in range(K):
        diff = O - mu[k]
        logB[:, k] = -0.5 * (np.sum(np.log(2.0 * math.pi * var[k]))
                             + np.sum(diff * diff / var[k], axis=1))
    logB = np.where(np.isfinite(logB), logB, -1e9)
    shift = logB.max(axis=1, keepdims=True)
    B = np.exp(logB - shift)                       # (T,K) ∈ (0,1]

    alpha = np.zeros((T, K))
    c = np.zeros(T)
    a = pi * B[0]
    c[0] = a.sum()
    if c[0] <= EPS:
        return None
    alpha[0] = a / c[0]
    for t in range(1, T):
        a = (alpha[t - 1] @ A) * B[t]
        s = a.sum()
        if s <= EPS:
            s = EPS
        c[t] = s
        alpha[t] = a / s

    beta = np.zeros((T, K))
    beta[-1] = 1.0
    for t in range(T - 2, -1, -1):
        beta[t] = (A @ (B[t + 1] * beta[t + 1])) / c[t + 1]

    gamma = alpha * beta
    gsum = gamma.sum(axis=1, keepdims=True)
    gsum = np.where(gsum > EPS, gsum, 1.0)
    gamma = gamma / gsum

    xi_sum = np.zeros((K, K))
    if T > 1:
        w = (B[1:] * beta[1:]) / np.maximum(c[1:], EPS)[:, None]   # (T-1,K)
        xi_sum = A * (alpha[:-1].T @ w)                            # 向量化累加

    loglik = float(np.sum(np.log(np.maximum(c, EPS))) + np.sum(shift))
    if not math.isfinite(loglik) or not np.all(np.isfinite(xi_sum)):
        return None
    return gamma, xi_sum, loglik


def _fit_gaussian_hmm(O: np.ndarray, K: int, rng: np.random.Generator,
                      iters: int = HMM_ITERS, tol: float = HMM_TOL):
    """Baum-Welch EM 拟合对角高斯 HMM。返回 dict 或 None（不收敛/退化）。"""
    T, D = O.shape
    if T < 2 * K or D < 1:
        return None
    try:
        # ── 随机初始化（子 rng 显式派生，禁止全局 np.random）──
        idx = rng.choice(T, size=K, replace=False)
        mu = O[idx].copy() + rng.normal(0.0, 0.10, size=(K, D))
        var = np.tile(O.var(axis=0) + 0.10, (K, 1))
        A = np.full((K, K), 1.0 / K) + rng.random((K, K)) * 0.10
        A = A / A.sum(axis=1, keepdims=True)
        pi = np.full(K, 1.0 / K)

        prev_ll = -np.inf
        gamma = None
        ll = -np.inf
        for it in range(iters):
            out = _forward_backward(O, pi, A, mu, var)
            if out is None:
                return None
            gamma, xi_sum, ll = out
            pi = np.maximum(gamma[0], 1e-12)
            pi = pi / pi.sum()
            denom_a = xi_sum.sum(axis=1, keepdims=True) + 1e-12
            A = (xi_sum + 1e-10) / (denom_a + 1e-10 * K)
            w = np.maximum(gamma.sum(axis=0), 1e-12)
            mu = (gamma.T @ O) / w[:, None]
            for k in range(K):
                diff = O - mu[k]
                var[k] = (gamma[:, k][:, None] * diff * diff).sum(axis=0) / w[k]
            var = np.maximum(var, HMM_VAR_FLOOR)
            if not (np.all(np.isfinite(mu)) and np.all(np.isfinite(var))
                    and np.all(np.isfinite(A))):
                return None
            if math.isfinite(prev_ll) and abs(ll - prev_ll) < tol * max(1.0, abs(prev_ll)):
                break
            prev_ll = ll

        if gamma is None or not math.isfinite(ll):
            return None
        return {"pi": pi, "A": A, "mu": mu, "var": var, "gamma": gamma,
                "loglik": ll}
    except Exception:
        return None


def _regime_conditioned(cond_expo: list[list[int]], cond_hits: list[list[int]],
                        pooled_p: list[float], s: int) -> list[float]:
    """状态 s 下各遗漏档的命中率（向池化 p_k 收缩）。"""
    out = [P0] * N_STATES
    for k in range(N_STATES):
        e = cond_expo[s][k]
        h = cond_hits[s][k]
        out[k] = clip01(safe_div(h + REGIME_PRIOR * pooled_p[k],
                                 e + REGIME_PRIOR, pooled_p[k]))
    return out


# ── 主入口 ────────────────────────────────────────────────────

def _rng_seed(cfg) -> int:
    try:
        return int(cfg.seed)
    except Exception:
        return 42


def analyze(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg) -> ModuleResult:
    """§4.5 马尔可夫链状态转移 + HMM。draws 最新在前，已裁剪到目标期之前。"""
    res = ModuleResult(name="markov", scores={})
    T = len(draws)
    exp_size = len(expanded_set) if expanded_set else 0
    rng = np.random.default_rng(_rng_seed(cfg))

    if T < MIN_SAMPLE:
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期")
        res.add("risk", f"- 马尔可夫模块：历史仅 {T} 期，状态转移无法估计，已跳过。")
        res.diagnostics.update({"T": T, "expanded_size": exp_size,
                                "reason": "insufficient_history"})
        return res

    # 统一转为**升序、最旧在前**的内部时序（所有前视风险集中在这一点）
    seq = list(reversed(draws))
    ns = list(range(1, 81))

    # ── 1. 逐号状态序列 + 逐号转移计数 ──
    states_all: dict[int, list[int]] = {}
    per_trans: dict[int, np.ndarray] = {}
    global_count = np.zeros((N_STATES, N_STATES))
    pooled_expo = [0] * N_STATES
    pooled_hits = [0] * N_STATES

    for n in ns:
        st = _state_sequence(seq, n)
        states_all[n] = st
        C = np.zeros((N_STATES, N_STATES))
        for t in range(T - 1):
            a, b = st[t], st[t + 1]
            C[a, b] += 1.0
            pooled_expo[a] += 1
            if b == 0:
                pooled_hits[a] += 1
        global_count += C
        per_trans[n] = C

    total_trans = float(global_count.sum())
    if total_trans <= 0:
        res.degrade("未观测到任何状态转移")
        res.add("risk", "- 马尔可夫模块：无可用状态转移样本，已跳过。")
        res.diagnostics.update({"T": T, "expanded_size": exp_size})
        return res

    # ── 2. 各档命中率 p_k 与比例检验（§4.5.2 核心检验） ──
    pooled_p = [clip01(safe_div(pooled_hits[k], pooled_expo[k], P0))
                for k in range(N_STATES)]
    alpha = 0.05
    try:
        alpha = float(cfg.thresholds.alpha or 0.05)
    except Exception:
        pass

    pk_stats: dict[str, dict] = {}
    pvals: list[float] = []
    for k in range(N_STATES):
        e = pooled_expo[k]
        h = pooled_hits[k]
        # 与 0.25 比较的比例检验：期望频数 >=5 用卡方，否则 fisher_or_skip
        stat, p, method = fisher_or_skip(
            [[h, e - h], [P0 * e, (1.0 - P0) * e]], min_expected=5.0)
        # 精确二项检验作为权威 p 值（始终有效）
        p_exact = 1.0
        try:
            from scipy.stats import binomtest
            if e > 0:
                p_exact = float(binomtest(h, e, P0, alternative="two-sided").pvalue)
        except Exception:
            p_exact = finite(p, 1.0)
        p_exact = clip01(finite(p_exact, 1.0))
        pk_stats[STATE_LABELS[k]] = {
            "p_k": round(pooled_p[k], 4),
            "exposure": e,
            "hits": h,
            "p_value": round(p_exact, 4),
            "screen_method": method,
            "screen_p": (round(float(p), 4) if p is not None else None),
        }
        pvals.append(p_exact)

    try:
        qvals, rejects = bh_fdr(pvals, q=alpha)
    except Exception:
        qvals, rejects = [1.0] * N_STATES, [False] * N_STATES
    for i, k in enumerate(range(N_STATES)):
        pk_stats[STATE_LABELS[k]]["q_value"] = round(float(qvals[i]), 4)
        pk_stats[STATE_LABELS[k]]["reject_025"] = bool(rejects[i])
    n_sig = int(sum(rejects))
    min_q = min(qvals) if qvals else 1.0

    # ── 3. HMM 市场状态（观测 = 每期全场特征） ──
    feats = np.asarray([_period_features(d) for d in seq], dtype=float)
    fmu = feats.mean(axis=0)
    fsd = feats.std(axis=0)
    fsd = np.where(fsd > EPS, fsd, 1.0)
    O = (feats - fmu) / fsd

    hmm = _fit_gaussian_hmm(O, HMM_STATES, rng)
    hmm_ok = hmm is not None
    regime_cur = 0
    regime_probs = [1.0 / HMM_STATES] * HMM_STATES
    regime_hist: list[int] = [0] * T
    regime_names = ["未启用"] * HMM_STATES

    if hmm_ok:
        gamma = hmm["gamma"]
        regime_hist = list(np.argmax(gamma, axis=1))
        last = gamma[-1]
        regime_cur = int(np.argmax(last))
        regime_probs = [float(x) for x in last]
        # 按"活跃度"（特征 0 = 连号对数均值）命名隐状态
        order = sorted(range(HMM_STATES), key=lambda s: -float(hmm["mu"][s][0]))
        for rank, s in enumerate(order):
            regime_names[s] = REGIME_NAMES[rank]

    # ── 4. 状态条件命中率 p_{k|s} ──
    cond_expo = [[0] * N_STATES for _ in range(HMM_STATES)]
    cond_hits = [[0] * N_STATES for _ in range(HMM_STATES)]
    if hmm_ok:
        for n in ns:
            st = states_all[n]
            for t in range(T - 1):
                s = regime_hist[t]
                a = st[t]
                cond_expo[s][a] += 1
                if st[t + 1] == 0:
                    cond_hits[s][a] += 1
    cond_p = _regime_conditioned(cond_expo, cond_hits, pooled_p, regime_cur) \
        if hmm_ok else list(pooled_p)

    # ── 5. 一步预测 + 打分 ──
    raw: dict[int, float] = {}
    trans_pooled = (global_count + SMOOTH_ALPHA) / \
        (global_count.sum(axis=1, keepdims=True) + SMOOTH_ALPHA * N_STATES)
    for n in ns:
        st = states_all[n]
        k = st[-1]
        P = (per_trans[n] + SMOOTH_ALPHA) / \
            (per_trans[n].sum(axis=1, keepdims=True) + SMOOTH_ALPHA * N_STATES)
        deep_uncond = float(P[k, 2] + P[k, 3])

        if hmm_ok:
            pk_s = cond_p[k]
            row = P[k]
            nonhit = 1.0 - float(row[0])
            deep_cond = 0.0
            if nonhit > EPS:
                deep_cond = (1.0 - pk_s) * float(row[2] + row[3]) / nonhit
            else:
                deep_cond = 1.0 - pk_s
            raw[n] = 0.5 * deep_uncond + 0.5 * float(deep_cond)
        else:
            raw[n] = deep_uncond

    vals = [finite(raw[n], 0.0) for n in ns]
    method = "rank"
    try:
        method = cfg.thresholds.norm_method or "rank"
    except Exception:
        pass
    try:
        normed = normalize(vals, method)
    except Exception:
        normed = normalize(vals, "rank")
    scores = {n: clip01(normed[i]) for i, n in enumerate(ns)}
    # 契约要求：完整 scores 必须**构造时**传入（§3.5），不得构造后再赋值
    res = ModuleResult(name="markov", scores=scores)

    # ── 6. 指标与诊断 ──
    bucket_now = [0] * N_STATES
    for n in ns:
        bucket_now[states_all[n][-1]] += 1
    top10 = sorted(ns, key=lambda n: (-scores[n], n))[:10]

    res.metrics = {
        "T": T,
        "p_k": {k: round(pooled_p[i], 4) for i, k in enumerate(STATE_LABELS)},
        "state_exposure": {k: pooled_expo[i] for i, k in enumerate(STATE_LABELS)},
        "state_now": {k: bucket_now[i] for i, k in enumerate(STATE_LABELS)},
        "significant_buckets": n_sig,
        "min_q_value": round(float(min_q), 4),
        "regime": (regime_names[regime_cur] if hmm_ok else "未启用"),
        "regime_prob": round(regime_probs[regime_cur], 4),
        "top10": top10,
    }
    res.diagnostics = {
        "T": T,
        "expanded_size": exp_size,
        "transitions": int(total_trans),
        "pk_test": pk_stats,
        "hmm_backend": "builtin_baum_welch" if hmm_ok else "unavailable",
        "hmm_loglik": (round(float(hmm["loglik"]), 3) if hmm_ok else None),
        "hmm_states": HMM_STATES,
        "regime_names": regime_names,
        "transition_matrix_pooled": [
            [round(float(x), 4) for x in row] for row in trans_pooled],
        "state_labels": list(STATE_LABELS),
        "norm_method": method,
        "insufficient_data": [],
    }

    # HMM 拟合失败 → 回退纯马尔可夫并标注（§3.6：拟合不收敛 → sufficient=False）
    if not hmm_ok:
        res.sufficient = False
        res.diagnostics["degraded"] = "HMM 拟合失败/样本不足，回退纯马尔可夫"
    # 全部档位都不显著偏离 0.25 → 报告须明说"遗漏回补效应未检出"（§4.5.7）
    if n_sig == 0:
        res.diagnostics["rebound_effect"] = "not_detected"

    # ── 7. narrative ──
    pk_txt = "、".join(f"{STATE_LABELS[i].split('(')[0]}={pooled_p[i]:.3f}"
                      for i in range(N_STATES))
    res.add("macro",
            f"- **遗漏分档命中率**（理论 0.25，T={T} 期）：{pk_txt}；"
            f"BH-FDR 校正后 {n_sig}/4 个档位显著偏离 0.25（最小 q={min_q:.3f}）。",
            order=30)
    res.add("macro",
            f"- **一步预测状态分布**：当前 S0/S1/S2/S3 号码数分别为 "
            f"{'/'.join(str(x) for x in bucket_now)}，"
            f"S2∪S3（深遗漏）打分最高的号码为 "
            f"{'、'.join(f'{n:02d}' for n in top10[:5])}。",
            order=31)
    if hmm_ok:
        res.add("macro",
                f"- **市场状态（HMM）**：当前判定为「{regime_names[regime_cur]}」"
                f"（后验 {regime_probs[regime_cur]:.2f}），"
                f"状态条件命中率 S0={cond_p[0]:.3f}、S3={cond_p[3]:.3f}，"
                f"据此调整冷热偏好。",
                order=32)
    else:
        res.add("risk",
                "- 马尔可夫模块：HMM 拟合未收敛（样本不足），已回退纯马尔可夫链，"
                "H6 融合权重按 sufficient=False 处理。", order=41)
    if n_sig == 0:
        res.add("risk",
                f"- **遗漏回补效应未检出**：各档命中率 p_k（{'、'.join(f'{p:.3f}' for p in pooled_p)}）"
                f"与 0.25 无显著差异（最小 q={min_q:.3f}），"
                f"马尔可夫信号在本数据上不构成增量。", order=40)

    return res
