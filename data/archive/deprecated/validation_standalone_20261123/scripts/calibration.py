# -*- coding: utf-8 -*-
"""概率校准 CLI：输入逐期 (prob, hit) 对，输出 Brier / LogLoss / 可靠性分箱。

输入 JSON 支持两种格式：
    [{"prob": 0.31, "hit": 1}, ...]
    [[0.31, 1], ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calibration import render, summary


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="JSON 文件：逐期 (prob, hit)")
    args = ap.parse_args(argv)
    raw = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    pairs = []
    for item in raw:
        if isinstance(item, dict):
            pairs.append((item["prob"], item["hit"]))
        else:
            pairs.append((item[0], item[1]))
    print(render(summary(pairs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
