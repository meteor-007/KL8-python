# -*- coding: utf-8 -*-
"""过滤方法集：对抗生成思维（§4.13，元模块，**不进主分**）。

本模块是"终极推荐的最后一道过滤器"：对每个候选号构造**逐号反证**
（"为什么不该推荐它"），反证越强越可疑。仅反证得分低于阈值的号可入榜。

§4.13 定义了四个可计算的逐号反证指征（各归一化到 [0,1]，越大 = 反证越强）：

    refute_crowd    该号在其他模块中的共识度（越拥挤越可疑，§4.4 consensus）
    refute_overfit  该号的外样本命中 lift 是否低于 1（样本不足 → 过拟合风险）
    refute_random   该号得分是否落在随机基线波动内 / 过于极端（噪声嫌疑）
    refute_phase    该号信号是否自相矛盾 / 相位下行（§4.2 / §4.8）

`refute[n] = 加权平均(四个指征)`，权重由 config 给出（缺省等权）。

**门控**：仅 `refute[n] < cfg.thresholds.adversarial_refute_max`（默认 0.5）
的号可进入终极推荐。

**熵值校正**：若入选集合过于集中于单一场域（分区多样性熵低于阈值），
强制引入对冲号（§4.13）。

**降级路径**（§4.13）：逐号外样本接口尚未实现 / 证据缺失时，本模块
**不作门控**（fail-open，全部候选通过），仅输出反证文字并在报告中标注。

签名（§4.4 / §4.13 与 §3.5 末尾）单列：

    gate(candidates, composite, per_number_stats, cfg) -> (通过门控的号, 反证得分)

另提供 `analyze(...) -> ModuleResult` 便捷适配器：在没有 ensemble 的场景下
由基础统计自建逐号证据、跑 gate()、产出报告文字（narrative）。该适配器
**不进 H1–H7 主分**，仅供单模块自测与报告层使用。
"""
from __future__ import annotations

from typing import Any

from .contracts import ModuleResult, NarrativeBlock, NumberGateStats
from .numerics import (EPS, MIN_SAMPLE, clip01, entropy_normalized, finite,
                       rank_normalize, safe_div, stdev)
from .points import compute_base_stats

# 四个反证指征的固定键名（与 §4.13 表格一一对应）
INDICATORS = ("refute_crowd", "refute_overfit", "refute_random", "refute_phase")

# 缺省等权（§4.13：权重在 config 中给出，默认等权）
_DEFAULT_WEIGHTS = {k: 0.25 for k in INDICATORS}

NUM_BALLS = 80


# ── 配置读取（缺键一律回退默认值，绝不抛异常）─────────────────────

def _thr(cfg, key: str, default: Any) -> Any:
    """从 cfg.thresholds 读取阈值键，缺失/None 时回退 default。"""
    sec = getattr(cfg, "thresholds", None) if cfg is not None else None
    if sec is None:
        return default
    val = sec.get(key) if hasattr(sec, "get") else getattr(sec, key, None)
    return default if val is None else val


def _weights(cfg) -> dict[str, float]:
    """反证指征权重：优先 cfg.thresholds.adversarial_refute_weights，
    其次 cfg.scoring.adversarial_weights，均缺失则等权（§4.13）。"""
    raw = None
    if cfg is not None:
        for sec_name, key in (("thresholds", "adversarial_refute_weights"),
                              ("scoring", "adversarial_weights")):
            sec = getattr(cfg, sec_name, None)
            if sec is None:
                continue
            val = sec.get(key) if hasattr(sec, "get") else getattr(sec, key, None)
            if isinstance(val, dict):
                raw = val
                break
    if not isinstance(raw, dict):
        return dict(_DEFAULT_WEIGHTS)
    w = {k: max(0.0, finite(raw.get(k, 0.0))) for k in INDICATORS}
    tot = sum(w.values())
    if tot <= EPS:
        return dict(_DEFAULT_WEIGHTS)
    return {k: w[k] / tot for k in INDICATORS}


# ── 归一化小工具 ──────────────────────────────────────────────

def _rank_or_zero(values: list[float]) -> list[float]:
    """秩归一；**列全等时返回全 0**（无区分度 = 无反证证据）。

    与 numerics.rank_normalize 的全等 → 0.5 不同：本模块语义是"反证强度"，
    没有证据就不应凭空抬高反证得分（否则退化输入会被整体否掉）。
    """
    vals = [finite(v, 0.0) for v in values]
    if not vals:
        return []
    if max(vals) - min(vals) < EPS:
        return [0.0] * len(vals)
    return rank_normalize(vals)


