# -*- coding: utf-8 -*-
import sys, re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

actual_draw = [3, 7, 10, 16, 21, 25, 29, 33, 35, 43, 45, 52, 58, 60, 64, 68, 69, 72, 76, 80]
actual_set = set(actual_draw)

print("=== 昨晚第 2026294 期真实开奖 20 码 ===")
print(" ".join(f"{x:02d}" for x in actual_draw))
print("-" * 80)

report_path = "storage/reports/全模块预测明细_2026294.md"
with open(report_path, "r", encoding="utf-8") as f:
    text = f.read()

sections = re.split(r"\n###\s+", text)
results = []
for sec in sections[1:]:
    lines = sec.strip().splitlines()
    header = lines[0].strip()
    for line in lines[1:]:
        if any(k in line for k in ["码：", "Top", "大底", "搭档", "最优 3 码", "金胆", "防线", "主力池", "精选中底", "阵容"]):
            m = re.findall(r"`([0-9\s]+)`", line)
            for raw in m:
                nums = [int(x) for x in re.findall(r"\b([0-7][0-9]|80)\b", raw)]
                if nums and len(nums) <= 30:
                    nums = list(dict.fromkeys(nums))
                    hits = [n for n in nums if n in actual_set]
                    rate = len(hits) / len(nums) * 100 if nums else 0.0
                    lift = rate / 25.0
                    title_part = line.split("`")[0].strip() if "`" in line else line.strip()
                    results.append((header, title_part, nums, hits, rate, lift))

seen = set()
for h, title, nums, hits, rate, lift in results:
    key = (h, title, tuple(nums))
    if key in seen:
        continue
    seen.add(key)
    hits_str = " ".join(f"{x:02d}" for x in hits) if hits else "0中"
    nums_str = " ".join(f"{x:02d}" for x in nums)
    print(f"{h[:18]:<18} | {title[:28]:<28} | 推荐{len(nums):2d} 命中{len(hits):2d} [{hits_str:<18}] | 胜率: {rate:5.1f}% (Lift:{lift:4.2f}x)")
