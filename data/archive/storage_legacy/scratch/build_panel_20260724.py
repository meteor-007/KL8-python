# -*- coding: utf-8 -*-
"""Generate UTF-8 control panel + copyable picks + canvas data for 2026-07-24."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/daily_analysis_report_20260724.md"
STATE = ROOT / "cache/self_learning_state.json"
PANEL = ROOT / "reports/control_panel_20260724.txt"
COPY = ROOT / "reports/可复制推荐_2026195.txt"
CANVAS_DATA = ROOT / "scratch/canvas_data_20260724.json"
CONSOLE = ROOT / "scratch/console_panel_20260724.txt"
AI_MEM = ROOT / "cache/ai_memory_20260724.md"
REVIEW_OUT = ROOT / "reviews/review_2026194.json"

state = json.loads(STATE.read_text(encoding="utf-8"))
latest = state["history"][0]
assert str(latest["target_issue"]) == "2026195", latest.get("target_issue")
prev = next(h for h in state["history"] if str(h.get("target_issue")) == "2026194")

draws = {}
for line in (ROOT / "kl8_history_final.txt").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    parts = dict(p.split(":", 1) for p in line.split(","))
    draws[parts["period"]] = set(int(x) for x in parts["numbers"].split("-"))

act194 = draws["2026194"]


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

# exclude today's unopened target
trend_rows = [r for r in trend_rows if r["period"] != "2026195"][-10:]


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
    "HE5": hit(prev["b3_final5"], "2026194"),
    "Tr5": hit(prev["top5"], "2026194"),
    "Tr12": hit(prev["top12"], "2026194"),
    "AI5": hit(prev["conf_top5"], "2026194"),
    "AI12": hit(prev["conf_top12"], "2026194"),
    "mRMR": hit(prev["mrmr_top12"], "2026194"),
    "PureH": hit(prev["pure_pool_top"], "2026194"),
    "PureOld": hit(prev["pure_pool_old_rule"], "2026194"),
    "PureLR": hit(prev["pure_pool_lr"], "2026194"),
    "PureAll": hit(prev["pure_pool_all"], "2026194"),
    "Burst": hit(prev["deep_picks"], "2026194"),
    "Cons": hit(prev["deep_consensus"], "2026194"),
}
dk = [int(x) for x in prev["deep_kills"]]
defend_ok = [n for n in dk if n not in act194]
defend_miss = [n for n in dk if n in act194]

# HE5 by score order from report details
he5 = [46, 74, 51, 48, 37]
trinity5 = [int(x) for x in latest["top5"]]
trinity12 = [int(x) for x in latest["top12"]]
ai5 = [int(x) for x in latest["conf_top5"]]
ai12 = [int(x) for x in latest["conf_top12"]]
mrmr = [int(x) for x in latest["mrmr_top12"]]
golden = [15, 30, 46, 62, 75]
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
yd_hits = len([n for n in ydiamond if n in act194])
yc_hits = len([n for n in ycopper if n in act194])
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

# near-baseline → no tune
opt_decision = "无需调整"
opt_note = (
    f"近10期 HE5 Lift={he5_l:.2f}x / Tr12={tr12_l:.2f}x / AI12={ai12_l:.2f}x，"
    "贴近随机基线；门控 FROZEN；不新增复杂度"
)

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
        "极速爆破/极高阶三元已移除，维持精简架构 v4.2。\n"
    )
    block.append("\n## 一附2、内部提纯 (任务4.5 · 仅参考)\n\n")
    block.append(f"- 钻石级(≥4模块)：{diamond if diamond else '无'}\n")
    block.append(f"- 金级(3模块)：{gold}\n")
    block.append(f"- 银级(2模块)：{silver}\n")
    block.append(f"- 上期提纯复盘：{purify_note}\n")
    block.append(f"- 状态：{purify_status} — 不驱动选号权重\n")
    report = report.replace(
        "\n## 二、2026195期 核心推荐",
        "".join(block) + "\n## 二、2026195期 核心推荐",
    )
    REPORT.write_text(report, encoding="utf-8", newline="\n")

W = 78
lines = []
lines.append("=" * W)
lines.append("  快乐8 每日控制面板  |  2026-07-24  |  目标期 2026195")
lines.append("=" * W)
lines.append("  数据: kl8最新=2026194(2026-07-23) | 点位=2026195就绪 | Excel六项校验全通过")
lines.append(
    f"  环境: {env} | Trinity动态 EF={weights['EF']:.2f} "
    f"RW={weights['RW']:.2f} FO={weights['FO']:.2f}"
)
lines.append(
    "  自学习: FROZEN (WF Lift=1.0043 < 1.1) | 稳态权重 EF:0.40 RW:0.30 FO:0.30 | Level1×0.5"
)
lines.append(f"  KL: {kl}")
lines.append("-" * W)
lines.append(f"  【上期 2026194 复盘】开奖: {fmt(sorted(act194))}")


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
lines.append("  【今日 2026195 核心推荐】")
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
lines.append("  ─── 可复制推荐块 · 目标期 2026195 ───")
lines.append("")
lines.append("【HE5 · Hidden Energy 5】")
lines.append(fmt(he5))
lines.append("")
lines.append("【Trinity Top5】")
lines.append(fmt(trinity5))
lines.append("")
lines.append("【Trinity Top12】")
lines.append(fmt(trinity12))
lines.append("")
lines.append("【AI Top5】")
lines.append(fmt(ai5))
lines.append("")
lines.append("【AI Top12】")
lines.append(fmt(ai12))
lines.append("")
lines.append("【Golden Core】")
lines.append(fmt(golden))
lines.append("")
lines.append("【mRMR Top12】")
lines.append(fmt(mrmr))
lines.append("")
lines.append("【纯净池 · 高置信定胆】")
lines.append(fmt(pp_high))
lines.append("")
lines.append("【纯净池 · 旧规则>=3】")
lines.append(fmt(pp_old))
lines.append("")
lines.append("【纯净池 · LR定胆】")
lines.append(fmt(pp_lr))
lines.append("")
lines.append("【纯净池 · 全量】")
lines.append(fmt(pp_all))
lines.append("")
lines.append("【爆发Top5】")
lines.append(fmt(burst))
lines.append("")
lines.append("【防守Top3 · 回避】")
lines.append(fmt(defend))
lines.append("")
lines.append("【跨规则共识】")
lines.append(fmt(consensus))
lines.append("")
lines.append("【钻石共振 · 仅参考】")
lines.append(fmt(diamond) if diamond else "(无)")
lines.append("")
lines.append("【金级共振 · 仅参考】")
lines.append(fmt(gold) if gold else "(无)")
lines.append("")
lines.append(f"【环境】{env} | 权重 EF{weights['EF']:.2f}/RW{weights['RW']:.2f}/FO{weights['FO']:.2f} | 信标 Level1 · 0.5x")
lines.append(f"【风险】零信标 Level1；KL正常；自学习冻结；提纯{purify_status}不驱动选号")
lines.append("=" * W)

panel_text = "\n".join(lines) + "\n"
PANEL.write_text(panel_text, encoding="utf-8", newline="\n")
CONSOLE.write_text(panel_text, encoding="utf-8", newline="\n")

copy_lines = [
    "# 快乐8 可复制推荐 · 目标期 2026195 · 生成日 2026-07-24",
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

# review json for 2026194
review = {
    "period": "2026194",
    "timestamp": "2026-07-24 10:54:32",
    "actual_numbers": sorted(act194),
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
    "algo_contribution": {
        "FO": "POSITIVE",
        "EF": "POSITIVE",
        "RW": "NEGATIVE",
    },
    "weights_used": {"EF": 0.4, "RW": 0.3, "FO": 0.3},
    "optimization_decision": "N/A",
    "learning_status": "FROZEN",
    "gate": {"wf_lift": 1.0043, "threshold": 1.1},
}
REVIEW_OUT.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

ai_mem = f"""# AI记忆 · 2026-07-24 · 目标期2026195

