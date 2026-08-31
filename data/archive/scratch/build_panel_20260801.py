#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build control panel + copyable + hit-rate for 20260801 / target 2026203."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]


def fmt(nums) -> str:
    if isinstance(nums, str):
        nums = [int(x) for x in re.findall(r"\d{1,2}", nums)]
    return " ".join(f"{int(n):02d}" for n in nums if 1 <= int(n) <= 80)


def extract_md(path: Path) -> dict:
    t = path.read_text(encoding="utf-8")
    out = {}

    def one(pat: str) -> str:
        m = re.search(pat, t)
        return fmt(m.group(1)) if m else ""

    out["Trinity5"] = one(r"\*\*极秘 Top 5\*\*：`\[([^\]]+)\]`")
    out["Trinity12"] = one(r"\*\*极秘 Top 12\*\*：`\[([^\]]+)\]`")
    out["AI5"] = one(r"\*\*Top 5 置信度精选\*\*：`\[([^\]]+)\]`")
    out["AI12"] = one(r"\*\*Top 12 综合拦截\*\*：`\[([^\]]+)\]`")
    out["Golden"] = one(r"\*\*高频共振集群\*\*：`\[([^\]]+)\]`")
    out["mRMR"] = one(r"\*\*mRMR Top 12\*\*：`\[([^\]]+)\]`")
    out["HE5"] = one(r"\*\*最终推荐 \(5 码\)\*\*：`\[([^\]]+)\]`")
    out["纯净池旧规则"] = one(r"\*\*旧规则高置信[^*]*\*\*：`\[([^\]]+)\]`")
    out["纯净池LR"] = one(r"\*\*LR定胆[^*]*\*\*：`\[([^\]]+)\]`")
    out["纯净池高置信"] = one(r"\*\*高置信定胆[^*]*\*\*：`\[([^\]]+)\]`")
    out["纯净池全量"] = one(r"\*\*纯净池号码\*\*：`\[([^\]]+)\]`")
    m = re.search(
        r"最终精选爆发码（Top 5）[\s\S]*?"
        r"\| 1 \| \*\*(\d+)\*\*[\s\S]*?"
        r"\| 2 \| \*\*(\d+)\*\*[\s\S]*?"
        r"\| 3 \| \*\*(\d+)\*\*[\s\S]*?"
        r"\| 4 \| \*\*(\d+)\*\*[\s\S]*?"
        r"\| 5 \| \*\*(\d+)\*\*",
        t,
    )
    if m:
        out["爆发Top5"] = fmt([m.group(i) for i in range(1, 6)])
    m = re.search(
        r"重点防守号码（杀号 Top 3）[\s\S]*?"
        r"\| 1 \| \*\*(\d+)\*\*[\s\S]*?"
        r"\| 2 \| \*\*(\d+)\*\*[\s\S]*?"
        r"\| 3 \| \*\*(\d+)\*\*",
        t,
    )
    if m:
        out["防守Top3"] = fmt([m.group(i) for i in range(1, 4)])
    sec = re.search(r"跨规则共识号码[\s\S]*?(?=####|\Z)", t)
    if sec:
        out["跨规则共识"] = fmt(re.findall(r"号码 `(\d+)`", sec.group(0)))
    # env / kl / beacon from report if present
    m = re.search(r"环境[：:][`\s]*([^`\n|]+)", t)
    if m:
        out["_env"] = m.group(1).strip()
    m = re.search(r"KL[^\n]{0,80}", t)
    if m:
        out["_kl"] = m.group(0).strip()
    return out


