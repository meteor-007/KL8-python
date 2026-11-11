# -*- coding: utf-8 -*-
"""复变函数分析（§4.8）→ H4（与 §4.2 cyclic 先几何平均，见 §4.14）。

**v1.0 缺陷（§4.8 原文）**：构造 z[t] = x_n[t] + i·y_n[t]（x 为 0/1 命中，
y 为场域能量）。arg(z)=atan2(y,x) 在 x=0（约 75% 期数）且 y>0 时**恒等于 π/2**，
与 y 取值无关，相位序列退化成常数加跳变，所谓"旋转趋势/相位上扬"无从判定。

**v2.0 修正（严格按规格）**：

1. 主路径（纯 FFT，与 §4.2 互验）：对实序列 x_n[t] 做 ``np.fft.rfft``，
   取功率谱 P[k]=|X[k]|²；**前置**仅对通过 Ljung-Box 的号码做谱分析
   （否则纯噪声也能得到"主频"）；主频 k* 取谱峰，谱平坦度 SF=几何均值/算术均值。
2. 解析信号路径：z[t]=hilbert(x_n[t])，|z| 为瞬时幅度包络，
   unwrap(arg z) 为展开相位；"相位上扬"定义为 d(phase)/dt>0 且持续 ≥3 期。
3. 相位共振：多个号主频一致且相位差 < π/4 → 共振群。
4. 打分：主频显著 + 相位一阶差分>0 的号得分高；谱平坦（白噪）记 0。

数值稳健（§3.6）：x_n 全 0 时 hilbert 返回全 0、相位未定义 → 该号记 0；
所有除法/对数走 numerics，退化输入不抛异常、不产生 nan/inf。
"""
from __future__ import annotations

import math

import numpy as np

from .contracts import ModuleResult
from .data_io import Draw
from .numerics import (EPS, MIN_SAMPLE, bh_fdr, clip01, finite, mean,
                       safe_div, safe_log)
from .points import NumberStats

# ── 模块常量 ────────────────────────────────────────────────────────────
LB_LAG = 20            # Ljung-Box 滞后阶数（§4.2 / §4.8）
# 谱平坦度阈值。规格曰"SF→1 表示白噪"，那是**平滑谱**的性质；本模块用原始
# 周期图 P[k]=|X[k]|²，白噪声下各频点独立指数分布，E[geo/arith]=e^{−γ}≈0.5615。
# 故把"白噪基线"校准到该值：SF ≥ 基线即判白噪，不加分记 0（§4.8 步骤 4）。
WHITE_SF = 0.56        # ≈ e^{−γ}，原始周期图的白噪基线
PHASE_MIN_RUN = 3      # "相位上扬"要求连续 ≥3 期一阶差分 > 0（§4.8 定义）
RESONANCE_TOL = math.pi / 4.0   # 相位共振的相位差容差（§4.8）
PY_TAU = 2.0 * math.pi


# ── 工具 ────────────────────────────────────────────────────────────────
def _cfg_get(cfg, key: str, default):
    """从 config.thresholds 取键，缺失/为 None 时回退默认。"""
    try:
        if cfg is None:
            return default
        th = getattr(cfg, "thresholds", None)
        val = getattr(th, key, None)
        return default if val is None else val
    except Exception:
        return default


def _ljung_box(x: np.ndarray, lag: int) -> tuple[float, float]:
    """Ljung-Box 白噪声检验（§4.2 前置）。返回 (Q, p)。

    Q = N(N+2)·Σ_{k=1..h} r_k²/(N−k)，H0 下近似 χ²(h)。
    N ≤ h+1 或序列恒定（方差为 0，自相关无定义）→ p=1（无结构）。
    """
    n = int(x.size)
    if n < lag + 2:
        return 0.0, 1.0
    xc = x - x.mean()
    denom = float(np.dot(xc, xc))
    if denom < EPS:
        return 0.0, 1.0
    acc = 0.0
    for k in range(1, lag + 1):
        num = float(np.dot(xc[k:], xc[:-k]))
        rk = safe_div(num, denom, 0.0)
        acc += safe_div(rk * rk, float(n - k), 0.0)
    q = finite(n * (n + 2) * acc, 0.0)
    try:
        from scipy.stats import chi2
        p = float(chi2.sf(q, lag))
    except Exception:
        return q, 1.0
    return q, clip01(finite(p, 1.0))


