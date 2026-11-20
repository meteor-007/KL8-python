# -*- coding: utf-8 -*-
import xlrd
from collections import Counter

draws_dict = {}
with open("../Python-Project/data/storage/raw/kl8_history_final.txt", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = dict(kv.split(":", 1) for kv in line.split(",") if ":" in kv)
        if "period" in parts and "numbers" in parts:
            p = int(parts["period"])
            nums = [int(x) for x in parts["numbers"].replace("-", " ").split()]
            draws_dict[p] = nums

points_dict = {}
with open("../Python-Project/data/storage/raw/daily_points.txt", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = dict(kv.split(":", 1) for kv in line.split(",") if ":" in kv)
        if "period" in parts and "points" in parts:
            p = int(parts["period"])
            nums = [int(x) for x in parts["points"].split()]
            points_dict[p] = nums

wb = xlrd.open_workbook("file/快八293期找胆图.xls", formatting_info=False)

def _get_triplets(sheet_idx: int, target_p: int):
    sh = wb.sheet_by_index(sheet_idx)
    res = []
    for r in range(1, sh.nrows):
        pval = sh.cell_value(r, 0)
        if pval and str(pval).replace(".0", "").isdigit() and int(float(pval)) == target_p:
            for c in range(1, sh.ncols, 4):
                if c + 2 < sh.ncols:
                    try:
                        n1 = int(float(sh.cell_value(r, c)))
                        n2 = int(float(sh.cell_value(r, c + 1)))
                        n3 = int(float(sh.cell_value(r, c + 2)))
                        if 1 <= n1 <= 80 and 1 <= n2 <= 80 and 1 <= n3 <= 80:
                            res.append((n1, n2, n3))
                    except Exception:
                        pass
            break
    return res

def _get_kills(sheet_idx: int, target_p: int):
    sh = wb.sheet_by_index(sheet_idx)
    res_set = set()
    for r in range(1, sh.nrows):
        pval = sh.cell_value(r, 0)
        p_int = None
        if pval and str(pval).replace(".0", "").isdigit():
            p_int = int(float(pval))
            if p_int < 1000:
                p_int += 2026000
        if p_int == target_p:
            for c in range(1, sh.ncols):
                try:
                    num = int(float(sh.cell_value(r, c)))
                    if 1 <= num <= 80:
                        res_set.add(num)
                except Exception:
                    pass
            break
    return res_set

periods_list = list(range(2026293 - 10 + 1, 2026294))
print("Backtesting periods:", periods_list)

results = []
for p in periods_list:
    draw_actual = set(draws_dict.get(p, []))
    prev_draw = set(draws_dict.get(p - 1, []))
    pts = set(points_dict.get(p, []))
    all_trips = _get_triplets(13, p) + _get_triplets(14, p) + _get_triplets(15, p) + _get_triplets(16, p)
    trip_counts = Counter(n for t in all_trips for n in t)
    dk = _get_kills(17, p) & _get_kills(18, p)
    sk = (_get_kills(17, p) | _get_kills(18, p)) - dk

    scores = {}
    for num in range(1, 81):
        if num in dk:
            continue
        sc = trip_counts[num] * 2.0
        if num in pts:
            sc += 3.0
        if num in prev_draw:
            sc += 0.5
        if num in sk:
            sc -= 1.5
        scores[num] = sc

    sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    old_t5 = sorted_nums[:5]
    old_t10 = sorted_nums[:10]
    old_h5 = len(set(old_t5) & draw_actual)
    old_h10 = len(set(old_t10) & draw_actual)

    t5 = []
    used_zones_5 = set()
    rep_count = 0
    for num in sorted_nums:
        z = (num - 1) // 10
        is_rep = num in prev_draw
        if z not in used_zones_5:
            if is_rep and rep_count >= 2:
                continue
            t5.append(num)
            used_zones_5.add(z)
            if is_rep:
                rep_count += 1
            if len(t5) == 5:
                break
    if len(t5) < 5:
        for num in sorted_nums:
            if num not in t5:
                t5.append(num)
                if len(t5) == 5:
                    break

    t7 = list(t5)
    used_zones_7 = set((x - 1) // 10 for x in t7)
    for num in sorted_nums:
        z = (num - 1) // 10
        if num not in t7 and z not in used_zones_7:
            t7.append(num)
            used_zones_7.add(z)
            if len(t7) == 7:
                break
    if len(t7) < 7:
        for num in sorted_nums:
            if num not in t7:
                t7.append(num)
                if len(t7) == 7:
                    break

    t10 = list(t7)
    for num in sorted_nums:
        if num in pts and num not in t10:
            t10.append(num)
            if len(t10) == 10:
                break
    if len(t10) < 10:
        for num in sorted_nums:
            if num not in t10:
                t10.append(num)
                if len(t10) == 10:
                    break

    p2 = [t5[0], t5[1]]
    h_p2 = set(p2) & draw_actual
    h_t5 = set(t5) & draw_actual
    h_t7 = set(t7) & draw_actual
    h_t10 = set(t10) & draw_actual

    results.append({
        "period": p,
        "pair_2": p2,
        "pair_hits": len(h_p2),
        "top_5": t5,
        "top_5_hits": len(h_t5),
        "top_5_hit_nums": sorted(list(h_t5)),
        "top_7": t7,
        "top_7_hits": len(h_t7),
        "top_10": t10,
        "top_10_hits": len(h_t10),
        "top_10_hit_nums": sorted(list(h_t10)),
        "old_top_5_hits": old_h5,
        "old_top_10_hits": old_h10,
    })

header = f"{'Period':<10} | {'Pair':<10} | {'P2 Hit':<6} | {'Top5 Hit':<8} | {'Top5 Hit Nums':<18} | {'Top7 Hit':<8} | {'Top10 Hit':<10} | {'Old T5'}"
print(header)
print("-" * len(header))
for r in results:
    p2_str = f"{r['pair_2'][0]:02d}-{r['pair_2'][1]:02d}"
    nums_str = str(r['top_5_hit_nums'])
    print(f"{r['period']:<10} | {p2_str:<10} | {r['pair_hits']:<6} | {r['top_5_hits']:<8} | {nums_str:<18} | {r['top_7_hits']:<8} | {r['top_10_hits']:<10} | {r['old_top_5_hits']}")

tot_t5 = sum(r['top_5_hits'] for r in results)
tot_t7 = sum(r['top_7_hits'] for r in results)
tot_t10 = sum(r['top_10_hits'] for r in results)
tot_old5 = sum(r['old_top_5_hits'] for r in results)
print("-" * len(header))
print(f"Top5 Hit Rate: {tot_t5}/50 = {tot_t5/50*100:.1f}% (vs Old {tot_old5}/50 = {tot_old5/50*100:.1f}%)")
print(f"Top7 Hit Rate: {tot_t7}/70 = {tot_t7/70*100:.1f}%")
print(f"Top10 Hit Rate: {tot_t10}/100 = {tot_t10/100*100:.1f}%")
