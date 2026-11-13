# -*- coding: utf-8 -*-
"""16 期窗口维度交叉研究 + 约束优化选号

研究问题（对应「新增模块」思路的深化）：
1. 出现次数 × 剩余次数：16 期窗口内每个号码的出现次数(freq_16) 与
   剩余次数(遗漏 omission) 的二维交叉分布，定位"高频短漏 / 高频长漏 /
   低频短漏 / 低频长漏"四类结构性机会。
2. 维度画像：各频次桶内号码的 尾数(0-9) / 012路(0,1,2) / 质合 分布，
   对照理论基线找出「聚集」与「空缺」。
3. 最优选号：在中热动量池(频3~6)内，以 尾数覆盖≥8、012路 6:7:7±1、
   质合比≈5:15 为硬约束，用带惩罚的爬山法求动量最优 20 码。
4. 回测仲裁：walk-forward 对比「纯动量 Top20」vs「动量+维度约束 Top20」
   的样本外命中率，用数据决定哪条轨更优。

设计原则：
- 轻量：不依赖重量级 analyze_at_index，仅计算本研究所需字段，回测可快跑。
- 可解释：每个结论都带号码清单与数字证据，不做黑盒。
"""
from __future__ import annotations

import json
import math
import os
import random
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.utils.paths import get_cache_dir
from backend.modules.sixteen.sixteen_engine import (
    WINDOW_SIZE,
    NUM_TOTAL,
    MIDHOT_SCORE_DECIMALS,
    midhot_score_for_ball,
    _window_gap_stats,
)

# 回补打分权重（与 sixteen_engine.analyze_at_index 完全一致）
W_SWEET, W_CUR, W_MX, W_AV, W_FREQ, W_R8 = 0.38, 0.05, 0.15, 0.10, 0.20, 0.12
SWEET_CENTER, SWEET_SIGMA = 10.0, 4.2


def _znorm(vals: List[float]) -> List[float]:
    if not vals:
        return []
    mu = sum(vals) / len(vals)
    sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1e-9
    return [(v - mu) / sd for v in vals]


def compute_rebound_scores(profiles: List[Dict[str, Any]]) -> None:
    """原地写入 rebound_score（复刻现有回补轨口径，用于跨轨仲裁）。"""
    sweet_l, cur_l, mx_l, av_l, freq_l, r8_l = [], [], [], [], [], []
    for p in profiles:
        om = p["omission"]
        sv = math.exp(-((om - SWEET_CENTER) ** 2) / (2 * SWEET_SIGMA ** 2))
        if om >= 16:
            sv *= 0.6
        sweet_l.append(sv)
        cur_l.append(p["omission"])
        mx_l.append(p["max_omission"])
        av_l.append(p["avg_omission"])
        freq_l.append(p["freq_16"])
        r8_l.append(p["recent_8_hits"])
    sw = _znorm(sweet_l); cz = _znorm(cur_l); mz = _znorm(mx_l)
    az = _znorm(av_l); fz = _znorm(freq_l); rz = _znorm(r8_l)
    for i, p in enumerate(profiles):
        p["rebound_score"] = round(
            W_SWEET * sw[i] + W_CUR * cz[i] + W_MX * mz[i]
            + W_AV * az[i] + W_FREQ * fz[i] + W_R8 * rz[i],
            MIDHOT_SCORE_DECIMALS,
        )

# ───────────────────────────── 基础维度 ─────────────────────────────

# 1~80 的质数表（1 既不是质数也不是合数）
PRIMES_1_80 = {
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
    53, 59, 61, 67, 71, 73, 79,
}
PRIME_COUNT = len(PRIMES_1_80)          # 22
COMPOSITE_COUNT = NUM_TOTAL - PRIME_COUNT - 1  # 57（排除 1）

# 理论基线（80 码总体）
THEORY_TAIL_COUNT = 8                   # 每个尾数 8 个（1-80 完全均匀）
THEORY_ROAD_COUNT = {"0": 26, "1": 27, "2": 27}
THEORY_PRIME_RATIO = PRIME_COUNT / NUM_TOTAL      # 0.275
THEORY_COMPOSITE_RATIO = COMPOSITE_COUNT / NUM_TOTAL  # 0.7125

