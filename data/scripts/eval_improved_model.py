# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import Counter, defaultdict
import math
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def calc_energy(history_draws_desc):
    # history_draws_desc 是降序 (最新在前)
    field = {n: 0.0 for n in range(1, 81)}
    decay_rate = 0.85
    diffusion_factor = 0.35
    for i, d in enumerate(history_draws_desc[:16]):
        w = (decay_rate ** i)
        for n in d['nums']:
            field[n] += w
            if n + 1 <= 80:
                field[n + 1] += w * diffusion_factor * 0.5
            if n - 1 >= 1:
                field[n - 1] += w * diffusion_factor * 0.5
    return field

def main():
    engine = FolkSixteenEngine()
    draws = engine.draws
    draws_30 = draws[-30:]

    tot_r, tot_y, tot_b, tot_g3, tot_p_hit, tot_p = 0, 0, 0, 0, 0, 0
    tot_b_len = 0

    for d in draws_30:
        p = d['period']
        idx = next(i for i, x in enumerate(draws) if x['period'] == p)
        # 严格屏蔽未来数据: 仅使用 idx 之前的数据
        hist_before = draws[:idx] # 升序
        hist_desc = list(reversed(hist_before))
        
        # 16期窗口
        w_draws = hist_before[-16:]
        fc = Counter()
        for wd in w_draws:
            fc.update(wd['nums'])
            
        last_nums = hist_before[-1]['nums_set']
        outgoing_nums = hist_before[-16]['nums_set']

        om_dict = {}
        for n in range(1, 81):
            om = 0
            for back_i in range(len(hist_before) - 1, -1, -1):
                if n in hist_before[back_i]['nums_set']:
                    break
                om += 1
            om_dict[n] = om

        energy = calc_energy(hist_desc)

        # 针对每个号码的综合能量得分
        scores = {}
        for n in range(1, 81):
            f = fc.get(n, 0)
            om = om_dict[n]
            e = energy[n]
            is_rep = (n in last_nums)
            is_out = (n in outgoing_nums)

            # 频次分 (3~5次黄金中热优先)
            f_score = {3: 35.0, 4: 42.0, 5: 38.0, 6: 28.0, 2: 24.0, 7: 15.0, 1: 10.0}.get(f, 5.0)

            # 遗漏生态分
            if om == 0:
                om_score = 28.0
            elif om in [1, 2]:
                om_score = 38.0
            elif 3 <= om <= 5:
                om_score = 25.0
            elif 6 <= om <= 9:
                om_score = 20.0
            else:
                om_score = 8.0

            # 出窗抗跌加分 (中热球处于出窗边缘，往往强力回补保住频次)
            out_bonus = 10.0 if (is_out and 3 <= f <= 6) else 0.0

            # 均值回归反过热惩罚 (近3期开出3次的，火过头必须降权)
            recent_3_hits = sum(1 for h in hist_desc[:3] if n in h['nums_set'])
            penalty = 0.7 if recent_3_hits >= 3 else 1.0

            total_s = (f_score + om_score + e * 8.0 + out_bonus) * penalty
            scores[n] = total_s

        # 选号：
        # 1. 20 码大底 (红底): 满足严格遗漏生态配比 (重号 4, 短遗漏 8, 中温 5, 冷号 3)
        sorted_all = sorted(range(1, 81), key=lambda x: scores[x], reverse=True)
        rep_cands = [n for n in sorted_all if om_dict[n] == 0]
        short_cands = [n for n in sorted_all if om_dict[n] in [1, 2]]
        warm_cands = [n for n in sorted_all if 3 <= om_dict[n] <= 5]
        cold_cands = [n for n in sorted_all if om_dict[n] >= 6]

        red_pool = []
        red_pool.extend(rep_cands[:4])
        red_pool.extend(short_cands[:8])
        red_pool.extend(warm_cands[:5])
        red_pool.extend(cold_cands[:3])

        # 2. 16 码精选 (黄底): 进攻冲锋队，侧重短遗漏和高动量
        yellow_pool = sorted_all[:16]

        # 3. 红框共振金胆: 红底 ∩ 黄底
        border_core = [n for n in red_pool if n in yellow_pool]
        if len(border_core) < 5:
            extra = [n for n in red_pool if n not in border_core]
            extra.sort(key=lambda x: scores[x], reverse=True)
            border_core = sorted(border_core + extra[:5 - len(border_core)])

        # 4. 最优 3 胆
        sorted_border = sorted(border_core, key=lambda x: scores[x], reverse=True)
        g3 = sorted_border[:3]

        # 5. 选 2 搭档
        pair_candidates = [
            [sorted_border[0], sorted_border[1]],
            [sorted_border[0], sorted_border[2]],
            [sorted_border[1], sorted_border[3] if len(sorted_border) > 3 else sorted_border[2]]
        ]

        actual = d['nums_set']
        r_hit = len(set(red_pool).intersection(actual))
        y_hit = len(set(yellow_pool).intersection(actual))
        b_hit = len(set(border_core).intersection(actual))
        g3_hit = len(set(g3).intersection(actual))

        tot_r += r_hit
        tot_y += y_hit
        tot_b += b_hit
        tot_b_len += len(border_core)
        tot_g3 += g3_hit

        for p_cand in pair_candidates:
            tot_p += 1
            if p_cand[0] in actual and p_cand[1] in actual:
                tot_p_hit += 1

    print('=' * 85)
    print('🔥 融合生态配比与反过热惩罚后——最近 30 期严格屏蔽未来数据 (Walk-Forward) 决算')
    print('=' * 85)
    print(f'1. 🔴 红底20码大底: 均期命中 {tot_r/30:.2f} 码 (单码率: {tot_r/(30*20)*100:.1f}%)')
    print(f'2. 🟡 黄底16码精选: 均期命中 {tot_y/30:.2f} 码 (单码率: {tot_y/(30*16)*100:.1f}%)')
    print(f'3. 🔲 红框共振金胆: 均期命中 {tot_b/30:.2f} 码 (单码率: {tot_b/tot_b_len*100:.1f}%)')
    print(f'4. ⚡ 最优 3 胆突破: 均期命中 {tot_g3/30:.2f} 码 (单码率: {tot_g3/(30*3)*100:.1f}%)')
    print(f'5. 💎 选2双中对数:  {tot_p} 组中双中 {tot_p_hit} 组 (双全中率: {tot_p_hit/tot_p*100:.1f}%, 随机基准约 6.0%)')
    print('=' * 85)

if __name__ == '__main__':
    main()
