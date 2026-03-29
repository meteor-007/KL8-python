import os
import sys
import re
from collections import defaultdict, Counter
import numpy as np
import datetime

print(f"DEBUG: Script started at {datetime.datetime.now()}")
print(f"DEBUG: sys.executable is {sys.executable}")
print(f"DEBUG: Current working directory is {os.getcwd()}")

BASE_DIR = r"D:\Dpanqianyi\Python-Project\KL8-点位-CODE\src\data-sum"
HIST_FILE = r"D:\Dpanqianyi\Python-Project\KL8-点位-CODE\src\data\kl8_history_final.txt"

def parse_group_line(line_str):
    if "→" in line_str: line_str = line_str.split("→", 1)[1].strip()
    else: line_str = line_str.strip()
    if "|" in line_str:
        parts = line_str.split("|", 1); m1, m2 = parts[0].split(), parts[1].split()
    elif re.search(r'\s{2,}', line_str):
        parts = re.split(r'\s{2,}', line_str, maxsplit=1); m1, m2 = parts[0].split(), parts[1].split()
    else:
        tokens = line_str.split(); m1, m2 = tokens[:4], tokens[4:8]
    m1 = [x.zfill(2) if x and x not in {".","-","_"} else "" for x in m1]
    m2 = [x.zfill(2) if x and x not in {".","-","_"} else "" for x in m2]
    m1 = (m1 + [""]*4)[:4]
    m2 = (m2 + [""]*4)[:4]
    return m1, m2

def get_expert_matrix_sets(filepath):
    if not os.path.exists(filepath): return []
    blocks = []
    curr_m1, curr_m2 = [], []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or "矩阵" in line: continue
            if "→" not in line and not any(c.isdigit() for c in line): continue
            
            r1, r2 = parse_group_line(line)
            curr_m1.append(r1)
            curr_m2.append(r2)
            if len(curr_m1) == 4:
                blocks.append(curr_m1)
                blocks.append(curr_m2)
                curr_m1, curr_m2 = [], []
    if curr_m1:
        blocks.append(curr_m1 + [[""]*4]*(4-len(curr_m1)))
        blocks.append(curr_m2 + [[""]*4]*(4-len(curr_m2)))
    return blocks

def load_actual_history(history_file):
    actual_draws = {}
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.search(r"date:([^,]+),period:([^,]+),numbers:([\d\-]+)", line.strip())
                if m:
                    actual_draws[m.group(1).replace('-', '')] = set(n.zfill(2) for n in m.group(3).split('-'))
    return actual_draws

