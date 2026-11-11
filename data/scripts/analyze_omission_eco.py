# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import defaultdict
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def main():
    engine = FolkSixteenEngine()
    draws = engine.draws

    draws_30 = draws[-30:]
    om_dist = defaultdict(list)

    for d in draws_30:
        p = d['period']
        idx = next(i for i, x in enumerate(draws) if x['period'] == p)
        om_dict = {}
        for n in range(1, 81):
            om = 0
            for back_i in range(idx - 1, -1, -1):
                if n in draws[back_i]['nums_set']:
                    break
                om += 1
            om_dict[n] = om
        
        curr_draw = d['nums']
        c_rep = sum(1 for n in curr_draw if om_dict[n] == 0)
        c_short = sum(1 for n in curr_draw if om_dict[n] in [1, 2])
        c_warm = sum(1 for n in curr_draw if 3 <= om_dict[n] <= 5)
        c_cold = sum(1 for n in curr_draw if om_dict[n] >= 6)
        
        om_dist['rep'].append(c_rep)
        om_dist['short'].append(c_short)
        om_dist['warm'].append(c_warm)
        om_dist['cold'].append(c_cold)

    print('实开20码遗漏黄金生态配比 (近30期实测均值):')
    print(f"1. 重号 (遗漏 0):  均期 {sum(om_dist['rep'])/30:.2f} 个 (约 4~5 个)")
    print(f"2. 短遗漏 (1~2):  均期 {sum(om_dist['short'])/30:.2f} 个 (约 6~7 个)")
    print(f"3. 中温号 (3~5):  均期 {sum(om_dist['warm'])/30:.2f} 个 (约 5~6 个)")
    print(f"4. 冷号回补 (>=6): 均期 {sum(om_dist['cold'])/30:.2f} 个 (约 3~4 个)")

if __name__ == '__main__':
    main()
