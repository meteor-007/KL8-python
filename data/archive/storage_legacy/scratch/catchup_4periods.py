#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""断档4期依次回补：2026201→2026204（截断 kl8 防前瞻，按日写报告）。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

HISTORY = ROOT / "kl8_history_final.txt"
BACKUP = ROOT / "scratch" / "kl8_history_full_backup_catchup.txt"
REPORTS = ROOT / "reports"

# (history_max_draw, review_period, target, report_date YYYYMMDD)
STEPS = [
    ("2026200", "2026200", "2026201", "20260730"),
    ("2026201", "2026201", "2026202", "20260731"),
    ("2026202", "2026202", "2026203", "20260801"),
    ("2026203", "2026203", "2026204", "20260802"),
]


def parse_history(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("date:"):
            continue
        parts = dict(p.split(":", 1) for p in line.split(",") if ":" in p)
        nums = [int(x) for x in parts["numbers"].replace("-", " ").split()]
        rows.append(
            {
                "date": parts["date"],
                "period": parts["period"],
                "numbers": nums,
                "raw": line,
            }
        )
    return rows


def write_truncated(full_rows: list[dict], max_period: str) -> None:
    kept = [r for r in full_rows if int(r["period"]) <= int(max_period)]
    HISTORY.write_text("\n".join(r["raw"] for r in kept) + "\n", encoding="utf-8")
    print(f"[history] truncate <= {max_period}, n={len(kept)}, head={kept[0]['period']}")


def run(cmd: list[str], env: dict | None = None) -> int:
    print(f"[run] {' '.join(cmd)}")
    e = os.environ.copy()
    if env:
        e.update(env)
    p = subprocess.run(cmd, cwd=str(ROOT), env=e)
    return p.returncode


def review_period(period: str, actual: list[int], history_rows: list[dict]) -> dict:
    from learning.autonomous_learner import AutonomousLearner

    learner = AutonomousLearner()
    hist = [
        {"period": r["period"], "numbers": r["numbers"], "date": r["date"]}
        for r in history_rows
        if int(r["period"]) <= int(period)
    ]
    report = learner.on_new_result(period, actual, hist)
    out = ROOT / "reviews" / f"review_{period}.json"
    # learner may already persist; also dump loop summary
    summary_path = ROOT / "reviews" / f"catchup_loop_{period}.json"
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[review] {period} top5={report.get('review_summary', {})} "
        f"opt={report.get('optimization_decision')} -> {out.exists()}"
    )
    return report


def build_copyable(target: str, report_date: str) -> Path:
    state_path = ROOT / "cache" / "self_learning_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    snap = None
    for h in state.get("history", []):
        if str(h.get("target_issue")) == str(target):
            snap = h
            break
    if not snap:
        raise RuntimeError(f"no snapshot for target {target}")

    def fmt(nums):
        return " ".join(f"{int(n):02d}" for n in nums)

    # fallback: parse from markdown report if keys missing
    import re

    md = REPORTS / f"daily_analysis_report_{report_date}.md"
    text = md.read_text(encoding="utf-8") if md.exists() else ""

    def extract(label_patterns, n_expect=None):
        for pat in label_patterns:
            m = re.search(pat, text, re.S)
            if m:
                nums = re.findall(r"\d{1,2}", m.group(1) if m.lastindex else m.group(0))
                if nums:
                    return " ".join(f"{int(x):02d}" for x in nums[: n_expect or len(nums)])
        return ""

    # 当前 self_learning_state 字段：b3_final5=HE5, top5/12=Trinity, conf_top*=AI
    mapping = [
        ("HE5", ["b3_final5", "he5", "hidden_energy_5"],
         [r"最终推荐\s*\(5\s*码\)\s*[:：]\s*`([^`]+)`"]),
        ("Trinity5", ["trinity_top5", "top5"],
         [r"极秘\s*Top\s*5\s*[:：]\s*`([^`]+)`"]),
        ("Trinity12", ["trinity_top12", "top12"],
         [r"极秘\s*Top\s*12\s*[:：]\s*`([^`]+)`"]),
        ("AI5", ["conf_top5", "ai_top5"],
         [r"Top\s*5\s*置信度精选\s*[:：]\s*`([^`]+)`"]),
        ("AI12", ["conf_top12", "ai_top12"],
         [r"Top\s*12\s*综合拦截\s*[:：]\s*`([^`]+)`"]),
        ("Golden", ["golden_core", "golden"],
         [r"高频共振集群.*?`([^`]+)`"]),
        ("mRMR", ["mrmr_top12", "mrmr"],
         [r"mRMR\s*Top\s*12\s*[:：]\s*`([^`]+)`"]),
        ("纯净池高置信", ["pure_pool_top", "pure_pool_high", "pure_high"],
         [r"高置信定胆[^\n]*推荐\s*`([^`]+)`", r"纯净池号码\s*[:：]\s*`([^`]+)`"]),
        ("纯净池旧规则", ["pure_pool_old_rule", "pure_pool_old", "pure_old"],
         [r"旧规则高置信[^\n]*[:：]\s*`([^`]+)`"]),
        ("纯净池LR", ["pure_pool_lr", "pure_lr"],
         [r"LR定胆[^\n]*[:：]\s*`([^`]+)`"]),
        ("纯净池全量", ["pure_pool_all", "pure_all"],
         [r"纯净池全量[^\n]*[:：]\s*`([^`]+)`"]),
        ("爆发Top5", ["deep_picks", "burst_top5"],
         [r"爆发Top5[^\n]*推荐\s*`([^`]+)`"]),
        ("防守Top3", ["deep_kills", "defense_top3"],
         [r"防守Top3[^\n]*[:：]\s*`([^`]+)`"]),
        ("跨规则共识", ["deep_consensus", "consensus"],
         [r"跨规则共识[^\n]*推荐\s*`([^`]+)`"]),
    ]

    out_lines = [f"【目标期 {target} · 报告日 {report_date}】"]
    for label, keys, pats in mapping:
        vals = None
        for k in keys:
            if snap.get(k):
                vals = snap[k]
                break
        if vals:
            s = fmt(vals) if not isinstance(vals, str) else vals
        else:
            s = extract(pats)
        out_lines.append(f"{label:<16}{s}")

    # Also dump raw snap keys for panel builder
    meta = {
        "target": target,
        "report_date": report_date,
        "snap_keys": sorted(snap.keys()),
        "snap": {k: snap[k] for k in snap if k in (
            "he5", "hidden_energy_5", "top5", "top12", "trinity_top5", "trinity_top12",
            "ai_top5", "ai_top12", "golden_core", "golden", "mrmr_top12",
            "pure_pool_high", "pure_pool_old", "pure_pool_lr", "pure_pool_all",
            "burst_top5", "defense_top3", "deep_picks", "deep_kills", "deep_consensus",
            "env", "beacon_level", "kl_msg", "weights"
        )},
    }
    (ROOT / "scratch" / f"catchup_snap_{target}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    out = REPORTS / f"可复制推荐_{target}.txt"
    out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"[copyable] {out}")
    return out