def run_analysis():
    output_path = os.path.join(BASE_DIR, "scientific_analysis_results.txt")
    f_out = open(output_path, "w", encoding="utf-8")
    def p(text):
        print(text)
        f_out.write(text + "\n")

    # 1. Load History
    draws = load_actual_history(HIST_FILE)
    
    # 2. Load Matrix Data
    date_dirs = sorted([d for d in os.listdir(BASE_DIR) if d.isdigit() and len(d) == 8])
    
    # Structure: history_data[date][source] = list of 4x4 blocks
    history_matrices = {}
    for date in date_dirs:
        history_matrices[date] = {
            "data1": get_expert_matrix_sets(os.path.join(BASE_DIR, date, f"{date}-data1.txt")),
            "data2": get_expert_matrix_sets(os.path.join(BASE_DIR, date, f"{date}-data2.txt"))
        }

    p(f"Loaded {len(date_dirs)} periods of data.")
    
    # ANALYSIS 1: Structural Stability (Positional Invariance)
    stability_scores = []
    for i in range(1, len(date_dirs)):
        d_prev, d_curr = date_dirs[i-1], date_dirs[i]
        overlap = 0
        total_cells = 0
        for src in ["data1", "data2"]:
            m_prev = history_matrices[d_prev][src]
            m_curr = history_matrices[d_curr][src]
            for b_idx in range(min(len(m_prev), len(m_curr))):
                for r in range(4):
                    for c in range(4):
                        if m_prev[b_idx][r][c] and m_prev[b_idx][r][c] == m_curr[b_idx][r][c]:
                            overlap += 1
                        total_cells += 1
        stability_scores.append((d_curr, overlap / total_cells if total_cells > 0 else 0))
    
    p("\n--- Structural Stability (Positional Invariance) ---")
    for d, s in stability_scores[-5:]:
        p(f"Date: {d}, Stability: {s:.2%}")

    # ANALYSIS 2: Hit Density Gradient (Energy Field)
    block_hit_stats = defaultdict(lambda: {"hits": 0, "total_periods": 0, "total_numbers": 0})
    for date in date_dirs:
        actual = draws.get(date)
        if not actual: continue
        for src in ["data1", "data2"]:
            blocks = history_matrices[date][src]
            for b_idx, block in enumerate(blocks):
                hits = 0
                nums = 0
                for r in range(4):
                    for c in range(4):
                        val = block[r][c]
                        if val:
                            nums += 1
                            if val in actual:
                                hits += 1
                key = f"{src}-B{b_idx+1}"
                block_hit_stats[key]["hits"] += hits
                block_hit_stats[key]["total_periods"] += 1
                block_hit_stats[key]["total_numbers"] += nums

    p("\n--- Block Performance (Energy Density) ---")
    sorted_blocks = sorted(block_hit_stats.items(), key=lambda x: (x[1]["hits"] / x[1]["total_numbers"]) if x[1]["total_numbers"] > 0 else 0, reverse=True)
    for name, stats in sorted_blocks[:10]:
        hr = (stats["hits"] / stats["total_numbers"]) * 100 if stats["total_numbers"] > 0 else 0
        p(f"Block: {name}, Hit Rate: {hr:.2f}% (Total Hits: {stats['hits']}, Total Numbers: {stats['total_numbers']})")

    # ANALYSIS 3: Cross-Manifold Entanglement (Resonance)
    resonance_history = []
    for date in date_dirs:
        actual = draws.get(date)
        m1 = history_matrices[date]["data1"]
        m2 = history_matrices[date]["data2"]
        resonance_nodes = []
        for b_idx in range(min(len(m1), len(m2))):
            for r in range(4):
                for c in range(4):
                    v1 = m1[b_idx][r][c]
                    v2 = m2[b_idx][r][c]
                    if v1 and v1 == v2:
                        is_hit = "HIT" if (actual and v1 in actual) else "MISS"
                        resonance_nodes.append((v1, f"B{b_idx+1}-R{r+1}-C{c+1}", is_hit))
        resonance_history.append((date, resonance_nodes))

    p("\n--- Cross-Manifold Resonance (Entanglement) ---")
    for date, nodes in resonance_history[-5:]:
        hits = [n for n, p, h in nodes if h == "HIT"]
        p(f"Date: {date}, Resonance Count: {len(nodes)}, Hits: {len(hits)} ({', '.join(hits)})")

    # ANALYSIS 4: Symmetery and Invariance
    coord_hits = Counter()
    coord_totals = Counter()
    for date in date_dirs:
        actual = draws.get(date)
        if not actual: continue
        for src in ["data1", "data2"]:
            blocks = history_matrices[date][src]
            for b_idx, block in enumerate(blocks):
                for r in range(4):
                    for c in range(4):
                        val = block[r][c]
                        if val:
                            coord_totals[(b_idx, r, c)] += 1
                            if val in actual:
                                coord_hits[(b_idx, r, c)] += 1
    
    p("\n--- Coord Accuracy (Top Spatial Invariants) ---")
    sorted_coords = sorted(coord_hits.keys(), key=lambda x: coord_hits[x]/coord_totals[x] if coord_totals[x] > 0 else 0, reverse=True)
    for coord in sorted_coords[:10]:
        rate = (coord_hits[coord] / coord_totals[coord]) * 100 if coord_totals[coord] > 0 else 0
        p(f"Coord: Block {coord[0]+1}, Row {coord[1]+1}, Col {coord[2]+1} | Accuracy: {rate:.2f}% ({coord_hits[coord]}/{coord_totals[coord]})")
    
    f_out.close()

if __name__ == "__main__":
    run_analysis()