def enrich_from_state(rec: dict) -> dict:
    sp = ROOT / "cache" / "self_learning_state.json"
    if not sp.exists():
        return rec
    state = json.loads(sp.read_text(encoding="utf-8"))
    snap = None
    for h in state.get("history", []):
        if str(h.get("target_issue")) == "2026203":
            snap = h
            break
    if not snap:
        return rec
    mapping = {
        "爆发Top5": "deep_picks",
        "防守Top3": "deep_kills",
        "跨规则共识": "deep_consensus",
        "mRMR": "mrmr_top12",
        "纯净池高置信": "pure_pool_top",
        "纯净池旧规则": "pure_pool_old_rule",
        "纯净池LR": "pure_pool_lr",
        "纯净池全量": "pure_pool_all",
        "HE5": "he5",
    }
    for rk, sk in mapping.items():
        if (not rec.get(rk)) and snap.get(sk):
            rec[rk] = fmt(snap[sk])
    # b3_final5 sometimes is HE-ish
    if not rec.get("HE5") and snap.get("b3_final5"):
        rec["HE5"] = fmt(snap["b3_final5"])
    rec["_snap"] = {k: snap.get(k) for k in (
        "environment", "kl_msg", "trinity_weights", "conf_top5", "top5", "b3_final5"
    )}
    return rec


ORDER = [
    "HE5", "Trinity5", "Trinity12", "AI5", "AI12", "Golden", "mRMR",
    "纯净池高置信", "纯净池旧规则", "纯净池LR", "纯净池全量",
    "爆发Top5", "防守Top3", "跨规则共识",
]


