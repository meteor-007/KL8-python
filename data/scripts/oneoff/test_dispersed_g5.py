# -*- coding: utf-8 -*-
"""
测试 golden_5 区间离散与重号协同约束对 30 期命中率的影响
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

engine = FolkSixteenEngine()
total = len(engine.draws)
N_TEST = 30
test_start = total - N_TEST

hits_standard = []
hits_dispersed = []

for i in range(test_start, total):
    res = engine.analyze_window(target_period=engine.draws[i]["period"])
    actual = res["hit_audit"]["actual_draw"]
    actual_set = set(actual)
    border = res["picks"]["red_border_core"]
    profiles = res["ball_profiles"]
    
    # 方案 1: 原纯得分排序
    # (先按分数排序取 top 5)
    # 取分析结果现有的 golden_5
    g5_std = res["picks"]["golden_5"]
    hits_standard.append(len(set(g5_std) & actual_set))
    
    # 方案 2: 区间离散优选 (每个十位区间最多容纳 1 码，不足时再放宽到 2 码)
    # 按照分数降序遍历 border
    # 模拟分数
    cands = sorted(border, key=lambda n: profiles[n]["freq"] + (10 if profiles[n]["is_repeat"] else 0) - profiles[n]["omission"], reverse=True)
    g5_new = []
    zone_count = {}
    for c in cands:
        z = (c - 1) // 10 + 1
        if zone_count.get(z, 0) < 1:
            g5_new.append(c)
            zone_count[z] = zone_count.get(z, 0) + 1
            if len(g5_new) == 5:
                break
    if len(g5_new) < 5:
        for c in cands:
            if c not in g5_new:
                g5_new.append(c)
                if len(g5_new) == 5:
                    break
    hits_dispersed.append(len(set(g5_new) & actual_set))

print(f"原 golden_5 30期总命中: {sum(hits_standard)} 码, 均期 {sum(hits_standard)/N_TEST:.2f} 码 ({sum(hits_standard)/N_TEST/5:.1%})")
print(f"离散优化后 30期总命中: {sum(hits_dispersed)} 码, 均期 {sum(hits_dispersed)/N_TEST:.2f} 码 ({sum(hits_dispersed)/N_TEST/5:.1%})")