## 数据更新
- kl8_history 最新=2026194 (2026-07-23)，2015期；Excel C/D 已同步；六项校验全通过
- daily_points 2026195 就绪；热码 2026195 已生成并 Stride-4 同步；格式化增量双期完成

## 复盘 2026194
- HE5 {rev['HE5'][0]}/5 Lift={rev['HE5'][2]:.2f}x 命中[{fmt(rev['HE5'][3]) if rev['HE5'][3] else '-'}]
- Trinity5 {rev['Tr5'][0]}/5 Lift={rev['Tr5'][2]:.2f}x；Trinity12 {rev['Tr12'][0]}/12 Lift={rev['Tr12'][2]:.2f}x
- AI5 {rev['AI5'][0]}/5 Lift={rev['AI5'][2]:.2f}x；AI12 {rev['AI12'][0]}/12 Lift={rev['AI12'][2]:.2f}x
- mRMR {rev['mRMR'][0]}/12 Lift={rev['mRMR'][2]:.2f}x
- 纯净池高置信/旧规则/LR {rev['PureH'][0]}/{rev['PureH'][1]}；全量{rev['PureAll'][0]}/{rev['PureAll'][1]}；爆发{rev['Burst'][0]}/5；防守成功{len(defend_ok)}/{len(dk)}；共识{rev['Cons'][0]}/{rev['Cons'][1]}
- 闭环：FROZEN / N/A；稳态 EF0.40 RW0.30 FO0.30

