# -*- coding: utf-8 -*-
"""
统一历史数据加载器
==================
消除各模块中重复定义的 load_history / load_hist 函数。
所有模块应引用此模块, 而非自行实现数据加载。

用法:
    from utils.history_loader import load_history
    history = load_history()          # 默认路径, 按期号降序(最新在前)
    history = load_history(limit=100) # 限制返回期数
"""
import os
import re
from typing import List, Dict, Optional


def _get_history_file() -> str:
    """获取历史数据文件路径"""
    try:
        from utils.paths import data_path
        return data_path('kl8_history_final.txt')
    except Exception:
        _PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(_PROJ, 'kl8_history_final.txt')


def load_history(history_file: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
    """加载开奖历史数据，按期号降序排列（最新在前）

    Args:
        history_file: 可选的文件路径，默认使用 utils.paths 定位
        limit: 可选的返回期数限制

    Returns:
        list[dict]: 每个元素 {'issue': str, 'numbers': list[int], 'date': str(可选)}
    """
    if history_file is None:
        history_file = _get_history_file()

    if not os.path.exists(history_file):
        return []

    history: List[Dict] = []
    with open(history_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # 标准格式: date:...,period:NNN,numbers:N1-N2...
            m = re.search(r'period:(\d+),numbers:([\d-]+)', line)
            if m:
                issue = m.group(1)
                num_str = m.group(2)
                numbers = sorted(int(x) for x in num_str.split('-') if x.isdigit())
                if len(numbers) >= 15:
                    # 尝试提取日期
                    date_m = re.search(r'date:(\S+)', line)
                    entry = {'issue': issue, 'numbers': numbers}
                    # 原始出球顺序 (供 deep_optimizer 序列熵使用; numbers 已被升序排序)
                    entry['draw_order'] = [int(x) for x in num_str.split('-') if x.isdigit()]
                    if date_m:
                        entry['date'] = date_m.group(1)
                    history.append(entry)
                continue

            # 兼容旧版空格分割格式
            parts = line.split()
            if len(parts) >= 2:
                issue = parts[0]
                try:
                    raw_nums = [int(x) for x in parts[1:] if x.isdigit()]
                    numbers = sorted(raw_nums)
                    if len(numbers) >= 15:
                        entry = {'issue': issue, 'numbers': numbers}
                        entry['draw_order'] = raw_nums
                        history.append(entry)
                except ValueError:
                    pass

    # 按期号降序排列
    history.sort(key=lambda h: h['issue'], reverse=True)

    if limit and len(history) > limit:
        history = history[:limit]

    return history
