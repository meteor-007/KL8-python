# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
sys.path.insert(0, os.path.abspath("."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def main():
    engine = FolkSixteenEngine()
    draws = engine.draws

    # 取最近 10 期进行逐期盲测（严格只用开奖前数据）
    recent_10 = draws[-10:]

    print('=' * 85)
    print('🔥 最近 10 期严格屏蔽未来数据 (Walk-Forward Blind Testing) 实战对账单')
    print('   【机制保证】：推演第 N 期时，算法只能看到 N-1 期及更早开奖，绝不触碰第 N 期开奖')
    print('=' * 85)

    total_red_hits = 0
    total_yellow_hits = 0
    total_border_hits = 0
    total_border_size = 0
    total_g3_hits = 0
    pair_hit_count = 0
    total_pairs_tested = 0

    for d in recent_10:
        p_val = d['period']
        res = engine.analyze_window(target_period=p_val)
        audit = res['hit_audit']
        actual = audit['actual_draw']
        
        red_pool = res['picks']['red_pool']
        yellow_pool = res['picks']['yellow_pool']
        border_core = res['picks']['red_border_core']
        g3 = res['picks']['golden_3']
        pairs = res['picks']['top_pairs']
        
        r_hits = audit['red_pool_hits']
        y_hits = audit['yellow_pool_hits']
        b_hits = audit['red_border_hits']
        g3_hits = [x for x in g3 if x in actual]
        
        p_hits_this = []
        for pair in pairs:
            total_pairs_tested += 1
            is_both = (pair[0] in actual and pair[1] in actual)
            if is_both:
                pair_hit_count += 1
                p_hits_this.append(pair)
                
        total_red_hits += len(r_hits)
        total_yellow_hits += len(y_hits)
        total_border_hits += len(b_hits)
        total_border_size += len(border_core)
        total_g3_hits += len(g3_hits)
        
        print(f"【第 {p_val} 期】实开: {' '.join(f'{x:02d}' for x in sorted(actual))}")
        print(f"  🔴 红底20码大底: 中 {len(r_hits):2d} / 20 码 ({len(r_hits)/20*100:4.1f}%) -> 命中: {' '.join(f'{x:02d}' for x in r_hits)}")
        print(f"  🟡 黄底16码精选: 中 {len(y_hits):2d} / 16 码 ({len(y_hits)/16*100:4.1f}%) -> 命中: {' '.join(f'{x:02d}' for x in y_hits)}")
        print(f"  🔲 红框共振金胆: 中 {len(b_hits):2d} / {len(border_core):2d} 码 ({len(b_hits)/len(border_core)*100:4.1f}%) -> 命中: {' '.join(f'{x:02d}' for x in b_hits)}")
        print(f"  ⚡ 最优 3 胆:    中 {len(g3_hits):2d} /  3 码 ({len(g3_hits)/3*100:4.1f}%) -> 命中: {' '.join(f'{x:02d}' for x in g3_hits)}")
        pair_str = ', '.join(f'[{p[0]:02d}-{p[1]:02d}]' for p in p_hits_this) if p_hits_this else '未双中'
        print(f"  💎 选2黄金搭档:  {pair_str}")
        print('-' * 85)

    print('\n' + '=' * 85)
    print('📊 【最近 10 期实战大考决算总表】 (大盘随机单码基线为 25.0%):')
    print('=' * 85)
    r_rate = total_red_hits / (10 * 20) * 100
    y_rate = total_yellow_hits / (10 * 16) * 100
    b_rate = total_border_hits / total_border_size * 100
    g3_rate = total_g3_hits / 30 * 100
    p_rate = pair_hit_count / total_pairs_tested * 100

    print(f"1. 🔴 红底20码大底: 均期中 {total_red_hits/10:.2f} 码 | 单码命中率: {r_rate:.2f}% (提升度: {r_rate/25.0:.2f}x)")
    print(f"2. 🟡 黄底16码精选: 均期中 {total_yellow_hits/10:.2f} 码 | 单码命中率: {y_rate:.2f}% (提升度: {y_rate/25.0:.2f}x)")
    print(f"3. 🔲 红框共振金胆: 均期中 {total_border_hits/10:.2f} 码 | 单码命中率: {b_rate:.2f}% (提升度: {b_rate/25.0:.2f}x)")
    print(f"4. ⚡ 最优 3 胆突破: 均期中 {total_g3_hits/10:.2f} 码 | 单码命中率: {g3_rate:.2f}% (提升度: {g3_rate/25.0:.2f}x)")
    print(f"5. 💎 选2双中对数:  30组对账中 {pair_hit_count} 组双中 (双全中率: {p_rate:.2f}%, 随机基准约 6.0%)")
    print('=' * 85)

if __name__ == '__main__':
    main()
