import main_workflow as mw
import deep_analysis as da
from collections import Counter

def expert_inference():
    base = r"D:\Dpanqianyi\Python-Project\KL8-点位-CODE\src\data-sum"
    hist = r"D:\Dpanqianyi\Python-Project\KL8-点位-CODE\src\data\kl8_history_final.txt"
    draws = mw.load_actual_history(hist)
    ed1 = mw.load_all_expert_data(base, "data1")
    ed2 = mw.load_all_expert_data(base, "data2")
    
    all_dates = sorted(set(list(ed1.keys()) + list(ed2.keys())), reverse=True)
    latest_dt = all_dates[0]
    prev_dt = all_dates[1] if len(all_dates) > 1 else None
    
    draw_seq = [draws.get(d, set()) for d in reversed(all_dates[:10])]
    prev_actual = draws.get(prev_dt, set()) if prev_dt else set()

    recommendations = Counter()
    
    # 1. Apply Rules to each Matrix Block
    all_matrices = []
    for label, ed_data in [("D1", ed1), ("D2", ed2)]:
        m_sets = mw.get_expert_matrix_sets(ed_data, latest_dt)
        prev_sets = mw.get_expert_matrix_sets(ed_data, prev_dt) if prev_dt else [None]*len(m_sets)
        for i, block in enumerate(m_sets):
            for sub_i, name in enumerate(["L", "R"]):
                sub_block = [r[0:4] if sub_i == 0 else r[4:8] for r in block]
                prev_sub = [r[0:4] if sub_i == 0 else r[4:8] for r in (prev_sets[i] if prev_sets[i] else [[""]*8]*4)]
                metrics = da.calculate_matrix_metrics(sub_block, draw_seq, prev_sub)
                nums = [n for r in sub_block for n in r if n]
                all_matrices.append({"id": f"{label}-B{i+1}-{name}", "metrics": metrics, "nums": nums})

    # --- Rule 1: High Energy ---
    for m in all_matrices:
        if m['metrics']['energy'] > 18:
            for n in m['nums']: recommendations[n] += 2.0
            
    # --- Rule 4: Manifold Coupling ---
    # (Simplified coupling check)
    d1_nums = set([n for m in all_matrices if m['id'].startswith("D1") for n in m['nums']])
    d2_nums = set([n for m in all_matrices if m['id'].startswith("D2") for n in m['nums']])
    overlap = d1_nums.intersection(d2_nums)
    for n in overlap: recommendations[n] += 3.0
    
    # --- Rule 6: Repeating Energy ---
    for m in all_matrices:
        if m['metrics']['energy'] > 15:
            repeats = [n for n in m['nums'] if n in prev_actual]
            for n in repeats: recommendations[n] += 4.0

    # Final Sort
    top_picks = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)
    return top_picks[:20]

if __name__ == "__main__":
    picks = expert_inference()
    print("Top Picks Based on the 6 Laws:")
    for n, s in picks:
        print(f"{n}: {s}")
