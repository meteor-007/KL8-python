# -*- coding: utf-8 -*-
"""
跟随策略多窗口样本外对账回测
"""
import os
import re
from collections import Counter

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORY_FILE = os.path.join(PROJ_DIR, "storage", "raw", "kl8_history_final.txt")

draws = []
with open(HISTORY_FILE, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line)
        if m:
            nums = [int(x) for x in m.group(3).split("-") if x.isdigit()]
            if len(nums) == 20:
                draws.append({
                    "period": int(m.group(2)),
                    "nums_set": set(nums),
                    "nums": sorted(nums)
                })

draws.sort(key=lambda x: x["period"])

test_len = 200
test_start = len(draws) - test_len
p_start = draws[test_start]["period"]
p_end = draws[-1]["period"]
print(f"=== 样本外滚动回测 {test_len} 期 (第 {p_start} 期 ~ 第 {p_end} 期) ===")
print("随机盲猜基准命中率: 25.0%\n")

# 测试不同窗口
windows = [
    ("全量历史(2000期)", None),
    ("500期窗口", 500),
    ("200期窗口", 200),
    ("100期窗口", 100),
    ("70期窗口", 70),
    ("30期窗口", 30),
]

for label, win in windows:
    hits_top3 = 0
    total_top3 = 0
    hits_top5 = 0
    total_top5 = 0
    
    for t in range(test_start, len(draws) - 1):
        actual_next = draws[t + 1]["nums_set"]
        train = draws[:t + 1] if win is None else draws[max(0, t + 1 - win) : t + 1]
        last_nums = draws[t]["nums_set"]
        
        follow_cnt = Counter()
        for idx in range(len(train) - 1):
            cur_s = train[idx]["nums_set"]
            nxt_s = train[idx + 1]["nums"]
            overlap = cur_s & last_nums
            for x in overlap:
                for y in nxt_s:
                    follow_cnt[y] += 1
                    
        mc = follow_cnt.most_common(5)
        top3 = [num for num, _ in mc[:3]]
        top5 = [num for num, _ in mc[:5]]
        
        hits_top3 += len(set(top3) & actual_next)
        total_top3 += len(top3)
        hits_top5 += len(set(top5) & actual_next)
        total_top5 += len(top5)
        
    rate_top3 = hits_top3 / total_top3 * 100
    rate_top5 = hits_top5 / total_top5 * 100
    lift_3 = rate_top3 / 25.0
    lift_5 = rate_top5 / 25.0
    print(f"[{label:16s}] Top3命中率: {rate_top3:.2f}% (提升度 {lift_3:.2f}x) | Top5命中率: {rate_top5:.2f}% (提升度 {lift_5:.2f}x)")
