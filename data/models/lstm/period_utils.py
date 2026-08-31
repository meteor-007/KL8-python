# -*- coding: utf-8 -*-
"""
快乐8 期号处理工具函数
=====================
格式: YYYYNNN (例如 2026224: 2026年第224期)
"""
from typing import Tuple


def parse_period(period: str) -> Tuple[int, int]:
    """'2026223' -> (2026, 223)"""
    s = str(period).strip()
    if len(s) < 5:
        return 2026, int(s) if s.isdigit() else 0
    return int(s[:4]), int(s[4:])


def next_period(period: str) -> str:
    """计算下一个目标期号"""
    year, seq = parse_period(period)
    return f"{year}{str(seq + 1).zfill(3)}"


def diff_period(a: str, b: str) -> int:
    """同一年内的期号差"""
    return parse_period(a)[1] - parse_period(b)[1]
