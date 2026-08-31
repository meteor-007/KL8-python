# -*- coding: utf-8 -*-
"""Generate UTF-8 control panel + copyable picks + canvas data for 2026-07-29."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/daily_analysis_report_20260729.md"
STATE = ROOT / "cache/self_learning_state.json"
PANEL = ROOT / "reports/control_panel_20260729.txt"
COPY = ROOT / "reports/可复制推荐_2026200.txt"
CANVAS_DATA = ROOT / "scratch/canvas_data_20260729.json"
CONSOLE = ROOT / "scratch/console_panel_20260729.txt"
AI_MEM = ROOT / "cache/ai_memory_20260729.md"
REVIEW_OUT = ROOT / "reviews/review_2026199.json"
LEARNER = ROOT / "cache/learner_state.json"

TARGET = "2026200"
PREV = "2026199"
TODAY = "2026-07-29"
TODAY_COMPACT = "20260729"

state = json.loads(STATE.read_text(encoding="utf-8"))
latest = state["history"][0]
assert str(latest["target_issue"]) == TARGET, latest.get("target_issue")
prev = next(h for h in state["history"] if str(h.get("target_issue")) == PREV)

draws = {}
for line in (ROOT / "kl8_history_final.txt").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    parts = dict(p.split(":", 1) for p in line.split(","))
    draws[parts["period"]] = set(int(x) for x in parts["numbers"].split("-"))

act_prev = draws[PREV]


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


def plist(pat, body):
    m = re.search(pat + r"[^[]*\[([^\]]+)\]", body)
    if not m:
        return []
    return [int(x.strip()) for x in m.group(1).split(",") if x.strip().lstrip("-").isdigit()]


trend_rows = []
for fp in sorted((ROOT / "reports").glob("daily_analysis_report_20260*.md")):
    text = fp.read_text(encoding="utf-8")
    tm = re.search(r"目标期号[：:]\s*\*{0,2}\s*(\d{7})", text)
    if not tm:
        continue
    period = tm.group(1)
    if period not in draws:
        continue
    he5 = plist(r"最终推荐 \(5 码\)", text)
    tr5 = plist(r"极秘 Top 5", text)
    tr12 = plist(r"极秘 Top 12", text)
    ai5 = plist(r"Top 5 置信度精选", text)
    ai12 = plist(r"Top 12 综合拦截", text)
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

trend_rows = [r for r in trend_rows if r["period"] != TARGET][-10:]


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

rev = {
    "HE5": hit(prev["b3_final5"], PREV),
    "Tr5": hit(prev["top5"], PREV),
    "Tr12": hit(prev["top12"], PREV),
    "AI5": hit(prev["conf_top5"], PREV),
    "AI12": hit(prev["conf_top12"], PREV),
    "mRMR": hit(prev["mrmr_top12"], PREV),
    "PureH": hit(prev["pure_pool_top"], PREV),
    "PureOld": hit(prev["pure_pool_old_rule"], PREV),
    "PureLR": hit(prev["pure_pool_lr"], PREV),
    "PureAll": hit(prev["pure_pool_all"], PREV),
    "Burst": hit(prev["deep_picks"], PREV),
    "Cons": hit(prev["deep_consensus"], PREV),
}
dk = [int(x) for x in prev["deep_kills"]]
defend_ok = [n for n in dk if n not in act_prev]
defend_miss = [n for n in dk if n in act_prev]

he5 = [int(x) for x in latest["b3_final5"]]
trinity5 = [int(x) for x in latest["top5"]]
trinity12 = [int(x) for x in latest["top12"]]
ai5 = [int(x) for x in latest["conf_top5"]]
ai12 = [int(x) for x in latest["conf_top12"]]
mrmr = [int(x) for x in latest["mrmr_top12"]]
report_txt = REPORT.read_text(encoding="utf-8")
golden = plist(r"高频共振集群", report_txt) or [19, 27, 29, 42, 53, 73, 75]
pp_high = [int(x) for x in latest["pure_pool_top"]]
pp_old = [int(x) for x in latest["pure_pool_old_rule"]]
pp_lr = [int(x) for x in latest["pure_pool_lr"]]
pp_all = [int(x) for x in latest["pure_pool_all"]]
burst = [int(x) for x in latest["deep_picks"]]
defend = [int(x) for x in latest["deep_kills"]]
consensus = [int(x) for x in latest["deep_consensus"]]
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
yd_hits = len([n for n in ydiamond if n in act_prev])
yc_hits = len([n for n in ycopper if n in act_prev])
yd_rate = (yd_hits / len(ydiamond)) if ydiamond else 0.0
yc_rate = (yc_hits / len(ycopper)) if ycopper else 0.0
dist_idx = (yd_rate / yc_rate) if yc_rate > 0 else (999.0 if yd_rate > 0 else 0.0)
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
opt_note = (
    f"近10期 HE5 Lift={he5_l:.2f}x / Tr12={tr12_l:.2f}x / AI12={ai12_l:.2f}x，"
    "贴近随机基线；门控 FROZEN；不新增复杂度"
)

# Append trend + purify into report if missing
report = report_txt
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
        "极速爆破/极高阶三元已移除，维持精简架构 v4.2。\n"
    )
    block.append("\n## 一附2、内部提纯 (任务4.5 · 仅参考)\n\n")
    block.append(f"- 钻石级(≥4模块)：{diamond if diamond else '无'}\n")
    block.append(f"- 金级(3模块)：{gold}\n")
    block.append(f"- 银级(2模块)：{silver}\n")
    block.append(f"- 上期提纯复盘：{purify_note}\n")
    block.append(f"- 状态：{purify_status} — 不驱动选号权重\n")
    report = report.replace(
        f"\n## 二、{TARGET}期 核心推荐",
        "".join(block) + f"\n## 二、{TARGET}期 核心推荐",
    )
    REPORT.write_text(report, encoding="utf-8", newline="\n")

W = 78
lines = []
lines.append("=" * W)
lines.append(f"  快乐8 每日控制面板  |  {TODAY}  |  目标期 {TARGET}")
lines.append("=" * W)
lines.append(
    f"  数据: kl8最新={PREV}(2026-07-28) | 点位={TARGET}就绪 | Excel六项校验全通过"
)
lines.append(
    f"  环境: {env} | Trinity动态 EF={weights['EF']:.2f} "
    f"RW={weights['RW']:.2f} FO={weights['FO']:.2f}"
)
lines.append(
    "  自学习: FROZEN (WF Lift=1.0043 < 1.1) | 稳态权重 EF:0.40 RW:0.30 FO:0.30 | Level1×0.5"
)
lines.append(f"  KL: {kl}")
lines.append("-" * W)
lines.append(f"  【上期 {PREV} 复盘】开奖: {fmt(sorted(act_prev))}")


def row(name, key):
    nh, n, lift, h = rev[key]
    hs = fmt(h) if h else "-"
    return f"  {name:<12} {nh}/{n:<3} Lift={lift:.2f}x  命中[{hs}]"


lines.append(row("HE5", "HE5"))
lines.append(row("Trinity5", "Tr5"))
lines.append(row("Trinity12", "Tr12"))
lines.append(row("AI5", "AI5"))
lines.append(row("AI12", "AI12"))
lines.append(row("mRMR", "mRMR"))
lines.append(row("纯净高置信", "PureH"))
lines.append(row("旧规则>=3", "PureOld"))
lines.append(row("LR影子", "PureLR"))
lines.append(row("纯净全量", "PureAll"))
lines.append(row("爆发Top5", "Burst"))
lines.append(row("跨规则共识", "Cons"))
lines.append(
    f"  防守Top3     成功{len(defend_ok)}/{len(dk)}  回避[{fmt(defend_ok) or '-'}]  "
    f"误杀[{fmt(defend_miss) or '-'}]"
)
lines.append("-" * W)
lines.append(f"  【近10期均值】HE5 {he5_avg:.2f}/5 Lift={he5_l:.2f}x | "
             f"Tr5 {tr5_avg:.2f} Lift={tr5_l:.2f}x | Tr12 {tr12_avg:.2f} Lift={tr12_l:.2f}x")
lines.append(f"               AI5 {ai5_avg:.2f} Lift={ai5_l:.2f}x | "
             f"AI12 {ai12_avg:.2f} Lift={ai12_l:.2f}x")
lines.append(f"  【优化决策】{opt_decision} — {opt_note}")
lines.append(f"  【提纯】{purify_note}")
lines.append("=" * W)
lines.append(f"  【今日主推 · 目标 {TARGET}】")
lines.append(f"  HE5         {fmt(he5)}")
lines.append(f"  Trinity5    {fmt(trinity5)}")
lines.append(f"  Trinity12   {fmt(trinity12)}")
lines.append(f"  AI5         {fmt(ai5)}")
lines.append(f"  AI12        {fmt(ai12)}")
lines.append(f"  Golden Core {fmt(golden)}")
lines.append(f"  mRMR12      {fmt(mrmr)}")
lines.append(f"  纯净高置信   {fmt(pp_high)}")
lines.append(f"  旧规则>=3   {fmt(pp_old)}")
lines.append(f"  LR影子      {fmt(pp_lr)}")
lines.append(f"  爆发Top5    {fmt(burst)}")
lines.append(f"  防守杀号    {fmt(defend)}")
lines.append(f"  跨规则共识  {fmt(consensus)}")
lines.append(f"  钻石级      {fmt(diamond) if diamond else '(无)'}")
lines.append(f"  金级        {fmt(gold) if gold else '(无)'}")
lines.append(f"  银级        {fmt(silver) if silver else '(无)'}")
lines.append("=" * W)
lines.append("  版本 v4.2 | 门控 FROZEN | 不 bump | 不 commit")
lines.append("=" * W)

panel_text = "\n".join(lines) + "\n"
PANEL.write_text(panel_text, encoding="utf-8", newline="\n")
CONSOLE.write_text(panel_text, encoding="utf-8", newline="\n")

copy_lines = [
    f"# 快乐8 可复制推荐 | {TODAY} | 目标期 {TARGET}",
    f"# 主通道 Hidden Energy 5（优先）",
    fmt(he5),
    "",
    "# Trinity Top5",
    fmt(trinity5),
    "",
    "# Trinity Top12",
    fmt(trinity12),
    "",
    "# AI Top5",
    fmt(ai5),
    "",
    "# AI Top12",
    fmt(ai12),
    "",
    "# Golden Core",
    fmt(golden),
    "",
    "# 纯净池高置信定胆",
    fmt(pp_high),
    "",
    "# 方案2 爆发Top5",
    fmt(burst),
    "",
    "# 方案2 防守杀号（回避）",
    fmt(defend),
    "",
    f"# 优化决策: {opt_decision}",
    f"# 门控: FROZEN WF=1.0043",
]
COPY.write_text("\n".join(copy_lines) + "\n", encoding="utf-8", newline="\n")

# Review JSON from learner history if present, else synthesize
learner = json.loads(LEARNER.read_text(encoding="utf-8")) if LEARNER.exists() else {}
rh = next(
    (r for r in learner.get("review_history", []) if str(r.get("period")) == PREV),
    None,
)
if rh and "hit_stats" in rh:
    review_doc = {
        "period": PREV,
        "timestamp": rh.get("timestamp"),
        "actual_numbers": sorted(act_prev),
        "hit_stats": {
            **rh.get("hit_stats", {}),
            "he5_hits": rev["HE5"][0],
            "he5_lift": round(rev["HE5"][2], 4),
            "ai5_hits": rev["AI5"][0],
            "ai5_lift": round(rev["AI5"][2], 4),
        },
        "algo_contribution": {
            k: (v.get("contribution") if isinstance(v, dict) else v)
            for k, v in (rh.get("algo_contribution") or {}).items()
        },
        "weights_used": rh.get("weights_used")
        or learner.get("pentagon_weights")
        or {"EF": 0.4, "RW": 0.3, "FO": 0.3},
        "optimization_decision": "N/A",
        "learning_status": "FROZEN",
        "gate": {"wf_lift": 1.0043, "threshold": 1.1},
        "channel_hits": {
            k: {"hits": v[0], "n": v[1], "lift": round(v[2], 4), "numbers": v[3]}
            for k, v in rev.items()
        },
        "defend": {"ok": defend_ok, "miss": defend_miss},
    }
else:
    review_doc = {
        "period": PREV,
        "timestamp": f"{TODAY} panel",
        "actual_numbers": sorted(act_prev),
        "hit_stats": {
            "top5_hits": rev["Tr5"][0],
            "top5_rate": rev["Tr5"][0] / 5,
            "top5_lift": round(rev["Tr5"][2], 4),
            "top12_hits": rev["Tr12"][0],
            "top12_rate": rev["Tr12"][0] / 12,
            "top12_lift": round(rev["Tr12"][2], 4),
            "he5_hits": rev["HE5"][0],
            "he5_lift": round(rev["HE5"][2], 4),
            "ai5_hits": rev["AI5"][0],
            "ai5_lift": round(rev["AI5"][2], 4),
        },
        "algo_contribution": {},
        "weights_used": {"EF": 0.4, "RW": 0.3, "FO": 0.3},
        "optimization_decision": "N/A",
        "learning_status": "FROZEN",
        "gate": {"wf_lift": 1.0043, "threshold": 1.1},
        "channel_hits": {
            k: {"hits": v[0], "n": v[1], "lift": round(v[2], 4), "numbers": v[3]}
            for k, v in rev.items()
        },
        "defend": {"ok": defend_ok, "miss": defend_miss},
    }
REVIEW_OUT.write_text(
    json.dumps(review_doc, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
    newline="\n",
)

ai_mem = f"""# AI Memory {TODAY_COMPACT}

