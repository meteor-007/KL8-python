# -*- coding: utf-8 -*-
"""数据一致性校验 CLI（只读；--apply 才写目标并备份）。

    python scripts/data_sync.py
    python scripts/data_sync.py --json
    python scripts/data_sync.py --apply --kind history --target <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.data_sync import apply_copy, apply_sorted, compare, render, summarize

A_HISTORY = ROOT.parent / "Python-Project" / "data" / "storage" / "raw" / "kl8_history_final.txt"
A_POINTS = ROOT / "data" / "cache" / "points_archive.txt"
B_ROOT = ROOT.parent / "yuce-kaiyuan"
C_ROOT = ROOT.parent / "微积分分区"
B_HISTORY = B_ROOT / "kl8_history_final.txt"
B_POINTS = B_ROOT / "daily_points.txt"
C_HISTORY = C_ROOT / "kl8_history.txt"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--apply", action="store_true", help="把源复制到目标（写前备份）")
    ap.add_argument("--kind", choices=["history", "points"], default="history")
    ap.add_argument("--source", default=None)
    ap.add_argument("--target", default=None)
    ap.add_argument("--order", choices=["preserve", "descending", "ascending"],
                    default="preserve", help="--apply 写出的期号顺序")
    ap.add_argument("--force", action="store_true",
                    help="允许 --apply 覆盖 A 的 canonical 冻结数据（会危及预注册）")
    args = ap.parse_args(argv)
    if not args.apply and (args.source or args.target):
        ap.error("--source/--target 只能与 --apply 一起使用")

    source = Path(args.source) if args.source else (
        A_HISTORY if args.kind == "history" else A_POINTS)
    if args.apply:
        if not args.target:
            print("✗ --apply 需要 --target", file=sys.stderr)
            return 1
        target = Path(args.target).resolve()
        frozen = {A_HISTORY.resolve(), A_POINTS.resolve()}
        if target in frozen and not args.force:
            print("✗ 拒绝改写 A 的 canonical 冻结数据（会使预注册失效）；"
                  "如确需请加 --force", file=sys.stderr)
            return 1
        try:
            backed_up = (apply_sorted(source, args.target, args.order, args.kind)
                         if args.order != "preserve" else apply_copy(source, args.target))
        except (OSError, ValueError) as exc:
            print(f"✗ 复制失败：{exc}", file=sys.stderr)
            return 1
        note = "（目标原文件已备份）" if backed_up else "（目标为新建）"
        print(f"已复制 {source} → {args.target}{note}")
        return 0

    comparisons = []
    tracked = (("B_history", B_HISTORY, "history"),
               ("B_points", B_POINTS, "points"),
               ("C_history", C_HISTORY, "history"))
    skipped = [name for name, path, _kind in tracked if not path.exists()]
    if B_HISTORY.exists():
        comparisons.append(compare("history", A_HISTORY, B_HISTORY))
    if C_HISTORY.exists():
        comparisons.append(compare("history", A_HISTORY, C_HISTORY))
    if B_POINTS.exists():
        comparisons.append(compare("points", A_POINTS, B_POINTS))

    if args.json:
        payload = {
            "summaries": {
                "A_history": summarize(A_HISTORY),
                "A_points": summarize(A_POINTS, "points"),
                "B_history": summarize(B_HISTORY),
                "B_points": summarize(B_POINTS, "points"),
                "C_history": summarize(C_HISTORY),
            },
            "skipped": skipped,
            "comparisons": [c.to_dict() for c in comparisons],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("== 数据摘要 ==")
        for name, path, kind in (("A_history", A_HISTORY, "history"),
                                 ("A_points", A_POINTS, "points"),
                                 ("B_history", B_HISTORY, "history"),
                                 ("B_points", B_POINTS, "points"),
                                 ("C_history", C_HISTORY, "history")):
            s = summarize(path, kind)
            print(f"{name:<10} count={s['count']:<5} latest={s['latest']}  {path}")
        if skipped:
            print(f"\n跳过（目标不存在）：{', '.join(skipped)}")
        print("\n== 一致性 ==")
        print(render(comparisons))

    return 0 if all(c.ok for c in comparisons) else 2


if __name__ == "__main__":
    sys.exit(main())