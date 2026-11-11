# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import Counter, defaultdict
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def test_cooccurrence():
    engine = FolkSixteenEngine()
    draws = engine.draws
    draws_30 = draws[-30:]

    tot_pairs = 0
    tot_hits = 0

    for d in draws_30:
        p = d['period']
        idx = next(i for i, x in enumerate(draws) if x['period'] == p)
        hist_before = draws[:idx]
        actual = d['nums_set']

        # 统计最近 30 期号码两两共同开出的频次 (共现)
        recent_30_hist = hist_before[-30:]
        pair_counts = Counter()
        for hd in recent_30_hist:
            nums = sorted(list(hd['nums_set']))
            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    pair_counts[(nums[i], nums[j])] += 1

        # 假设我们从优质候选池 (比如前 10 码) 里，挑共现最高的搭档
        top_candidates = [n for n in range(1, 81) if n % 3 == 0 or n % 3 == 1][:15] # 临时
        
        # 寻找 top_candidates 内部共现次数最高的对子
        pairs = []
        for i in range(len(top_candidates)):
            for j in range(i + 1, len(top_candidates)):
                n1, n2 = min(top_candidates[i], top_candidates[j]), max(top_candidates[i], top_candidates[j])
                pairs.append(((n1, n2), pair_counts.get((n1, n2), 0)))
        pairs.sort(key=lambda x: x[1], reverse=True)
        
        selected_3_pairs = [p[0] for p in pairs[:3]]
        for sp in selected_3_pairs:
            tot_pairs += 1
            if sp[0] in actual and sp[1] in actual:
                tot_hits += 1

    print(f"共现搭档选2双中率: {tot_hits}/{tot_pairs} = {tot_hits/tot_pairs*100:.2f}% (大盘基准约 6.0%)")

if __name__ == '__main__':
    test_cooccurrence()
