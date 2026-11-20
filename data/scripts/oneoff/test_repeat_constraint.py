# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import Counter
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def build_repeat_constrained_selector(engine, target_period=None):
    draws = engine.draws
    if target_period is None:
        idx = len(draws) - 1
        predicted_target = draws[idx]['period'] + 1
        has_actual = False
        actual = set()
    else:
        idx = next((i for i, x in enumerate(draws) if x['period'] == target_period), len(draws) - 1)
        if idx < len(draws) and draws[idx]['period'] == target_period:
            idx = idx - 1 # 严格屏蔽未来
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

    # 评分函数 (非重号按遗漏与频次打分, 重号按连庄动量打分)
    def score_ball(n):
        f = fc[n]
        om = om_dict[n]
        is_rep = n in last_set
        is_out = n in outgoing_set

        # 频次底分
        s = {8: 45.0, 7: 42.0, 6: 40.0, 5: 36.0, 4: 30.0, 3: 24.0, 2: 15.0, 1: 6.0}.get(f, 0.0)

        # 遗漏生态分
        if is_rep:
            s += 30.0 # 重号高分，但名额受限
        elif om == 1:
            s += 28.0 # 隔期跳号
        elif om == 2:
            s += 24.0 # 斜连回踩
        elif 3 <= om <= 5:
            s += 18.0 # 中温反弹
        elif 6 <= om <= 9:
            s += 14.0 # 冷号回补
        else:
            s += 4.0

        # 区域动量
        if not is_out and f >= 5:
            s += 12.0 # 剩余区高频
        if is_out and f >= 6:
            s += 14.0 # 出窗抗跌

        return s

    rem_candidates = [n for n in range(1, 81) if n not in outgoing_set]
    out_candidates = [n for n in range(1, 81) if n in outgoing_set]

    # 分离出重号与非重号
    rem_rep = sorted([n for n in rem_candidates if n in last_set], key=score_ball, reverse=True)
    rem_non_rep = sorted([n for n in rem_candidates if n not in last_set], key=score_ball, reverse=True)

    out_rep = sorted([n for n in out_candidates if n in last_set], key=score_ball, reverse=True)
    out_non_rep = sorted([n for n in out_candidates if n not in last_set], key=score_ball, reverse=True)

    # 黄金配额执行：
    # 20 码大底 = 剩余区 15 码 + 出窗区 5 码
    # 重号总数严卡 5~6 码 (剩余区 4 码重号 + 出窗区 1~2 码重号)
    # 剩余区 15 码 = 4 码重号 + 11 码非重号
    # 出窗区 5 码 = 1~2 码重号 + 3~4 码非重号
    picks_rem = rem_rep[:4] + rem_non_rep[:11]
    picks_out = out_rep[:2] + out_non_rep[:3]

    grand_20 = sorted(picks_rem + picks_out)
    rep_in_grand = [n for n in grand_20 if n in last_set]
    non_rep_in_grand = [n for n in grand_20 if n not in last_set]

    return {
        'target_period': predicted_target,
        'grand_20': grand_20,
        'rep_in_grand': rep_in_grand,
        'non_rep_in_grand': non_rep_in_grand,
        'has_actual': has_actual,
        'actual': actual,
        'hits': [n for n in grand_20 if n in actual] if has_actual else []
    }

def main():
    engine = FolkSixteenEngine()
    # 1. 盲测第 2026262 期
    res_262 = build_repeat_constrained_selector(engine, target_period=2026262)
    print("=" * 85)
    print(f"🔥 第 {res_262['target_period']} 期【重号严控配额模型】实测对账:")
    print(f"大底 20 码: {res_262['grand_20']}")
    print(f"重号数量:   {len(res_262['rep_in_grand'])} 码 (严格限制在 5~6 码) -> {res_262['rep_in_grand']}")
    print(f"非重号数量: {len(res_262['non_rep_in_grand'])} 码 -> {res_262['non_rep_in_grand']}")
    print(f"实开 20 码命中: {len(res_262['hits'])} / 20 码 (命中率: {len(res_262['hits'])/20*100:.1f}%)")
    print(f"命中清单:   {sorted(res_262['hits'])}")
    print("=" * 85)

    # 2. 预测今晚第 2026263 期
    res_263 = build_repeat_constrained_selector(engine)
    print(f"\n👑 今晚最新第 {res_263['target_period']} 期【重号严控黄金 20 码大底】:")
    print(f"大底 20 码: {res_263['grand_20']}")
    print(f"重号数量:   {len(res_263['rep_in_grand'])} 码 -> {res_263['rep_in_grand']}")
    print(f"非重号数量: {len(res_263['non_rep_in_grand'])} 码 -> {res_263['non_rep_in_grand']}")
    print("=" * 85)

if __name__ == '__main__':
    main()
