# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import Counter
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def dump_data():
    engine = FolkSixteenEngine()
    draws = engine.draws

    base_draw = draws[-1]
    base_period = base_draw['period']
    target_period = base_period + 1

    window_draws = draws[-16:]
    outgoing_draw = window_draws[0]
    last_draw = window_draws[-1]

    fc = Counter()
    for wd in window_draws:
        fc.update(wd['nums'])

    outgoing_set = outgoing_draw['nums_set']
    last_set = last_draw['nums_set']

    # 遗漏
    om_dict = {}
    for n in range(1, 81):
        om = 0
        for back_i in range(len(draws) - 1, -1, -1):
            if n in draws[back_i]['nums_set']:
                break
            om += 1
        om_dict[n] = om

    print(f"基准开奖期: {base_period} | 目标研判期: {target_period}")
    out_p = outgoing_draw['period']
    print(f"出窗期号: {out_p} | 出窗 20 码: {sorted(list(outgoing_set))}")
    last_p = last_draw['period']
    print(f"昨夜实开: {last_p} | 昨夜 20 码: {sorted(list(last_set))}")
    print("=" * 80)
    print("【当前 16 期窗口大盘光谱 (1~8+ 级频次分桶)】:")
    for freq in range(8, 0, -1):
        in_tier = [n for n in range(1, 81) if (fc[n] == freq or (freq == 8 and fc[n] >= 8))]
        out_tier = [n for n in in_tier if n in outgoing_set]
        rem_tier = [n for n in in_tier if n not in outgoing_set]
        tier_lbl = f"{freq}+次" if freq == 8 else f"{freq}次"
        print(f"  · {tier_lbl:4s} (共 {len(in_tier):2d} 码): 出窗 {len(out_tier)} 码 {out_tier} | 剩余 {len(rem_tier):2d} 码 {rem_tier}")

    print("=" * 80)
    print("【昨夜开出的 20 码在当前 16 期窗口中的频次与遗漏】:")
    for n in sorted(list(last_set)):
        print(f"  球 {n:02d}: 16期频次={fc[n]}, 012路={n%3}, 十位={n//10}头, 尾数={n%10}尾, 是否出窗={n in outgoing_set}")

if __name__ == '__main__':
    dump_data()
