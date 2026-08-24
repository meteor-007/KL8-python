# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "logs" / "kill_logs.jsonl"
periods = []
bad = 0
with p.open(encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            periods.append(str(d.get("period")))
        except Exception:
            bad += 1
            m = re.search(r'"period"\s*:\s*"(\d+)"', line)
            periods.append(m.group(1) if m else f"BAD@{i}")

nums = [int(x) for x in periods if str(x).isdigit()]
have = set(nums)
print("count", len(periods), "bad_json", bad)
print("last20", periods[-20:])
print("max", max(nums))
print("--- gap scan 2026190..2026199 ---")
for t in range(2026190, 2026200):
    print(t, "HAVE" if t in have else "MISSING")
