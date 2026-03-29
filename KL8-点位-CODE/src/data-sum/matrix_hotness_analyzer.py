import os
import re
from collections import defaultdict, Counter

# === 🛠️ Core Configuration (From Codebase) ===
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
    m1 = (m1 + [""]*4)[:4]; m2 = (m2 + [""]*4)[:4]
    return [x.zfill(2) if x and x not in {".","-","_"} else "" for x in m1], [x.zfill(2) if x and x not in {".","-","_"} else "" for x in m2]

def get_expert_matrix_sets(filepath):
    """Parses a file into lists of 4x4 matrix blocks."""
    if not os.path.exists(filepath): return []
    blocks = []
    curr_m1, curr_m2 = [], []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip() or "→" not in line: 
                if curr_m1:
                    blocks.append(curr_m1); blocks.append(curr_m2)
                    curr_m1, curr_m2 = [], []
                continue
            r1, r2 = parse_group_line(line)
            curr_m1.append(r1); curr_m2.append(r2)
            if len(curr_m1) == 4:
                blocks.append(curr_m1); blocks.append(curr_m2)
                curr_m1, curr_m2 = [], []
    if curr_m1:
        blocks.append(curr_m1 + [[""]*4]*(4-len(curr_m1)))
        blocks.append(curr_m2 + [[""]*4]*(4-len(curr_m2)))
    return blocks

def analyze_matrix_hotness(date_str, hot_numbers):
    f1 = os.path.join(BASE_DIR, date_str, f"{date_str}-data1.txt")
    f2 = os.path.join(BASE_DIR, date_str, f"{date_str}-data2.txt")
    
    m1_blocks = get_expert_matrix_sets(f1)
    m2_blocks = get_expert_matrix_sets(f2)
    
    all_blocks = []
    for b in m1_blocks: all_blocks.append(("Data1", b))
    for b in m2_blocks: all_blocks.append(("Data2", b))
    
    results = []
    for idx, (src, block) in enumerate(all_blocks):
        score = 0
        nums_present = []
        for r in range(4):
            for c in range(4):
                val = block[r][c]
                if val:
                    local_score = 1.0
                    if val in hot_numbers: local_score += 2.5 # Weight for identified hot numbers
                    score += local_score
                    nums_present.append(val)
        
        # Calculate density (MD)
        density = len(nums_present) / 16.0
        # Final Score adjustment based on density
        final_score = score * (1 + density)
        results.append({
            "id": f"{src}-Block{idx+1}",
            "score": final_score,
            "density": density,
            "nums": sorted(list(set(nums_present)))
        })
    
    return sorted(results, key=lambda x: x["score"], reverse=True)

if __name__ == "__main__":
    # User's Hot Numbers
    hot_nums = ["08", "75", "03", "02", "52", "79"]
    target_date = "20260325"
    
    rankings = analyze_matrix_hotness(target_date, hot_nums)
    
    print(f"\n🔥 KL8 Matrix Area Hotness Analysis (Period {target_date}) 🔥")
    print("-" * 60)
    for i, res in enumerate(rankings[:5]):
        status = "🌟 BEST" if i == 0 else "🔥 HOT"
        print(f"[{status}] {res['id']}")
        print(f"   Density: {res['density']:.1%}")
        print(f"   Score: {res['score']:.2f}")
        print(f"   Key Numbers: {', '.join(res['nums'][:8])}...")
        print("-" * 60)
    
    best = rankings[0]
    print(f"\n✅ RECOMENDATION: Focus on {best['id']} area.")
    print(f"Logic: This block shows maximal structural resonance with the current period's 'Repeat' numbers.")
