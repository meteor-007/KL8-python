# -*- coding: utf-8 -*-
"""KillSeeker 2026174期杀号复盘"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

actual = [61,13,23,25,80,7,30,11,77,18,21,76,31,2,54,53,62,48,69,55]
actual_set = set(actual)

high_kills = [12, 24, 27, 17, 38, 30, 4, 2, 77, 1]
mid_kills = [70, 44, 66, 33, 37, 74, 3, 35, 8, 58]
low_kills = [80, 54, 5, 41, 61]
all_kills = high_kills + mid_kills + low_kills
safe_nums = [29, 28, 48, 13, 42, 78, 14, 34, 45, 76, 15, 43, 60, 53, 57, 26, 64, 65, 52, 22]

high_set = set(high_kills)
mid_set = set(mid_kills)
low_set = set(low_kills)
all_set = set(all_kills)
safe_set = set(safe_nums)

# 杀号命中 = 杀掉的号码没有在开奖中出现
high_hit = len(high_set - actual_set)
mid_hit = len(mid_set - actual_set)
low_hit = len(low_set - actual_set)
all_hit = len(all_set - actual_set)
safe_hit = len(safe_set & actual_set)

high_miss = sorted(high_set & actual_set)
mid_miss = sorted(mid_set & actual_set)
low_miss = sorted(low_set & actual_set)

print("=" * 60)
print("  KillSeeker 2026174期杀号复盘")
print("=" * 60)
print(f"  实际开奖: {'-'.join(f'{n:02d}' for n in sorted(actual))}")
print()
print(f"  高置信杀号: {high_hit}/{len(high_kills)} = {high_hit/len(high_kills)*100:.0f}%")
print(f"    漏杀(实际开出): {'-'.join(f'{n:02d}' for n in high_miss) if high_miss else '无'}")
print(f"  中置信杀号: {mid_hit}/{len(mid_kills)} = {mid_hit/len(mid_kills)*100:.0f}%")
print(f"    漏杀(实际开出): {'-'.join(f'{n:02d}' for n in mid_miss) if mid_miss else '无'}")
print(f"  观察区杀号: {low_hit}/{len(low_kills)} = {low_hit/len(low_kills)*100:.0f}%")
print(f"    漏杀(实际开出): {'-'.join(f'{n:02d}' for n in low_miss) if low_miss else '无'}")
print(f"  全部杀号:   {all_hit}/{len(all_kills)} = {all_hit/len(all_kills)*100:.0f}%")
print(f"  保留号命中: {safe_hit}/{len(safe_nums)} = {safe_hit/len(safe_nums)*100:.0f}%")
