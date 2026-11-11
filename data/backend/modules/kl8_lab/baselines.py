# -*- coding: utf-8 -*-
"""随机基线（§9.5）。

**重要的解析事实**：无论从拓展集合里抽 5 个、还是从全 80 里抽 5 个，命中数
都服从同一个超几何分布 Hypergeom(N=80, K=20, n=5)，因此两条基线的
期望（1.25）与方差（0.8900）**完全相同**。

方案要求 B1/B2 都算，理由不是"两者分布不同"，而是它们回答两个不同的问题：

  B1「系统是否胜过只在点位拓展集里瞎选」——检验的是**方法层**的价值
  B2「系统是否胜过从全部 80 号里瞎选」——检验的是**整条链路**的价值

两者共用同一个零分布，因此本模块把它们实现为同一个解析零分布 + 两次
Monte Carlo 验证（确认经验均值确实落在 1.25 附近），并把重点放在两个
**输入信息量指标**上：

  lift_exp —— 点位拓展集合本身的信息量（若 ≈1，后续 11 个方法不可能救回来）
  lift_pts —— 原始 20 点位的信息量
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .numerics import (EPS, hypergeom_mean, hypergeom_var, safe_div,
                       theoretical_std)
from .stats_tests import (E_HITS, SD_HITS, TestResult, evaluate,
                          evaluate_variable)

E_EXPANDED_PER_NUMBER = 0.25


@dataclass
class BaselineReport:
    T: int = 0
    system: TestResult | None = None
    null_mean: float = E_HITS
    null_sd: float = SD_HITS
    b1_mc_mean: float = 0.0
    b2_mc_mean: float = 0.0
    expanded_lift: TestResult | None = None
    points_lift: TestResult | None = None
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "| 对象 | 每期抽取 | T | 均值命中 | 期望 | lift | z | p | 判定 |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        if self.system:
            lines.append(_row("系统 Top5", "5", self.system))
        lines.append(
            f"| B1 拓展集内随机 | 5 | {self.T} | {self.b1_mc_mean:.4f} | "
            f"{self.null_mean:.4f} | 1.0000 | — | — | 零分布 |")
        lines.append(
            f"| B2 全 80 随机 | 5 | {self.T} | {self.b2_mc_mean:.4f} | "
            f"{self.null_mean:.4f} | 1.0000 | — | — | 零分布 |")
        if self.expanded_lift:
            lines.append(_row("点位拓展集合", "|expanded|", self.expanded_lift))
        if self.points_lift:
            lines.append(_row("原始 20 点位", "20", self.points_lift))
        return "\n".join(lines)


def _row(label: str, size: str, r: TestResult) -> str:
    return (f"| {label} | {size} | {r.T} | {r.mean_hits:.4f} | {r.expected:.4f} | "
            f"{r.lift:.4f} | {r.z:+.3f} | {r.p_value:.4f} | {r.verdict} |")


def build_baselines(top5_hits: list[float],
                    expanded_hits: list[float],
                    expanded_sizes: list[int],
                    points_hits: list[float],
                    actual_draws: list[set[int]],
                    expanded_sets: list[set[int]],
                    n_iters: int = 1000,
                    seed: int = 42,
                    alpha: float = 0.05) -> BaselineReport:
    T = len(actual_draws)
    rep = BaselineReport(T=T)
    if T == 0:
        rep.notes.append("无可用配对期，基线不可计算")
        return rep

    rng = np.random.default_rng(seed)

    # MC 验证：两条基线的经验均值都应落在 1.25 附近
    rep.b2_mc_mean = _mc_mean(rng, actual_draws, None, 5, n_iters)
    rep.b1_mc_mean = _mc_mean(rng, actual_draws, expanded_sets, 5, n_iters)

    for label, got in (("B2", rep.b2_mc_mean), ("B1", rep.b1_mc_mean)):
        if abs(got - E_HITS) > 4 * SD_HITS / math.sqrt(T * n_iters):
            rep.notes.append(
                f"{label} 的 Monte Carlo 均值 {got:.4f} 偏离解析期望 {E_HITS} 超出容差，"
                f"请检查抽样实现。")

    # 系统对照零分布
    rep.system = evaluate(top5_hits, label="系统 Top5", alpha=alpha)

    # 输入信息量
    rep.expanded_lift = evaluate_variable(
        expanded_hits, expanded_sizes, label="点位拓展集合", alpha=alpha)
    rep.points_lift = evaluate(points_hits, label="原始 20 点位", alpha=alpha,
                               expected=20 * E_EXPANDED_PER_NUMBER)

    if (rep.expanded_lift and abs(rep.expanded_lift.lift - 1.0) < 0.02
            and not rep.expanded_lift.significant):
        rep.notes.append(
            "**点位拓展集合本身未显示超过随机的信息量**（lift≈1）。"
            "若如此，后续 11 个方法无论如何组合都难以产生真实优势——"
            "这是本系统最重要的先决检验。")

    return rep


def _mc_mean(rng, actual_draws: list[set[int]], pools, n_pick: int,
             n_iters: int) -> float:
    """逐期重采样 n_iters 次，返回全局平均命中数。"""
    total_hits = 0.0
    total_draws = 0
    for i, actual in enumerate(actual_draws):
        pool = pools[i] if pools is not None else None
        cand = np.arange(1, 81) if pool is None else np.fromiter(sorted(pool), dtype=int)
        if len(cand) == 0:
            continue
        k = min(n_pick, len(cand))
        for _ in range(n_iters):
            pick = rng.choice(cand, size=k, replace=False)
            total_hits += sum(1 for x in pick if int(x) in actual)
            total_draws += 1
    return safe_div(total_hits, total_draws, 0.0)
