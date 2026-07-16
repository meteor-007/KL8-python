from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Sequence, Tuple

from core.data_loader import KL8Draw

Road = Tuple[int, int, int]


def _dominant(road: Road) -> int:
    return max(range(3), key=lambda i: (road[i], -i))


class TransitionModel:
    """期→期分路比转移（Laplace +1）+ 主导路粗表。"""

    def __init__(self, draws: Sequence[KL8Draw]):
        self._pair_counts: Dict[Road, Counter] = defaultdict(Counter)
        self._all_states: set[Road] = set()
        for i in range(len(draws) - 1):
            a = draws[i].road
            b = draws[i + 1].road
            self._pair_counts[a][b] += 1
            self._all_states.add(a)
            self._all_states.add(b)
        if not self._all_states and draws:
            self._all_states.add(draws[-1].road)

    def next_distribution(self, state: Road) -> Dict[Road, float]:
        targets = self._pair_counts.get(state)
        universe = set(self._all_states)
        if targets:
            universe |= set(targets.keys())
        if not universe:
            return {state: 1.0}

        # Laplace +1 over observed universe for this from-state
        scores: Dict[Road, float] = {}
        for s in universe:
            scores[s] = float(targets.get(s, 0) if targets else 0) + 1.0
        total = sum(scores.values())
        return {s: v / total for s, v in scores.items()}

    def dominant_transition_table(self) -> Dict[int, Dict[int, float]]:
        """主导路 from -> to 概率粗表。"""
        coarse: Dict[int, Counter] = defaultdict(Counter)
        for src, counter in self._pair_counts.items():
            d_from = _dominant(src)
            for dst, c in counter.items():
                coarse[d_from][_dominant(dst)] += c

        out: Dict[int, Dict[int, float]] = {}
        for d_from, cnt in coarse.items():
            # Laplace over 0/1/2
            scores = {k: cnt.get(k, 0) + 1.0 for k in (0, 1, 2)}
            total = sum(scores.values())
            out[d_from] = {k: v / total for k, v in scores.items()}
        return out
