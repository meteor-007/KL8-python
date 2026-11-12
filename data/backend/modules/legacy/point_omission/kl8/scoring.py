# -*- coding: utf-8 -*-
"""Top5 与 5+2 推荐规则（§5.3 / §5.4）。"""
from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import ModuleResult
from .ensemble import FusionResult
from .numerics import finite


def zone_of(n: int) -> int:
    """10 号段编号 0..7。"""
    return (n - 1) // 10


def zone_label(n: int) -> str:
    z = zone_of(n) * 10 + 1
    return f"{z:02d}-{z + 9:02d}"


@dataclass
class Selection:
    core: list[int]                       # 五码核心
    relaxed: bool = False                 # 是否放宽过多样性约束
    short: bool = False                   # 是否因候选池不足而少于 5 个
    notes: list[str] = field(default_factory=list)


@dataclass
class Pick52:
    core: list[int]
    defensive: list[int] = field(default_factory=list)
    short_defensive: bool = False
    notes: list[str] = field(default_factory=list)


def select_top5(fusion: FusionResult,
                candidates: list[int],
                cfg) -> Selection:
    """§5.3：按 composite 降序取前 5，施加多样性约束。

    替换只从候选池顺位选取，被跳过的号仍留在池中——约束是在"已选结果"上
    计数的，因此不会出现回池造成的连锁超限。
    """
    top_n = int(cfg.scoring.top_n or 5)
    use_guard = bool(cfg.scoring.diversity_guard)
    base_max = int(cfg.scoring.diversity_max_per_zone or 3)

    pool = sorted(set(candidates), key=lambda n: (-fusion.composite.get(n, 0.0), n))
    notes: list[str] = []

    if not use_guard:
        picked = pool[:top_n]
        return Selection(core=picked, short=len(picked) < top_n,
                         notes=["多样性约束已关闭"])

    relaxed = False
    max_per_zone = base_max
    for _ in range(8):                     # 放宽上界，防止病态输入下死循环
        picked: list[int] = []
        zone_count: dict[int, int] = {}
        for n in pool:
            if len(picked) >= top_n:
                break
            z = zone_of(n)
            if zone_count.get(z, 0) < max_per_zone:
                picked.append(n)
                zone_count[z] = zone_count.get(z, 0) + 1
        if len(picked) >= top_n or max_per_zone >= len(pool):
            if max_per_zone > base_max:
                relaxed = True
                notes.append(f"多样性约束放宽至每段 {max_per_zone} 个")
            return Selection(core=picked, relaxed=relaxed,
                             short=len(picked) < top_n, notes=notes)
        max_per_zone += 1

    return Selection(core=picked, relaxed=True, short=len(picked) < top_n, notes=notes)


def _heatmap_rebound_candidates(heatmap: ModuleResult | None,
                                omission_scores: dict[int, float] | None,
                                pool: set[int]) -> list[int]:
    """heatmap 的"低能量场域 + 历史回补活跃"候选（§5.4）。

    低能量 = heatmap 主分数低；回补活跃 = omission 分数高。
    """
    if heatmap is None or not heatmap.sufficient:
        return []
    out = []
    for n in sorted(pool):
        energy = heatmap.scores.get(n, 0.0)
        rebound = (omission_scores or {}).get(n, 0.0)
        if energy <= 0.5 and rebound >= 0.5:
            out.append(n)
    return out


def select_52(fusion: FusionResult,
              core: list[int],
              pool: set[int],
              results: dict[str, ModuleResult],
              omission_scores: dict[int, float] | None,
              contrarian: ModuleResult | None,
              cfg) -> Pick52:
    """§5.4：两码备防。

    候选 = contrarian 通过质量门控的反向候选
          ∪ heatmap 中"低能量场域 + 历史回补活跃"的号码
    过滤：排除已在五码核心中的号
    排序：按 omission_score 降序
    选取：前 config.report.defensive_picks 个
    """
    want = int(cfg.report.defensive_picks or 2)

    cand: set[int] = set()
    notes: list[str] = []

    if contrarian is not None and contrarian.sufficient:
        gate = contrarian.metrics.get("gate_passed") if contrarian.metrics else None
        if isinstance(gate, (list, tuple, set)):
            cand.update(int(x) for x in gate)
        else:
            cand.update(contrarian.top(want * 4))

    reb = _heatmap_rebound_candidates(results.get("heatmap"), omission_scores, pool)
    if reb:
        cand.update(reb)

    cand -= set(core)
    cand &= set(pool)

    ordered = sorted(cand, key=lambda n: (-(omission_scores or {}).get(n, 0.0), n))
    picks = ordered[:want]

    if len(picks) < want:
        notes.append(f"备防候选不足：仅有 {len(picks)} 个（期望 {want} 个）")

    if not cand:
        notes.append("无通过门控的反向候选，备防码为空")

    return Pick52(core=list(core), defensive=picks,
                  short_defensive=len(picks) < want, notes=notes)
