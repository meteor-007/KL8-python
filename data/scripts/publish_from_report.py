# -*- coding: utf-8 -*-
"""从已生成的当日研报重建微信发布原文（不重跑预测、不覆盖研报）。

用法：
    python scripts/publish_from_report.py
    python scripts/publish_from_report.py --report storage/reports/daily_analysis_report_20261123.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = Path(__file__).resolve().parent
_DATA_DIR = _SCRIPT_DIR.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from backend.modules.wheel_matrix.wheel_engine import BUILTIN_WHEELS, WheelEngine


def _load_target_period() -> int:
    p = _DATA_DIR / "storage" / "cache" / "sixteen_period" / "latest_summary.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
            tp = int(data.get("target_period") or 0)
            if tp:
                return tp
        except Exception:
            pass
    return 0


def _load_points(target: int) -> list[str]:
    p = _DATA_DIR / "storage" / "raw" / "daily_points.txt"
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            if f"period:{target}" in line:
                m = re.search(r"points:([0-9 ]+)", line)
                if m:
                    return [f"{int(x):02d}" for x in m.group(1).split() if x.isdigit()]
    return []


def _load_tri_high(target: int) -> dict:
    p = _DATA_DIR / "storage" / "points" / "tri_high_points.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
            for r in data.get("records") or []:
                if str(r.get("period")) == str(target):
                    return r
        except Exception:
            pass
    return {}


def _find_report(target: int, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    tag = datetime.now().strftime("%Y%m%d")
    for p in (
        _DATA_DIR / f"daily_analysis_report_{tag}.md",
        _DATA_DIR / "storage" / "reports" / f"daily_analysis_report_{tag}.md",
    ):
        if p.exists():
            return p
    candidates = sorted((_DATA_DIR / "storage" / "reports").glob("daily_analysis_report_*.md"), reverse=True)
    for p in candidates:
        if f"## 二、{target}期" in p.read_text(encoding="utf-8", errors="ignore"):
            return p
    raise FileNotFoundError("未找到包含目标期的研报")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="从研报重建微信发布原文")
    parser.add_argument("--report", default=None, help="指定研报路径")
    parser.add_argument("--period", type=int, default=None, help="目标期（默认自动推断）")
    args = parser.parse_args(argv)

    target = args.period or _load_target_period()
    if not target:
        print("❌ 无法推断目标期")
        return 1

    report_path = _find_report(target, args.report)
    report_text = report_path.read_text(encoding="utf-8", errors="ignore")
    print(f"目标期: {target} | 研报: {report_path}")

    missing = []

    def grab(pattern: str, label: str):
        m = re.search(pattern, report_text)
        if not m:
            missing.append(label)
            return None
        return m.group(1).strip()

    p2_val = grab(r"👑 黄金搭档.*?`([0-9\s\-]+)`", "极简选2黄金搭档")
    if p2_val and len(re.findall(r"\d+", p2_val)) < 2:
        missing.append("极简选2号码对")
    gold_val = grab(r"👑 全场至尊核心金胆.*?`([0-9]+)`", "至尊金胆")
    opt20_val = grab(r"动量\+维度硬约束最优 20 码.*?`([0-9\s]+)`", "16期维度硬约束20码")
    top5_val = grab(r"极秘 Top 5.*?`(\[[0-9,\s]+\])`", "三维一体极秘Top5")
    top12_val = grab(r"极秘 Top 12.*?`(\[[0-9,\s]+\])`", "三维一体极秘Top12")

    if opt20_val and len([x for x in opt20_val.split() if x.isdigit()]) < 20:
        missing.append("16期维度硬约束20码(不足20码)")

    if missing:
        print(f"❌ 关键字段解析失败: {', '.join(missing)}")
        return 3

    points_20 = _load_points(target)
    tri_high = _load_tri_high(target)

    top12_nums = [int(x) for x in re.findall(r"\d+", top12_val)][:10]
    banker_num = int(gold_val) if gold_val.isdigit() else top12_nums[0]
    effective_banker = banker_num if banker_num in top12_nums else top12_nums[0]
    tpl = BUILTIN_WHEELS.get("W5_10_4_4_6")
    if not tpl:
        print("❌ 未找到旋转矩阵模板 W5_10_4_4_6")
        return 4
    wheel_tickets = WheelEngine.generate_wheel(tpl, top12_nums, bankers=[effective_banker])
    if len(wheel_tickets) < 6:
        print(f"❌ 旋转矩阵仅生成 {len(wheel_tickets)} 注（需 6 注）")
        return 4

    top20_list = [f"{int(x):02d}" for x in opt20_val.split()[:20]]
    p2_pair = re.findall(r"\d+", p2_val)
    p2_str = f"{int(p2_pair[0]):02d}  {int(p2_pair[1]):02d}"

    d3_str = f"{p2_str}  {top20_list[2]}"
    d5_str = f"{d3_str}  {top20_list[3]}  {top20_list[4]}"
    d7_str = f"{d5_str}  {top20_list[5]}  {top20_list[6]}"
    d10_str = f"{d7_str}  {top20_list[7]}  {top20_list[8]}  {top20_list[9]}"
    top20_str = "  ".join(top20_list)
    ticket_strs = [" ".join([f"{x:02d}" for x in t]) for t in wheel_tickets[:6]]

    m_avoid = re.search(r"◎\s*重点防守号码[^\n]*\n([0-9,\s]+)", report_text)
    def_avoid_nums = (
        [f"{int(x):02d}" for x in re.findall(r"\d+", m_avoid.group(1))] if m_avoid else []
    )
    def_avoid_str = "  ".join(def_avoid_nums) if def_avoid_nums else "（研报未给出防守号码）"

    today_str = datetime.now().strftime("%Y-%m-%d")
    content = f"""🔥【快乐8 第{target}期 核心研判与金胆推荐】🔥
📅 研判日期：{today_str} (工业级深度融合实测版)
--------------------------------
🎯【精选分桶推荐·一键投注参考】
👑 至尊独胆：【 {int(gold_val):02d} 】
🥈 黄金双飞选2：【 {p2_str} 】
🥉 必拿铁三角选3：【 {d3_str} 】
💎 五虎上将选5：【 {d5_str} 】
🚀 稳健实战选7：【 {d7_str} 】
🏆 围底十码选10：【 {d10_str} 】

🎲【盖尔·霍华德旋转矩阵·选五保四 (6注)】
1️⃣ {ticket_strs[0]}
2️⃣ {ticket_strs[1]}
3️⃣ {ticket_strs[2]}
4️⃣ {ticket_strs[3]}
5️⃣ {ticket_strs[4]}
6️⃣ {ticket_strs[5]}

🧭【16期动量与维度硬约束20码】
{top20_str}

⚠️【防守回避号码】
{def_avoid_str}
--------------------------------
💡 科学提示：量化概率贴合，理智购彩参考，祝老铁们好运连连！🧧
"""

    out = _DATA_DIR / "storage" / "reports" / f"wechat_publish_{target}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"✅ 已生成: {out}")
    print(f"   金胆={gold_val} | 选2={p2_str} | 矩阵定胆={effective_banker:02d} | 矩阵注数={len(wheel_tickets)}")
    print(f"   点位: {' '.join(points_20) if points_20 else '无'} | 三高记录: {'有' if tri_high else '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())