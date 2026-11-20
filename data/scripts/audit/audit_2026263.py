# -*- coding: utf-8 -*-
"""
复盘对账：针对第 2026263 期实开号码，核对我们在 2026263 期预测的命中表现
实开号码: 07 08 09 10 11 13 22 24 25 26 31 33 37 45 50 51 62 67 70 80
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

engine = FolkSixteenEngine()
# 分析 2026263 期的预测 (base_period 为 2026262)
res_263 = engine.analyze_window(target_period=2026263)

picks = res_263["picks"]
audit = res_263["hit_audit"]

actual_set = set(audit["actual_draw"])
red_set = set(picks["red_pool"])
yellow_set = set(picks["yellow_pool"])
border_set = set(picks["red_border_core"])
elite_set = set(picks["elite_12"])
g5_set = set(picks["golden_5"])
g3_set = set(picks["golden_3"])

print("=" * 80)
print("第 2026263 期实开对账总决算 (基于无未来函数预测)")
print("=" * 80)
print(f"实开 20 码: {sorted(list(actual_set))}")
print(f"红底 20 码: {sorted(list(red_set))} -> 命中 {len(red_set & actual_set)} 码: {sorted(list(red_set & actual_set))}")
print(f"黄底 16 码: {sorted(list(yellow_set))} -> 命中 {len(yellow_set & actual_set)} 码: {sorted(list(yellow_set & actual_set))}")
print(f"红框核心 {len(border_set)} 码: {sorted(list(border_set))} -> 命中 {len(border_set & actual_set)} 码: {sorted(list(border_set & actual_set))}")
print(f"精选 12 码: {sorted(list(elite_set))} -> 命中 {len(elite_set & actual_set)} 码: {sorted(list(elite_set & actual_set))}")
print(f"黄金 5 胆: {sorted(list(g5_set))} -> 命中 {len(g5_set & actual_set)} 码: {sorted(list(g5_set & actual_set))}")
print(f"最优 3 胆: {sorted(list(g3_set))} -> 命中 {len(g3_set & actual_set)} 码: {sorted(list(g3_set & actual_set))}")
print("\n选 2 黄金搭档对账:")
for p in picks["top_pairs"]:
    h = set(p) & actual_set
    print(f"  搭档 {p} -> 命中 {len(h)} 码: {list(h)}")
print("=" * 80)