# 遗漏分桶（剩余次数）
OMISSION_BUCKETS: List[Tuple[str, int, int]] = [
    ("0", 0, 0),
    ("1", 1, 1),
    ("2", 2, 2),
    ("3-4", 3, 4),
    ("5-7", 5, 7),
    ("8-11", 8, 11),
    ("12-15", 12, 15),
    ("16+", 16, 10 ** 6),
]

FREQ_ROWS: List[str] = ["0", "1", "2", "3", "4", "5", "6", "7", "8+"]


def tail_class(num: int) -> int:
    """尾数 0-9"""
    return num % 10


def road_class(num: int) -> int:
    """012 路：num % 3 → 0/1/2"""
    return num % 3


def prime_class(num: int) -> str:
    """质 / 合 / 中性(1)"""
    if num == 1:
        return "neutral"
    return "prime" if num in PRIMES_1_80 else "composite"


def omission_bucket(omission: int) -> str:
    for label, lo, hi in OMISSION_BUCKETS:
        if lo <= omission <= hi:
            return label
    return "16+"


def freq_bucket(freq: int) -> str:
    return "8+" if freq >= 8 else str(freq)


# ───────────────────────────── 画像计算 ─────────────────────────────

def compute_ball_profiles(draws: List[Dict[str, Any]], target_idx: int) -> List[Dict[str, Any]]:
    """轻量计算 target_idx 作为窗口末期时，80 码的研究画像。

    与 analyze_at_index 的窗口口径完全一致：
      window = draws[target_idx-15 : target_idx+1]
      target_period = draws[target_idx].period + 1
    """
    if target_idx < WINDOW_SIZE - 1:
        raise ValueError(f"至少需要 {WINDOW_SIZE} 期历史数据")

    window_draws = draws[target_idx - WINDOW_SIZE + 1: target_idx + 1]
    outgoing_draw = window_draws[0]
    outgoing_nums = set(outgoing_draw["nums"])

    freq_16: Counter = Counter()
    freq_8: Counter = Counter()
    for d in window_draws:
        freq_16.update(d["nums"])
    for d in window_draws[-8:]:
        freq_8.update(d["nums"])

    omissions: Dict[int, int] = {}
    for num in range(1, NUM_TOTAL + 1):
        om = 0
        found = False
        for d in reversed(draws[: target_idx + 1]):
            if num in d["nums"]:
                found = True
                break
            om += 1
        omissions[num] = om if found else 99

    profiles: List[Dict[str, Any]] = []
    for num in range(1, NUM_TOTAL + 1):
        f16 = int(freq_16.get(num, 0))
        is_out = num in outgoing_nums
        max_om, avg_om, max_stk = _window_gap_stats(num, window_draws)
        ball = {
            "number": num,
            "display": f"{num:02d}",
            "freq_16": f16,
            "window_remaining": WINDOW_SIZE - f16,   # 窗口内剩余次数（未出现期数）
            "omission": int(omissions[num]),          # 剩余次数（遗漏期数）
            "omission_bucket": omission_bucket(int(omissions[num])),
            "recent_8_hits": int(freq_8.get(num, 0)),
            "is_outgoing": bool(is_out),
            "zone": (num - 1) // 10 + 1,
            "tail": tail_class(num),
            "road012": road_class(num),
            "prime_class": prime_class(num),
            "max_omission": int(max_om),
            "avg_omission": float(avg_om),
            "max_streak": int(max_stk),
        }
        ball["midhot_score"] = round(midhot_score_for_ball(ball), MIDHOT_SCORE_DECIMALS)
        profiles.append(ball)
    compute_rebound_scores(profiles)
    return profiles


# ───────────────────────────── 交叉矩阵 ─────────────────────────────

