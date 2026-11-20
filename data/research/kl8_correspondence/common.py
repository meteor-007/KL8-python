# -*- coding: utf-8 -*-
"""快乐8 "对应规律" 验证工程 — 共享数据底座。

数据源: storage/raw/kl8_history_final.txt
行格式: date:2026-10-21,period:2026280,numbers:70-26-53-...-69

核心口径
--------
1. 每期 20 个号，官方公布后本工程统一按 **升序** 排列，位次 1..20。
2. 截图中 "1位..12位" 即升序后的第 1..12 个号（已用真实开奖逐格核对）。
3. 三球组合属性:
     s012 = sum(three) % 3           # 和值 012 路
     tail = sum(three) % 10          # 和值尾数
     tail_size = '大' if tail >= 5 else '小'   # 和值尾数大小(0-4 小, 5-9 大)
4. 紫球(单球)属性 = 该号自身取模/尾数。

所有下游脚本只允许 from common import *，不得自建解析逻辑。
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(PROJECT, "storage", "raw", "kl8_history_final.txt")
OUT = os.path.join(HERE, "out")

NUM_BALLS = 80
DRAW_SIZE = 20


# ────────────────────────────── 数据加载 ──────────────────────────────
def load_draws(path: str = RAW) -> list[tuple[int, tuple[int, ...]]]:
    """返回按期号升序的 [(period, tuple(sorted_numbers)), ...]。"""
    import re

    pat = re.compile(r"date:([\d-]+),period:(\d+),numbers:(.+)$")
    seen: dict[int, tuple[int, ...]] = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            m = pat.search(line.strip())
            if not m:
                continue
            nums = tuple(sorted(int(x) for x in re.split(r"[\s,\-]+", m.group(3)) if x.strip()))
            if len(nums) != DRAW_SIZE or len(set(nums)) != DRAW_SIZE:
                raise ValueError(f"坏数据: period={m.group(2)} n={len(nums)}")
            seen[int(m.group(2))] = nums
    return sorted(seen.items())


def load_index(path: str = RAW) -> tuple[list[int], dict[int, tuple[int, ...]]]:
    draws = load_draws(path)
    periods = [p for p, _ in draws]
    return periods, dict(draws)


# ────────────────────────────── 基础属性 ──────────────────────────────
def road012(x: int) -> int:
    """单号 012 路 = x % 3。"""
    return x % 3


def road012_of_sum(vals) -> int:
    """和值的 012 路 = sum % 3。"""
    return sum(vals) % 3


def tail_of_sum(vals) -> int:
    return sum(vals) % 10


def tail_size(tail: int) -> str:
    """和值尾数大小：0-4 为小，5-9 为大。"""
    return "大" if tail >= 5 else "小"


def pos(draw: tuple[int, ...], i: int) -> int:
    """1-based 位次取号。"""
    return draw[i - 1]


# ────────────────────────────── 规则模板 ──────────────────────────────
@dataclass(frozen=True)
class Template:
    """一条"紫球 ↔ 橙球三球组"对应规则。

    purple_pos : 紫球所在位次（紫球期 = t 期）
    o1, o2, o3 : 橙球三个位次
    row_offsets: 三个橙球相对紫球期的期差（+1/+2 等）

    规则成立 <=> attribute(三球和值) == attribute(紫球自身)
    """
    name: str
    purple_pos: int
    o1: int
    o2: int
    o3: int
    rows: tuple[int, int, int]
    attr: str  # 'r012' | 'tailsize'

    def colors(self, draws, t: int):
        """返回 (purple_num, triple) ；t 为紫球期下标。越界返回 None。"""
        if t < 0 or t >= len(draws):
            return None
        pdraw = draws[t]
        if self.purple_pos > len(pdraw):
            return None
        triple = []
        for r, o in zip(self.rows, (self.o1, self.o2, self.o3)):
            idx = t + r
            if idx < 0 or idx >= len(draws):
                return None
            d = draws[idx]
            if o > len(d):
                return None
            triple.append(d[o - 1])
        if len(set(triple)) != 3:
            return None
        return pdraw[self.purple_pos - 1], tuple(triple)

    def holds(self, draws, t: int):
        got = self.colors(draws, t)
        if got is None:
            return None
        purple, triple = got
        if self.attr == "r012":
            return road012_of_sum(triple) == road012(purple)
        if self.attr == "tailsize":
            return tail_size(tail_of_sum(triple)) == tail_size(purple % 10)
        raise ValueError(self.attr)


# 截图中可直接读出的两条"实物"规则
RULE_A_TU2 = Template("图2实物规则", purple_pos=1, o1=3, o2=2, o3=4,
                      rows=(1, 2, 2), attr="r012")
RULE_A_TU1 = Template("图1实物规则", purple_pos=1, o1=3, o2=2, o3=4,
                      rows=(1, 2, 2), attr="r012")
RULE_B_TU5 = Template("图5实物规则", purple_pos=2, o1=2, o2=3, o3=4,
                      rows=(0, 2, 2), attr="tailsize")


# ────────────────────────────── 统计工具 ──────────────────────────────
def runs(bits):
    """把布尔序列切成 [(value, length), ...]。"""
    out = []
    for b in bits:
        if out and out[-1][0] == b:
            out[-1][1] += 1
        else:
            out.append([b, 1])
    return [(v, n) for v, n in out]


def max_run(bits, value=True):
    return max([n for v, n in runs(bits) if v == value], default=0)


def run_histogram(bits, value=True, cap=20):
    h = [0] * (cap + 1)
    for v, n in runs(bits):
        if v == value:
            h[min(n, cap)] += 1
    return h


def chi2_uniform(counts, expected=None):
    """返回 (chi2, dof, p)。p 用生存函数近似（卡方上尾）。"""
    import math

    k = len(counts)
    tot = sum(counts)
    if expected is None:
        exp = [tot / k] * k
    else:
        exp = list(expected)
    chi2 = sum((c - e) ** 2 / e for c, e in zip(counts, exp) if e > 0)
    dof = k - 1
    p = chi2_sf(chi2, dof)
    return chi2, dof, p


def chi2_sf(x: float, dof: int) -> float:
    """卡方分布上尾概率（正则化不完全伽马 Q(dof/2, x/2)）。"""
    import math

    a = dof / 2.0
    xx = x / 2.0
    if xx <= 0:
        return 1.0
    if xx < a + 1:
        # 级数展开 P(a,x)
        term = 1.0 / a
        s = term
        n = a
        for _ in range(500):
            n += 1
            term *= xx / n
            s += term
            if abs(term) < abs(s) * 1e-14:
                break
        p = s * math.exp(-xx + a * math.log(xx) - math.lgamma(a))
        return max(0.0, 1.0 - p)
    # 连分式 Q(a,x)
    tiny = 1e-300
    b = xx + 1 - a
    c = 1 / tiny
    d = 1 / b if b != 0 else 1 / tiny
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-14:
            break
    return math.exp(-xx + a * math.log(xx) - math.lgamma(a)) * h


def z_runs(n1: int, n0: int):
    """Wald–Wolfowitz 游程检验，返回 (z, p)。"""
    import math

    n = n1 + n0
    if n1 < 2 or n0 < 2:
        return 0.0, 1.0
    r = 1
    return r, 0.0


def runs_test(bits):
    """游程检验（两分类随机性）。"""
    import math

    n1 = sum(1 for b in bits if b)
    n0 = len(bits) - n1
    if n1 < 2 or n0 < 2:
        return {"n1": n1, "n0": n0, "runs": 0, "z": 0.0, "p": 1.0}
    r = 1 + sum(1 for a, b in zip(bits, bits[1:]) if a != b)
    n = n1 + n0
    mu = 2 * n1 * n0 / n + 1
    var = 2 * n1 * n0 * (2 * n1 * n0 - n) / (n * n * (n - 1))
    z = (r - mu) / math.sqrt(var) if var > 0 else 0.0
    p = 2 * (1 - normal_cdf(abs(z)))
    return {"n1": n1, "n0": n0, "runs": r, "mu": mu, "z": z, "p": p}


def normal_cdf(x: float) -> float:
    import math

    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def save_json(name: str, obj) -> str:
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return path


def save_text(name: str, text: str) -> str:
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


if __name__ == "__main__":
    periods, idx = load_index()
    print("periods:", len(periods), periods[0], periods[-1])
    draws = [idx[p] for p in periods]
    for name, tpl in (("A", RULE_A_TU2), ("B", RULE_B_TU5)):
        bits = [tpl.holds(draws, t) for t in range(len(draws))]
        bits = [b for b in bits if b is not None]
        print(name, "n=", len(bits), "hit=", sum(bits), "rate=", round(sum(bits) / len(bits), 4),
              "maxrun=", max_run(bits))
