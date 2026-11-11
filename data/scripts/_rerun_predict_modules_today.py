# -*- coding: utf-8 -*-
"""一键重跑当期预测相关模块（UTF-8，按退出码判定成败）。"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

sys.path.insert(0, str(ROOT))
from backend.utils.paths import find_module_script  # noqa: E402


def _job(label: str, script_name: str, *args: str, lane: str = "daily") -> tuple:
    path = find_module_script(script_name)
    return (label, [sys.executable, path, *args], lane)


def _mod(label: str, module: str, *args: str, lane: str = "daily") -> tuple:
    return (label, [sys.executable, "-m", module, *args], lane)


# (显示名, argv, lane)  lane=daily|research；research 需 --with-research
JOBS = [
    ("热号统计 hot_excel", [sys.executable, str(ROOT / "backend" / "data_acquisition" / "generate_hot_excel.py")], "daily"),
    ("热号处理 process_hot", [sys.executable, str(ROOT / "backend" / "data_acquisition" / "process_hot_numbers.py")], "daily"),
    _job("未开点位反弹 suppression", "run_suppression_daily.py", "30"),
    _job("点位+遗漏 omission", "run_omission_daily.py"),
    _job("16期中热 sixteen", "run_sixteen_daily.py", "30"),
    _mod("全合一驾驶舱 cockpit", "backend.modules.build_unified_master_excel"),
    _job("顺口溜 jingle", "run_jingle_daily.py", "30"),
    _job("定胆选2 pick2", "run_pick2_daily.py", "30"),
    _job("数据源1×2 datasource", "run_datasource_daily.py"),
    _mod("质合尾数012 prime", "backend.modules.prime_composite.run_daily"),
    _mod("心理博弈 psych", "backend.modules.psychological_game.run_daily"),
    _mod("多维共振 multi_resonance", "backend.modules.multi_resonance.run_daily"),
    _mod("三高×点位 tri_high", "backend.modules.tri_high.tri_high_engine"),
    _job("遗传算法 genetic", "run_genetic_daily.py", lane="research"),
    _job("线性代数 LA", "run_linear_algebra_daily.py", lane="research"),
    _job("DTW", "run_dtw_daily.py", lane="research"),
    _job("Transformer", "run_transformer_daily.py", lane="research"),
    _job("MatrixProfile", "run_matrix_profile_daily.py", lane="research"),
    _job("TDA", "run_tda_daily.py", lane="research"),
    _job("随机森林 RF", "run_random_forest_daily.py", lane="research"),
    _mod("统一决策脑 brain", "backend.modules.unified_brain.run_daily", lane="research"),
    _mod("三维交集共识 straddle", "backend.modules.consensus_straddle.run_daily"),
    _mod("一胆拖三盾 spear", "backend.modules.spear_shield_portfolio.run_daily"),
    _mod("点位012压缩 compressor", "backend.modules.point_road_compressor.run_daily"),
    _job("残差改错 error_correction", "run_error_correction_daily.py"),
    _job("终审汇总 aggregation", "run_aggregation_daily.py", "--force"),
]


def run_one(name: str, argv: list[str], timeout: int = 600) -> dict:
    t0 = time.time()
    print(f"\n[{name}] START {' '.join(argv)}", flush=True)
    try:
        p = subprocess.run(
            argv,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )
        elapsed = time.time() - t0
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        tail = "\n".join(out.strip().splitlines()[-8:])
        ok = p.returncode == 0
        print(f"[{name}] {'OK' if ok else 'FAIL'} rc={p.returncode} {elapsed:.1f}s", flush=True)
        if tail:
            for line in tail.splitlines():
                try:
                    print(f"  | {line}", flush=True)
                except UnicodeEncodeError:
                    print("  | " + line.encode(sys.stdout.encoding or "utf-8", "replace").decode(sys.stdout.encoding or "utf-8", "replace"), flush=True)
        return {"name": name, "ok": ok, "rc": p.returncode, "sec": round(elapsed, 1), "tail": tail}
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        print(f"[{name}] TIMEOUT {elapsed:.1f}s", flush=True)
        return {"name": name, "ok": False, "rc": -9, "sec": round(elapsed, 1), "tail": "TIMEOUT"}
    except FileNotFoundError as e:
        print(f"[{name}] MISSING {e}", flush=True)
        return {"name": name, "ok": False, "rc": -2, "sec": 0.0, "tail": str(e)}


def main() -> int:
    import argparse
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="一键重跑当期预测模块")
    parser.add_argument(
        "--with-research",
        action="store_true",
        help="同时跑 research 舱（genetic/dtw/.../brain）；默认跳过以减噪",
    )
    args = parser.parse_args()

    jobs = [j for j in JOBS if j[2] == "daily" or args.with_research]
    print(f"=== 预测模块重跑开始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"ROOT={ROOT} 共 {len(jobs)} 项 (research={'ON' if args.with_research else 'OFF'})")
    results = []
    for name, argv, _lane in jobs:
        # skip missing entry scripts
        script = None
        if len(argv) >= 2 and argv[1].endswith(".py") and not argv[1].startswith("-"):
            script = ROOT / argv[1]
        if script is not None and not script.exists():
            # try alternate paths for hot excel helpers
            alt = ROOT / "backend" / "data_acquisition" / script.name
            if alt.exists():
                argv = [argv[0], str(alt)] + argv[2:]
            else:
                results.append({"name": name, "ok": False, "rc": -2, "sec": 0.0, "tail": f"missing {script}"})
                print(f"[{name}] SKIP missing {script}")
                continue
        results.append(run_one(name, argv))

    # 统一对账快照（采集各模块产物，不重算引擎）
    try:
        print("\n[unified_audit snapshot] START", flush=True)
        from backend.modules.unified_audit.run_daily import run_snapshot
        snap = run_snapshot()
        print(
            f"[unified_audit snapshot] {snap.get('status')} target={snap.get('target_period')} "
            f"report={snap.get('report')}",
            flush=True,
        )
        results.append({
            "name": "unified_audit snapshot",
            "ok": snap.get("status") == "ok",
            "rc": 0 if snap.get("status") == "ok" else 1,
            "sec": 0.0,
            "tail": str(snap.get("message") or snap.get("target_period") or ""),
        })
    except Exception as e:
        print(f"[unified_audit snapshot] FAIL {e}", flush=True)
        results.append({
            "name": "unified_audit snapshot",
            "ok": False,
            "rc": 1,
            "sec": 0.0,
            "tail": str(e),
        })

    ok_n = sum(1 for r in results if r["ok"])
    print("\n=== 汇总 ===")
    print(f"成功 {ok_n}/{len(results)}")
    fails = [r for r in results if not r["ok"]]
    if fails:
        print("失败:")
        for r in fails:
            print(f"  - {r['name']}: rc={r['rc']} ({r['sec']}s)")
    log = ROOT / "storage" / "logs" / f"rerun_predict_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "\n".join(
            [
                f"{'OK' if r['ok'] else 'FAIL'}\t{r['name']}\trc={r['rc']}\t{r['sec']}s\t"
                f"{str(r.get('tail') or '')[:200]}"
                for r in results
            ]
        ),
        encoding="utf-8",
    )
    print(f"日志: {log}")
    return 0 if ok_n == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
