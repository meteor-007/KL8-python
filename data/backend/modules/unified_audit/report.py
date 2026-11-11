# -*- coding: utf-8 -*-
"""统一对账 Markdown 日报。"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from backend.modules.unified_audit.ledger import load_latest, recent_settled
from backend.utils.paths import get_outputs_dir, get_project_root


def _fmt(nums) -> str:
    if not nums:
        return "—"
    out = []
    for x in nums:
        try:
            out.append(f"{int(x):02d}")
        except Exception:
            continue
    return " ".join(out) if out else "—"


def _avg(rows: List[Dict], key: str) -> Optional[float]:
    vals = []
    for r in rows:
        h = r.get("hits") or {}
        if h.get(key) is not None:
            vals.append(float(h[key]))
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def render_report(proj_dir: Optional[str] = None) -> str:
    root = proj_dir or get_project_root()
    latest = load_latest(root) or {}
    settled = recent_settled(30, root)
    tp = latest.get("target_period")
    based = latest.get("based_on_period")
    flags = latest.get("strategy_flags") or {}
    hits = latest.get("hits") or {}

    lines = [
        f"# 统一对账日报 · 目标期 {tp}",
        "",
        f"- 锚定期: `{based}`｜快照: `{latest.get('snapshot_at')}`｜已结算: `{latest.get('settled')}`",
        f"- 评分版本: `{latest.get('a_scoring_version')}`",
        f"- 形态仓位: **{flags.get('stance', '—')}**｜{flags.get('note', '')}",
        f"- 同源旁证激活: `{flags.get('homology_evidence_active')}` (count={flags.get('homology_count')})",
        f"- 012战术抬权允许: `{flags.get('tactical_boost_allowed')}`",
        "",
        "## 本期预测快照",
        "",
        "| 维度 | 内容 |",
        "|------|------|",
        f"| A tip3 | `{_fmt(latest.get('a_tip3'))}` |",
        f"| A Top5 | `{_fmt(latest.get('a_top5'))}` |",
        f"| A Top12 | `{_fmt(latest.get('a_top12'))}` |",
        f"| A 回补 | `{latest.get('a_rebound')}` |",
        f"| A 同源4 | `{_fmt(latest.get('a_homology4'))}` |",
        f"| B VIP | `{_fmt(latest.get('b_vip_top5'))}` |",
        f"| B 孪生 | `{_fmt(latest.get('b_twin_pair'))}` |",
        f"| B 012 | `{latest.get('b_road_ratio')}` |",
        f"| 三高金/对/Top5 | `{latest.get('tri_high_gold')}` / `{_fmt(latest.get('tri_high_pair'))}` / `{_fmt(latest.get('tri_high_top5'))}` |",
        f"| 选2 | 金`{latest.get('pick2_golden')}` 热`{latest.get('pick2_hot')}` 对`{_fmt(latest.get('pick2_pair'))}` |",
        f"| 反弹 Top1/3 | `{latest.get('suppression_top1')}` / `{_fmt(latest.get('suppression_top3'))}` |",
        f"| Kill 高杀 | `{_fmt(latest.get('kill_high'))}`｜近窗高杀命中率 `{latest.get('kill_avg_high_rate')}` |",
        f"| 桥接短名单 | `{_fmt(latest.get('bridge_shortlist'))}` |",
        f"| 桥接明细 | `{latest.get('bridge_details')}` |",
        "",
    ]

    if latest.get("settled"):
        lines += [
            "## 本期结算",
            "",
            f"- 实开: `{_fmt(latest.get('actual_numbers'))}`",
            f"- tip3命中 {hits.get('tip3_hits')}/{hits.get('tip3_n')}｜Top5 {hits.get('top5_hits')}/{hits.get('top5_n')}｜Top12 {hits.get('top12_hits')}/{hits.get('top12_n')}",
            f"- VIP {hits.get('vip_hits')}/{hits.get('vip_n')}｜孪生 {hits.get('twin_hits')}/{hits.get('twin_n')} 双飞 `{hits.get('twin_double')}`",
            f"- 选2命中 {hits.get('pick2_hits')} 双飞 `{hits.get('pick2_both')}`｜反弹Top1 `{hits.get('suppression_top1_hit')}`",
            f"- 桥接命中 {hits.get('bridge_hits')}/{hits.get('bridge_n')}",
            f"- Kill高杀漏杀率(开出/总数) `{hits.get('kill_high_miss_rate')}`｜成功回避率 `{hits.get('kill_high_success_rate')}`",
            "",
        ]

    # 近30滚动
    if settled:
        lines += [
            "## 近30期已结算滚动（可复制）",
            "",
            "```text",
            f"样本={len(settled)}",
            f"A tip3均命中={_avg(settled, 'tip3_hits')}",
            f"A Top5均命中={_avg(settled, 'top5_hits')}",
            f"A Top12均命中={_avg(settled, 'top12_hits')}",
            f"B VIP均命中={_avg(settled, 'vip_hits')}",
            f"桥接均命中={_avg(settled, 'bridge_hits')}",
            f"Kill高杀漏杀率均值={_avg(settled, 'kill_high_miss_rate')}",
            "```",
            "",
            "| 期号 | tip3 | Top5 | VIP | 孪生 | 选2双 | 反弹1 | 桥接 | 高杀漏杀率 |",
            "|------|------|------|-----|------|-------|-------|------|------------|",
        ]
        for r in settled[-15:]:
            h = r.get("hits") or {}
            lines.append(
                f"| {r.get('target_period')} | {h.get('tip3_hits')}/{h.get('tip3_n')} | "
                f"{h.get('top5_hits')}/{h.get('top5_n')} | {h.get('vip_hits')}/{h.get('vip_n')} | "
                f"{h.get('twin_hits')}/{h.get('twin_n')} | {h.get('pick2_both')} | "
                f"{h.get('suppression_top1_hit')} | {h.get('bridge_hits')}/{h.get('bridge_n')} | "
                f"{h.get('kill_high_miss_rate')} |"
            )
        lines.append("")

    lines += [
        "## 可抄票面（本期）",
        "",
        "```text",
        f"【统一对账·{tp}】stance={flags.get('stance')}",
        f"A tip3 {_fmt(latest.get('a_tip3'))}｜Top5 {_fmt(latest.get('a_top5'))}｜12 {_fmt(latest.get('a_top12'))}",
        f"B VIP {_fmt(latest.get('b_vip_top5'))}｜孪生 {_fmt(latest.get('b_twin_pair'))}",
        f"三高 {latest.get('tri_high_gold')}｜选2 {_fmt(latest.get('pick2_pair'))}｜反弹 {latest.get('suppression_top1')}",
        f"桥接 {_fmt(latest.get('bridge_shortlist'))}",
        f"Kill高杀 {_fmt(latest.get('kill_high'))}",
        "```",
        "",
    ]
    return "\n".join(lines)


def write_report(proj_dir: Optional[str] = None) -> str:
    root = proj_dir or get_project_root()
    text = render_report(root)
    out_dir = os.path.join(get_outputs_dir(), "reports")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "unified_audit_report_latest.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
