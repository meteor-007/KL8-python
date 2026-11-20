# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import Counter
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def optimize_and_test():
    engine = FolkSixteenEngine()
    draws = engine.draws

    draws_30 = draws[-30:]

    total_hits_20 = 0
    total_hits_12 = 0
    total_hits_5 = 0
    total_hits_3 = 0

    for d in draws_30:
        p = d['period']
        idx = next(i for i, x in enumerate(draws) if x['period'] == p)
        w_draws = draws[idx - 16 : idx]
        fc = Counter()
        for wd in w_draws:
            fc.update(wd['nums'])
        
        last_nums = draws[idx - 1]['nums_set']
        outgoing_nums = draws[idx - 16]['nums_set']
        
        om_dict = {}
        for n in range(1, 81):
            om = 0
            for back_i in range(idx - 1, -1, -1):
                if n in draws[back_i]['nums_set']:
                    break
                om += 1
            om_dict[n] = om

        # 评分模型：动量 + 遗漏生态平衡
        # 1. 频次权重对齐真实出号概率 (3~5次最高)
        # 2. 遗漏权重：短遗漏 (1~2) 和 连庄 (0) 以及 均值回归 (6+)
        def ball_score(n):
            f = fc.get(n, 0)
            om = om_dict[n]
            is_rep = (n in last_nums)
            is_out = (n in outgoing_nums)

            # 基础频次偏好 (钟形曲线: 3~5次得分最高)
            f_score = {3: 35.0, 4: 40.0, 5: 38.0, 6: 28.0, 2: 25.0, 7: 15.0, 1: 12.0}.get(f, 5.0)
            
            # 遗漏生态分
            if om == 0:
                om_score = 30.0 # 重号
            elif om in [1, 2]:
                om_score = 38.0 # 短遗漏主力
            elif 3 <= om <= 5:
                om_score = 25.0 # 中温
            elif 6 <= om <= 9:
                om_score = 20.0 # 冷号回补区
            else:
                om_score = 5.0  # 极冷号适度防守
                
            out_bonus = 8.0 if (is_out and 3 <= f <= 6) else 0.0
            
            return f_score + om_score + out_bonus

        # 分层配额选 20 码大底：
        # 必须满足遗漏生态约束：重号 <= 5, 短遗漏 7~8, 中温 4~5, 冷号 2~3
        all_sorted = sorted(range(1, 81), key=ball_score, reverse=True)
        
        # 候选池过滤构建
        rep_cands = [n for n in all_sorted if om_dict[n] == 0]
        short_cands = [n for n in all_sorted if om_dict[n] in [1, 2]]
        warm_cands = [n for n in all_sorted if 3 <= om_dict[n] <= 5]
        cold_cands = [n for n in all_sorted if om_dict[n] >= 6]

        grand_20 = []
        grand_20.extend(rep_cands[:4])      # 4 个重号
        grand_20.extend(short_cands[:8])    # 8 个短遗漏 (1~2)
        grand_20.extend(warm_cands[:5])     # 5 个中温号 (3~5)
        grand_20.extend(cold_cands[:3])     # 3 个冷号回补 (>=6)

        # 精选 12 码：从中挑选动量最强的主力 (短遗漏 5 + 重号 2 + 中温 3 + 回补 2)
        elite_12 = []
        elite_12.extend(short_cands[:5])
        elite_12.extend(rep_cands[:2])
        elite_12.extend(warm_cands[:3])
        elite_12.extend(cold_cands[:2])
        
        # 核心 5 胆与 3 胆
        top_in_elite = sorted(elite_12, key=ball_score, reverse=True)
        golden_5 = top_in_elite[:5]
        golden_3 = golden_5[:3]

        actual = d['nums_set']
        h20 = len(set(grand_20).intersection(actual))
        h12 = len(set(elite_12).intersection(actual))
        h5 = len(set(golden_5).intersection(actual))
        h3 = len(set(golden_3).intersection(actual))

        total_hits_20 += h20
        total_hits_12 += h12
        total_hits_5 += h5
        total_hits_3 += h3

    print(f"优化后 30 期样本外盲测决算:")
    print(f"  20码大底: 均期中 {total_hits_20/30:.2f} 码 (单码率: {total_hits_20/(30*20)*100:.1f}%)")
    print(f"  12码精选: 均期中 {total_hits_12/30:.2f} 码 (单码率: {total_hits_12/(30*12)*100:.1f}%)")
    print(f"  5码金胆:  均期中 {total_hits_5/30:.2f} 码 (单码率: {total_hits_5/(30*5)*100:.1f}%)")
    print(f"  3码最优:  均期中 {total_hits_3/30:.2f} 码 (单码率: {total_hits_3/(30*3)*100:.1f}%)")

if __name__ == '__main__':
    optimize_and_test()