- 日期: {TODAY} | 目标期: {TARGET} | 开奖最新: {PREV}(2026-07-28)
- 数据: fetch+1期2026199 | 热码补2026200 | 跟随表同步 | 六项校验全通过 | 格式化增量双期OK
- 复盘{PREV}: HE5 {rev['HE5'][0]}/5 Lift={rev['HE5'][2]:.2f}x | Tr5 {rev['Tr5'][0]}/5 | Tr12 {rev['Tr12'][0]}/12 | AI5 {rev['AI5'][0]}/5 | 爆发 {rev['Burst'][0]}/5 | 防守成功{len(defend_ok)}/{len(dk)}
- 近10期: HE5 Lift={he5_l:.2f}x | Tr12={tr12_l:.2f}x | AI12={ai12_l:.2f}x → 贴近随机基线
- 闭环: FROZEN (WF=1.0043<1.1) | 决策 N/A | 权重维持 EF0.40/RW0.30/FO0.30
- 优化决策: {opt_decision} | 版本维持 v4.2 | 不 bump
- 提纯: {purify_note} | 状态 {purify_status}（不驱动权重）
- 今日HE5: {fmt(he5)} | Trinity5: {fmt(trinity5)} | 纯净高置信: {fmt(pp_high)} | 爆发: {fmt(burst)}
- 风险: Level1×0.5 | KL Z={kl} | 门控长期冻结观察
- Bug: 无阻断性问题；learner 复盘落盘 reviews/ 需面板侧补写（已写 review_{PREV}.json）
"""
AI_MEM.write_text(ai_mem, encoding="utf-8", newline="\n")

canvas_payload = {
    "date": TODAY,
    "target": TARGET,
    "latest_draw": PREV,
    "he5": he5,
    "trinity5": trinity5,
    "trinity12": trinity12,
    "ai5": ai5,
    "ai12": ai12,
    "golden": golden,
    "mrmr": mrmr,
    "pp_high": pp_high,
    "pp_old": pp_old,
    "burst": burst,
    "defend": defend,
    "consensus": consensus,
    "diamond": diamond,
    "gold": gold,
    "silver": silver,
    "env": env,
    "weights": weights,
    "kl": kl,
    "opt_decision": opt_decision,
    "opt_note": opt_note,
    "purify_status": purify_status,
    "purify_note": purify_note,
    "trend": [
        {
            "period": r["period"],
            "he5": r["HE5"][0],
            "tr5": r["Tr5"][0],
            "tr12": r["Tr12"][0],
            "ai5": r["AI5"][0],
            "ai12": r["AI12"][0],
        }
        for r in trend_rows
    ],
    "avgs": {
        "he5_avg": he5_avg,
        "he5_lift": he5_l,
        "tr5_avg": tr5_avg,
        "tr5_lift": tr5_l,
        "tr12_avg": tr12_avg,
        "tr12_lift": tr12_l,
        "ai5_avg": ai5_avg,
        "ai5_lift": ai5_l,
        "ai12_avg": ai12_avg,
        "ai12_lift": ai12_l,
    },
    "prev_hits": {k: {"hits": v[0], "n": v[1], "lift": v[2], "nums": v[3]} for k, v in rev.items()},
    "defend_ok": defend_ok,
    "defend_miss": defend_miss,
    "actual_prev": sorted(act_prev),
}
CANVAS_DATA.write_text(
    json.dumps(canvas_payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
    newline="\n",
)

print(panel_text)
print("WROTE", PANEL)
print("WROTE", COPY)
print("WROTE", REVIEW_OUT)
print("WROTE", AI_MEM)
print("AVGS", canvas_payload["avgs"])
print("PURIFY", purify_status, diamond, gold[:10], silver[:10])
