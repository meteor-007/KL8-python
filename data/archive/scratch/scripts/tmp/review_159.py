#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026159期复盘计算"""
actual = {66,22,77,70,23,35,56,8,60,5,47,71,26,39,27,4,50,12,58,61}

# 昨日推荐(2026159期)
top5 = [17,18,38,62,64]
top12 = [10,11,12,17,18,29,38,40,62,63,64,77]
he5 = [5,11,29,38,63]
gc = [10,11,12,17,18,29,38,62,63,64]
gauss = [63,11,62,64,12]
cluster = [62,38,27,11,33]
fourier = [49,19,50,28,38]
fusion = [63,38,11,62,19]
pure = [40,24,49,59]
conf5 = [5,11,29,38,51]
conf12 = [5,11,29,38,51,54,63,69,26,76,80,9]
mrmr = [77,38,66,4,17,75,11,10,3,30,54,14]

results = {}
for name, pred in [
    ('三维融合Top5', top5), ('三维融合Top12', top12),
    ('HE5', he5), ('Golden Core', gc),
    ('高斯5', gauss), ('聚类5', cluster), ('傅里叶5', fourier), ('极致整合5', fusion),
    ('纯净池高置信', pure), ('AI置信Top5', conf5), ('AI置信Top12', conf12), ('mRMR', mrmr)
]:
    hit = sorted(set(pred) & actual)
    n = len(pred)
    h = len(hit)
    lift = (h/n) / 0.25 if n > 0 else 0
    results[name] = {'hit': h, 'total': n, 'lift': lift, 'nums': hit}
    print(f"{name}: {h}/{n} Lift={lift:.2f}x 命中号码={hit}")

# 今日点位
points_160 = {2,3,15,16,18,22,30,32,38,42,46,48,52,57,58,60,62,70,78,80}
# 今日推荐
top5_160 = [12,70,71,77,78]
top12_160 = [12,27,38,39,40,49,58,60,70,71,77,78]
he5_160 = [12,17,39,61,80]
gc_160 = [12,27,38,39,49,58,71,77]
gauss_160 = [39,38,40,77,78]
cluster_160 = [62,27,38,11,50]
fourier_160 = [8,63,6,44,59]
fusion_160 = [38,39,41,71,49]
pure_160 = [40,17,53,44]

print("\n=== 今日点位覆盖 ===")
for name, pred in [
    ('Top5', top5_160), ('Top12', top12_160), ('HE5', he5_160),
    ('Golden Core', gc_160), ('高斯5', gauss_160), ('聚类5', cluster_160),
    ('傅里叶5', fourier_160), ('极致整合5', fusion_160), ('纯净池', pure_160)
]:
    overlap = sorted(set(pred) & points_160)
    print(f"{name}: 点位重叠 {len(overlap)}/{len(pred)} = {overlap}")

# 八区分析
print("\n=== 2026159期开奖八区分布 ===")
zones = {i: [] for i in range(8)}
for n in sorted(actual):
    z = (n-1)//10
    zones[z].append(n)
for z in range(8):
    lo, hi = z*10+1, (z+1)*10
    print(f"  Z{z+1}({lo:02d}-{hi:02d}): {len(zones[z])}码 {zones[z]}")

# 尾数分析
print("\n=== 2026159期尾数分布 ===")
tails = {i: [] for i in range(10)}
for n in sorted(actual):
    t = n % 10
    tails[t].append(n)
for t in range(10):
    print(f"  尾{t}: {len(tails[t])}码 {tails[t]}")
