# -*- coding: utf-8 -*-
from collections import Counter
from typing import List, Dict, Any

NUM_TOTAL = 80
BASE_RATE = 20 / 80

def generate_proxy_signals(draws_history: List[Dict[str, Any]], t: int) -> Dict[str, List[int]]:
    hist = draws_history[:t]
    if not hist:
        return {'高频': [], '遗漏回补': [], '邻号扩散': [], '重复号': []}

    last_nums = hist[-1]['nums']
    win = hist[-20:]
    flat = [x for s in win for x in s['nums']]
    freq = Counter(flat)

    gap = {}
    for n in range(1, NUM_TOTAL + 1):
        g = len(hist)
        for i in range(len(hist) - 1, -1, -1):
            if n in hist[i]['nums']:
                g = len(hist) - 1 - i
                break
        gap[n] = g

    sig_freq = [n for n, _ in freq.most_common(5)]
    cand_om = [n for n in range(1, NUM_TOTAL + 1) if 3 <= gap[n] <= 6]
    sig_om = sorted(cand_om, key=lambda n: -freq[n])[:5]

    cand_dif = []
    for n in range(1, NUM_TOTAL + 1):
        left_n = 80 if n == 1 else n - 1
        right_n = 1 if n == 80 else n + 1
        if left_n in last_nums or right_n in last_nums:
            cand_dif.append(n)
    sig_dif = sorted(cand_dif, key=lambda n: -freq[n])[:5]

    cnt, hit = Counter(), Counter()
    for i in range(len(hist) - 1):
        for n in hist[i]['nums']:
            cnt[n] += 1
            if n in hist[i + 1]['nums']:
                hit[n] += 1
    rate = {n: (hit[n] + 2 * BASE_RATE) / (cnt[n] + 2) for n in last_nums}
    sig_rep = sorted(last_nums, key=lambda n: -rate[n])[:5]

    return {
        '高频': sig_freq,
        '遗漏回补': sig_om,
        '邻号扩散': sig_dif,
        '重复号': sig_rep
    }