def main() -> int:
    full_text = HISTORY.read_text(encoding="utf-8")
    BACKUP.write_text(full_text, encoding="utf-8")
    full_rows = parse_history(full_text)
    by_period = {r["period"]: r for r in full_rows}
    print(f"[backup] {BACKUP} n={len(full_rows)} latest={full_rows[0]['period']}")

    results = []
    try:
        for history_max, review_p, target, report_date in STEPS:
            print("\n" + "=" * 70)
            print(f" STEP target={target} review={review_p} history<={history_max} date={report_date}")
            print("=" * 70)

            write_truncated(full_rows, history_max)

            # 确保目标期跟随 data1 已进 Excel（断档回补常见缺口）
            run([sys.executable, "data_acquisition/process_hot_numbers.py",
                 "--target-period", target])
            cache = ROOT / "data_cache.json"
            if cache.exists():
                cache.unlink()

            # review draw period with actual from full backup
            actual = by_period[review_p]["numbers"]
            # history for learner: up to review period inclusive
            hist_for_review = [r for r in full_rows if int(r["period"]) <= int(review_p)]
            loop = review_period(review_p, actual, hist_for_review)

            # formats (incremental) — best effort
            run([sys.executable, "format/apply_formats.py"])

            # generate report as of report_date
            rc = run(
                [sys.executable, "pipeline/auto_generate_daily_report.py"],
                env={"KL8_REPORT_DATE": report_date},
            )
            if rc != 0:
                print(f"[ERROR] report gen failed rc={rc} for {target}")
                return rc

            md = REPORTS / f"daily_analysis_report_{report_date}.md"
            if not md.exists():
                # engine may have written today's date if env missed — find newest
                print(f"[WARN] missing {md.name}, listing reports...")
                return 2

            try:
                build_copyable(target, report_date)
            except Exception as e:
                print(f"[WARN] copyable build: {e}")

            results.append(
                {
                    "target": target,
                    "review": review_p,
                    "report_date": report_date,
                    "loop": loop.get("review_summary"),
                    "opt": loop.get("optimization_decision"),
                    "report": str(md),
                    "report_bytes": md.stat().st_size,
                }
            )
    finally:
        # always restore full history
        shutil.copy2(BACKUP, HISTORY)
        print(f"[restore] history -> {full_rows[0]['period']}")

    # final sync/validate on full data
    run([sys.executable, "utils/data_validator.py", "--auto-fix"])
    run([sys.executable, "format/apply_formats.py"])

    summary = ROOT / "scratch" / "catchup_4periods_summary.json"
    summary.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] summary -> {summary}")
    for r in results:
        print(f"  {r['report_date']} target={r['target']} review={r['review']} "
              f"hits={r['loop']} bytes={r['report_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
