# -*- coding: utf-8 -*-
"""报告协议检查 CLI：效应量/CI/p/T/MDE/基线/免责声明缺一不可。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.report_audit import check_file, render


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    paths = list(argv or sys.argv[1:])
    if not paths:
        print("用法：python scripts/report_audit.py <report.md> [...]", file=sys.stderr)
        return 2
    bad = 0
    for p in paths:
        missing = check_file(p)
        print(render(p, missing))
        bad += 1 if missing else 0
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
