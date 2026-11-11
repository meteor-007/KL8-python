# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import Counter, defaultdict
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def main():
    engine = FolkSixteenEngine()
    draws = engine.draws

    draws_30 = draws[-30:]
    tier_dist = defaultdict(list)

    for d in draws_30:
        p = d['period']
        idx = next(i for i, x in enumerate(draws) if x['period'] == p)
        # 开奖前 16 期频次
        w_draws = draws[idx - 16 : idx]
        fc = Counter()
        for wd in w_draws:
            fc.update(wd['nums'])
        
        curr_draw = d['nums']
        for n in curr_draw:
            f = fc.get(n, 0)
            bucket = f if f <= 7 else 8
            tier_dist[bucket].append(n)

    print('实开20码在16期频次分桶的真实出号均值 (近30期实测均期开出个数):')
    for b in range(8, 0, -1):
        lbl = f"{b}+次" if b == 8 else f"{b}次"
        cnt = len(tier_dist[b])
        print(f"  · {lbl:4s}: 均期开出 {cnt/30:.2f} 个")

if __name__ == '__main__':
    main()
