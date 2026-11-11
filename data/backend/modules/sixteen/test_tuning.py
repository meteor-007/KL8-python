# -*- coding: utf-8 -*-
"""
双轨融合优化测试：多维动量 + 动力学分桶守卫
"""
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine
import numpy as np

def test_engine():
    engine = FolkSixteenEngine()
    draws = engine.draws
    total_draws = len(draws)
    test_indices = list(range(total_draws - 30, total_draws))

    def evaluate_params(w_freq, w_rep, w_om12, w_sweet):
        hits_20, hits_12, hits_5, hits_3 = [], [], [], []
        for idx in test_indices:
            past_draws = draws[:idx]
            eng = FolkSixteenEngine(history_draws=past_draws)
            target_p = draws[idx]["period"]
            actual_set = draws[idx]["nums_set"]
            
            # 手动执行打分
            res = eng.analyze_window(target_period=target_p)
            bp = res["ball_profiles"]
            scores = {}
            for n in range(1, 81):
                p = bp[n]
                freq = p["freq"]
                om = p["omission"]
                is_out = p["is_outgoing"]
                is_rep = p["is_repeat"]
                
                s = 0.0
                if freq in [4, 5, 6]:
                    s += w_sweet
                elif freq == 7:
                    s += w_sweet * 0.7
                elif freq == 3:
                    s += w_sweet * 0.6
                elif freq >= 8:
                    s += w_sweet * 0.4
                elif freq == 2 and om >= 8:
                    s += w_sweet * 0.8
                
                if is_rep:
                    s += w_rep
                elif om in [1, 2]:
                    s += w_om12
                
                if is_out:
                    if is_rep:
                        s += 5.0
                    else:
                        s -= 8.0
                scores[n] = s
            
            # 选 20 码: 优先满足出窗码 4~5 个, 重号 4~5 个, 大冷 1~2 个
            sorted_all = sorted(range(1, 81), key=lambda x: scores[x], reverse=True)
            sel_20 = []
            
            # 1. 冷号回补 1~2 个
            colds = [n for n in sorted_all if bp[n]["freq"] == 2 and bp[n]["omission"] >= 8]
            sel_20.extend(colds[:2])
            
            # 2. 贪心补足
            out_c = sum(1 for n in sel_20 if bp[n]["is_outgoing"])
            rep_c = sum(1 for n in sel_20 if bp[n]["is_repeat"])
            for n in sorted_all:
                if len(sel_20) >= 20: break
                if n in sel_20: continue
                is_o = bp[n]["is_outgoing"]
                is_r = bp[n]["is_repeat"]
                if is_o and out_c >= 5: continue
                if is_r and rep_c >= 6: continue
                sel_20.append(n)
                if is_o: out_c += 1
                if is_r: rep_c += 1
            
            for n in sorted_all:
                if len(sel_20) >= 20: break
                if n not in sel_20: sel_20.append(n)
            
            ranked_20 = sorted(sel_20, key=lambda x: scores[x], reverse=True)
            e12 = ranked_20[:12]
            g5 = ranked_20[:5]
            g3 = ranked_20[:3]
            
            hits_20.append(len(set(sel_20).intersection(actual_set)))
            hits_12.append(len(set(e12).intersection(actual_set)))
            hits_5.append(len(set(g5).intersection(actual_set)))
            hits_3.append(len(set(g3).intersection(actual_set)))
        
        print(f"w_sweet={w_sweet}, w_rep={w_rep}, w_om12={w_om12} -> 20均中:{np.mean(hits_20):.2f}, 12均中:{np.mean(hits_12):.2f}, 5均中:{np.mean(hits_5):.2f}, 3均中:{np.mean(hits_3):.2f}")

    evaluate_params(w_freq=30, w_rep=25, w_om12=15, w_sweet=35)
    evaluate_params(w_freq=30, w_rep=30, w_om12=18, w_sweet=40)
    evaluate_params(w_freq=25, w_rep=20, w_om12=12, w_sweet=30)

if __name__ == "__main__":
    test_engine()
