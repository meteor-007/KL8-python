# 顺口溜/eval_ool.py
# -*- coding: utf-8 -*-
"""顺口溜规则 OOF 评估：验证「史%」是否在样本外仍成立。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parse_numbers(lines):
    sets = []
    for ln in lines:
        m = re.search(r"numbers:([\d\-]+)", ln)
        if m:
            sets.append(set(int(x) for x in m.group(1).split("-")))
    return sets


def at_least_one_baseline(k):
    """随机选 k 个号至少一中基线（不放回超几何精确值）= 1 - C(60,k)/C(80,k)。"""
    from math import comb
    return 1.0 - comb(80 - 20, k) / comb(80, k)


def hit_rate_for_rule(rule_outputs, actuals):
    """rule_outputs: [ [号码...], ... ] 每期规则预测集合；actuals: [set] 每期开奖。
    按「至少一中」计命中。返回 (命中数, 期数, 命中率)。"""
    hits = 0
    n = 0
    for out, act in zip(rule_outputs, actuals):
        if not out:
            continue
        n += 1
        if any(x in act for x in out):
            hits += 1
    return hits, n, (hits / n if n else 0.0)