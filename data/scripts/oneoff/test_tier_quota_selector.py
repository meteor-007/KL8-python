# -*- coding: utf-8 -*-
"""
验证真正的民间神技: 能级阶梯配额 (Tier-Quota Selection) 模型
"""
import sys, os
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

engine = FolkSixteenEngine()

def run_tier_quota_selector(base_index: int):
    window_draws = engine.draws[base_index - 15 : base_index + 1]
    outgoing_set = window_draws[0]["nums_set"]
    last_set = window_draws[-1]["nums_set"]
    
    freq_counter = Counter()
    for d in window_draws:
        freq_counter.update(d["nums"])
        
    omissions = {}
    for n in range(1, 81):
        om = 0
        for b in range(base_index, -1, -1):
            if n in engine.draws[b]["nums_set"]:
                break
            om += 1
        omissions[n] = om

    # 桶内评分函数: 核心看 遗漏生态 (0=连庄, 1=隔期, 2=斜连) + 剩余区溢价 + 近邻沾光
    def _in_tier_score(n: int) -> float:
        om = omissions[n]
        is_rep = (n in last_set)
        is_out = (n in outgoing_set)
        
        # 遗漏生态分
        if om == 0:
            om_score = 30.0 # 连庄
        elif om == 1:
            om_score = 35.0 # 隔期跳号 (最高频爆发)
        elif om == 2:
            om_score = 32.0 # 斜连回踩
        elif 3 <= om <= 5:
            om_score = 22.0
        elif 6 <= om <= 9:
            om_score = 16.0
        else:
            om_score = 8.0
            
        # 剩余区大幅领先于出窗区
        rem_score = 15.0 if not is_out else 5.0
        
        # 连开3期防过热惩罚
        consec = 0
        for b in range(base_index, max(-1, base_index - 4), -1):
            if n in engine.draws[b]["nums_set"]:
                consec += 1
            else:
                break
        penalty = 0.50 if consec >= 3 else (0.80 if consec == 2 else 1.0)
        
        return (om_score + rem_score) * penalty

    # 分桶
    tier_balls = {k: [] for k in range(8, 0, -1)}
    for n in range(1, 81):
        f = freq_counter.get(n, 0)
        level = min(f, 8)
        if level >= 1:
            tier_balls[level].append(n)

    # 专家能级配额表:
    # 8次: 1码 (若无合规号可0)
    # 7次: 1码
    # 6次: 3码
    # 5次: 4码
    # 4次: 4码
    # 3次: 2码
    # 1~2次: 1码
    yellow_picks = []
    
    # 8次桶 (配1)
    cands_8 = sorted(tier_balls[8], key=_in_tier_score, reverse=True)
    if cands_8:
        yellow_picks.append(cands_8[0])
        
    # 7次桶 (配1)
    cands_7 = sorted(tier_balls[7], key=_in_tier_score, reverse=True)
    if cands_7:
        yellow_picks.append(cands_7[0])
        
    # 6次桶 (配3)
    cands_6 = sorted(tier_balls[6], key=_in_tier_score, reverse=True)
    yellow_picks.extend(cands_6[:3])
    
    # 5次桶 (配4)
    cands_5 = sorted(tier_balls[5], key=_in_tier_score, reverse=True)
    yellow_picks.extend(cands_5[:4])
    
    # 4次桶 (配4)
    cands_4 = sorted(tier_balls[4], key=_in_tier_score, reverse=True)
    yellow_picks.extend(cands_4[:4])
    
    # 3次桶 (配2)
    cands_3 = sorted(tier_balls[3], key=_in_tier_score, reverse=True)
    yellow_picks.extend(cands_3[:2])
    
    # 1~2次桶 (配1)
    cands_12 = sorted(tier_balls[1] + tier_balls[2], key=_in_tier_score, reverse=True)
    if cands_12:
        yellow_picks.append(cands_12[0])
        
    yellow_picks = sorted(list(set(yellow_picks))[:16])
    
    # 红框金胆: 从 4次、5次、6次 黄金桶中，精挑 遗漏 <= 2 的最强矛头
    border_cands = [n for n in (cands_4 + cands_5 + cands_6) if omissions[n] <= 2]
    border_cands.sort(key=_in_tier_score, reverse=True)
    red_border_core = sorted(border_cands[:6])
    
    # 红底20码: 黄底16码 + 补充4码高分子集
    rem_all = sorted([n for n in range(1, 81) if n not in yellow_picks], key=_in_tier_score, reverse=True)
    red_pool = sorted(yellow_picks + rem_all[: 20 - len(yellow_picks)])
    
    return {
        "red_pool": red_pool,
        "yellow_pool": yellow_picks,
        "red_border_core": red_border_core
    }

# 测试 2026262 期
idx_262 = [i for i, d in enumerate(engine.draws) if d["period"] == 2026262][0]
res_262 = run_tier_quota_selector(idx_262 - 1)
act_262 = engine.draws[idx_262]["nums_set"]
print("=" * 80)
print("【2026262 期能级阶梯配额选拔对账】")
print(f"实开: {sorted(list(act_262))}")
print(f"黄底 16 码: {res_262['yellow_pool']} -> 命中 {len(set(res_262['yellow_pool']) & act_262)} 码: {sorted(list(set(res_262['yellow_pool']) & act_262))}")
print(f"红框核心 {len(res_262['red_border_core'])} 码: {res_262['red_border_core']} -> 命中 {len(set(res_262['red_border_core']) & act_262)} 码: {sorted(list(set(res_262['red_border_core']) & act_262))}")
print(f"红底 20 码: {res_262['red_pool']} -> 命中 {len(set(res_262['red_pool']) & act_262)} 码: {sorted(list(set(res_262['red_pool']) & act_262))}")

# 测试 2026263 期
idx_263 = [i for i, d in enumerate(engine.draws) if d["period"] == 2026263][0]
res_263 = run_tier_quota_selector(idx_263 - 1)
act_263 = engine.draws[idx_263]["nums_set"]
print("\n" + "=" * 80)
print("【2026263 期能级阶梯配额选拔对账】")
print(f"实开: {sorted(list(act_263))}")
print(f"黄底 16 码: {res_263['yellow_pool']} -> 命中 {len(set(res_263['yellow_pool']) & act_263)} 码: {sorted(list(set(res_263['yellow_pool']) & act_263))}")
print(f"红框核心 {len(res_263['red_border_core'])} 码: {res_263['red_border_core']} -> 命中 {len(set(res_263['red_border_core']) & act_263)} 码: {sorted(list(set(res_263['red_border_core']) & act_263))}")
print(f"红底 20 码: {res_263['red_pool']} -> 命中 {len(set(res_263['red_pool']) & act_263)} 码: {sorted(list(set(res_263['red_pool']) & act_263))}")
print("=" * 80)
