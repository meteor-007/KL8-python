# -*- coding: utf-8 -*-
"""对冲方法集：反向心理博弈模型 Contrarian Insight（§4.4）。

**元模块**（非 11 个同构模块之一，签名见 §3.5 末尾）。它消费其他模块的
`scores` 构造"拥挤度"，对共识过强的号码行使反向否决，并通过 omission 的
Z 反弹分做质量门控，产出"反向候选"清单，供 §5.4 备防两码与报告"拥挤"预警。

算法（严格照 §4.4）：
  1. 共识度 consensus[n] = mean_{m ∈ 主分方法集} scores_m[n]
     —— 主分方法集为 11 个同构模块（§4.14），显式排除 contrarian 自身与 adversarial。
  2. 拥挤度 crowd[n] = consensus[n]。
  3. 质量门控：omission_z_rebound[n] ≥ contrarian_gate_z（默认 0.5）
     且 crowd[n] < contrarian_veto（默认 0.75）。
     通过者 contrarian[n] = 1 − crowd[n]；
     未通过者 contrarian[n] = crowd[n]（反向否决标记，记入 metrics.vetoed，不进候选）。
  4. 反向候选 = 通过门控者，按 omission 得分降序（§5.4）。

本模块**不进 H1–H7 主分**（§4.14 对冲方法集，避免双重计数）。
"""
from __future__ import annotations

from typing import Any

from .contracts import ModuleResult
from .numerics import clip01, entropy_normalized, finite, mean

N = 80

# §4.14 主分方法集：11 个同构模块。顺序即 §4.4 给定顺序。
MAIN_METHODS: tuple[str, ...] = (
    "cluster", "cyclic", "heatmap", "markov", "fibonacci",
    "linalg_svd", "complex_fft", "graph_net", "volatility",
    "remainder", "entropy",
)
# §4.4 明确排除：contrarian 自身与 adversarial（本就在主分集之外，双保险）
META_METHODS: tuple[str, ...] = ("contrarian", "adversarial")

DEFAULT_GATE_Z = 0.5     # config.thresholds.contrarian_gate_z
DEFAULT_VETO = 0.75      # config.thresholds.contrarian_veto
MAX_CANDIDATES_SHOWN = 10


# ── 配置读取（兼容 Section / dict / None，§3.4）─────────────────

def _threshold(cfg: Any, key: str, default: float) -> float:
    """从 cfg.thresholds 读取阈值；任意退化 cfg 都回落到默认值。"""
    val = None
    try:
        val = getattr(getattr(cfg, "thresholds", None), key, None)
    except Exception:
        val = None
    if val is None:
        try:
            val = (cfg or {})["thresholds"][key]        # dict 形态的 cfg
        except Exception:
            val = None
    return finite(val, default) if val is not None else default


def _scores_of(res: Any) -> dict[int, float] | None:
    """取出某模块结果的全 80 号 scores；非法输入返回 None（不抛异常）。"""
    sc = getattr(res, "scores", None)
    if not isinstance(sc, dict) or not sc:
        return None
    return {n: clip01(finite(sc.get(n, 0.0), 0.0)) for n in range(1, N + 1)}


def _collect_consensus(results: Any) -> tuple[dict[int, float], list[str]]:
    """按主分方法集求逐号共识度。返回 (consensus, 实际参与的模块名)。"""
    mats: list[dict[int, float]] = []
    used: list[str] = []
    if isinstance(results, dict):
        for name in MAIN_METHODS:
            if name in META_METHODS:                    # 显式排除，§4.4
                continue
            sc = _scores_of(results.get(name))
            if sc is None:
                continue
            mats.append(sc)
            used.append(name)

    if not mats:
        return {n: 0.0 for n in range(1, N + 1)}, []

    consensus = {n: clip01(mean([m[n] for m in mats])) for n in range(1, N + 1)}
    return consensus, used


