# -*- coding: utf-8 -*-
"""
黄金能级 (4~6次) 核心战法模拟器:
1. 聚焦 4~6 次生命周期
2. 4个4~6次优质重号 (避开7~8次过热重号)
3. 隔期跳号 (遗漏1)
4. 强邻号 (与上期号码相邻±1)
5. 出窗抗跌号
"""
import sys, os
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

engine = FolkSixteenEngine()

def run_golden_midhot_strategy(base_idx: int):
    base_draw = engine.draws[base_idx]
    target_period = engine.draws[base_idx + 1]["period"]
    actual_set = engine.draws[base_idx + 1]["nums_set"]
    
    window_16 = engine.draws[base_idx - 15 : base_idx + 1]
    outgoing_set = window_16[0]["nums_set"]
    last_set = base_draw["nums_set"]
    prev2_set = engine.draws[base_idx - 1]["nums_set"]
    
    freq_counter = Counter()
    for d in window_16:
        freq_counter.update(d["nums"])
        
    omissions = {}
    for n in range(1, 81):
        om = 0
        for b in range(base_idx, -1, -1):
            if n in engine.draws[b]["nums_set"]:
                break
            om += 1
        omissions[n] = om

    # 1. 优质重号 (从 last_set 中选, 必须 freq 在 [4, 6] 之间, 坚决不选 freq >= 7 的过载号)
    rep_candidates = [n for n in last_set if 4 <= freq_counter[n] <= 6]
    # 按照频次与近邻活跃度排序
    rep_picks = sorted(rep_candidates, key=lambda n: (freq_counter[n], -omissions[n]), reverse=True)[:4]
    
    # 2. 隔期跳号 (在 prev2_set 中, 但不在 last_set 中, 且 freq 在 [3, 6] 之间)
    jump_candidates = [n for n in prev2_set if n not in last_set and 3 <= freq_counter[n] <= 6 and omissions[n] == 1]
    
    # 3. 出窗抗跌码 (在 outgoing_set 中, 且 freq 在 [5, 6] 之间)
    out_candidates = [n for n in outgoing_set if 5 <= freq_counter[n] <= 6]
    
    # 4. 强邻号 (不是重号, 与 last_set 中某个号码差为 ±1, 且 freq 在 [3, 6] 之间)
    neighbor_candidates = []
    for n in range(1, 81):
        if n not in last_set and 3 <= freq_counter[n] <= 6:
            if (n - 1 in last_set) or (n + 1 in last_set):
                neighbor_candidates.append(n)
                
    # 综合打分排序
    def _score(n: int) -> float:
        f = freq_counter[n]
        om = omissions[n]
        is_rep = n in last_set
        is_jump = (om == 1 and n in prev2_set)
        is_out = n in outgoing_set
        is_neigh = (n - 1 in last_set) or (n + 1 in last_set)
        
        # 基础分: 4次与5次最高
        s = 0.0
        if f in [4, 5]:
            s += 40.0
        elif f == 6:
            s += 35.0
        elif f == 3:
            s += 25.0
        else:
            s += 10.0
            
        if is_rep and 4 <= f <= 6:
            s += 35.0  # 4~6次优质连庄极大加分
        if is_jump:
            s += 32.0  # 隔期跳号极大加分
        if is_out and 5 <= f <= 6:
            s += 28.0  # 出窗抗跌
        if is_neigh:
            s += 20.0  # 强邻号加分
            
        if om == 2:
            s += 15.0  # 斜连号
        elif 3 <= om <= 6:
            s += 10.0
            
        return s

    all_scored = sorted(range(1, 81), key=_score, reverse=True)
    
    # 选 11 码核心共振金胆
    top_11 = sorted(all_scored[:11])
    # 选 16 码黄底
    top_16 = sorted(all_scored[:16])
    # 选 20 码大底 (兼顾012路平衡)
    top_20 = sorted(all_scored[:20])
    
    hit_11 = len(set(top_11) & actual_set)
    hit_16 = len(set(top_16) & actual_set)
    hit_20 = len(set(top_20) & actual_set)
    
    return {
        "period": target_period,
        "top_11": top_11,
        "hit_11": hit_11,
        "top_16": top_16,
        "hit_16": hit_16,
        "top_20": top_20,
        "hit_20": hit_20,
        "actual": sorted(list(actual_set))
    }

for p in [2026262, 2026263]:
    idx = [i for i, d in enumerate(engine.draws) if d["period"] == p][0]
    res = run_golden_midhot_strategy(idx - 1)
    print("=" * 80)
    print(f"期号 {res['period']} 实开: {res['actual']}")
    print(f"核心 11 胆: {res['top_11']} -> 命中 {res['hit_11']} 码 ({res['hit_11']/11:.1%}): {sorted(list(set(res['top_11']) & set(res['actual'])))}")
    print(f"精选 16 码: {res['top_16']} -> 命中 {res['hit_16']} 码 ({res['hit_16']/16:.1%}): {sorted(list(set(res['top_16']) & set(res['actual'])))}")
    print(f"大底 20 码: {res['top_20']} -> 命中 {res['hit_20']} 码 ({res['hit_20']/20:.1%}): {sorted(list(set(res['top_20']) & set(res['actual'])))}")
