# -*- coding: utf-8 -*-
"""
深入复核: 2026262 期实开 20 码，在新版引擎下的逐号命中与四维特征全息诊断
实开: 04 06 09 12 15 17 20 33 42 44 49 54 55 59 61 65 72 73 78 80
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

engine = FolkSixteenEngine()
res_262 = engine.analyze_window(target_period=2026262)

picks = res_262["picks"]
audit = res_262["hit_audit"]
profiles = res_262["ball_profiles"]

actual_set = set(audit["actual_draw"])
red_set = set(picks["red_pool"])
yellow_set = set(picks["yellow_pool"])
border_set = set(picks["red_border_core"])

last_draw_set = engine.draws[engine.draws.index([d for d in engine.draws if d['period'] == 2026262][0]) - 1]["nums_set"]

print("=" * 80)
print("第 2026262 期实战单期深度对账全景复盘")
print("=" * 80)
print(f"实开 20 码: {sorted(list(actual_set))}")
print(f"红底 20 码: {sorted(list(red_set))}")
print(f"命中 {len(red_set & actual_set)} 码: {sorted(list(red_set & actual_set))}")
print(f"黄底 16 码: {sorted(list(yellow_set))}")
print(f"命中 {len(yellow_set & actual_set)} 码: {sorted(list(yellow_set & actual_set))}")
print(f"红框核心 {len(border_set)} 码: {sorted(list(border_set))}")
print(f"命中 {len(border_set & actual_set)} 码: {sorted(list(border_set & actual_set))}")
print(f"精选 12 码: {picks['elite_12']} -> 命中 {len(set(picks['elite_12']) & actual_set)} 码: {sorted(list(set(picks['elite_12']) & actual_set))}")
print(f"黄金 5 胆: {picks['golden_5']} -> 命中 {len(set(picks['golden_5']) & actual_set)} 码: {sorted(list(set(picks['golden_5']) & actual_set))}")
print(f"最优 3 胆: {picks['golden_3']} -> 命中 {len(set(picks['golden_3']) & actual_set)} 码: {sorted(list(set(picks['golden_3']) & actual_set))}")
print(f"选 2 搭档: {picks['top_pairs']}")
for p in picks['top_pairs']:
    hits = set(p) & actual_set
    print(f"  搭档 {p} 命中 {len(hits)} 码: {list(hits)}")

print("\n四维指标验证:")
rep_nums = [n for n in red_set if n in last_draw_set]
print(f"1. 重号数: {len(rep_nums)} 码 -> {rep_nums} (实测开奖重号 {len(actual_set & last_draw_set)} 码)")
r0 = sum(1 for n in red_set if n % 3 == 0)
r1 = sum(1 for n in red_set if n % 3 == 1)
r2 = sum(1 for n in red_set if n % 3 == 2)
print(f"2. 012路比: {r0}:{r1}:{r2} (目标 7:6:7)")
zones = set((n - 1) // 10 + 1 for n in red_set)
print(f"3. 十位区间覆盖: {len(zones)}/8 区 -> 覆盖区间: {sorted(list(zones))}")
tails = set(n % 10 for n in red_set)
print(f"4. 尾数全息离散: {len(tails)}/10 尾 -> 覆盖尾数: {sorted(list(tails))}")
print("=" * 80)
