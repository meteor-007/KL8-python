# -*- coding: utf-8 -*-
"""期号工具:快乐8期号=年份头4位+年内序号(跨年不连续)。"""


def parse_period(period):
    """'2026223' -> (2026, 223)"""
    s = str(period)
    return int(s[:4]), int(s[4:])


def next_period(period):
    year, seq = parse_period(period)
    return str(year) + str(seq + 1).zfill(3)


def period_day(period):
    """按历史文件 date 反查某期日期;若无则返回 ''。"""
    return ""


def diff_period(a, b):
    """期号差(同年内)。"""
    return parse_period(a)[1] - parse_period(b)[1]