def _resolve_z(z_rebound: Any, omission: Any) -> tuple[dict[int, float] | None, str]:
    """确定质量门控所用的反弹分 z。返回 (z, 来源标记)。

    优先用调用方传入的 omission_z_rebound（§3.5 / §4.4 门控口径）。
    缺失时退化为 omission 模块自身的 rank 归一得分（仍是 [0,1] 有界量，
    阈值 0.5 量级可比），并把来源记入 diagnostics 以免误读。
    """
    if isinstance(z_rebound, dict) and z_rebound:
        return {n: finite(z_rebound.get(n, 0.0), 0.0) for n in range(1, N + 1)}, \
               "omission_z_rebound"

    if omission is None or getattr(omission, "sufficient", True) is False:
        return None, "none"                             # 数据不足，不予门控

    sc = _scores_of(omission)
    if sc is None:
        return None, "none"
    return sc, "omission_score_fallback"


def _detail(n: int, crowd: float, z: float, base_stats: Any) -> dict[str, Any]:
    """候选号的可解释明细（基础统计仅作附注，不参与门控）。"""
    row: dict[str, Any] = {"n": n, "crowd": round(crowd, 4), "z_rebound": round(z, 3)}
    st = base_stats.get(n) if isinstance(base_stats, dict) else None
    if st is not None:
        row["miss"] = int(getattr(st, "miss", 0))
        row["hit10"] = int(getattr(st, "hit10", 0))
        row["z_score"] = round(finite(getattr(st, "z_score", 0.0), 0.0), 3)
    return row


# ── 主入口（§3.5 末尾元模块签名）─────────────────────────────

