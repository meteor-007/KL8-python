from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

import numpy as np

from core.data_loader import KL8Draw

Road = Tuple[int, int, int]


def _dominant(road: Road) -> int:
    return max(range(3), key=lambda i: (road[i], -i))


def _streak_info(
    draws: Sequence[KL8Draw],
    road_idx: int,
    expected: float,
) -> dict:
    """相对期望的偏高/偏低 streak。"""
    signs: List[int] = []
    for d in draws:
        v = d.road[road_idx]
        if v > expected:
            signs.append(1)
        elif v < expected:
            signs.append(-1)
        else:
            signs.append(0)

    max_high = max_low = 0
    cur = 0
    cur_dir = 0
    lengths_high: List[int] = []
    lengths_low: List[int] = []

    def flush():
        nonlocal max_high, max_low, cur, cur_dir
        if cur_dir == 1:
            lengths_high.append(cur)
            max_high = max(max_high, cur)
        elif cur_dir == -1:
            lengths_low.append(cur)
            max_low = max(max_low, cur)

    for s in signs:
        if s == 0:
            flush()
            cur = 0
            cur_dir = 0
        elif s == cur_dir:
            cur += 1
        else:
            flush()
            cur_dir = s
            cur = 1
    flush()

    # current streak at end (ignore trailing zeros already flushed)
    current_dir = 0
    current_len = 0
    if signs:
        # walk back from end skipping zeros
        i = len(signs) - 1
        while i >= 0 and signs[i] == 0:
            i -= 1
        if i >= 0:
            current_dir = signs[i]
            current_len = 1
            i -= 1
            while i >= 0 and signs[i] == current_dir:
                current_len += 1
                i -= 1

    return {
        "max_high": max_high,
        "max_low": max_low,
        "current_dir": current_dir,  # 1 high, -1 low, 0 flat
        "current_len": current_len,
        "avg_high": float(np.mean(lengths_high)) if lengths_high else 0.0,
        "avg_low": float(np.mean(lengths_low)) if lengths_low else 0.0,
    }


def analyze_association(
    draws: Sequence[KL8Draw],
    expected: Tuple[float, float, float] = (6.5, 6.75, 6.75),
) -> dict:
    streaks = {
        r: _streak_info(draws, r, expected[r]) for r in (0, 1, 2)
    }

    sums = [d.sum_value for d in draws]
    sum_cross: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    if len(sums) >= 3:
        q1, q2 = np.percentile(sums, [33.33, 66.67])
    else:
        q1 = q2 = (sums[0] if sums else 0)

    for d in draws:
        dom = _dominant(d.road)
        s = d.sum_value
        if s <= q1:
            bucket = "low"
        elif s <= q2:
            bucket = "mid"
        else:
            bucket = "high"
        sum_cross[f"dom{dom}"][bucket] += 1

    return {
        "streaks": streaks,
        "sum_cross": {k: dict(v) for k, v in sum_cross.items()},
    }
