# -*- coding: utf-8 -*-
"""Post-backfill hit-rate + recommendation dump."""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from core.data_loader import DataLoader
from main import load_all_predictions, review_prediction

dl = DataLoader()
dl.load()
opened = {d.period: set(d.numbers) for d in dl.history}
preds = {p["period"]: p for p in load_all_predictions()}

print("=== Backfill periods review (opened only) ===")
for t in ["2026196", "2026197", "2026198", "2026199"]:
    p = preds.get(t)
    if not p:
        print(t, "MISSING")
        continue
    if t not in opened:
        print(t, "PENDING (target)", "high=", p["high_conf_kills"], "cf=", bool(p.get("cross_feed")))
        continue
    r = review_prediction(p, opened[t])
    print(
        t,
        f"H{r['high_hit']}/{r['high_total']}={r['high_hit']/r['high_total']:.0%}",
        f"M{r['mid_hit']}/{r['mid_total']}={r['mid_hit']/r['mid_total']:.0%}",
        f"A{r['all_hit']}/{r['all_total']}={r['all_hit']/r['all_total']:.0%}",
        f"S{r['safe_hit']}/{r['safe_total']}={r['safe_hit']/r['safe_total']:.0%}",
        "leak_h", r["high_miss"],
    )

print("\n=== Recent 10 opened (excl pending) ===")
results = []
seen = set()
for pred in reversed(load_all_predictions()):
    period = pred.get("period", "")
    if period in seen or period not in opened:
        continue
    seen.add(period)
    results.append(review_prediction(pred, opened[period]))
    if len(results) >= 10:
        break

for r in reversed(results):
    print(
        r["period"],
        f"H{r['high_hit']}/{r['high_total']}",
        f"M{r['mid_hit']}/{r['mid_total']}",
        f"A{r['all_hit']}/{r['all_total']}",
        f"S{r['safe_hit']}/{r['safe_total']}",
    )

th = sum(r["high_hit"] for r in results)
tht = sum(r["high_total"] for r in results)
tm = sum(r["mid_hit"] for r in results)
tmt = sum(r["mid_total"] for r in results)
ta = sum(r["all_hit"] for r in results)
tat = sum(r["all_total"] for r in results)
ts = sum(r["safe_hit"] for r in results)
tst = sum(r["safe_total"] for r in results)
print(f"\nSUM10 high {th}/{tht}={th/tht:.1%}")
print(f"SUM10 mid  {tm}/{tmt}={tm/tmt:.1%}")
print(f"SUM10 all  {ta}/{tat}={ta/tat:.1%}")
print(f"SUM10 safe {ts}/{tst}={ts/tst:.1%}")

# last 5 including backfill opened
print("\n=== Last5 opened ===")
last5 = results[:5]
th5 = sum(r["high_hit"] for r in last5); tht5 = sum(r["high_total"] for r in last5)
ta5 = sum(r["all_hit"] for r in last5); tat5 = sum(r["all_total"] for r in last5)
print(f"L5 high {th5}/{tht5}={th5/tht5:.1%}  all {ta5}/{tat5}={ta5/tat5:.1%}")

# dump CF summary for control panel periods
print("\n=== CF summaries ===")
for t in ["2026196", "2026197", "2026198", "2026199"]:
    p = preds[t]
    cf = p.get("cross_feed") or {}
    print(f"\n[{t}] conf={p['kill_confidence']:.1%}")
    print("  high", p["high_conf_kills"])
    print("  mid ", p["mid_conf_kills"])
    print("  low ", p["low_conf_kills"])
    print("  safe", p["safe_numbers"])
    print("  danger", cf.get("danger"), cf.get("danger_sources"))
    print("  review", cf.get("review"))
    print("  resonate", cf.get("resonate"))
    print("  indep", cf.get("independent_kills"))
    print("  coverage", cf.get("kill_coverage"), "chaos", cf.get("chaos_flag"))
    print("  advice", cf.get("advice"))
    pr = cf.get("prev_review") or {}
    print("  prev", pr.get("status"), pr.get("index"), pr.get("advice"))
    wr = cf.get("window_review") or {}
    print("  window", wr.get("status"), wr.get("index"), wr.get("advice"))
    print("  boost", cf.get("stable_kill_boost"), "leak_down", cf.get("leak_downgrade"))
