# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# verify 2026193 persistence
rows = [
    json.loads(l)
    for l in Path("logs/kill_logs.jsonl").read_text(encoding="utf-8").splitlines()
    if l.strip()
]
r = next(x for x in rows if x["period"] == "2026193")
cf = r["cross_feed"]
print("=== 2026193 log OK ===")
print("high:", r["high_conf_kills"])
print("mid:", r["mid_conf_kills"])
print("low:", r["low_conf_kills"])
print("safe:", r["safe_numbers"])
print("conf:", round(r["kill_confidence"], 4))
print("cov:", cf.get("kill_coverage"))
print("danger:", cf.get("danger"))
print("review:", cf.get("review"))
print("resonate:", cf.get("resonate"))
print("indep:", cf.get("independent_kills"))
print("prev:", cf.get("prev_review"))
print("win:", {k: cf.get("window_review", {}).get(k) for k in ("n", "status", "index", "avg_danger_miss_rate", "avg_resonate_hit_rate", "advice")})
print("sources:", list((cf.get("sources") or {}).keys()))
print("files:", Path("logs/control_panel_2026193.md").exists(), Path("logs/kill_report.txt").exists())

# recompute window with fixed logic
from core.data_loader import DataLoader
from core.cross_feed import review_cross_feed_window, review_previous_cross_feed

dl = DataLoader()
dl.load()
opened = {d.period: set(d.numbers) for d in dl.history}
win = review_cross_feed_window(rows, opened, n=5)
print("\n=== window recompute ===")
print(win["status"], win["index"], "zero-aware")
for row in win["rows"]:
    print(row["period"], row["status"], "dmr=", row.get("danger_miss_rate"), "rhr=", row.get("resonate_hit_rate"), "idx=", row.get("index"))

# 2026192 review
prev = next(x for x in rows if x["period"] == "2026192")
rev = review_previous_cross_feed(prev, opened["2026192"])
print("\n=== 2026192 feed review ===")
print(rev)