def _invert_rank(values: list[float]) -> list[float]:
    """样本越少 → 反证越强 = 1 − 秩归一（列全等时全 0）。"""
    vals = [finite(v, 0.0) for v in values]
    if not vals or max(vals) - min(vals) < EPS:
        return [0.0] * len(vals)
    return [1.0 - x for x in rank_normalize(vals)]


def _h_dispersion(h_values: dict) -> float:
    """逐号维度一致性：h_values 的离散度（越大 = 各维度信号越矛盾）。"""
    if not isinstance(h_values, dict) or len(h_values) < 2:
        return 0.0
    vals = [clip01(finite(v, 0.0)) for v in h_values.values()]
    return finite(stdev(vals), 0.0)


def _stat_of(stats: dict, n: int) -> NumberGateStats:
    """取逐号证据；缺失时返回中性空证据（不抛异常）。"""
    s = stats.get(n)
    return s if isinstance(s, NumberGateStats) else NumberGateStats(n=n)


def _zone(n: int) -> int:
    """场域划分：每 10 号一区，共 8 区（§4.13"单一场域"的多样性口径）。"""
    return (n - 1) // 10


# ── 反证指征合成 ──────────────────────────────────────────────

def _refute_scores(pool: list[int], stats: dict, composite: dict,
                   cfg) -> dict[int, float]:
    """在 pool 内计算四个指征并加权合成逐号反证得分（§4.13）。"""
    crowd = [clip01(finite(_stat_of(stats, n).crowding, 0.0)) for n in pool]
    sample = [finite(_stat_of(stats, n).sample_size, 0.0) for n in pool]
    zabs = [abs(finite(_stat_of(stats, n).z_score, 0.0)) for n in pool]
    disp = [_h_dispersion(_stat_of(stats, n).h_values) for n in pool]

    # 指征 1 拥挤：直接取 §4.4 consensus 归一量（已 ∈ [0,1]）
    ind_crowd = crowd
    # 指征 2 过拟合：样本不足 → 反证强
    ind_overfit = _invert_rank(sample)
    # 指征 3 随机：|z| 越极端（无论正负）越可能是噪声 / 随机波动
    ind_random = _rank_or_zero(zabs)
    # 指征 4 相位：各维度信号越自相矛盾越可疑（相位下行）
    ind_phase = _rank_or_zero(disp)

    w = _weights(cfg)
    out: dict[int, float] = {}
    for i, n in enumerate(pool):
        r = (w["refute_crowd"] * ind_crowd[i]
             + w["refute_overfit"] * ind_overfit[i]
             + w["refute_random"] * ind_random[i]
             + w["refute_phase"] * ind_phase[i])
        out[n] = clip01(r)
    return out


def _diversity_fix(passed: list[int], refute: dict[int, float],
                   composite: dict[int, float], stats: dict,
                   pool_all: list[int], thr: float, cfg) -> list[int]:
    """熵值校正（§4.13）：入选集合过于集中时强制引入对冲号。"""
    if len(passed) < 3:
        return passed

    # 场域多样性熵
    zones = [0] * 8
    for n in passed:
        zones[_zone(n)] += 1
    ent = entropy_normalized(zones)

    # 方法/维度多样性熵（有 h_values 时取主导维度分布）
    dim_counts: dict[str, int] = {}
    for n in passed:
        hv = _stat_of(stats, n).h_values
        if isinstance(hv, dict) and hv:
            dom = max(hv, key=lambda k: finite(hv[k], 0.0))
            dim_counts[dom] = dim_counts.get(dom, 0) + 1
    if dim_counts:
        ent = min(ent, entropy_normalized(list(dim_counts.values())))

    div_min = clip01(finite(_thr(cfg, "adversarial_diversity_min", 0.5), 0.5))
    if ent >= div_min:
        return passed

    hedge_k = int(finite(_thr(cfg, "adversarial_hedge_k", 2), 2.0))
    if hedge_k <= 0:
        return passed

    # 对冲号池：未入选、且本身通过门控的号 —— 优先补进空场域
    chosen = set(passed)
    cand_pool = [n for n in pool_all
                 if n not in chosen and refute.get(n, 1.0) < thr]
    zone_now = {z: zones[z] for z in range(8)}
    extra: list[int] = []

    # 第一轮：只从当前人数为 0 的场域取（快速拉平多样性）
    for n in sorted(cand_pool, key=lambda x: (refute.get(x, 1.0),
                                              -composite.get(x, 0.0))):
        z = _zone(n)
        if zone_now.get(z, 0) > 0:
            continue
        zone_now[z] = zone_now.get(z, 0) + 1
        extra.append(n)
        if len(extra) >= hedge_k:
            break
    # 第二轮：仍不足则按反证最弱补齐
    if len(extra) < hedge_k:
        for n in sorted(cand_pool, key=lambda x: (refute.get(x, 1.0),
                                                  -composite.get(x, 0.0))):
            if n in extra:
                continue
            extra.append(n)
            if len(extra) >= hedge_k:
                break

    if not extra:
        return passed
    out = list(passed) + extra
    out.sort(key=lambda n: (-composite.get(n, 0.0), n))
    return out


