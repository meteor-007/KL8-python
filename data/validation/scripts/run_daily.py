# -*- coding: utf-8 -*-
"""每日一键运行：前置检查 → 生成当期引擎 → 融合研报 → 主系统 → 模块明细。

用法：
    python scripts/run_daily.py --points "07 08 13 ..."
    python scripts/run_daily.py --points-file today.txt
    python scripts/run_daily.py --dry-run          # 只检查数据与图表，不写档案、不预测

期号、日期、图表文件名、回测截止期全部自动识别，不需要手工修改。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "data/state/preflight.json"


def run_step(name: str, cmd: list[str], log_path: Path) -> tuple[int, float]:
    t0 = time.time()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write("$ " + " ".join(cmd) + "\n\n")
        fh.flush()
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env,
                              stdout=fh, stderr=subprocess.STDOUT)
    elapsed = time.time() - t0
    status = "OK" if proc.returncode in (0, 2) else "FAIL"
    print(f"  [{status}] {name}  ({elapsed:.1f}s)  日志: {log_path.relative_to(ROOT)}", flush=True)
    return proc.returncode, elapsed


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", default=None)
    ap.add_argument("--points-file", default=None)
    ap.add_argument("--n", type=int, default=60, help="主系统回测窗口")
    ap.add_argument("--no-backtest", action="store_true")
    ap.add_argument("--skip-main", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    py = sys.executable
    pf_cmd = [py, "scripts/daily_preflight.py"]
    if args.points:
        pf_cmd += ["--points", args.points]
    elif args.points_file:
        pf_cmd += ["--points-file", args.points_file]
    if args.dry_run:
        pf_cmd.append("--dry-run")

    print("▶ 步骤 1/4：前置检查", flush=True)
    t0 = time.time()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.run(pf_cmd, cwd=str(ROOT), env=env)
    if proc.returncode == 1:
        print("✗ 前置检查失败，流水线终止。", file=sys.stderr)
        return 1
    if not PREFLIGHT.exists():
        print("✗ 未生成 preflight.json", file=sys.stderr)
        return 1

    pf = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    target = pf["target"]
    period = int(target["period"])
    out_dir = ROOT / "output" / target["date"].replace("-", "")
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run or not pf.get("points", {}).get("list"):
        print("\n（dry-run 或未提供点位：不执行预测）")
        return 2 if pf.get("warnings") else 0

    manifest = {"target": target, "steps": [], "warnings": pf.get("warnings", [])}

    print("\n▶ 步骤 2/4：生成当期引擎")
    rc, sec = run_step("生成引擎", [py, "scripts/make_fusion_daily.py"],
                       out_dir / "logs" / "make_engine.log")
    manifest["steps"].append({"step": "make_engine", "rc": rc, "sec": round(sec, 1)})
    if rc not in (0, 2):
        return 1

    engine = ROOT / "scripts" / f"fusion_engine_{period}.py"
    if not engine.exists():
        print(f"✗ 未生成 {engine}", file=sys.stderr)
        return 1

    print("\n▶ 步骤 3/4：融合研报")
    rc, sec = run_step("融合研报", [py, str(engine)],
                       out_dir / "logs" / "fusion_engine.log")
    manifest["steps"].append({"step": "fusion_engine", "rc": rc, "sec": round(sec, 1)})
    if rc not in (0, 2):
        return 1

    print("\n▶ 步骤 4/4：主系统与模块明细")
    if not args.skip_main:
        cmd = [py, "main.py", "analyze", "--period", str(period), "--n", str(args.n)]
        if args.no_backtest:
            cmd.append("--no-backtest")
        rc, sec = run_step("主系统分析", cmd, out_dir / "logs" / "main_analyze.log")
        manifest["steps"].append({"step": "main_analyze", "rc": rc, "sec": round(sec, 1)})

    rc, sec = run_step("模块明细与复盘",
                       [py, "scripts/dump_module_details.py",
                        "--period", str(period),
                        "--prev", str(pf["latest_draw"]["period"]),
                        "--out-dir", str(out_dir)],
                       out_dir / "logs" / "module_details.log")
    manifest["steps"].append({"step": "module_details", "rc": rc, "sec": round(sec, 1)})

    # 预注册锁定（存在活动登记且已到起始期时；失败不阻断已生成的产物）
    prereg_path = ROOT / "prereg" / "active.json"
    if prereg_path.exists():
        try:
            reg = json.loads(prereg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reg = {}
        if reg.get("status") == "active" and period >= int(reg.get("start_period", 0)):
            lock_models = ["fusion"] if args.skip_main else ["main", "fusion"]
            lock_cmd = [py, "scripts/prereg.py", "lock"]
            for m in lock_models:
                lock_cmd += ["--model", m]
            rc, sec = run_step("预注册锁定", lock_cmd,
                               out_dir / "logs" / "prereg_lock.log")
            manifest["steps"].append(
                {"step": "prereg_lock", "rc": rc, "sec": round(sec, 1)})

    manifest["elapsed_sec"] = round(time.time() - t0, 1)
    manifest["outputs"] = sorted(p.name for p in out_dir.iterdir() if p.is_file())
    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n完成：{period} 期，产物目录 {out_dir.relative_to(ROOT)}")
    for name in manifest["outputs"]:
        print("  -", name)
    return 2 if pf.get("warnings") else 0


if __name__ == "__main__":
    sys.exit(main())