def analyze_contrarian(results: dict[str, ModuleResult],
                       omission: ModuleResult,
                       cfg,
                       z_rebound: dict[int, float] | None = None,
                       base_stats: dict | None = None,
                       expanded_set: set[int] | None = None) -> ModuleResult:
    """反向心理博弈。results 为其他模块结果的字典（键为模块 key）。"""
    gate_z = _threshold(cfg, "contrarian_gate_z", DEFAULT_GATE_Z)
    veto = _threshold(cfg, "contrarian_veto", DEFAULT_VETO)
    ns = list(range(1, N + 1))

    consensus, used = _collect_consensus(results)
    om_score = _scores_of(omission) or {}

    # ── 无共识来源：本模块无内容可判 ──
    if not used:
        res = ModuleResult(name="contrarian", scores={})
        res.metrics = {"n_modules": 0, "gate_z": round(gate_z, 4),
                       "veto": round(veto, 4)}
        res.diagnostics = {"degraded": "no_modules", "modules_used": []}
        res.degrade("无任何主分模块结果，共识度无法计算")
        res.add("risk", "- 反向博弈：未收到其他模块评分，拥挤度无从计算，本模块已跳过。",
                order=30)
        return res

    # ── 质量门控依据（§4.4 第 3 步）──
    z, z_source = _resolve_z(z_rebound, omission)
    if z is None:
        res = ModuleResult(name="contrarian", scores={})
        res.metrics = {"n_modules": len(used), "gate_z": round(gate_z, 4),
                       "veto": round(veto, 4),
                       "modules_used": used}
        res.diagnostics = {"degraded": "no_omission_z", "z_source": z_source}
        res.degrade("omission 缺失或数据不足，反弹门控无依据")
        res.add("risk", "- 反向博弈：遗漏模块无可用反弹分，质量门控无法执行，本模块已跳过。",
                order=30)
        return res

    # ── 逐号门控与打分 ──
    passed = [n for n in ns if z[n] >= gate_z and consensus[n] < veto]
    passed_set = set(passed)
    scores = {n: (clip01(1.0 - consensus[n]) if n in passed_set
                  else clip01(consensus[n])) for n in ns}

    vetoed = [n for n in ns if n not in passed_set]
    vetoed_crowd = [n for n in ns if consensus[n] >= veto]
    vetoed_rebound = [n for n in vetoed if n not in set(vetoed_crowd)]

    # §5.4：候选按 omission 得分降序（缺失时退化为反弹分）
    def _om(n: int) -> float:
        return om_score.get(n, 0.0) if om_score else z[n]

    candidates = sorted(passed, key=lambda n: (-_om(n), -z[n], n))

    top_crowd = sorted(ns, key=lambda n: (-consensus[n], n))[:5]

    res = ModuleResult(name="contrarian", scores=scores)
    res.metrics = {
        "modules_used": used,
        "n_modules": len(used),
        "gate_z": round(gate_z, 4),
        "veto": round(veto, 4),
        "consensus": {n: round(consensus[n], 6) for n in ns},
        "crowd": {n: round(consensus[n], 6) for n in ns},   # §809 refute_crowd 同源
        "crowd_top": [(n, round(consensus[n], 3)) for n in top_crowd],
        "candidates": candidates,          # 反向候选 = 通过质量门控者
        "gate_passed": candidates,         # scoring.select_52 读取的键（§5.4）
        "candidate_count": len(candidates),
        "vetoed": sorted(vetoed),
        "vetoed_crowd": sorted(vetoed_crowd),
        "vetoed_rebound": sorted(vetoed_rebound),
        "candidate_detail": [_detail(n, consensus[n], z[n], base_stats)
                             for n in candidates[:MAX_CANDIDATES_SHOWN]],
    }
    res.diagnostics = {
        "z_source": z_source,
        "n_passed": len(candidates),
        "n_vetoed": len(vetoed),
        "n_vetoed_crowd": len(vetoed_crowd),
        # 拥挤分布集中度：越低说明共识越集中于少数号（拥挤越危险）
        "crowding_entropy": round(
            entropy_normalized([max(consensus[n], 0.0) for n in ns]), 4),
        "mean_crowd": round(mean([consensus[n] for n in ns]), 4),
        "expanded_size": len(expanded_set) if expanded_set else 0,
        "base_stats_used": bool(isinstance(base_stats, dict) and base_stats),
    }

    # ── narrative（§3.5：至少一条 macro/risk，数值取自实算 metrics）──
    res.add("macro",
            f"- **拥挤度预警**：{len(used)} 个主分模块的逐号共识中，"
            f"共识度最高的为 "
            f"{'、'.join(f'{n:02d}({consensus[n]:.2f})' for n in top_crowd)}"
            f"（均值 {res.diagnostics['mean_crowd']:.3f}，"
            f"集中度熵 {res.diagnostics['crowding_entropy']:.3f}）。",
            order=30)
    res.add("risk",
            f"- **反向博弈**：{len(vetoed)} 个号码被否决——其中拥挤度 ≥ "
            f"{veto:.2f} 者 {len(vetoed_crowd)} 个、反弹分 < {gate_z:.2f} 者 "
            f"{len(vetoed_rebound)} 个；通过质量门控的反向候选 {len(candidates)} 个"
            f"（门控依据：{z_source}）。",
            order=31)
    if candidates:
        res.add("tree",
                f"- **备防候选池**（低拥挤 + 合理遗漏结构，按遗漏得分降序）："
                f"{'、'.join(f'{n:02d}' for n in candidates[:MAX_CANDIDATES_SHOWN])}"
                f"{'…' if len(candidates) > MAX_CANDIDATES_SHOWN else ''}。",
                order=32)
    else:
        res.add("tree", "- **备防候选池**：本期无号码同时满足低拥挤与反弹门控。",
                order=32)
    if z_source == "omission_score_fallback":
        res.add("risk",
                "- 反向博弈：未获得 omission 的 z 反弹分，门控退化用其 rank 归一得分，"
                "严格性下降。", order=41)

    return res


# 契约层按模块名统一分派时的别名（元模块签名见 §3.5 末尾；对退化输入不抛异常）
analyze = analyze_contrarian
