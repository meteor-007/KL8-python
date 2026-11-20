# -*- coding: utf-8 -*-
"""
30 期样本外严苛走前盲测 (Walk-Forward Blind Test) - 生产级全景对账
========================================================================
1. 逐期调用 FolkSixteenEngine.analyze_window(target_period=P)
2. 引擎内部严格 base_index = P-1，杜绝未来函数
3. 每期输出：红底20码命中数 / 黄底16码命中数 / 红框核心命中数 / 金5 / 金3
4. 每期输出四维诊断：重号数 / 012路构成 / 十位区间覆盖 / 尾数覆盖
5. 最终汇总统计与基线对比 (Lift)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

engine = FolkSixteenEngine()
total_draws = len(engine.draws)
N_TEST = 30
test_start = total_draws - N_TEST

red_hits_total = 0
yellow_hits_total = 0
border_hits_total = 0
border_balls_total = 0
grand_hits_total = 0
elite_hits_total = 0
golden5_hits_total = 0
golden3_hits_total = 0

pair_double_total = 0
pair_single_total = 0
pair_total_count = 0

repeat_counts = []
zone_counts = []
tail_counts = []

print("=" * 110)
print(f"{'Period':>8}  {'Red20':>7}  {'Yel16':>7}  {'BorderCore':>11}  {'Elite12':>8}  {'G5':>5}  {'G3':>5}  {'Reps':>5}  {'012Road':>8}  {'Zone':>5}  {'Tail':>5}")
print("=" * 110)

for i in range(test_start, total_draws):
    target_period = engine.draws[i]["period"]
    actual_set = engine.draws[i]["nums_set"]

    result = engine.analyze_window(target_period=target_period)
    picks = result["picks"]
    audit = result["hit_audit"]

    red_pool = picks["red_pool"]
    yellow_pool = picks["yellow_pool"]
    border_core = picks["red_border_core"]
    grand_20 = picks["grand_20"]
    elite_12 = picks["elite_12"]
    golden_5 = picks["golden_5"]
    golden_3 = picks["golden_3"]
    top_pairs = picks["top_pairs"]

    red_h = audit["red_pool_hit_count"]
    yellow_h = audit["yellow_pool_hit_count"]
    border_h = audit["red_border_hit_count"]
    grand_h = audit["grand_20_hit_count"]
    elite_h = audit["elite_12_hit_count"]
    g5_h = audit["golden_5_hit_count"]
    g3_h = audit["golden_3_hit_count"]

    red_hits_total += red_h
    yellow_hits_total += yellow_h
    border_hits_total += border_h
    border_balls_total += len(border_core)
    grand_hits_total += grand_h
    elite_hits_total += elite_h
    golden5_hits_total += g5_h
    golden3_hits_total += g3_h

    # 四维诊断
    base_idx = i - 1
    last_set = engine.draws[base_idx]["nums_set"]
    rep_in_red = [n for n in red_pool if n in last_set]
    rep_count = len(rep_in_red)
    repeat_counts.append(rep_count)

    r0 = sum(1 for n in red_pool if n % 3 == 0)
    r1 = sum(1 for n in red_pool if n % 3 == 1)
    r2 = sum(1 for n in red_pool if n % 3 == 2)
    road_str = f"{r0}:{r1}:{r2}"

    zones_hit = set((n - 1) // 10 + 1 for n in red_pool)
    zone_counts.append(len(zones_hit))

    tails_hit = set(n % 10 for n in red_pool)
    tail_counts.append(len(tails_hit))

    for pair in top_pairs:
        pair_total_count += 1
        hits_in_pair = sum(1 for p in pair if p in actual_set)
        if hits_in_pair == 2:
            pair_double_total += 1
        elif hits_in_pair == 1:
            pair_single_total += 1

    print(f"{target_period:>8}  {red_h:>5}/20  {yellow_h:>5}/16  {border_h:>5}/{len(border_core):<3}  {elite_h:>6}/12  {g5_h:>3}/5  {g3_h:>3}/3  {rep_count:>5}  {road_str:>8}  {len(zones_hit):>3}/8  {len(tails_hit):>3}/10")

print("=" * 110)

print(f"\n{'='*80}")
print(f"  30-Period Walk-Forward Blind Test Total Summary")
print(f"{'='*80}")
print(f"  Red Pool 20 Avg Hits:     {red_hits_total / N_TEST:.2f} / 20  (Rate: {red_hits_total / N_TEST / 20 * 100:.1f}%, Lift: {red_hits_total / N_TEST / 20 / 0.25:.2f}x)")
print(f"  Yellow Pool 16 Avg Hits:  {yellow_hits_total / N_TEST:.2f} / 16  (Rate: {yellow_hits_total / N_TEST / 16 * 100:.1f}%, Lift: {yellow_hits_total / N_TEST / 16 / 0.25:.2f}x)")
print(f"  Red Border Core Avg Hits: {border_hits_total / N_TEST:.2f} / {border_balls_total / N_TEST:.1f} (Rate: {border_hits_total / border_balls_total * 100:.1f}%, Lift: {border_hits_total / border_balls_total / 0.25:.2f}x)")
print(f"  Elite 12 Avg Hits:        {elite_hits_total / N_TEST:.2f} / 12  (Rate: {elite_hits_total / N_TEST / 12 * 100:.1f}%, Lift: {elite_hits_total / N_TEST / 12 / 0.25:.2f}x)")
print(f"  Golden 5 Avg Hits:        {golden5_hits_total / N_TEST:.2f} / 5   (Rate: {golden5_hits_total / N_TEST / 5 * 100:.1f}%, Lift: {golden5_hits_total / N_TEST / 5 / 0.25:.2f}x)")
print(f"  Golden 3 Avg Hits:        {golden3_hits_total / N_TEST:.2f} / 3   (Rate: {golden3_hits_total / N_TEST / 3 * 100:.1f}%, Lift: {golden3_hits_total / N_TEST / 3 / 0.25:.2f}x)")
print()
print(f"  Repeat Numbers:  Avg {sum(repeat_counts)/len(repeat_counts):.2f} (Min: {min(repeat_counts)}, Max: {max(repeat_counts)})")
print(f"  Zone Coverage:   Avg {sum(zone_counts)/len(zone_counts):.2f} / 8")
print(f"  Tail Coverage:   Avg {sum(tail_counts)/len(tail_counts):.2f} / 10")
print(f"  Top Pairs:       {pair_total_count} pairs, Double Hits: {pair_double_total} ({pair_double_total * 100 / max(pair_total_count, 1):.1f}% vs baseline 6.0%), Single Hits: {pair_single_total} ({pair_single_total * 100 / max(pair_total_count, 1):.1f}%)")
print(f"{'='*80}")
