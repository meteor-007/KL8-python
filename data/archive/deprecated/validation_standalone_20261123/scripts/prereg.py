# -*- coding: utf-8 -*-
"""预注册 CLI：create / lock / status / evaluate / invalidate。

    python scripts/prereg.py create --id KL8-2026-11-10-001 --model main \
        --periods 300 --start 2026300 \
        --hypothesis "主系统 Top5 相对命中率高于超几何随机基线"
    python scripts/prereg.py lock --model main --model fusion
    python scripts/prereg.py status
    python scripts/prereg.py evaluate            # 到期后才输出正式 p
    python scripts/prereg.py evaluate --exploratory
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kl8.config import load_config
from kl8.prereg import PreregStore


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create", help="创建预注册登记（冻结代码/配置/数据前缀）")
    p.add_argument("--id", required=True)
    p.add_argument("--model", default="main", choices=["main", "fusion"])
    p.add_argument("--periods", type=int, default=300)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--endpoint", default="top5_lift",
                   choices=["top5_lift", "points20_lift"])
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--hypothesis", default="")

    p = sub.add_parser("lock", help="锁定当期预测（必须在开奖前）")
    p.add_argument("--model", action="append", default=None,
                   help="可重复；默认 main 与 fusion")

    sub.add_parser("status", help="查看进度（不输出正式 p 值）")

    p = sub.add_parser("evaluate", help="达到计划期数后做唯一一次正式分析")
    p.add_argument("--exploratory", action="store_true",
                   help="未到期时做探索性分析，明确标注非预注册")

    p = sub.add_parser("invalidate", help="手动作废登记")
    p.add_argument("--reason", required=True)

    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    store = PreregStore(cfg)

    try:
        if args.cmd == "create":
            reg = store.create(args.id, args.model, args.periods, args.start,
                               hypothesis=args.hypothesis, alpha=args.alpha,
                               endpoint=args.endpoint)
            print("已创建预注册登记：")
            print(json.dumps({k: reg[k] for k in
                              ("registration_id", "created_at", "status", "model",
                               "primary_endpoint", "planned_periods", "start_period",
                               "mde_lift_at_plan")},
                             ensure_ascii=False, indent=2))
            print(f"冻结数据截止期：{reg['frozen']['data_cutoff_period']}")
            return 0

        if args.cmd == "lock":
            models = args.model or ["main", "fusion"]
            for model in models:
                res = store.lock(model)
                rec = res["record"]
                print(f"{model}: {res['status']}  {rec['period']}  "
                      f"{rec['core']}")
            return 0

        if args.cmd == "status":
            print(store.render_status())
            return 0

        if args.cmd == "evaluate":
            result = store.evaluate(exploratory=args.exploratory)
            print(store.render_evaluation(result))
            return 0

        if args.cmd == "invalidate":
            reg = store.invalidate(args.reason)
            print(f"已作废：{reg['registration_id']}（{args.reason}）")
            return 0
    except (ValueError, FileNotFoundError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())