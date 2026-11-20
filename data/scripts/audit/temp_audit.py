# -*- coding: utf-8 -*-
import sys, re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

actual_draw = [19, 23, 25, 34, 39, 42, 43, 44, 45, 48, 53, 54, 56, 57, 62, 73, 74, 75, 77, 78]
actual_set = set(actual_draw)

print(f"=== 昨晚第 2026293 期真实开奖 20 码 ===")
print(" ".join(f"{x:02d}" for x in actual_draw))
print("-" * 75)

report_path = "storage/reports/全模块预测明细_2026293.md"
with open(report_path, "r", encoding="utf-8") as f:
    text = f.read()

# 拆分所有模块
sections = re.split(r"\n###\s+", text)
results = []
for sec in sections[1:]:
    lines = sec.strip().splitlines()
    header = lines[0].strip()
    for line in lines[1:]:
        if any(k in line for k in ["码：", "Top", "大底", "搭档", "最优 3 码", "金胆", "防线", "主力池", "精选中底"]):
            # 提取反引号或粗体中的号码
            m = re.findall(r"`([0-9\s]+)`", line)
            for raw in m:
                nums = [int(x) for x in re.findall(r"\b([0-7][0-9]|80)\b", raw)]
                if nums and len(nums) <= 30:
                    nums = list(dict.fromkeys(nums))
                    hits = [n for n in nums if n in actual_set]
                    rate = len(hits) / len(nums) * 100 if nums else 0.0
                    lift = rate / 25.0
                    results.append((header, line.split("`")[0].strip(), nums, hits, rate, lift))

seen = set()
for h, title, nums, hits, rate, lift in results:
    key = (h, title, tuple(nums))
    if key in seen:
        continue
    seen.add(key)
    hits_str = " ".join(f"{x:02d}" for x in hits) if hits else "0中"
    nums_str = " ".join(f"{x:02d}" for x in nums)
    print(f"{h[:18]:<18} | {title[:28]:<28} | 推荐{len(nums):2d}码 命中{len(hits):2d}码 [{hits_str}] | 胜率: {rate:5.1f}% (Lift:{lift:4.2f}x)")
