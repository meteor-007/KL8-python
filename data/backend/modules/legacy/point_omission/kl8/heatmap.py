# -*- coding: utf-8 -*-
"""§4.3 数字场域能量分布图 Heat Zone Mapping（heatmap.py）。

目标：把 1–80 划分为多尺度场域，量出能量分布，并给出：
  * 主分 `scores`（→ H4 周期/波动）：场域能量 = 区间热度 + 区间内密度 + 区间间迁移；
  * 均衡子项 `metrics["balance"]`（→ H7 熵/均衡）：低能量但历史回补活跃的场域得分高；
  * `metrics["defensive_candidates"]`：低能量场域 + 历史回补活跃的号码，供 §5.4 两码备防。

多尺度场域（§4.3 步骤 1）：
  * 8 段（每段 10 号）：[1-10]…[71-80]
  * 4 象限（每象限 20 号）
  * 余数 8 区（mod 8）

能量密度（§4.3 步骤 2）：
  d_zone = 窗口内该场域总命中数 / 窗口期数（单期平均命中数）
  E_zone = size_zone × 20/80 = size_zone / 4（单期期望）
  r = d_zone / E_zone（能量比）
偏向指数 bias = max(r) − min(r)（§4.3 步骤 3）。

实现约定（§3.5 / §4.0 / 硬性要求 4）：
  * 分数覆盖全 1–80 号；拓展集合**不**限制计算范围，只在推荐阶段被 ensemble 遮罩。
  * 全程只用 numerics 的稳健算子，绝不裸除法/裸 log，不产生 nan/inf。
  * 不使用任何随机过程，不读盘，不访问 draws 之外的期次（无前视）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .contracts import ModuleResult
from .data_io import Draw, NUM_BALLS
from .numerics import (MIN_SAMPLE, clip01, finite, median, normalize,
                       safe_div)
from .points import NumberStats

# 能量窗口期数（≤ 30）：短窗捕捉当下热点，长历史用于历史回补估计
HEAT_WINDOW = 30
# 场域"低能量"判定阈值：能量比 r < 1.0 视为低于期望
LOW_ENERGY_RATIO = 1.0
# 三尺度权重（8 段为主，象限与余数 8 区为辅）
SCALE_WEIGHTS = {"seg": 0.40, "quad": 0.20, "rem": 0.20}
# 场域内三子项权重：热度 / 密度 / 迁移
COMBINE_WEIGHTS = {"heat": 0.50, "density": 0.25, "migration": 0.25}
# 单号"局部密度"权重（该号自身在窗口内的活跃度，提供号内分辨率）
LOCAL_WEIGHT = 0.20
# 热力矩阵阴影（10 级）
SHADES = " .:-=+*#%@"


@dataclass
class ZoneEnergy:
    """单个场域的能量画像。"""
    zone: int
    size: int
    win_hits: int
    d: float            # 单期平均命中数
    e: float            # 单期期望命中数 = size/4
    r: float            # 能量比 = d / e
    coverage: float     # 区间内密度：窗口内至少命中一次的不同号占比
    momentum: float     # 区间间迁移：后半窗与前半窗的单位期命中差
    rebound: float      # 历史回补活跃度：冷窗后下一窗恢复的比例


# ── 场域划分 ────────────────────────────────────────────────────────

def _zone_members(kind: str) -> dict[int, list[int]]:
    if kind == "seg":      # 8 段，每段 10 号
        return {z: list(range(10 * (z - 1) + 1, 10 * z + 1)) for z in range(1, 9)}
    if kind == "quad":     # 4 象限，每象限 20 号
        return {z: list(range(20 * (z - 1) + 1, 20 * z + 1)) for z in range(1, 5)}
    if kind == "rem":      # 余数 8 区（mod 8，余 1…8），每区 10 号
        return {z: [n for n in range(1, NUM_BALLS + 1) if (n - 1) % 8 + 1 == z]
                for z in range(1, 9)}
    raise ValueError(f"未知场域类型: {kind}")


def _zone_of(kind: str, n: int) -> int:
    if kind == "seg":
        return (n - 1) // 10 + 1
    if kind == "quad":
        return (n - 1) // 20 + 1
    return (n - 1) % 8 + 1


# ── 能量计算 ────────────────────────────────────────────────────────

def _num_counts(draws: list[Draw], W: int, half: int):
    """预统计：每个号在窗内的总命中、最近半窗、较早半窗命中数。"""
    wc = {n: 0 for n in range(1, NUM_BALLS + 1)}
    hc_new = {n: 0 for n in range(1, NUM_BALLS + 1)}
    hc_old = {n: 0 for n in range(1, NUM_BALLS + 1)}
    window = draws[:W]
    for i, d in enumerate(window):
        for n in d.numbers:
            if n < 1 or n > NUM_BALLS:
                continue
            wc[n] += 1
            if i < half:
                hc_new[n] += 1
            else:
                hc_old[n] += 1
    return wc, hc_new, hc_old


def _rebound_rate(draws: list[Draw], nums: list[int], W: int) -> tuple[float, int]:
    """历史回补活跃度：非重叠窗序列中，冷窗（r<1）之后下一窗恢复（r>=1）的比例。

    draws 最新在前：窗口 0 最新，窗口 K−1 最旧。时间上"冷→恢复"对应
    较旧的窗 k（冷）之后的较新窗 k−1 是否回到期望之上。
    """
    T = len(draws)
    K = T // W
    if K < 2:
        return 0.0, 0
    nums_set = set(nums)
    size = len(nums)
    exp_win = size * 20.0 / 80.0 * W            # 窗内期望命中 = size/4 × W
    hits: list[int] = []
    for k in range(K):
        seg = draws[k * W:(k + 1) * W]
        h = 0
        for d in seg:
            h += len(nums_set.intersection(d.numbers_set))
        hits.append(h)
    cold = 0
    rec = 0
    for k in range(1, K):                        # k 较旧，k−1 较新
        r_old = safe_div(hits[k], exp_win, 0.0)
        if r_old < LOW_ENERGY_RATIO:
            cold += 1
            r_new = safe_div(hits[k - 1], exp_win, 0.0)
            if r_new >= LOW_ENERGY_RATIO:
                rec += 1
    return clip01(safe_div(rec, cold, 0.0)), cold


def _energy_table(draws: list[Draw], members: dict[int, list[int]], W: int,
                  half: int, wc, hc_new, hc_old) -> dict[int, ZoneEnergy]:
    tab: dict[int, ZoneEnergy] = {}
    for z in sorted(members):
        nums = members[z]
        size = len(nums)
        wh = sum(wc[n] for n in nums)
        hn = sum(hc_new[n] for n in nums)
        ho = sum(hc_old[n] for n in nums)
        d = safe_div(wh, W, 0.0)
        e = size * 20.0 / 80.0
        r = safe_div(d, e, 0.0)
        distinct = sum(1 for n in nums if wc[n] > 0)
        coverage = safe_div(distinct, size, 0.0)
        momentum = safe_div(hn - ho, half, 0.0)
        reb, _ = _rebound_rate(draws, nums, W)
        tab[z] = ZoneEnergy(zone=z, size=size, win_hits=wh, d=d, e=e, r=r,
                            coverage=coverage, momentum=momentum, rebound=reb)
    return tab


def _norm_map(keys: list[int], values: dict[int, float], method: str) -> dict[int, float]:
    """对给定键的原始量做归一（方法由 config.thresholds.norm_method 决定）。"""
    if not keys:
        return {}
    norms = normalize([finite(values[k], 0.0) for k in keys], method)
    return {k: clip01(v) for k, v in zip(keys, norms)}


def _field_combo(tab: dict[int, ZoneEnergy], method: str) -> dict[int, float]:
    """场域能量 = 区间热度 + 区间内密度 + 区间间迁移（各分量先归一再加权）。"""
    keys = sorted(tab)
    heat = _norm_map(keys, {k: tab[k].r for k in keys}, method)
    dens = _norm_map(keys, {k: tab[k].coverage for k in keys}, method)
    migr = _norm_map(keys, {k: tab[k].momentum for k in keys}, method)
    return {k: clip01(COMBINE_WEIGHTS["heat"] * heat[k]
                      + COMBINE_WEIGHTS["density"] * dens[k]
                      + COMBINE_WEIGHTS["migration"] * migr[k]) for k in keys}


def _shade(score: float) -> str:
    idx = int(clip01(score) * (len(SHADES) - 1) + 1e-9)
    return SHADES[min(idx, len(SHADES) - 1)]


def _heat_matrix_md(scores: dict[int, float]) -> str:
    """10 行 × 8 列的 Markdown 热力矩阵：列 = 余数 8 区，行 = 区内位次。

    单元格为 `号+阴影`，阴影映射主分（越暗能量越高）。
    """
    lines = ["| 位次\\余区 | 余1 | 余2 | 余3 | 余4 | 余5 | 余6 | 余7 | 余8 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in range(10):
        cells = []
        for c in range(8):
            n = r * 8 + c + 1
            cells.append(f"{n:02d}{_shade(scores.get(n, 0.0))}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ── 主入口 ──────────────────────────────────────────────────────────

def analyze(draws: list[Draw], expanded_set: set[int],
            base_stats: dict[int, NumberStats], cfg) -> ModuleResult:
    """§3.5 统一签名。draws 最新在前、已裁剪到目标期之前（无前视）。"""
    res = ModuleResult(name="heatmap", scores={})
    draws = list(draws or [])
    T = len(draws)

    if T < MIN_SAMPLE:
        res.degrade(f"历史仅 {T} 期，少于 {MIN_SAMPLE} 期，无法估计场域能量")
        res.add("risk", f"- 场域能量图：历史仅 {T} 期，样本不足，已跳过。", order=10)
        return res

    method = "rank"
    try:
        m = getattr(cfg.thresholds, "norm_method", None) if cfg is not None else None
        if m in ("rank", "minmax", "sigmoid"):
            method = m
    except Exception:
        method = "rank"

    W = min(T, HEAT_WINDOW)
    half = max(1, W // 2)
    wc, hc_new, hc_old = _num_counts(draws, W, half)

    seg_members = _zone_members("seg")
    quad_members = _zone_members("quad")
    rem_members = _zone_members("rem")
    members_by_kind = {"seg": seg_members, "quad": quad_members, "rem": rem_members}

    tables = {k: _energy_table(draws, mem, W, half, wc, hc_new, hc_old)
              for k, mem in members_by_kind.items()}

    # ── 多尺度场域能量合成 → 主分（H4） ──
    combos = {k: _field_combo(tables[k], method) for k in tables}
    local_norm = _norm_map(list(range(1, NUM_BALLS + 1)), wc, method)

    raw = {}
    for n in range(1, NUM_BALLS + 1):
        v = LOCAL_WEIGHT * local_norm[n]
        for kind, w in SCALE_WEIGHTS.items():
            v += w * combos[kind][_zone_of(kind, n)]
        raw[n] = v

    score_list = normalize([raw[n] for n in range(1, NUM_BALLS + 1)], method)
    scores = {n: clip01(score_list[i]) for i, n in enumerate(range(1, NUM_BALLS + 1))}
    res.scores = scores

    # ── 均衡子项（H7）：低能量但历史回补活跃的场域得分高（能量反转） ──
    seg_keys = sorted(tables["seg"])
    energy_rank = _norm_map(seg_keys, {z: tables["seg"][z].r for z in seg_keys}, method)
    rebound_rank = _norm_map(seg_keys, {z: tables["seg"][z].rebound for z in seg_keys}, method)
    bal_raw = {}
    for n in range(1, NUM_BALLS + 1):
        z = _zone_of("seg", n)
        # 低能量（1 − energy_rank 大）× 回补活跃（rebound 大）
        bal_raw[n] = (1.0 - energy_rank[z]) * (0.25 + 0.75 * rebound_rank[z])
    bal_list = normalize([bal_raw[n] for n in range(1, NUM_BALLS + 1)], method)
    balance = {n: clip01(bal_list[i]) for i, n in enumerate(range(1, NUM_BALLS + 1))}

    # ── 偏向指数 bias（8 段，§4.3 步骤 3） ──
    r_vals = [tables["seg"][z].r for z in seg_keys]
    bias = finite(max(r_vals) - min(r_vals), 0.0)
    hot_zone = max(seg_keys, key=lambda z: (tables["seg"][z].r, -z))
    cold_zone = min(seg_keys, key=lambda z: (tables["seg"][z].r, z))

    # ── §5.4 备防候选：低能量场域 + 历史回补活跃 ──
    low_zones = [z for z in seg_keys if tables["seg"][z].r < LOW_ENERGY_RATIO]
    if not low_zones:
        med_r = median(r_vals)
        low_zones = [z for z in seg_keys if tables["seg"][z].r <= med_r]
    low_rebs = [tables["seg"][z].rebound for z in low_zones]
    reb_thr = median(low_rebs) if low_rebs else 0.0
    active_low = [z for z in low_zones if tables["seg"][z].rebound >= reb_thr]
    if not active_low:
        active_low = low_zones or seg_keys
    cand_numbers = sorted({n for z in active_low for n in seg_members[z]},
                          key=lambda n: (-balance[n], n))

    # ── metrics ──
    def _tab_rows(kind: str):
        return [{"zone": e.zone, "size": e.size, "d": round(e.d, 4),
                 "E": round(e.e, 4), "r": round(e.r, 4),
                 "coverage": round(e.coverage, 4),
                 "momentum": round(e.momentum, 4),
                 "rebound": round(e.rebound, 4)}
                for e in (tables[kind][z] for z in sorted(tables[kind]))]

    res.metrics = {
        "T": T,
        "window": W,
        "zone_table": _tab_rows("seg"),
        "quad_table": _tab_rows("quad"),
        "remainder_table": _tab_rows("rem"),
        "bias": round(bias, 4),
        "hot_zone": hot_zone,
        "cold_zone": cold_zone,
        "balance": balance,
        "defensive_candidates": cand_numbers,
        "active_low_zones": active_low,
        "heat_matrix_md": _heat_matrix_md(scores),
    }

    res.diagnostics = {
        "method": method,
        "window": W,
        "mean_zone_energy_ratio": round(finite(sum(r_vals) / len(r_vals), 1.0), 4),
        "low_energy_zones": low_zones,
        "rebound_active_zones": active_low,
        "candidate_count": len(cand_numbers),
    }

    # ── narrative（数值全部来自上方 metrics） ──
    hot_e = tables["seg"][hot_zone]
    cold_e = tables["seg"][cold_zone]
    res.add("macro",
            f"- **场域能量分布**（窗口 {W} 期）：最热场域为第 {hot_zone} 段 "
            f"[{10 * (hot_zone - 1) + 1}-{10 * hot_zone}]，能量比 r={hot_e.r:.2f}"
            f"（单期命中 {hot_e.d:.2f}，期望 {hot_e.e:.2f}）；"
            f"最冷场域为第 {cold_zone} 段 "
            f"[{10 * (cold_zone - 1) + 1}-{10 * cold_zone}]，r={cold_e.r:.2f}。",
            order=40)
    res.add("macro",
            f"- **冷热不均度**：场域偏向指数 bias={bias:.2f}"
            f"（max r − min r）；区间内密度最高为第 "
            f"{max(seg_keys, key=lambda z: tables['seg'][z].coverage)} 段"
            f"（覆盖率 {max(tables['seg'][z].coverage for z in seg_keys):.2f}），"
            f"能量净流入最强为第 "
            f"{max(seg_keys, key=lambda z: tables['seg'][z].momentum)} 段"
            f"（迁移 {max(tables['seg'][z].momentum for z in seg_keys):+.2f}/期）。",
            order=41)
    if cand_numbers:
        cand_txt = "、".join(f"{n:02d}" for n in cand_numbers[:8])
        res.add("risk",
                f"- **低能量回补场域**：第 "
                f"{'/'.join(str(z) for z in active_low)} 段当前能量低于期望，"
                f"且历史上冷窗后回补比例较高，候选号（按均衡子项排序）：{cand_txt}"
                f"{' 等' if len(cand_numbers) > 8 else ''}。可作为备防方向，"
                f"不构成投注建议。",
                order=42)
    else:
        res.add("risk", "- **低能量回补场域**：当前无同时满足低能量与历史回补活跃的场域。",
                order=42)
    res.add("dashboard", _heat_matrix_md(scores), order=60)

    return res
