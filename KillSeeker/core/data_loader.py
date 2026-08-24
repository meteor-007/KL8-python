"""
MorphoSeeker V1.0 — 数据加载层
只读共享 data/ 层，提供统一的数据访问接口
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import numpy as np

from config.paths import KL8_HISTORY_FILE


@dataclass
class KL8Draw:
    """单期开奖数据"""
    date: str
    period: str
    numbers: List[int]  # 20个开奖号码(已排序)

    @property
    def number_set(self) -> set:
        return set(self.numbers)

    @property
    def matrix_8x10(self) -> np.ndarray:
        """将20个号码映射到8×10二值矩阵"""
        matrix = np.zeros((8, 10), dtype=np.int8)
        for num in self.numbers:
            row = (num - 1) // 10
            col = (num - 1) % 10
            matrix[row, col] = 1
        return matrix

    @property
    def zone_counts(self) -> List[int]:
        """8个十年区间的出号数"""
        counts = [0] * 8
        for num in self.numbers:
            zone = (num - 1) // 10
            counts[zone] += 1
        return counts

    @property
    def sum_value(self) -> int:
        return sum(self.numbers)

    @property
    def span(self) -> int:
        return max(self.numbers) - min(self.numbers)

    @property
    def consecutive_count(self) -> int:
        """连号对数"""
        count = 0
        sorted_nums = sorted(self.numbers)
        for i in range(len(sorted_nums) - 1):
            if sorted_nums[i + 1] - sorted_nums[i] == 1:
                count += 1
        return count


class DataLoader:
    """数据加载器 — 只读共享 data/ 层"""

    def __init__(self):
        self._history: List[KL8Draw] = []
        self._daily_points: Dict[str, List[int]] = {}
        self._loaded = False

    def load(self) -> None:
        """加载所有数据"""
        self._load_history()
        self._load_daily_points()
        self._loaded = True

    def _load_history(self) -> None:
        """加载开奖历史

        数据格式: date:YYYY-MM-DD,period:XXXXXXX,numbers:XX-XX-...-XX
        """
        if not KL8_HISTORY_FILE.exists():
            raise FileNotFoundError(f"开奖历史文件不存在: {KL8_HISTORY_FILE}")

        self._history = []
        with open(KL8_HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.split(",")
                    date_str = parts[0].split(":", 1)[1]
                    period_str = parts[1].split(":", 1)[1]
                    numbers_str = parts[2].split(":", 1)[1]
                    numbers = sorted([int(x) for x in numbers_str.split("-")])
                    # 数据校验：KL8每期20个号码，范围1-80
                    if len(numbers) != 20 or not all(1 <= n <= 80 for n in numbers):
                        continue  # 跳过异常行
                    self._history.append(KL8Draw(date_str, period_str, numbers))
                except (IndexError, ValueError) as e:
                    # 格式异常行静默跳过
                    continue

        # 按期号降序排列（最新在最前）
        self._history.sort(key=lambda d: d.period, reverse=True)

    def _load_daily_points(self) -> None:
        """每日点位加载 (KillSeeker不需要点位数据, 跳过)"""
        pass

    @property
    def history(self) -> List[KL8Draw]:
        if not self._loaded:
            self.load()
        return self._history

    @property
    def latest_period(self) -> Optional[str]:
        if self._history:
            return self._history[0].period
        return None

    @property
    def total_periods(self) -> int:
        return len(self._history)

    def get_daily_points(self, period: str) -> Optional[List[int]]:
        return self._daily_points.get(period)

    def get_history_up_to(self, period: str) -> List[KL8Draw]:
        """获取 ≤period 的所有历史数据（严禁未来函数）

        注意：self.history 已按期号降序排列（最新最前），
        因此 "≤period" 的数据在列表后半部分。
        """
        result = []
        for draw in self.history:
            if draw.period <= period:
                result.append(draw)
        return result

    def truncate_as_of(self, period: str) -> int:
        """就地截断历史到 ≤period（补跑/回放用，严禁未来函数）。

        Returns:
            截断后保留的期数。
        """
        if not self._loaded:
            self.load()
        before = len(self._history)
        self._history = [d for d in self._history if d.period <= period]
        if not self._history:
            raise ValueError(f"as-of={period} 截断后无历史数据 (原{before}期)")
        return len(self._history)
