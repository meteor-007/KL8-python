# -*- coding: utf-8 -*-
"""每日一条命令：run_daily 流程 + 台账自动提交/推送。

    python scripts/daily_all.py --points "01 02 ..."
    python scripts/daily_all.py --points-file today.txt
    python scripts/daily_all.py --dry-run          # 只做前置检查，不做预测/不提交
    python scripts/daily_all.py --no-git           # 只跑流程，不提交
    python scripts/daily_all.py --no-push          # 只本地提交，不推送

默认只提交预注册台账（data/state/prereg_ledger.jsonl、prereg/active.json、
prereg/trials.jsonl）。代码/配置变更默认拒绝；如确需提交，显式加 --git-all
（会触发预注册冻结校验，通常应当避免）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "data" / "state" / "preflight.json"


def _read_target_period(path: Path | None = None) -> int | None:
    path = Path(path or PREFLIGHT)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data["target"]["period"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="每日一条命令：run_daily + 台账 git 同步")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--points", default=None, help="一行 20 个点位")
    group.add_argument("--points-file", default=None, help="从文件读取点位")
    ap.add_argument("--n", type=int, default=60, help="主系统回测窗口")
    ap.add_argument("--no-backtest", action="store_true")
    ap.add_argument("--skip-main", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-git", action="store_true", help="不提交/推送")
    ap.add_argument("--no-push", action="store_true", help="只提交，不推送")
    ap.add_argument("--git-all", action="store_true",
                    help="允许提交台账之外的文件（不推荐，通常会触发冻结失效）")
    return ap


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    args = build_parser().parse_args(argv)
    py = sys.executable

    cmd = [py, "scripts/run_daily.py"]
    if args.points:
        cmd += ["--points", args.points]
    elif args.points_file:
        cmd += ["--points-file", args.points_file]
    cmd += ["--n", str(args.n)]
    if args.no_backtest:
        cmd.append("--no-backtest")
    if args.skip_main:
        cmd.append("--skip-main")
    if args.dry_run:
        cmd.append("--dry-run")

    print("▶ 每日流程", flush=True)
    rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
    if rc == 1:
        print("✗ 每日流程失败，跳过 git 同步", file=sys.stderr)
        return 1
    if args.dry_run or args.no_git:
        print("（dry-run / --no-git：跳过 git 同步）")
        return rc

    period = _read_target_period()
    if period is None:
        print("✗ 无法从 preflight.json 读取目标期号，跳过 git 同步", file=sys.stderr)
        return 1

    git_cmd = [py, "scripts/git_sync.py", "--period", str(period)]
    if not args.no_push:
        git_cmd.append("--push")
    if args.git_all:
        git_cmd.append("--all")
    print(f"\n▶ 台账 git 同步（{period}）", flush=True)
    grc = subprocess.run(git_cmd, cwd=str(ROOT)).returncode
    if grc == 1:
        print("✗ git 同步失败（本地提交可能已保留）", file=sys.stderr)
        return 1
    if grc == 2:
        print("台账无变更；流程完成。")
    return rc


if __name__ == "__main__":
    sys.exit(main())