# ── 公开接口：gate（§4.4 / §4.13）────────────────────────────

def gate(candidates: list[int],
         composite: dict[int, float],
         per_number_stats: dict[int, NumberGateStats],
         cfg) -> tuple[list[int], dict[int, float]]:
    """对抗门控：逐号反证，仅反证低于阈值者可入榜（§4.13）。

    参数
    ----
    candidates       : 待门控的候选号（通常为 composite 的 Top-k 或拓展集合）。
    composite        : 融合层给出的逐号综合分（用于排序与对冲挑选）。
    per_number_stats : 逐号证据（z_score / miss / hit10 / h_values / crowding /
                       sample_size），由 ensemble / 回测层填充。
    cfg              : 全局配置（阈值键 adversarial_refute_max 等）。

    返回
    ----
    (通过门控的号列表[按综合分降序], {号: 反证得分 ∈ [0,1]})

    退化处置：候选为空 → 返回 ([], {})；证据缺失（无区分度）→ 反证全 0，
    **fail-open** 全数通过（对应 §4.13"不作门控"的降级精神）。
    """
    cands = sorted({int(n) for n in (candidates or []) if 1 <= int(n) <= NUM_BALLS})
    stats = dict(per_number_stats or {})
    comp = {int(k): finite(v, 0.0) for k, v in (composite or {}).items()}

    if not cands:
        return [], {}

    # 归一化参考池：全部有证据的号 ∪ 候选 ∪ 综合分号（全号段口径，不限于拓展集合）
    pool = sorted(set(stats) | set(cands) | set(comp))
    pool = [n for n in pool if 1 <= n <= NUM_BALLS]
    if not pool:
        return list(cands), {n: 0.0 for n in cands}

    refute = _refute_scores(pool, stats, comp, cfg)

    thr = clip01(finite(_thr(cfg, "adversarial_refute_max", 0.5), 0.5))
    passed = [n for n in cands if refute.get(n, 0.0) < thr]
    passed.sort(key=lambda n: (-comp.get(n, 0.0), n))

    passed = _diversity_fix(passed, refute, comp, stats, pool, thr, cfg)

    return passed, {n: refute.get(n, 0.0) for n in pool}


# ── 便捷适配器：analyze（不进主分，仅供自测与报告）─────────────

def _nb(section: str, text: str, order: int = 0) -> NarrativeBlock:
    return NarrativeBlock(section, text, order)


