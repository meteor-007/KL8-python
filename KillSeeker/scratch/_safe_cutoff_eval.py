"""评估保留号不同截断规模的命中率（历史预测 vs 开奖）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.data_loader import DataLoader  # noqa: E402

CUTS = [5, 8, 10, 12, 15, 20]
BASELINE = 0.25  # 20/80


def main() -> None:
    loader = DataLoader()
    loader.load()
    hist = {d.period: set(d.numbers) for d in loader.history}

    preds = []
    log = ROOT / "logs" / "kill_logs.jsonl"
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            preds.append(json.loads(line))

    stats = {c: {"hit": 0, "tot": 0, "n": 0} for c in CUTS}
    recent = []
    for p in preds:
        period = p.get("period")
        if period not in hist:
            continue
        safe = p.get("safe_numbers") or []
        if len(safe) < 5:
            continue
        actual = hist[period]
        row = {"period": period}
        for c in CUTS:
            top = safe[:c]
            h = len(set(top) & actual)
            stats[c]["hit"] += h
            stats[c]["tot"] += len(top)
            stats[c]["n"] += 1
            row[c] = (h, c)
        recent.append(row)

    print(f"样本期数: {stats[20]['n']}  |  随机基线保留命中率: {BASELINE:.0%}")
    print("-" * 64)
    for c in CUTS:
        hit, tot, n = stats[c]["hit"], stats[c]["tot"], stats[c]["n"]
        rate = hit / tot if tot else 0.0
        avg = hit / n if n else 0.0
        lift = (rate / BASELINE - 1) * 100
        print(
            f"Top{c:>2}: 命中率={rate:5.1%}  均命中={avg:.2f}/{c}  "
            f"vs随机 {lift:+.1f}%  (n={n})"
        )

    print("\n最近12期明细 (命中数/规模):")
    print(f"{'期号':<10} " + " ".join(f"{'T'+str(c):>7}" for c in CUTS))
    for row in recent[-12:]:
        cells = " ".join(f"{row[c][0]}/{c}".rjust(7) for c in CUTS)
        print(f"{row['period']:<10} {cells}")

    # 近10期对比 Top10 vs Top20
    last10 = recent[-10:]
    if last10:
        print("\n近10期汇总:")
        for c in (10, 12, 15, 20):
            h = sum(r[c][0] for r in last10)
            t = sum(r[c][1] for r in last10)
            print(f"  Top{c}: {h}/{t} = {h/t:.1%}")


if __name__ == "__main__":
    main()
