# -*- coding: utf-8 -*-
"""斐波那契 / 黄金分割分析（§4.6）→ H1 低权子项 + 决策树"顺势"分支辅助过滤。

诚实性前置声明（§4.6 / §1.4）：斐波那契与黄金分割对**均匀随机序列没有理论
支撑**（不像 §4.5 的遗漏过程有首达结构）。本模块位置默认**低权**，且必须通过
回测显著性检验才保留，否则由回测层清零并在报告标注"已停用"。本文件只负责：
  ① 产出分数；② 给出显著性诊断（diagnostics），供回测/报告层决策。

算法（严格照抄 §4.6）：
  1. 斐波那契集 F：取 ≤80 的斐波那契数，对 >80 者取 mod 80 补回，最后去重。
  2. 黄金分割锚点 A：anchor = floor(80·r)，r ∈ {0.382, 0.5, 0.618, 0.786}
     → {30, 40, 49, 62}。黄金分割是**连续量**，本模块的确定离散化规则即
     `anchor = floor(80·r)`（单点落位，非区间），并在 metrics 中披露。
  3. 冷热识别：近 N 期「F 集」vs「非 F 集」命中率做比例检验
     （期望频数 < 5 时改用 Fisher 精确检验，见 numerics.fisher_or_skip）。
  4. 打分：号码 ∈ F（或 ∈ A）**且** 处于回补窗口（miss ≥ 该号历史中位连失）
     才加分；纯斐波那契巧合（未进入回补窗口）不给分。

打分公式（已在本文件披露，metrics 亦记录）：
    rebound(n) = 0                                          , miss < 中位连失
               = 0.5 + 0.5·clip((miss−med)/(2·med))          , miss ≥ 中位连失
    raw(n)     = rebound(n) · ( 1[n∈F] + 0.5·1[n∈A] )        ∈ [0, 1]
    score(n)   = clip01(raw(n))

    raw 本身即有界（指示量 × [0,1] 强度），故直接作为 score，不做二次秩归一：
    稀疏二值信号若过 rank 归一，会令大量 0 被抬到 0.4 左右而丧失可解释性。
    这与 §4.0「有界量无需再归一」一致（归一化的目标是 z/危险率那类无界量）。
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import ModuleResult
from .data_io import Draw, NUM_BALLS
from .numerics import (MIN_SAMPLE, clip01, finite, fisher_or_skip, median,
                       safe_div)
from .points import NumberStats

# ── 常量（全部在此披露，便于审计）──────────────────────────────

# 斐波那契生成上限：取该上限内的斐波那契数，≤80 直接保留，>80 取 mod 80 补回。
# 规格只给了 89 一例，未定义上限；本模块取 1000（覆盖 89/144/233/377/610/987），
# 该取值记录于 metrics["fib_gen_limit"]。若需收紧，改这一个常量即可。
FIB_GEN_LIMIT = 1000

# 黄金分割回撤位（标准位，§4.6 修正 v1.0 的 0.764 → √0.618 ≈ 0.786）
GOLDEN_RATIOS = (0.382, 0.5, 0.618, 0.786)

# 冷热识别的近 N 期窗口（§4.6「近 N 期」未给具体值，此处披露取 30）
FIB_WINDOW = 30

# 黄金锚点相对斐波那契号的权重（斐波那契为主，黄金为低权增强项）
GOLDEN_REL_WEIGHT = 0.5

# 单号回补窗口所需的最少历史连失样本数（不足则该号不参与打分）
MIN_GAPS = 3

# 中位连失缺失（全部连失为 0）时的兜底参考中失
FALLBACK_MEDIAN_MISS = 3.0


def fibonacci_set(limit: int = FIB_GEN_LIMIT) -> tuple[list[int], set[int], dict[int, int]]:
    """按 §4.6 构造斐波那契号集。

    返回 (原始斐波那契数列, 落在 1..80 的集合并去重, {原始值→mod80 投影})。
    >80 者取 mod 80 补回；投影为 0 时按 80 处理（80 号）。
    """
    raw: list[int] = []
    a, b = 1, 2                      # §4.6 集合以 1,2,3,5,8,13... 起（无重复 1）
    while a <= max(1, limit):
        raw.append(a)
        a, b = b, a + b

    proj: dict[int, int] = {}
    fib_set: set[int] = set()
    for x in raw:
        y = x % NUM_BALLS
        y = NUM_BALLS if y == 0 else y
        proj[x] = y
        if 1 <= y <= NUM_BALLS:
            fib_set.add(y)
    return raw, fib_set, proj


def golden_anchors() -> dict[float, int]:
    """黄金分割锚点：anchor = floor(80·r)。确定性离散化规则。"""
    return {r: int(NUM_BALLS * r) for r in GOLDEN_RATIOS}   # int() 即 floor（正数）


def _miss_and_gaps(draws: list[Draw], n: int) -> tuple[int, list[int]]:
    """从最新一期往前：返回 (当前连失, 历史完整连失长度列表)。"""
    hits = [i for i, d in enumerate(draws) if n in d.numbers_set]
    if not hits:
        return len(draws), []
    cur = hits[0]
    gaps = [hits[i + 1] - hits[i] - 1 for i in range(len(hits) - 1)]
    return cur, gaps


def _hit_indices(draws: list[Draw]) -> dict[int, list[int]]:
    """一趟扫过全部期次，返回每号的命中下标列表（降序语义由调用方处理）。

    比逐号调用 _miss_and_gaps 快一个量级：避免对 Draw.numbers_set
    属性做 80×T 次 frozenset 重建。
    """
    idx: dict[int, list[int]] = {n: [] for n in range(1, NUM_BALLS + 1)}
    for i, d in enumerate(draws):
        for n in d.numbers:
            if 1 <= n <= NUM_BALLS:
                idx[n].append(i)
    return idx


def _miss_and_gaps_from_idx(hits: list[int], T: int) -> tuple[int, list[int]]:
    """由升序命中下标列表得到 (当前连失, 完整连失长度列表)。"""
    if not hits:
        return T, []
    cur = hits[0]
    gaps = [hits[i + 1] - hits[i] - 1 for i in range(len(hits) - 1)]
    return cur, gaps


def _rebound_strength(miss: int, gaps: list[int]) -> tuple[float, bool]:
    """回补强度 ∈ [0,1]（§4.6 第 4 步：miss ≥ 该号历史中位连失才加分）。

    返回 (强度, 该号是否具备足够连失样本)。
    """
    if len(gaps) < MIN_GAPS:
        return 0.0, False
    med = median(gaps)
    ref = med if med > 0 else FALLBACK_MEDIAN_MISS
    if miss < ref:
        return 0.0, True
    depth = clip01(safe_div(miss - ref, 2.0 * ref, 0.0))   # 超出中位的相对深度
    return clip01(0.5 + 0.5 * depth), True


def _fib_intervals(fib_sorted: list[int]) -> list[tuple[int, int]]:
    """由 F 内号码切出的半开区间 [f_k, f_{k+1})，用于披露「落位」。"""
    return [(fib_sorted[i], fib_sorted[i + 1])
            for i in range(len(fib_sorted) - 1)]


def _interval_pos(n: int, intervals: list[tuple[int, int]]) -> tuple[int, float] | None:
    for lo, hi in intervals:
        if lo <= n < hi:
            return (lo, clip01(safe_div(n - lo, hi - lo, 0.0)))
    return None


def _proportion_test(draws: list[Draw], fib_set: set[int],
                     window: int, cfg) -> dict:
    """近 window 期 F 集 vs 非 F 集命中率比例检验（§4.6 第 3 步）。"""
    recent = draws[:window]
    n_fib = len(fib_set)
    n_non = NUM_BALLS - n_fib
    trials_fib = n_fib * len(recent)
    trials_non = n_non * len(recent)

    hits_fib = sum(1 for d in recent for n in d.numbers if n in fib_set)
    hits_non = sum(1 for d in recent for n in d.numbers if n not in fib_set)

    p_fib = safe_div(hits_fib, trials_fib, 0.0)
    p_non = safe_div(hits_non, trials_non, 0.0)
    lift = safe_div(p_fib, p_non, 0.0)

    out = {
        "window": len(recent),
        "fib_rate": round(p_fib, 4),
        "non_fib_rate": round(p_non, 4),
        "lift": round(finite(lift, 0.0), 4),
    }
    if trials_fib <= 0 or trials_non <= 0:
        out.update({"method": "skipped", "p_value": None, "significant": None})
        return out

    table = [[hits_fib, trials_fib - hits_fib],
             [hits_non, trials_non - hits_non]]
    try:
        stat, p, method = fisher_or_skip(table, min_expected=5.0)
    except Exception:                       # scipy 缺失/退化一律降级
        stat, p, method = None, None, "skipped"

    out["method"] = method
    out["stat"] = None if stat is None else round(finite(stat, 0.0), 4)
    out["p_value"] = None if p is None else round(finite(p, 1.0), 4)
    alpha = _cfg_value(cfg, "alpha", 0.05)
    out["significant"] = (None if p is None else bool(p < alpha))
    return out


def _cfg_value(cfg, key: str, default):
    """从 cfg.thresholds 安全取阈值，缺键/None 回退默认。"""
    try:
        th = getattr(cfg, "thresholds", None)
        if th is None:
            return default
        val = getattr(th, key, None)
        return default if val is None else val
    except Exception:
        return default


def analyze(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg) -> ModuleResult:
    """斐波那契/黄金分割分析（§4.6）。

    draws 必须最新在前，且已裁剪到目标期之前（无前视，§9.2）。
    expanded_set 不作为计算范围限制——本模块对全 80 号给出判断，
    仅在推荐阶段由融合层 masked_scores 施加筛选（§3.5）。
    """
    draws = list(draws or [])
    T = len(draws)

    fib_raw, fib_set, fib_proj = fibonacci_set()
    anchors = golden_anchors()
    anchor_set = set(anchors.values())
    fib_sorted = sorted(fib_set)
    intervals = _fib_intervals(fib_sorted)

    metrics: dict = {
        "T": T,
        "fib_gen_limit": FIB_GEN_LIMIT,
        "fib_raw": fib_raw,
        "fib_set": fib_sorted,
        "fib_mod_projection": {x: y for x, y in fib_proj.items() if x > NUM_BALLS},
        "golden_ratios": list(GOLDEN_RATIOS),
        "golden_anchors": {str(r): a for r, a in anchors.items()},
        "discretization_rule": "anchor = floor(80 * r), r ∈ {0.382,0.5,0.618,0.786}",
        "score_formula": "clip01( rebound_strength * ( 1[n∈F] + 0.5*1[n∈A] ) )",
        "window": min(T, FIB_WINDOW),
        "expanded_size": len(expanded_set or ()),
    }
    diagnostics: dict = {
        "fib_set_size": len(fib_set),
        "anchor_set": sorted(anchor_set),
        "expanded_used_for_filtering": False,
    }

    # ── 退化：历史不足 §3.6 ──
    if T < MIN_SAMPLE:
        res = ModuleResult(name="fibonacci", scores={})
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期")
        res.metrics = metrics
        res.metrics["rebound_qualifiers"] = []
        res.diagnostics = diagnostics
        res.diagnostics["degraded_reason"] = f"T={T} < MIN_SAMPLE={MIN_SAMPLE}"
        res.add("risk",
                f"- 斐波那契/黄金分割分析：历史仅 {T} 期（< {MIN_SAMPLE}），"
                f"样本不足，本模块已跳过（权重按 0 处理）。")
        return res

    # ── 逐号：连失 → 回补强度（一趟扫过全部期次，避免 frozenset 重复重建）──
    hit_idx = _hit_indices(draws)
    miss_map: dict[int, int] = {}
    med_map: dict[int, float] = {}
    strength: dict[int, float] = {}
    insufficient = 0
    for n in range(1, NUM_BALLS + 1):
        miss, gaps = _miss_and_gaps_from_idx(hit_idx[n], T)
        rs, ok = _rebound_strength(miss, gaps)
        miss_map[n] = miss
        med_map[n] = median(gaps)
        strength[n] = rs
        if not ok:
            insufficient += 1

    # ── 打分：F/A 成员 × 回补强度 ──
    scores: dict[int, float] = {}
    for n in range(1, NUM_BALLS + 1):
        ind = 0.0
        if n in fib_set:
            ind += 1.0
        if n in anchor_set:
            ind += GOLDEN_REL_WEIGHT
        scores[n] = clip01(strength[n] * ind)

    # ── 冷热比例检验（§4.6 第 3 步）──
    prop = _proportion_test(draws, fib_set, min(T, FIB_WINDOW), cfg)
    diagnostics["proportion_test"] = prop
    diagnostics["n_numbers_insufficient_gaps"] = insufficient
    diagnostics["retained_pending_backtest"] = True

    # ── 回补窗口中的天然位（供报告与指标）──
    qualifiers = [n for n in range(1, NUM_BALLS + 1) if scores[n] > 0.0]
    qualifiers.sort(key=lambda n: (-scores[n], n))
    top_q = qualifiers[:8]
    metrics["rebound_qualifiers"] = [
        {
            "n": n,
            "score": round(scores[n], 4),
            "miss": miss_map[n],
            "median_miss": round(med_map[n], 2),
            "in_fib": n in fib_set,
            "in_golden": n in anchor_set,
        }
        for n in top_q
    ]
    metrics["n_qualifiers"] = len(qualifiers)
    # 落位披露：回补位号码在斐波那契区间中的相对位置
    metrics["interval_positions"] = [
        (n, _interval_pos(n, intervals)) for n in top_q[:5]
    ]

    res = ModuleResult(name="fibonacci", scores=scores)
    res.metrics = metrics
    res.diagnostics = diagnostics

    # ── narrative（macro / risk，数值真实来自上方 metrics）──
    fib_str = "、".join(f"{n:02d}" for n in fib_sorted)
    anchor_str = "、".join(str(a) for a in sorted(anchor_set))
    if top_q:
        q_str = "、".join(
            f"{n:02d}(连失{miss_map[n]}/中位{med_map[n]:.0f}"
            f"{'/斐' if n in fib_set else '/金'})"
            for n in top_q)
    else:
        q_str = "无"

    res.add("macro",
            f"- **斐波那契集**（§4.6）：{fib_str}（共 {len(fib_set)} 个）；"
            f"原始数列 {fib_raw}，>80 者按 mod 80 补回（如 "
            f"{'、'.join(f'{x}→{y:02d}' for x, y in metrics['fib_mod_projection'].items())}）。",
            order=30)
    res.add("macro",
            f"- **黄金分割锚点**：离散化规则 `floor(80·r)`，"
            f"r∈{{0.382,0.5,0.618,0.786}} → {anchor_str}。",
            order=31)
    res.add("macro",
            f"- **天然回补位**（∈F/A 且连失 ≥ 自身历史中位连失）：{q_str}，"
            f"共 {len(qualifiers)} 个；纯斐波那契巧合（未入回补窗口）不计分。",
            order=32)
    p_txt = "NA" if prop["p_value"] is None else f"{prop['p_value']:.3f}"
    res.add("macro",
            f"- **冷热检验**：近 {prop['window']} 期 F 集命中率 "
            f"{prop['fib_rate']:.2%} vs 非 F 集 {prop['non_fib_rate']:.2%}"
            f"（lift={prop['lift']:.3f}，{prop['method']} 检验 p={p_txt}）。",
            order=33)

    sig = prop.get("significant")
    if sig is False:
        res.add("risk",
                f"- 斐波那契/黄金分割对均匀随机序列无理论支撑（§4.6）；近 "
                f"{prop['window']} 期 F 集与非 F 集命中率差异不显著"
                f"（p={prop['p_value']:.3f} ≥ α={_cfg_value(cfg, 'alpha', 0.05)}）。"
                f"本模块按低权子项参与 H1，是否保留待回测显著性检验。",
                order=50)
    elif sig is None:
        res.add("risk",
                "- 斐波那契/黄金分割：冷热比例检验不可用（样本退化），"
                "本模块结论仅供参考，保留与否待回测。", order=50)

    if insufficient > 0:
        res.add("risk",
                f"- {insufficient} 个号码的历史连失样本不足（< {MIN_GAPS} 段），"
                f"其回补强度记为 0（§3.6）。", order=51)

    return res
