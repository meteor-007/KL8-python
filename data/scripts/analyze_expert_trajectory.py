# -*- coding: utf-8 -*-
"""
深入解剖: 专家选出的 11 个红框号 (命中 10 个) vs 其余 69 个号码的全部统计差异!
找准专家的真正选号秘诀!
"""
import sys, os
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

engine = FolkSixteenEngine()
idx_262 = [i for i, d in enumerate(engine.draws) if d["period"] == 2026262][0]
base_idx = idx_262 - 1
base_draw = engine.draws[base_idx]

expert_picks = [4, 13, 17, 33, 42, 44, 49, 54, 59, 61, 80]
actual_262 = engine.draws[idx_262]["nums_set"]

window_16 = engine.draws[base_idx - 15 : base_idx + 1]
outgoing_set = window_16[0]["nums_set"]
last_set = base_draw["nums_set"]

# 上上期号码 (base - 1)
prev2_set = engine.draws[base_idx - 1]["nums_set"]
# 上上上期 (base - 2)
prev3_set = engine.draws[base_idx - 2]["nums_set"]

print("=" * 80)
print(f"基准期 2026261 开出号码: {sorted(list(last_set))}")
print(f"上上期 2026260 开出号码: {sorted(list(prev2_set))}")
print(f"上上上期 2026259 开出号码: {sorted(list(prev3_set))}")
print(f"16期前出窗号码: {sorted(list(outgoing_set))}")
print("=" * 80)

# 对比这 11 个号码在近几期的开出轨迹:
print(f"{'Num':>4}  {'Hit?':>5}  {'上期':>5}  {'上上期':>6}  {'上3期':>6}  {'出窗':>5}  {'近16频':>6}  {'邻号?':>8}")
for n in expert_picks:
    is_hit = "YES" if n in actual_262 else "no"
    in_last = "是" if n in last_set else "否"
    in_prev2 = "是" if n in prev2_set else "否"
    in_prev3 = "是" if n in prev3_set else "否"
    in_out = "是" if n in outgoing_set else "否"
    freq = sum(1 for d in window_16 if n in d["nums_set"])
    
    # 是否是上期开出号的邻号 (左邻右舍 n-1, n+1)?
    is_neighbor = "是" if ((n-1 in last_set) or (n+1 in last_set)) else "否"
    
    print(f"{n:>4}  {is_hit:>5}  {in_last:>5}  {in_prev2:>6}  {in_prev3:>6}  {in_out:>5}  {freq:>6}  {is_neighbor:>8}")
