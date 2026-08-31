# -*- coding: utf-8 -*-
"""Compute recent hit rates + internal purification for daily panel."""
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

hist = {}
for line in (ROOT / "kl8_history_final.txt").open(encoding="utf-8"):
    m = re.search(r"date:(\d{4}-\d{2}-\d{2}),period:(\d+),numbers:([0-9\-]+)", line)
    if m:
        hist[m.group(2)] = set(int(x) for x in m.group(3).split("-"))

points = {}
for line in (ROOT / "daily_points.txt").open(encoding="utf-8"):
    m = re.search(r"date:(\d{4}-\d{2}-\d{2}),period:(\d+)", line)
    if m:
        points[m.group(1).replace("-", "")] = m.group(2)


def parse_list(s: str):
    return [int(x) for x in re.findall(r"\d+", s) if 1 <= int(x) <= 80]


def extract(text: str, *patterns: str):
    for p in patterns:
        m = re.search(p, text)
        if m:
            return parse_list(m.group(1))
    return []


def section_two(text: str) -> str:
    m = re.search(r"## 二、.*?(?=## 📊|## 附录|\Z)", text, re.S)
    return m.group(0) if m else text


rows = []
for rp in sorted((ROOT / "reports").glob("daily_analysis_report_202607*.md")):
    date = rp.stem.replace("daily_analysis_report_", "")
    period = points.get(date)
    if not period or period not in hist:
        continue
    text = section_two(rp.read_text(encoding="utf-8"))
    he5 = extract(text, r"最终推荐 \(5 码\).*?`\[([^\]]+)\]")
    tr5 = extract(text, r"极秘 Top 5.*?`\[([^\]]+)\]")
    tr12 = extract(text, r"极秘 Top 12.*?`\[([^\]]+)\]")
    ai5 = extract(text, r"Top 5 置信度精选.*?`\[([^\]]+)\]")
    ai12 = extract(text, r"Top 12 综合拦截.*?`\[([^\]]+)\]")
    actual = hist[period]

    def hits(pred, n=None):
        if not pred:
            return None
        p = pred[:n] if n else pred
        return len(set(p) & actual), len(p)

    h5, t5, t12, a5, a12 = hits(he5, 5), hits(tr5, 5), hits(tr12, 12), hits(ai5, 5), hits(ai12, 12)
    if not all([h5, t5, t12, a5, a12]):
        continue
    rows.append((period, h5, t5, t12, a5, a12, date))

rows = sorted(rows, key=lambda x: x[0])[-10:]
print("period\tHE5\tTr5\tTr12\tAI5\tAI12")
for r in rows:
    print(f"{r[0]}\t{r[1][0]}/{r[1][1]}\t{r[2][0]}/{r[2][1]}\t{r[3][0]}/{r[3][1]}\t{r[4][0]}/{r[4][1]}\t{r[5][0]}/{r[5][1]}")


def avg(idx, den):
    vals = [r[idx][0] for r in rows]
    mean = sum(vals) / len(vals)
    return mean, mean / (den * 0.25)


for name, idx, den in [("HE5", 1, 5), ("Tr5", 2, 5), ("Tr12", 3, 12), ("AI5", 4, 5), ("AI12", 5, 12)]:
    a, lift = avg(idx, den)
    print(f"{name}: avg={a:.2f}/{den} Lift={lift:.2f}x")

# Internal purification for today
today = (ROOT / "reports/daily_analysis_report_20260723.md").read_text(encoding="utf-8")
sec = section_two(today)
mods = {
    "HE5": extract(sec, r"最终推荐 \(5 码\).*?`\[([^\]]+)\]"),
    "Trinity": extract(sec, r"极秘 Top 12.*?`\[([^\]]+)\]"),
    "AI": extract(sec, r"Top 12 综合拦截.*?`\[([^\]]+)\]"),
    "mRMR": extract(sec, r"mRMR Top 12.*?`\[([^\]]+)\]"),
    "Pure": extract(sec, r"高置信定胆[^\n]*`\[([^\]]+)\]"),
    "Golden": extract(sec, r"高频共振集群.*?`\[([^\]]+)\]"),
    "Burst": [2, 38, 62, 51, 27],
}
pool = defaultdict(list)
for mname, nums in mods.items():
    for n in nums:
        pool[n].append(mname)
tiers = {4: [], 3: [], 2: [], 1: []}
for n, srcs in sorted(pool.items()):
    tiers[min(len(srcs), 4)].append((n, srcs))
print("DIAMOND", tiers[4])
print("GOLD", tiers[3])
print("SILVER", tiers[2])
print("COPPER_COUNT", len(tiers[1]))

prev = (ROOT / "reports/daily_analysis_report_20260722.md").read_text(encoding="utf-8")
m = re.search(r"钻石级[^\n]*：\[([^\]]+)\]", prev)
diamond = parse_list(m.group(1)) if m else []
copper_m = re.search(r"银级[^\n]*：\[([^\]]+)\]", prev)
silver = parse_list(copper_m.group(1)) if copper_m else []
actual193 = hist["2026193"]
dh = len(set(diamond) & actual193) if diamond else 0
sh = len(set(silver) & actual193) if silver else 0
print(f"prev_diamond={diamond} hits={dh}/{len(diamond) or 1}")
print(f"prev_silver={silver} hits={sh}/{len(silver) or 1}")
disc = (dh / len(diamond) / (sh / len(silver))) if diamond and silver and sh else 0
print(f"disc_proxy={disc:.2f}x (diamond vs silver as copper proxy)")
