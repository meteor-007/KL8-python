# -*- coding: utf-8 -*-
"""
深度诊断: 每期红底20码 vs 实际开奖, 逐号对比打分排名
看看被选中但没中的号 vs 没选但实际开出的号，打分差在哪
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

engine = FolkSixteenEngine()
total = len(engine.draws)

# 取最近5期详细诊断
for i in range(total - 5, total):
    target_period = engine.draws[i]["period"]
    actual_set = engine.draws[i]["nums_set"]
    result = engine.analyze_window(target_period=target_period)
    picks = result["picks"]
    red_pool_set = set(picks["red_pool"])
    profiles = result["ball_profiles"]
    
    # 上一期号码
    last_set = engine.draws[i-1]["nums_set"]
    
    # 中了但没选的 (漏选号码)
    missed = sorted(actual_set - red_pool_set)
    # 选了但没中的 (虚选号码)
    wasted = sorted(red_pool_set - actual_set)
    # 命中号码
    hit_nums = sorted(red_pool_set & actual_set)
    
    print(f"\n{'='*100}")
    print(f"期号 {target_period}  |  实开: {sorted(actual_set)}  |  红底20: {sorted(red_pool_set)}")
    print(f"  命中 {len(hit_nums)} 码: {hit_nums}")
    print(f"  漏选 {len(missed)} 码: {missed}")
    print(f"  虚选 {len(wasted)} 码: {wasted}")
    
    # 分析漏选号码的特征
    print(f"\n  --- 漏选号码特征分析 (这些号码开出了但我们没选) ---")
    for n in missed[:10]:
        p = profiles[n]
        rep_flag = "连庄" if n in last_set else "非连"
        out_flag = "出窗" if p["is_outgoing"] else "剩余"
        print(f"    {n:02d}  freq={p['freq']}  遗漏={p['omission']}  {out_flag}  {rep_flag}  012路={p['r012']}  区间={p['zone']}")
    
    # 分析虚选号码的特征
    print(f"\n  --- 虚选号码特征分析 (选了但没开出) ---")
    for n in wasted[:10]:
        p = profiles[n]
        rep_flag = "连庄" if n in last_set else "非连"
        out_flag = "出窗" if p["is_outgoing"] else "剩余"
        print(f"    {n:02d}  freq={p['freq']}  遗漏={p['omission']}  {out_flag}  {rep_flag}  012路={p['r012']}  区间={p['zone']}")
    
    # 关键统计
    missed_from_remaining = [n for n in missed if not profiles[n]["is_outgoing"]]
    missed_repeats = [n for n in missed if n in last_set]
    wasted_repeats = [n for n in wasted if n in last_set]
    print(f"\n  漏选中来自剩余区: {len(missed_from_remaining)}/{len(missed)}")
    print(f"  漏选中是重号: {len(missed_repeats)}/{len(missed)}")
    print(f"  虚选中是重号: {len(wasted_repeats)}/{len(wasted)}")
    
    # 漏选号码的频次分布
    from collections import Counter
    missed_freq = Counter(profiles[n]["freq"] for n in missed)
    wasted_freq = Counter(profiles[n]["freq"] for n in wasted)
    print(f"  漏选号频次分布: {dict(sorted(missed_freq.items()))}")
    print(f"  虚选号频次分布: {dict(sorted(wasted_freq.items()))}")
