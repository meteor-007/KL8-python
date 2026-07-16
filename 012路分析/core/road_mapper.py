from __future__ import annotations
from typing import Dict, List, Sequence, Tuple

def road_of(n: int) -> int:
    if not 1 <= n <= 80:
        raise ValueError(f"number out of range: {n}")
    return n % 3

def numbers_of_road(r: int) -> List[int]:
    if r not in (0, 1, 2):
        raise ValueError(f"invalid road: {r}")
    return [n for n in range(1, 81) if n % 3 == r]

def all_roads() -> Dict[int, int]:
    return {n: n % 3 for n in range(1, 81)}

def road_vector(numbers: Sequence[int]) -> Tuple[int, int, int]:
    counts = [0, 0, 0]
    for n in numbers:
        counts[road_of(n)] += 1
    return counts[0], counts[1], counts[2]

def fmt_ratio(r: Tuple[int, int, int]) -> str:
    return f"{r[0]}:{r[1]}:{r[2]}"
