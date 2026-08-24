# -*- coding: utf-8 -*-
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lines = (root / "logs" / "kill_logs.jsonl").read_text(encoding="utf-8").splitlines()
found = {}
for l in lines:
    if not l.strip():
        continue
    try:
        d = json.loads(l)
    except json.JSONDecodeError:
        continue
    found[d.get("period")] = bool(d.get("cross_feed"))

for t in ["2026195", "2026196", "2026197", "2026198", "2026199"]:
    if t not in found:
        print(t, "MISSING")
    elif found[t]:
        print(t, "OK_CF")
    else:
        print(t, "OK_NO_CF")

for t in ["2026196", "2026197", "2026198", "2026199"]:
    p = root / "logs" / f"control_panel_{t}.md"
    print("panel", t, p.exists())
