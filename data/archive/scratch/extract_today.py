# -*- coding: utf-8 -*-
from pathlib import Path
import json
import re
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
report = (ROOT / "reports/daily_analysis_report_20260721.md").read_text(encoding="utf-8")
state = json.loads((ROOT / "cache/self_learning_state.json").read_text(encoding="utf-8"))
latest = state["history"][0]
assert latest["target_issue"] == "2026192", latest["target_issue"]

draws = {}
for line in (ROOT / "kl8_history_final.txt").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    parts = dict(p.split(":", 1) for p in line.split(","))
    draws[parts["period"]] = set(int(x) for x in parts["numbers"].split("-"))


def hit(picks, period):
    act = draws.get(str(period), set())
    pk = [int(x) for x in picks]
    h = [n for n in pk if n in act]
    n = len(pk)
    nh = len(h)
    lift = (nh / n / 0.25) if n else 0.0
    return nh, n, lift, h


# unique snaps by target_issue (first = newest)
seen = set()
snaps = []
for h in state["history"]:
    ti = h.get("target_issue")
    if not ti or ti in seen:
        continue
    seen.add(ti)
    snaps.append(h)

out = []
out.append("LATEST_KEYS=" + ",".join(sorted(latest.keys())))
for k in [
    "target_issue",
    "latest_issue",
    "environment",
    "trinity_weights",
    "top5",
    "top12",
    "conf_top5",
    "conf_top12",
    "golden_core",
    "mrmr_top12",
    "he5",
    "hidden_energy_5",
    "pure_pool_top",
    "pure_pool_old_rule",
    "pure_pool_lr",
    "pure_pool_all",
    "deep_picks",
    "deep_kills",
    "deep_consensus",
    "gauss_top5",
    "cluster_top5",
    "fourier_top5",
    "fusion_top5",
    "kl_msg",
    "stacking_level",
    "entropy",
]:
    if k in latest:
        out.append(f"{k}={latest[k]!r}")

m = re.search(r"最终推荐 \(5 码\)[：:]\s*`?\[([^\]]+)\]", report)
he5_today = [int(x) for x in re.findall(r"\d+", m.group(1))] if m else []
out.append(f"HE5_FROM_REPORT={he5_today}")

# parse more from report
patterns = {
    "trinity5": r"极秘 Top 5[：:]\s*`?\[([^\]]+)\]",
    "trinity12": r"极秘 Top 12[：:]\s*`?\[([^\]]+)\]",
    "ai5": r"Top 5 置信度精选[：:]\s*`?\[([^\]]+)\]",
    "ai12": r"Top 12 综合拦截[：:]\s*`?\[([^\]]+)\]",
    "golden": r"高频共振集群[：:]\s*`?\[([^\]]+)\]",
    "mrmr": r"mRMR Top 12[：:]\s*`?\[([^\]]+)\]",
    "pp_all": r"纯净池号码[：:]\s*`?\[([^\]]+)\]",
    "pp_old": r"旧规则高置信[^\n]*[：:]\s*`?\[([^\]]+)\]",
    "pp_lr": r"LR定胆[^\n]*[：:]\s*`?\[([^\]]+)\]",
    "pp_high": r"高置信定胆[^\n]*[：:]\s*`?\[([^\]]+)\]",
}
parsed = {}
for name, pat in patterns.items():
    mm = re.search(pat, report)
    parsed[name] = [int(x) for x in re.findall(r"\d+", mm.group(1))] if mm else []
    out.append(f"MD_{name}={parsed[name]}")

# scheme2 from report tables
burst = re.findall(
    r"\|\s*\d+\s*\|\s*\*\*(\d+)\*\*",
    report.split("最终精选爆发码")[1].split("重点防守")[0] if "最终精选爆发码" in report else "",
)
defend = re.findall(
    r"\|\s*\d+\s*\|\s*\*\*(\d+)\*\*",
    report.split("重点防守号码")[1].split("<details>")[0] if "重点防守号码" in report else "",
)
parsed["burst"] = [int(x) for x in burst[:5]]
parsed["defend"] = [int(x) for x in defend[:3]]
out.append(f"MD_burst={parsed['burst']}")
out.append(f"MD_defend={parsed['defend']}")

consensus = []
if "跨规则共识号码" in report:
    block = report.split("跨规则共识号码")[1].split("###")[0].split("####")[0]
    consensus = [int(x) for x in re.findall(r"号码\s*`(\d+)`", block)]
parsed["consensus"] = consensus
out.append(f"MD_consensus={consensus}")

# high-order
for label, key in [
    ("高斯", "gauss"),
    ("聚类", "cluster"),
    ("傅里叶", "fourier"),
    ("终极推荐", "fusion"),
]:
    mm = re.search(rf"{label}[^\n]*[：:]\s*`?\[([^\]]+)\]", report)
    if not mm:
        mm = re.search(rf"{label}[^\n]*最优\s*5\s*码[^\n]*[：:]\s*`?\[([^\]]+)\]", report)
    parsed[key] = [int(x) for x in re.findall(r"\d+", mm.group(1))] if mm else latest.get(f"{key}_top5", [])
    out.append(f"MD_{key}={parsed[key]}")

