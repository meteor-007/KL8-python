# -*- coding: utf-8 -*-
"""波动率聚类分析（§4.10，`volatility.py`）→ H4 波动子项 + 报告 §四 风险预警。

v2.0 修正（§4.10）：**不对 0/1 伯努利序列套金融 GARCH**。v1.0 的递推式
`σ²[t] = ω + α·r[t−1]² + β·σ²[t−1]²` 把方差又平方（四次量纲、参数不可辨识），
且 `r = x − x̄` 只有两个取值、`r²` 是 `x` 的确定性变换，金融 GARCH 根本不适用
（`Ljung-Box(r²)` 实际检验的是 `x` 自身的自相关，与 §4.2 重复）。

改用与伯努利匹配的量（严格按 §4.10 步骤 1–4）：

1. **二项过度离散检验**：对每个号码，用滑动窗口 W=30 统计各窗口命中数 `h_w`。
   - i.i.d. 零假设下 `h_w ~ Bin(30, 0.25)`，期望 7.5，方差 5.625；
   - 统计量 `D = Σ(h_w − 7.5)² / 5.625`，零假设下近似 `χ²`（自由度 = 窗口数 − 1）；
   - `D` 显著大于自由度 → 存在过度离散（波动聚集）。
2. **游程拟合优度**（与 §4.2 共用实现）：连失游程长度对几何分布做卡方检验
   （期望频数 < 5 的尾格合并）。
3. **打分**：过度离散显著 **且** 当前处于"活跃簇"（最近窗口命中数高于窗口命中
   中位数）→ 加分。
4. **风险联动**：高波动号进入报告 §四 风险预警。

数值约定：全程走 `numerics`（无裸除法/对数），退化输入不抛异常；对全 80 号打分，
`expanded_set` **不用于限制计算范围**（只在融合/推荐阶段遮罩）。
"""
from __future__ import annotations

import math
from collections import Counter

from .contracts import ModuleResult
from .data_io import Draw
from .numerics import (EPS, MIN_SAMPLE, bh_fdr, bonferroni, clip01, finite,
                       mean, median, normalize, safe_div)
from .points import NumberStats

# ── §4.10 常量 ────────────────────────────────────────────────
W = 30                              # 滑动窗口长度
P_HIT = 0.25                        # 单号单期命中概率 20/80
BINOM_MEAN = W * P_HIT              # 7.5
BINOM_VAR = W * P_HIT * (1.0 - P_HIT)   # 5.625
# 至少 W 个窗口 + MIN_SAMPLE 个有效样本，才能给出有意义的过度离散判断
MIN_PERIODS = W + MIN_SAMPLE        # 60

# 打分权重（合成后仍会归一化，权重只决定相对贡献）
W_PHI = 0.45                        # 过度离散幅度
W_ACT = 0.30                        # 活跃度
W_RUNS = 0.25                       # 游程结构偏离
BONUS = 0.30                        # 显著且活跃的加分幅度


# ── 小工具 ────────────────────────────────────────────────────
def _cfg_get(cfg, section: str, key: str, default):
    """从 cfg.<section>.<key> 读配置，缺失时兜底 default。"""
    if cfg is None:
        return default
    sec = getattr(cfg, section, None)
    if sec is None:
        return default
    getter = getattr(sec, "get", None)
    if callable(getter):
        val = getter(key, None)
        return default if val is None else val
    val = getattr(sec, key, None)
    return default if val is None else val


_CHI2_SF = None


def _chi2_sf(x: float, df: int) -> float:
    """χ² 上尾概率 P(X >= x)，scipy 不可用时用 Wilson–Hilferty 正态近似回退。"""
    global _CHI2_SF
    if df <= 0:
        return 1.0
    if _CHI2_SF is None:
        try:
            from scipy.stats import chi2 as _c2
            _CHI2_SF = _c2.sf
        except Exception:
            _CHI2_SF = False
    if _CHI2_SF is not False:
        try:
            return clip01(float(_CHI2_SF(x, df)))
        except Exception:
            pass
    z = ((x / df) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))) / math.sqrt(2.0 / (9.0 * df))
    return clip01(0.5 * math.erfc(z / math.sqrt(2.0)))


