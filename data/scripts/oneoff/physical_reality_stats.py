# -*- coding: utf-8 -*-
"""
Physical Reality: What frequency numbers ACTUALLY get drawn?
Statistics over 50 periods to build the TRUE frequency->hit-rate mapping.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine
from collections import Counter, defaultdict

engine = FolkSixteenEngine()
total = len(engine.draws)
N = 50

freq_hit_counts = defaultdict(lambda: {"total": 0, "hits": 0})
omission_hit_counts = defaultdict(lambda: {"total": 0, "hits": 0})
repeat_actual_counts = []
remaining_hit_counts = []
outgoing_hit_counts = []
road_distributions = []

for i in range(total - N, total):
    actual_set = engine.draws[i]["nums_set"]
    last_set = engine.draws[i-1]["nums_set"]
    
    # Build 16-period window BEFORE this draw
    base_idx = i - 1
    if base_idx < 15:
        continue
    window = engine.draws[base_idx - 15 : base_idx + 1]
    outgoing_set = set(window[0]["nums"])
    
    freq_counter = Counter()
    for d in window:
        freq_counter.update(d["nums"])
    
    # Omission calculation
    omission = {}
    for n in range(1, 81):
        om = 0
        for back in range(base_idx, -1, -1):
            if n in engine.draws[back]["nums_set"]:
                break
            om += 1
        omission[n] = om
    
    # Stats per ball
    actual_repeats = 0
    actual_from_remaining = 0
    actual_from_outgoing = 0
    actual_roads = Counter()
    
    for n in range(1, 81):
        f = freq_counter.get(n, 0)
        om = omission[n]
        is_out = n in outgoing_set
        is_hit = n in actual_set
        is_rep = n in last_set
        
        freq_hit_counts[f]["total"] += 1
        if is_hit:
            freq_hit_counts[f]["hits"] += 1
        
        om_bucket = min(om, 20)
        omission_hit_counts[om_bucket]["total"] += 1
        if is_hit:
            omission_hit_counts[om_bucket]["hits"] += 1
    
    for n in actual_set:
        if n in last_set:
            actual_repeats += 1
        if n in outgoing_set:
            actual_from_outgoing += 1
        else:
            actual_from_remaining += 1
        actual_roads[n % 3] += 1
    
    repeat_actual_counts.append(actual_repeats)
    remaining_hit_counts.append(actual_from_remaining)
    outgoing_hit_counts.append(actual_from_outgoing)
    road_distributions.append((actual_roads.get(0,0), actual_roads.get(1,0), actual_roads.get(2,0)))

print("=" * 80)
print(f"  50-Period Physical Reality Statistics")
print("=" * 80)

print("\n--- Frequency -> Actual Hit Rate (per ball) ---")
print(f"{'Freq':>6}  {'Count':>8}  {'Hits':>6}  {'Rate':>8}  {'Lift':>6}")
baseline = 20/80  # 25%
for f in range(0, 17):
    d = freq_hit_counts[f]
    if d["total"] > 0:
        rate = d["hits"] / d["total"]
        lift = rate / baseline
        print(f"{f:>6}  {d['total']:>8}  {d['hits']:>6}  {rate:>7.1%}  {lift:>5.2f}x")

print("\n--- Omission -> Actual Hit Rate (per ball) ---")
print(f"{'Omiss':>6}  {'Count':>8}  {'Hits':>6}  {'Rate':>8}")
for om in range(0, 21):
    d = omission_hit_counts[om]
    if d["total"] > 0:
        rate = d["hits"] / d["total"]
        print(f"{om:>6}  {d['total']:>8}  {d['hits']:>6}  {rate:>7.1%}")

print(f"\n--- Repeat Numbers (from last draw, actual) ---")
print(f"  Average: {sum(repeat_actual_counts)/len(repeat_actual_counts):.2f}")
print(f"  Min: {min(repeat_actual_counts)}, Max: {max(repeat_actual_counts)}")
print(f"  Distribution: {Counter(repeat_actual_counts).most_common()}")

print(f"\n--- Remaining vs Outgoing (actual) ---")
print(f"  Remaining avg: {sum(remaining_hit_counts)/len(remaining_hit_counts):.2f}")
print(f"  Outgoing avg: {sum(outgoing_hit_counts)/len(outgoing_hit_counts):.2f}")

print(f"\n--- 012 Road Distribution (actual) ---")
r0_avg = sum(r[0] for r in road_distributions) / len(road_distributions)
r1_avg = sum(r[1] for r in road_distributions) / len(road_distributions)
r2_avg = sum(r[2] for r in road_distributions) / len(road_distributions)
print(f"  0-road avg: {r0_avg:.1f}, 1-road avg: {r1_avg:.1f}, 2-road avg: {r2_avg:.1f}")
r0_range = [min(r[0] for r in road_distributions), max(r[0] for r in road_distributions)]
r1_range = [min(r[1] for r in road_distributions), max(r[1] for r in road_distributions)]
r2_range = [min(r[2] for r in road_distributions), max(r[2] for r in road_distributions)]
print(f"  0-road range: {r0_range}, 1-road range: {r1_range}, 2-road range: {r2_range}")
