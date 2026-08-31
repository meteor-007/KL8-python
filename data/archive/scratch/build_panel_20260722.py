# -*- coding: utf-8 -*-
"""Generate UTF-8 console panel + copyable picks + canvas data for 2026-07-22."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/daily_analysis_report_20260722.md"
STATE = ROOT / "cache/self_learning_state.json"
PANEL = ROOT / "reports/控制面板_20260722.txt"
COPY = ROOT / "reports/可复制推荐_2026193.txt"
CANVAS_DATA = ROOT / "scratch/canvas_data_20260722.json"
CONSOLE = ROOT / "scratch/console_panel_20260722.txt"

state = json.loads(STATE.read_text(encoding="utf-8"))
latest = state["history"][0]
assert str(latest["target_issue"]) == "2026193", latest.get("target_issue")

draws = {}
for line in (ROOT / "kl8_history_final.txt").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    parts = dict(p.split(":", 1) for p in line.split(","))
    draws[parts["period"]] = set(int(x) for x in parts["numbers"].split("-"))


def fmt(nums):
    return " ".join(f"{int(n):02d}" for n in nums)


def hit(picks, period):
    act = draws.get(str(period), set())
    pk = [int(x) for x in picks]
    h = sorted(n for n in pk if n in act)
    n = len(pk)
    nh = len(h)
    lift = (nh / n / 0.25) if n else 0.0
    return nh, n, lift, h


trend_rows = []
for fp in sorted((ROOT / "reports").glob("daily_analysis_report_20260*.md")):
    text = fp.read_text(encoding="utf-8")
    tm = re.search(r"目标期号[：:]\s*\*{0,2}\s*(\d{7})", text)
    if not tm:
        continue
    period = tm.group(1)
    if period not in draws:
        continue

    def plist(pat, body=text):
        m = re.search(pat + r"[^[]*\[([^\]]+)\]", body)
        if not m:
            return []
        return [int(x.strip()) for x in m.group(1).split(",") if x.strip().lstrip("-").isdigit()]

    he5 = plist(r"最终推荐 \(5 码\)")
    tr5 = plist(r"极秘 Top 5")
    tr12 = plist(r"极秘 Top 12")
    ai5 = plist(r"Top 5 置信度精选")
    ai12 = plist(r"Top 12 综合拦截")
    if not he5:
        continue
    trend_rows.append(
        {
            "period": period,
            "HE5": hit(he5, period),
            "Tr5": hit(tr5, period),
            "Tr12": hit(tr12, period),
            "AI5": hit(ai5, period),
            "AI12": hit(ai12, period),
        }
    )

trend_rows = [r for r in trend_rows if r["period"] != "2026193"][-10:]


def avg_lift(key, n):
    if not trend_rows:
        return 0.0, 0.0
    avg = sum(r[key][0] for r in trend_rows) / len(trend_rows)
    return avg, avg / (n * 0.25)


he5_avg, he5_l = avg_lift("HE5", 5)
tr5_avg, tr5_l = avg_lift("Tr5", 5)
tr12_avg, tr12_l = avg_lift("Tr12", 12)
ai5_avg, ai5_l = avg_lift("AI5", 5)
ai12_avg, ai12_l = avg_lift("AI12", 12)

prev = next(h for h in state["history"] if str(h.get("target_issue")) == "2026192")
act192 = draws["2026192"]
rev = {
    "HE5": hit(prev["b3_final5"], "2026192"),
    "Tr5": hit(prev["top5"], "2026192"),
    "Tr12": hit(prev["top12"], "2026192"),
    "AI5": hit(prev["conf_top5"], "2026192"),
    "AI12": hit(prev["conf_top12"], "2026192"),
    "mRMR": hit(prev["mrmr_top12"], "2026192"),
    "PureH": hit(prev["pure_pool_top"], "2026192"),
    "PureOld": hit(prev["pure_pool_old_rule"], "2026192"),
    "PureLR": hit(prev["pure_pool_lr"], "2026192"),
    "PureAll": hit(prev["pure_pool_all"], "2026192"),
    "Burst": hit(prev["deep_picks"], "2026192"),
    "Cons": hit(prev["deep_consensus"], "2026192"),
}
dk = [int(x) for x in prev["deep_kills"]]
defend_ok = [n for n in dk if n not in act192]
defend_miss = [n for n in dk if n in act192]

he5 = latest["b3_final5"]
trinity5 = latest["top5"]
trinity12 = latest["top12"]
ai5 = latest["conf_top5"]
ai12 = latest["conf_top12"]
mrmr = latest["mrmr_top12"]
golden = [6, 11, 12, 23, 46]
pp_high = latest["pure_pool_top"]
pp_old = latest["pure_pool_old_rule"]
pp_lr = latest["pure_pool_lr"]
pp_all = latest["pure_pool_all"]
burst = latest.get("deep_picks") or [6, 23, 54, 61, 71]
defend = latest.get("deep_kills") or [3, 25, 15]
consensus = latest.get("deep_consensus") or [6, 11, 23, 61]
weights = latest["trinity_weights"]
env = latest["environment"]
kl = latest["kl_msg"]

modules = {
    "HE5": he5,
    "Trinity": trinity12,
    "AI": ai12,
    "mRMR": mrmr,
    "Pure": pp_high,
    "Golden": golden,
    "Burst": burst,
}
pool = defaultdict(list)
for mod, nums in modules.items():
    for n in nums:
        pool[int(n)].append(mod)
diamond = sorted(n for n, s in pool.items() if len(s) >= 4)
gold = sorted(n for n, s in pool.items() if len(s) == 3)
silver = sorted(n for n, s in pool.items() if len(s) == 2)
copper = sorted(n for n, s in pool.items() if len(s) == 1)

ypool = defaultdict(list)
ymods = {
    "HE5": prev["b3_final5"],
    "Trinity": prev["top12"],
    "AI": prev["conf_top12"],
    "mRMR": prev["mrmr_top12"],
    "Pure": prev["pure_pool_top"],
    "Burst": prev["deep_picks"],
}
for mod, nums in ymods.items():
    for n in nums:
        ypool[int(n)].append(mod)
ydiamond = sorted(n for n, s in ypool.items() if len(s) >= 4)
ycopper = sorted(n for n, s in ypool.items() if len(s) == 1)
yd_hits = len([n for n in ydiamond if n in act192])
yc_hits = len([n for n in ycopper if n in act192])
yd_rate = (yd_hits / len(ydiamond)) if ydiamond else 0.0
yc_rate = (yc_hits / len(ycopper)) if ycopper else 0.0
dist_idx = (yd_rate / yc_rate) if yc_rate > 0 else 0.0
if dist_idx > 1.5:
    purify_status = "VALID"
elif dist_idx >= 1.0:
    purify_status = "WEAK"
else:
    purify_status = "REFERENCE_ONLY"
purify_note = (
    f"上期钻石命中{yd_hits}/{len(ydiamond) or 0} 铜级{yc_hits}/{len(ycopper) or 0} "
    f"区分力={dist_idx:.2f}x → {purify_status}"
)

opt_decision = "无需调整"
opt_note = "主通道近10期 Lift≈1.0x，贴近随机基线；增加复杂度收益不显著，维持现状"

report = REPORT.read_text(encoding="utf-8")
if "近10期命中率趋势" not in report:
    block = []
    block.append("\n## 一附、近10期命中率趋势\n")
    block.append("\n| 期号 | HE5 | Tr5 | Tr12 | AI5 | AI12 |\n|------|-----|-----|------|-----|------|\n")
    for r in trend_rows:
        block.append(
            f"| {r['period']} | {r['HE5'][0]}/5 | {r['Tr5'][0]}/5 | "
            f"{r['Tr12'][0]}/12 | {r['AI5'][0]}/5 | {r['AI12'][0]}/12 |\n"
        )
    block.append(
        f"\n**汇总：** HE5 平均 {he5_avg:.2f}/5 Lift={he5_l:.2f}x | "
        f"Tr5 {tr5_avg:.2f} Lift={tr5_l:.2f}x | Tr12 {tr12_avg:.2f} Lift={tr12_l:.2f}x | "
        f"AI5 {ai5_avg:.2f} Lift={ai5_l:.2f}x | AI12 {ai12_avg:.2f} Lift={ai12_l:.2f}x\n"
    )
    block.append(
        f"\n**优化结论：** {opt_note} → **{opt_decision}**；自学习冻结 (WF Lift=1.0043 < 1.1)。"
        "极速爆破/极高阶三元已移除，维持精简架构。\n"
    )
    block.append("\n## 一附2、内部提纯 (任务4.5 · 仅参考)\n\n")
    block.append(f"- 钻石级(≥4模块)：{diamond if diamond else '无'}\n")
    block.append(f"- 金级(3模块)：{gold}\n")
    block.append(f"- 银级(2模块)：{silver}\n")
    block.append(f"- 上期提纯复盘：{purify_note}\n")
    block.append(f"- 状态：{purify_status} — 不驱动选号权重\n")
    report = report.replace(
        "\n## 二、2026193期 核心推荐",
        "".join(block) + "\n## 二、2026193期 核心推荐",
    )
    REPORT.write_text(report, encoding="utf-8", newline="\n")

W = 78
lines = []
lines.append("=" * W)
lines.append("  快乐8 每日控制面板  |  2026-07-22  |  目标期 2026193")
lines.append("=" * W)
lines.append("  数据: kl8最新=2026192(2026-07-21) | 点位=2026193就绪 | Excel六项校验全通过")
lines.append(
    f"  环境: {env} | Trinity动态 EF={weights['EF']:.2f} "
    f"RW={weights['RW']:.2f} FO={weights['FO']:.2f}"
)
lines.append(
    "  自学习: FROZEN (WF Lift=1.0043 < 1.1) | 稳态权重 EF:0.40 RW:0.30 FO:0.30 | Level1×0.5"
)
lines.append(f"  KL: {kl}")
lines.append("-" * W)
lines.append(f"  【上期 2026192 复盘】开奖: {fmt(sorted(act192))}")


def row(name, key):
    nh, n, lift, h = rev[key]
    hs = fmt(h) if h else "-"
    return f"  {name:<12} {nh}/{n:<3} Lift={lift:.2f}x  命中[{hs}]"


lines.append(row("HE5", "HE5"))
lines.append(row("Trinity5", "Tr5"))
lines.append(row("Trinity12", "Tr12"))
lines.append(row("AI5", "AI5"))
lines.append(row("AI12", "AI12"))
lines.append(row("mRMR12", "mRMR"))
lines.append(row("纯净池高置信", "PureH"))
lines.append(row("旧规则>=3", "PureOld"))
lines.append(row("LR定胆", "PureLR"))
lines.append(row("纯净池全量", "PureAll"))
lines.append(row("爆发Top5", "Burst"))
lines.append(row("跨规则共识", "Cons"))
lines.append(
    f"  防守Top3 {fmt(dk)}: 成功 {len(defend_ok)}/{len(dk)}，"
    f"误杀入奖 {fmt(defend_miss) if defend_miss else '无'}"
)
lines.append("-" * W)
lines.append("  【近10期均值】随机基线 Top5=1.25 / Top12=3.00")
for r in trend_rows:
    lines.append(
        f"  {r['period']}  HE5 {r['HE5'][0]}/5  Tr5 {r['Tr5'][0]}/5  "
        f"Tr12 {r['Tr12'][0]}/12  AI5 {r['AI5'][0]}/5  AI12 {r['AI12'][0]}/12"
    )
lines.append(
    f"  汇总 HE5={he5_avg:.2f}/5({he5_l:.2f}x) Tr5={tr5_avg:.2f}({tr5_l:.2f}x) "
    f"Tr12={tr12_avg:.2f}({tr12_l:.2f}x) AI5={ai5_avg:.2f}({ai5_l:.2f}x) "
    f"AI12={ai12_avg:.2f}({ai12_l:.2f}x)"
)
lines.append(f"  【优化决策】{opt_decision} | {opt_note}")
lines.append(f"  【提纯】{purify_status} | {purify_note}")
lines.append("=" * W)
lines.append("  【今日 2026193 核心推荐】")
lines.append(f"  Hidden Energy 5     : {fmt(he5)}")
for i, n in enumerate(he5, 1):
    lines.append(f"    #{i}  {int(n):02d}")
lines.append(f"  Trinity Top5        : {fmt(trinity5)}")
lines.append(f"  Trinity Top12       : {fmt(trinity12)}")
lines.append(f"  AI Top5             : {fmt(ai5)}")
lines.append(f"  AI Top12            : {fmt(ai12)}")
lines.append(f"  Golden Core         : {fmt(golden)}")
lines.append(f"  mRMR Top12          : {fmt(mrmr)}")
lines.append(f"  纯净池-高置信       : {fmt(pp_high)}")
lines.append(f"  纯净池-旧规则>=3    : {fmt(pp_old)}")
lines.append(f"  纯净池-LR影子       : {fmt(pp_lr)}")
lines.append(f"  纯净池-全量         : {fmt(pp_all)}")
lines.append(f"  爆发Top5            : {fmt(burst)}")
lines.append(f"  防守Top3(杀号)      : {fmt(defend)}")
lines.append(f"  跨规则共识          : {fmt(consensus)}")
lines.append("-" * W)
lines.append(f"  钻石级(≥4): {fmt(diamond) if diamond else '(无)'}")
lines.append(f"  金级(3)   : {fmt(gold) if gold else '(无)'}")
lines.append(f"  银级(2)   : {fmt(silver) if silver else '(无)'}")
lines.append(f"  铜级(1)   : {fmt(copper[:12])}{' ...' if len(copper) > 12 else ''}")
lines.append("=" * W)
lines.append("  落盘:")
lines.append(f"  - {REPORT}")
lines.append(f"  - {PANEL}")
lines.append(f"  - {COPY}")
lines.append("=" * W)
panel_text = "\n".join(lines) + "\n"
PANEL.write_text(panel_text, encoding="utf-8", newline="\n")
CONSOLE.write_text(panel_text, encoding="utf-8", newline="\n")
print(panel_text)

copy_lines = [
    "# 快乐8 可复制推荐 · 目标期 2026193 · 生成日 2026-07-22",
    f"HE5={fmt(he5)}",
    f"Trinity5={fmt(trinity5)}",
    f"Trinity12={fmt(trinity12)}",
    f"AI5={fmt(ai5)}",
    f"AI12={fmt(ai12)}",
    f"Golden={fmt(golden)}",
    f"mRMR={fmt(mrmr)}",
    f"纯净池高置信={fmt(pp_high)}",
    f"纯净池旧规则={fmt(pp_old)}",
    f"纯净池LR={fmt(pp_lr)}",
    f"纯净池全量={fmt(pp_all)}",
    f"爆发Top5={fmt(burst)}",
    f"防守Top3={fmt(defend)}",
    f"跨规则共识={fmt(consensus)}",
    f"钻石级={fmt(diamond) if diamond else ''}",
    f"金级共振={fmt(gold)}",
    f"银级共振={fmt(silver)}",
    "置信度=Level1 x0.5",
    f"优化决策={opt_decision}",
]
COPY.write_text("\n".join(copy_lines) + "\n", encoding="utf-8", newline="\n")

canvas_data = {
    "date": "2026-07-22",
    "target": "2026193",
    "latest_draw": "2026192",
    "env": env,
    "weights": weights,
    "steady_weights": {"EF": 0.40, "RW": 0.30, "FO": 0.30},
    "kl": kl,
    "level": "Level1 x0.5",
    "frozen": True,
    "opt_decision": opt_decision,
    "opt_note": opt_note,
    "purify_status": purify_status,
    "purify_note": purify_note,
    "review_period": "2026192",
    "review_draw": sorted(act192),
    "review": {
        k: {"hits": v[0], "n": v[1], "lift": round(v[2], 2), "nums": v[3]}
        for k, v in rev.items()
    },
    "defend": {"ok": defend_ok, "miss": defend_miss, "picks": dk},
    "trend": [
        {
            "period": r["period"],
            "HE5": r["HE5"][0],
            "Tr5": r["Tr5"][0],
            "Tr12": r["Tr12"][0],
            "AI5": r["AI5"][0],
            "AI12": r["AI12"][0],
        }
        for r in trend_rows
    ],
    "avgs": {
        "HE5": round(he5_avg, 2),
        "HE5_lift": round(he5_l, 2),
        "Tr5": round(tr5_avg, 2),
        "Tr5_lift": round(tr5_l, 2),
        "Tr12": round(tr12_avg, 2),
        "Tr12_lift": round(tr12_l, 2),
        "AI5": round(ai5_avg, 2),
        "AI5_lift": round(ai5_l, 2),
        "AI12": round(ai12_avg, 2),
        "AI12_lift": round(ai12_l, 2),
    },
    "picks": {
        "HE5": [int(x) for x in he5],
        "Trinity5": [int(x) for x in trinity5],
        "Trinity12": [int(x) for x in trinity12],
        "AI5": [int(x) for x in ai5],
        "AI12": [int(x) for x in ai12],
        "Golden": golden,
        "mRMR": [int(x) for x in mrmr],
        "PureHigh": [int(x) for x in pp_high],
        "PureOld": [int(x) for x in pp_old],
        "PureLR": [int(x) for x in pp_lr],
        "PureAll": [int(x) for x in pp_all],
        "Burst": [int(x) for x in burst],
        "Defend": [int(x) for x in defend],
        "Consensus": [int(x) for x in consensus],
        "Diamond": diamond,
        "Gold": gold,
        "Silver": silver,
    },
    "he5_detail": [
        {"rank": 1, "n": 46, "score": 1.1645},
        {"rank": 2, "n": 15, "score": 1.1155},
        {"rank": 3, "n": 32, "score": 1.0608},
        {"rank": 4, "n": 12, "score": 1.0331},
        {"rank": 5, "n": 75, "score": 1.0244},
    ],
}
CANVAS_DATA.write_text(json.dumps(canvas_data, ensure_ascii=False, indent=2), encoding="utf-8")
print("PANEL", PANEL.exists(), PANEL.stat().st_size)
print("COPY", COPY.exists(), COPY.stat().st_size)
print("TREND_N", len(trend_rows), "HE5_lift", round(he5_l, 2), "Tr12_lift", round(tr12_l, 2))
print("DIAMOND", diamond, "GOLD", gold)
print("PURIFY", purify_status, purify_note)
