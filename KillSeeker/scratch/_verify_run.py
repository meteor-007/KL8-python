# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.paths import KILL_LOGS, KILL_REPORT, OUTPUT_DIR

lines = Path(KILL_LOGS).read_text(encoding="utf-8").strip().splitlines()
last = json.loads(lines[-1])
print("LAST_PERIOD", last["period"])
print("HAS_CF", "cross_feed" in last)
print("HIGH", last["high_conf_kills"])
print("MID", last["mid_conf_kills"])
print("LOW", last["low_conf_kills"])
print("SAFE", last["safe_numbers"])
print("CONF", last["kill_confidence"])
print("ENG", last.get("engine_contributions"))
cf = last.get("cross_feed", {})
print("DANGER", cf.get("danger"))
print("REVIEW", cf.get("review"))
print("RESONATE", cf.get("resonate"))
print("INDEP", cf.get("independent_kills"))
print("COV", cf.get("kill_coverage"))
print("ADVICE", cf.get("advice"))
print("PREV", cf.get("prev_review"))
win = cf.get("window_review") or {}
print(
    "WIN",
    {
        k: win.get(k)
        for k in [
            "n",
            "index",
            "status",
            "avg_danger_miss_rate",
            "avg_resonate_hit_rate",
            "advice",
        ]
    },
)
print("SOURCES", list((cf.get("sources") or {}).keys()))
for name, nums in (cf.get("sources") or {}).items():
    print(f"  SRC {name}: {nums}")
print("DANGER_SRC", cf.get("danger_sources"))
print("RESONATE_SRC", cf.get("resonate_sources"))
print("LEAK", cf.get("leak_downgrade"))
print("BOOST", cf.get("stable_kill_boost"))

cp = OUTPUT_DIR / f"control_panel_{last['period']}.md"
print("CONTROL_PANEL", cp, "EXISTS", cp.exists(), "SIZE", cp.stat().st_size if cp.exists() else 0)
print("KILL_REPORT", KILL_REPORT.exists(), KILL_REPORT.stat().st_size if KILL_REPORT.exists() else 0)

agg = Path(r"D:\Dpanqianyi\Python-Project\数据汇总复盘\logs")
print("AGG_DIR", agg.exists())
if agg.exists():
    files = sorted(agg.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    for f in files:
        txt = f.read_text(encoding="utf-8", errors="replace")
        print(
            f"  {f.name} has_194={'2026194' in txt} has_193={'2026193' in txt} size={f.stat().st_size}"
        )

# recompute near-window hit rates
from core.data_loader import DataLoader
from main import load_all_predictions, review_prediction

dl = DataLoader()
dl.load()
opened = {d.period: set(d.numbers) for d in dl.history}
preds = load_all_predictions()
recent = []
seen = set()
for pred in reversed(preds):
    p = pred.get("period", "")
    if p in seen or p not in opened or p == last["period"]:
        continue
    seen.add(p)
    recent.append(review_prediction(pred, opened[p]))
    if len(recent) >= 10:
        break
print("\n=== NEAR WINDOW DETAIL ===")
for r in reversed(recent):
    hr = r["high_hit"] / r["high_total"] if r["high_total"] else 0
    mr = r["mid_hit"] / r["mid_total"] if r["mid_total"] else 0
    ar = r["all_hit"] / r["all_total"] if r["all_total"] else 0
    sr = r["safe_hit"] / r["safe_total"] if r["safe_total"] else 0
    print(
        f"{r['period']}: H={r['high_hit']}/{r['high_total']}({hr:.1%}) "
        f"M={r['mid_hit']}/{r['mid_total']}({mr:.1%}) "
        f"A={r['all_hit']}/{r['all_total']}({ar:.1%}) "
        f"S={r['safe_hit']}/{r['safe_total']}({sr:.1%})"
    )
th = sum(r["high_hit"] for r in recent)
th_t = sum(r["high_total"] for r in recent)
tm = sum(r["mid_hit"] for r in recent)
tm_t = sum(r["mid_total"] for r in recent)
ta = sum(r["all_hit"] for r in recent)
ta_t = sum(r["all_total"] for r in recent)
ts = sum(r["safe_hit"] for r in recent)
ts_t = sum(r["safe_total"] for r in recent)
print(
    f"MEAN10: H={th}/{th_t}={th/th_t:.1%} M={tm}/{tm_t}={tm/tm_t:.1%} "
    f"A={ta}/{ta_t}={ta/ta_t:.1%} S={ts}/{ts_t}={ts/ts_t:.1%} "
    f"vs75%={(ta/ta_t/0.75-1)*100:+.1f}%"
)

# 2026193 detailed review
for pred in preds:
    if pred.get("period") == "2026193":
        r = review_prediction(pred, opened["2026193"])
        print("\n=== 2026193 REVIEW ===")
        print(r)
        break
