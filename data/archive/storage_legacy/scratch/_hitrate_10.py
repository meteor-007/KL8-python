#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recent hit-rate summary for daily analysis."""
import re
import glob
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = {}
with open(os.path.join(ROOT, "kl8_history_final.txt"), encoding="utf-8") as f:
    for line in f:
        m = re.match(r"date:([^,]+),period:(\d+),numbers:(.+)", line.strip())
        if m:
            H[m.group(2)] = set(int(x) for x in m.group(3).split("-"))


def parse_list(text, key):
    m = re.search(key + r"[^[]*\[([^\]]+)\]", text)
    if not m:
        return []
    return [int(x.strip()) for x in m.group(1).split(",") if x.strip().isdigit()]


reports = sorted(glob.glob(os.path.join(ROOT, "reports", "daily_analysis_report_202607*.md")))
rows = []
for fp in reports:
    t = open(fp, encoding="utf-8").read()
    tm = re.search(r"目标期号[^0-9]*(\d{7})", t)
    if not tm:
        continue
    p = tm.group(1)
    if p not in H:
        continue
    a = H[p]
    he5 = parse_list(t, r"最终推荐 \(5 码\)")
    tr5 = parse_list(t, r"极秘 Top 5")
    tr12 = parse_list(t, r"极秘 Top 12")
    ai5 = parse_list(t, r"Top 5 置信度精选")
    ai12 = parse_list(t, r"Top 12 综合拦截")
    m = re.search(r"高置信定胆[^`\n]*`\[([^\]]+)\]`", t)
    pp = [int(x.strip()) for x in m.group(1).split(",") if x.strip().isdigit()] if m else []
    sec = re.search(r"最终精选爆发码[\s\S]*?重点防守", t)
    burst = [int(x) for x in re.findall(r"\*\*(\d+)\*\*", sec.group(0))] if sec else []
    gc = parse_list(t, r"高频共振集群")

    def h(lst):
        return (len(set(lst) & a), len(lst)) if lst else (0, 0)

    rows.append(
        {
            "period": p,
            "HE5": h(he5),
            "Tr5": h(tr5),
            "Tr12": h(tr12),
            "AI5": h(ai5),
            "AI12": h(ai12),
            "PP": h(pp),
            "Burst": h(burst),
            "GC": h(gc),
        }
    )

# last 10 with actuals
rows = rows[-10:]
print("=" * 78)
print(" Recent 10 periods hit summary (with actuals)")
print("=" * 78)
hdr = f"{'period':<10} {'HE5':>7} {'Tr5':>7} {'Tr12':>7} {'AI5':>7} {'AI12':>7} {'PP':>7} {'Burst':>7} {'GC':>7}"
print(hdr)
print("-" * 78)
for r in rows:
    def fmt(x):
        return f"{x[0]}/{x[1]}" if x[1] else "-"

    print(
        f"{r['period']:<10} {fmt(r['HE5']):>7} {fmt(r['Tr5']):>7} {fmt(r['Tr12']):>7} "
        f"{fmt(r['AI5']):>7} {fmt(r['AI12']):>7} {fmt(r['PP']):>7} {fmt(r['Burst']):>7} {fmt(r['GC']):>7}"
    )

print("-" * 78)
for key, n in [
    ("HE5", 5),
    ("Tr5", 5),
    ("Tr12", 12),
    ("AI5", 5),
    ("AI12", 12),
    ("PP", 3),
    ("Burst", 5),
    ("GC", 5),
]:
    vals = [r[key][0] for r in rows if r[key][1] > 0]
    ns = [r[key][1] for r in rows if r[key][1] > 0]
    if not vals:
        print(f"  {key}: no data")
        continue
    avg = sum(vals) / len(vals)
    avg_n = sum(ns) / len(ns)
    lift = avg / (avg_n * 0.25) if avg_n else 0
    print(f"  {key}: avg hit {avg:.2f}/{avg_n:.1f}  Lift={lift:.2f}x  (N={len(vals)})")
