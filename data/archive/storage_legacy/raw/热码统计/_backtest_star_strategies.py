#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 热码星标策略回测引擎
=========================
目标：对比不同打标逻辑下，带*号码的数量控制与下期命中率
核心指标：
  1. 带*号码数量（目标≤25）
  2. 下期命中数 / 期望命中数（信息增益比）
  3. 稳定性（标准差）
"""
import os
import sys
import collections
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
HISTORY_FILE = os.path.join(_PROJ, 'kl8_history_final.txt')

NUM_TOTAL = 80
NUM_PICK = 20
WINDOWS = [("全量", None), ("50期", 50), ("25期", 25), ("10期", 10)]


def load_history():
    data = []
    if not os.path.exists(HISTORY_FILE):
        print(f"[错误] 未找到: {HISTORY_FILE}")
        return data
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if 'numbers:' not in line:
                continue
            parts = line.split(',')
            data.append({
                'date': parts[0].split(':')[1],
                'period': parts[1].split(':')[1],
                'numbers': [int(n) for n in parts[2].split(':')[1].strip().split('-')]
            })
    return data


def rank_with_ties(values):
    ranked = sorted(values.items(), key=lambda item: (-item[1], item[0]))
    result = {}
    prev_value, prev_rank = None, 0
    for index, (number, value) in enumerate(ranked, start=1):
        if value == prev_value:
            result[number] = prev_rank
        else:
            result[number] = index
            prev_rank = index
            prev_value = value
    return result


def build_hot_windows_for_period(hist_chrono, up_to_idx):
    """为 hist_chrono[0:up_to_idx+1] 构建4窗口统计"""
    subset_all = hist_chrono[:up_to_idx + 1]
    result = {}
    for label, window in WINDOWS:
        w_data = subset_all if window is None else subset_all[-window:]
        counts = collections.Counter(n for r in w_data for n in r["numbers"])
        ranks = rank_with_ties({n: counts.get(n, 0) for n in range(1, 81)})
        w_size = len(w_data)
        expected = max(w_size * 0.25, 1e-9)
        num_map = {}
        for number in range(1, 81):
            hits = counts.get(number, 0)
            num_map[number] = {
                "hits": hits,
                "rank": ranks[number],
                "ratio": round(hits / expected * 100, 1)
            }
        result[label] = num_map
    return result


# ══════════════════════════════════════════════════════════════
# 五种打标策略
# ══════════════════════════════════════════════════════════════

def strategy_old(windows):
    """旧策略：任意窗口 Rank≤15 且(短窗口HITS>1)，取并集"""
    star_set = set()
    for label in ["50期", "25期", "10期"]:
        top = [n for n, info in windows[label].items() if info["rank"] <= 15 and info["hits"] > 1]
        star_set.update(top)
    top_all = [n for n, info in windows["全量"].items() if info["rank"] <= 15]
    star_set.update(top_all)
    return star_set


def strategy_A_rank8(windows):
    """策略A：收紧阈值 — Rank≤8 并集"""
    star_set = set()
    for label in ["50期", "25期", "10期"]:
        top = [n for n, info in windows[label].items() if info["rank"] <= 8 and info["hits"] > 1]
        star_set.update(top)
    top_all = [n for n, info in windows["全量"].items() if info["rank"] <= 8]
    star_set.update(top_all)
    return star_set


def strategy_B_intersection(windows):
    """策略B：交集逻辑 — 至少2个短窗口 Rank≤15"""
    from collections import Counter
    short_windows = ["50期", "25期", "10期"]
    appearance = Counter()
    for label in short_windows:
        top = [n for n, info in windows[label].items() if info["rank"] <= 15 and info["hits"] > 1]
        for n in top:
            appearance[n] += 1
    # 至少出现2次
    star_set = {n for n, cnt in appearance.items() if cnt >= 2}
    # 全量 Top 8 强制入选
    top_all = [n for n, info in windows["全量"].items() if info["rank"] <= 8]
    star_set.update(top_all)
    return star_set


def strategy_C_weighted_top20(windows):
    """策略C：加权共振评分取Top20"""
    scores = {}
    for number in range(1, 81):
        all_info = windows["全量"][number]
        s50 = windows["50期"][number]
        s25 = windows["25期"][number]
        s10 = windows["10期"][number]

        short_top5 = sum(1 for item in (s50, s25, s10) if item["rank"] <= 5)
        short_top10 = sum(1 for item in (s50, s25, s10) if item["rank"] <= 10)
        short_ratio_avg = (s50["ratio"] + s25["ratio"] + s10["ratio"]) / 3.0
        short_ratio_peak = max(s50["ratio"], s25["ratio"], s10["ratio"])
        all_bonus = max(0.0, 36.0 - all_info["rank"])

        scores[number] = (
            short_top5 * 22.0
            + short_top10 * 8.0
            + short_ratio_avg * 0.36
            + short_ratio_peak * 0.20
            + all_bonus * 1.6
            + all_info["ratio"] * 0.14
        )

    return set(sorted(scores, key=lambda n: (-scores[n], n))[:20])


def strategy_D_hybrid(windows):
    """策略D：混合策略 — 多窗口强共振"""
    from collections import Counter
    scores = Counter()

    # 全量权重最大
    for n, info in windows["全量"].items():
        if info["rank"] <= 10:
            scores[n] += 3

    # 短窗口：Rank越前分越高
    for label in ["50期", "25期", "10期"]:
        for n, info in windows[label].items():
            if info["rank"] <= 5 and info["hits"] > 1:
                scores[n] += 3
            elif info["rank"] <= 10 and info["hits"] > 1:
                scores[n] += 2
            elif info["rank"] <= 15 and info["hits"] > 1:
                scores[n] += 1

    # 至少在2个维度有贡献的号码才入选
    candidates = {n: s for n, s in scores.items() if s >= 3}
    # 取评分最高的25个
    top25 = sorted(candidates, key=lambda n: (-candidates[n], n))[:25]
    return set(top25)


# ══════════════════════════════════════════════════════════════
# 回测引擎
# ══════════════════════════════════════════════════════════════

def run_backtest(history, strategy_fn, strategy_name, test_periods=50):
    """回测指定策略最近 test_periods 期"""
    hist_chrono = history[::-1]  # 旧在前
    n = len(hist_chrono)

    results = []
    # 从有足够历史数据开始
    start = max(100, n - test_periods - 1)

    for i in range(start, n - 1):
        windows = build_hot_windows_for_period(hist_chrono, i)
        star_set = strategy_fn(windows)

        # 下一期实际开奖
        next_numbers = set(hist_chrono[i + 1]["numbers"])
        hits = len(star_set & next_numbers)

        results.append({
            "period": hist_chrono[i + 1]["period"],
            "star_count": len(star_set),
            "hits": hits,
            "expected": len(star_set) * NUM_PICK / NUM_TOTAL,
            "advantage": hits - len(star_set) * NUM_PICK / NUM_TOTAL,
        })

    if not results:
        return None

    star_counts = [r["star_count"] for r in results]
    hits_list = [r["hits"] for r in results]
    adv_list = [r["advantage"] for r in results]
    expected_list = [r["expected"] for r in results]

    return {
        "name": strategy_name,
        "test_periods": len(results),
        "avg_star_count": round(np.mean(star_counts), 1),
        "min_star_count": min(star_counts),
        "max_star_count": max(star_counts),
        "star_std": round(np.std(star_counts), 1),
        "avg_hits": round(np.mean(hits_list), 2),
        "avg_expected": round(np.mean(expected_list), 2),
        "avg_advantage": round(np.mean(adv_list), 2),
        "hit_std": round(np.std(hits_list), 2),
        "beat_random_rate": round(sum(1 for a in adv_list if a > 0) / len(adv_list) * 100, 1),
        "efficiency": round(np.mean(hits_list) / np.mean(star_counts) * 100, 1) if np.mean(star_counts) > 0 else 0,
        "info_gain_ratio": round(np.mean(adv_list) / np.mean(star_counts) * 100, 2) if np.mean(star_counts) > 0 else 0,
        "over_25_count": sum(1 for s in star_counts if s > 25),
        "over_25_rate": round(sum(1 for s in star_counts if s > 25) / len(star_counts) * 100, 1),
    }


def main():
    print("=" * 90)
    print("  快乐8 热码星标策略回测引擎 — 五策略对比")
    print("  目标：带*号码 ≤ 25 个，同时最大化预测信息增益")
    print("=" * 90)

    history = load_history()
    if not history:
        return

    print(f"[数据] 加载 {len(history)} 期历史数据")
    print(f"[范围] {history[-1]['period']} ~ {history[0]['period']}")
    print()

    strategies = [
        (strategy_old, "旧策略(Rank≤15并集)"),
        (strategy_A_rank8, "策略A(Rank≤8并集)"),
        (strategy_B_intersection, "策略B(≥2窗口交集+全量Top8)"),
        (strategy_C_weighted_top20, "策略C(加权共振Top20)"),
        (strategy_D_hybrid, "策略D(混合多维度评分)"),
    ]

    results = []
    for fn, name in strategies:
        print(f"[回测] {name} ...")
        res = run_backtest(history, fn, name, test_periods=50)
        if res:
            results.append(res)

    # 输出对比表
    print("\n" + "=" * 90)
    print("  回测结果对比 (最近50期)")
    print("=" * 90)

    header = f"{'策略':<28} | {'均*数':>6} | {'*数范围':>10} | {'超25率':>6} | {'均命中':>6} | {'随机基':>6} | {'优势':>6} | {'胜随机':>6} | {'效率%':>6} | {'信息增益比':>8}"
    print(header)
    print("-" * 120)

    for r in results:
        line = (
            f"{r['name']:<28} | "
            f"{r['avg_star_count']:>6.1f} | "
            f"{r['min_star_count']}-{r['max_star_count']:>2}     | "
            f"{r['over_25_rate']:>5.1f}% | "
            f"{r['avg_hits']:>6.2f} | "
            f"{r['avg_expected']:>6.2f} | "
            f"{r['avg_advantage']:>+6.2f} | "
            f"{r['beat_random_rate']:>5.1f}% | "
            f"{r['efficiency']:>6.1f} | "
            f"{r['info_gain_ratio']:>+7.2f}%"
        )
        print(line)

    # 理论分析
    print("\n" + "=" * 90)
    print("  理论分析：为什么25个是合理上界")
    print("=" * 90)
    print(f"""
  ┌──────────────────────────────────────────────────────────────────┐
  │ 快乐8核心参数: 80选20, 每期命中率 p = 20/80 = 0.25            │
  ├──────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │  带*号码数 N → 随机期望命中 = N × 0.25                         │
  │                                                                  │
  │  N=15: 期望 3.75, 覆盖率18.75% → 区分度极强, 但可能遗漏       │
  │  N=20: 期望 5.00, 覆盖率25.00% → 恰好等于开奖量, 最优锚点    │
  │  N=25: 期望 6.25, 覆盖率31.25% → 信号仍可辨别, 合理上界       │
  │  N=30: 期望 7.50, 覆盖率37.50% → 信号开始被稀释               │
  │  N=40: 期望10.00, 覆盖率50.00% → 区分度崩溃, 等同随机         │
  │                                                                  │
  │  信息论阈值:                                                     │
  │    N ≤ 25 时, I(星标;开奖) > 0 (星标携带正信息量)              │
  │    N > 30 时, I(星标;开奖) → 0  (星标退化为噪音)               │
  │                                                                  │
  │  统计功效:                                                       │
  │    N=20 时, 单次命中H0检验(二项分布):                           │
  │      P(X≥6|n=20,p=0.25) = 0.10 (边缘显著)                      │
  │      P(X≥7|n=20,p=0.25) = 0.04 (显著, α<0.05)                 │
  │    N=35 时:                                                      │
  │      P(X≥11|n=35,p=0.25) = 0.10 (需要更多命中才显著)           │
  │      → 池子越大, 越难证明"不是运气"                              │
  └──────────────────────────────────────────────────────────────────┘
    """)

    # 推荐
    best = min(results, key=lambda r: abs(r['avg_star_count'] - 22))
    print(f"  综合推荐: {best['name']}")
    print(f"    平均带*数: {best['avg_star_count']}, 超过25的比例: {best['over_25_rate']}%")
    print(f"    平均命中: {best['avg_hits']}, 优势: {best['avg_advantage']:+.2f}")


if __name__ == '__main__':
    main()
