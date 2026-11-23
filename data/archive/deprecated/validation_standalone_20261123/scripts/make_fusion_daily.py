# -*- coding: utf-8 -*-
"""按当期 preflight 结果，从模板生成当期融合引擎。

用法：
    python scripts/make_fusion_daily.py
    python scripts/make_fusion_daily.py --preflight data/state/preflight.json
    python scripts/make_fusion_daily.py --template scripts/fusion_engine_template.py

生成：scripts/fusion_engine_<目标期>.py
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_TEMPLATE = ROOT / "scripts/fusion_engine_template.py"
DEFAULT_PREFLIGHT = ROOT / "data/state/preflight.json"

CONST_RE = re.compile(
    r"TARGET_PERIOD: int = \d+.*?PREV_DRAW_NUMBERS: Tuple\[int, \.\.\.\] = \(\n.*?\n\)",
    re.S,
)
PICK_RE = re.compile(
    r"    # 本日图表角色：.*?\n"
    r"    path_dw = _pick\(.*?\)\n"
    r"    path_fx = _pick\(.*?\)\n"
    r"    path_zd = _pick\(.*?\)",
    re.S,
)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT))
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    pf = json.loads(Path(args.preflight).read_text(encoding="utf-8"))
    target = pf["target"]
    prev = pf["latest_draw"]
    period = int(target["period"])
    prev_period = int(prev["period"])
    charts = pf.get("charts", {})

    missing = [r for r in ("点位图", "高概率图表", "找胆图") if not charts.get(r, {}).get("name")]
    if missing:
        print(f"✗ preflight 缺少图表：{missing}；先运行 daily_preflight.py", file=sys.stderr)
        return 1

    text = Path(args.template).read_text(encoding="utf-8")

    const_new = (
        f"TARGET_PERIOD: int = {period}\n"
        f"PREVIOUS_PERIOD: int = {prev_period}\n"
        f"PREVIOUS_DRAW_DATE: str = \"{prev['date']}\"\n"
        f"TARGET_PREDICT_DATE: str = \"{target['date']}\"\n"
        f"BACKTEST_END_PERIOD: int = {int(pf['backtest_end_period'])}"
        f"          # 找胆图数据覆盖上限（自动识别）\n"
        f"POINTS_ARCHIVE_PATH: str = \"data/cache/points_archive.txt\"\n"
        f"PREV_PUBLISHED_DIR: str = \"{pf['prev_published_dir']}\"\n\n"
        f"PREV_DRAW_NUMBERS: Tuple[int, ...] = (\n    "
        + ", ".join(str(n) for n in pf["prev_draw_numbers"])
        + "\n)"
    )
    text, n = CONST_RE.subn(const_new, text, count=1)
    if n != 1:
        print("✗ 未能定位常量块", file=sys.stderr)
        return 1

    pick_new = (
        "    # 图表由 preflight 按 sheet 内容识别，不使用文件名硬编码\n"
        f"    path_dw = os.path.join(file_dir, {charts['点位图']['name']!r})\n"
        f"    path_fx = os.path.join(file_dir, {charts['高概率图表']['name']!r})\n"
        f"    path_zd = os.path.join(file_dir, {charts['找胆图']['name']!r})"
    )
    text, n = PICK_RE.subn(pick_new, text, count=1)
    if n != 1:
        print("✗ 未能定位图表路径块", file=sys.stderr)
        return 1

    text = re.sub(r"快乐8 \d{7}期 全栈", f"快乐8 {period}期 全栈", text, count=1)
    text = re.sub(r"上期\(\d+期\)实开值", f"上期({prev_period % 1000}期)实开值", text)
    text = re.sub(r"当期\(\d+期\)均值回归研判", f"当期({period % 1000}期)均值回归研判", text)
    text = re.sub(r"第 \d+ 期均值回归研判", f"第 {period % 1000} 期均值回归研判", text)
    text = re.sub(r"@since \d{4}-\d{2}-\d{2}", f"@since {target['date']}", text, count=1)

    out = Path(args.out) if args.out else ROOT / "scripts" / f"fusion_engine_{period}.py"
    out.write_text(text, encoding="utf-8", newline="\n")
    ast.parse(text)

    print(f"已生成 {out}")
    print(f"  目标期 {period}（{target['date']}），基准期 {prev_period}（{prev['date']}）")
    print(f"  图表：{charts['点位图']['name']} / {charts['高概率图表']['name']} / {charts['找胆图']['name']}")
    print(f"  回测截止：{pf['backtest_end_period']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())