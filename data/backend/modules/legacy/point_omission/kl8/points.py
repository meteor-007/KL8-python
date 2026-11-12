# -*- coding: utf-8 -*-
"""循环三元组扩展 + 拓展集合基础统计（§2.4 / §2.5）。"""
from __future__ import annotations

from dataclasses import dataclass

from .numerics import safe_div, theoretical_std
from .data_io import Draw, NUM_BALLS

P_HIT = 20.0 / 80.0          # 单号单期命中概率 = 0.25


@dataclass(frozen=True)
class NumberStats:
    """单个号码的基础统计（§2.5）。"""
    n: int
    hit10: int          # 近 10 期出现次数  0–10
    hit3: int           # 近 3 期出现次数   0–3
    miss: int           # 连失期数，最新一期命中则为 0
    freq_full: int      # 全样本出现次数    0–T
    exp_hit: float      # 期望 = T × 0.25
    std: float          # 理论标准差 √(T·p·(1−p))
    z_score: float      # 热度偏离
    T: int              # 本号码所依据的历史期数


def expand(points) -> set[int]:
    """循环三元组扩展（§2.4）。

    prev = p-1 if p > 1 else 80
    next = p+1 if p < 80 else 1
    01 的前一位是 80，80 的后一位是 01。
    """
    out: set[int] = set()
    for p in points:
        prev = p - 1 if p > 1 else NUM_BALLS
        nxt = p + 1 if p < NUM_BALLS else 1
        out.update((prev, p, nxt))
    return out


def _miss_streak(draws: list[Draw], n: int) -> int:
    """从最新一期往前数连续未开出的期数；最新一期命中则 0。"""
    streak = 0
    for d in draws:
        if n in d.numbers_set:
            break
        streak += 1
    return streak


def compute_base_stats(draws: list[Draw],
                       expanded_set: set[int] | None = None) -> dict[int, NumberStats]:
    """计算基础统计。

    draws 必须**按时序降序（最新在前）**，且已由调用方裁剪到目标期之前
    （无前视，§9.2）。

    覆盖全部 1–80 号：模块需要对全 80 号打分，只在推荐阶段才筛拓展集合
    （见 §3.5 与 test_module_ignores_expanded_restriction）。expanded_set
    作为上下文保留在签名中，不用于限制计算范围。
    """
    T = len(draws)
    std = theoretical_std(T, P_HIT)
    exp_hit = T * P_HIT

    # 预统计：每个号在全部期次中的命中位置（用于 hit10/hit3）
    recent10 = draws[:10]
    recent3 = draws[:3]
    freq: dict[int, int] = {n: 0 for n in range(1, NUM_BALLS + 1)}
    for d in draws:
        for n in d.numbers:
            freq[n] += 1

    stats: dict[int, NumberStats] = {}
    for n in range(1, NUM_BALLS + 1):
        f = freq[n]
        stats[n] = NumberStats(
            n=n,
            hit10=sum(1 for d in recent10 if n in d.numbers_set),
            hit3=sum(1 for d in recent3 if n in d.numbers_set),
            miss=_miss_streak(draws, n),
            freq_full=f,
            exp_hit=exp_hit,
            std=std,
            z_score=safe_div(f - exp_hit, std, 0.0),
            T=T,
        )
    return stats


def stats_for(stats: dict[int, NumberStats], n: int) -> NumberStats | None:
    return stats.get(n)
