# -*- coding: utf-8 -*-
"""OUT 最大值/最小值(前三) 遗漏值表生成器。

口径：目标期 P 的 OUT = 每个号码截至 P-1 期开奖的连续未出期数。
  · OUT=0 表示上一期刚开出
  · 按 OUT 值分组列出 1-80 号码
  · 最大值(前三)：遗漏值最大的 3 个号码（红色高亮）
  · 最小值(前三)：遗漏值最小的 3 个号码（红色高亮）

用法：
    python scripts/omission_top3.py
    python scripts/omission_top3.py --last 10
    python scripts/omission_top3.py --periods 2026306-2026315
    python scripts/omission_top3.py --xlsx storage/reports/out_top3.xlsx --json storage/reports/out_top3.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_DATA_DIR = Path(__file__).resolve().parent.parent
_HISTORY = _DATA_DIR / "storage" / "raw" / "kl8_history_final.txt"

RED = "FFC00000"
BLACK = "FF000000"
TOP_FILL = PatternFill("solid", fgColor="FFFF0000")
HEAD_FILL = PatternFill("solid", fgColor="FFD9E1F2")
THIN = Side(style="thin", color="FFBFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def load_draws() -> list[tuple[int, list[int]]]:
    draws: list[tuple[int, list[int]]] = []
    for line in _HISTORY.read_text(encoding="utf-8-sig").splitlines():
        m = re.search(r"period:(\d+),numbers:([0-9\-]+)", line)
        if m:
            draws.append((int(m.group(1)), [int(x) for x in m.group(2).split("-")]))
    draws.sort()
    return draws


def omission_snapshot(draws: list[tuple[int, list[int]]], target: int) -> dict[int, int]:
    """返回 target 期开奖前的遗漏值：0=上一期刚开出。"""
    prev = [d for d in draws if d[0] < target]
    if not prev:
        return {n: 0 for n in range(1, 81)}
    om = {n: None for n in range(1, 81)}
    for idx, (_, nums) in enumerate(reversed(prev)):
        for n in nums:
            if om[n] is None:
                om[n] = idx
    for n in om:
        if om[n] is None:
            om[n] = len(prev)
    return om


def build_rows(draws: list[tuple[int, list[int]]], periods: list[int]) -> list[dict]:
    rows = []
    for p in periods:
        om = omission_snapshot(draws, p)
        groups: dict[int, list[int]] = {}
        for n, o in om.items():
            groups.setdefault(o, []).append(n)
        for o in groups:
            groups[o].sort()
        max_top3 = sorted(range(1, 81), key=lambda n: (-om[n], n))[:3]
        min_top3 = sorted(range(1, 81), key=lambda n: (om[n], n))[:3]
        rows.append({
            "period": p,
            "omission": om,
            "groups": groups,
            "max_top3": max_top3,
            "min_top3": min_top3,
        })
    return rows


def _rich_numbers(nums: list[int], picked: set[int]) -> CellRichText:
    parts = []
    for n in nums:
        text = f"{n:02d} "
        font = InlineFont(color=RED, b=True) if n in picked else InlineFont(color=BLACK)
        parts.append(TextBlock(font, text))
    return CellRichText(parts)


def write_xlsx(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    specs = [
        ("OUT最大值前三", "max_top3", "最大值(前三)"),
        ("OUT最小值前三", "min_top3", "最小值(前三)"),
    ]
    for idx, (title, key, sub) in enumerate(specs):
        ws = wb.active if idx == 0 else wb.create_sheet()
        ws.title = title
        ws.cell(row=1, column=1, value="OUT")
        ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
        ws.cell(row=1, column=1).fill = HEAD_FILL
        ws.cell(row=1, column=1).border = BORDER
        ws.cell(row=2, column=1).border = BORDER

        max_om = max(max(r["groups"]) for r in rows)
        for i, r in enumerate(rows):
            c = 2 + i * 2
            ws.cell(row=1, column=c, value=f"{r['period']}期")
            ws.merge_cells(start_row=1, start_column=c, end_row=1, end_column=c + 1)
            ws.cell(row=1, column=c).fill = HEAD_FILL
            ws.cell(row=1, column=c).border = BORDER
            ws.cell(row=2, column=c, value="OUT").fill = HEAD_FILL
            ws.cell(row=2, column=c).border = BORDER
            ws.cell(row=2, column=c + 1, value=sub).fill = HEAD_FILL
            ws.cell(row=2, column=c + 1).border = BORDER

        for om in range(0, max_om + 1):
            rr = 3 + om
            ws.cell(row=rr, column=1, value=om).border = BORDER
            for i, r in enumerate(rows):
                c = 2 + i * 2
                nums = r["groups"].get(om, [])
                picked = set(r[key]) & set(nums)
                ws.cell(row=rr, column=c, value=om).border = BORDER
                cell = ws.cell(row=rr, column=c + 1)
                cell.value = _rich_numbers(nums, picked) if nums else ""
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                cell.border = BORDER
        ws.freeze_panes = "B3"
        ws.column_dimensions["A"].width = 6
        for i in range(len(rows)):
            ws.column_dimensions[chr(66 + i * 2)].width = 6
            ws.column_dimensions[chr(67 + i * 2)].width = 28

    wb.save(path)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OUT 最大值/最小值(前三) 遗漏值表")
    ap.add_argument("--last", type=int, default=10, help="最近 N 个目标期（默认 10）")
    ap.add_argument("--periods", default=None, help="指定区间，如 2026306-2026315")
    ap.add_argument("--xlsx", default=None, help="输出 Excel 路径")
    ap.add_argument("--json", default=None, help="输出 JSON 路径")
    args = ap.parse_args(argv)

    draws = load_draws()
    if not draws:
        print("❌ 无开奖历史")
        return 1
    latest = draws[-1][0]
    if args.periods:
        a, b = args.periods.split("-")
        periods = list(range(int(a), int(b) + 1))
    else:
        periods = list(range(latest + 2 - args.last, latest + 2))

    rows = build_rows(draws, periods)
    stamp = datetime.now().strftime("%Y%m%d")
    xlsx = Path(args.xlsx) if args.xlsx else _DATA_DIR / "storage" / "reports" / f"OUT前三_遗漏值_{stamp}.xlsx"
    write_xlsx(rows, xlsx)

    if args.json:
        out = []
        for r in rows:
            out.append({
                "period": r["period"],
                "groups": {str(k): v for k, v in sorted(r["groups"].items())},
                "max_top3": r["max_top3"],
                "min_top3": r["min_top3"],
            })
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ 已生成: {xlsx}")
    print(f"   目标期: {periods[0]} - {periods[-1]} | 最新开奖: {latest}")
    for r in rows:
        mx = ", ".join(f"{n:02d}({r['omission'][n]})" for n in r["max_top3"])
        mn = ", ".join(f"{n:02d}({r['omission'][n]})" for n in r["min_top3"])
        print(f"   {r['period']}  最大值前三: {mx}  |  最小值前三: {mn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())