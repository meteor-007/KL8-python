# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

rows = [
    json.loads(l)
    for l in Path("logs/kill_logs.jsonl").read_text(encoding="utf-8").splitlines()
    if l.strip()
]
for r in rows[-3:]:
    cf = r.get("cross_feed") or {}
    prev = cf.get("prev_review") or {}
    win = cf.get("window_review") or {}
    print(
        f"period={r['period']} conf={r.get('kill_confidence'):.3f} "
        f"cov={cf.get('kill_coverage')} danger={cf.get('danger')} "
        f"resonate={cf.get('resonate')}"
    )
    print(
        f"  prev_status={prev.get('status')} idx={prev.get('index')} "
        f"win_status={win.get('status')} win_idx={win.get('index')}"
    )
    print(f"  sources={list((cf.get('sources') or {}).keys())}")

from core.cross_feed import collect_upstream

srcs = collect_upstream("2026193")
print("upstream 2026193:")
for s in srcs:
    print(f"  {s.name}: {s.numbers[:12]} ({s.note})")
