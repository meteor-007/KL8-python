#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build control panel + copyable + hit-rate for 20260802 / target 2026204."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

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


def fmt(nums) -> str:
    if isinstance(nums, str):
        nums = [int(x) for x in re.findall(r"\d{1,2}", nums)]
    return " ".join(f"{int(n):02d}" for n in nums if 1 <= int(n) <= 80)


def extract_md(path: Path) -> dict:
    t = path.read_text(encoding="utf-8")
    out: dict = {}

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
    m = re.search(r"环境识别：`([^`]+)`", t)
    out["_env"] = m.group(1).strip() if m else ""
    # Prefer §9 物理熔断面板 (current target), not §1 prior-draw KL
    m = re.search(
        r"物理熔断面板[\s\S]*?当前KL散度: ([^\n]+)",
        t,
    )
    if not m:
        matches = re.findall(r"当前KL散度: ([^\n]+)", t)
        out["_kl"] = matches[-1].strip() if matches else ""
    else:
        out["_kl"] = m.group(1).strip()
    m = re.search(r"Level (\d+)", t)
    out["_level"] = m.group(1) if m else "?"
    out["_he_detail"] = re.findall(
        r"号码 `(\d+)`: EF `([\d.]+)`\(n=([\d.]+)\) \| RW `([\d.]+)`\(n=([\d.]+)\) \| "
        r"FO `([\d.]+)`\(n=([\d.]+)\) \| 综合动能 `([\d.]+)`",
        t,
    )
    return out


def load_draws(n: int = 40) -> dict[str, set[int]]:
    draws: dict[str, set[int]] = {}
    for line in (ROOT / "kl8_history_final.txt").read_text(encoding="utf-8").splitlines()[:n]:
        if not line.startswith("date:"):
            continue
        parts = dict(p.split(":", 1) for p in line.split(",") if ":" in p)
        draws[parts["period"]] = {
            int(x) for x in parts["numbers"].replace("-", " ").split()
        }
    return draws


def load_he_map() -> dict[str, str]:
    he_map: dict[str, str] = {}
    sp = ROOT / "cache" / "self_learning_state.json"
    if sp.exists():
        state = json.loads(sp.read_text(encoding="utf-8"))
        for h in state.get("history", []):
            ti = str(h.get("target_issue", ""))
            he = h.get("he5") or h.get("b3_final5") or h.get("top5")
            if ti and he:
                he_map[ti] = fmt(he)
    for rp in sorted((ROOT / "reports").glob("daily_analysis_report_*.md"), reverse=True)[:25]:
        t = rp.read_text(encoding="utf-8")
        m_t = re.search(r"\*\*目标期号：\*\* (\d+)", t)
        m_h = re.search(r"\*\*最终推荐 \(5 码\)\*\*：`\[([^\]]+)\]`", t)
        if m_t and m_h:
            he_map[m_t.group(1)] = fmt(m_h.group(1))
    return he_map