# Review 2026191
prev = next(h for h in snaps if h["target_issue"] == "2026191")
out.append("---REVIEW_2026191---")
review_map = {
    "Trinity5": prev.get("top5", []),
    "Trinity12": prev.get("top12", []),
    "AI5": prev.get("conf_top5", []),
    "AI12": prev.get("conf_top12", []),
    "PureHigh": prev.get("pure_pool_top", []),
    "PureOld": prev.get("pure_pool_old_rule", []),
    "PureLR": prev.get("pure_pool_lr", []),
    "PureAll": prev.get("pure_pool_all", []),
    "Burst": prev.get("deep_picks", []),
    "Defend": prev.get("deep_kills", []),
    "Consensus": prev.get("deep_consensus", []),
    "HE5": [41, 42, 44, 54, 70],  # from yesterday report
    "Golden": [1, 11, 12, 33, 42, 55],
    "mRMR": [77, 69, 33, 38, 12, 39, 30, 7, 27, 42, 11, 67],
}
for name, picks in review_map.items():
    if not picks:
        out.append(f"{name}: EMPTY")
        continue
    nh, n, lift, h = hit(picks, "2026191")
    if name == "Defend":
        miss = [x for x in picks if x not in draws["2026191"]]
        false_kill = [x for x in picks if x in draws["2026191"]]
        out.append(f"{name}: success={len(miss)}/{n} avoided={miss} false_kill={false_kill}")
    else:
        out.append(f"{name}: {nh}/{n} Lift={lift:.2f}x hits={h} picks={picks}")

# 10-period trend from reports table + new period
# Build from snaps where possible
out.append("---TREND---")
trend = []
for h in snaps:
    ti = h["target_issue"]
    if ti not in draws:
        continue
    tr5 = hit(h.get("top5", []), ti)
    tr12 = hit(h.get("top12", []), ti)
    ai5 = hit(h.get("conf_top5", []), ti)
    ai12 = hit(h.get("conf_top12", []), ti)
    he5p = None
    # try fields
    for k in ("he5", "hidden_energy_5", "he5_final", "final_he5"):
        if h.get(k):
            he5p = hit(h[k], ti)
            break
    trend.append((ti, he5p, tr5, tr12, ai5, ai12))
    if len(trend) >= 12:
        break

for row in trend[:10]:
    ti, he5p, tr5, tr12, ai5, ai12 = row
    he_s = f"{he5p[0]}/{he5p[1]}" if he5p else "?"
    out.append(
        f"{ti} HE5={he_s} Tr5={tr5[0]}/{tr5[1]} Tr12={tr12[0]}/{tr12[1]} AI5={ai5[0]}/{ai5[1]} AI12={ai12[0]}/{ai12[1]}"
    )

# Internal resonance for today
modules = {
    "HE5": he5_today or latest.get("he5") or [],
    "Trinity": latest.get("top12", []),
    "AI": latest.get("conf_top12", []),
    "mRMR": parsed.get("mrmr") or latest.get("mrmr_top12") or [],
    "Pure": latest.get("pure_pool_top") or parsed.get("pp_high") or [],
    "HighOrd": parsed.get("fusion") or latest.get("fusion_top5") or [],
    "Golden": parsed.get("golden") or latest.get("golden_core") or [],
}
pool = defaultdict(list)
for mod, nums in modules.items():
    for n in nums:
        pool[int(n)].append(mod)
diamond = sorted([n for n, s in pool.items() if len(s) >= 4])
gold = sorted([n for n, s in pool.items() if len(s) == 3])
silver = sorted([n for n, s in pool.items() if len(s) == 2])
copper = sorted([n for n, s in pool.items() if len(s) == 1])
out.append("---PURIFY---")
out.append(f"modules={ {k:v for k,v in modules.items()} }")
out.append(f"diamond={diamond}")
out.append(f"gold={gold}")
out.append(f"silver={silver}")
out.append(f"copper_count={len(copper)}")

payload = {
    "date": "2026-07-21",
    "target": "2026192",
    "latest_draw": "2026191",
    "latest": {k: latest.get(k) for k in latest},
    "parsed": parsed,
    "he5": he5_today,
    "purify": {
        "modules": {k: list(map(int, v)) for k, v in modules.items()},
        "diamond": diamond,
        "gold": gold,
        "silver": silver,
        "copper": copper,
        "pool": {str(k): v for k, v in pool.items()},
    },
    "review_2026191": {k: list(v) for k, v in review_map.items()},
}
(ROOT / "scratch/today_payload.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
)
(ROOT / "scratch/extract_out.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
print("WROTE scratch/today_payload.json")
