#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026172期复盘对账"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

actual = {4, 5, 11, 16, 17, 19, 20, 26, 37, 44, 46, 47, 51, 55, 61, 63, 66, 68, 70, 75}
print(f"实际开奖({len(actual)}个): {sorted(actual)}")
print()

modules = {
    "三维融合Top5": [21, 31, 32, 33, 40],
    "三维融合Top12": [16, 17, 21, 22, 24, 30, 31, 32, 33, 35, 39, 40],
    "AI核心Top5": [6, 20, 23, 52, 62],
    "AI核心Top12": [6, 20, 23, 52, 62, 72, 16, 31, 33, 39, 41, 73],
    "Hidden Energy 5": [16, 22, 31, 33, 39],
    "Golden Core": [16, 21, 22, 24, 31, 33, 35, 39, 40],
    "高斯扩散5": [32, 31, 33, 30, 34],
    "聚类马尔可夫5": [62, 17, 11, 33, 39],
    "傅里叶5": [17, 30, 24, 37, 39],
    "极致整合5": [17, 33, 39, 31, 30],
    "mRMR12": [66, 71, 39, 38, 33, 17, 12, 57, 2, 56, 54, 63],
    "纯净池高置信": [33, 25, 53, 31, 2, 38, 27, 1],
}

baseline = 0.25
print(f"{'模块':<20} {'命中':<8} {'命中率':<8} {'Lift':<8} 命中号码")
print("=" * 80)
for name, preds in modules.items():
    hits = [n for n in preds if n in actual]
    rate = len(hits) / len(preds)
    lift = rate / baseline
    status = "✅" if lift >= 1.0 else "❌"
    hit_str = str(hits) if hits else "无"
    rate_str = f"{rate:.1%}"
    lift_str = f"{lift:.2f}x"
    print(f"{name:<20} {len(hits)}/{len(preds):<6} {rate_str:<8} {lift_str:<8} {status}  {hit_str}")

print()
print("=== 近期趋势(近10期2026162-2026171) ===")
print("  三维Top5: 8.6%(Lift=0.34x❌)")
print("  三维Top12: 20.2%(Lift=0.81x❌)")
print("  AI Top5: 40.0%(Lift=1.60x✅最佳)")
print("  傅里叶: 34.3%(Lift=1.37x✅次佳)")
print("  HE5: 8.6%(Lift=0.34x❌)")
print()
print("=== 2026172期复盘总结 ===")
print("三维Top5=0/5(Lift=0.00x❌❌) 灾难性")
print("AI Top5=1/5(Lift=0.80x❌)")
print("傅里叶=2/5(Lift=1.60x✅) 唯一亮点")
print("聚类=2/5(Lift=1.60x✅) 并列最佳")
