from __future__ import annotations

from collections import Counter
from typing import Dict, List, Sequence, Tuple

from core.data_loader import KL8Draw
from core.road_mapper import fmt_ratio

Road = Tuple[int, int, int]


def _mean_road(draws: Sequence[KL8Draw]) -> Tuple[float, float, float]:
    if not draws:
        return (0.0, 0.0, 0.0)
    n = len(draws)
    s0 = sum(d.road[0] for d in draws)
    s1 = sum(d.road[1] for d in draws)
    s2 = sum(d.road[2] for d in draws)
    return (s0 / n, s1 / n, s2 / n)


def analyze_distribution(
    draws: Sequence[KL8Draw],
    window: int = 100,
    window_long: int = 300,
    expected: Tuple[float, float, float] = (6.5, 6.75, 6.75),
    top_n: int = 10,
) -> dict:
    """分路比分布、Top 形态、近窗热冷偏离。"""
    if not draws:
        return {
            "mean_all": (0.0, 0.0, 0.0),
            "mean_short": (0.0, 0.0, 0.0),
            "mean_long": (0.0, 0.0, 0.0),
            "top_patterns": [],
            "hot_cold": {"dev": (0.0, 0.0, 0.0), "window": window},
        }

    short = draws[-window:] if window > 0 else draws
    long = draws[-window_long:] if window_long > 0 else draws
    mean_all = _mean_road(draws)
    mean_short = _mean_road(short)
    mean_long = _mean_road(long)

    cnt = Counter(fmt_ratio(d.road) for d in draws)
    total = len(draws)
    top_patterns = [
        (ratio, c, c / total) for ratio, c in cnt.most_common(top_n)
    ]

    dev = tuple(mean_short[i] - expected[i] for i in range(3))
    return {
        "mean_all": mean_all,
        "mean_short": mean_short,
        "mean_long": mean_long,
        "top_patterns": top_patterns,
        "hot_cold": {"dev": dev, "window": min(window, len(draws))},
    }
