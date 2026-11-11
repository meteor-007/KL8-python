# -*- coding: utf-8 -*-
from collections import Counter
from typing import List, Set, Dict, Any

def top_freq_in_window(draws: List[Set[int]], t: int, window: int = 20, top_n: int = 5) -> List[int]:
    cnt = Counter()
    start_idx = max(0, t - window)
    for s in draws[start_idx:t]:
        cnt.update(s)
    return [n for n, _ in cnt.most_common(top_n)]

def walk_forward_stable(draws: List[Set[int]], window: int = 20, top_n: int = 5, min_history: int = 30) -> Dict[str, Any]:
    hits_list = []
    n_periods = 0
    total = len(draws)
    start_t = min(min_history, total - 1) if total > min_history else 1

    for t in range(start_t, total):
        picks = top_freq_in_window(draws, t, window, top_n)
        h = len(set(picks) & draws[t])
        hits_list.append(h)
        n_periods += 1

    mean_hits = sum(hits_list) / n_periods if n_periods else 0.0
    expected_hits = top_n * (20 / 80)
    lift = (mean_hits / expected_hits) if expected_hits > 0 else 0.0

    return {
        'n_periods': n_periods,
        'mean_hits_per_period': round(mean_hits, 2),
        'expected_hits': round(expected_hits, 2),
        'lift': round(lift, 2),
        'hits_list': hits_list
    }

def is_lookahead_free(period_idx: int, window: int, n_periods: int) -> bool:
    return (period_idx - window >= 0) and (period_idx < n_periods)
