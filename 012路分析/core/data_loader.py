from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from config.paths import KL8_HISTORY_FILE
from core.road_mapper import road_vector


@dataclass
class KL8Draw:
    date: str
    period: str
    numbers: List[int]
    road: Tuple[int, int, int]

    @property
    def sum_value(self) -> int:
        return sum(self.numbers)

    @property
    def odd_even(self) -> Tuple[int, int]:
        odd = sum(1 for n in self.numbers if n % 2 == 1)
        return odd, 20 - odd


class DataLoader:
    """只读开奖历史 kl8_history_final.txt（与点位 daily_points 无关）。"""

    def __init__(self, history_file: Optional[Path] = None):
        self.history_file = Path(history_file) if history_file else KL8_HISTORY_FILE
        self._history: List[KL8Draw] = []
        self.skipped: int = 0
        self._loaded = False

    def load(self) -> None:
        if not self.history_file.exists():
            raise FileNotFoundError(f"开奖历史不存在: {self.history_file}")
        self._history = []
        self.skipped = 0
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                draw = self._parse_line(line)
                if draw is None:
                    self.skipped += 1
                    continue
                self._history.append(draw)
        # Ascending: oldest first, newest last
        self._history.sort(key=lambda d: d.period)
        self._loaded = True

    def _parse_line(self, line: str) -> Optional[KL8Draw]:
        try:
            parts = line.split(",")
            date_str = parts[0].split(":", 1)[1]
            period_str = parts[1].split(":", 1)[1]
            numbers_str = parts[2].split(":", 1)[1]
            numbers = sorted(int(x) for x in numbers_str.split("-"))
            if len(numbers) != 20 or not all(1 <= n <= 80 for n in numbers):
                return None
            if len(set(numbers)) != 20:
                return None
            return KL8Draw(date_str, period_str, numbers, road_vector(numbers))
        except (IndexError, ValueError):
            return None

    @property
    def history(self) -> List[KL8Draw]:
        if not self._loaded:
            self.load()
        return self._history

    @property
    def latest(self) -> Optional[KL8Draw]:
        if not self._loaded:
            self.load()
        return self._history[-1] if self._history else None
