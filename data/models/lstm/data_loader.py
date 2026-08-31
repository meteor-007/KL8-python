# -*- coding: utf-8 -*-
"""
双层LSTM 历史数据加载模块
=======================
统一读取主系统 kl8_history_final.txt，返回按时间升序(旧→新)排列的数据列表。
"""
import os
import re
from typing import List, Optional
from . import config


class KL8Draw:
    __slots__ = ("date", "period", "numbers", "set")

    def __init__(self, date: str, period: str, numbers: List[int]):
        self.date = date
        self.period = str(period).strip()
        self.numbers = sorted(numbers)
        self.set = set(numbers)

    def __repr__(self):
        return f"<KL8Draw {self.period} ({self.date}): {len(self.numbers)} balls>"


LINE_RE = re.compile(r"date:(\d{4}-\d{2}-\d{2}),period:(\d+),numbers:([0-9\-]+)")


def load_history(path: Optional[str] = None) -> List[KL8Draw]:
    """
    返回按时间升序(旧→新)的 KL8Draw 列表。
    主系统文件中通常是最新在前，这里统一排序为旧→新，供时序滑动窗口使用。
    """
    path = path or config.HISTORY_FILE
    if not os.path.exists(path):
        # 尝试使用主系统统一路径
        try:
            from utils.paths import data_path
            path = data_path("kl8_history_final.txt")
        except Exception:
            pass

    draws: List[KL8Draw] = []
    if not os.path.exists(path):
        return draws

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            m = LINE_RE.search(line_str)
            if m:
                nums = [int(x) for x in m.group(3).split("-") if x.isdigit()]
                if len(nums) == 20:
                    draws.append(KL8Draw(m.group(1), m.group(2), nums))
                continue

            # 兼容其他文本格式
            parts = line_str.split()
            if len(parts) >= 21:
                period = parts[0]
                nums = [int(x) for x in parts[1:21] if x.isdigit()]
                if len(nums) == 20:
                    draws.append(KL8Draw("未知日期", period, nums))

    # 按期号升序（旧 -> 新），便于滑动窗口无未来泄露切片
    draws.sort(key=lambda d: int(d.period))
    return draws


def get_latest(draws: List[KL8Draw]) -> Optional[KL8Draw]:
    """获取最新的一期开奖"""
    return draws[-1] if draws else None
