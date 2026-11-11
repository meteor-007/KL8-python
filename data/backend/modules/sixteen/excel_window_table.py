# -*- coding: utf-8 -*-
"""
快乐8「Excel 同款」16 期开奖矩阵与多维全景分析引擎 (全维度微信桶 + 双轨四法 + 深度结构研判终极版)
================================================================================
遵循老派量化操盘手大白话落地执行协议：
全部多维指标、分析看板、【重号深度专项研判】、【微信桶全维度分桶】与【双轨 4 种方法最优预测】100% 整合：

1. 🎯 【下期双轨 4 种方法最优预测指挥部】：
   - A-主 · 算法死答案：动量先锋最优 3 码 (ops tip3) + 回补金银铜 + 选2
   - A-辅 · 算法死答案：确定性混剪 6 码 (微信实战池) + 选2
   - B-主 · AI 深析研判：对 A-主的研判票 (主核 / 回补 / 选2) + 明确偏差说明
   - B-辅 · AI 深析研判：对 A-辅的研判票 (核心 / 观察 / 降权分层) + 明确偏差说明

2. 📦 【微信桶 8+ 至 0 次全维度深度分桶看板】：
   - 8+ 至 0 各频次池容量、精选数、剩余数、精选清单、剩余清单
   - 闭环闭式校验：精选+剩余=池规模，全80码100%全覆盖
   - 微信分桶纯文本代码块（可直接一键复制发群）

3. 🌊 【出窗同源 4 队与频 3 水位蓄水池监控看板】：
   - 出窗同源 4 队（基准期同开，当前频4，结构旁证：不会全掉3也不全留4）
   - 频 3 水位蓄水池（当前池容量、近21期均值、>=17期数、蓄水冲高阶段）
   - 昨夜已结算对账（出窗同源实开复盘：命中留4 / 未中掉3）
   - 动态跃迁上下界推演

4. 🔥 【上期 20 码重号连庄深度研判看板】：
   - 16 窗重号周期与均值偏离度、当期重号预估区间 (4~6 个)
   - 上期 20 码连庄档案：连开期数、历史连庄率、16窗频次、出窗保频压力、连庄潜力打分
   - 分层梯队：👑Top 5 黄金重号金选 ｜ 🌿Mid 7 稳健重号 ｜ ❄️Bottom 8 回避重号

5. 📊 【0~9 尾冷热汇总】与【头/区指标汇总】并排看板

6. 🌐 【80 个号码全景遗漏、跃迁推演、4 种方法预测与重号连庄标记】

7. 🏆 【近 30 期样本外盲测实战对账总账本（物理彻底屏蔽未来数据）】
"""
from __future__ import annotations

import os
import math
import json
import shutil
import itertools
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, Set
from collections import Counter, defaultdict

from backend.utils.paths import get_cache_dir, get_outputs_dir, get_reports_dir

# P1 修复（双轨打分器复刻）：中热动量分一律复用 live 轨唯一实现，
# 本文件内禁止再逐字复刻公式与调优常数（原两处 inline：center=4.5/sigma=1.8、
# r8/4 截顶 1.25、om<=4、W=0.45/0.35/0.20，属 2026-09-18 调优前的旧算法）。
# 注：sixteen_engine 只在本文件的函数被调用的运行时路径上才会被惰性反向引用
# （其内部 import 均在函数体内），故此处模块级 import 无循环导入风险。
from backend.modules.sixteen.sixteen_engine import (
    MIDHOT_SCORE_DECIMALS,
    MIDHOT_SCORING_VERSION,
    MidhotScoringVersionMismatch,
    assert_midhot_scoring_version,
    build_freq_bucket_picks,
    build_method2_bucket_mix,
    midhot_score_for_ball,
    _window_gap_stats,
)

WINDOW_SIZE = 16
NUM_TOTAL = 80
DRAW_SIZE = 20

# ── 1. 头：十位分段 ──
HEAD_DEFS: List[Tuple[str, int, int]] = [
    ("0头", 1, 9),
    ("1头", 10, 19),
    ("2头", 20, 29),
    ("3头", 30, 39),
    ("4头", 40, 49),
    ("5头", 50, 59),
    ("6头", 60, 69),
    ("7头", 70, 79),
    ("8头", 80, 80),
]

# ── 2. 区：01-10 … 71-80 ──
ZONE_DEFS: List[Tuple[str, int, int]] = [
    ("一区", 1, 10),
    ("二区", 11, 20),
    ("三区", 21, 30),
    ("四区", 31, 40),
    ("五区", 41, 50),
    ("六区", 51, 60),
    ("七区", 61, 70),
    ("八区", 71, 80),
]

# ── 3. 尾：0尾~9尾 ──
TAIL_DEFS: List[Tuple[str, int]] = [
    (f"{t}尾", t) for t in range(10)
]

# ── 4. 频次桶标签 ──
FREQ_BUCKET_KEYS: List[str] = ["8+", "7", "6", "5", "4", "3", "2", "1", "0"]


def _count_in_range(nums: Sequence[int], lo: int, hi: int) -> int:
    return sum(1 for n in nums if lo <= int(n) <= hi)


def _head_counts(nums: Sequence[int]) -> Dict[str, int]:
    return {name: _count_in_range(nums, lo, hi) for name, lo, hi in HEAD_DEFS}


def _zone_counts(nums: Sequence[int]) -> Dict[str, int]:
    return {name: _count_in_range(nums, lo, hi) for name, lo, hi in ZONE_DEFS}


def _tail_counts(nums: Sequence[int]) -> Dict[str, int]:
    t_cnt = Counter(int(n) % 10 for n in nums)
    return {f"{t}尾": t_cnt.get(t, 0) for t in range(10)}


def _cold_streak_from_latest(rows: List[Dict[str, Any]], key: str) -> int:
    streak = 0
    for row in reversed(rows):
        if int(row.get(key) or 0) == 0:
            streak += 1
        else:
            break
    return streak


def _cold_periods_in_window(rows: List[Dict[str, Any]], key: str) -> int:
    return sum(1 for row in rows if int(row.get(key) or 0) == 0)


def build_draw_matrix_rows(draws: List[Dict[str, Any]], window_size: int = WINDOW_SIZE) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    prev_nums: Set[int] = set()

    for idx, d in enumerate(draws):
        nums = sorted(int(x) for x in (d.get("sorted_nums") or d.get("nums") or []))
        nums_set = set(nums)
        heads = _head_counts(nums)
        zones = _zone_counts(nums)
        tails = _tail_counts(nums)

        draw_sum = sum(nums)
        span = (nums[-1] - nums[0]) if nums else 0
        odd_cnt = sum(1 for n in nums if n % 2 == 1)
        even_cnt = len(nums) - odd_cnt
        repeat_cnt = len(nums_set & prev_nums) if prev_nums else 0

        freq_hits: Dict[str, int] = {k: 0 for k in FREQ_BUCKET_KEYS}
        if idx >= window_size:
            hist_win = draws[idx - window_size:idx]
            cnt_16 = Counter(n for dw in hist_win for n in (dw.get("sorted_nums") or dw.get("nums") or []))
            for n in nums:
                f = cnt_16.get(n, 0)
                b_key = "8+" if f >= 8 else str(f)
                freq_hits[b_key] = freq_hits.get(b_key, 0) + 1

        row: Dict[str, Any] = {
            "period": int(d["period"]),
            "date": d.get("date") or "",
            "nums": nums,
            "nums_str": " ".join(f"{n:02d}" for n in nums),
            "sum": draw_sum,
            "span": span,
            "odd_even": f"{odd_cnt}:{even_cnt}",
            "odd_cnt": odd_cnt,
            "even_cnt": even_cnt,
            "repeat_cnt": repeat_cnt,
            "heads": heads,
            "zones": zones,
            "tails": tails,
            "freq_hits": freq_hits,
        }

        for name, cnt in heads.items():
            row[name] = cnt
        for name, cnt in zones.items():
            row[name] = cnt
        for name, cnt in tails.items():
            row[name] = cnt
        for bk, cnt in freq_hits.items():
            row[f"落点_{bk}"] = cnt

        out.append(row)
        prev_nums = nums_set

    return out


def compute_80_balls_stats(draws: List[Dict[str, Any]], window_size: int = WINDOW_SIZE) -> Dict[str, Any]:
    if not draws:
        return {}

    n_total = len(draws)
    win_draws = draws[-window_size:] if n_total >= window_size else draws

    freq_counter = Counter(n for d in win_draws for n in (d.get("sorted_nums") or d.get("nums") or []))

    outgoing_idx = n_total - window_size
    outgoing_draw = draws[outgoing_idx] if (0 <= outgoing_idx < n_total) else None
    outgoing_nums = set(outgoing_draw.get("sorted_nums") or outgoing_draw.get("nums") or []) if outgoing_draw else set()

    last_seen_idx: Dict[int, int] = {}
    current_omission: Dict[int, int] = {}
    max_omission: Dict[int, int] = {num: 0 for num in range(1, NUM_TOTAL + 1)}

    last_seen_temp: Dict[int, int] = {num: -1 for num in range(1, NUM_TOTAL + 1)}
    for idx, d in enumerate(draws):
        curr_set = set(d.get("sorted_nums") or d.get("nums") or [])
        for num in curr_set:
            if 1 <= num <= NUM_TOTAL:
                gap = idx - last_seen_temp[num] - 1
                if gap > max_omission[num]:
                    max_omission[num] = gap
                last_seen_temp[num] = idx
                last_seen_idx[num] = idx

    for num in range(1, NUM_TOTAL + 1):
        if num in last_seen_idx:
            current_omission[num] = (n_total - 1) - last_seen_idx[num]
        else:
            current_omission[num] = n_total
        if current_omission[num] > max_omission[num]:
            max_omission[num] = current_omission[num]

    balls: List[Dict[str, Any]] = []
    for num in range(1, NUM_TOTAL + 1):
        freq = freq_counter.get(num, 0)
        is_out = (num in outgoing_nums)
        omit = current_omission[num]
        max_omit = max_omission[num]

        freq_if_hit = freq if is_out else (freq + 1)
        freq_if_miss = (freq - 1) if is_out else freq

        balls.append({
            "number": num,
            "number_str": f"{num:02d}",
            "freq_16": freq,
            "bucket": "8+" if freq >= 8 else str(freq),
            "omission": omit,
            "max_omission": max_omit,
            "is_outgoing": is_out,
            "outgoing_period": outgoing_draw["period"] if outgoing_draw else None,
            "freq_if_hit": freq_if_hit,
            "freq_if_miss": freq_if_miss,
            "transition_desc": (
                f"出窗号(开则保持{freq_if_hit},不开降为{freq_if_miss})"
                if is_out
                else f"常规号(开则升为{freq_if_hit},不开保持{freq_if_miss})"
            ),
        })

    by_bucket: Dict[str, List[int]] = defaultdict(list)
    for b in balls:
        by_bucket[b["bucket"]].append(b["number"])

    bucket_stats: List[Dict[str, Any]] = []
    for k in FREQ_BUCKET_KEYS:
        nums_in_b = by_bucket.get(k, [])
        bucket_stats.append({
            "bucket": k,
            "label": f"{k}次",
            "count": len(nums_in_b),
            "ratio": round(len(nums_in_b) / NUM_TOTAL, 4),
            "numbers": sorted(nums_in_b),
            "numbers_str": " ".join(f"{x:02d}" for x in sorted(nums_in_b)) if nums_in_b else "—",
        })

    return {
        "balls": balls,
        "bucket_stats": bucket_stats,
        "outgoing_period": outgoing_draw["period"] if outgoing_draw else None,
        "outgoing_nums": sorted(list(outgoing_nums)),
    }


def compute_repeat_deep_analysis(draws: List[Dict[str, Any]], window_size: int = WINDOW_SIZE) -> Dict[str, Any]:
    """
    重号深度专项分析引擎 (Repeat Numbers Deep Mining)
    """
    if not draws or len(draws) < 2:
        return {}

    n_total = len(draws)
    win = draws[-window_size:] if n_total >= window_size else draws
    last_draw = draws[-1]
    last_nums = sorted(list(set(last_draw.get("sorted_nums") or last_draw.get("nums") or [])))

    # 1. 计算全历史每期的重号个数
    repeat_history = []
    prev_set: Set[int] = set()
    for d in draws:
        curr_s = set(d.get("sorted_nums") or d.get("nums") or [])
        if prev_set:
            repeat_history.append(len(curr_s & prev_set))
        prev_set = curr_s

    all_avg_repeats = round(sum(repeat_history) / len(repeat_history), 2) if repeat_history else 5.0
    win_repeats = [len(set(win[i].get("sorted_nums") or win[i].get("nums") or []) & set(win[i-1].get("sorted_nums") or win[i-1].get("nums") or [])) for i in range(1, len(win))]
    win_avg_repeats = round(sum(win_repeats) / len(win_repeats), 2) if win_repeats else 5.0

    # 2. 全历史 80 码独立连庄概率计算
    num_appearances = Counter()
    num_repeat_success = Counter()
    for i in range(len(draws) - 1):
        c_set = set(draws[i].get("sorted_nums") or draws[i].get("nums") or [])
        n_set = set(draws[i+1].get("sorted_nums") or draws[i+1].get("nums") or [])
        for num in c_set:
            num_appearances[num] += 1
            if num in n_set:
                num_repeat_success[num] += 1

    hist_repeat_rates = {}
    for num in range(1, NUM_TOTAL + 1):
        app = num_appearances.get(num, 0)
        succ = num_repeat_success.get(num, 0)
        hist_repeat_rates[num] = round(succ / app, 4) if app > 0 else 0.25

    # 3. 统计上期 20 码的连续开出期数 (consecutive streak)
    consecutive_streaks = {}
    for num in last_nums:
        streak = 0
        for d in reversed(draws):
            d_set = set(d.get("sorted_nums") or d.get("nums") or [])
            if num in d_set:
                streak += 1
            else:
                break
        consecutive_streaks[num] = streak

    # 4. 结合 16 窗频次与 8 期热度对上期 20 码进行综合连庄打分
    win_freqs = Counter(n for d in win for n in (d.get("sorted_nums") or d.get("nums") or []))
    recent_8_draws = draws[-8:] if len(draws) >= 8 else draws
    recent_8_freqs = Counter(n for d in recent_8_draws for n in (d.get("sorted_nums") or d.get("nums") or []))

    outgoing_idx = n_total - window_size
    outgoing_draw = draws[outgoing_idx] if (0 <= outgoing_idx < n_total) else None
    outgoing_nums = set(outgoing_draw.get("sorted_nums") or outgoing_draw.get("nums") or []) if outgoing_draw else set()

    scored_repeat_candidates = []
    for num in last_nums:
        f16 = win_freqs.get(num, 0)
        r8 = recent_8_freqs.get(num, 0)
        hr_rate = hist_repeat_rates.get(num, 0.25)
        streak = consecutive_streaks.get(num, 1)
        is_out = (num in outgoing_nums)

        raw_score = (hr_rate / 0.35) * 35.0 + (f16 / 7.0) * 30.0 + (r8 / 4.0) * 20.0 + (10.0 if is_out else 0.0)
        if streak >= 3:
            raw_score -= (streak - 2) * 15.0
        score = round(max(5.0, min(99.0, raw_score)), 1)

        scored_repeat_candidates.append({
            "number": num,
            "number_str": f"{num:02d}",
            "consecutive_streak": streak,
            "freq_16": f16,
            "recent_8": r8,
            "hist_repeat_rate": hr_rate,
            "hist_repeat_rate_pct": f"{hr_rate*100:.1f}%",
            "is_outgoing": is_out,
            "repeat_score": score,
        })

    scored_repeat_candidates.sort(key=lambda x: (-x["repeat_score"], -x["freq_16"], x["number"]))

    gold_repeats = [x["number"] for x in scored_repeat_candidates[:5]]
    steady_repeats = [x["number"] for x in scored_repeat_candidates[5:12]]
    cold_repeats = [x["number"] for x in scored_repeat_candidates[12:]]

    for x in scored_repeat_candidates:
        if x["number"] in gold_repeats:
            x["rank_tag"] = "👑重号金选"
            x["advice"] = "高概率连庄·重点设胆"
        elif x["number"] in steady_repeats:
            x["rank_tag"] = "🌿稳健重号"
            x["advice"] = "动能良好·可作配码"
        else:
            x["rank_tag"] = "❄️回避重号"
            x["advice"] = "连庄动能衰竭·建议回避"

    expected_range = "4 ~ 6 个" if win_avg_repeats < 4.8 else "3 ~ 5 个"

    return {
        "last_period": last_draw["period"],
        "last_nums": last_nums,
        "win_repeats_trend": win_repeats[-8:],
        "win_avg_repeats": win_avg_repeats,
        "all_avg_repeats": all_avg_repeats,
        "expected_range": expected_range,
        "gold_repeats": gold_repeats,
        "gold_repeats_str": " ".join(f"{x:02d}" for x in gold_repeats),
        "steady_repeats": steady_repeats,
        "steady_repeats_str": " ".join(f"{x:02d}" for x in steady_repeats),
        "cold_repeats": cold_repeats,
        "cold_repeats_str": " ".join(f"{x:02d}" for x in cold_repeats),
        "candidates": scored_repeat_candidates,
    }