def build_cross_matrix(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """出现次数 × 剩余次数(遗漏) 二维交叉矩阵。

    行 = 16 期出现次数(0~8+)，列 = 剩余次数(遗漏分桶)。
    每格给出号码数、号码清单与格内平均动量分，用于定位结构性机会。
    """
    matrix: Dict[str, Dict[str, Any]] = {
        row: {col: {"count": 0, "nums": [], "avg_midhot": 0.0} for col, _, _ in OMISSION_BUCKETS}
        for row in FREQ_ROWS
    }
    for p in profiles:
        row = freq_bucket(p["freq_16"])
        col = p["omission_bucket"]
        cell = matrix[row][col]
        cell["count"] += 1
        cell["nums"].append(p["number"])
        cell["avg_midhot"] += float(p.get("midhot_score") or 0.0)

    for row in FREQ_ROWS:
        for col, _, _ in OMISSION_BUCKETS:
            cell = matrix[row][col]
            cell["nums"] = sorted(cell["nums"])
            cell["avg_midhot"] = round(cell["avg_midhot"] / cell["count"], 4) if cell["count"] else 0.0

    # 结构性机会解读：四类象限
    def _nums_in(rows: List[str], cols: List[str]) -> List[int]:
        out = []
        for r in rows:
            for c in cols:
                out.extend(matrix[r][c]["nums"])
        return sorted(set(out))

    quadrants = {
        "hot_short_omission": {
            "label": "高频短漏",
            "desc": "出现≥4次且遗漏≤2期：动量正盛，追热首选",
            "rows": ["4", "5", "6", "7", "8+"],
            "cols": ["0", "1", "2"],
            "nums": _nums_in(["4", "5", "6", "7", "8+"], ["0", "1", "2"]),
        },
        "hot_long_omission": {
            "label": "高频长漏",
            "desc": "出现≥4次但遗漏≥5期：动量中断，等回补确认",
            "rows": ["4", "5", "6", "7", "8+"],
            "cols": ["5-7", "8-11", "12-15", "16+"],
            "nums": _nums_in(["4", "5", "6", "7", "8+"], ["5-7", "8-11", "12-15", "16+"]),
        },
        "cold_short_omission": {
            "label": "低频短漏",
            "desc": "出现≤2次但遗漏≤2期：刚开过的冷号，观察能否转温",
            "rows": ["0", "1", "2"],
            "cols": ["0", "1", "2"],
            "nums": _nums_in(["0", "1", "2"], ["0", "1", "2"]),
        },
        "cold_long_omission": {
            "label": "低频长漏",
            "desc": "出现≤2次且遗漏≥8期：深度冷区，均值回归备选",
            "rows": ["0", "1", "2"],
            "cols": ["8-11", "12-15", "16+"],
            "nums": _nums_in(["0", "1", "2"], ["8-11", "12-15", "16+"]),
        },
    }
    for q in quadrants.values():
        q["count"] = len(q["nums"])

    return {
        "rows": FREQ_ROWS,
        "cols": [c for c, _, _ in OMISSION_BUCKETS],
        "matrix": matrix,
        "quadrants": quadrants,
        "note": "行=16期出现次数；列=剩余次数(遗漏期数)。格内数字为号码个数。",
    }


# ───────────────────────────── 维度画像 ─────────────────────────────

def _deviation_flag(count: int, expected: float) -> str:
    if expected <= 0:
        return "均衡"
    ratio = count / expected
    if ratio >= 1.4:
        return "聚集"
    if ratio <= 0.5:
        return "空缺"
    return "均衡"


def build_dimension_profile(
    profiles: List[Dict[str, Any]],
    pool_name: str = "中热池(频3~6)",
    pool_filter: Optional[callable] = None,
) -> Dict[str, Any]:
    """对指定池做 尾数 / 012路 / 质合 维度画像，对照理论基线标记聚集/空缺。"""
    pool = [p for p in profiles if (pool_filter(p) if pool_filter else True)]
    n = len(pool)
    if n == 0:
        return {"pool_name": pool_name, "pool_size": 0, "tail": [], "road": [], "prime": {}}

    # 尾数
    tail_groups: Dict[int, List[int]] = defaultdict(list)
    for p in pool:
        tail_groups[p["tail"]].append(p["number"])
    tail_expected = n * THEORY_TAIL_COUNT / NUM_TOTAL
    tail_rows = []
    for t in range(10):
        nums = sorted(tail_groups.get(t, []))
        cnt = len(nums)
        tail_rows.append({
            "tail": t,
            "count": cnt,
            "nums": nums,
            "expected": round(tail_expected, 2),
            "ratio": round(cnt / tail_expected, 2) if tail_expected else 0.0,
            "flag": _deviation_flag(cnt, tail_expected),
        })

    # 012 路
    road_groups: Dict[int, List[int]] = defaultdict(list)
    for p in pool:
        road_groups[p["road012"]].append(p["number"])
    road_rows = []
    for r in range(3):
        nums = sorted(road_groups.get(r, []))
        cnt = len(nums)
        exp = n * THEORY_ROAD_COUNT[str(r)] / NUM_TOTAL
        road_rows.append({
            "road": r,
            "count": cnt,
            "nums": nums,
            "expected": round(exp, 2),
            "ratio": round(cnt / exp, 2) if exp else 0.0,
            "flag": _deviation_flag(cnt, exp),
        })

    # 质合
    prime_nums = sorted(p["number"] for p in pool if p["prime_class"] == "prime")
    comp_nums = sorted(p["number"] for p in pool if p["prime_class"] == "composite")
    neutral_nums = sorted(p["number"] for p in pool if p["prime_class"] == "neutral")
    prime_expected = n * THEORY_PRIME_RATIO
    prime_rows = {
        "prime": {
            "count": len(prime_nums), "nums": prime_nums,
            "expected": round(prime_expected, 2),
            "ratio": round(len(prime_nums) / prime_expected, 2) if prime_expected else 0.0,
            "flag": _deviation_flag(len(prime_nums), prime_expected),
        },
        "composite": {
            "count": len(comp_nums), "nums": comp_nums,
            "expected": round(n * THEORY_COMPOSITE_RATIO, 2),
            "flag": _deviation_flag(len(comp_nums), n * THEORY_COMPOSITE_RATIO),
        },
        "neutral": {"count": len(neutral_nums), "nums": neutral_nums},
    }

    # 交叉：频次桶 × 维度（每桶的尾数/012路/质合集中度）
    freq_dim_cross = {}
    for row in FREQ_ROWS:
        sub = [p for p in pool if freq_bucket(p["freq_16"]) == row]
        if not sub:
            continue
        tc = Counter(p["tail"] for p in sub)
        rc = Counter(p["road012"] for p in sub)
        pc = Counter(p["prime_class"] for p in sub)
        freq_dim_cross[row] = {
            "count": len(sub),
            "top_tails": [t for t, _ in tc.most_common(3)],
            "tail_entropy": round(_entropy(list(tc.values())), 3),
            "top_roads": [r for r, _ in rc.most_common(2)],
            "road_counts": {str(k): v for k, v in sorted(rc.items())},
            "prime_count": pc.get("prime", 0),
            "composite_count": pc.get("composite", 0),
        }

    return {
        "pool_name": pool_name,
        "pool_size": n,
        "tail": tail_rows,
        "road": road_rows,
        "prime": prime_rows,
        "freq_dim_cross": freq_dim_cross,
        "theory": {
            "tail_count_per_tail": THEORY_TAIL_COUNT,
            "road_count": THEORY_ROAD_COUNT,
            "prime_ratio": round(THEORY_PRIME_RATIO, 4),
            "composite_ratio": round(THEORY_COMPOSITE_RATIO, 4),
        },
    }


def _entropy(counts: List[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        h -= p * math.log2(p)
    return h


# ───────────────────────────── 约束优化选号 ─────────────────────────────

# 硬约束（基于理论基线与民间引擎实证）
CONSTRAINTS = {
    "min_tail_coverage": 8,          # 尾数覆盖 ≥ 8 个（防聚集）
    "road_min": 6,                   # 012 路每路 ≥ 6
    "road_max": 8,                   # 012 路每路 ≤ 8
    "prime_min": 4,                  # 质数 ≥ 4
    "prime_max": 8,                  # 质数 ≤ 8
    "pick_size": 20,
}
PENALTY_LAMBDA = 200.0


def _constraint_violation(picks: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
    tails = {p["tail"] for p in picks}
    roads = Counter(p["road012"] for p in picks)
    primes = sum(1 for p in picks if p["prime_class"] == "prime")

    v = 0.0
    detail = {
        "tail_coverage": len(tails),
        "tail_violation": max(0, CONSTRAINTS["min_tail_coverage"] - len(tails)),
        "road_counts": {str(r): roads.get(r, 0) for r in range(3)},
        "road_violation": 0,
        "prime_count": primes,
        "prime_violation": 0,
    }
    v += detail["tail_violation"] * 10.0

    road_v = 0
    for r in range(3):
        c = roads.get(r, 0)
        if c < CONSTRAINTS["road_min"]:
            road_v += CONSTRAINTS["road_min"] - c
        elif c > CONSTRAINTS["road_max"]:
            road_v += c - CONSTRAINTS["road_max"]
    detail["road_violation"] = road_v
    v += road_v * 3.0

    if primes < CONSTRAINTS["prime_min"]:
        pv = CONSTRAINTS["prime_min"] - primes
    elif primes > CONSTRAINTS["prime_max"]:
        pv = primes - CONSTRAINTS["prime_max"]
    else:
        pv = 0
    detail["prime_violation"] = pv
    v += pv * 3.0

    return v, detail


def _objective(picks: List[Dict[str, Any]]) -> float:
    """目标函数 = 动量总分 − 惩罚项。越大越优。"""
    score = sum(float(p.get("midhot_score") or 0.0) for p in picks)
    viol, _ = _constraint_violation(picks)
    return score - PENALTY_LAMBDA * viol


def select_optimal_picks(
    profiles: List[Dict[str, Any]],
    pick_size: int = CONSTRAINTS["pick_size"],
    restarts: int = 60,
    max_steps: int = 400,
    seed: int = 20260831,
) -> Dict[str, Any]:
    """在动量池内做约束优化选号。

    候选池：频 3~6（中热）。不足时向 2~7、1~7 逐级扩池。
    方法：多起点随机贪心 + 爬山（swap 邻域），目标为动量分最大且满足硬约束。
    """
    pool = [p for p in profiles if 3 <= p["freq_16"] <= 6]
    pool_scope = "中热池(频3~6)"
    if len(pool) < pick_size:
        pool = [p for p in profiles if 2 <= p["freq_16"] <= 7]
        pool_scope = "扩池(频2~7)"
    if len(pool) < pick_size:
        pool = [p for p in profiles if 1 <= p["freq_16"] <= 7]
        pool_scope = "再扩池(频1~7)"
    if len(pool) < pick_size:
        pool = list(profiles)
        pool_scope = "全80码"

    pool = sorted(pool, key=lambda x: float(x.get("midhot_score") or 0.0), reverse=True)
    n = len(pool)
    rng = random.Random(seed)

    best_picks: List[Dict[str, Any]] = []
    best_obj = -1e18
    best_detail: Dict[str, Any] = {}

    for _ in range(restarts):
        # 起点：按动量序取前 pick_size，再加一点随机扰动
        start = pool[:pick_size]
        if rng.random() < 0.5 and n > pick_size:
            # 随机替换 1~3 个，制造多样性
            for _k in range(rng.randint(1, 3)):
                if n <= pick_size:
                    break
                idx_out = rng.randrange(pick_size)
                idx_in = rng.randrange(pick_size, n)
                start[idx_out] = pool[idx_in]
        current = list(start)
        cur_obj = _objective(current)

        for _step in range(max_steps):
            improved = False
            # 邻域：所有 (选内, 选外) 交换
            out_indices = list(range(pick_size))
            in_indices = list(range(pick_size, n))
            rng.shuffle(out_indices)
            rng.shuffle(in_indices)
            for oi in out_indices:
                for ii in in_indices:
                    cand = list(current)
                    cand[oi] = pool[ii]
                    obj = _objective(cand)
                    if obj > cur_obj + 1e-9:
                        current = cand
                        cur_obj = obj
                        improved = True
                        break
                if improved:
                    break
            if not improved:
                break

        if cur_obj > best_obj:
            best_obj = cur_obj
            best_picks = current
            _, best_detail = _constraint_violation(best_picks)

    picks_sorted = sorted(best_picks, key=lambda x: float(x.get("midhot_score") or 0.0), reverse=True)
    total_score = round(sum(float(p.get("midhot_score") or 0.0) for p in picks_sorted), 4)
    violation, detail = _constraint_violation(picks_sorted)
    feasible = violation <= 1e-9

    return {
        "picks": [p["number"] for p in picks_sorted],
        "pick_size": len(picks_sorted),
        "pool_scope": pool_scope,
        "pool_size": n,
        "total_midhot_score": total_score,
        "feasible": feasible,
        "violation": round(violation, 4),
        "constraint_detail": detail,
        "constraints": dict(CONSTRAINTS),
        "detail": [
            {
                "number": p["number"],
                "display": p["display"],
                "freq_16": p["freq_16"],
                "omission": p["omission"],
                "recent_8_hits": p["recent_8_hits"],
                "midhot_score": p["midhot_score"],
                "tail": p["tail"],
                "road012": p["road012"],
                "prime_class": p["prime_class"],
                "is_outgoing": p["is_outgoing"],
            }
            for p in picks_sorted
        ],
    }


# ───────────────────────────── 综合分析入口 ─────────────────────────────

def analyze_dimension_cross(
    draws: List[Dict[str, Any]],
    target_idx: Optional[int] = None,
) -> Dict[str, Any]:
    """一次性产出：交叉矩阵 + 维度画像 + 最优选号。"""
    if not draws:
        return {"status": "error", "message": "无开奖历史"}
    idx = (len(draws) - 1) if target_idx is None else target_idx
    if idx < WINDOW_SIZE - 1:
        return {"status": "error", "message": f"历史不足 {WINDOW_SIZE} 期"}

    profiles = compute_ball_profiles(draws, idx)
    cross = build_cross_matrix(profiles)

    midhot_profiles = [p for p in profiles if 3 <= p["freq_16"] <= 6]
    dim_midhot = build_dimension_profile(
        profiles, pool_name="中热池(频3~6)",
        pool_filter=lambda p: 3 <= p["freq_16"] <= 6,
    )
    dim_all = build_dimension_profile(profiles, pool_name="全80码")

    optimal = select_optimal_picks(profiles)

    # 纯动量基准（Top20 无约束），用于对比
    momentum_pool = [p for p in profiles if 3 <= p["freq_16"] <= 6]
    if len(momentum_pool) < CONSTRAINTS["pick_size"]:
        momentum_pool = [p for p in profiles if 2 <= p["freq_16"] <= 7]
    momentum_top20 = sorted(
        momentum_pool, key=lambda x: float(x.get("midhot_score") or 0.0), reverse=True
    )[: CONSTRAINTS["pick_size"]]

    return {
        "status": "ok",
        "target_idx": idx,
        "target_period": int(draws[idx]["period"]) + 1,
        "latest_period": int(draws[idx]["period"]),
        "window_range": f"{draws[idx - WINDOW_SIZE + 1]['period']}~{draws[idx]['period']}",
        "outgoing_period": int(draws[idx - WINDOW_SIZE + 1]["period"]),
        "cross_matrix": cross,
        "dimension_profile": dim_midhot,
        "dimension_profile_all": dim_all,
        "optimal_picks": optimal,
        "momentum_baseline": {
            "picks": [p["number"] for p in momentum_top20],
            "total_midhot_score": round(
                sum(float(p.get("midhot_score") or 0.0) for p in momentum_top20), 4
            ),
        },
        "theory": {
            "prime_count_1_80": PRIME_COUNT,
            "composite_count_1_80": COMPOSITE_COUNT,
            "tail_count_per_tail": THEORY_TAIL_COUNT,
            "road_count": THEORY_ROAD_COUNT,
            "note": "1~80 中质数 22 个、合数 57 个、1 为中性；尾数每类 8 个；012 路 26/27/27。",
        },
    }


# ───────────────────────────── 回测仲裁 ─────────────────────────────

def _t_test(vals: List[float], expected: float) -> Tuple[float, float]:
    """单样本 t 检验（大样本近似正态），返回 (t, p)。"""
    n = len(vals)
    if n < 2:
        return 0.0, 1.0
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        return 0.0, 1.0
    t = (mean - expected) / (sd / math.sqrt(n))
    p = math.erfc(abs(t) / math.sqrt(2))
    return round(t, 3), round(p, 4)


def run_dimension_arbitrage(
    draws: List[Dict[str, Any]],
    n_periods: int = 200,
    pick_size: int = 20,
    restarts: int = 25,
) -> Dict[str, Any]:
    """三轨样本外仲裁：纯动量 vs 动量+维度约束 vs 遗漏甜区回补。

    - momentum    : 中热池(频3~6)按 midhot_score 取 Top N
    - constrained : 在 momentum 基础上施加 尾数/012路/质合 硬约束（本研究核心）
    - rebound     : 按 rebound_score 取 Top N（现有金胆轨，对照组）

    每期用 pred_idx=idx-1 的窗口预测，对账 draws[idx] 实际开奖。
    输出各轨平均命中、命中率、对随机期望的 lift 与显著性检验。
    """
    if len(draws) < WINDOW_SIZE + 2:
        return {"status": "error", "message": "历史不足，无法回测"}

    n = min(int(n_periods), len(draws) - WINDOW_SIZE - 1)
    start_idx = len(draws) - n
    size = int(pick_size)
    random_expect = size * 20.0 / NUM_TOTAL

    records: List[Dict[str, Any]] = []
    series = {"momentum": [], "constrained": [], "rebound": []}

    for idx in range(start_idx, len(draws)):
        pred_idx = idx - 1
        profiles = compute_ball_profiles(draws, pred_idx)
        actual = set(draws[idx]["nums"])

        # 轨 1：纯动量
        mom_pool = [p for p in profiles if 3 <= p["freq_16"] <= 6]
        if len(mom_pool) < size:
            mom_pool = [p for p in profiles if 2 <= p["freq_16"] <= 7]
        mom_top = sorted(mom_pool, key=lambda x: x["midhot_score"], reverse=True)[:size]
        mom_hits = sorted(set(p["number"] for p in mom_top) & actual)

        # 轨 2：动量 + 维度约束
        optimal = select_optimal_picks(profiles, pick_size=size, restarts=restarts)
        opt_hits = sorted(set(optimal["picks"]) & actual)

        # 轨 3：遗漏甜区回补
        reb_top = sorted(profiles, key=lambda x: x["rebound_score"], reverse=True)[:size]
        reb_hits = sorted(set(p["number"] for p in reb_top) & actual)

        series["momentum"].append(len(mom_hits))
        series["constrained"].append(len(opt_hits))
        series["rebound"].append(len(reb_hits))

        records.append({
            "period": int(draws[idx]["period"]),
            "actual": sorted(actual),
            "momentum_picks": [p["number"] for p in mom_top],
            "momentum_hits": mom_hits,
            "momentum_hit_n": len(mom_hits),
            "constrained_picks": optimal["picks"],
            "constrained_hits": opt_hits,
            "constrained_hit_n": len(opt_hits),
            "constrained_feasible": optimal["feasible"],
            "rebound_picks": [p["number"] for p in reb_top],
            "rebound_hits": reb_hits,
            "rebound_hit_n": len(reb_hits),
        })

    total = len(records)
    track_summary = {}
    for name, vals in series.items():
        avg = round(sum(vals) / total, 4) if total else 0.0
        rate = round(avg / size * 100, 2) if size else 0.0
        lift = round(avg / random_expect, 3) if random_expect > 0 else None
        t, p = _t_test(vals, random_expect)
        track_summary[name] = {
            "avg_hits": avg,
            "hit_rate_pct": rate,
            "random_expect": round(random_expect, 3),
            "lift": lift,
            "t": t,
            "p": p,
            "significant": bool(p < 0.05),
        }

    # 轨道间配对比较：constrained vs momentum
    diff = [c - m for c, m in zip(series["constrained"], series["momentum"])]
    pair_t, pair_p = _t_test(diff, 0.0)
    pair_mean = round(sum(diff) / total, 4) if total else 0.0

    verdict = _arbitrage_verdict(track_summary, pair_mean, pair_p, total)

    return {
        "status": "ok",
        "n_periods": total,
        "window_size": WINDOW_SIZE,
        "pick_size": size,
        "random_expect": round(random_expect, 3),
        "constraints": dict(CONSTRAINTS),
        "tracks": track_summary,
        "pair_test": {
            "compare": "constrained vs momentum",
            "mean_diff": pair_mean,
            "t": pair_t,
            "p": pair_p,
            "significant": bool(pair_p < 0.05),
        },
        "verdict": verdict,
        "records": records,
    }


def _arbitrage_verdict(tracks: Dict[str, Any], pair_mean: float, pair_p: float, n: int) -> str:
    if n < 30:
        return "样本不足（<30 期），结论仅供参考"
    sig = [k for k, v in tracks.items() if v.get("significant")]
    if not sig:
        return ("三轨对随机期望均无统计显著优势（p≥0.05）。"
                "维度约束不提升命中，价值在结构描述与风险分散，不在选号增益。")
    parts = []
    for k in sig:
        v = tracks[k]
        parts.append(f"{k}（{v['hit_rate_pct']}%，lift {v['lift']}，p={v['p']}）")
    if tracks["constrained"].get("significant") and not tracks["momentum"].get("significant"):
        dim_note = "维度约束带来显著增益，可升级为主轨。"
    elif tracks["constrained"].get("significant") and tracks["momentum"].get("significant"):
        dim_note = "两轨均显著，维度约束未削弱动量，可作为结构均衡器。"
    elif not tracks["constrained"].get("significant") and tracks["momentum"].get("significant"):
        dim_note = "维度约束未能在动量基础上提供额外显著增益。"
    else:
        dim_note = f"维度约束 vs 动量 配对检验 p={pair_p}，差异不显著。"
    return f"统计显著轨道：{('、'.join(parts))}。{dim_note}"


# ───────────────────────────── 仲裁缓存（供研报/大屏复用） ─────────────────────────────

ARBITRAGE_CACHE_REL = os.path.join("sixteen_period", "dimension_arbitrage_latest.json")
ARBITRAGE_MAX_AGE_DAYS = 7


def arbitrage_cache_path() -> str:
    return os.path.join(get_cache_dir(), ARBITRAGE_CACHE_REL)


def load_arbitrage_cache() -> Optional[Dict[str, Any]]:
    p = arbitrage_cache_path()
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("status") != "ok":
        return None
    return data


def save_arbitrage_cache(data: Dict[str, Any]) -> str:
    p = arbitrage_cache_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    payload = dict(data)
    payload["cached_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return p


def get_dimension_arbitrage(
    draws: List[Dict[str, Any]],
    n_periods: int = 200,
    pick_size: int = 20,
    restarts: int = 25,
    use_cache: bool = True,
    max_age_days: int = ARBITRAGE_MAX_AGE_DAYS,
) -> Dict[str, Any]:
    """读取仲裁缓存；缺失 / 过期 / 参数不匹配则重算并落盘。

    研报与每日流水线不应每晚重跑 200 期回测（约 100 秒），
    因此按 7 天有效期复用缓存，参数变化时自动失效。
    """
    if use_cache:
        cached = load_arbitrage_cache()
        if cached:
            age_ok = True
            ts = cached.get("cached_at")
            if ts:
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    age_ok = (datetime.now() - dt).total_seconds() / 86400.0 <= max_age_days
                except Exception:
                    age_ok = False
            params_ok = (
                int(cached.get("n_periods") or 0) == int(n_periods)
                and int(cached.get("pick_size") or 0) == int(pick_size)
            )
            if age_ok and params_ok:
                return cached
    result = run_dimension_arbitrage(
        draws, n_periods=n_periods, pick_size=pick_size, restarts=restarts,
    )
    if result.get("status") == "ok":
        save_arbitrage_cache(result)
    return result
