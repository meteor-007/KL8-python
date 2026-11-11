# -*- coding: utf-8 -*-
"""
四维全息协同调优：
1. 重号量化防过热 (4~5码)
2. 012路三角对称 (7:6:7 动态弹性微调)
3. 十位区间网格全覆盖 (0头~7头，覆盖 >= 7 个区间)
4. 尾数全息离散覆盖 (0~9尾，覆盖 >= 9 个尾数)
5. 黄金搭档双中率升级
"""
import sys, os
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def run_four_dimensional_refinement():
    engine = FolkSixteenEngine()
    total = len(engine.draws)
    N_TEST = 30
    test_start = total - N_TEST

    red_hits_list = []
    g5_hits_list = []
    g3_hits_list = []
    zone_coverages = []
    tail_coverages = []
    pair_doubles = 0
    pair_total = 0

    for i in range(test_start, total):
        target_period = engine.draws[i]["period"]
        actual_set = engine.draws[i]["nums_set"]
        base_index = i - 1

        window_draws = engine.draws[base_index - 15 : base_index + 1]
        outgoing_set = window_draws[0]["nums_set"]
        last_set = window_draws[-1]["nums_set"]

        freq_counter = Counter()
        for d in window_draws:
            freq_counter.update(d["nums"])

        omission_dict = {}
        for num in range(1, 81):
            om = 0
            for back_i in range(base_index, -1, -1):
                if num in engine.draws[back_i]["nums_set"]:
                    break
                om += 1
            omission_dict[num] = om

        # 近期开奖衰减能量场
        hist_before_desc = list(reversed(engine.draws[: base_index + 1]))
        energy_field = {n: 0.0 for n in range(1, 81)}
        decay_rate = 0.82
        for step, d in enumerate(hist_before_desc[:12]):
            w = (decay_rate ** step)
            for n in d["nums"]:
                energy_field[n] += w
                if n + 1 <= 80:
                    energy_field[n + 1] += w * 0.25
                if n - 1 >= 1:
                    energy_field[n - 1] += w * 0.25

        empirical_f_score = {
            1: 43.0, 6: 41.0, 0: 38.0, 3: 36.0, 5: 35.0, 2: 34.0, 4: 31.0,
            7: 21.0, 8: 10.0, 9: 8.0, 10: 8.0
        }

        ball_scores = {}
        for n in range(1, 81):
            f = freq_counter.get(n, 0)
            om = omission_dict[n]
            is_out = (n in outgoing_set)
            e = energy_field[n]

            s_f = empirical_f_score.get(f, 15.0)

            if om == 0:
                s_om = 26.0
            elif om in [1, 2]:
                s_om = 36.0
            elif 3 <= om <= 5:
                s_om = 28.0
            elif 6 <= om <= 9:
                s_om = 22.0
            elif 10 <= om <= 16:
                s_om = 38.0
            else:
                s_om = 18.0

            recent_consec = 0
            for h in hist_before_desc[:4]:
                if n in h["nums_set"]:
                    recent_consec += 1
                else:
                    break
            consec_penalty = 1.0
            if recent_consec >= 2:
                consec_penalty = 0.65
            if recent_consec >= 3:
                consec_penalty = 0.35

            rem_bonus = 16.0 if not is_out else 0.0
            ball_scores[n] = (s_f + s_om + e * 7.5 + rem_bonus) * consec_penalty

        # 四维立体选拔
        # 1. 重号严格优选 4~5 码
        rep_candidates = sorted([n for n in last_set], key=lambda x: ball_scores[x], reverse=True)
        num_reps = 5 if ball_scores[rep_candidates[4]] > 65.0 else 4
        picked_reps = rep_candidates[:num_reps]

        # 2. 012 路三角基础骨架
        r0_picked = [n for n in picked_reps if n % 3 == 0]
        r1_picked = [n for n in picked_reps if n % 3 == 1]
        r2_picked = [n for n in picked_reps if n % 3 == 2]

        target_r0 = 7 - len(r0_picked)
        target_r1 = 6 - len(r1_picked)
        target_r2 = 7 - len(r2_picked)

        non_rep_cands = sorted([n for n in range(1, 81) if n not in picked_reps], key=lambda x: ball_scores[x], reverse=True)
        r0_pool = [n for n in non_rep_cands if n % 3 == 0]
        r1_pool = [n for n in non_rep_cands if n % 3 == 1]
        r2_pool = [n for n in non_rep_cands if n % 3 == 2]

        opt_red = list(picked_reps)
        opt_red.extend(r0_pool[:target_r0])
        opt_red.extend(r1_pool[:target_r1])
        opt_red.extend(r2_pool[:target_r2])

        # 3. 维度 3 & 4：区间网格打散与尾数覆盖检查与微调
        # 检查是否缺失区间或严重缺少尾数，若有缺失，用对应区间/尾数的最高分候选进行同路等价替换
        zones = set((n - 1) // 10 + 1 for n in opt_red)
        tails = set(n % 10 for n in opt_red)

        # 如果区间覆盖 < 7，寻找未覆盖区间中得分最高的号码，在同路号码中替换掉最低分的那个
        for z in range(1, 9):
            if z not in zones and len(opt_red) == 20:
                zone_cands = [n for n in non_rep_cands if ((n - 1) // 10 + 1) == z and n not in opt_red]
                if zone_cands:
                    best_z = zone_cands[0]
                    # 寻找同路的最低分号码替换
                    same_road_in_red = sorted([n for n in opt_red if n % 3 == best_z % 3 and n not in picked_reps], key=lambda x: ball_scores[x])
                    if same_road_in_red and ball_scores[best_z] >= ball_scores[same_road_in_red[0]] - 10.0:
                        opt_red.remove(same_road_in_red[0])
                        opt_red.append(best_z)
                        zones.add(z)

        # 如果尾数覆盖 < 9，同样进行同路微调
        for t in range(0, 10):
            if t not in tails and len(opt_red) == 20:
                tail_cands = [n for n in non_rep_cands if (n % 10) == t and n not in opt_red]
                if tail_cands:
                    best_t = tail_cands[0]
                    same_road_in_red = sorted([n for n in opt_red if n % 3 == best_t % 3 and n not in picked_reps], key=lambda x: ball_scores[x])
                    if same_road_in_red and ball_scores[best_t] >= ball_scores[same_road_in_red[0]] - 8.0:
                        opt_red.remove(same_road_in_red[0])
                        opt_red.append(best_t)
                        tails.add(t)

        opt_red = sorted(opt_red)

        # 黄底 16 码
        opt_yellow = sorted(sorted(range(1, 81), key=lambda x: ball_scores[x], reverse=True)[:16])

        # 红框核心共振
        opt_border = sorted(list(set(opt_red).intersection(set(opt_yellow))))

        # 金5与金3：取红框中的最高分核心
        sorted_border = sorted(opt_border, key=lambda x: ball_scores[x], reverse=True)
        if len(sorted_border) < 5:
            extra = sorted([n for n in opt_red if n not in sorted_border], key=lambda x: ball_scores[x], reverse=True)
            sorted_border.extend(extra[: 5 - len(sorted_border)])
        opt_g5 = sorted_border[:5]
        opt_g3 = sorted_border[:3]

        # 选2黄金搭档 (基于近 30 期开奖在红框核心号码上的共现协同度)
        hist_30 = engine.draws[max(0, base_index - 30 + 1) : base_index + 1]
        pair_counts = Counter()
        b_set = set(opt_border if len(opt_border) >= 4 else opt_g5)
        for hd in hist_30:
            inter = sorted(list(hd["nums_set"] & b_set))
            for p1 in range(len(inter)):
                for p2 in range(p1 + 1, len(inter)):
                    pair_counts[(inter[p1], inter[p2])] += 1

        b_list = sorted(list(b_set))
        pair_candidates = []
        for p1 in range(len(b_list)):
            for p2 in range(p1 + 1, len(b_list)):
                pk = (b_list[p1], b_list[p2])
                score_pair = pair_counts.get(pk, 0) * 12.0 + (ball_scores[b_list[p1]] + ball_scores[b_list[p2]]) * 0.15
                pair_candidates.append((pk, score_pair))
        pair_candidates.sort(key=lambda x: x[1], reverse=True)
        top_3_pairs = [list(p[0]) for p in pair_candidates[:3]]

        # 统计
        hit_red = len(set(opt_red) & actual_set)
        hit_g5 = len(set(opt_g5) & actual_set)
        hit_g3 = len(set(opt_g3) & actual_set)
        red_hits_list.append(hit_red)
        g5_hits_list.append(hit_g5)
        g3_hits_list.append(hit_g3)

        z_cov = len(set((n - 1) // 10 + 1 for n in opt_red))
        t_cov = len(set(n % 10 for n in opt_red))
        zone_coverages.append(z_cov)
        tail_coverages.append(t_cov)

        for p in top_3_pairs:
            pair_total += 1
            if len(set(p) & actual_set) == 2:
                pair_doubles += 1

    avg_red = sum(red_hits_list) / N_TEST
    avg_g5 = sum(g5_hits_list) / N_TEST
    avg_g3 = sum(g3_hits_list) / N_TEST
    avg_zone = sum(zone_coverages) / N_TEST
    avg_tail = sum(tail_coverages) / N_TEST

    print("=" * 80)
    print("四维全息协同模型 30 期实测总决算")
    print("=" * 80)
    print(f"红底20码平均命中: {avg_red:.2f} / 20 ({avg_red/20:.1%}, Lift: {avg_red/20/0.25:.2f}x)")
    print(f"金5码平均命中:   {avg_g5:.2f} / 5  ({avg_g5/5:.1%}, Lift: {avg_g5/5/0.25:.2f}x)")
    print(f"金3码平均命中:   {avg_g3:.2f} / 3  ({avg_g3/3:.1%}, Lift: {avg_g3/3/0.25:.2f}x)")
    print(f"区间网格平均覆盖: {avg_zone:.2f} / 8 区")
    print(f"尾数离散平均覆盖: {avg_tail:.2f} / 10 尾")
    print(f"黄金选2双中率:   {pair_doubles} / {pair_total} 组 ({pair_doubles/pair_total:.1%}) vs 随机基线 6.0%")
    print("=" * 80)

if __name__ == "__main__":
    run_four_dimensional_refinement()