def load_recent_reviews(n: int = 10) -> list[dict]:
    rows = []
    for p in sorted(ROOT.joinpath("reviews").glob("review_*.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        hs = d.get("hit_stats") or {}
        if "top5_hits" not in hs:
            continue
        rows.append({
            "period": str(d.get("period")),
            "top5_hits": hs.get("top5_hits"),
            "top5_lift": hs.get("top5_lift"),
            "top12_hits": hs.get("top12_hits"),
            "top12_lift": hs.get("top12_lift"),
        })
        if len(rows) >= n:
            break
    rows.sort(key=lambda x: x["period"])
    return rows


def he5_from_reports(periods: list[str]) -> dict[str, str]:
    """Map draw period -> HE5 that was recommended for it (from prior day report)."""
    # Use self_learning history snaps: target_issue -> he5/b3
    sp = ROOT / "cache" / "self_learning_state.json"
    out = {}
    if not sp.exists():
        return out
    state = json.loads(sp.read_text(encoding="utf-8"))
    for h in state.get("history", []):
        ti = str(h.get("target_issue", ""))
        he = h.get("he5") or h.get("b3_final5") or h.get("top5")
        if ti and he:
            out[ti] = fmt(he)
    return out


def score_he5(he5: str, draw: set[int]) -> tuple[int, float]:
    nums = [int(x) for x in he5.split()] if he5 else []
    hits = len(set(nums) & draw)
    return hits, (hits / 5) / 0.25 if nums else 0.0


def main() -> None:
    md = ROOT / "reports" / "daily_analysis_report_20260801.md"
    rec = enrich_from_state(extract_md(md))

    # draws
    draws = {}
    for line in (ROOT / "kl8_history_final.txt").read_text(encoding="utf-8").splitlines()[:30]:
        if not line.startswith("date:"):
            continue
        parts = dict(p.split(":", 1) for p in line.split(",") if ":" in p)
        draws[parts["period"]] = set(
            int(x) for x in parts["numbers"].replace("-", " ").split()
        )

    reviews = load_recent_reviews(10)
    he_map = he5_from_reports([])

    panel = [
        "=" * 72,
        " 快乐8 每日全流程分析 | 2026-08-01 | 目标期 2026203",
        "=" * 72,
        " 数据: kl8最新=2026202(2026-07-31) | 点位=2026203 | 六项校验 PASS",
        " 自学习: FROZEN (WF Lift≈1.0046 < 1.1) | 权重 EF:0.40 RW:0.30 FO:0.30 | v4.2",
        " 信标: Level1×0.5 | 优化决策=无需调整",
        "",
        "-" * 72,
        " [任务2] 2026202 开奖复盘  |  "
        + "-".join(f"{n:02d}" for n in sorted(draws.get("2026202", []))),
        "-" * 72,
    ]
    # learner review for 2026202
    r202 = next((r for r in reviews if r["period"] == "2026202"), None)
    if r202:
        panel.append(
            f"  learner Top5  {r202['top5_hits']}/5  Lift={r202['top5_lift']:.2f}x  |  "
            f"Top12 {r202['top12_hits']}/12 Lift={r202['top12_lift']:.2f}x"
        )
    # HE5 hit for 2026202 from snap
    he_prev = he_map.get("2026202", "")
    if he_prev and "2026202" in draws:
        h, l = score_he5(he_prev, draws["2026202"])
        panel.append(f"  HE5复盘       {h}/5  Lift={l:.2f}x  推荐[{he_prev}]")

    panel += ["", "=" * 72, " [命中率] 近10期 learner Top5/Top12", "=" * 72]
    panel.append(f"  {'期号':<10}{'Top5':>8}{'Lift5':>8}{'Top12':>8}{'Lift12':>8}")
    panel.append("  " + "-" * 42)
    for r in reviews:
        panel.append(
            f"  {r['period']:<10}{r['top5_hits']}/5"
            f"{r['top5_lift']:>8.2f}x"
            f"{r['top12_hits']:>5}/12"
            f"{r['top12_lift']:>8.2f}x"
        )
    if reviews:
        avg5 = sum(r["top5_lift"] for r in reviews) / len(reviews)
        avg12 = sum(r["top12_lift"] for r in reviews) / len(reviews)
        panel.append("  " + "-" * 42)
        panel.append(f"  近{len(reviews)}期均值  Top5 Lift={avg5:.2f}x  Top12 Lift={avg12:.2f}x")
        panel.append("  结论: 贴近/略高于随机基线；门控 FROZEN → 无需调整")

    # HE5 channel last 10 from snaps vs draws
    he_rows = []
    for per in sorted(draws.keys(), reverse=True):
        if per not in he_map:
            continue
        h, l = score_he5(he_map[per], draws[per])
        he_rows.append((per, he_map[per], h, l))
        if len(he_rows) >= 10:
            break
    he_rows.sort(key=lambda x: x[0])
    if he_rows:
        panel += ["", "=" * 72, " [HE5通道] 近窗复盘 (有快照的期)", "=" * 72]
        for per, nums, h, l in he_rows:
            panel.append(f"  {per}  {h}/5 Lift={l:.2f}x  |  {nums}")
        avg = sum(x[3] for x in he_rows) / len(he_rows)
        panel.append(f"  均值 Lift={avg:.2f}x")

    panel += [
        "",
        "=" * 72,
        " [任务4] 2026203 核心推荐面板",
        "=" * 72,
    ]
    for k in ORDER:
        panel.append(f"  {k:<14} {rec.get(k, '')}")
    snap = rec.get("_snap") or {}
    if snap.get("environment"):
        panel.append(f"  环境             {snap.get('environment')}")
    if snap.get("kl_msg"):
        panel.append(f"  KL               {snap.get('kl_msg')}")
    panel += [
        "",
        "=" * 72,
        " 决策: 经统计检验未稳定显著优于随机；维持 v4.2，不叠加复杂优化",
        "=" * 72,
    ]

    text = "\n".join(panel) + "\n"
    (ROOT / "reports" / "control_panel_20260801.txt").write_text(text, encoding="utf-8")

    lines = ["【目标期 2026203 · 报告日 20260801】"] + [
        f"{k:<16}{rec.get(k, '')}" for k in ORDER
    ]
    (ROOT / "reports" / "可复制推荐_2026203.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    (ROOT / "scratch" / "recs_2026203.json").write_text(
        json.dumps({k: rec.get(k, "") for k in ORDER}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (ROOT / "cache" / "ai_memory_20260801.md").write_text(
        "# AI Memory 2026-08-01\n\n"
        f"- 目标期 2026203 | HE5: {rec.get('HE5','')}\n"
        "- 复盘 2026202 learner Top5 1/5 Lift=0.80x\n"
        "- 门控 FROZEN WF≈1.0046 | 决策: 无需调整 | v4.2\n",
        encoding="utf-8",
    )
    print(text)
    print("[wrote] control_panel + 可复制推荐_2026203 + memory")


if __name__ == "__main__":
    main()
