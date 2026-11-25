#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TPRD v4.0 数据同步与加载模块 (Data Sync Engine)
支持多分隔符兼容、UTF-8-SIG 账本读取、幂等去重与增量开奖补齐
"""

import os
import re
from typing import List, Dict, Tuple, Optional
import numpy as np


def sync_latest_draws(filepath: str = "data/kl8_history_final.txt", extra_records: Optional[List[str]] = None) -> int:
    """
    按期号去重并严格按期号倒序重排，自动补齐增量数据
    """
    patch_records = [
        "date:2026-10-23,period:2026282,numbers:02-08-09-13-14-23-24-32-35-36-40-41-43-44-59-61-68-73-78-80",
        "date:2026-10-24,period:2026283,numbers:01-03-07-15-16-25-28-34-41-43-44-60-61-67-70-71-72-74-75-80",
        "date:2026-10-25,period:2026284,numbers:05-06-07-09-11-16-18-22-29-34-36-39-41-50-52-53-58-62-69-78",
        "date:2026-10-26,period:2026285,numbers:03-09-10-12-14-18-25-27-29-31-37-41-44-47-54-56-61-63-74-78",
        "date:2026-10-27,period:2026286,numbers:01-03-05-09-17-22-27-30-37-47-51-52-55-56-58-68-69-72-75-80",
        "date:2026-10-28,period:2026287,numbers:02-09-16-19-24-25-50-55-56-58-64-66-67-68-70-73-75-76-77-79",
        "date:2026-10-29,period:2026288,numbers:05-10-14-19-22-23-26-27-28-39-40-47-50-53-59-61-66-73-75-79",
        "date:2026-10-30,period:2026289,numbers:02-04-05-06-07-11-16-17-18-33-34-36-47-56-58-62-68-73-76-78",
        "date:2026-10-31,period:2026290,numbers:03-04-12-19-24-25-27-28-31-32-33-40-43-49-51-52-63-69-71-72",
        "date:2026-11-01,period:2026291,numbers:03-13-16-21-24-26-29-34-40-42-50-54-58-59-60-61-64-66-67-78",
        "date:2026-11-02,period:2026292,numbers:02-05-10-17-22-25-26-36-43-45-50-51-52-57-62-64-68-70-71-75",
        "date:2026-11-03,period:2026293,numbers:19-23-25-34-39-42-43-44-45-48-53-54-56-57-62-73-74-75-77-78",
        "date:2026-11-04,period:2026294,numbers:03-07-10-16-21-25-29-33-35-43-45-52-58-60-64-68-69-72-76-80",
        "date:2026-11-05,period:2026295,numbers:05-06-07-11-12-16-18-21-24-32-33-36-38-44-47-56-57-61-75-77",
        "date:2026-11-06,period:2026296,numbers:01-02-04-07-13-15-19-30-34-42-44-45-48-50-54-63-67-71-73-74",
        "date:2026-11-07,period:2026297,numbers:02-11-17-48-72-66-25-43-45-50-13-36-79-58-05-76-23-49-41-42",
        "date:2026-11-08,period:2026298,numbers:02-05-08-12-16-20-25-27-28-29-31-35-36-42-43-49-57-58-72-75",
        "date:2026-11-09,period:2026299,numbers:01-07-10-13-23-25-26-28-45-46-47-49-61-63-64-72-73-77-78-79",
        "date:2026-11-10,period:2026300,numbers:08-12-17-23-28-30-31-33-35-39-43-45-47-51-52-58-63-66-69-75",
        "date:2026-11-11,period:2026301,numbers:08-13-14-17-22-23-33-34-35-36-47-49-51-54-60-63-68-69-75-79",
        "date:2026-11-12,period:2026302,numbers:03-11-16-26-27-29-35-37-44-47-48-52-53-56-58-61-67-69-70-75",
        "date:2026-11-13,period:2026303,numbers:01-02-05-14-18-28-38-48-50-53-58-59-61-67-68-69-73-75-79-80",
    ]
    if extra_records:
        patch_records.extend(extra_records)

    record_map = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = re.search(r'period:(\d+)', line)
                if m:
                    record_map[int(m.group(1))] = line

    for rec in patch_records:
        m = re.search(r'period:(\d+)', rec)
        if m:
            record_map[int(m.group(1))] = rec

    sorted_lines = [record_map[p] for p in sorted(record_map.keys(), reverse=True)]
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for line in sorted_lines:
            f.write(line + "\n")
    return len(sorted_lines)


def load_history(filepath: str = "data/kl8_history_final.txt") -> Tuple[List[Dict], np.ndarray]:
    """
    加载全量账本并按时间正序排列（最旧到最新），构造时序二值张量 B
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"账本文件未找到: {filepath}")

    with open(filepath, "r", encoding="utf-8-sig") as f:
        lines = [line.strip() for line in f if line.strip()]

    draws = []
    # 原始文件按期号倒序（第0行为最新），因此反转为时间正序
    for line in reversed(lines):
        try:
            parts = line.split(',')
            date = parts[0].split(':')[1].strip()
            period = parts[1].split(':')[1].strip()
            raw_nums = parts[2].split(':')[1].strip()
            nums = sorted([int(x) for x in re.split(r'[-\s]+', raw_nums) if x])
            if len(nums) == 20 and all(1 <= n <= 80 for n in nums):
                draws.append({'date': date, 'period': period, 'nums': nums, 'set': set(nums)})
        except Exception:
            continue

    N = len(draws)
    B = np.zeros((N + 1, 81), dtype=np.int32)
    for t, d in enumerate(draws):
        for n in d['nums']:
            B[t, n] = 1
    return draws, B


def parse_and_append_draw(filepath: str, period: int, date: str, raw_numbers: str) -> bool:
    """
    解析用户手动输入的一期开奖号码并同步追加到账本
    支持空格、逗号或连字符分隔
    """
    nums = sorted([int(x) for x in re.split(r'[-\s,]+', raw_numbers.strip()) if x])
    if len(nums) != 20:
        raise ValueError(f"开奖号码必须为20个号码，当前解析出 {len(nums)} 个: {nums}")
    if any(n < 1 or n > 80 for n in nums):
        raise ValueError("号码必须在 1~80 范围内")
    if len(set(nums)) != 20:
        raise ValueError("存在重复号码，必须为20个不重复号码")

    nums_str = "-".join(f"{n:02d}" for n in nums)
    new_line = f"date:{date},period:{period},numbers:{nums_str}"
    sync_latest_draws(filepath, extra_records=[new_line])
    return True
