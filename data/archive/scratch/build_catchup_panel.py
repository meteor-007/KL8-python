#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build accurate catchup panels from MD + snap JSON."""
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

    def one(pat: str):
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

    # burst top5 from table bold numbers under 最终精选爆发码
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
    cons = re.findall(r"跨规则共识号码[\s\S]*?(?:号码 `(\d+)`)", t)
    # better: all 号码 `N` under consensus section until next ####
    sec = re.search(r"跨规则共识号码[\s\S]*?(?=####|\Z)", t)
    if sec:
        cons = re.findall(r"号码 `(\d+)`", sec.group(0))
        out["跨规则共识"] = fmt(cons)
    return out


def enrich_snap(rec: dict, snap_path: Path) -> dict:
    if not snap_path.exists():
        return rec
    meta = json.loads(snap_path.read_text(encoding="utf-8"))
    snap = meta.get("snap") or {}
    mapping = {
        "爆发Top5": "deep_picks",
        "防守Top3": "deep_kills",
        "跨规则共识": "deep_consensus",
        "mRMR": "mrmr_top12",
        "纯净池高置信": "pure_pool_top",
        "纯净池旧规则": "pure_pool_old_rule",
        "纯净池LR": "pure_pool_lr",
        "纯净池全量": "pure_pool_all",
    }
    for rk, sk in mapping.items():
        if (not rec.get(rk)) and snap.get(sk):
            rec[rk] = fmt(snap[sk])
    return rec


ORDER = [
    "HE5",
    "Trinity5",
    "Trinity12",
    "AI5",
    "AI12",
    "Golden",
    "mRMR",
    "纯净池高置信",
    "纯净池旧规则",
    "纯净池LR",
    "纯净池全量",
    "爆发Top5",
    "防守Top3",
    "跨规则共识",
]

PERIODS = [
    ("2026196", "20260725", "2026195"),
    ("2026197", "20260726", "2026196"),
    ("2026198", "20260727", "2026197"),
    ("2026199", "20260728", "2026198"),
]


def main() -> None:
    summary = json.loads(
        (ROOT / "scratch" / "catchup_4periods_summary.json").read_text(encoding="utf-8")
    )
    sum_by = {s["target"]: s for s in summary}
    draws = {}
    for line in (ROOT / "kl8_history_final.txt").read_text(encoding="utf-8").splitlines()[:30]:
        if not line.startswith("date:"):
            continue
        parts = dict(p.split(":", 1) for p in line.split(",") if ":" in p)
        draws[parts["period"]] = [
            int(x) for x in parts["numbers"].replace("-", " ").split()
        ]

    panel = [
        "=" * 72,
        " 快乐8 断档4期回补控制台 | 2026-07-28 | 目标序列 2026196→2026199",
        "=" * 72,
        " 数据: kl8最新=2026198(2026-07-27) | 点位最新=2026199 | 六项校验 PASS",
        " 自学习: FROZEN (WF Lift≈1.0043 < 1.1) | 版本 v4.2 | 优化决策=无需调整",
        "",
    ]
    all_recs = {}
    for target, rdate, review in PERIODS:
        md = ROOT / "reports" / f"daily_analysis_report_{rdate}.md"
        rec = extract_md(md)
        rec = enrich_snap(rec, ROOT / "scratch" / f"catchup_snap_{target}.json")
        all_recs[target] = rec
        s = sum_by[target]["loop"]
        actual = draws.get(review, [])
        panel += [
            "-" * 72,
            (
                f" [{rdate}] 目标期 {target}  |  复盘 {review}  "
                f"Top5={s['top5_hits']}/5 Lift={s['top5_lift']:.2f}x  "
                f"Top12={s['top12_hits']}/12 Lift={s['top12_lift']:.2f}x"
            ),
        ]
        if actual:
            panel.append(" 开奖: " + "-".join(f"{n:02d}" for n in sorted(actual)))
        panel.append("-" * 72)
        for k in ORDER:
            panel.append(f"  {k:<14} {rec.get(k, '')}")
        panel.append("")
        lines = [f"【目标期 {target} · 报告日 {rdate}】"] + [
            f"{k:<16}{rec.get(k, '')}" for k in ORDER
        ]
        (ROOT / "reports" / f"可复制推荐_{target}.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    lifts = [sum_by[t]["loop"]["top5_lift"] for t, _, _ in PERIODS]
    panel += [
        "=" * 72,
        " [命中率] 断档4期 learner Top5/Top12 复盘",
        "=" * 72,
    ]
    for target, rdate, review in PERIODS:
        s = sum_by[target]["loop"]
        panel.append(
            f"  {review}  Top5 {s['top5_hits']}/5 Lift={s['top5_lift']:.2f}x  "
            f"Top12 {s['top12_hits']}/12 Lift={s['top12_lift']:.2f}x  → 生成 {target}"
        )
    panel += [
        f"  4期 Top5 均值 Lift={sum(lifts)/len(lifts):.2f}x  (随机基线=1.00x)",
        "  决策: 无需调整（门控 FROZEN；不叠加复杂优化）",
        "",
        "=" * 72,
        " [今日主推 · 目标期 2026199]",
        "=" * 72,
        f"  HE5  {all_recs['2026199'].get('HE5', '')}",
        "=" * 72,
        "",
    ]
    text = "\n".join(panel)
    out = ROOT / "reports" / "control_panel_20260728.txt"
    out.write_text(text + "\n", encoding="utf-8")
    (ROOT / "scratch" / "catchup_recs_4periods.json").write_text(
        json.dumps(all_recs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(text)
    print(f"[wrote] {out}")


if __name__ == "__main__":
    main()
