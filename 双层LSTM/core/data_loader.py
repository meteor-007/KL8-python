# -*- coding: utf-8 -*-
"""历史数据加载(只读)"""
import os, re
import config


class KL8Draw:
    __slots__ = ("date", "period", "numbers", "set")

    def __init__(self, date, period, numbers):
        self.date = date
        self.period = period
        self.numbers = sorted(numbers)
        self.set = set(numbers)


LINE_RE = re.compile(r"date:(\d{4}-\d{2}-\d{2}),period:(\d+),numbers:([0-9\-]+)")


def load_history(path=None):
    """返回按时间升序(旧→新)的 KL8Draw 列表。文件里是最新在前,这里反转。"""
    path = path or config.HISTORY_FILE
    draws = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = LINE_RE.search(line.strip())
            if not m:
                continue
            nums = [int(x) for x in m.group(3).split("-") if x.isdigit()]
            if len(nums) != 20:
                continue
            draws.append(KL8Draw(m.group(1), m.group(2), nums))
    draws.sort(key=lambda d: int(d.period))  # 旧→新
    return draws


def get_latest(draws):
    return draws[-1] if draws else None