def analyze(draws: list,
            expanded_set: set[int],
            base_stats: dict | None = None,
            cfg=None) -> ModuleResult:
    """独立运行适配器：自建逐号证据 → gate() → ModuleResult（§3.5 形态）。

    ⚠ 本模块为**过滤方法集**，**不进 H1–H7 主分**。返回的 scores 语义为
    "通过对抗门控的可信度" = 1 − refute[n]（越高越可信，覆盖全 1–80 号），
    仅供报告与单模块自测使用；融合层应改用 `gate()`。

    无前视：只使用传入的 draws（调用方已裁剪到目标期之前）。
    """
    draws = list(draws or [])
    expanded = set(expanded_set or set())
    T = len(draws)

    base = dict(base_stats or {})
    if not base and draws:
        base = compute_base_stats(draws, expanded)

    if T < MIN_SAMPLE or not base:
        res = ModuleResult(name="adversarial", scores={})
        res.degrade(f"历史仅 {T} 期 / 基础统计缺失，对抗门控降级为仅文字输出")
        res.add("risk",
                f"- **对抗生成**：历史仅 {T} 期（< {MIN_SAMPLE}），样本不足，"
                f"本轮**不作门控**，仅输出反证提示（§4.13 降级路径）。", order=60)
        return res

    # ── 自建逐号证据（子信号均在池内秩归一，量纲一致）──
    ns = sorted(base)
    z_raw = [finite(base[n].z_score, 0.0) for n in ns]
    miss_raw = [float(base[n].miss) for n in ns]
    h10_raw = [float(base[n].hit10) for n in ns]
    h3_raw = [float(base[n].hit3) for n in ns]

    z_n = rank_normalize(z_raw)
    m_n = rank_normalize(miss_raw)
    h10_n = rank_normalize(h10_raw)
    h3_n = rank_normalize(h3_raw)

    per: dict[int, NumberGateStats] = {}
    comp: dict[int, float] = {}
    for i, n in enumerate(ns):
        # 拥挤代理：循环三元组落入拓展集合的比例（点位密集处 = 拥挤）
        triple = {(n - 1) if n > 1 else NUM_BALLS,
                  n,
                  (n + 1) if n < NUM_BALLS else 1}
        crowd = clip01(safe_div(len(triple & expanded), 3.0, 0.0))
        # 信号矛盾由四个可计算子维度体现（热度/反弹/近10/动量）
        h_vals = {"hot": z_n[i], "rebound": m_n[i],
                  "recent": h10_n[i], "momentum": h3_n[i]}
        per[n] = NumberGateStats(
            n=n, z_score=z_raw[i], miss=int(base[n].miss),
            hit10=int(base[n].hit10), composite=0.0, h_values=h_vals,
            crowding=crowd, sample_size=int(base[n].freq_full))
        comp[n] = clip01(0.30 * z_n[i] + 0.30 * m_n[i]
                         + 0.20 * h10_n[i] + 0.20 * h3_n[i])

    cands = list(range(1, NUM_BALLS + 1))       # 全号段判断，不用拓展集合限范围
    passed, refute = gate(cands, comp, per, cfg)

    scores = {n: clip01(1.0 - finite(refute.get(n, 0.0))) for n in range(1, NUM_BALLS + 1)}

    # ── 统计口径 ──
    rvals = [refute.get(n, 0.0) for n in cands]
    thr = clip01(finite(_thr(cfg, "adversarial_refute_max", 0.5), 0.5))
    rejected = sorted(cands, key=lambda n: (-refute.get(n, 0.0), n))
    top_reject = rejected[:5]
    r_mean = safe_div(sum(rvals), len(rvals), 0.0)
    r_med = sorted(rvals)[len(rvals) // 2] if rvals else 0.0
    z_extreme = sorted(cands, key=lambda n: -abs(finite(per[n].z_score, 0.0)))[:3]

    zones = [0] * 8
    for n in passed:
        zones[_zone(n)] += 1
    div_ent = entropy_normalized(zones)

    metrics = {
        "T": T,
        "n_candidates": len(cands),
        "n_pass": len(passed),
        "pass_ratio": round(safe_div(len(passed), len(cands), 0.0), 3),
        "refute_max_threshold": thr,
        "refute_mean": round(r_mean, 3),
        "refute_median": round(r_med, 3),
        "top_rejected": [(n, round(refute.get(n, 0.0), 3)) for n in top_reject],
        "most_extreme_z": [(n, round(finite(per[n].z_score, 0.0), 2))
                           for n in z_extreme],
        "weights": _weights(cfg),
        "diversity_entropy": round(div_ent, 3),
    }
    diagnostics = {
        "n_numbers": len(ns),
        "min_sample": MIN_SAMPLE,
        "sample_median": int(sorted(per[n].sample_size for n in ns)[len(ns) // 2]),
        "gate_mode": "enforce" if r_mean > 0 else "no-evidence(fail-open)",
    }

    narrative = [
        _nb("macro",
            f"- **对抗反证**：{len(cands)} 个候选号平均反证得分 "
            f"{r_mean:.3f}（中位 {r_med:.3f}），门控阈值 {thr:.2f}，"
            f"通过 {len(passed)} 个（{safe_div(len(passed), len(cands), 0.0):.0%}）。",
            order=50),
        _nb("macro",
            "- **反证最强**（最不该推荐）："
            + "、".join(f"{n:02d}(refute={refute.get(n, 0.0):.2f})"
                        for n in top_reject) + "。",
            order=51),
        _nb("risk",
            "- **异常 z 警戒**："
            + "、".join(f"{n:02d}(z={finite(per[n].z_score, 0.0):+.2f})"
                        for n in z_extreme)
            + f"，|z| 越极端越可能是随机波动，已在反证中计权。",
            order=52),
        _nb("risk",
            f"- **场域多样性**：入选号分属 8 区的归一化熵 {div_ent:.3f}，"
            + ("低于阈值，已按 §4.13 引入对冲号。"
               if div_ent < clip01(finite(_thr(cfg, "adversarial_diversity_min", 0.5), 0.5))
               else "分布均衡，未触发对冲。"),
            order=53),
    ]

    return ModuleResult(
        name="adversarial",
        scores=scores,
        metrics=metrics,
        narrative=narrative,
        diagnostics=diagnostics,
        sufficient=True,
    )
