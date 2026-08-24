# -*- coding: utf-8 -*-
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.data_loader import DataLoader
from main import load_all_predictions, review_prediction, _feed_force_remove
from config.paths import KILL_LOGS, KILL_REPORT

dl = DataLoader()
dl.load()
opened = {d.period: set(d.numbers) for d in dl.history}
preds = load_all_predictions()
last = [p for p in preds if p["period"] == "2026191"][-1]
assert last.get("cross_feed"), "missing cross_feed"
cf = last["cross_feed"]
assert "danger_sources" in cf, "missing danger_sources"
assert cf.get("prev_review"), "missing prev_review"
assert "失真" in str(cf["prev_review"].get("status", "")), cf["prev_review"]
assert _feed_force_remove(cf) is False, "should soft-remove danger"
print("PASS persistence + soft-danger checks")
print("period", last["period"])
print("high", last["high_conf_kills"])
print("mid", last["mid_conf_kills"])
print("low", last["low_conf_kills"])
print("safe", last["safe_numbers"])
print("conf", round(last["kill_confidence"], 4))
print("engines", {k: round(v, 3) for k, v in last["engine_contributions"].items()})
print("danger", cf["danger"])
print("danger_sources", cf["danger_sources"])
print("review", cf["review"])
print("resonate", cf["resonate"])
print("indep", cf["independent_kills"])
print("coverage", cf["kill_coverage"], "chaos", cf["chaos_flag"])
print("prev", cf["prev_review"])
wr = cf.get("window_review") or {}
print(
    "window",
    {
        k: wr.get(k)
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
print("report", KILL_REPORT.exists(), KILL_REPORT.stat().st_size)
print("logs", KILL_LOGS.exists(), KILL_LOGS.stat().st_size)

recent = []
seen = set()
for pred in reversed(preds):
    p = pred.get("period", "")
    if p in seen or p not in opened or p == "2026191":
        continue
    seen.add(p)
    recent.append(review_prediction(pred, opened[p]))
    if len(recent) >= 10:
        break
th = sum(r["high_hit"] for r in recent)
tht = sum(r["high_total"] for r in recent)
ta = sum(r["all_hit"] for r in recent)
tat = sum(r["all_total"] for r in recent)
tm = sum(r["mid_hit"] for r in recent)
tmt = sum(r["mid_total"] for r in recent)
ts = sum(r["safe_hit"] for r in recent)
tst = sum(r["safe_total"] for r in recent)
print(f"recent10 high {th}/{tht}={th/tht:.1%}")
print(f"recent10 mid {tm}/{tmt}={tm/tmt:.1%}")
print(f"recent10 all {ta}/{tat}={ta/tat:.1%}")
print(f"recent10 safe {ts}/{tst}={ts/tst:.1%}")
for r in reversed(recent):
    print(
        r["period"],
        f"H{r['high_hit']}/{r['high_total']} "
        f"M{r['mid_hit']}/{r['mid_total']} "
        f"A{r['all_hit']}/{r['all_total']} "
        f"S{r['safe_hit']}/{r['safe_total']}",
    )

# write markdown control panel report
md = []
md.append("# KillSeeker 控制面板详细报告 — 2026191期")
md.append("")
md.append(f"- 生成依据: 最新开奖 `{dl.latest_period}` · 历史 `{dl.total_periods}` 期")
md.append(f"- 综合把握: **{last['kill_confidence']:.1%}**")
md.append("")
md.append("## ① 近10期命中率")
md.append("")
md.append("| 期号 | 高置信 | 中置信 | 全部杀号 | 保留号 |")
md.append("|------|--------|--------|----------|--------|")
for r in reversed(recent):
    hr = r["high_hit"] / r["high_total"]
    mr = r["mid_hit"] / r["mid_total"]
    ar = r["all_hit"] / r["all_total"]
    sr = r["safe_hit"] / r["safe_total"]
    md.append(
        f"| {r['period']} | {r['high_hit']}/{r['high_total']} ({hr:.0%}) | "
        f"{r['mid_hit']}/{r['mid_total']} ({mr:.0%}) | "
        f"{r['all_hit']}/{r['all_total']} ({ar:.0%}) | "
        f"{r['safe_hit']}/{r['safe_total']} ({sr:.0%}) |"
    )
md.append("")
md.append(
    f"**汇总**: 高置信 {th}/{tht}={th/tht:.1%} · 中置信 {tm}/{tmt}={tm/tmt:.1%} · "
    f"全部 {ta}/{tat}={ta/tat:.1%} · 保留 {ts}/{tst}={ts/tst:.1%} · "
    f"相对基线75% {(ta/tat/0.75-1)*100:+.1f}%"
)
md.append("")
md.append("## ② 2026191 杀号推荐")
md.append("")
eng = last["engine_contributions"]
md.append(
    f"- 引擎: 相似 {eng.get('similarity',0):.0%} / 密集 {eng.get('density',0):.0%} / "
    f"形态 {eng.get('pattern',0):.0%} / 曲线 {eng.get('curve',0):.0%}"
)
md.append(
    f"- 🔴 高置信: {', '.join(f'{n:02d}' for n in last['high_conf_kills'])}"
)
md.append(
    f"- 🟡 中置信: {', '.join(f'{n:02d}' for n in last['mid_conf_kills'])}"
)
md.append(
    f"- 🟠 观察区: {', '.join(f'{n:02d}' for n in last['low_conf_kills'])}"
)
md.append(
    f"- 🟢 保留号: {', '.join(f'{n:02d}' for n in last['safe_numbers'])}"
)
md.append("")
md.append("## ③ 杀号反哺交叉矩阵")
md.append("")


def _src(nums, smap):
    parts = []
    for n in nums:
        srcs = smap.get(str(n)) or smap.get(n) or []
        tag = ",".join(srcs) if srcs else ""
        parts.append(f"{n:02d}[{tag}]" if tag else f"{n:02d}")
    return ", ".join(parts) if parts else "(无)"


md.append(f"- 🔴 危险信号: {_src(cf['danger'], cf.get('danger_sources') or {})}")
md.append(f"- 🟡 需复核: {_src(cf['review'], cf.get('review_sources') or {})}")
md.append(f"- 🟢 共振确认: {_src(cf['resonate'], cf.get('resonate_sources') or {})}")
md.append(
    f"- ⚪ 独立杀号: {', '.join(f'{n:02d}' for n in cf.get('independent_kills') or []) or '(无)'}"
)
md.append(f"- 击杀率: {cf['kill_coverage']:.0%} · {cf.get('advice')}")
md.append(
    f"- 上期回验: {cf['prev_review'].get('status')} · {cf['prev_review'].get('advice')}"
)
md.append(
    f"- 近窗: {wr.get('status')} 指数={wr.get('index')} "
    f"危险未中均={wr.get('avg_danger_miss_rate')} 共振命中均={wr.get('avg_resonate_hit_rate')}"
)
md.append("")
md.append("## ④ 行动清单（已校准）")
md.append("")
md.append("1. 高置信杀号 → 从大盘直接划去")
md.append("2. 🔴危险信号 → **仅供参考，不强制剔除**（上期反哺区分力失真）")
md.append("3. 🟡需复核 → 降权 0.5x")
md.append("4. 🟢共振确认 → 提高优先级（上期共振全灭，本期谨慎）")
md.append("5. 杀号仅缩水，不做主战做多")
md.append("6. 近窗全部杀号 <75% → 观察区降权，勿扩大杀号面")
md.append("")

out = Path(__file__).resolve().parents[1] / "logs" / "control_panel_2026191.md"
out.write_text("\n".join(md) + "\n", encoding="utf-8")
print("wrote", out)
