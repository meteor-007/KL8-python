# -*- coding: utf-8 -*-
"""试验登记 CLI（审计元数据，不参与预测路径）。

    python scripts/trials.py add --id T-001 --family methods --category method \
        --description "..." --z 1.2 --q 0.4 --lift 1.03 --T 60
    python scripts/trials.py list [--family methods-60]
    python scripts/trials.py summary [--alpha 0.05]
    python scripts/trials.py registration [--alpha 0.05]
    python scripts/trials.py seed --report output/2026-11-10/daily_report.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.trials import TrialRegistry


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / "prereg" / "trials.jsonl"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="登记一个试验")
    p.add_argument("--id", required=True)
    p.add_argument("--family", required=True)
    p.add_argument("--category", default="method")
    p.add_argument("--description", required=True)
    p.add_argument("--status", default="run")
    p.add_argument("--z", type=float)
    p.add_argument("--q", type=float)
    p.add_argument("--lift", type=float)
    p.add_argument("--T", dest="n_periods", type=int)
    p.add_argument("--source", default="manual")

    p = sub.add_parser("list", help="列出试验")
    p.add_argument("--family", default=None)

    p = sub.add_parser("summary", help="按家族汇总（Bonferroni / 期望最大 z）")
    p.add_argument("--alpha", type=float, default=0.05)

    p = sub.add_parser("registration", help="对照预注册：登记前/后试验数")
    p.add_argument("--registration", default=str(ROOT / "prereg" / "active.json"))
    p.add_argument("--alpha", type=float, default=0.05)

    p = sub.add_parser("seed", help="一次性写入已知历史试验")
    p.add_argument("--report", default=str(ROOT / "output/2026-11-10/daily_report.md"))

    args = ap.parse_args(argv)
    reg = TrialRegistry(Path(args.file))

    if args.cmd == "add":
        result = {}
        for key, val in (("z", args.z), ("q", args.q), ("lift", args.lift),
                         ("T", args.n_periods)):
            if val is not None:
                result[key] = val
        rec = reg.add(args.id, args.family, args.category, args.description,
                      status=args.status, result=result, source=args.source)
        print(f"已登记 {rec['trial_id']}（{rec['family']} / {rec['category']}）")
        return 0

    if args.cmd == "list":
        records = reg.load()
        if args.family:
            records = [r for r in records if r.get("family") == args.family]
        for r in records:
            print(f"{r['trial_id']:<28} {r['family']:<18} {r['category']:<12} "
                  f"{r['status']:<10} {r['description']}")
        print(f"\n共 {len(records)} 条")
        return 0

    if args.cmd == "summary":
        s = reg.summary(alpha=args.alpha)
        print(f"试验总数: {s['total']}")
        print("按类别  :", s["by_category"])
        print("按状态  :", s["by_status"])
        print()
        print(f"{'家族':<20}{'N':>4}{'Bonf α':>10}{'E[max z]':>11}"
              f"{'best z':>9}{'best q':>9}  判定")
        for fam, d in sorted(s["families"].items()):
            print(f"{fam:<20}{d['N']:>4}"
                  f"{(d['bonferroni_alpha'] or 0):>10.5f}"
                  f"{d['expected_max_z']:>11.3f}"
                  f"{(d['observed_best_z'] if d['observed_best_z'] is not None else 0):>9.3f}"
                  f"{(d['best_q'] if d['best_q'] is not None else 0):>9.4f}  {d['verdict']}")
        o = s["overall"]
        print(f"\n总体: N={o['N']}  Bonferroni α={o['bonferroni_alpha']:.5f}  "
              f"E[max z]={o['expected_max_z']:.3f}  "
              f"observed best z={o['observed_best_z']}  → {o['verdict']}")
        return 0

    if args.cmd == "registration":
        r = reg.registration_summary(Path(args.registration), alpha=args.alpha)
        print(f"登记号              : {r['registration_id']}")
        print(f"登记时间            : {r['registered_at']}")
        print(f"登记前试验数 N      : {r['trials_before_registration']}")
        print(f"Bonferroni 阈值     : {r['bonferroni_alpha']}")
        print(f"E[max z | N]        : {r['expected_max_z']}")
        print(f"登记前最好 z        : {r['observed_best_z_before']}")
        print(f"登记后新增试验      : {r['trials_after_registration']} "
              f"{r['after_ids'] if r['after_ids'] else ''}")
        print(f"前瞻清洁            : {'是' if r['clean'] else '否 —— ' + r['note']}")
        return 0

    if args.cmd == "seed":
        out = reg.seed(Path(args.report))
        print(f"已写入 {out['added']} 条，跳过 {out['skipped']} 条（已存在）")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())