# -*- coding: utf-8 -*-
"""
thirty_ball_benchmark.py — 快乐8 全模块 30 码黄金大底多方案滚动盲测对决竞技场
================================================================================

【业务背景与架构定位】:
本模块专为攻坚“30 码命中 11+ 码”实战目标而设计。
针对不同量化逻辑，构建 4 套差异化选号模型 + 1 套超级融合冠军模型：
  - 方案 1: 全模块多维投票共识大底 (Voting Ensemble)
  - 方案 2: 点位重码引力×左右双翼扩展大底 (Point Road & Twin Wings)
  - 方案 3: 热温冷三梯队平衡配比大底 (Temperature Tri-Tier)
  - 方案 4: 成对共现图引力×8区最大覆盖大底 (Co-occurrence MVO)
  - 方案 5: 超级赛博融合大底 (Champion Hybrid Ensemble)

在近 100 期真实历史开奖上进行严格的逐期 OOF (样本外) 滚动对账，杜绝任何未来函数穿透。

@author Antigravity Quant Team & Old-School Quant Trader
@since 2026-10-12
"""

from __future__ import annotations

import os
import sys
import json
import math
from datetime import datetime
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Any

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.dirname(_CURR_DIR)
_BACKEND_DIR = os.path.dirname(_MODULES_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils.paths import data_path, get_outputs_dir, get_reports_dir

TOTAL_BALLS = 80
DRAW_BALLS = 20
PORTFOLIO_SIZE = 30
BASE_HIT_EXP = PORTFOLIO_SIZE * (DRAW_BALLS / TOTAL_BALLS)  # 7.50


@dataclass
class PeriodRecord:
    period: int
    numbers: Set[int]
    raw_str: str


def load_history_records(limit: int = 500) -> List[PeriodRecord]:
    """从 storage/raw/kl8_history_final.txt 加载历史开奖数据（按时间先后升序排列）。"""
    hpath = data_path("kl8_history_final.txt")
    if not os.path.exists(hpath):
        alt = os.path.join(_PROJ_DIR, "storage", "raw", "kl8_history_final.txt")
        if os.path.exists(alt):
            hpath = alt
        else:
            raise FileNotFoundError(f"历史开奖数据文件未找到: {hpath}")

    records: List[PeriodRecord] = []
    with open(hpath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            try:
                p_str = parts[1].split(":")[1]
                n_str = parts[2].split(":")[1]
                p_int = int(p_str)
                nums = set(int(x) for x in n_str.split("-") if x)
                if len(nums) == DRAW_BALLS:
                    records.append(PeriodRecord(period=p_int, numbers=nums, raw_str=n_str))
            except Exception:
                continue

    # 按期号升序（从早到晚）
    records.sort(key=lambda r: r.period)
    if limit > 0 and len(records) > limit:
        records = records[-limit:]
    return records


def _omissions_from(pre: List[PeriodRecord]) -> Dict[int, int]:
    """遗漏值 (与逐期 reversed 扫描语义完全一致): 距上一次开出的期数; 窗口内从未开出 → 0。

    O(len(pre)) 单遍实现, 替代原先 O(80×len(pre)) 的逐球回扫, 结果不变。
    """
    last: Dict[int, int] = {}
    for j, rec in enumerate(pre):
        for b in rec.numbers:
            last[b] = j
    idx = len(pre)
    return {b: (idx - 1 - last[b]) if b in last else 0 for b in range(1, TOTAL_BALLS + 1)}


# =========================================================================
# 5 大候选策略核心实现 (严格只使用测试期之前的数据)
# =========================================================================

def strategy_1_voting_ensemble(history: List[PeriodRecord], idx: int) -> List[int]:
    """方案 1: 多维特征/模块投票共识大底。"""
    past_16 = history[max(0, idx - 16):idx]
    past_30 = history[max(0, idx - 30):idx]
    past_5 = history[max(0, idx - 5):idx]
    prev_draw = history[idx - 1].numbers

    # 1. 16 期频次（出窗进窗特征）
    c16 = Counter()
    for rec in past_16:
        c16.update(rec.numbers)

    # 2. 5 期动量冲刺
    c5 = Counter()
    for rec in past_5:
        c5.update(rec.numbers)

    # 3. 遗漏回补得分 (甜区 6~14)
    omissions = _omissions_from(history[:idx])

    # 4. 马尔可夫跟随转移得分
    past_60 = history[max(0, idx - 60):idx]
    follow_scores = Counter()
    for step in range(1, len(past_60)):
        p_nums = past_60[step - 1].numbers
        c_nums = past_60[step].numbers
        overlap = len(p_nums & prev_draw)
        for b in c_nums:
            follow_scores[b] += overlap

    # 综合投票加权
    scores = {}
    for b in range(1, TOTAL_BALLS + 1):
        s = 0.0
        # 16期中热得分 (中等偏热最高, 5~7 次为甜点)
        cnt16 = c16[b]
        if 4 <= cnt16 <= 7:
            s += 3.0
        elif cnt16 > 7:
            s += 2.0
        elif cnt16 >= 2:
            s += 1.0

        # 短期动量
        s += c5[b] * 0.5

        # 遗漏回补
        om = omissions[b]
        if 6 <= om <= 14:
            s += 2.5
        elif om > 20:
            s += 1.2

        # 跟随带出
        s += follow_scores[b] * 0.04

        # 重码惯性
        if b in prev_draw:
            s += 1.5

        scores[b] = s

    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return ranked[:PORTFOLIO_SIZE]


def strategy_2_point_twin_wings(history: List[PeriodRecord], idx: int) -> List[int]:
    """方案 2: 点位重码引力 + 左右双翼扩展大底。"""
    prev_draw = history[idx - 1].numbers
    # 扩展池：上期 20 码 + 左右双翼
    candidate_pool = set()
    for b in prev_draw:
        candidate_pool.add(b)
        if b > 1:
            candidate_pool.add(b - 1)
        if b < TOTAL_BALLS:
            candidate_pool.add(b + 1)

    # 补充历史高跟随带出码，确保候选池 >= 45 码
    past_40 = history[max(0, idx - 40):idx]
    follow_cnt = Counter()
    for step in range(1, len(past_40)):
        if len(past_40[step - 1].numbers & prev_draw) >= 4:
            follow_cnt.update(past_40[step].numbers)

    for b, _ in follow_cnt.most_common():
        if len(candidate_pool) >= 50:
            break
        candidate_pool.add(b)

    # 针对 candidate_pool 进行 012 路与近期活跃度精选
    past_10 = history[max(0, idx - 10):idx]
    freq10 = Counter()
    for rec in past_10:
        freq10.update(rec.numbers)

    # 排序：优先上期重码 + 双翼 + 近期出号频率
    def score_cand(ball: int) -> float:
        s = 0.0
        if ball in prev_draw:
            s += 4.0
        s += freq10[ball] * 0.8
        # 012 平衡微调
        s += (ball % 3) * 0.1
        return s

    ranked = sorted(candidate_pool, key=score_cand, reverse=True)
    return ranked[:PORTFOLIO_SIZE]


def strategy_3_temperature_tri_tier(history: List[PeriodRecord], idx: int) -> List[int]:
    """方案 3: 热温冷三梯队平衡配比大底 (12热 + 12温 + 6冷)。"""
    past_10 = history[max(0, idx - 10):idx]
    past_30 = history[max(0, idx - 30):idx]

    c10 = Counter()
    for rec in past_10:
        c10.update(rec.numbers)

    c30 = Counter()
    for rec in past_30:
        c30.update(rec.numbers)

    # 遗漏值
    omissions = _omissions_from(history[:idx])

    # 1. 12 个热码（近 10 期最高频）
    hot_candidates = sorted(range(1, TOTAL_BALLS + 1), key=lambda x: (c10[x], c30[x]), reverse=True)
    hot_12 = hot_candidates[:12]
    used = set(hot_12)

    # 2. 6 个冷码（遗漏最大）
    cold_candidates = sorted(
        [b for b in range(1, TOTAL_BALLS + 1) if b not in used],
        key=lambda x: omissions[x],
        reverse=True
    )
    cold_6 = cold_candidates[:6]
    used.update(cold_6)

    # 3. 12 个温码（近 30 期频次贴近理论均值 7.5 次的中热稳定码）
    warm_candidates = sorted(
        [b for b in range(1, TOTAL_BALLS + 1) if b not in used],
        key=lambda x: abs(c30[x] - 7.5)
    )
    warm_12 = warm_candidates[:12]

    combo = hot_12 + warm_12 + cold_6
    return sorted(combo)


def strategy_4_cooccurrence_mvo(history: List[PeriodRecord], idx: int) -> List[int]:
    """方案 4: 成对共现图引力×8区最大覆盖大底。"""
    past_50 = history[max(0, idx - 50):idx]

    # 构建两两成对共现矩阵
    cooc: Dict[int, Counter] = defaultdict(Counter)
    freq = Counter()
    for rec in past_50:
        freq.update(rec.numbers)
        slist = list(rec.numbers)
        for i in range(len(slist)):
            for j in range(i + 1, len(slist)):
                b1, b2 = slist[i], slist[j]
                cooc[b1][b2] += 1
                cooc[b2][b1] += 1

    # 8 分区定义 (每个区 10 个球: 1-10, 11-20, ..., 71-80)
    zones: Dict[int, List[int]] = defaultdict(list)
    for b in range(1, TOTAL_BALLS + 1):
        z = (b - 1) // 10
        zones[z].append(b)

    # 每个分区贪心选取 3~4 个球 (6个分区选4个, 2个分区选3个 = 30个)
    selected: List[int] = []
    zone_limits = [4, 4, 4, 4, 4, 4, 3, 3]  # 合计 30

    for z in range(8):
        limit = zone_limits[z]
        cands = zones[z]
        # 在该分区内，挑出单体频次高且在全局共现网中度中心性最大的球
        def zone_score(ball: int) -> float:
            single_f = freq[ball]
            cooc_sum = sum(cooc[ball].values())
            return single_f * 2.0 + cooc_sum * 0.1

        sorted_cands = sorted(cands, key=zone_score, reverse=True)
        selected.extend(sorted_cands[:limit])

    return sorted(selected)


def strategy_5_champion_hybrid(history: List[PeriodRecord], idx: int) -> List[int]:
    """方案 5: 超级赛博融合大底 (结合 1~4 方案的优势因子，非线性综合打分与分区约束)。"""
    p1 = set(strategy_1_voting_ensemble(history, idx)[:15])
    p2 = set(strategy_2_point_twin_wings(history, idx)[:12])
    p3 = set(strategy_3_temperature_tri_tier(history, idx)[:15])
    p4 = set(strategy_4_cooccurrence_mvo(history, idx)[:15])

    vote = Counter()
    vote.update(p1)
    vote.update(p2)
    vote.update(p3)
    vote.update(p4)

    # 近期基础频率作为次级排序键
    past_20 = history[max(0, idx - 20):idx]
    base_freq = Counter()
    for rec in past_20:
        base_freq.update(rec.numbers)

    # 先挑出至少 2 票以上的共识核心
    consensus = [b for b, cnt in vote.most_common() if cnt >= 2]

    # 按 8 分区进行平衡选拔，防止过度扎堆
    zones_selected: Dict[int, List[int]] = defaultdict(list)
    for b in consensus:
        z = (b - 1) // 10
        if len(zones_selected[z]) < 5:  # 每区最多 5 个
            zones_selected[z].append(b)

    final_picks: List[int] = []
    for z in range(8):
        final_picks.extend(zones_selected[z])

    # 如果不足 30，按总得分依次补齐
    if len(final_picks) < PORTFOLIO_SIZE:
        rem = sorted(
            [b for b in range(1, TOTAL_BALLS + 1) if b not in set(final_picks)],
            key=lambda x: (vote[x], base_freq[x]),
            reverse=True
        )
        for b in rem:
            if len(final_picks) >= PORTFOLIO_SIZE:
                break
            final_picks.append(b)

    # 如果超过 30，截断
    final_picks = final_picks[:PORTFOLIO_SIZE]
    return sorted(final_picks)


def strategy_6_sixteen_datasource_focus(history: List[PeriodRecord], idx: int) -> List[int]:
    """方案 6: 16期出窗进窗×双源共振特供大底 (基于用户提议的高命中模块深度优化，严格零未来数据穿透)。"""
    past_16 = history[max(0, idx - 16):idx]
    past_8 = history[max(0, idx - 8):idx]

    f16 = Counter()
    for r in past_16:
        f16.update(r.numbers)

    r8 = Counter()
    for r in past_8:
        r8.update(r.numbers)

    omissions = _omissions_from(history[:idx])

    # 计算 16 期高斯钟形中热得分 (网格搜索最优：中心 5.25, 宽度 1.6)
    scores = {}
    for b in range(1, TOTAL_BALLS + 1):
        f = f16[b]
        om = omissions[b]
        r_hits = r8[b]

        freq_bell = math.exp(-((f - 5.25) ** 2) / (2 * (1.6 ** 2)))
        r8_term = r_hits / 8.0
        if om <= 5:
            om_term = math.exp(-((om - 2.5) ** 2) / (2 * (2.2 ** 2)))
        elif om <= 7:
            om_term = 0.40
        else:
            om_term = 0.08

        # 16 期核心动量分 (占 80% 权重)
        s = (0.45 * freq_bell + 0.45 * r8_term + 0.10 * om_term) * 5.0

        # 重码惯性对冲
        if b in history[idx - 1].numbers:
            s += 1.5

        scores[b] = s

    # 8 分区几何均衡拦截 (防止号码过度扎堆暴死，每区选 3~4 码)
    zone_buckets = defaultdict(list)
    for b, sc in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        z = (b - 1) // 10
        zone_buckets[z].append(b)

    final_30 = []
    for z in range(8):
        final_30.extend(zone_buckets[z][:3])

    zone_cnt = Counter((b - 1) // 10 for b in final_30)
    rem = sorted([b for b in range(1, TOTAL_BALLS + 1) if b not in set(final_30)], key=lambda x: scores[x], reverse=True)
    for b in rem:
        if len(final_30) >= PORTFOLIO_SIZE:
            break
        z = (b - 1) // 10
        if zone_cnt[z] < 5:
            final_30.append(b)
            zone_cnt[z] += 1

    return sorted(final_30[:PORTFOLIO_SIZE])


def strategy_7_statistical_blend(history: List[PeriodRecord], idx: int) -> List[int]:
    """方案 7: 统计因子融合×8分区约束大底 (原产线 ThirtyBallEngine 打分器的可回测版)。

    仅保留可由历史开奖回测的统计因子 (16期甜区/遗漏回补/上期重码/左右双翼),
    剔除 lanes_vote/daily_points 因子 —— 历史上不存在逐期票池与点位数据, 带入即造假。
    """
    if idx < 1:
        raise ValueError("idx 必须 >= 1 (方案函数需要至少一期历史)")
    pre = history[:idx]
    prev_draw = pre[-1].numbers

    freq16 = Counter()
    for rec in pre[-16:]:
        freq16.update(rec.numbers)

    omissions: Dict[int, int] = {}
    for ball in range(1, TOTAL_BALLS + 1):
        om = 0
        for step, rec in enumerate(reversed(pre)):
            if ball in rec.numbers:
                om = step
                break
        omissions[ball] = om

    scores: Dict[int, float] = {}
    for b in range(1, TOTAL_BALLS + 1):
        s = 0.0
        cnt16 = freq16[b]
        if 4 <= cnt16 <= 7:
            s += 2.8
        elif cnt16 > 7:
            s += 1.8
        elif cnt16 >= 2:
            s += 1.0
        om = omissions[b]
        if 6 <= om <= 14:
            s += 2.4
        elif om > 20:
            s += 1.5
        if b in prev_draw:
            s += 2.0
        if any(abs(b - p) == 1 for p in prev_draw):
            s += 1.2
        scores[b] = s

    # 8 分区几何约束: 每区保底 2 码, 补齐时单区上限 5 码
    zone_buckets: Dict[int, List[int]] = defaultdict(list)
    for b, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        zone_buckets[(b - 1) // 10].append(b)

    selected: List[int] = []
    for z in range(8):
        selected.extend(zone_buckets[z][:2])

    zone_counts = Counter((b - 1) // 10 for b in selected)
    ranked = [b for b, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
    chosen = set(selected)
    for b in ranked:
        if len(selected) >= PORTFOLIO_SIZE:
            break
        if b in chosen:
            continue
        z = (b - 1) // 10
        if zone_counts[z] < 5:
            selected.append(b)
            chosen.add(b)
            zone_counts[z] += 1

    for b in ranked:
        if len(selected) >= PORTFOLIO_SIZE:
            break
        if b not in chosen:
            selected.append(b)
            chosen.add(b)

    return sorted(selected[:PORTFOLIO_SIZE])


def strategy_8_freq_momentum(history: List[PeriodRecord], idx: int) -> List[int]:
    """方案 8: 30期频次动量 Top30 大底 (尾部型选号, 提示性未确证)。

    假设来源 (2026-10-12 全历史 2031 期筛查): 前/后半段 >=11 码率 6.7%/6.8% 方向一致
    (合并精确二项 p=0.016; 8 方案族 BH-FDR q=0.13 未过) —— 属"提示性、未确证"。
    均中不升 (7.50), 逐球命中率 25.02% (无号码优势); 机制上是连号动量带来的尾部增厚,
    代价是低命中期也更多 (更不稳定), 仅作覆盖型备选, 不作加注依据。
    """
    c30 = Counter()
    for rec in history[max(0, idx - 30):idx]:
        c30.update(rec.numbers)
    ranked = sorted(range(1, TOTAL_BALLS + 1), key=lambda b: (-c30[b], b))
    return ranked[:PORTFOLIO_SIZE]


# =========================================================================
# 策略注册表: 产线引擎只允许从这里取函数对象, 保证"产线成员 = 被回测算法"单一事实源
# =========================================================================
STRATEGY_REGISTRY: Dict[str, Tuple[str, Any]] = {
    "strategy_1_voting_ensemble": ("方案 1: 全模块多维投票共识大底", strategy_1_voting_ensemble),
    "strategy_2_point_twin_wings": ("方案 2: 点位重码引力×左右双翼大底", strategy_2_point_twin_wings),
    "strategy_3_temperature_tri_tier": ("方案 3: 热温冷三梯队平衡配比大底", strategy_3_temperature_tri_tier),
    "strategy_4_cooccurrence_mvo": ("方案 4: 成对共现图引力×8区最大覆盖大底", strategy_4_cooccurrence_mvo),
    "strategy_5_champion_hybrid": ("方案 5: 超级赛博融合冠军大底", strategy_5_champion_hybrid),
    "strategy_6_sixteen_datasource_focus": ("方案 6: 16期出窗进窗×高斯中热特供大底", strategy_6_sixteen_datasource_focus),
    "strategy_7_statistical_blend": ("方案 7: 统计因子融合×8分区约束大底", strategy_7_statistical_blend),
    "strategy_8_freq_momentum": ("方案 8: 30期频次动量 Top30 大底 (尾部型/未确证)", strategy_8_freq_momentum),
}
DEFAULT_STRATEGY_ID = "strategy_5_champion_hybrid"


# =========================================================================
# 回测执行与对决统计分析
# =========================================================================

@dataclass
class StrategyMetrics:
    name: str
    n_periods: int
    mean_hits: float
    ge10_count: int
    ge10_rate: float
    ge11_count: int
    ge11_rate: float
    ge12_count: int
    ge12_rate: float
    max_hits: int
    min_hits: int
    lift: float  # (mean_hits / 30) / 0.25
    hit_history: List[int]


def evaluate_strategy(
    name: str,
    strat_func: Any,
    history: List[PeriodRecord],
    test_periods: int = 100
) -> StrategyMetrics:
    """对单策略执行逐期 OOF 滚动测试。"""
    n_total = len(history)
    start_idx = max(60, n_total - test_periods)
    actual_test_n = n_total - start_idx

    hit_history: List[int] = []
    for i in range(start_idx, n_total):
        target_rec = history[i]
        picks = strat_func(history, i)
        hits = len(set(picks) & target_rec.numbers)
        hit_history.append(hits)

    mean_h = sum(hit_history) / actual_test_n if actual_test_n > 0 else 0.0
    ge10 = sum(1 for h in hit_history if h >= 10)
    ge11 = sum(1 for h in hit_history if h >= 11)
    ge12 = sum(1 for h in hit_history if h >= 12)

    return StrategyMetrics(
        name=name,
        n_periods=actual_test_n,
        mean_hits=round(mean_h, 2),
        ge10_count=ge10,
        ge10_rate=round(ge10 / actual_test_n * 100, 1),
        ge11_count=ge11,
        ge11_rate=round(ge11 / actual_test_n * 100, 1),
        ge12_count=ge12,
        ge12_rate=round(ge12 / actual_test_n * 100, 1),
        max_hits=max(hit_history) if hit_history else 0,
        min_hits=min(hit_history) if hit_history else 0,
        lift=round((mean_h / PORTFOLIO_SIZE) / 0.25, 2),
        hit_history=hit_history
    )


def run_benchmark(n_periods: int = 100) -> Dict[str, Any]:
    """运行全方案横向滚动对比测试, 输出 JSON 证据产物 + 中性口径 MD 战报。"""
    from backend.modules.kl8_lab.numerics import hypergeom_sf, wilson_lower
    from backend.core.multiple_testing import bh_fdr
    from backend.modules.calc_follow_stats import _exact_binomial_p

    history = load_history_records(limit=n_periods + 80)
    print(f"📊 加载历史开奖总记录: {len(history)} 期，实测滚动期数: {n_periods} 期")

    baseline = {
        "p_ge10": hypergeom_sf(10, PORTFOLIO_SIZE, TOTAL_BALLS, DRAW_BALLS),
        "p_ge11": hypergeom_sf(11, PORTFOLIO_SIZE, TOTAL_BALLS, DRAW_BALLS),
        "p_ge12": hypergeom_sf(12, PORTFOLIO_SIZE, TOTAL_BALLS, DRAW_BALLS),
        "mean": round(PORTFOLIO_SIZE * DRAW_BALLS / TOTAL_BALLS, 2),
    }

    metrics_by_id: Dict[str, StrategyMetrics] = {}
    p_by_id: Dict[str, float] = {}
    for sid, (name, func) in STRATEGY_REGISTRY.items():
        m = evaluate_strategy(name, func, history, test_periods=n_periods)
        metrics_by_id[sid] = m
        p_by_id[sid] = _exact_binomial_p(m.n_periods, m.ge11_count, baseline["p_ge11"])
        print(f"  [完成] {name:32s} -> 均中: {m.mean_hits:.2f} 码 | >=11码: {m.ge11_count}/{m.n_periods} ({m.ge11_rate}%) | 最大: {m.max_hits} 码")

    sig_mask, q_values = bh_fdr([p_by_id[sid] for sid in STRATEGY_REGISTRY], alpha=0.05)
    q_by_id = {sid: q for sid, q in zip(STRATEGY_REGISTRY, q_values)}
    sig_by_id = {sid: s for sid, s in zip(STRATEGY_REGISTRY, sig_mask)}

    strategies_payload: List[Dict[str, Any]] = []
    for sid, (name, _func) in STRATEGY_REGISTRY.items():
        m = metrics_by_id[sid]
        strategies_payload.append({
            "id": sid,
            "name": name,
            "n_periods": m.n_periods,
            "mean_hits": m.mean_hits,
            "ge10_rate": m.ge10_rate,
            "ge11_count": m.ge11_count,
            "ge11_rate": m.ge11_rate,
            "ge12_rate": m.ge12_rate,
            "max_hits": m.max_hits,
            "min_hits": m.min_hits,
            "lift": m.lift,
            "p_value": round(p_by_id[sid], 6),
            "bh_q": round(q_by_id[sid], 6),
            "wilson_lo": round(wilson_lower(m.ge11_count, m.n_periods), 4),
            "wilson_hi": round(1.0 - wilson_lower(m.n_periods - m.ge11_count, m.n_periods), 4),
            "significant": bool(sig_by_id[sid]),
        })

    # 推荐决策: 按 ≥11 码命中次数、再按均中排序 (按次数, 不按舍入后的比率)。
    # significant 仅记录不设门槛: 30 码底是覆盖型产品, 未过显著性也如实推荐并注明。
    recommended_sid = max(
        STRATEGY_REGISTRY.keys(),
        key=lambda sid: (metrics_by_id[sid].ge11_count, metrics_by_id[sid].mean_hits),
    )
    rec = next(r for r in strategies_payload if r["id"] == recommended_sid)
    if rec["significant"]:
        decision_note = (
            f"按≥11码命中次数最高({rec['ge11_count']}/{rec['n_periods']})选出；"
            f"BH-q={rec['bh_q']:.3f} 通过 0.05 门槛，仍需样本外持续跟踪复现。"
        )
    else:
        decision_note = (
            f"按≥11码命中次数最高({rec['ge11_count']}/{rec['n_periods']})选出；"
            f"BH-q={rec['bh_q']:.3f} 未通过 0.05 门槛，与随机基线({baseline['p_ge11'] * 100:.1f}%)差异不能排除随机波动，"
            f"仅作覆盖型参考(期望命中≈{baseline['mean']}码)，不构成概率优势证据、不作加注依据。"
        )

    payload: Dict[str, Any] = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_period": history[-1].period,
        "n_periods": metrics_by_id[recommended_sid].n_periods,
        "baseline": baseline,
        "strategies": strategies_payload,
        "recommended": recommended_sid,
        "decision_note": decision_note,
    }

    out_dir = os.path.join(get_outputs_dir(), "reports")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "thirty_ball_benchmark_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ 回测证据 JSON 已写入: {json_path}")

    # ── MD 战报 (中性措辞, 数字全部来自本次实测) ──
    report_path = os.path.join(out_dir, "thirty_ball_benchmark_report.md")
    sorted_rows = sorted(
        strategies_payload,
        key=lambda r: (r["ge11_count"], r["mean_hits"]),
        reverse=True,
    )

    lines = [
        "# 🎯 快乐8 全模块 30 码黄金大底 · 多方案滚动盲测对决总决算",
        "",
        f"> 📅 **对账时间**：近 {payload['n_periods']} 期滚动实测（最新开奖基准期：{payload['base_period']}）",
        "> ⚖️ **评判口径**：严格逐期 OOF 样本外盲测，禁止未来数据穿透；显著性一律经 BH-FDR 校正并附 Wilson 区间，未过门槛的差距不得表述为优势。",
        "",
        "---",
        "",
        f"## 一、 {len(strategies_payload)} 大方案横向决算积分榜 (Leaderboard)",
        "",
        "| 排名 | 方案名称 | 平均命中 | $\\ge 10$ 码 | $\\ge 11$ 码 (目标) | $\\ge 12$ 码 | 最大/最小 | Wilson95[$\\ge 11$] | BH-q | 显著性 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for rank, r in enumerate(sorted_rows, 1):
        mark = "👑 **首推**" if r["id"] == recommended_sid else f"第 {rank} 名"
        sig_txt = "✅ 通过" if r["significant"] else "❌ 未通过"
        lines.append(
            f"| {mark} | **{r['name']}** | **{r['mean_hits']:.2f}** | {r['ge10_rate']:.1f}% | "
            f"**{r['ge11_count']}期 ({r['ge11_rate']:.1f}%)** | {r['ge12_rate']:.1f}% | {r['max_hits']}/{r['min_hits']} | "
            f"[{r['wilson_lo'] * 100:.1f}%, {r['wilson_hi'] * 100:.1f}%] | {r['bh_q']:.3f} | {sig_txt} |"
        )
    lines.append(
        f"| — | *随机盲猜基线 (超几何精确值)* | *{baseline['mean']:.2f}* | *{baseline['p_ge10'] * 100:.1f}%* | "
        f"*{baseline['p_ge11'] * 100:.1f}%* | *{baseline['p_ge12'] * 100:.1f}%* | *—* | *—* | *—* | *理论参照* |"
    )

    lines.extend([
        "",
        "---",
        "",
        "## 二、 回测结论 (中性口径, 数字均来自本次实测)",
        "",
        f"1. **首推方案**：「{rec['name']}」在 {rec['n_periods']} 期 OOF 中 ≥11 码 **{rec['ge11_count']}/{rec['n_periods']} ({rec['ge11_rate']:.1f}%)**，"
        f"随机基线 {baseline['p_ge11'] * 100:.1f}%，Wilson95 [{rec['wilson_lo'] * 100:.1f}%, {rec['wilson_hi'] * 100:.1f}%]，BH-q={rec['bh_q']:.3f}。",
        (
            "2. **显著性判定**：通过 BH-FDR 0.05 门槛；仍属历史窗口内的结论，需后续逐期跟踪复现，不可外推为长期优势。"
            if rec["significant"]
            else "2. **显著性判定**：未通过 BH-FDR 0.05 门槛 —— 上述差距**不能排除随机波动**；本表所有方案均未证明对随机存在可复现优势。"
        ),
        "3. **使用须知**：30 码大底按**覆盖型工具**使用（随机期望命中 ≈ 7.5 码/期）；单期最高命中为小样本极值，不代表期望；"
        "分区约束属于结构性防扎堆设计，不改变成员算法本身。",
        "",
        "---",
        "",
        "## 三、 落地推荐",
        "",
        f"- 产线 `ThirtyBallEngine` 以 `{recommended_sid}` 为默认成员算法（读取本 JSON 的 `recommended` 字段，缺失时回退 `{DEFAULT_STRATEGY_ID}`）；票数/点位仅用于展示排序，不改变成员。",
        f"- 决策说明：{decision_note}",
        "",
    ])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ 对决总决算战报已物理写入: {report_path}")
    return {
        "status": "success",
        "json_path": json_path,
        "report_path": report_path,
        "recommended": recommended_sid,
        "results": strategies_payload,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="30码黄金大底多方案滚动对决评测")
    parser.add_argument("--periods", type=int, default=100, help="回测期数 (默认 100 期)")
    args = parser.parse_args()
    run_benchmark(n_periods=args.periods)
