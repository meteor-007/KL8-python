# -*- coding: utf-8 -*-
"""覆盖/平衡组合构造（对应整改清单 5.2.6）。

数学事实：m 张 k 码票的**期望总命中**恒为 m·k/4，任何构造都改变不了；
但把每个号的出现次数尽量均衡，可以降低总命中的方差。
当 m·k 是 80 的整数倍时，每个号出现次数相同，方差可降到 0
（每期恰好命中 m·k/4 个）。

本工具只做组合覆盖，不构成投注建议。
"""
from __future__ import annotations

from typing import Sequence

BASE_P = 0.25


def build_balanced_tickets(n_tickets: int, size: int = 5,
                           n_numbers: int = 80) -> tuple[list[list[int]], list[int]]:
    """贪心轮转：每张票选当前出现次数最少的 size 个号（并列按号序）。"""
    if n_tickets < 0 or size <= 0 or size > n_numbers:
        raise ValueError("参数非法：需 0 < size <= n_numbers，tickets >= 0")
    counts = [0] * n_numbers
    tickets: list[list[int]] = []
    for _ in range(n_tickets):
        order = sorted(range(n_numbers), key=lambda i: (counts[i], i))
        chosen = order[:size]
        for i in chosen:
            counts[i] += 1
        tickets.append(sorted(i + 1 for i in chosen))
    return tickets, counts


def expected_hits(n_tickets: int, size: int = 5, p: float = BASE_P) -> float:
    return n_tickets * size * p


def total_variance(counts: Sequence[int], p: float = BASE_P) -> float:
    """总命中数的方差（超几何抽样，固定每期开 20 号）。"""
    N = len(counts)
    if N <= 1:
        return 0.0
    A = sum(counts)
    s2 = sum(a * a for a in counts)
    return p * (1 - p) * (s2 * N / (N - 1) - A * A / (N - 1))


def summarize(n_tickets: int, size: int = 5, n_numbers: int = 80) -> dict:
    tickets, counts = build_balanced_tickets(n_tickets, size, n_numbers)
    var = total_variance(counts)
    indep_var = n_tickets * size * BASE_P * (1 - BASE_P) * ((n_numbers - size) / (n_numbers - 1))
    return {
        "n_tickets": n_tickets,
        "size": size,
        "appearances_min": min(counts) if counts else 0,
        "appearances_max": max(counts) if counts else 0,
        "expected_hits": expected_hits(n_tickets, size),
        "variance": var,
        "sd": var ** 0.5,
        "independent_variance": indep_var,
        "variance_reduction": 1 - var / indep_var if indep_var > 0 else 0.0,
        "tickets": tickets,
        "counts": counts,
    }


def render(res: dict) -> str:
    lines = [
        f"票数 / 每票码数 : {res['n_tickets']} / {res['size']}",
        f"每号出现次数    : {res['appearances_min']}–{res['appearances_max']}",
        f"期望总命中      : {res['expected_hits']:.2f}（不随构造改变）",
        f"总命中方差      : {res['variance']:.4f}（SD {res['sd']:.3f}）",
        f"独立票方差      : {res['independent_variance']:.4f}",
        f"方差降幅        : {res['variance_reduction']:.1%}",
        "",
        "| 票号 | 号码 |",
        "|---|---|",
    ]
    for i, t in enumerate(res["tickets"], 1):
        lines.append(f"| {i} | {' '.join(f'{n:02d}' for n in t)} |")
    lines.append("")
    lines.append("> 覆盖构造只改变方差，不改变每元期望；不构成投注建议。")
    return "\n".join(lines)