def _fisher_g(power: np.ndarray) -> tuple[float, int, float]:
    """Fisher 隐周期检验，返回 (g, 谱峰下标, p 值)。

    g = max P[k] / Σ P[k]。H0（白噪）下功率谱各分量独立指数分布，故
      P(G ≥ g) = Σ_{j=1}^{⌊1/g⌋} (−1)^{j−1} C(K,j)(1 − j·g)^{K−1}。
    该 p 值即"主频显著"的判据（已内建对搜索频点数 K 的校正）。
    """
    k = int(power.size)
    if k < 2:
        return 0.0, 0, 1.0
    total = float(power.sum())
    if total < EPS:
        return 0.0, 0, 1.0
    idx = int(np.argmax(power))
    g = clip01(safe_div(float(power[idx]), total, 0.0))
    if g <= 0.0:
        return 0.0, idx, 1.0
    p = 0.0
    jmax = int(min(math.floor(safe_div(1.0, g, 1.0)), 100))
    try:
        for j in range(1, jmax + 1):
            term = 1.0 - j * g
            if term <= 0.0:
                break
            comb = math.comb(k, j) if j <= k else 0.0
            p += ((-1.0) ** (j - 1)) * comb * (term ** (k - 1))
    except (OverflowError, ValueError):
        return g, idx, 1.0
    return g, idx, clip01(finite(p, 1.0))


def _spectral_flatness(power: np.ndarray, eps: float = 1e-9) -> float:
    """谱平坦度 SF = 几何均值 / 算术均值 ∈ [0,1]。SF→1 白噪，SF→0 单峰。"""
    n = int(power.size)
    if n < 2:
        return 1.0
    logs = [safe_log(float(v) + eps, 0.0) for v in power]
    gm = math.exp(mean(logs))
    am = mean([float(v) for v in power]) + eps
    return clip01(safe_div(gm, am, 0.0))


