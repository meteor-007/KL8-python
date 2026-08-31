#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026161期复盘计算"""
actual = set([62,43,76,50,30,51,23,57,74,2,35,28,49,39,44,69,15,14,60,53])

# 昨日(20260620报告)对2026161期的推荐
top5 = set([38,40,47,60,77])
top12 = set([38,39,40,47,56,58,60,70,71,76,77,80])
ai5 = set([28,4,15,26,38])
ai12 = set([28,4,15,26,38,55,56,60,69,23,11,47])
he5 = set([4,38,47,60,76])
gc = set([38,39,47,58,77])
pure = set([53,38])
gauss5 = set([39,40,38,77,76])
cluster5 = set([14,11,38,28,71])
fourier5 = set([17,57,37,32,45])
fusion5 = set([38,71,75,57,14])
mrmr12 = set([77,38,66,17,75,4,3,11,10,54,12,69])

def calc(name, recommended, actual_set):
    hit = sorted(recommended & actual_set)
    n = len(recommended)
    h = len(hit)
    rate = h/n*100
    lift = rate/25.0
    return f"{name}: 命中{hit} → {h}/{n}={rate:.1f}% Lift={lift:.2f}x"

print("=" * 70)
print("  2026161期 复盘对账表 (data目录主分析)")
print("=" * 70)
print(f"实际开奖: {sorted(actual)}")
print()
print(calc("三维融合Top5", top5, actual))
print(calc("三维融合Top12", top12, actual))
print(calc("传统AI Top5", ai5, actual))
print(calc("传统AI Top12", ai12, actual))
print(calc("Hidden Energy 5", he5, actual))
print(calc("Golden Core", gc, actual))
print(f"纯净池高置信: 命中{sorted(pure & actual)} → {len(pure & actual)}/2={len(pure & actual)/2*100:.1f}%")
print(calc("高斯5", gauss5, actual))
print(calc("聚类5", cluster5, actual))
print(calc("傅里叶5", fourier5, actual))
print(calc("极致整合5", fusion5, actual))
print(calc("mRMR Top12", mrmr12, actual))
