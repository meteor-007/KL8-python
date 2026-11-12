# -*- coding: utf-8 -*-
"""统一接口契约（§3.5）。

> 说明：本文件不属于 §3.1 目录树中显式列出的文件。把契约单独成文件是为了
> 让 13 个方法模块与融合层共享同一份定义，避免循环 import。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .data_io import Draw
from .points import NumberStats
from .numerics import clip01, finite

# narrative.section 的合法取值（对应报告六章节 + 一句话结论）
SECTIONS = ("overview", "dashboard", "top5", "macro", "risk", "tree", "final")


@dataclass
class NarrativeBlock:
    """结构化解读片段，由 report 层按 section 路由到报告章节。"""
    section: str
    text: str
    order: int = 0

    def __post_init__(self):
        if self.section not in SECTIONS:
            raise ValueError(f"未知 narrative section: {self.section}（合法值 {SECTIONS}）")


@dataclass
class ModuleResult:
    """11 个同构分析模块的统一返回。

    scores 覆盖 **全部 1–80 号**，值为 [0,1] 的有限数。

    为什么不把拓展集合外的号码置 0：拓展集合是"输入点位"的邻域，而方法应当
    对全号段给出判断——只在推荐阶段才用拓展集合做筛选。若模块内部就限定在
    拓展集合内计算，则 §9.5 的 lift_exp 检验退化为恒等式，且 contrarian 无法
    观察集合外号码。融合阶段由 ensemble 调用 `masked_scores()` 施加约束。
    """
    name: str
    scores: dict[int, float]
    metrics: dict[str, Any] = field(default_factory=dict)
    narrative: list[NarrativeBlock] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    sufficient: bool = True

    def __post_init__(self):
        cleaned: dict[int, float] = {}
        for n in range(1, 81):
            cleaned[n] = clip01(finite(self.scores.get(n, 0.0), 0.0))
        self.scores = cleaned

    def masked_scores(self, allowed) -> dict[int, float]:
        """把拓展集合外的号码压为 0.0。仅在融合/推荐阶段调用。"""
        allow = set(allowed)
        return {n: (v if n in allow else 0.0) for n, v in self.scores.items()}

    def top(self, k: int = 5, restrict_to=None) -> list[int]:
        """降序取前 k 个号码。restrict_to 不为空时先做遮罩。"""
        src = self.masked_scores(restrict_to) if restrict_to else self.scores
        return sorted(src, key=lambda n: (-src[n], n))[:k]

    def add(self, section: str, text: str, order: int = 0) -> None:
        self.narrative.append(NarrativeBlock(section, text, order))

    def degrade(self, reason: str) -> None:
        """标记数据不足并归零全部得分（§3.6 样本量不足的处置）。"""
        self.sufficient = False
        self.diagnostics["degraded"] = reason
        self.scores = {n: 0.0 for n in range(1, 81)}


@dataclass
class NumberGateStats:
    """对抗门控（§4.13）所需的逐号证据。"""
    n: int
    z_score: float = 0.0
    miss: int = 0
    hit10: int = 0
    composite: float = 0.0
    h_values: dict[str, float] = field(default_factory=dict)
    crowding: float = 0.0          # 拥挤度 0–1，越高越可能是"共识陷阱"
    sample_size: int = 0


class AnalyzeFn(Protocol):
    """11 个同构模块的统一签名（§3.5）。"""

    def __call__(self,
                 draws: list[Draw],
                 expanded_set: set[int],
                 base_stats: dict[int, NumberStats],
                 cfg: Any) -> ModuleResult: ...


def empty_result(name: str, reason: str = "") -> ModuleResult:
    res = ModuleResult(name=name, scores={})
    if reason:
        res.degrade(reason)
    return res
