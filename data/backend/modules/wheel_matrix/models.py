# -*- coding: utf-8 -*-
"""
领域模型定义 (Domain Models)
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum
import datetime

class GameType(str, Enum):
    KENO = "KENO"          # 基诺/快乐8 (80选20, 目标选2/选5)
    PICK_6 = "PICK_6"      # 选6型 (双色球红球, 6/49)
    PICK_5 = "PICK_5"      # 选5型 (大乐透前区, 5/35)
    PICK_7 = "PICK_7"      # 选7型 (七乐彩)

@dataclass(frozen=True)
class LotteryGameSpec:
    game_id: str
    name: str
    game_type: GameType
    main_pool: int         # 主区球总数 (如 80, 33, 35)
    main_pick: int         # 每期开奖出号数 (如 20, 6, 5)
    target_pick: int = 2   # 目标投注选号数 (如 选2, 选5)
    extra_pool: int = 0
    extra_pick: int = 0
    
    @property
    def expected_sum(self) -> float:
        return (self.main_pick * (1 + self.main_pool)) / 2.0

    @property
    def default_golden_sum_range(self) -> Tuple[int, int]:
        mid = int(self.expected_sum)
        span = int(self.main_pick * (self.main_pool / 8.0))
        return (mid - span, mid + span)

PRESET_GAMES: Dict[str, LotteryGameSpec] = {
    "kl8": LotteryGameSpec("kl8", "快乐8 (KL8 极简选2)", GameType.KENO, main_pool=80, main_pick=20, target_pick=2),
    "ssq": LotteryGameSpec("ssq", "双色球 (SSQ)", GameType.PICK_6, main_pool=33, main_pick=6, target_pick=6, extra_pool=16, extra_pick=1),
    "dlt": LotteryGameSpec("dlt", "超级大乐透 (DLT)", GameType.PICK_5, main_pool=35, main_pick=5, target_pick=5, extra_pool=12, extra_pick=2),
    "lotto649": LotteryGameSpec("lotto649", "经典 6/49 (Lotto 6/49)", GameType.PICK_6, main_pool=49, main_pick=6, target_pick=6),
}

@dataclass
class DrawRecord:
    draw_id: str
    draw_date: str
    main_balls: List[int]
    extra_balls: List[int] = field(default_factory=list)

    def __post_init__(self):
        self.main_balls = sorted(self.main_balls)
        self.extra_balls = sorted(self.extra_balls)

@dataclass
class FilterConfig:
    sum_range: Optional[Tuple[int, int]] = None
    allowed_odd_counts: Optional[Tuple[int, ...]] = None
    allowed_high_counts: Optional[Tuple[int, ...]] = None
    max_consecutive: int = 3
    max_same_tail: int = 3
    exclude_all_even_odd: bool = True
    exclude_arithmetic_progression: bool = True
    exclude_history_jackpot: bool = True

@dataclass
class WheelTemplate:
    template_id: str
    name: str
    game_type: GameType
    pool_size: int
    pick_count: int
    line_count: int
    guarantee: str
    matrix: List[List[int]]
