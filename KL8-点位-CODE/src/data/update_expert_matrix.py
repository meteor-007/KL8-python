import os
import json
import re

def update_expert_matrix():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) 
    data_sum_dir = os.path.join(base_dir, "src", "data-sum")
    history_file = os.path.join(base_dir, "src", "data", "kl8_history_final.txt")

    # 1. Load actual draws
    actual_draws = {}
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                m = re.match(r"date:([^,]+),period:([^,]+),numbers:([\d\-]+)", line)
                if m:
                    date_str = m.group(1).replace('-', '')
                    nums = [int(n) for n in m.group(3).split('-')]
                    actual_draws[date_str] = nums

    # 2. Parse datasets
    expert_dates = []
    # To keep reading order, we will store a list of numbers for each date in exact reading order
    file_reading_order = {}
    
    if os.path.exists(data_sum_dir):
        for item in os.listdir(data_sum_dir):
            date_dir = os.path.join(data_sum_dir, item)
            if os.path.isdir(date_dir) and re.match(r"^\d{8}$", item):
                txt_file = os.path.join(date_dir, f"{item}-data.txt")
                if os.path.exists(txt_file):
                    expert_dates.append(item)
                    ordered_nums = []
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if '→' in line:
                                parts = line.split('→')
                                if len(parts) > 1:
                                    for num_str in parts[1].strip().split():
                                        try:
                                            n = int(num_str)
                                            ordered_nums.append(n)
                                        except: pass
                    file_reading_order[item] = ordered_nums

    expert_dates.sort()

    if not expert_dates:
        print("No expert data found.")
        return

    # Determine unique numbers ordered by the latest available reading sequence
    latest_date = expert_dates[-1]
    unique_ordered_nums = []
    seen = set()
    # first pass: latest day
    for n in file_reading_order[latest_date]:
        if n not in seen:
            seen.add(n)
            unique_ordered_nums.append(n)

    # Add any remaining numbers from older days that weren't in the latest day
    for d in expert_dates[:-1][::-1]:
        for n in file_reading_order[d]:
            if n not in seen:
                seen.add(n)
                unique_ordered_nums.append(n)

    # Finally, add any numbers strictly 1-80 not seen at all
    for n in range(1, 81):
        if n not in seen:
            seen.add(n)
            unique_ordered_nums.append(n)

    # 3. Build UI representation
    # matrix structure: array of rows
    # each row represents a date: { "date": "20260324", "cells": { "43": "hit", "41": "missed" } }
    
    matrix_rows = []
    for date in expert_dates:
        actual = actual_draws.get(date, [])
        expert_set = set(file_reading_order.get(date, []))
        
        cells = {}
        for num in unique_ordered_nums:
            in_expert = num in expert_set
            in_actual = num in actual
            
            if in_expert and in_actual:
                st = 'hit'
            elif in_expert and not in_actual:
                st = 'missed_prediction'
            elif not in_expert and in_actual:
                st = 'unexpected_hit'
            else:
                st = 'none'
            cells[num] = st
            
        matrix_rows.append({
            "date": date,
            "cells": cells
        })

    output = {
        "columns": unique_ordered_nums,
        "rows": matrix_rows
    }

    json_path = os.path.join(base_dir, "src", "data", "expert_matrix.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("expert_matrix.json updated.")

if __name__ == "__main__":
    update_expert_matrix()
