# -*- coding: utf-8 -*-
"""
选2黄金搭档专项调优：测试不同池子（红框 vs 精12 vs 20大底）+ 不同历史跨度（30期 vs 50期 vs 100期）的共现双中表现
"""
import sys, os
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def tune_pairs():
    engine = FolkSixteenEngine()
    total = len(engine.draws)
    N_TEST = 30
    test_start = total - N_TEST

    for window_span in [30, 50, 80]:
        for pool_type in ["border", "elite12", "grand20"]:
            double_hits = 0
            single_hits = 0
            total_pairs = 0

            for i in range(test_start, total):
                actual_set = engine.draws[i]["nums_set"]
                base_index = i - 1

                # 采用优化后的引擎打分
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

                hist_before_desc = list(reversed(engine.draws[: base_index + 1]))
                energy_field = {n: 0.0 for n in range(1, 81)}
                decay_rate = 0.82
                for step, d in enumerate(hist_before_desc[:12]):
                    w = (decay_rate ** step)
                    for n in d["nums"]:
                        energy_field[n] += w

                empirical_f_score = {1: 43.0, 6: 41.0, 0: 38.0, 3: 36.0, 5: 35.0, 2: 34.0, 4: 31.0, 7: 21.0, 8: 10.0}
                ball_scores = {}
                for n in range(1, 81):
                    f = freq_counter.get(n, 0)
                    om = omission_dict[n]
                    is_out = (n in outgoing_set)
                    e = energy_field[n]
                    s_f = empirical_f_score.get(f, 15.0)
                    s_om = 26.0 if om == 0 else (36.0 if om in [1, 2] else (28.0 if 3 <= om <= 5 else (38.0 if 10 <= om <= 16 else 20.0)))
                    consec = sum(1 for h in hist_before_desc[:3] if n in h["nums_set"])
                    p = 0.65 if consec >= 2 else 1.0
                    rem_b = 16.0 if not is_out else 0.0
                    ball_scores[n] = (s_f + s_om + e * 7.5 + rem_b) * p

                rep_cands = sorted([n for n in last_set], key=lambda x: ball_scores[x], reverse=True)[:4]
                non_rep = sorted([n for n in range(1, 81) if n not in rep_cands], key=lambda x: ball_scores[x], reverse=True)
                r0 = [n for n in non_rep if n % 3 == 0]
                r1 = [n for n in non_rep if n % 3 == 1]
                r2 = [n for n in non_rep if n % 3 == 2]

                red_20 = sorted(rep_cands + r0[:7-sum(1 for n in rep_cands if n%3==0)] + r1[:6-sum(1 for n in rep_cands if n%3==1)] + r2[:7-sum(1 for n in rep_cands if n%3==2)])
                yellow_16 = sorted(sorted(range(1, 81), key=lambda x: ball_scores[x], reverse=True)[:16])
                border_core = sorted(list(set(red_20) & set(yellow_16)))
                elite_12 = sorted(border_core + [n for n in red_20 if n not in border_core])[:12]

                if pool_type == "border":
                    target_pool = border_core if len(border_core) >= 2 else elite_12[:5]
                elif pool_type == "elite12":
                    target_pool = elite_12
                else:
                    target_pool = red_20

                # 寻找共现最高的 pair
                hist_span = engine.draws[max(0, base_index - window_span + 1) : base_index + 1]
                cooccur = Counter()
                for hd in hist_span:
                    in_pool = sorted(list(hd["nums_set"] & set(target_pool)))
                    for x1 in range(len(in_pool)):
                        for x2 in range(x1 + 1, len(in_pool)):
                            cooccur[(in_pool[x1], in_pool[x2])] += 1

                cand_pairs = []
                t_list = sorted(list(target_pool))
                for x1 in range(len(t_list)):
                    for x2 in range(x1 + 1, len(t_list)):
                        pk = (t_list[x1], t_list[x2])
                        # 综合分数：共现频次 * 15 + 单码动能和
                        sc = cooccur.get(pk, 0) * 15.0 + (ball_scores[t_list[x1]] + ball_scores[t_list[x2]]) * 0.2
                        cand_pairs.append((pk, sc))
                cand_pairs.sort(key=lambda x: x[1], reverse=True)
                top_3 = [p[0] for p in cand_pairs[:3]]

                for p in top_3:
                    total_pairs += 1
                    hits = len(set(p) & actual_set)
                    if hits == 2:
                        double_hits += 1
                    elif hits == 1:
                        single_hits += 1

            print(f"跨度 {window_span}期 | 候选池 {pool_type:<8} | 选2双中率: {double_hits}/{total_pairs} ({double_hits/total_pairs:.1%}) | 单中率: {single_hits/total_pairs:.1%}")

if __name__ == "__main__":
    tune_pairs()
