# -*- coding: utf-8 -*-
"""覆盖/平衡组合 CLI：构造 m 张 k 码票，报告期望与方差（不改变期望）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.coverage import render, summarize


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickets", type=int, default=16)
    ap.add_argument("--size", type=int, default=5)
    ap.add_argument("--numbers", type=int, default=80)
    ap.add_argument("--json", default=None, help="把结果写入 JSON")
    args = ap.parse_args(argv)
    res = summarize(args.tickets, args.size, args.numbers)
    print(render(res))
    if args.json:
        Path(args.json).write_text(
            json.dumps({k: v for k, v in res.items() if k != "tickets"},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已写入 {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
