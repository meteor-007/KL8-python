# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from collections import Counter
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def test_tier_quota_selection():
    engine = FolkSixteenEngine()
    draws = engine.draws

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

    user_marked = [73, 54, 78, 4, 65, 72, 61, 80, 17, 49, 59]

    # 单球动力学评分
    def score_ball(n):
        f = fc[n]
        om = om_dict[n]
        is_out = n in outgoing_set
        is_rep = n in last_set

        s = 0.0
        # 1. 重号龙头溢价 (昨夜开出的号，具有强烈连庄惯性)
        if is_rep:
            s += 35.0

        # 2. 遗漏动能
        if om == 1:
            s += 28.0 # 隔期跳
        elif om == 2:
            s += 24.0 # 斜连
        elif 3 <= om <= 4:
            s += 18.0
        elif 5 <= om <= 7:
            s += 15.0 # 中温回暖 (如 49, 59, 09)

        # 3. 区域属性: 剩余区高频动量加分
        if not is_out and f >= 5:
            s += 12.0
        # 出窗极热抗跌
        if is_out and f >= 6:
            s += 15.0

        return s

    # 分行配额挑选
    # 7次行: 配 2 码
    t7 = [n for n in range(1, 81) if fc[n] >= 7]
    t7_sorted = sorted(t7, key=score_ball, reverse=True)
    picks_7 = t7_sorted[:2]

    # 6次行: 配 5 码 (优先挑重号与剩余区动量)
    t6 = [n for n in range(1, 81) if fc[n] == 6]
    t6_sorted = sorted(t6, key=score_ball, reverse=True)
    picks_6 = t6_sorted[:5]

    # 5次行: 配 4 码
    t5 = [n for n in range(1, 81) if fc[n] == 5]
    t5_sorted = sorted(t5, key=score_ball, reverse=True)
    picks_5 = t5_sorted[:4]

    # 4次行: 配 5 码 (包含 80, 49, 59, 17, 33 等)
    t4 = [n for n in range(1, 81) if fc[n] == 4]
    t4_sorted = sorted(t4, key=score_ball, reverse=True)
    picks_4 = t4_sorted[:5]

    # 3次行: 配 3 码
    t3 = [n for n in range(1, 81) if fc[n] == 3]
    t3_sorted = sorted(t3, key=score_ball, reverse=True)
    picks_3 = t3_sorted[:3]

    # 2次行: 配 1 码
    t2 = [n for n in range(1, 81) if fc[n] == 2]
    t2_sorted = sorted(t2, key=score_ball, reverse=True)
    picks_2 = t2_sorted[:1]

    final_20 = sorted(picks_7 + picks_6 + picks_5 + picks_4 + picks_3 + picks_2)
    hits = [n for n in final_20 if n in actual]
    user_hits = [n for n in final_20 if n in user_marked]
    user_miss = [n for n in user_marked if n not in final_20]

    print("=" * 85)
    print("🔥 修复分行配额与重号溢价后，第 2026262 期选号结果:")
    print(f"推荐 20 码: {final_20}")
    print(f"实开 20 码命中: {len(hits)} / 20 码 (命中率: {len(hits)/20*100:.1f}%)")
    print(f"命中清单: {sorted(hits)}")
    print(f"用户红框标记号码共 {len(user_marked)} 个，成功挑出 {len(user_hits)} 个: {sorted(user_hits)}")
    print(f"未挑出用户红框码: {user_miss}")
    print("=" * 85)

if __name__ == '__main__':
    test_tier_quota_selection()