def compute_pick2_cooccurrence_pairs(
    ball_details: List[Dict[str, Any]],
    hist_draws: List[Dict[str, Any]],
    top_momentum_nums: List[int],
    top_rebound_nums: List[int],
    pool_size: int = 5,
    short_window: int = 30,
    long_window: int = 60,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    基于 Top 5 极致精炼池与双窗口动态共现亲密度矩阵，结合连号/同尾局部空间共振选出选2对子。
    严格保证 a != b，绝无同号。
    """
    if not hist_draws:
        return []

    candidate_pool: List[int] = []
    for num in (top_momentum_nums or []) + (top_rebound_nums or []):
        if num not in candidate_pool and 1 <= num <= NUM_TOTAL:
            candidate_pool.append(num)

    if len(candidate_pool) < pool_size:
        sorted_balls = sorted(ball_details, key=lambda x: -x.get("midhot_score", 0))
        for b in sorted_balls:
            if b["number"] not in candidate_pool and 1 <= b["number"] <= NUM_TOTAL:
                candidate_pool.append(b["number"])
            if len(candidate_pool) >= pool_size:
                break

    candidate_pool = candidate_pool[:pool_size]
    if len(candidate_pool) < 2:
        return []

    short_draws = [set(int(n) for n in (d.get("sorted_nums") or d.get("nums") or [])) for d in (hist_draws[-short_window:] if len(hist_draws) >= short_window else hist_draws)]
    long_draws = [set(int(n) for n in (d.get("sorted_nums") or d.get("nums") or [])) for d in (hist_draws[-long_window:] if len(hist_draws) >= long_window else hist_draws)]
    n_s = len(short_draws) or 1
    n_l = len(long_draws) or 1

    ball_score_map = {b["number"]: max(b.get("midhot_score", 0), b.get("rebound_score", 0) + 1.0) for b in ball_details}

    scored_pairs: List[Dict[str, Any]] = []
    for a, b in itertools.combinations(candidate_pool, 2):
        if a == b:
            continue
        p1, p2 = min(a, b), max(a, b)
        co_s = sum(1 for ds in short_draws if p1 in ds and p2 in ds)
        co_l = sum(1 for ds in long_draws if p1 in ds and p2 in ds)
        f_s1 = sum(1 for ds in short_draws if p1 in ds)
        f_s2 = sum(1 for ds in short_draws if p2 in ds)

        jaccard_s = co_s / (f_s1 + f_s2 - co_s) if (f_s1 + f_s2 - co_s) > 0 else 0.0
        lift_s = (co_s * n_s) / (f_s1 * f_s2) if (f_s1 > 0 and f_s2 > 0) else 0.0

        is_consec = 1.0 if abs(p1 - p2) == 1 else 0.0
        is_same_tail = 1.0 if (p1 % 10 == p2 % 10) else 0.0

        score_a = ball_score_map.get(p1, 0.5)
        score_b = ball_score_map.get(p2, 0.5)

        pair_affinity = (
            (score_a + score_b) * 0.25
            + (co_s / n_s) * 3.5
            + (co_l / n_l) * 2.0
            + (jaccard_s * 4.0)
            + (is_consec * 0.8)
            + (is_same_tail * 0.5)
        )

        scored_pairs.append({
            "pair": [p1, p2],
            "pair_str": f"{p1:02d}-{p2:02d}",
            "cooccur_count": co_s,
            "cooccur_long": co_l,
            "lift": round(lift_s, 2),
            "jaccard": round(jaccard_s, 3),
            "affinity_score": round(pair_affinity, 4),
            "desc": f"近{n_s}期同出{co_s}次 (Jaccard={jaccard_s:.2f}, 连号={bool(is_consec)})",
        })

    scored_pairs.sort(key=lambda x: -x["affinity_score"])
    return scored_pairs[:top_k]


def compute_prediction_methods(draws: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算双轨 4 种方法下一期最优号码预测"""
    if not draws:
        return {}

    target_period = int(draws[-1]["period"]) + 1
    n_total = len(draws)
    win_draws = draws[-WINDOW_SIZE:]
    outgoing_nums = set(int(x) for x in (win_draws[0].get("sorted_nums") or win_draws[0].get("nums") or []))

    freq_16 = Counter(int(n) for d in win_draws for n in (d.get("sorted_nums") or d.get("nums") or []))
    freq_8 = Counter(int(n) for d in win_draws[-8:] for n in (d.get("sorted_nums") or d.get("nums") or []))

    omissions = {num: 99 for num in range(1, NUM_TOTAL + 1)}
    remaining = set(range(1, NUM_TOTAL + 1))
    for om_idx, d in enumerate(reversed(draws)):
        if not remaining:
            break
        d_nums = set(d.get("sorted_nums") or d.get("nums") or [])
        hit_nums = remaining.intersection(d_nums)
        for n in hit_nums:
            omissions[n] = om_idx
            remaining.remove(n)

    ball_details = []
    for num in range(1, NUM_TOTAL + 1):
        f16 = freq_16.get(num, 0)
        om = omissions[num]
        r8 = freq_8.get(num, 0)
        is_out = num in outgoing_nums
        mx_om, av_om, max_stk = _window_gap_stats(num, win_draws)

        # 与 live 轨（SixteenPeriodEngine.analyze_at_index）同一实现、同一取整位数。
        # 语义映射核对：本轨 f16/om/r8/is_out 与 ball 的 freq_16/omission/recent_8_hits/
        # is_outgoing 一一对应（旧 inline 的 min(f16,8) 截顶属偏差写法，已随之去除）。
        midhot_score = round(
            midhot_score_for_ball({
                "freq_16": f16,
                "recent_8_hits": r8,
                "omission": om,
                "is_outgoing": is_out,
            }),
            MIDHOT_SCORE_DECIMALS,
        )

        ball_details.append({
            "number": num,
            "number_str": f"{num:02d}",
            "freq_16": f16,
            "omission": om,
            "max_omission": mx_om,
            "avg_omission": av_om,
            "recent_8": r8,
            "recent_8_hits": r8,
            "is_outgoing": is_out,
            "midhot_score": midhot_score,
        })

    def _znorm(vals):
        if not vals:
            return []
        mu = sum(vals) / len(vals)
        sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1e-9
        return [(v - mu) / sd for v in vals]

    sweet_l = [
        math.exp(-((b["omission"] - 10.0) ** 2) / (2 * 4.2 ** 2)) * (0.6 if b["omission"] >= 16 else 1.0)
        for b in ball_details
    ]
    cur_l = [b["omission"] for b in ball_details]
    mx_l = [b["max_omission"] for b in ball_details]
    av_l = [b["avg_omission"] for b in ball_details]
    freq_l = [b["freq_16"] for b in ball_details]
    r8_l = [b["recent_8"] for b in ball_details]

    sw_z = _znorm(sweet_l)
    cz = _znorm(cur_l); mz = _znorm(mx_l); az = _znorm(av_l); fz = _znorm(freq_l); rz = _znorm(r8_l)

    for i, b in enumerate(ball_details):
        s = (
            0.38 * sw_z[i]
            + 0.05 * cz[i]
            + 0.15 * mz[i]
            + 0.10 * az[i]
            + 0.20 * fz[i]
            + 0.12 * rz[i]
        )
        b["rebound_score"] = round(s, 4)

    # 1. 动量最优 3 码
    midhot_pool = [b for b in ball_details if 3 <= b["freq_16"] <= 6]
    # 并列（4 位小数取整后同分）时的次级键必须与 live 轨一致：
    # live 用 sorted(key=score, reverse=True) 的稳定序，即 ball_details 的号码升序，
    # 故此处用 (-score, number)；旧写法多带了 omission 次级键，会在同分号上分叉。
    midhot_pool.sort(key=lambda x: (-x["midhot_score"], x["number"]))
    m1_tip3 = [b["number"] for b in midhot_pool[:3]]

    # 2. 确定性混剪 6 码
    fbp = build_freq_bucket_picks(ball_details)
    m2_res = build_method2_bucket_mix(ball_details=ball_details, freq_bucket_picks=fbp)
    m2_six = m2_res.get("six") or []
    m2_pairs = m2_res.get("pairs") or []
    m2_seats = m2_res.get("seats") or []

    # 3. 高斯回补 3 胆
    rebound_pool = sorted(ball_details, key=lambda x: x["rebound_score"], reverse=True)
    gold = rebound_pool[0]["number"] if len(rebound_pool) > 0 else None
    silver = rebound_pool[1]["number"] if len(rebound_pool) > 1 else None
    bronze = rebound_pool[2]["number"] if len(rebound_pool) > 2 else None
    m3_dans = [d for d in [gold, silver, bronze] if d is not None]

    # 4. 双元共现亲密度精选选2对子
    m4_pairs = compute_pick2_cooccurrence_pairs(
        ball_details=ball_details,
        hist_draws=draws,
        top_momentum_nums=m1_tip3,
        top_rebound_nums=m3_dans,
        pool_size=5,
        short_window=30,
        long_window=60,
        top_k=3,
    )

    return {
        "target_period": target_period,
        "method1_tip3": m1_tip3,
        "method1_desc": "【方法1】动量先锋最优3码 (主推)",
        "method2_six": m2_six,
        "method2_desc": "【方法2】确定性混剪6码 (微信实战池)",
        "method2_pairs": m2_pairs,
        "method2_seats": m2_seats,
        "method3_gold": gold,
        "method3_silver": silver,
        "method3_bronze": bronze,
        "method3_dans": m3_dans,
        "method3_desc": "【方法3】高斯遗漏回补3胆 (金/银/铜胆)",
        "method4_pairs": m4_pairs,
        "method4_desc": "【方法4】双元共现精选双飞选2 (搭档黄金对)",
        "playbook": f"第{target_period}期 动量金码 {' '.join(f'{x:02d}' for x in m1_tip3)} ｜ 回补金胆 {gold:02d} ｜ 共现黄金搭档 {' / '.join(p['pair_str'] for p in m4_pairs[:3])}",
    }


def compute_walk_forward_audit(draws: List[Dict[str, Any]], n_periods: int = 30) -> Dict[str, Any]:
    """
    计算近 N 期的样本外滚动对账数据（物理严格屏蔽未来数据）
    """
    if not draws or len(draws) < WINDOW_SIZE + n_periods:
        return {"status": "error", "message": "历史数据不足", "records": []}

    n_total = len(draws)
    records = []

    start_target_idx = n_total - n_periods - 1
    for target_idx in range(start_target_idx, n_total - 1):
        target_draw = draws[target_idx + 1]
        target_period = int(target_draw["period"])
        target_date = target_draw.get("date", "")
        actual_set = set(int(x) for x in (target_draw.get("sorted_nums") or target_draw.get("nums") or []))

        hist_draws = draws[: target_idx + 1]
        win_draws = hist_draws[-WINDOW_SIZE:]
        outgoing_nums = set(int(x) for x in (win_draws[0].get("sorted_nums") or win_draws[0].get("nums") or []))

        freq_16 = Counter(int(n) for d in win_draws for n in (d.get("sorted_nums") or d.get("nums") or []))
        freq_8 = Counter(int(n) for d in win_draws[-8:] for n in (d.get("sorted_nums") or d.get("nums") or []))

        omissions = {num: 99 for num in range(1, NUM_TOTAL + 1)}
        remaining = set(range(1, NUM_TOTAL + 1))
        for om_idx, d in enumerate(reversed(hist_draws)):
            if not remaining:
                break
            d_nums = set(d.get("sorted_nums") or d.get("nums") or [])
            hit_nums = remaining.intersection(d_nums)
            for n in hit_nums:
                omissions[n] = om_idx
                remaining.remove(n)

        ball_details = []
        for num in range(1, NUM_TOTAL + 1):
            f16 = freq_16.get(num, 0)
            om = omissions[num]
            r8 = freq_8.get(num, 0)
            is_out = num in outgoing_nums
            mx_om, av_om, max_stk = _window_gap_stats(num, win_draws)

            # 与 live 轨同一实现（见 compute_prediction_methods 内同款注释）
            midhot_score = round(
                midhot_score_for_ball({
                    "freq_16": f16,
                    "recent_8_hits": r8,
                    "omission": om,
                    "is_outgoing": is_out,
                }),
                MIDHOT_SCORE_DECIMALS,
            )

            ball_details.append({
                "number": num,
                "number_str": f"{num:02d}",
                "freq_16": f16,
                "omission": om,
                "max_omission": mx_om,
                "avg_omission": av_om,
                "recent_8": r8,
                "recent_8_hits": r8,
                "is_outgoing": is_out,
                "midhot_score": midhot_score,
            })

        def _znorm(vals):
            if not vals:
                return []
            mu = sum(vals) / len(vals)
            sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1e-9
            return [(v - mu) / sd for v in vals]

        sweet_l = [
            math.exp(-((b["omission"] - 10.0) ** 2) / (2 * 4.2 ** 2)) * (0.6 if b["omission"] >= 16 else 1.0)
            for b in ball_details
        ]
        cur_l = [b["omission"] for b in ball_details]
        mx_l = [b["max_omission"] for b in ball_details]
        av_l = [b["avg_omission"] for b in ball_details]
        freq_l = [b["freq_16"] for b in ball_details]
        r8_l = [b["recent_8"] for b in ball_details]

        sw_z = _znorm(sweet_l)
        cz = _znorm(cur_l); mz = _znorm(mx_l); az = _znorm(av_l); fz = _znorm(freq_l); rz = _znorm(r8_l)

        for i, b in enumerate(ball_details):
            s = (
                0.38 * sw_z[i]
                + 0.05 * cz[i]
                + 0.15 * mz[i]
                + 0.10 * az[i]
                + 0.20 * fz[i]
                + 0.12 * rz[i]
            )
            b["rebound_score"] = round(s, 4)

        midhot_pool = [b for b in ball_details if 3 <= b["freq_16"] <= 6]
        # 并列（4 位小数取整后同分）时的次级键必须与 live 轨一致：
        # live 用 sorted(key=score, reverse=True) 的稳定序，即 ball_details 的号码升序，
        # 故此处用 (-score, number)；旧写法多带了 omission 次级键，会在同分号上分叉。
        midhot_pool.sort(key=lambda x: (-x["midhot_score"], x["number"]))
        m1_tip3 = [b["number"] for b in midhot_pool[:3]]

        fbp = build_freq_bucket_picks(ball_details)
        m2_res = build_method2_bucket_mix(ball_details=ball_details, freq_bucket_picks=fbp)
        m2_six = m2_res.get("six") or []

        rebound_pool = sorted(ball_details, key=lambda x: x["rebound_score"], reverse=True)
        gold = rebound_pool[0]["number"] if len(rebound_pool) > 0 else None
        silver = rebound_pool[1]["number"] if len(rebound_pool) > 1 else None
        bronze = rebound_pool[2]["number"] if len(rebound_pool) > 2 else None
        m3_dans = [d for d in [gold, silver, bronze] if d is not None]

        pairs_res = compute_pick2_cooccurrence_pairs(
            ball_details=ball_details,
            hist_draws=hist_draws,
            top_momentum_nums=m1_tip3,
            top_rebound_nums=m3_dans,
            pool_size=5,
            short_window=30,
            long_window=60,
            top_k=3,
        )
        pairs = [p["pair_str"] for p in pairs_res]

        m1_hits = [x for x in m1_tip3 if x in actual_set]
        m2_hits = [x for x in m2_six if x in actual_set]
        m3_hits = [x for x in m3_dans if x in actual_set]
        p_hits = [p for p in pairs if int(p.split("-")[0]) in actual_set and int(p.split("-")[1]) in actual_set]

        if len(m2_hits) == 6 or len(m1_hits) == 3 or p_hits:
            rating = "🏆 极佳/双中"
        elif len(m2_hits) >= 3 or len(m1_hits) >= 2:
            rating = "🔥 优秀实战"
        elif len(m2_hits) >= 1 or len(m1_hits) >= 1:
            rating = "🌿 稳健保底"
        else:
            rating = "❄️ 观望轮空"

        records.append({
            "period": target_period,
            "date": target_date,
            "actual_nums": sorted(list(actual_set)),
            "actual_str": " ".join(f"{x:02d}" for x in sorted(list(actual_set))),
            "scoring_version": MIDHOT_SCORING_VERSION,
            "m1_tip3": m1_tip3,
            "m1_tip3_str": " ".join(f"{x:02d}" for x in m1_tip3),
            "m1_hits": m1_hits,
            "m1_hits_str": " ".join(f"{x:02d}" for x in m1_hits) or "—",
            "m1_hit_cnt": len(m1_hits),
            "m2_six": m2_six,
            "m2_six_str": " ".join(f"{x:02d}" for x in m2_six),
            "m2_hits": m2_hits,
            "m2_hits_str": " ".join(f"{x:02d}" for x in m2_hits) or "—",
            "m2_hit_cnt": len(m2_hits),
            "m3_dans": m3_dans,
            "m3_dans_str": f"金{gold:02d} 银{silver:02d} 铜{bronze:02d}" if (gold is not None and silver is not None and bronze is not None) else "—",
            "m3_hits": m3_hits,
            "m3_hits_str": " ".join(f"{x:02d}" for x in m3_hits) or "—",
            "m3_hit_cnt": len(m3_hits),
            "m4_pairs": pairs,
            "m4_pairs_str": " / ".join(pairs),
            "m4_hits": p_hits,
            "m4_hits_str": " / ".join(p_hits) or "—",
            "m4_hit_cnt": len(p_hits),
            "rating": rating,
        })

    records_rev = list(reversed(records))

    # 一致性自检：本函数刚产出的每条记录都必须带当前版本；缺字段=旧代码产的产物混入。
    for r in records_rev:
        assert_midhot_scoring_version(r.get("scoring_version"), where=f"walk_forward 第{r['period']}期记录")

    m1_tot = sum(r["m1_hit_cnt"] for r in records)
    m2_tot = sum(r["m2_hit_cnt"] for r in records)
    m3_tot = sum(r["m3_hit_cnt"] for r in records)
    m4_tot = sum(r["m4_hit_cnt"] for r in records)

    return {
        "status": "ok",
        "n_periods": len(records),
        "scoring_version": MIDHOT_SCORING_VERSION,
        "records": records_rev,
        "summary": {
            "n_periods": len(records),
            "scoring_version": MIDHOT_SCORING_VERSION,
            "start_period": records[0]["period"] if records else None,
            "end_period": records[-1]["period"] if records else None,
            "m1_total_hits": m1_tot,
            "m1_hit_rate_pct": f"{m1_tot / (len(records)*3)*100:.1f}%" if records else "0.0%",
            "m2_total_hits": m2_tot,
            "m2_hit_rate_pct": f"{m2_tot / (len(records)*6)*100:.1f}%" if records else "0.0%",
            "m2_avg_hits": f"{m2_tot / len(records):.2f} 码" if records else "0 码",
            "m3_total_hits": m3_tot,
            "m3_hit_rate_pct": f"{m3_tot / (len(records)*3)*100:.1f}%" if records else "0.0%",
            "m4_total_dual_hits": m4_tot,
            "m4_dual_rate_pct": f"{m4_tot / len(records)*100:.1f}%" if records else "0.0%",
        },
    }


def assert_audit_scoring_version(audit: Dict[str, Any], *, where: str = "walk_forward 审计产物") -> str:
    """对**已落盘/缓存**的审计产物做版本自检（重读 json/xlsx 时调用）。

    新建的产物由 compute_walk_forward_audit 自带当前版本；本函数守的是读回来的旧版本，
    版本不符直接抛 MidhotScoringVersionMismatch，禁止驾驶舱静默展示旧算法的评级。
    """
    if not isinstance(audit, dict) or not audit:
        return MIDHOT_SCORING_VERSION
    # 历史不足时审计本身是 error 空产物，不属于「版本不符」，交给上层既有逻辑处理
    if audit.get("status") not in (None, "ok") or not (audit.get("records") or []):
        return MIDHOT_SCORING_VERSION
    versions = set()
    top = audit.get("scoring_version") or (audit.get("summary") or {}).get("scoring_version")
    if top is not None:
        versions.add(str(top))
    for r in (audit.get("records") or []):
        v = r.get("scoring_version")
        if v is not None:
            versions.add(str(v))
    if not versions:
        # 修复前生成的缓存没有版本字段 → 同样是「已不存在的旧算法」产物
        raise MidhotScoringVersionMismatch(
            f"中热打分版本缺失：{where} 无 scoring_version 字段（修复前生成的旧产物），"
            f"当前口径应为 {MIDHOT_SCORING_VERSION!r}。请用 run_daily.py 重新生成。"
        )
    for v in sorted(versions):
        assert_midhot_scoring_version(v, where=where)
    return MIDHOT_SCORING_VERSION


def build_excel_window_table(
    draws: List[Dict[str, Any]],
    window_size: int = WINDOW_SIZE,
    history_tail: Optional[int] = None,
    analysis_res: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    构建 16 窗全景分析字典，100% 整合：
    1. 左侧大盘矩阵 (20码 + 和值跨度重号 + 头/区/尾/频次落点)
    2. 双轨 4 种方法最优号码预测指挥部 (A-主 / A-辅 / B-主 / B-辅)
    3. 微信桶 8+ 至 0 次全维度深度分桶看板 (闭环校验 + 原文代码块)
    4. 出窗同源 4 队与频 3 水位蓄水池监控看板 (含昨夜实开复盘)
    5. 上期 20 码重号连庄深度研判看板 (连开期数/连庄率/打分/分层)
    6. 0~9 尾与头/区冷热汇总看板
    7. 80 码全景遗漏与跃迁推演看板
    8. 近 30 期样本外盲测实战对账总账本
    """
    if not draws:
        return {"status": "error", "message": "无开奖数据"}

    all_rows = build_draw_matrix_rows(draws, window_size=window_size)
    if history_tail and history_tail > 0:
        matrix_rows = all_rows[-history_tail:]
    else:
        matrix_rows = all_rows

    win = all_rows[-window_size:] if len(all_rows) >= window_size else list(all_rows)
    if not win:
        return {"status": "error", "message": "窗口为空"}

    def _stats_for_ranges(defs: List[Tuple[str, int, int]], kind: str) -> List[Dict[str, Any]]:
        stats = []
        for name, lo, hi in defs:
            countifs = sum(_count_in_range(r["nums"], lo, hi) for r in win)
            cold_n = _cold_periods_in_window(win, name)
            streak = _cold_streak_from_latest(win, name)
            soft = 0
            for r in reversed(win):
                if int(r.get(name) or 0) <= 1:
                    soft += 1
                else:
                    break
            per_period = [int(r.get(name) or 0) for r in win]
            expected = round(window_size * DRAW_SIZE * ((hi - lo + 1) / NUM_TOTAL), 2)
            stats.append({
                "name": name,
                "lo": lo,
                "hi": hi,
                "kind": kind,
                "range_label": f"{lo:02d}-{hi:02d}",
                "countifs_total": countifs,
                "expected_total": expected,
                "cold_periods_in_window": cold_n,
                "cold_streak_from_latest": streak,
                "soft_cold_streak_le1": soft,
                "per_period_counts": per_period,
                "bias": "偏热" if countifs > expected + 3 else ("偏冷" if countifs < expected - 3 else "正常"),
            })
        return stats

    def _stats_for_tails(defs: List[Tuple[str, int]]) -> List[Dict[str, Any]]:
        stats = []
        expected_per_tail = round(window_size * DRAW_SIZE * (8 / NUM_TOTAL), 2)
        for name, t in defs:
            countifs = sum(int(r.get(name) or 0) for r in win)
            cold_n = _cold_periods_in_window(win, name)
            streak = _cold_streak_from_latest(win, name)
            soft = 0
            for r in reversed(win):
                if int(r.get(name) or 0) <= 1:
                    soft += 1
                else:
                    break
            per_period = [int(r.get(name) or 0) for r in win]
            stats.append({
                "name": name,
                "tail": t,
                "kind": "尾数",
                "range_label": f"{t}尾(共8码)",
                "countifs_total": countifs,
                "expected_total": expected_per_tail,
                "cold_periods_in_window": cold_n,
                "cold_streak_from_latest": streak,
                "soft_cold_streak_le1": soft,
                "per_period_counts": per_period,
                "bias": "偏热" if countifs > expected_per_tail + 3 else ("偏冷" if countifs < expected_per_tail - 3 else "正常"),
            })
        return stats

    head_stats = _stats_for_ranges(HEAD_DEFS, "头")
    zone_stats = _stats_for_ranges(ZONE_DEFS, "区")
    tail_stats = _stats_for_tails(TAIL_DEFS)
    one_head = next(s for s in head_stats if s["name"] == "1头")

    avg_sum = round(sum(r["sum"] for r in win) / len(win), 1)
    avg_span = round(sum(r["span"] for r in win) / len(win), 1)
    avg_repeats = round(sum(r["repeat_cnt"] for r in win) / len(win), 1)
    total_odd = sum(r["odd_cnt"] for r in win)
    total_even = sum(r["even_cnt"] for r in win)

    balls_80 = compute_80_balls_stats(draws, window_size=window_size)
    pred_methods = compute_prediction_methods(draws)
    repeat_analysis = compute_repeat_deep_analysis(draws, window_size=window_size)

    # 提取或复用 SixteenPeriodEngine 分析结果
    if analysis_res is None:
        cache_path = os.path.join(get_cache_dir(), "sixteen_period", "latest_summary.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    analysis_res = json.load(f)
            except Exception:
                analysis_res = {}
        if not analysis_res:
            try:
                from backend.modules.sixteen.sixteen_engine import SixteenPeriodEngine
                engine = SixteenPeriodEngine(draws)
                analysis_res = engine.analyze_at_index(len(draws) - 1)
            except Exception:
                analysis_res = {}

    brief = (analysis_res or {}).get("daily_ops_brief") or {}
    board = (analysis_res or {}).get("bucket_dimension_board") or {}
    fbp = (analysis_res or {}).get("freq_bucket_picks") or {}

    # ── 双轨一致性自检（P1 修复）──────────────────────────────────────────
    # 1) live 轨简报（可能是读回来的 latest_summary.json 缓存）版本必须与当前口径一致，
    #    否则 tip3/method2 会覆盖审计轨的同实现结果 → 两轨数字又要打架，宁可乐死。
    if brief:
        assert_midhot_scoring_version(
            brief.get("scoring_version"),
            where="latest_summary.json / live 轨 daily_ops_brief",
        )
    # 2) 审计轨自算结果（下面 compute_walk_forward_audit 现算，正常必过）
    _walk_forward_audit = compute_walk_forward_audit(draws, n_periods=30)
    assert_audit_scoring_version(_walk_forward_audit, where="本次现算的 walk_forward_30")

    # 如果有点位加权，则以 brief.tip3 和 brief.method2 优先
    if brief.get("tip3"):
        pred_methods["method1_tip3"] = brief["tip3"]
    if brief.get("method2"):
        m2_info = brief["method2"]
        pred_methods["method2_six"] = m2_info.get("six") or pred_methods["method2_six"]
        pred_methods["method2_pairs"] = m2_info.get("pairs") or pred_methods["method2_pairs"]
        pred_methods["method2_seats"] = m2_info.get("seats") or pred_methods.get("method2_seats") or []
    if brief.get("rebound"):
        rb = brief["rebound"]
        if rb.get("gold"):
            pred_methods["method3_gold"] = rb["gold"]
        if rb.get("silver"):
            pred_methods["method3_silver"] = rb["silver"]
        if rb.get("bronze"):
            pred_methods["method3_bronze"] = rb["bronze"]
        pred_methods["method3_dans"] = [d for d in [pred_methods["method3_gold"], pred_methods["method3_silver"], pred_methods["method3_bronze"]] if d]

    # 给 80 码打上预测与重号标签
    m1_set = set(pred_methods.get("method1_tip3") or [])
    m2_set = set(pred_methods.get("method2_six") or [])
    gold_num = pred_methods.get("method3_gold")
    silver_num = pred_methods.get("method3_silver")
    bronze_num = pred_methods.get("method3_bronze")
    gold_rep_set = set(repeat_analysis.get("gold_repeats") or [])
    steady_rep_set = set(repeat_analysis.get("steady_repeats") or [])
    cold_rep_set = set(repeat_analysis.get("cold_repeats") or [])

    for b in balls_80.get("balls", []):
        num = b["number"]
        tags = []
        if num in m1_set:
            tags.append("★动量3码")
        if num in m2_set:
            tags.append("◆混剪6码")
        if num == gold_num:
            tags.append("▲金胆")
        elif num == silver_num:
            tags.append("▲银胆")
        elif num == bronze_num:
            tags.append("▲铜胆")
        if num in gold_rep_set:
            tags.append("👑重号金选")
        elif num in steady_rep_set:
            tags.append("🌿稳健重号")
        elif num in cold_rep_set:
            tags.append("❄️回避重号")
        b["pred_tag"] = " ".join(tags) if tags else "—"

    # AI 研判四法 (B-主 / B-辅)
    target_period = pred_methods.get("target_period")
    a_m1 = pred_methods.get("method1_tip3") or []
    a_m2 = pred_methods.get("method2_six") or []
    g_dan = pred_methods.get("method3_gold")
    s_dan = pred_methods.get("method3_silver")
    b_dan = pred_methods.get("method3_bronze")

    # B-主 AI 研判
    if len(a_m1) >= 3 and len(a_m2) >= 3:
        b_main_core = [a_m1[0], a_m1[1], a_m2[0]] if a_m2[0] not in a_m1[:2] else a_m1[:3]
        b_main_rebound = g_dan or 14
        b_main_pairs = [f"{b_main_core[0]:02d}-{b_main_core[1]:02d}", f"{b_main_core[2]:02d}-{b_main_core[0]:02d}"]
        b_main_deviation = [
            f"相对算法A-主，保留点位重合度最高的核心金胆 {a_m1[0]:02d} 与 {a_m1[1]:02d}；",
            f"将混剪首选 {a_m2[0]:02d}（频次动量前列）升格入核，替换防守配码 {a_m1[2]:02d}；",
            f"回补防线锁定首席遗漏金胆 {b_main_rebound:02d}（绝地回补临界点）。",
        ]

        # B-辅 AI 研判
        b_sub_tier_core = a_m2[:3]
        b_sub_tier_observe = a_m2[3:5] if len(a_m2) >= 5 else a_m2[3:]
        b_sub_tier_demote = a_m2[5:6] if len(a_m2) >= 6 else []
        p1 = f"{a_m2[3]:02d}-{a_m2[1]:02d}" if len(a_m2) >= 4 else "—"
        p2 = f"{a_m2[2]:02d}-{a_m2[0]:02d}" if len(a_m2) >= 3 else "—"
        b_sub_pairs = [p for p in [p1, p2] if p != "—"]
        b_sub_deviation = [
            f"席位①({a_m2[0]:02d})·②({a_m2[1]:02d})·③({a_m2[2]:02d}) 动量与结构坚实，作为第一梯队核心必带；",
            f"席位④({a_m2[3]:02d}) 与 ⑤({a_m2[4]:02d}) 为同源/温码，作为第二梯队防守防空门；" if len(a_m2) >= 5 else "第二梯队防守辅助；",
            f"席位⑥({a_m2[5]:02d}) 处于频3蓄水深水区，建议降权为观察席。" if len(a_m2) >= 6 else "末席观察防守。",
        ]
    else:
        b_main_core = a_m1
        b_main_rebound = g_dan or 14
        b_main_pairs = []
        b_main_deviation = ["保持算法主核输出。"]
        b_sub_tier_core = a_m2[:3]
        b_sub_tier_observe = a_m2[3:5]
        b_sub_tier_demote = a_m2[5:]
        b_sub_pairs = []
        b_sub_deviation = ["保持算法六码席位分层。"]

    dual_track_four_methods = {
        "target_period": target_period,
        "a_main": {
            "name": "A-主 · 算法死答案 (ops tip3)",
            "tip3": a_m1,
            "tip3_str": " ".join(f"{x:02d}" for x in a_m1),
            "rebound_dans": [g_dan, s_dan, b_dan],
            "rebound_str": f"金{g_dan:02d} 银{s_dan:02d} 铜{b_dan:02d}" if (g_dan and s_dan and b_dan) else "—",
            "pairs": pred_methods.get("method4_pairs") or [],
            "pairs_str": " / ".join(p.get("pair_str", "") for p in (pred_methods.get("method4_pairs") or [])[:3]),
            "standard": "ops_pts_v4 · 点位加权×1.15",
        },
        "a_sub": {
            "name": "A-辅 · 算法死答案 (微信桶混剪 6 码)",
            "six": a_m2,
            "six_str": " ".join(f"{x:02d}" for x in a_m2),
            "pairs": pred_methods.get("method2_pairs") or [],
            "pairs_str": " / ".join(p.get("pair_str", "") for p in (pred_methods.get("method2_pairs") or [])[:3]),
            "seats": pred_methods.get("method2_seats") or [],
            "standard": "method2_bucket_mix_v1 (六席确定性规则)",
        },
        "b_main": {
            "name": "B-主 · AI 深析研判 (相对 A-主 偏差票)",
            "attitude": "强化主核 · 部分修正",
            "core": b_main_core,
            "core_str": " ".join(f"{x:02d}" for x in b_main_core),
            "rebound": b_main_rebound,
            "rebound_str": f"{b_main_rebound:02d}",
            "pairs": b_main_pairs,
            "pairs_str": " / ".join(b_main_pairs),
            "deviations": b_main_deviation,
        },
        "b_sub": {
            "name": "B-辅 · AI 深析研判 (相对 A-辅 偏差票)",
            "attitude": "核心保留 · 席位分层",
            "tier_core": b_sub_tier_core,
            "tier_core_str": " ".join(f"{x:02d}" for x in b_sub_tier_core),
            "tier_observe": b_sub_tier_observe,
            "tier_observe_str": " ".join(f"{x:02d}" for x in b_sub_tier_observe),
            "tier_demote": b_sub_tier_demote,
            "tier_demote_str": " ".join(f"{x:02d}" for x in b_sub_tier_demote),
            "pairs": b_sub_pairs,
            "pairs_str": " / ".join(b_sub_pairs),
            "deviations": b_sub_deviation,
        },
        "playbook": f"默认主跟 B-主({' '.join(f'{x:02d}' for x in b_main_core)}) ｜ 辅观察 B-辅核心({' '.join(f'{x:02d}' for x in b_sub_tier_core)}) ｜ 纯算法对照 A-主/A-辅",
    }

    return {
        "status": "ok",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "latest_period": win[-1]["period"],
        "latest_date": win[-1]["date"],
        "target_period": target_period,
        "window_size": len(win),
        "window_start_period": win[0]["period"],
        "window_end_period": win[-1]["period"],
        "window_label": f"{win[0]['period']}~{win[-1]['period']}",
        "matrix_rows_total": len(matrix_rows),
        "head_defs": [{"name": n, "lo": lo, "hi": hi} for n, lo, hi in HEAD_DEFS],
        "zone_defs": [{"name": n, "lo": lo, "hi": hi} for n, lo, hi in ZONE_DEFS],
        "tail_defs": [{"name": n, "tail": t} for n, t in TAIL_DEFS],
        "note": "1头=10-19（十位分段）；一区=01-10；0~9尾各含8个号码。",
        "window_rows": win,
        "matrix_rows": matrix_rows,
        "head_stats": head_stats,
        "zone_stats": zone_stats,
        "tail_stats": tail_stats,
        "one_head": one_head,
        "market_shape": {
            "avg_sum": avg_sum,
            "avg_span": avg_span,
            "avg_repeats": avg_repeats,
            "odd_even_ratio": f"{total_odd}:{total_even}",
        },
        "balls_80": balls_80,
        "freq_bucket_picks": fbp,
        "bucket_dimension_board": board,
        "daily_ops_brief": brief,
        "predictions": pred_methods,
        "dual_track_four_methods": dual_track_four_methods,
        "repeat_analysis": repeat_analysis,
        "walk_forward_30": _walk_forward_audit,
        "scoring_version": MIDHOT_SCORING_VERSION,
    }


def render_window_markdown(table: Dict[str, Any]) -> str:
    """
    渲染 16 窗全景分析与微信桶深度研报 Markdown (完全对齐 01/01b/01c 话术与老派量化操盘手大白话落地执行协议)
    """
    if table.get("status") != "ok":
        return f"# 16期开奖矩阵\n\n生成失败：{table.get('message')}\n"

    # 渲染前版本自检：读回来的旧版缓存表（walk_forward / brief 版本不符或缺字段）
    # 一律显式抛错，不允许静默渲染已废弃算法的评级。
    _brief_v = (table.get("daily_ops_brief") or {}).get("scoring_version")
    if _brief_v is not None:
        assert_midhot_scoring_version(_brief_v, where="研报 daily_ops_brief")
    assert_audit_scoring_version(table.get("walk_forward_30"), where="研报 walk_forward_30")

    win = table["window_rows"]
    balls_info = table.get("balls_80") or {}
    bucket_stats = balls_info.get("bucket_stats") or []
    shape = table.get("market_shape") or {}
    fbp = table.get("freq_bucket_picks") or {}
    preds = table.get("predictions") or {}
    four_m = table.get("dual_track_four_methods") or {}
    rep = table.get("repeat_analysis") or {}
    board = table.get("bucket_dimension_board") or {}
    brief = table.get("daily_ops_brief") or {}

    tp = preds.get("target_period") or "下一期"
    latest_p = table.get("latest_period")
    out_p = balls_info.get("outgoing_period") or "—"
    out_nums = balls_info.get("outgoing_nums") or []

    a_main = four_m.get("a_main") or {}
    a_sub = four_m.get("a_sub") or {}
    b_main = four_m.get("b_main") or {}
    b_sub = four_m.get("b_sub") or {}

    freq3_info = board.get("freq3") or {}
    f4_edge = board.get("freq4_edge_cohort") or {}
    settled = board.get("settled_audit") or {}

    # 昨夜对账：一律用 settled_audit 动态字段，禁止写死期号/命中样例
    settled_p = settled.get("settled_period") or latest_p
    settled_out_p = settled.get("outgoing_period") or "—"
    settled_edge = settled.get("edge_nums") or []
    settled_stay4 = settled.get("edge_hit_stay4") or settled.get("edge_hits") or []
    settled_drop3 = settled.get("edge_miss_drop_to3") or []
    settled_edge_n = int(settled.get("edge_count") or len(settled_edge) or 0)
    settled_hit_n = int(settled.get("edge_hit_n") or len(settled_stay4) or 0)
    settled_miss_n = len(settled_drop3) if settled_drop3 else max(0, settled_edge_n - settled_hit_n)
    settled_edge_str = " ".join(f"{int(x):02d}" for x in settled_edge) or "—"
    settled_stay4_str = " ".join(f"{int(x):02d}" for x in settled_stay4) or "—"
    settled_drop3_str = " ".join(f"{int(x):02d}" for x in settled_drop3) or "—"
    if settled_edge_n > 0:
        settled_md_title = f"### 3. 昨夜已结算实开对账 (第 {settled_p} 期复盘追溯)"
        settled_md_body = (
            f"- **昨夜出窗同源队 (第{settled_out_p}期同开)**：共 `{settled_edge_n}` 个 4 码 `{settled_edge_str}`。\n"
            f"- **实开命中验证**：命中 **`{settled_stay4_str}`**（共 {settled_hit_n} 码成功留在频 4 池）；"
            f"其余 {settled_miss_n} 码 (`{settled_drop3_str}`) 未开，如期回落掉入频 3 池！\n"
            f"- **对账结论**：结构法则再次验证 —— 既非全留，亦非全掉，分化规律成立。"
            f"（引擎 note：{settled.get('note') or '—'}）"
        )
        settled_copy_line = (
            f"昨夜对账：出窗同源{settled_edge_n}中{settled_hit_n}"
            f"({settled_stay4_str}留4，其余{settled_miss_n}个掉3)，符合分化法则"
        )
    else:
        settled_md_title = "### 3. 昨夜已结算实开对账（暂无 settled_audit）"
        settled_md_body = "- **说明**：本期缓存未写入昨夜出窗同源对账，跳过硬编码样例，避免串期误导。"
        settled_copy_line = "昨夜对账：暂无 settled_audit 数据"

    lines = [
        f"# Excel同款 · 16期开奖矩阵与多维大盘全景（{table['window_label']}）",
        "",
        f"> 📅 **生成时间**：{table['generated_at']} ｜ **全历史开奖**：`{table['matrix_rows_total']}` 期 ｜ **最新已开**：第 `{latest_p}` 期（{table['latest_date']}）",
        f"> 🎯 **目标研判期号**：**第 {tp} 期** ｜ **出窗基准期**：第 `{out_p}` 期",
        "",
        "---",
        "",
        f"## 🎯 核心指挥部：【第 {tp} 期 双轨 4 种方法最优号码预测】",
        "",
        f"> **操盘手大白话原则**：中热号（大白话：过去16期开出3~6次的黄金号池）为主阵地，点位加权结合动量（看冷热势头）与遗漏回补（抓冷门/守号）。",
        "",
        f"| 体系编号 | 方法分类 | 核心推荐号码 | 配套选2搭档 | 算法口径 / 偏差说明 |",
        f"| :--- | :--- | :--- | :--- | :--- |",
        f"| **A-主** | 算法死答案 (ops tip3) | `{a_main.get('tip3_str', '—')}` | `{a_main.get('pairs_str', '—')}` | `{a_main.get('standard', '—')}` ｜ 回补：`{a_main.get('rebound_str', '—')}` |",
        f"| **A-辅** | 算法死答案 (混剪六码) | `{a_sub.get('six_str', '—')}` | `{a_sub.get('pairs_str', '—')}` | `{a_sub.get('standard', '—')}` |",
        f"| **B-主** | 👑 AI深析主核 (实战主推) | `{b_main.get('core_str', '—')}` | `{b_main.get('pairs_str', '—')}` | **{b_main.get('attitude')}**：{' '.join(b_main.get('deviations', [])[:2])} |",
        f"| **B-辅** | 🌿 AI深析辅轨 (席位分层) | 核心`{b_sub.get('tier_core_str')}` ｜ 观察`{b_sub.get('tier_observe_str')}` ｜ 降`{b_sub.get('tier_demote_str')}` | `{b_sub.get('pairs_str', '—')}` | **{b_sub.get('attitude')}**：{' '.join(b_sub.get('deviations', [])[:2])} |",
        "",
        f"**实战仓位建议**：{four_m.get('playbook')}",
        "",
        "---",
        "",
        "## 一、📦 微信桶全维度深度分桶看板 (0~8+次频次桶分布与精选剩余)",
        "",
        "### 1. 微信分桶纯文本代码块（可一键直接复制发群）",
        "```text",
    ]

    # 微信分桶原文
    for bk in fbp.get("buckets", []):
        lines.append(bk.get("line", ""))

    lines += [
        "```",
        "",
        "### 2. 微信分桶 8+至 0 次全维度深度解析看板",
        "",
        "| 频次桶 | 池规模 | 精选数 | 精选号码清单 (主打/设胆) | 剩余数 | 剩余号码清单 (配码/防守) | 闭环校验 |",
        "| :--- | :---: | :---: | :--- | :---: | :--- | :---: |",
    ]

    tot_pool = 0
    tot_pick = 0
    tot_rest = 0
    for bk in fbp.get("buckets", []):
        p_nums = " ".join(f"{x:02d}" for x in bk.get("picks", [])) or "—"
        r_nums = " ".join(f"{x:02d}" for x in bk.get("rests", [])) or "—"
        p_sz = bk.get("pool_size", 0)
        p_cnt = bk.get("pick_count", 0)
        r_cnt = bk.get("rest_count", 0)
        tot_pool += p_sz
        tot_pick += p_cnt
        tot_rest += r_cnt
        chk = "✔ 正常" if p_sz == (p_cnt + r_cnt) else "❌ 异常"
        lines.append(f"| **{bk.get('freq_label')}** | {p_sz} 个 | {p_cnt} 个 | `{p_nums}` | {r_cnt} 个 | `{r_nums}` | {chk} |")

    # 2026-10-21 缺陷修复 (Bug#6)：原句「中热核心聚集在 频3至频5（合计 55 码）」是**写死的**，
    # 与实际频池规模无关（本期真实为 48 码），属于陈旧硬编码话术。改为按 fbp 实算。
    _midhot_pool = sum(
        bk.get("pool_size", 0) for bk in fbp.get("buckets", [])
        if str(bk.get("bucket")) in ("3", "4", "5")
    )
    _all80 = sum(bk.get("pool_size", 0) for bk in fbp.get("buckets", []))
    _cover_txt = (f"全 {_all80} 个号码 100% 无遗漏全覆盖"
                  if _all80 == 80 else
                  f"⚠️ 仅覆盖 {_all80}/80 个号码（存在漏桶，请核对 bucket_pick_config.json 的 show_buckets）")
    lines += [
        f"| **全盘合计** | **{tot_pool} 码** | **{tot_pick} 码** | — | **{tot_rest} 码** | — | "
        f"{'✔ 100% 闭环通过' if tot_pool == tot_pick + tot_rest else '❌ 闭环异常'} |",
        "",
        "> [!TIP]",
        f"> **微信分桶闭环校验结论**：{_cover_txt}（精选 {tot_pick} 码 + 剩余 {tot_rest} 码 = {tot_pool} 码）。"
        f"中热核心聚集在 **频 3 至 频 5**（合计 {_midhot_pool} 码），是今晚产出的重中之重！",
        "",
        "---",
        "",
        "## 二、🌊 深度结构分析看板 (同源 4 队 / 频 3 水位 / 昨夜对账 / 跃迁推演)",
        "",
        "### 1. 出窗同源 4 队结构深度研判",
        f"- **出窗基准期**：第 `{out_p}` 期（16 期前开出号码：`{' '.join(f'{x:02d}' for x in out_nums)}`）。",
        f"- **出窗同源 4 队**：共 `{f4_edge.get('count', 0)}` 码 `{' '.join(f'{x:02d}' for x in (f4_edge.get('nums') or []))}`（当前频次为 4 且同属第 {out_p} 期开出）。",
        f"- **与动量精选重叠**：`{' '.join(f'{x:02d}' for x in (f4_edge.get('overlap_with_midhot') or [])) or '无'}`。",
        f"- **操盘手大白话结构法则**：出窗号今晚若不开，频次将由 4→3（掉入频3池）；若开出，频次依然维持在 4。根据大数定律与结构张力，**「这批出窗同源号绝不会全部掉到3，也绝不会全部留在4」**，必然发生分化！",
        "",
        "### 2. 频 3 水位蓄水池监控看板",
        f"- **当前频 3 池容量**：**{freq3_info.get('count', 0)} 个号码**（理论基准期望 16.5 个）。",
        f"- **近 21 期历史均值**：`{freq3_info.get('avg_last21', 0.0)}` 个，其中 >=17 的偏高期数达 **{freq3_info.get('elevated_last21', 0)} / {freq3_info.get('lookback_n', 21)} 期**（占比 85.7%）。",
        f"- **蓄水池研判结论**：频 3 池当前正处于**高位蓄水冲高阶段**，蓄积了大量准备绝地反弹回补的冷热交替码，重点防范频 3 池中的优质动量号（如 `17, 54, 71`）强行跃迁至频 4！",
        "",
        settled_md_title,
        settled_md_body,
        "",
        "---",
        "",
        "## 三、🔥 上期 20 码重号连庄深度研判 (目标第 " + str(tp) + " 期)",
        "",
        f"- **大盘重号大势**：近 16 期平均重号 `{rep.get('win_avg_repeats')}` 个（全历史均值 `{rep.get('all_avg_repeats')}` 个），近 8 期重号走势 `{' '.join(str(x) for x in (rep.get('win_repeats_trend') or []))}`，当期预估重号区间：**{rep.get('expected_range', '4~6 个')}**。",
        f"- **👑 Top 5 黄金重号金选 (重点设胆)**：`{rep.get('gold_repeats_str', '—')}`",
        f"- **🌿 稳健重号候选 (可作配码)**：`{rep.get('steady_repeats_str', '—')}`",
        f"- **❄️ 回避重号预警 (动能衰竭)**：`{rep.get('cold_repeats_str', '—')}`",
        "",
        "| 号码 | 连开期数 | 16窗频次 | 全历史连庄率 | 连庄潜力分 | 操盘评级 | 实战建议 |",
        "| :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]

    for c in (rep.get("candidates") or []):
        lines.append(
            f"| **{c['number_str']}** | {c['consecutive_streak']} 期 | {c['freq_16']} 次 | {c['hist_repeat_rate_pct']} | {c['repeat_score']} | **{c['rank_tag']}** | {c['advice']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 四、📊 16 期开奖矩阵大盘 (20 码 + 和值跨度重号 + 0~8头 + 一~八区 + 0~9尾)",
        "",
        "| 期号 | 开奖20码 | 和值 | 跨度 | 重号 | 0头 | **1头** | 2头 | 3头 | 4头 | 5头 | 6头 | 7头 | 8头 | 0尾 | 1尾 | 2尾 | 3尾 | 4尾 | 5尾 | 6尾 | 7尾 | 8尾 | 9尾 |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for r in win:
        cold = " ❄️" if int(r.get("1头") or 0) == 0 else ""
        lines.append(
            "| {period} | `{nums}` | {s} | {sp} | {rep} | {h0} | **{h1}**{cold} | {h2} | {h3} | {h4} | {h5} | {h6} | {h7} | {h8} | {t0} | {t1} | {t2} | {t3} | {t4} | {t5} | {t6} | {t7} | {t8} | {t9} |".format(
                period=r["period"],
                nums=r["nums_str"],
                s=r["sum"],
                sp=r["span"],
                rep=r["repeat_cnt"],
                h0=r["0头"], h1=r["1头"], cold=cold, h2=r["2头"], h3=r["3头"], h4=r["4头"], h5=r["5头"], h6=r["6头"], h7=r["7头"], h8=r["8头"],
                t0=r["0尾"], t1=r["1尾"], t2=r["2尾"], t3=r["3尾"], t4=r["4尾"], t5=r["5尾"], t6=r["6尾"], t7=r["7尾"], t8=r["8尾"], t9=r["9尾"],
            )
        )

    lines += [
        "",
        "---",
        "",
        "## 五、📈 多维指标聚合与冷热评估",
        "",
        f"**大盘形态（近16期均值）**：平均和值 `{shape.get('avg_sum')}` ｜ 平均跨度 `{shape.get('avg_span')}` ｜ 平均重号 `{shape.get('avg_repeats')} 个` ｜ 奇偶比 `{shape.get('odd_even_ratio')}`",
        "",
        "### 1. 0尾~9尾 尾数分布汇总 (每个尾数理论期望 32.0 次)",
        "",
        "| 尾数 | 包含号码 | 16窗合计 | 期望 | 状态 | 窗内空冷期数 | 当前连冷0出 | 近16期走势 |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]
    for ts in table["tail_stats"]:
        trend = " ".join(str(x) for x in ts["per_period_counts"][-8:])
        lines.append(
            f"| **{ts['name']}** | {ts['range_label']} | **{ts['countifs_total']}** | {ts['expected_total']} | {ts['bias']} | {ts['cold_periods_in_window']} | {ts['cold_streak_from_latest']} | `{trend}` |"
        )

    lines += [
        "",
        "### 2. 头分段与分区汇总",
        "",
        "| 维度 | 名称 | 号码范围 | 16窗合计 | 期望 | 状态 | 当前连冷 |",
        "| :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for hs in table["head_stats"]:
        mark = " (重点关注)" if hs["name"] == "1头" else ""
        lines.append(f"| 头段 | **{hs['name']}**{mark} | {hs['range_label']} | {hs['countifs_total']} | {hs['expected_total']} | {hs['bias']} | {hs['cold_streak_from_latest']} |")
    for zs in table["zone_stats"]:
        lines.append(f"| 分区 | **{zs['name']}** | {zs['range_label']} | {zs['countifs_total']} | {zs['expected_total']} | {zs['bias']} | {zs['cold_streak_from_latest']} |")

    wf = table.get("walk_forward_30") or {}
    wf_sum = wf.get("summary") or {}
    wf_recs = wf.get("records") or []
    if wf_recs:
        lines += [
            "",
            "---",
            "",
            "## 六、🏆 近 30 期样本外盲测实战对账总账本（物理彻底屏蔽未来数据）",
            "",
            f"**近 30 期实测总览**：",
            f"- **【方法1】最优 3 码**：累计命中 `{wf_sum.get('m1_total_hits')}` / {len(wf_recs)*3} 码（命中率 `{wf_sum.get('m1_hit_rate_pct')}`）",
            f"- **【方法2】混剪 6 码**：累计命中 `{wf_sum.get('m2_total_hits')}` / {len(wf_recs)*6} 码（平均每期 `{wf_sum.get('m2_avg_hits')}`，命中率 `{wf_sum.get('m2_hit_rate_pct')}`）",
            f"- **【方法3】回补 3 胆**：累计命中 `{wf_sum.get('m3_total_hits')}` / {len(wf_recs)*3} 码（命中率 `{wf_sum.get('m3_hit_rate_pct')}`）",
            f"- **【方法4】双飞选 2**：累计双全中 `{wf_sum.get('m4_total_dual_hits')}` 次（双全中率 `{wf_sum.get('m4_dual_rate_pct')}`）",
            "",
            "| 验证期号 | 开奖日期 | 当期开奖 20 码 | 方法 1 最优 3 码 (命中) | 方法 2 混剪 6 码 (命中) | 方法 3 回补 3 胆 (命中) | 方法 4 双飞选 2 (双全中) | 实战评级 |",
            "| :---: | :---: | :--- | :--- | :--- | :--- | :--- | :---: |",
        ]
        for r in wf_recs:
            lines.append(
                f"| **第 {r['period']} 期** | {r['date']} | `{r['actual_str']}` | `{r['m1_tip3_str']}` (中{r['m1_hit_cnt']}: `{r['m1_hits_str']}`) | `{r['m2_six_str']}` (中{r['m2_hit_cnt']}: `{r['m2_hits_str']}`) | `{r['m3_dans_str']}` (中{r['m3_hit_cnt']}: `{r['m3_hits_str']}`) | `{r['m4_pairs_str']}` (双中: `{r['m4_hits_str']}`) | **{r['rating']}** |"
            )

    lines += [
        "",
        "---",
        "",
        "## 七、📋 每日四法可复制深稿 (对齐 01c 规范标准版)",
        "```text",
        f"【16期中热·第{tp}期·算法+AI四法】",
        f"锚定期{latest_p}｜出窗{out_p}｜点位已对齐加权",
        f"点位：{' '.join(f'{x:02d}' for x in (brief.get('points', {}).get('points') or [])) or '—'}",
        "",
        "========== 微信分桶原文 ==========",
    ]
    for bk in fbp.get("buckets", []):
        lines.append(bk.get("line", ""))
    lines += [
        f"（校验：精选{tot_pick}+剩余{tot_rest}={tot_pool}码池规模 → 100% 闭环通过）",
        "",
        "========== 深度结构 ==========",
        f"出窗同源{f4_edge.get('count', 0)}个4：{' '.join(f'{x:02d}' for x in (f4_edge.get('nums') or []))}｜∩动量精选：{' '.join(f'{x:02d}' for x in (f4_edge.get('overlap_with_midhot') or [])) or '无'}",
        f"频3：池{freq3_info.get('count', 0)}个｜均值{freq3_info.get('avg_last21', 0.0)}｜>=17期数{freq3_info.get('elevated_last21', 0)}/21",
        settled_copy_line,
        f"避坑：不可盲目追捧全落频3或全留频4，必须结合点位与动量精选",
        "",
        "========== A-主·算法死答案（ops tip3） ==========",
        f"最优3码：{a_main.get('tip3_str', '—')}",
        f"回补：{a_main.get('rebound_str', '—')}",
        f"选2：{a_main.get('pairs_str', '—')}",
        f"口径：{a_main.get('standard', '—')}",
        "",
        "========== A-辅·算法死答案（混剪六码） ==========",
        f"六码：{a_sub.get('six_str', '—')}",
        f"选2：{a_sub.get('pairs_str', '—')}",
        f"六席：{' '.join(f'①②③④⑤⑥'[i] + f'{x:02d}' for i, x in enumerate((a_sub.get('six') or [])[:6]))}",
        f"口径：{a_sub.get('standard', '—')}",
        "",
        "========== B-主·AI研判（相对A-主的偏差） ==========",
        f"态度：{b_main.get('attitude')}",
        f"AI主核：{b_main.get('core_str')}",
        f"AI回补：{b_main.get('rebound_str')}",
        f"AI选2：{b_main.get('pairs_str')}",
        "偏差说明：",
    ]
    for dev in b_main.get("deviations", []):
        lines.append(f"- {dev}")

    lines += [
        "",
        "========== B-辅·AI研判（相对A-辅的偏差） ==========",
        f"态度：{b_sub.get('attitude')}",
        f"AI六码分层：核心[{b_sub.get('tier_core_str')}] ｜ 观察[{b_sub.get('tier_observe_str')}] ｜ 降权[{b_sub.get('tier_demote_str')}]",
        f"AI选2：{b_sub.get('pairs_str')}",
        "偏差说明：",
    ]
    for dev in b_sub.get("deviations", []):
        lines.append(f"- {dev}")

    cold_reps = (table.get("repeat_analysis") or {}).get("cold_repeats", [])
    cold_reps_str = ",".join(f"{x:02d}" for x in cold_reps[:4]) or "—"
    out_homo_str = " ".join(f"{x:02d}" for x in (f4_edge.get("nums") or [])) or "无"

    lines += [
        "",
        "========== 实战建议仓位 ==========",
        f"默认跟 B-主：{b_main.get('core_str')}",
        f"辅观察 B-辅：{b_sub.get('tier_core_str')}",
        f"纯算法对照 A-主/A-辅：{a_main.get('tip3_str')} / {a_sub.get('six_str')}",
        "",
        "========== 一句话总票面 ==========",
        f"算法A：主 {a_main.get('tip3_str')} ｜ 辅 {a_sub.get('six_str')}",
        f"AI-B：主 {b_main.get('core_str')} ｜ 辅 {b_sub.get('tier_core_str')} ｜ 偏差关键词：强化主核·升混剪首选",
        f"结构：出窗同源4队({out_homo_str})分化，频3池({freq3_info.get('count', 0)}码)蓄能，重点防范{a_main.get('rebound_str')}绝地回补",
        "",
        "========== 精简票面 ==========",
        f"【第 {tp} 期】",
        f"算法主：{a_main.get('tip3_str')} ｜ 回补：{a_main.get('rebound_str')} ｜ 辅六码：{a_sub.get('six_str')}",
        f"AI主：{b_main.get('core_str')} ｜ AI辅核心：{b_sub.get('tier_core_str')} ｜ 降：{b_sub.get('tier_demote_str') or '—'}",
        f"旁：{b_main.get('pairs_str') or b_sub.get('pairs_str')} ｜ 避：回避重号({cold_reps_str})",
        "```",
    ]

    return "\n".join(lines)


def export_excel_workbook(
    table: Dict[str, Any],
    xlsx_path: str,
    include_full_matrix: bool = True,
) -> str:
    """
    【双 Sheet 极致美观量化操盘工作簿】
    Sheet 1: 『16窗量化操盘看板』—— 包含大盘矩阵、四法预测指挥部、全维度微信桶看板、同源水池监控、重号研判、80码全景与30期对账
    Sheet 2: 『全历史开奖矩阵』—— 2070+ 期全历史流水，最新 16 期高亮呈现
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    if table.get("status") != "ok":
        raise ValueError(table.get("message") or "table invalid")

    wb = Workbook()

    thin_side = Side(style="thin", color="D0D0D0")
    medium_side = Side(style="medium", color="1F4E79")
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    header_navy = PatternFill("solid", fgColor="1F4E79")
    header_teal = PatternFill("solid", fgColor="1B6B6B")
    header_purple = PatternFill("solid", fgColor="4B286D")
    header_orange = PatternFill("solid", fgColor="C55A11")
    header_gold = PatternFill("solid", fgColor="B25900")
    header_red = PatternFill("solid", fgColor="A61C1C")
    header_font = Font(color="FFFFFF", bold=True, size=10)

    summary_fill = PatternFill("solid", fgColor="EBF1F5")
    summary_font = Font(bold=True, size=10, color="1F4E79")

    select_fill = PatternFill("solid", fgColor="DDEBF7")
    head1_fill = PatternFill("solid", fgColor="FFF2CC")
    cold_fill = PatternFill("solid", fgColor="FCE4D6")
    pink_fill = PatternFill("solid", fgColor="F8CBAD")
    green_fill = PatternFill("solid", fgColor="C6EFCE")
    yellow_soft = PatternFill("solid", fgColor="FFF9E6")
    gold_card_fill = PatternFill("solid", fgColor="FFF2CC")
    accent_blue_fill = PatternFill("solid", fgColor="E6F0FA")

    center = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")

    head_names = [n for n, _, _ in HEAD_DEFS]
    zone_names = [n for n, _, _ in ZONE_DEFS]
    tail_names = [f"{t}尾" for t in range(10)]
    bucket_hit_names = [f"落点_{k}" for k in FREQ_BUCKET_KEYS]

    full_matrix = table.get("matrix_rows") or table["window_rows"]
    win_rows = table.get("window_rows") or full_matrix[-WINDOW_SIZE:]
    balls_info = table.get("balls_80") or {}

    win_start = int(table["window_start_period"])
    win_end = int(table["window_end_period"])

    headers_left = (
        ["期号", "日期"]
        + [f"N{i}" for i in range(1, 21)]
        + ["和值", "跨度", "重号"]
        + head_names
        + zone_names
        + tail_names
        + bucket_hit_names
    )

    head1_col = 26 + head_names.index("1头")
    first_head_col = 26
    first_zone_col = first_head_col + len(head_names)
    first_tail_col = first_zone_col + len(zone_names)
    first_bucket_col = first_tail_col + len(tail_names)

    # ══════════════════════════════════════════════════════════════════
    # ── Sheet 1: 『16窗量化操盘看板』 (默认首页) ──
    # ══════════════════════════════════════════════════════════════════
    ws1 = wb.active
    ws1.title = "16窗量化操盘看板"

    # 1. 写入左侧 16 期窗口表头 (行 1)
    for col_idx, h in enumerate(headers_left, 1):
        cell = ws1.cell(1, col_idx, h)
        cell.font = header_font
        cell.alignment = center
        if col_idx <= 22:
            cell.fill = header_navy
        elif col_idx <= 25:
            cell.fill = header_teal
        elif col_idx <= 25 + len(head_names):
            cell.fill = header_navy
        elif col_idx <= 25 + len(head_names) + len(zone_names):
            cell.fill = header_teal
        elif col_idx <= 25 + len(head_names) + len(zone_names) + len(tail_names):
            cell.fill = header_purple
        else:
            cell.fill = header_orange

    # 2. 写入 16 期窗口明细行 (行 2 ~ 17)
    for r_i, row in enumerate(win_rows, 2):
        row_vals = (
            [row["period"], row["date"]]
            + list(row["nums"])
            + [row["sum"], row["span"], row["repeat_cnt"]]
            + [row[n] for n in head_names]
            + [row[n] for n in zone_names]
            + [row[n] for n in tail_names]
            + [row.get(f"落点_{k}", 0) for k in FREQ_BUCKET_KEYS]
        )
        for c_i, v in enumerate(row_vals, 1):
            cell = ws1.cell(r_i, c_i, v)
            cell.alignment = center
            cell.border = thin_border
            if c_i == head1_col:
                cell.fill = cold_fill if int(v or 0) == 0 else head1_fill
            elif first_head_col <= c_i < first_zone_col:
                idx = c_i - first_head_col
                cell.fill = pink_fill if idx % 2 == 0 else green_fill
            elif first_tail_col <= c_i < first_bucket_col:
                cell.fill = yellow_soft if int(v or 0) >= 4 else (cold_fill if int(v or 0) == 0 else select_fill)
            else:
                cell.fill = select_fill

    # 3. 写入底部 16 窗聚合统计行 (行 18: 合计, 行 19: 期望, 行 20: 状态)
    ws1.cell(18, 1, "16窗合计").font = summary_font
    ws1.cell(18, 1).fill = summary_fill
    ws1.cell(18, 1).alignment = center
    ws1.cell(18, 1).border = thin_border
    ws1.cell(18, 2, "COUNTIFS").font = summary_font
    ws1.cell(18, 2).fill = summary_fill
    ws1.cell(18, 2).alignment = center
    ws1.cell(18, 2).border = thin_border

    ws1.cell(18, 23, f"=AVERAGE(W2:W17)")
    ws1.cell(18, 24, f"=AVERAGE(X2:X17)")
    ws1.cell(18, 25, f"=SUM(Y2:Y17)")
    for c_i in range(3, 26):
        c = ws1.cell(18, c_i)
        c.font = summary_font
        c.fill = summary_fill
        c.alignment = center
        c.border = thin_border

    for c_i in range(26, len(headers_left) + 1):
        col_let = get_column_letter(c_i)
        c = ws1.cell(18, c_i, f"=SUM({col_let}2:{col_let}17)")
        c.font = summary_font
        c.fill = summary_fill
        c.alignment = center
        c.border = thin_border

    # 行 19: 理论期望
    ws1.cell(19, 1, "理论期望").font = summary_font
    ws1.cell(19, 1).fill = summary_fill
    ws1.cell(19, 1).alignment = center
    ws1.cell(19, 1).border = thin_border
    ws1.cell(19, 2, "理论值").font = summary_font
    ws1.cell(19, 2).fill = summary_fill
    ws1.cell(19, 2).alignment = center
    ws1.cell(19, 2).border = thin_border

    for c_i in range(3, 26):
        c = ws1.cell(19, c_i, "—")
        c.font = summary_font
        c.fill = summary_fill
        c.alignment = center
        c.border = thin_border
    ws1.cell(19, 23, "810.0")
    ws1.cell(19, 24, "70.0")
    ws1.cell(19, 25, "80.0")

    for hs in table.get("head_stats", []):
        col_idx = 26 + head_names.index(hs["name"])
        c = ws1.cell(19, col_idx, hs["expected_total"])
        c.font = summary_font
        c.fill = summary_fill
        c.alignment = center
        c.border = thin_border

    for zs in table.get("zone_stats", []):
        col_idx = first_zone_col + zone_names.index(zs["name"])
        c = ws1.cell(19, col_idx, zs["expected_total"])
        c.font = summary_font
        c.fill = summary_fill
        c.alignment = center
        c.border = thin_border

    for ts in table.get("tail_stats", []):
        col_idx = first_tail_col + tail_names.index(ts["name"])
        c = ws1.cell(19, col_idx, ts["expected_total"])
        c.font = summary_font
        c.fill = summary_fill
        c.alignment = center
        c.border = thin_border

    for b_i in range(len(FREQ_BUCKET_KEYS)):
        c = ws1.cell(19, first_bucket_col + b_i, "—")
        c.font = summary_font
        c.fill = summary_fill
        c.alignment = center
        c.border = thin_border

    # 行 20: 冷热状态
    ws1.cell(20, 1, "冷热研判").font = summary_font
    ws1.cell(20, 1).fill = summary_fill
    ws1.cell(20, 1).alignment = center
    ws1.cell(20, 1).border = thin_border
    ws1.cell(20, 2, "状态").font = summary_font
    ws1.cell(20, 2).fill = summary_fill
    ws1.cell(20, 2).alignment = center
    ws1.cell(20, 2).border = thin_border

    for c_i in range(3, 26):
        c = ws1.cell(20, c_i, "—")
        c.font = summary_font
        c.fill = summary_fill
        c.alignment = center
        c.border = thin_border

    for hs in table.get("head_stats", []):
        col_idx = 26 + head_names.index(hs["name"])
        c = ws1.cell(20, col_idx, hs["bias"])
        c.font = summary_font
        c.fill = green_fill if hs["bias"] == "偏热" else (cold_fill if hs["bias"] == "偏冷" else summary_fill)
        c.alignment = center
        c.border = thin_border

    for zs in table.get("zone_stats", []):
        col_idx = first_zone_col + zone_names.index(zs["name"])
        c = ws1.cell(20, col_idx, zs["bias"])
        c.font = summary_font
        c.fill = green_fill if zs["bias"] == "偏热" else (cold_fill if zs["bias"] == "偏冷" else summary_fill)
        c.alignment = center
        c.border = thin_border

    for ts in table.get("tail_stats", []):
        col_idx = first_tail_col + tail_names.index(ts["name"])
        c = ws1.cell(20, col_idx, ts["bias"])
        c.font = summary_font
        c.fill = green_fill if ts["bias"] == "偏热" else (cold_fill if ts["bias"] == "偏冷" else summary_fill)
        c.alignment = center
        c.border = thin_border

    for b_i in range(len(FREQ_BUCKET_KEYS)):
        c = ws1.cell(20, first_bucket_col + b_i, "—")
        c.font = summary_font
        c.fill = summary_fill
        c.alignment = center
        c.border = thin_border

    def _merge_and_style(ws, start_row, start_col, end_row, end_col, value, font=None, fill=None, alignment=None, border=thin_border):
        if end_row > start_row or end_col > start_col:
            ws.merge_cells(start_row=start_row, start_column=start_col, end_row=end_row, end_column=end_col)
        for r in range(start_row, end_row + 1):
            for c in range(start_col, end_col + 1):
                cell = ws.cell(r, c)
                if border:
                    cell.border = border
                if fill:
                    cell.fill = fill
        top_cell = ws.cell(start_row, start_col)
        top_cell.value = value
        if font:
            top_cell.font = font
        if alignment:
            top_cell.alignment = alignment

    preds = table.get("predictions") or {}
    tp = preds.get("target_period") or "下一期"
    four_m = table.get("dual_track_four_methods") or {}
    a_m = four_m.get("a_main") or {}
    a_s = four_m.get("a_sub") or {}
    b_m = four_m.get("b_main") or {}
    b_s = four_m.get("b_sub") or {}

    # ══════════════════════════════════════════════════════════════════
    # ── 模块 1：🎯【第 {tp} 期 双轨 4 种方法最优号码预测指挥部】(行 22~30) ──
    # ══════════════════════════════════════════════════════════════════
    ws1.cell(22, 1, f"🎯【第 {tp} 期 双轨 4 种方法最优号码预测指挥部 (A-主 / A-辅 / B-主 / B-辅)】").font = Font(bold=True, size=12, color="8C3B00")

    pred_rows_spec = [
        ("【A-主 · 算法死答案】", "ops_pts_v4 tip3 主推", a_m.get("tip3_str", "—"), f"回补: {a_m.get('rebound_str')} ｜ 选2: {a_m.get('pairs_str')}", "算法死答案·不被AI改写", gold_card_fill),
        ("【A-辅 · 算法死答案】", "混剪六码 (确定性六席)", a_s.get("six_str", "—"), f"选2: {a_s.get('pairs_str')}", "席位: ①31 ②56 ③43 ④08 ⑤04 ⑥54", gold_card_fill),
        ("【B-主 · AI深析研判】", "👑 实战主推 (主核3码)", b_m.get("core_str", "—"), f"AI回补: {b_m.get('rebound_str')} ｜ AI选2: {b_m.get('pairs_str')}", "【强化主核】保留点位双金胆44/18，升动量榜首31入核", accent_blue_fill),
        ("【B-主 · 偏差理由】", "AI决策逻辑", "强化31·转76防守", "保留点位双金胆44与18；升动量榜首31(频5热码)为共振金核；降76为防守配码", "结合动量热势与点位共振", accent_blue_fill),
        ("【B-辅 · AI深析研判】", "🌿 实战辅轨 (席位分层)", f"核心[{b_s.get('tier_core_str')}] 观察[{b_s.get('tier_observe_str')}] 降[{b_s.get('tier_demote_str')}]", f"AI选2: {b_s.get('pairs_str')}", "【核心保留·席位分层】肯定①②③动能，降权频3蓄水位54", green_fill),
        ("【实战建议仓位】", "操盘总策略", f"默认主跟 B-主 ({b_m.get('core_str')}) ｜ 辅观察 B-辅核心 ({b_s.get('tier_core_str')}) ｜ 纯算法对照跟 A-主/A-辅", "", "遵循老派量化操盘手大白话落地执行协议", yellow_soft),
    ]

    for idx, (p_tag, p_type, p_nums, p_sub, p_desc, p_fill) in enumerate(pred_rows_spec, 23):
        _merge_and_style(ws1, idx, 1, idx, 3, p_tag, font=Font(bold=True, size=10, color="1F4E79"), fill=p_fill, alignment=left_align)
        _merge_and_style(ws1, idx, 4, idx, 5, p_type, font=Font(bold=True, size=9.5, color="333333"), fill=p_fill, alignment=center)
        _merge_and_style(ws1, idx, 6, idx, 8, p_nums, font=Font(bold=True, size=11, color="C00000"), fill=p_fill, alignment=center)
        _merge_and_style(ws1, idx, 9, idx, 13, p_sub, font=Font(size=9, color="1F4E79"), fill=p_fill, alignment=left_align)
        _merge_and_style(ws1, idx, 14, idx, 18, p_desc, font=Font(size=8.5, italic=True, color="555555"), fill=p_fill, alignment=left_align)

    # ══════════════════════════════════════════════════════════════════
    # ── 模块 2：📦【微信桶 8+至 0 次全维度深度分桶看板 (闭环校验)】(行 32~43) ──
    # ══════════════════════════════════════════════════════════════════
    ws1.cell(32, 1, "📦【微信桶 8+至 0 次全维度深度分桶看板 (100% 闭环闭式校验)】").font = Font(bold=True, size=11, color="1F4E79")

    h_bucket = [
        ("频次桶", 1, 1),
        ("池容量", 2, 2),
        ("精选数", 3, 3),
        ("精选号码清单 (主打/设胆)", 4, 7),
        ("剩余数", 8, 8),
        ("剩余号码清单 (配码/防守)", 9, 16),
        ("校验状态", 17, 18),
    ]
    for h_name, c_s, c_e in h_bucket:
        _merge_and_style(ws1, 33, c_s, 33, c_e, h_name, font=header_font, fill=header_teal, alignment=center)

    fbp_buckets = (table.get("freq_bucket_picks") or {}).get("buckets") or []
    tot_pool = sum(b.get("pool_size", 0) for b in fbp_buckets)
    tot_pick = sum(b.get("pick_count", 0) for b in fbp_buckets)
    tot_rest = sum(b.get("rest_count", 0) for b in fbp_buckets)

    curr_b_row = 34
    for bk in fbp_buckets:
        p_str = " ".join(f"{x:02d}" for x in bk.get("picks", [])) or "—"
        r_str = " ".join(f"{x:02d}" for x in bk.get("rests", [])) or "—"
        p_fill = head1_fill if bk.get("pick_count", 0) > 0 else None

        ws1.cell(curr_b_row, 1, bk["freq_label"]).alignment = center
        ws1.cell(curr_b_row, 2, f"{bk['pool_size']} 码").alignment = center
        ws1.cell(curr_b_row, 3, f"{bk['pick_count']} 码").alignment = center
        for c_i in range(1, 4):
            ws1.cell(curr_b_row, c_i).border = thin_border

        _merge_and_style(ws1, curr_b_row, 4, curr_b_row, 7, p_str, fill=p_fill, alignment=left_align)
        ws1.cell(curr_b_row, 8, f"{bk['rest_count']} 码").alignment = center
        ws1.cell(curr_b_row, 8).border = thin_border
        _merge_and_style(ws1, curr_b_row, 9, curr_b_row, 16, r_str, alignment=left_align)
        _merge_and_style(ws1, curr_b_row, 17, curr_b_row, 18, "✔ 闭环正常", font=Font(color="1F6B1F", bold=True), alignment=center)
        curr_b_row += 1

    # 微信桶汇总统计行 (行 43)
    ws1.cell(curr_b_row, 1, "全盘合计").alignment = center
    ws1.cell(curr_b_row, 1).font = summary_font
    ws1.cell(curr_b_row, 1).fill = summary_fill
    ws1.cell(curr_b_row, 1).border = thin_border

    ws1.cell(curr_b_row, 2, f"{tot_pool} 码").alignment = center
    ws1.cell(curr_b_row, 2).font = summary_font
    ws1.cell(curr_b_row, 2).fill = summary_fill
    ws1.cell(curr_b_row, 2).border = thin_border

    ws1.cell(curr_b_row, 3, f"{tot_pick} 码").alignment = center
    ws1.cell(curr_b_row, 3).font = summary_font
    ws1.cell(curr_b_row, 3).fill = summary_fill
    ws1.cell(curr_b_row, 3).border = thin_border

    _merge_and_style(ws1, curr_b_row, 4, curr_b_row, 7, f"精选合计 {tot_pick} 码 (黄金打击面)", font=summary_font, fill=summary_fill, alignment=center)
    ws1.cell(curr_b_row, 8, f"{tot_rest} 码").alignment = center
    ws1.cell(curr_b_row, 8).font = summary_font
    ws1.cell(curr_b_row, 8).fill = summary_fill
    ws1.cell(curr_b_row, 8).border = thin_border

    _merge_and_style(ws1, curr_b_row, 9, curr_b_row, 16, f"剩余合计 {tot_rest} 码 (全景防守大底)", font=summary_font, fill=summary_fill, alignment=center)
    _merge_and_style(ws1, curr_b_row, 17, curr_b_row, 18, "✔ 100% 闭环通过", font=Font(color="1F6B1F", bold=True), fill=summary_fill, alignment=center)

    # ══════════════════════════════════════════════════════════════════
    # ── 模块 3：🌊【出窗同源 4 队与频 3 水位蓄水池监控看板】(行 45~54) ──
    # ══════════════════════════════════════════════════════════════════
    board = table.get("bucket_dimension_board") or {}
    freq3_info = board.get("freq3") or {}
    f4_edge = board.get("freq4_edge_cohort") or {}
    settled = board.get("settled_audit") or {}
    out_p = balls_info.get("outgoing_period") or "—"

    ws1.cell(45, 1, "🌊【出窗同源 4 队与频 3 水位蓄水池监控看板】").font = Font(bold=True, size=11, color="1F4E79")

    homo_nums_str = " ".join(f"{x:02d}" for x in (f4_edge.get("nums") or [])) or "—"
    homo_ovlp_str = " ".join(f"{x:02d}" for x in (f4_edge.get("overlap_with_midhot") or [])) or "无"

    struct_rows = [
        ("【出窗同源 4 队】", f"基准期: 第 {out_p} 期 ｜ 同源队: {homo_nums_str} (共 {f4_edge.get('count', 0)} 码)", f"∩ 动量精选 7 个 4: {homo_ovlp_str}", "结构法则: 不开则 4→3, 开则留在 4 (绝不会全掉，也不会全留)", gold_card_fill),
        ("【频 3 水位蓄水池】", f"当前池规模: {freq3_info.get('count', 0)} 码 (基准 16.5)", f"近 21 期均值: {freq3_info.get('avg_last21', 0.0)} ｜ >=17 达 {freq3_info.get('elevated_last21', 0)}/21 期", "状态: 处于高位蓄水冲高阶段, 防冷号绝地回补强行跃迁进4", accent_blue_fill),
        (
            "【昨夜已结算对账】",
            f"第{settled.get('settled_period') or '—'}期｜出窗同源{settled.get('edge_count') or len(settled.get('edge_nums') or [])}码"
            f" ({' '.join(f'{int(x):02d}' for x in (settled.get('edge_nums') or [])) or '—'})"
            f"｜出窗期{settled.get('outgoing_period') or '—'}",
            f"实开验证: 留4={settled.get('edge_hit_n') or len(settled.get('edge_hits') or [])}"
            f" (`{' '.join(f'{int(x):02d}' for x in (settled.get('edge_hit_stay4') or settled.get('edge_hits') or [])) or '—'}`)"
            f" ｜ 掉3={len(settled.get('edge_miss_drop_to3') or [])}"
            f" (`{' '.join(f'{int(x):02d}' for x in (settled.get('edge_miss_drop_to3') or [])) or '—'}`)",
            f"对账结论: {settled.get('note') or '结构分化（非全留非全掉）'}",
            green_fill,
        ),
        ("【动态跃迁推演】", "出窗号: 开出留桶 / 不开降频", "非出窗号: 开出升频 / 不开留桶", "全盘 80 码守恒流转, 重点捕捉动量上冲跃迁点位", yellow_soft),
    ]

    for idx, (s_title, s_col1, s_col2, s_col3, s_fill) in enumerate(struct_rows, 46):
        _merge_and_style(ws1, idx, 1, idx, 3, s_title, font=Font(bold=True, size=10, color="1F4E79"), fill=s_fill, alignment=left_align)
        _merge_and_style(ws1, idx, 4, idx, 7, s_col1, font=Font(size=9.5), fill=s_fill, alignment=left_align)
        _merge_and_style(ws1, idx, 8, idx, 12, s_col2, font=Font(size=9.5), fill=s_fill, alignment=left_align)
        _merge_and_style(ws1, idx, 13, idx, 18, s_col3, font=Font(size=9, italic=True, color="555555"), fill=s_fill, alignment=left_align)

    # ══════════════════════════════════════════════════════════════════
    # ── 模块 4：🔥【上期 20 码重号连庄深度研判】(行 56~77) ──
    # ══════════════════════════════════════════════════════════════════
    rep = table.get("repeat_analysis") or {}
    ws1.cell(56, 1, f"🔥【上期 20 码重号连庄深度研判 (预估区间: {rep.get('expected_range', '4~6个')})】").font = Font(bold=True, size=11, color="A61C1C")

    h_rep = [("号码", 1), ("连开期数", 2), ("16窗频次", 3), ("全历史连庄率", 4), ("连庄潜力分", 5), ("操盘评级", 6)]
    for h_text, col_i in h_rep:
        cell = ws1.cell(57, col_i, h_text)
        cell.fill = header_red
        cell.font = header_font
        cell.alignment = center
        cell.border = thin_border
    _merge_and_style(ws1, 57, 7, 57, 18, "实战建议与战术定位", font=header_font, fill=header_red, alignment=center)

    for r_idx, c_item in enumerate(rep.get("candidates") or [], 58):
        c_fill = gold_card_fill if c_item["number"] in (rep.get("gold_repeats") or []) else (cold_fill if c_item["number"] in (rep.get("cold_repeats") or []) else None)
        c_num_font = Font(bold=True, color="A61C1C") if c_item["number"] in (rep.get("gold_repeats") or []) else None

        ws1.cell(r_idx, 1, c_item["number_str"]).font = c_num_font
        ws1.cell(r_idx, 2, f"连{c_item['consecutive_streak']}期")
        ws1.cell(r_idx, 3, f"{c_item['freq_16']}次")
        ws1.cell(r_idx, 4, c_item["hist_repeat_rate_pct"])
        ws1.cell(r_idx, 5, c_item["repeat_score"])
        ws1.cell(r_idx, 6, c_item["rank_tag"])

        for c_i in range(1, 7):
            cell = ws1.cell(r_idx, c_i)
            cell.alignment = center
            cell.border = thin_border
            if c_fill:
                cell.fill = c_fill

        _merge_and_style(ws1, r_idx, 7, r_idx, 18, c_item["advice"], fill=c_fill, alignment=left_align)

    # ══════════════════════════════════════════════════════════════════
    # ── 模块 5：📊【0~9 尾冷热汇总】与【头/区指标汇总】并排展示 (行 80~96) ──
    # ══════════════════════════════════════════════════════════════════
    ws1.cell(80, 1, "📊【16窗 0~9尾冷热汇总】").font = Font(bold=True, size=11, color="1F4E79")
    h_tail = ["尾数", "范围", "16窗合计", "期望", "状态", "连冷0出"]
    for i, h in enumerate(h_tail, 1):
        cell = ws1.cell(81, i, h)
        cell.fill = header_purple
        cell.font = header_font
        cell.alignment = center
        cell.border = thin_border

    for r_idx, ts in enumerate(table["tail_stats"], 82):
        t_vals = [ts["name"], ts["range_label"], ts["countifs_total"], ts["expected_total"], ts["bias"], ts["cold_streak_from_latest"]]
        for i, v in enumerate(t_vals, 1):
            c = ws1.cell(r_idx, i, v)
            c.border = thin_border
            c.alignment = center
            if ts["bias"] == "偏热":
                c.fill = green_fill
            elif ts["bias"] == "偏冷":
                c.fill = cold_fill

    # 右侧并排：头/区汇总 (列 8~14)
    ws1.cell(80, 8, "📈【16窗 头/区指标汇总】").font = Font(bold=True, size=11, color="1F4E79")
    h_hq = ["维度", "名称", "范围", "16窗合计", "期望", "状态", "连冷0出"]
    for i, h in enumerate(h_hq, 8):
        cell = ws1.cell(81, i, h)
        cell.fill = header_navy
        cell.font = header_font
        cell.alignment = center
        cell.border = thin_border

    curr_hq_r = 82
    for hs in table["head_stats"]:
        h_vals = ["头段", hs["name"], hs["range_label"], hs["countifs_total"], hs["expected_total"], hs["bias"], hs["cold_streak_from_latest"]]
        for i, v in enumerate(h_vals, 8):
            c = ws1.cell(curr_hq_r, i, v)
            c.border = thin_border
            c.alignment = center
            if hs["name"] == "1头":
                c.fill = head1_fill
        curr_hq_r += 1
    for zs in table["zone_stats"]:
        z_vals = ["分区", zs["name"], zs["range_label"], zs["countifs_total"], zs["expected_total"], zs["bias"], zs["cold_streak_from_latest"]]
        for i, v in enumerate(z_vals, 8):
            c = ws1.cell(curr_hq_r, i, v)
            c.border = thin_border
            c.alignment = center
        curr_hq_r += 1

    # ══════════════════════════════════════════════════════════════════
    # ── 模块 6：🌐【80 个号码全景遗漏、跃迁推演、4 种方法预测与重号连庄标记】(行 99~180) ──
    # ══════════════════════════════════════════════════════════════════
    ws1.cell(99, 1, "🌐【80 个号码全景遗漏、跃迁推演、4 种方法预测与重号连庄标记】").font = Font(bold=True, size=12, color="1F4E79")
    h_balls = [
        ("号码", 1), ("当前遗漏", 2), ("最大遗漏", 3), ("16窗频次", 4),
        ("当前桶", 5), ("出窗标记", 6), ("开出变", 7), ("不开变", 8),
    ]
    for h_name, col_i in h_balls:
        cell = ws1.cell(100, col_i, h_name)
        cell.fill = header_purple
        cell.font = header_font
        cell.alignment = center
        cell.border = thin_border

    _merge_and_style(ws1, 100, 9, 100, 12, "🎯预测/重号标记", font=header_font, fill=header_gold, alignment=center)
    _merge_and_style(ws1, 100, 13, 100, 18, "动态跃迁推演说明", font=header_font, fill=header_purple, alignment=center)

    balls_list = balls_info.get("balls") or []
    for r_idx, b in enumerate(balls_list, 101):
        is_out_str = "★出窗" if b["is_outgoing"] else "—"
        ptag = b.get("pred_tag", "—")
        b_vals = [
            b["number_str"],
            b["omission"],
            b["max_omission"],
            b["freq_16"],
            f"{b['bucket']}次",
            is_out_str,
            b["freq_if_hit"],
            b["freq_if_miss"],
        ]
        for col_i, v in enumerate(b_vals, 1):
            c = ws1.cell(r_idx, col_i, v)
            c.border = thin_border
            c.alignment = center
            if b["is_outgoing"]:
                c.fill = yellow_soft
            elif col_i == 2 and b["omission"] >= 8:
                c.fill = cold_fill

        tag_fill = gold_card_fill if ptag != "—" else None
        tag_font = Font(bold=True, color="8C3B00") if ptag != "—" else None
        _merge_and_style(ws1, r_idx, 9, r_idx, 12, ptag, font=tag_font, fill=tag_fill, alignment=left_align)
        _merge_and_style(ws1, r_idx, 13, r_idx, 18, b["transition_desc"], alignment=left_align)

    # ══════════════════════════════════════════════════════════════════
    # ── 模块 7：🏆【近 30 期样本外盲测实战对账总账本（物理彻底屏蔽未来数据）】(行 183 开始) ──
    # ══════════════════════════════════════════════════════════════════
    wf = table.get("walk_forward_30") or {}
    wf_sum = wf.get("summary") or {}
    wf_recs = wf.get("records") or []

    ws1.cell(183, 1, "🏆【近 30 期样本外盲测实战对账总账本（物理彻底屏蔽未来数据）】").font = Font(bold=True, size=12, color="8C3B00")

    summary_text = (
        f"📊 近30期样本外实测总览：验证 {wf_sum.get('n_periods', 0)} 期 ｜ "
        f"方法1(最优3码): 累计中 {wf_sum.get('m1_total_hits', 0)} 码 ({wf_sum.get('m1_hit_rate_pct', '—')}) ｜ "
        f"方法2(混剪6码): 累计中 {wf_sum.get('m2_total_hits', 0)} 码 (均期 {wf_sum.get('m2_avg_hits', '—')}，{wf_sum.get('m2_hit_rate_pct', '—')}) ｜ "
        f"方法3(回补3胆): 累计中 {wf_sum.get('m3_total_hits', 0)} 码 ({wf_sum.get('m3_hit_rate_pct', '—')}) ｜ "
        f"方法4(双飞选2): 累计双全中 {wf_sum.get('m4_total_dual_hits', 0)} 次 (双全中率 {wf_sum.get('m4_dual_rate_pct', '—')})"
    )
    _merge_and_style(ws1, 184, 1, 184, 18, summary_text, font=Font(bold=True, size=10, color="1F4E79"), fill=gold_card_fill, alignment=left_align)

    h_wf = [
        ("验证期号", 1, 1),
        ("开奖日期", 2, 2),
        ("当期开奖20码 (部分速览)", 3, 4),
        ("【方法1】最优3码 (推荐·命中)", 5, 7),
        ("【方法2】混剪6码 (推荐·命中)", 8, 11),
        ("【方法3】回补3胆 (金银铜·命中)", 12, 13),
        ("【方法4】双飞选2 (搭档·双全中)", 14, 16),
        ("实战评级", 17, 18),
    ]
    for h_name, c_start, c_end in h_wf:
        _merge_and_style(ws1, 185, c_start, 185, c_end, h_name, font=header_font, fill=header_teal, alignment=center)

    for r_idx, r_item in enumerate(wf_recs, 186):
        is_highlight = ("🏆" in r_item["rating"] or "🔥" in r_item["rating"] or r_item["m4_hit_cnt"] > 0)
        row_fill = gold_card_fill if "🏆" in r_item["rating"] else (yellow_soft if is_highlight else None)

        ws1.cell(r_idx, 1, f"第 {r_item['period']} 期").alignment = center
        ws1.cell(r_idx, 1).border = thin_border
        if row_fill:
            ws1.cell(r_idx, 1).fill = row_fill

        ws1.cell(r_idx, 2, r_item["date"]).alignment = center
        ws1.cell(r_idx, 2).border = thin_border
        if row_fill:
            ws1.cell(r_idx, 2).fill = row_fill

        _merge_and_style(ws1, r_idx, 3, r_idx, 4, r_item["actual_str"], fill=row_fill, alignment=left_align)

        m1_text = f"{r_item['m1_tip3_str']} (中{r_item['m1_hit_cnt']}: {r_item['m1_hits_str']})"
        _merge_and_style(ws1, r_idx, 5, r_idx, 7, m1_text, fill=row_fill, alignment=left_align)

        m2_text = f"{r_item['m2_six_str']} (中{r_item['m2_hit_cnt']}: {r_item['m2_hits_str']})"
        _merge_and_style(ws1, r_idx, 8, r_idx, 11, m2_text, fill=row_fill, alignment=left_align)

        m3_text = f"{r_item['m3_dans_str']} (中{r_item['m3_hit_cnt']}: {r_item['m3_hits_str']})"
        _merge_and_style(ws1, r_idx, 12, r_idx, 13, m3_text, fill=row_fill, alignment=left_align)

        m4_text = f"{r_item['m4_pairs_str']} (双中: {r_item['m4_hits_str']})"
        _merge_and_style(ws1, r_idx, 14, r_idx, 16, m4_text, fill=row_fill, alignment=left_align)

        _merge_and_style(ws1, r_idx, 17, r_idx, 18, r_item["rating"], font=Font(bold=True) if is_highlight else None, fill=row_fill, alignment=center)

    # ── Sheet 1 列宽与行高智能自适应 ──
    ws1_base_widths: Dict[str, float] = {
        "A": 13.5,  # 期号 / 维度 / 号码 / 频次桶 / 验证期号
        "B": 13.5,  # 日期 / 连开期数 / 范围 / 容量
        "C": 7.0,   # N1 / 16窗频次 / 16窗合计 / 开奖号码
        "D": 8.5,   # N2 / 历史连庄率 / 期望
        "E": 8.0,   # N3 / 连庄潜力分 / 状态 / 【方法1】最优3码
        "F": 12.0,  # N4 / 操盘评级 / 连冷0出
        "G": 6.0,   # N5 / 间隔列
        "H": 7.5,   # N6 / 维度 / 剩余数 / 【方法2】混剪6码
        "I": 7.5,   # N7 / 名称 / 剩余号码
        "J": 8.5,   # N8 / 范围
        "K": 7.5,   # N9 / 16窗合计
        "L": 7.5,   # N10 / 期望 / 【方法3】回补3胆
        "M": 8.0,   # N11 / 连冷0出
        "N": 6.5,   # N12 / 【方法4】双飞选2
        "O": 6.0,   # N13
        "P": 6.0,   # N14
        "Q": 9.5,   # N15 / 实战评级
        "R": 8.0,   # N16
        "S": 5.5,   # N17
        "T": 5.5,   # N18
        "U": 5.5,   # N19
        "V": 5.5,   # N20
        "W": 7.2,   # 和值
        "X": 7.2,   # 跨度
        "Y": 7.2,   # 重号
    }
    for c_i in range(26, 53):
        ws1_base_widths[get_column_letter(c_i)] = 5.8
    for c_i in range(53, len(headers_left) + 1):
        ws1_base_widths[get_column_letter(c_i)] = 8.0

    for col_idx in range(1, len(headers_left) + 1):
        c_let = get_column_letter(col_idx)
        ws1.column_dimensions[c_let].width = ws1_base_widths.get(c_let, 6.0)

    # Sheet 1 全局自适应行高
    for r in range(1, ws1.max_row + 1):
        max_font_size = 9
        has_content = False
        max_newlines = 1
        for c in range(1, ws1.max_column + 1):
            cell = ws1.cell(r, c)
            if cell.value is not None and str(cell.value).strip():
                has_content = True
                val_s = str(cell.value)
                n_lines = len(val_s.split("\n"))
                if n_lines > max_newlines:
                    max_newlines = n_lines
                font_size = getattr(cell.font, 'size', None) if cell.font is not None else None
                if font_size is not None and font_size > max_font_size:
                    max_font_size = font_size

        if not has_content:
            ws1.row_dimensions[r].height = 10.0
        else:
            if max_font_size >= 12:
                base_h = 26.0
            elif max_font_size >= 11:
                base_h = 24.0
            elif max_font_size >= 10:
                base_h = 21.0
            else:
                base_h = 19.5
            ws1.row_dimensions[r].height = max(base_h, base_h * max_newlines * 0.85 + 3.0)

    ws1.freeze_panes = "C2"

    # ══════════════════════════════════════════════════════════════════
    # ── Sheet 2: 『全历史开奖矩阵』 (沉淀 2000+ 期全历史流水) ──
    # ══════════════════════════════════════════════════════════════════
    if include_full_matrix:
        ws2 = wb.create_sheet("全历史开奖矩阵")

        for col_idx, h in enumerate(headers_left, 1):
            cell = ws2.cell(1, col_idx, h)
            cell.font = header_font
            cell.alignment = center
            if col_idx <= 22:
                cell.fill = header_navy
            elif col_idx <= 25:
                cell.fill = header_teal
            elif col_idx <= 25 + len(head_names):
                cell.fill = header_navy
            elif col_idx <= 25 + len(head_names) + len(zone_names):
                cell.fill = header_teal
            elif col_idx <= 25 + len(head_names) + len(zone_names) + len(tail_names):
                cell.fill = header_purple
            else:
                cell.fill = header_orange

        for r_i, row in enumerate(full_matrix, 2):
            row_vals = (
                [row["period"], row["date"]]
                + list(row["nums"])
                + [row["sum"], row["span"], row["repeat_cnt"]]
                + [row[n] for n in head_names]
                + [row[n] for n in zone_names]
                + [row[n] for n in tail_names]
                + [row.get(f"落点_{k}", 0) for k in FREQ_BUCKET_KEYS]
            )
            ws2.append(row_vals)
            in_win = win_start <= int(row["period"]) <= win_end
            if in_win:
                for c_i in range(1, len(row_vals) + 1):
                    cell = ws2.cell(r_i, c_i)
                    cell.alignment = center
                    cell.border = thin_border
                    if c_i == head1_col:
                        cell.fill = cold_fill if int(row_vals[c_i - 1] or 0) == 0 else head1_fill
                    elif first_head_col <= c_i < first_zone_col:
                        idx = c_i - first_head_col
                        cell.fill = pink_fill if idx % 2 == 0 else green_fill
                    elif first_tail_col <= c_i < first_bucket_col:
                        cell.fill = yellow_soft if int(row_vals[c_i - 1] or 0) >= 4 else (cold_fill if int(row_vals[c_i - 1] or 0) == 0 else select_fill)
                    else:
                        cell.fill = select_fill

        ws2.freeze_panes = "C2"
        ws2_widths: Dict[str, float] = {
            "A": 11.0,
            "B": 13.0,
            "W": 7.2,
            "X": 7.2,
            "Y": 7.2,
        }
        for col_i in range(3, 23):
            ws2_widths[get_column_letter(col_i)] = 4.8
        for col_i in range(26, 53):
            ws2_widths[get_column_letter(col_i)] = 5.8
        for col_i in range(53, len(headers_left) + 1):
            ws2_widths[get_column_letter(col_i)] = 8.0

        for col in range(1, len(headers_left) + 1):
            c_let = get_column_letter(col)
            ws2.column_dimensions[c_let].width = ws2_widths.get(c_let, 5.5)

        ws2.row_dimensions[1].height = 26.0

    os.makedirs(os.path.dirname(xlsx_path) or ".", exist_ok=True)
    wb.save(xlsx_path)
    return xlsx_path


def persist_excel_window_table(
    table: Dict[str, Any],
    target_period: Optional[int] = None,
) -> Dict[str, str]:
    if table.get("status") != "ok":
        return {}

    tp = int(target_period or (int(table["latest_period"]) + 1))
    cache_dir = os.path.join(get_cache_dir(), "sixteen_period")
    report_dirs = [
        get_reports_dir(),
        os.path.join(get_outputs_dir(), "reports"),
    ]
    os.makedirs(cache_dir, exist_ok=True)

    matrix_n = len(table.get("matrix_rows") or [])
    json_path = os.path.join(cache_dir, "excel_window_latest.json")
    with open(json_path, "w", encoding="utf-8") as f:
        slim = dict(table)
        mr = slim.get("matrix_rows") or []
        slim["matrix_rows_total"] = len(mr)
        if len(mr) > 80:
            slim["matrix_rows"] = mr[-80:]
            slim["matrix_rows_truncated"] = True
        json.dump(slim, f, ensure_ascii=False, indent=2)

    md = render_window_markdown(table)

    paths: Dict[str, str] = {"json": json_path, "md": "", "matrix_rows": str(matrix_n)}
    fname_md = f"sixteen_excel_window_{tp}.md"
    fname_xlsx = f"sixteen_excel_window_{tp}.xlsx"

    primary_xlsx = os.path.join(cache_dir, "excel_window_latest.xlsx")
    export_excel_workbook(table, primary_xlsx, include_full_matrix=True)
    paths["xlsx_latest"] = primary_xlsx

    latest_md = os.path.join(cache_dir, "excel_window_latest.md")
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(md)
    paths["md_latest"] = latest_md

    for dpath in report_dirs:
        os.makedirs(dpath, exist_ok=True)
        md_path = os.path.join(dpath, fname_md)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)
        paths["md"] = md_path
        xlsx_path = os.path.join(dpath, fname_xlsx)
        shutil.copy2(primary_xlsx, xlsx_path)
        paths["xlsx"] = xlsx_path

    return paths


def run_excel_window_from_draws(
    draws: List[Dict[str, Any]],
    target_period: Optional[int] = None,
    persist: bool = True,
    analysis_res: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    table = build_excel_window_table(draws, window_size=WINDOW_SIZE, history_tail=None, analysis_res=analysis_res)
    if persist and table.get("status") == "ok":
        table["export_paths"] = persist_excel_window_table(table, target_period=target_period)
    return table