def _all_series(draws: list[Draw]) -> dict[int, list[int]]:
    """一次遍历构建全部 80 号的 0/1 时序（时间升序，最旧在前）。

    draws 最新在前（§3.5），故 reversed 后索引随时间递增。逐号扫描会做
    80×T 次集合判断，这里合并为一次 T×20 次赋值。
    """
    T = len(draws)
    series = {n: [0] * T for n in range(1, 81)}
    for t, d in enumerate(reversed(draws)):
        for n in d.numbers:
            series[n][t] = 1
    return series


def _window_counts(series: list[int], w: int = W) -> list[int]:
    """滑动窗口（步长 1）命中数。窗口按时间升序，末位为最近窗口。"""
    T = len(series)
    if T < w:
        return []
    prefix = [0] * (T + 1)
    for i, x in enumerate(series):
        prefix[i + 1] = prefix[i] + x
    return [prefix[i + w] - prefix[i] for i in range(T - w + 1)]


def _overdispersion(counts: list[int], w: int = W):
    """二项过度离散检验，返回 (D, df, p_value)。

    注意：E[D] = 窗口数（每格独立期望为 1），故零假设下 D ≈ df + 1，
    用 D/df 作离散指数、χ² 上尾作显著性判据。
    """
    nw = len(counts)
    if nw <= 1 or BINOM_VAR <= EPS:
        return 0.0, 0, 1.0
    D = sum((h - BINOM_MEAN) ** 2 for h in counts) / BINOM_VAR
    df = nw - 1
    return float(D), df, _chi2_sf(D, df)


def _gaps(series: list[int]) -> list[int]:
    """相邻两次命中之间的连失长度（完整游程，不含首尾截断段）。"""
    hits = [i for i, x in enumerate(series) if x]
    return [hits[i + 1] - hits[i] - 1 for i in range(len(hits) - 1)]


def _geometric_gof(gaps: list[int], p: float = P_HIT,
                   min_expected: float = 5.0, min_samples: int = MIN_SAMPLE):
    """连失游程长度对几何分布的卡方拟合优度（§4.2 / §4.10 步骤 2）。

    几何零假设：P(L = ℓ) = p·(1−p)^ℓ。期望频数 < 5 的尾格全部合并为一格
    （§3.6：期望频数 < 5 需合并或改用精确检验）。

    返回 (chi2, df, p_value, method)；样本不足或无法分箱时 chi2 为 None。
    """
    N = len(gaps)
    if N < min_samples or p <= 0.0 or p >= 1.0:
        return None, 0, 1.0, "insufficient"
    q = 1.0 - p

    # 尾部合并点 ℓ：让 ℓ 之前的每一格期望频数 >= min_expected
    ell = 0
    while ell < 64 and N * p * (q ** ell) >= min_expected:
        ell += 1
    if ell < 1:
        # 连第一格的期望都不足 → 无法做卡方（§3.6 处置）
        return None, 0, 1.0, "skipped"

    cnt = Counter(gaps)
    obs = [cnt.get(k, 0) for k in range(ell)]
    exp = [N * p * (q ** k) for k in range(ell)]
    # 尾格：P(L >= ell) = q^ell
    obs.append(sum(v for g, v in cnt.items() if g >= ell))
    exp.append(N * (q ** ell))

    chi2_stat = sum((o - e) ** 2 / e for o, e in zip(obs, exp) if e > EPS)
    df = len(obs) - 1
    if df < 1:
        return None, 0, 1.0, "skipped"
    return float(chi2_stat), df, _chi2_sf(chi2_stat, df), "chi2"