def _phase_uplift(xc: np.ndarray) -> tuple[float, float]:
    """解析信号路径（§4.8 步骤 2）。返回 (上扬占比, 是否持续上扬)。

    z[t] = hilbert(xc[t])（去均值，避免直流分量把相位压成常数——这正是
    v1.0 相位退化的同源问题）；unwrap(arg z) 为展开相位；
    一阶差分 dφ/dt > 0 表示相位上扬，"持续 ≥3 期"要求末 3 个差分同为正。
    """
    try:
        from scipy.signal import hilbert
        z = hilbert(xc)
        phase = np.unwrap(np.angle(z))
        d = np.diff(phase)
    except Exception:
        return 0.0, 0.0
    if d.size == 0:
        return 0.0, 0.0
    width = int(max(PHASE_MIN_RUN, min(20, d.size // 2 or PHASE_MIN_RUN)))
    recent = d[-width:]
    uplift = float(np.mean(recent > 0.0)) if recent.size else 0.0
    # "持续 ≥3 期"：最近窗口内存在一段长度 ≥ PHASE_MIN_RUN 的连续正差分
    best = cur = 0
    for v in recent:
        cur = cur + 1 if v > 0.0 else 0
        if cur > best:
            best = cur
    sustained = 1.0 if best >= PHASE_MIN_RUN else 0.0
    return clip01(uplift), sustained


def _circular_dev(a: float, b: float) -> float:
    """两角度的圆周距离 ∈ [0, π]。"""
    diff = (a - b) % PY_TAU
    return abs(diff - PY_TAU if diff > math.pi else diff)


# ── 主入口 ──────────────────────────────────────────────────────────────
def analyze(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg) -> ModuleResult:
    """复变/傅里叶频谱分析（§4.8）。

    draws 已按时序降序（最新在前），且由调用方裁剪到目标期之前（无前视，§9.2）。
    expanded_set 不限制计算范围——本模块对全 80 号给出判断，只在推荐阶段筛集合
    （见 contracts.ModuleResult 与 §3.5；若限定在集合内，§9.5 的 lift_exp 检验
    会退化为恒等式）。
    """
    name = "complex_fft"
    T = len(draws)
    alpha_lb = float(_cfg_get(cfg, "cyclic_alpha", 0.05) or 0.05)

    # 退化输入：历史不足（§3.6 样本量下限）
    if T < MIN_SAMPLE:
        res = ModuleResult(name=name, scores={})
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期")
        res.add("risk", f"- 复变/傅里叶分析：历史仅 {T} 期，样本不足，已跳过。")
        return res

    # 0/1 命中矩阵（时序升序，供 FFT/Hilbert 使用；最新一期在末尾）
    chrono = list(reversed(draws))
    hits = np.zeros((T, 81), dtype=float)
    for t, d in enumerate(chrono):
        for n in d.numbers:
            if 1 <= n <= 80:
                hits[t, n] = 1.0

    lag = int(min(LB_LAG, max(2, T // 5)))
    raw: dict[int, float] = {}          # 通检验号码的原始分
    signif: dict[int, float] = {}       # 主频显著性 = 1 − p_Fisher
    k_star: dict[int, int] = {}
    t_star: dict[int, float] = {}
    sf_map: dict[int, float] = {}
    g_map: dict[int, float] = {}         # Fisher g = 谱峰占谱总能量比
    pval: dict[int, float] = {}
    phase_ang: dict[int, float] = {}
    sustained_map: dict[int, float] = {}

    n_const = 0            # 恒定序列（全 0 / 全 1）
    n_lb_fail = 0          # 未通过 Ljung-Box
    n_white = 0            # 谱平坦（白噪）
    n_short = 0            # 频点数不足

    for n in range(1, 81):
        x = hits[:, n]
        s = float(x.sum())
        if s <= 0.0 or s >= T:            # 从未开出 / 期期开出：方差为 0
            n_const += 1
            continue

        _, p_lb = _ljung_box(x, lag)
        if p_lb > alpha_lb:              # 前置：未通过白噪声检验 → 判定无周期
            n_lb_fail += 1
            continue

        xc = x - x.mean()
        spec = np.fft.rfft(xc)
        power = np.abs(spec) ** 2
        k_nyq = 1 if T % 2 == 0 else 0   # 偶数长度时弃用 Nyquist 频点
        if power.size - 1 - k_nyq < 2:
            n_short += 1
            continue
        puse = power[1:power.size - k_nyq] if k_nyq else power[1:]

        g, kidx, p_g = _fisher_g(puse)
        sg = clip01(1.0 - p_g)

        sf = _spectral_flatness(puse)
        if sf >= WHITE_SF:               # 白噪：不加分，记 0（§4.8 步骤 4）
            n_white += 1
            continue

        up, sus = _phase_uplift(xc)
        pf = clip01(0.5 * up + 0.5 * sus)   # ∈ [0,1]，持续上扬 → 1

        k = int(kidx + 1)                # 频点下标（0 为直流，已剔除）
        raw[n] = clip01(sg * pf)
        signif[n] = sg
        k_star[n] = k
        t_star[n] = safe_div(float(T), float(k), float(T))
        sf_map[n] = sf
        g_map[n] = g
        pval[n] = p_g
        phase_ang[n] = float(np.angle(spec[k]))
        sustained_map[n] = sus

    # ── 显著性诊断（§3.5 / §4.0）：对全部受检号做 BH-FDR 校正 ──
    # 未进入谱分析的号（LB 未过 / 白噪 / 频点不足）按 p=1 计入族，保持保守。
    fam_p = [1.0] * 80
    for n, p in pval.items():
        fam_p[n - 1] = p
    qvals, rejects = bh_fdr(fam_p, q=0.05)
    q_map = {n: qvals[n - 1] for n in range(1, 81)}
    fdr_sig = sorted(n for n in range(1, 81) if rejects[n - 1])

    # ── 相位共振（§4.8 步骤 3）：主频一致 + 相位差 < π/4 ──
    resonance: dict[int, float] = {}
    resonant_groups: list[list[int]] = []
    by_freq: dict[int, list[int]] = {}
    for n in raw:
        by_freq.setdefault(k_star[n], []).append(n)
    for k, members in by_freq.items():
        if len(members) < 2:
            continue
        cos_m = mean([math.cos(phase_ang[m]) for m in members])
        sin_m = mean([math.sin(phase_ang[m]) for m in members])
        mu = math.atan2(sin_m, cos_m)
        if max(_circular_dev(phase_ang[m], mu) for m in members) < RESONANCE_TOL:
            resonant_groups.append(sorted(members))
            for m in members:
                resonance[m] = 1.0

    # 共振仅放大已有显著性的号（不凭空造分）
    final_raw: dict[int, float] = {}
    for n in raw:
        bonus = 0.15 * signif[n] * resonance.get(n, 0.0)
        final_raw[n] = clip01(raw[n] + bonus)

    # ── 打分：raw 已是 [0,1] 有界量，直接用原值 ──
    # §4.0 的归一化针对 z_score/危险率/邻居数这类**无界**量；本模块的
    # raw = 主频显著性 × 相位上扬因子 天然落在 [0,1]，再做秩归一会把
    # 仅 3 个候选中显著性 p=0.46 的噪声号抬到 1.0，制造虚假强信号。
    # 故直接输出有界原值；未通过 Ljung-Box 的号恒为 0（§4.8 前置）。
    full_scores = {n: clip01(finite(final_raw.get(n, 0.0), 0.0))
                   for n in range(1, 81)}
    keys = sorted(final_raw)
    top = sorted(keys, key=lambda n: (-full_scores[n], n))[:10]

    res = ModuleResult(name=name, scores=full_scores)
    res.metrics = {
        "T": T,
        "lb_lag": lag,
        "n_candidates": len(raw),                     # 通过 Ljung-Box 的号数
        "n_scored": sum(1 for n in keys if full_scores[n] > 0.0),
        "top10": [(n, round(full_scores[n], 3)) for n in top],
        "top_periods": [(n, round(t_star[n], 1), k_star[n],
                         round(pval[n], 3)) for n in top[:5]],
        "resonant_groups": resonant_groups,
        "median_flatness": round(mean(list(sf_map.values())), 4) if sf_map else 0.0,
        "median_peak_ratio": round(mean(list(g_map.values())), 4) if g_map else 0.0,
        "fdr_significant_numbers": fdr_sig,
    }
    res.diagnostics = {
        "constant_series": n_const,
        "ljung_box_failed": n_lb_fail,
        "white_noise_flat": n_white,
        "too_few_bins": n_short,
        "with_period_structure": len(raw),
        "alpha_ljung_box": round(alpha_lb, 3),
        "white_sf_threshold": WHITE_SF,
        "n_fdr_significant": len(fdr_sig),
        "fdr_q_min": round(min(q_map.values()), 4) if q_map else 1.0,
    }

    if not keys:
        res.degrade(
            f"80 号中无通过 Ljung-Box(α={alpha_lb}) 且非白噪的周期结构")
        res.add("risk",
                f"- 复变/傅里叶分析：{n_lb_fail} 号未通过 Ljung-Box、"
                f"{n_white} 号谱平坦（白噪）、{n_const} 号序列恒定，"
                f"无一号呈现显著周期，本模块判定无有效信号。", order=41)
        return res

    top_period = sorted(keys, key=lambda n: (-signif[n], n))[:5]
    res.add("macro",
            f"- **频谱主频**（T={T} 期，Ljung-Box 滞后 {lag}，α={alpha_lb}）："
            f"{len(raw)}/{80} 号通过白噪声检验，"
            f"其中 {'、'.join(f'{n:02d}(周期≈{t_star[n]:.1f}期,p={pval[n]:.3f})' for n in top_period)}。",
            order=22)
    if resonant_groups:
        grp = max(resonant_groups, key=len)
        res.add("macro",
                f"- **相位共振群**：主频一致且相位差 < π/4 的号群共 "
                f"{len(resonant_groups)} 组，最大一组为 "
                f"{'、'.join(f'{m:02d}' for m in grp)}（主频一致）。", order=23)
    else:
        res.add("macro",
                "- **相位共振**：未发现主频一致且相位差 < π/4 的号码群，"
                "当前周期结构各自独立。", order=23)
    rising = [n for n in keys if sustained_map[n] >= 1.0]
    res.add("risk",
            f"- 复变/傅里叶：{n_lb_fail} 号白噪声检验未过、{n_white} 号谱平坦"
            f"（白噪记 0）、{n_const} 号序列恒定；相位持续上扬（≥{PHASE_MIN_RUN} 期）"
            f"的号 {len(rising)} 个"
            f"{'（' + '、'.join(f'{n:02d}' for n in sorted(rising)[:8]) + '）' if rising else ''}。",
            order=42)
    res.add("risk",
            f"- 多重检验校正：对全部受检号做 BH-FDR(q=0.05) 后，"
            f"{len(fdr_sig)} 号主频仍显著"
            f"{'（' + '、'.join(f'{n:02d}' for n in fdr_sig[:8]) + '）' if fdr_sig else ''}"
            f"；最小 q 值 {min(q_map.values()):.3f}，无显著号时融合层应对本模块降权。",
            order=43)
    return res