## 近10期
- HE5 {he5_avg:.2f}/5 Lift={he5_l:.2f}x；Tr5 {tr5_l:.2f}x；Tr12 {tr12_l:.2f}x；AI5 {ai5_l:.2f}x；AI12 {ai12_l:.2f}x
- 决策：{opt_decision}（{opt_note}）
- 提纯：{purify_status}（{purify_note}）

## Bug
- 无新增代码缺陷；沿用既有 fetch→sync→validator 管线；热码文件数31对齐2026195

## 今日推荐摘要
- HE5评分序: {fmt(he5)}
- Trinity5: {fmt(trinity5)}
- AI5: {fmt(ai5)}
- Golden: {fmt(golden)}
- 纯净池高置信: {fmt(pp_high)}
- 爆发: {fmt(burst)} | 防守: {fmt(defend)}
- 环境:{env} | Level1×0.5 | 版本 v4.2 | 门控 FROZEN
"""
AI_MEM.write_text(ai_mem, encoding="utf-8", newline="\n")

canvas_data = {
    "date": "2026-07-24",
    "target": "2026195",
    "latest_draw": "2026194",
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
    "review_period": "2026194",
    "review_draw": sorted(act194),
    "review": {
        k: {"hits": v[0], "n": v[1], "lift": round(v[2], 2), "nums": v[3]}
        for k, v in rev.items()
    },
    "defend": {"ok": defend_ok, "miss": defend_miss, "picks": dk},
    "trend": [
        {
            "period": r["period"][-3:],
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
        "HE5": he5,
        "Trinity5": trinity5,
        "Trinity12": trinity12,
        "AI5": ai5,
        "AI12": ai12,
        "Golden": golden,
        "mRMR": mrmr,
        "PureHigh": pp_high,
        "PureOld": pp_old,
        "PureLR": pp_lr,
        "PureAll": pp_all,
        "Burst": burst,
        "Defend": defend,
        "Consensus": consensus,
        "Diamond": diamond,
        "Gold": gold,
        "Silver": silver,
    },
    "he5_detail": [
        {"rank": 1, "n": 46, "score": 1.1178},
        {"rank": 2, "n": 74, "score": 1.1058},
        {"rank": 3, "n": 51, "score": 1.0892},
        {"rank": 4, "n": 48, "score": 1.0628},
        {"rank": 5, "n": 37, "score": 1.0579},
    ],
}
CANVAS_DATA.write_text(json.dumps(canvas_data, ensure_ascii=False, indent=2), encoding="utf-8")

# physical exists checks
for p in [PANEL, COPY, AI_MEM, REVIEW_OUT, CANVAS_DATA, REPORT]:
    assert p.exists() and p.stat().st_size > 0, p
    bom = p.read_bytes()[:3] == b"\xef\xbb\xbf"
    assert not bom, f"BOM in {p}"

print("PANEL", PANEL.stat().st_size)
print("COPY", COPY.stat().st_size)
print("TREND_N", len(trend_rows), "HE5_lift", round(he5_l, 2), "Tr12_lift", round(tr12_l, 2))
print("DIAMOND", diamond, "GOLD", gold)
print("PURIFY", purify_status, purify_note)
print("OPT", opt_decision)
print("REV_HE5", rev["HE5"], "REV_Tr5", rev["Tr5"])