# ── 主入口（§3.5 统一签名） ───────────────────────────────────
def analyze(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg) -> ModuleResult:
    """波动率聚类分析。draws 已裁剪到目标期之前（无前视）。"""
    res = ModuleResult(name="volatility", scores={})
    T = len(draws)
    norm_method = _cfg_get(cfg, "thresholds", "norm_method", "rank")
    alpha = float(_cfg_get(cfg, "thresholds", "alpha", 0.05) or 0.05)
    fdr_method = (_cfg_get(cfg, "thresholds", "fdr_method", "bh") or "bh")

    if T < MIN_PERIODS:
        res.degrade(f"历史仅 {T} 期，少于 {MIN_PERIODS} 期"
                    f"（W={W} 滑动窗口 + {MIN_SAMPLE} 个有效窗口）")
        res.add("risk",
                f"- 波动率聚类：历史仅 {T} 期，不足 {MIN_PERIODS} 期，"
                f"无法做二项过度离散检验，已跳过。", order=40)
        return res

    ns = list(range(1, 81))
    nw = T - W + 1

    phi: dict[int, float] = {}          # 离散指数 D/df
    pdisp: dict[int, float] = {}        # 过度离散 χ² 上尾 p 值
    active: dict[int, float] = {}       # 最近窗口命中数 − 窗口命中中位数
    runs_excess: dict[int, float] = {}  # 游程结构偏离（χ²/df − 1，取正部）
    gap_n: dict[int, int] = {}
    degenerate: list[int] = []
    runs_used = 0

    series_by_n = _all_series(draws)
    for n in ns:
        series = series_by_n[n]
        total = sum(series)
        # §3.6：某号从未开出 / 期期开出 → 0/1 序列退化，二项零假设不适用
        if total == 0 or total == T:
            degenerate.append(n)
            phi[n] = 1.0
            pdisp[n] = 1.0
            active[n] = 0.0
            runs_excess[n] = 0.0
            gap_n[n] = 0
            continue

        counts = _window_counts(series)
        D, df, pval = _overdispersion(counts)
        phi[n] = finite(safe_div(D, df, 1.0), 1.0)
        pdisp[n] = clip01(finite(pval, 1.0))
        active[n] = float(counts[-1] - median(counts)) if counts else 0.0

        gaps = _gaps(series)
        gap_n[n] = len(gaps)
        c2, dfr, _pr, _method = _geometric_gof(gaps)
        if c2 is None:
            runs_excess[n] = 0.0
        else:
            runs_used += 1
            runs_excess[n] = max(0.0, safe_div(c2, dfr, 0.0) - 1.0)

    if len(degenerate) == len(ns):
        res.degrade("全部号码序列退化（从未开出或期期开出），无法检验波动聚集")
        res.diagnostics["degenerate_numbers"] = degenerate
        res.diagnostics["insufficient_data"] = len(degenerate)
        res.add("risk", "- 波动率聚类：全部号码序列退化，已跳过。", order=40)
        return res

    # ── 各子项在**全 80 号**内归一（§4.0 统一约定） ──
    r_phi = normalize([max(0.0, phi[n] - 1.0) for n in ns], norm_method)
    r_act = normalize([active[n] for n in ns], norm_method)
    r_runs = normalize([runs_excess[n] for n in ns], norm_method)

    # ── 显著性诊断：对 80 个过度离散 p 值做多重比较校正（§4.0 要求） ──
    pvals = [pdisp[n] for n in ns]
    if fdr_method == "bonferroni":
        _adj, rejects = bonferroni(pvals, alpha)
    else:
        _adj, rejects = bh_fdr(pvals, alpha)
    sig = {n: bool(rejects[i]) for i, n in enumerate(ns)}

    # ── 合成：基分（幅度 / 活跃 / 游程）+ 显著且活跃的加分（§4.10 步骤 3） ──
    composite: list[float] = []
    for i, n in enumerate(ns):
        base = W_PHI * r_phi[i] + W_ACT * r_act[i] + W_RUNS * r_runs[i]
        bonus = BONUS * r_act[i] if (sig[n] and active[n] > 0.0) else 0.0
        composite.append(finite(base + bonus, 0.0))

    raw_scores = normalize(composite, norm_method)
    scores: dict[int, float] = {}
    for i, n in enumerate(ns):
        # 退化号整体降级（§3.6）：score = 0.0
        scores[n] = 0.0 if n in degenerate else clip01(raw_scores[i])
    res.scores = scores

    # ── 统计口径 ──
    live = [n for n in ns if n not in degenerate]
    n_raw_sig = sum(1 for n in live if pdisp[n] < alpha)
    n_fdr_sig = sum(1 for n in live if sig[n])
    med_phi = median([phi[n] for n in live])

    top_phi = sorted(live, key=lambda n: (-phi[n], n))[:5]
    top_act = sorted(live, key=lambda n: (-active[n], n))[:5]
    # 风险预警：显著且活跃者优先，不足 5 个时用离散指数补齐
    risk_pool = [n for n in live if sig[n] and active[n] > 0.0]
    risk_pool.sort(key=lambda n: (-phi[n], n))
    for n in top_phi:
        if len(risk_pool) >= 5:
            break
        if n not in risk_pool:
            risk_pool.append(n)
    top_risk = risk_pool[:5]

    res.metrics = {
        "T": T,
        "window": W,
        "n_windows": nw,
        "chi2_df": nw - 1,
        "alpha": alpha,
        "fdr_method": fdr_method,
        "n_overdisp_raw": n_raw_sig,
        "n_overdisp_fdr": n_fdr_sig,
        "median_dispersion_index": round(med_phi, 3),
        "top_overdispersed": [(n, round(phi[n], 3)) for n in top_phi],
        "top_active_cluster": [(n, int(active[n])) for n in top_act],
        "risk_watch": [n for n in top_risk],
    }
    res.diagnostics = {
        "n_windows": nw,
        "df": nw - 1,
        "significant_raw": n_raw_sig,
        "significant_fdr": n_fdr_sig,
        "runs_test_used": runs_used,
        "runs_test_skipped": len(live) - runs_used,
        "degenerate_numbers": degenerate,
        "insufficient_data": len(degenerate),
        "median_gaps": round(mean([gap_n[n] for n in live]) if live else 0.0, 2),
        "sigma_window": round(math.sqrt(BINOM_VAR), 4),
    }
    if len(degenerate) > 0:
        res.diagnostics["note_degenerate"] = (
            f"{len(degenerate)} 个号序列退化（从未开出/期期开出），已按 §3.6 置 0.0")

    # ── narrative（真实数值，中文解读） ──
    res.add("macro",
            f"- **波动率聚类**（W={W} 滑动窗口，{nw} 个窗口）："
            f"二项过度离散检验在 α={alpha} 下校正前显著 {n_raw_sig}/80 号、"
            f"经 {'Bonferroni' if fdr_method == 'bonferroni' else 'BH-FDR'} 校正后"
            f"显著 {n_fdr_sig}/80 号；离散指数中位数 φ={med_phi:.2f}"
            f"（φ=1 即与伯努利 i.i.d. 一致，φ>1 表示命中呈突发聚集）。",
            order=30)
    res.add("macro",
            f"- **活跃簇**（最近窗口命中数 − 该号窗口命中中位数）："
            f"{'、'.join(f'{n:02d}({int(active[n]):+d})' for n in top_act)}；"
            f"过度离散最强的号码为 "
            f"{'、'.join(f'{n:02d}(φ={phi[n]:.2f})' for n in top_phi)}。",
            order=31)
    res.add("risk",
            f"- 波动预警：{'、'.join(f'{n:02d}' for n in top_risk)} 近期命中呈"
            f"突发聚集（Φ>1 且处于活跃簇），按 §4.10 步骤 4 进入风险清单——"
            f"高波动号回撤概率高于平稳号，宜降权或作备防。",
            order=41)

    return res
