# -*- coding: utf-8 -*-
"""概率校准评估：Brier / LogLoss / 可靠性分箱（对应整改清单 5.2.5）。

用法：给定逐期 (prob, hit) 对，比较模型概率与常数基线 0.25。
若 Brier 不优于常数 0.25，说明分数没有概率含义，不应按概率解读。
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

BASE_P = 0.25


def _clean(pairs: Iterable[Sequence[float]]) -> list[tuple[float, int]]:
    out = []
    for p, y in pairs:
        p = float(p)
        y = int(y)
        if not (0.0 <= p <= 1.0) or y not in (0, 1):
            raise ValueError(f"非法样本 ({p}, {y})：prob 须在 [0,1]，hit 须为 0/1")
        out.append((p, y))
    return out


def brier(pairs) -> float:
    data = _clean(pairs)
    if not data:
        return float("nan")
    return sum((p - y) ** 2 for p, y in data) / len(data)


def log_loss(pairs, eps: float = 1e-12) -> float:
    data = _clean(pairs)
    if not data:
        return float("nan")
    total = 0.0
    for p, y in data:
        p = min(1.0 - eps, max(eps, p))
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(data)


def reliability(pairs, n_bins: int = 10) -> list[dict]:
    data = _clean(pairs)
    bins = []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        subset = [(p, y) for p, y in data
                  if lo <= p < hi or (i == n_bins - 1 and p == 1.0)]
        if not subset:
            continue
        bins.append({
            "bin": f"[{lo:.1f},{hi:.1f}]",
            "n": len(subset),
            "mean_prob": sum(p for p, _ in subset) / len(subset),
            "hit_rate": sum(y for _, y in subset) / len(subset),
        })
    return bins


def summary(pairs) -> dict:
    data = _clean(pairs)
    n = len(data)
    base_brier = BASE_P * (1 - BASE_P)
    base_ll = -(BASE_P * math.log(BASE_P) + (1 - BASE_P) * math.log(1 - BASE_P))
    return {
        "n": n,
        "brier": brier(data),
        "brier_baseline": base_brier,
        "log_loss": log_loss(data),
        "log_loss_baseline": base_ll,
        "brier_skill": 1.0 - brier(data) / base_brier if n else None,
        "reliability": reliability(data),
    }


def render(res: dict) -> str:
    lines = [
        f"样本数        : {res['n']}",
        f"Brier         : {res['brier']:.6f}（常数 0.25 基线 {res['brier_baseline']:.6f}）",
        f"LogLoss       : {res['log_loss']:.6f}（常数基线 {res['log_loss_baseline']:.6f}）",
        f"Brier Skill   : {res['brier_skill']:+.4f}（>0 才优于常数基线）" if res["brier_skill"] is not None else "",
        "",
        "| 概率分箱 | n | 平均概率 | 实际命中率 |",
        "|---|---|---|---|",
    ]
    for b in res["reliability"]:
        lines.append(f"| {b['bin']} | {b['n']} | {b['mean_prob']:.3f} | {b['hit_rate']:.3f} |")
    return "\n".join(lines)