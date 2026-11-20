# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import Counter
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def test_remaining_first_strategy():
    engine = FolkSixteenEngine()
    draws = engine.draws

    # 测试第 2026262 期
    idx = next(i for i, x in enumerate(draws) if x['period'] == 2026262)
    hist_before = draws[:idx]
    w_draws = hist_before[-16:]
    actual = draws[idx]['nums_set']

    fc = Counter()
    for wd in w_draws:
        fc.update(wd['nums'])

    outgoing_set = w_draws[0]['nums_set']
    last_set = hist_before[-1]['nums_set']

    om_dict = {}
    for n in range(1, 81):
        om = 0
        for bi in range(len(hist_before) - 1, -1, -1):
            if n in hist_before[bi]['nums_set']:
                break
            om += 1
        om_dict[n] = om

    # 专门给剩余区的 60 个号码打分
    def score_rem_ball(n):
        f = fc[n]
        om = om_dict[n]
        is_rep = n in last_set

        s = 0.0
        # 频次权重 (6~7次极高, 4~5次主力, 3次蓄势)
        s += {7: 50.0, 6: 45.0, 5: 38.0, 4: 32.0, 3: 25.0, 2: 15.0, 1: 5.0}.get(f, 0.0)

        # 重号 (连庄惯性)
        if is_rep:
            s += 28.0
        # 短遗漏 (隔期与斜连)
        if om == 1:
            s += 22.0
        elif om == 2:
            s += 18.0
        elif 3 <= om <= 4:
            s += 15.0
        elif 5 <= om <= 7:
            s += 12.0

        return s

    # 专门给出窗区的 20 个号码打分 (只挑真抗跌连庄)
    def score_out_ball(n):
        f = fc[n]
        om = om_dict[n]
        is_rep = n in last_set

        s = 0.0
        if is_rep:
            s += 40.0 # 出窗必须是连庄强庄才选 (如 78, 80)
        if f >= 6:
            s += 30.0 # 高频出窗抗跌 (如 54, 78)
        elif f == 5:
            s += 20.0
        if om <= 2:
            s += 15.0

        return s

    rem_candidates = [n for n in range(1, 81) if n not in outgoing_set]
    out_candidates = [n for n in range(1, 81) if n in outgoing_set]

    sorted_rem = sorted(rem_candidates, key=score_rem_ball, reverse=True)
    sorted_out = sorted(out_candidates, key=score_out_ball, reverse=True)

    # 核心策略: 剩余区挑 15 码 + 出窗区挑 5 码 = 20 码大底
    picks_rem_15 = sorted_rem[:15]
    picks_out_5 = sorted_out[:5]

    grand_20 = sorted(picks_rem_15 + picks_out_5)
    hits = [n for n in grand_20 if n in actual]
    rem_hits = [n for n in picks_rem_15 if n in actual]
    out_hits = [n for n in picks_out_5 if n in actual]

    print("=" * 85)
    print("🔥 【剩余区绝对主力战略】——第 2026262 期实测战报:")
    print("=" * 85)
    print(f"剩余区挑出 15 码: {sorted(picks_rem_15)}")
    print(f"剩余区命中数:     {len(rem_hits)} / 15 码 ({len(rem_hits)/15*100:.1f}%) -> 命中: {sorted(rem_hits)}")
    print(f"出窗区挑出  5 码: {sorted(picks_out_5)}")
    print(f"出窗区命中数:     {len(out_hits)} /  5 码 ({len(out_hits)/5*100:.1f}%) -> 命中: {sorted(out_hits)}")
    print("-" * 85)
    print(f"总计推荐 20 码大底: {grand_20}")
    print(f"实开 20 码总命中:   {len(hits)} / 20 码 (命中率高达: {len(hits)/20*100:.1f}%)")
    print(f"命中号码清单 ({len(hits)}个): {sorted(hits)}")
    print("=" * 85)

if __name__ == '__main__':
    test_remaining_first_strategy()
