# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import Counter
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def analyze_folk_pic1_picks():
    engine = FolkSixteenEngine()
    draws = engine.draws
    
    # 图 1 对应的基准是 2026261 期开奖之后，预测 2026262 期
    idx_262 = next(i for i, x in enumerate(draws) if x['period'] == 2026262)
    draw_262 = draws[idx_262]
    actual_262 = draw_262['nums_set']
    
    # 2026261 期的 16 期窗口
    w_draws = draws[idx_262 - 16 : idx_262]
    fc = Counter()
    for wd in w_draws:
        fc.update(wd['nums'])
        
    last_set = draws[idx_262 - 1]['nums_set']
    outgoing_set = draws[idx_262 - 16]['nums_set']

    # 图 1 中标黄的 20 个号码：
    pic1_yellow_20 = [2, 3, 4, 6, 9, 12, 17, 19, 20, 23, 31, 33, 35, 42, 44, 54, 55, 70, 73, 78]
    
    hits = [n for n in pic1_yellow_20 if n in actual_262]
    misses = [n for n in pic1_yellow_20 if n not in actual_262]
    
    print('=' * 85)
    print(f'🔥 图 1 民间高手 20 码大底 vs 第 2026262 期实开 20 码 深度解密')
    print('=' * 85)
    actual_str = " ".join(f"{x:02d}" for x in sorted(actual_262))
    picks_str = " ".join(f"{x:02d}" for x in sorted(pic1_yellow_20))
    hits_str = " ".join(f"{x:02d}" for x in sorted(hits))
    miss_str = " ".join(f"{x:02d}" for x in sorted(misses))

    print(f'实开号码: {actual_str}')
    print(f'高手推荐: {picks_str}')
    print(f'命中战报: 20 码中 {len(hits)} 码 (命中率: {len(hits)/20*100:.1f}%)！')
    print(f'命中号码 ({len(hits)}个): {hits_str}')
    print(f'未中号码 ({len(misses)}个): {miss_str}')
    print('-' * 85)
    
    # 深入分析这 20 个号码的统计维度：
    # 1. 遗漏分析
    om_dict = {}
    for n in range(1, 81):
        om = 0
        for back_i in range(idx_262 - 1, -1, -1):
            if n in draws[back_i]['nums_set']:
                break
            om += 1
        om_dict[n] = om

    print('【维度 1：遗漏分布】')
    for n in pic1_yellow_20:
        is_hit = '✅命中' if n in actual_262 else '❌未中'
        print(f'  球 {n:02d}: 频次={fc[n]}, 遗漏={om_dict[n]:2d}, 012路={n%3}, 十位={n//10}头, 尾数={n%10}尾, 出窗={n in outgoing_set}, 重号={n in last_set} | {is_hit}')

    # 统计 012 路比
    r0 = sum(1 for n in pic1_yellow_20 if n % 3 == 0)
    r1 = sum(1 for n in pic1_yellow_20 if n % 3 == 1)
    r2 = sum(1 for n in pic1_yellow_20 if n % 3 == 2)
    print(f'\n【维度 2：012 路配比】: 0路 {r0} 码, 1路 {r1} 码, 2路 {r2} 码 (配比: {r0}:{r1}:{r2})')
    
    # 统计尾数分布
    tails = Counter(n % 10 for n in pic1_yellow_20)
    print(f'【维度 3：尾数分布】: {sorted(tails.items())}')
    
    # 统计十位区间分布
    zones = Counter(n // 10 for n in pic1_yellow_20)
    print(f'【维度 4：十位区间分布 (0~7头)】: {sorted(zones.items())}')

    # 统计重号与出窗
    rep_cnt = sum(1 for n in pic1_yellow_20 if n in last_set)
    out_cnt = sum(1 for n in pic1_yellow_20 if n in outgoing_set)
    print(f'【维度 5：重号与出窗】: 上期重号包含 {rep_cnt} 个, 出窗码包含 {out_cnt} 个')

if __name__ == '__main__':
    analyze_folk_pic1_picks()