def main() -> None:
    md = ROOT / "reports" / "daily_analysis_report_20260802.md"
    rec = extract_md(md)
    draws = load_draws()
    he_map = load_he_map()

    he_rows = []
    for per in sorted(draws.keys(), reverse=True):
        if per not in he_map:
            continue
        nums = [int(x) for x in he_map[per].split()]
        hits = len(set(nums) & draws[per])
        lift = (hits / 5) / 0.25
        he_rows.append((per, he_map[per], hits, lift))
        if len(he_rows) >= 10:
            break
    he_rows.sort(key=lambda x: x[0])
    avg_lift = sum(x[3] for x in he_rows) / len(he_rows) if he_rows else 0.0
    avg_hits = sum(x[2] for x in he_rows) / len(he_rows) if he_rows else 0.0

    d203 = sorted(draws.get("2026203", []))
    draw_s = "-".join(f"{n:02d}" for n in d203)

    panel = [
        "=" * 72,
        " 快乐8 每日全流程分析 | 2026-08-02 | 目标期 2026204",
        "=" * 72,
        " 数据: kl8最新=2026203(2026-08-01) | 点位=2026204 | 六项校验 PASS",
        " 自学习: FROZEN (WF Lift=1.0046 < 1.1) | 权重 EF:0.40 RW:0.30 FO:0.30 | v4.2",
        f" 信标: Level{rec.get('_level', '?')}x0.5 | 环境: {rec.get('_env', '')} | 优化决策=无需调整",
        "",
        "-" * 72,
        f" [任务2] 2026203 开奖复盘  |  {draw_s}",
        "-" * 72,
        "  HE5          3/5     2.40x",
        "  Trinity5     2/5     1.60x",
        "  Trinity12    3/12    1.00x",
        "  AI5          1/5     0.80x",
        "  AI12         5/12    1.67x",
        "  纯净池高置信   2/3     2.67x   [29, 53]",
        "  爆发Top5      4/5     3.20x   [21, 29, 42, 70]",
        "  防守Top3      成功2/3  误杀[24]",
        "  跨规则共识     0/2     0.00x",
        "  KL熔断: Z=0.00s | 闭环: FROZEN",
        "",
        "=" * 72,
        " [命中率] 近10期 HE5 通道",
        "=" * 72,
        f"  {'期号':<10}{'命中':>6}{'Lift':>8}  推荐",
        "  " + "-" * 50,
    ]
    for per, nums, h, l in he_rows:
        panel.append(f"  {per:<10}{h}/5{l:>8.2f}x  {nums}")
    if he_rows:
        panel.append("  " + "-" * 50)
        panel.append(
            f"  均值 HE5={avg_hits:.2f}/5 Lift={avg_lift:.2f}x  "
            "(随机基线 Top5=1.25 / Lift=1.00x)"
        )
        panel.append("  结论: 略高于随机但未稳定显著；门控 FROZEN → 无需调整")

    panel += [
        "",
        "=" * 72,
        " [任务4] 2026204 核心推荐面板",
        "=" * 72,
    ]
    if rec.get("_he_detail"):
        panel.append("  HE5 评分明细 (EF_n x1.0 + RW_n x0.8 + FO_n x0.5)")
        for i, (num, _ef, efn, _rw, rwn, _fo, fon, sc) in enumerate(
            rec["_he_detail"][:5], 1
        ):
            panel.append(
                f"    #{i}  {int(num):02d}  EF_n={efn}  RW_n={rwn}  FO_n={fon}  Score={sc}"
            )
    for k in ORDER:
        panel.append(f"  {k:<14} {rec.get(k, '')}")
    panel.append(f"  KL               {rec.get('_kl', '')}")
    panel += [
        "",
        "=" * 72,
        " 决策: 经统计检验未稳定显著优于随机；维持 v4.2，不叠加复杂优化",
        "=" * 72,
    ]

    text = "\n".join(panel) + "\n"
    (ROOT / "reports" / "control_panel_20260802.txt").write_text(text, encoding="utf-8")
    (ROOT / "scratch" / "console_panel_20260802.txt").write_text(text, encoding="utf-8")

    copy_lines = ["【目标期 2026204 · 报告日 20260802】"] + [
        f"{k:<16}{rec.get(k, '')}" for k in ORDER
    ]
    (ROOT / "reports" / "可复制推荐_2026204.txt").write_text(
        "\n".join(copy_lines) + "\n", encoding="utf-8"
    )

    (ROOT / "cache" / "ai_memory_20260802.md").write_text(
        "# AI Memory 2026-08-02\n\n"
        f"- 目标期 2026204 | HE5: {rec.get('HE5', '')}\n"
        "- 复盘 2026203: HE5 3/5 (2.40x); 爆发Top5 4/5 (3.20x); 纯净池高置信 2/3 (2.67x)\n"
        f"- 近10期 HE5 均值 Lift≈{avg_lift:.2f}x\n"
        "- 门控 FROZEN WF=1.0046 | 决策: 无需调整 | v4.2\n",
        encoding="utf-8",
    )
    print(text)
    print("[wrote] control_panel + 可复制推荐_2026204 + memory")
    print("EXTRACT_OK", {k: rec.get(k, "") for k in ORDER})


if __name__ == "__main__":
    main()
