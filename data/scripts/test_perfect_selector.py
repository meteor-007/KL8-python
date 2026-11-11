# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import Counter
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def build_perfect_four_dim_selector(engine, target_period=None):
    draws = engine.draws
    if target_period is None:
        idx = len(draws) - 1
        predicted_target = draws[idx]['period'] + 1
        has_actual = False
        actual = set()
    else:
        idx = next((i for i, x in enumerate(draws) if x['period'] == target_period), len(draws) - 1)
        if idx < len(draws) and draws[idx]['period'] == target_period:
            idx = idx - 1
            predicted_target = target_period
            has_actual = True
            actual = draws[idx + 1]['nums_set']
        else:
            idx = len(draws) - 1
            predicted_target = target_period
            has_actual = False
            actual = set()

    hist_before = draws[: idx + 1]
    w_draws = hist_before[-16:]
    outgoing_set = w_draws[0]['nums_set']
    last_set = hist_before[-1]['nums_set']

    fc = Counter()
    for wd in w_draws:
        fc.update(wd['nums'])

    om_dict = {}
    for n in range(1, 81):
        om = 0
        for bi in range(len(hist_before) - 1, -1, -1):
            if n in hist_before[bi]['nums_set']:
                break
            om += 1
        om_dict[n] = om

    def score_ball(n):
        f = fc[n]
        om = om_dict[n]
        is_rep = n in last_set
        is_out = n in outgoing_set

        s = {8: 45.0, 7: 42.0, 6: 40.0, 5: 36.0, 4: 30.0, 3: 24.0, 2: 15.0, 1: 6.0}.get(f, 0.0)

        if is_rep:
            s += 30.0
        elif om == 1:
            s += 28.0
        elif om == 2:
            s += 24.0
        elif 3 <= om <= 5:
            s += 18.0
        elif 6 <= om <= 9:
            s += 14.0
        else:
            s += 4.0

        if not is_out and f >= 5:
            s += 12.0
        if is_out and f >= 6:
            s += 14.0

        return s

    rem_candidates = [n for n in range(1, 81) if n not in outgoing_set]
    out_candidates = [n for n in range(1, 81) if n in outgoing_set]

    # 1. 挑选重号 (严格卡死在 5~6 码)
    # 挑选在剩余区与出窗区中最强劲的 5~6 个连庄重号
    all_rep_cands = sorted([n for n in range(1, 81) if n in last_set], key=score_ball, reverse=True)
    selected_rep = all_rep_cands[:6]  # 严格 6 码重号

    # 2. 挑选非重号 (必须严谨满足 012 路对称平衡与剩余区为主)
    # 当前已选 6 个重号的 012 路
    r0_cnt = sum(1 for n in selected_rep if n % 3 == 0)
    r1_cnt = sum(1 for n in selected_rep if n % 3 == 1)
    r2_cnt = sum(1 for n in selected_rep if n % 3 == 2)

    # 目标 20 码大底配比: 0路 7 码, 1路 6 码, 2路 7 码 (总计 20 码)
    target_r0 = 7 - r0_cnt
    target_r1 = 6 - r1_cnt
    target_r2 = 7 - r2_cnt

    # 候选非重号池 (优先剩余区，不足取优质出窗非重号)
    non_rep_cands = [n for n in range(1, 81) if n not in last_set]
    # 剩余区非重号排序
    non_rep_rem = sorted([n for n in non_rep_cands if n not in outgoing_set], key=score_ball, reverse=True)
    non_rep_out = sorted([n for n in non_rep_cands if n in outgoing_set], key=score_ball, reverse=True)

    non_rep_sorted = non_rep_rem + non_rep_out

    picks_r0 = [n for n in non_rep_sorted if n % 3 == 0][:target_r0]
    picks_r1 = [n for n in non_rep_sorted if n % 3 == 1][:target_r1]
    picks_r2 = [n for n in non_rep_sorted if n % 3 == 2][:target_r2]

    grand_20 = sorted(selected_rep + picks_r0 + picks_r1 + picks_r2)
    rep_in_grand = [n for n in grand_20 if n in last_set]
    non_rep_in_grand = [n for n in grand_20 if n not in last_set]

    # 剩余区与出窗区数量
    rem_in_grand = [n for n in grand_20 if n not in outgoing_set]
    out_in_grand = [n for n in grand_20 if n in outgoing_set]

    r0_final = [n for n in grand_20 if n % 3 == 0]
    r1_final = [n for n in grand_20 if n % 3 == 1]
    r2_final = [n for n in grand_20 if n % 3 == 2]

    return {
        'target_period': predicted_target,
        'grand_20': grand_20,
        'rep_in_grand': rep_in_grand,
        'non_rep_in_grand': non_rep_in_grand,
        'rem_in_grand': rem_in_grand,
        'out_in_grand': out_in_grand,
        'r0_len': len(r0_final),
        'r1_len': len(r1_final),
        'r2_len': len(r2_final),
        'hits': [n for n in grand_20 if n in actual] if has_actual else []
    }

def main():
    engine = FolkSixteenEngine()
    # 1. 盲测昨夜 2026262 期
    res_262 = build_perfect_four_dim_selector(engine, target_period=2026262)
    print("=" * 85)
    print(f"🔥 第 {res_262['target_period']} 期【四维平衡 + 重号严控】实测对账:")
    print(f"大底 20 码: {res_262['grand_20']}")
    print(f"重号数量:   {len(res_262['rep_in_grand'])} 码 (严格卡死在 6 码) -> {res_262['rep_in_grand']}")
    print(f"非重号数量: {len(res_262['non_rep_in_grand'])} 码 -> {res_262['non_rep_in_grand']}")
    print(f"区域配比:   剩余区 {len(res_262['rem_in_grand'])} 码 vs 出窗区 {len(res_262['out_in_grand'])} 码")
    print(f"012路配比:  0路 {res_262['r0_len']} 码, 1路 {res_262['r1_len']} 码, 2路 {res_262['r2_len']} 码")
    print(f"实开 20 码命中: {len(res_262['hits'])} / 20 码 (命中率: {len(res_262['hits'])/20*100:.1f}%) -> {sorted(res_262['hits'])}")
    print("=" * 85)

    # 2. 预测今晚 2026263 期
    res_263 = build_perfect_four_dim_selector(engine)
    print(f"\n👑 今晚最新第 {res_263['target_period']} 期【四维平衡 + 重号严控大盘】:")
    print(f"大底 20 码: {res_263['grand_20']}")
    print(f"重号数量:   {len(res_263['rep_in_grand'])} 码 (严格卡死在 6 码) -> {res_263['rep_in_grand']}")
    print(f"非重号数量: {len(res_263['non_rep_in_grand'])} 码 -> {res_263['non_rep_in_grand']}")
    print(f"区域配比:   剩余区 {len(res_263['rem_in_grand'])} 码 vs 出窗区 {len(res_263['out_in_grand'])} 码")
    print(f"012路配比:  0路 {res_263['r0_len']} 码, 1路 {res_263['r1_len']} 码, 2路 {res_263['r2_len']} 码")
    print("=" * 85)

if __name__ == '__main__':
    main()
