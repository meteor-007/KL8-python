# -*- coding: utf-8 -*-
"""统一对账日报 CLI。"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional

from backend.modules.unified_audit.collector import collect_snapshot
from backend.modules.unified_audit.ledger import load_all, load_latest, upsert_row
from backend.modules.unified_audit.report import write_report
from backend.modules.unified_audit.settle import settle_period
from backend.utils.paths import get_project_root


def run_snapshot(target_period: Optional[int] = None, proj_dir: Optional[str] = None) -> Dict[str, Any]:
    root = proj_dir or get_project_root()
    row = collect_snapshot(root, target_period=target_period)
    if not row.get("target_period"):
        return {"status": "error", "message": "无法推断 target_period，请先跑 sixteen"}
    upsert_row(row, root)
    path = write_report(root)
    return {"status": "ok", "target_period": row["target_period"], "row": row, "report": path}


def run_settle(period: Optional[int] = None, proj_dir: Optional[str] = None) -> Dict[str, Any]:
    root = proj_dir or get_project_root()
    res = settle_period(period=period, proj_dir=root)
    if res.get("status") == "ok":
        res["report"] = write_report(root)
    return res


def run_report(proj_dir: Optional[str] = None) -> Dict[str, Any]:
    path = write_report(proj_dir)
    return {"status": "ok", "report": path, "latest": load_latest(proj_dir)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="统一对账看板")
    parser.add_argument("action", choices=["snapshot", "settle", "report", "ledger"], help="动作")
    parser.add_argument("--period", type=int, default=None, help="目标期/结算期")
    parser.add_argument("--limit", type=int, default=30, help="ledger 条数")
    args = parser.parse_args(argv)

    if args.action == "snapshot":
        res = run_snapshot(target_period=args.period)
    elif args.action == "settle":
        res = run_settle(period=args.period)
    elif args.action == "report":
        res = run_report()
    else:
        rows = load_all()[-args.limit :]
        res = {"status": "ok", "n": len(rows), "rows": rows}
    print(json.dumps({k: v for k, v in res.items() if k != "row"}, ensure_ascii=False, indent=2))
    if res.get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
