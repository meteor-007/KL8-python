# -*- coding: utf-8 -*-
"""研究引擎桥接测试（不加载 C/torch）。"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json

from tools.research_bridge import (ResearchConfig, _a_top5,
                                   _assert_period, _top_scores,
                                   default_target_period, history_for_period,
                                   latest_history_period,
                                   points_for_period, render_markdown,
                                   summarize_result)


def _h(period: int, nums: list[int]) -> str:
    return (f"date:2026-01-01,period:{period:07d},numbers:"
            + "-".join(f"{n:02d}" for n in nums))


def _p(period: int, nums: list[int]) -> str:
    return (f"date:2026-01-01,period:{period:07d},points:"
            + " ".join(f"{n:02d}" for n in nums))


def test_history_trim_and_points(tmp_path: Path):
    hist = tmp_path / "h.txt"
    hist.write_text("\n".join([_h(2026003, list(range(1, 21))),
                               _h(2026002, list(range(2, 22))),
                               _h(2026001, list(range(3, 23)))]) + "\n",
                    encoding="utf-8")
    assert latest_history_period(hist) == 2026003
    trimmed = history_for_period(hist, 2026003, tmp_path)
    text = trimmed.read_text(encoding="utf-8")
    assert "2026003" not in text and "2026002" in text and "2026001" in text
    full = history_for_period(hist, 2026004, tmp_path)
    assert full == hist

    pts = tmp_path / "p.txt"
    pts.write_text(_p(2026003, list(range(1, 21))) + "\n", encoding="utf-8")
    assert points_for_period(pts, 2026003) == list(range(1, 21))
    assert points_for_period(pts, 2026004) is None


def test_summarize_and_markdown():
    ens = SimpleNamespace(
        gold_pool=(3,), main_pool=(1, 2, 3, 4, 5),
        shrinkage_pool_30=tuple(range(1, 31)),
        full_order=tuple(range(1, 81)),
        scores=np.arange(80, 0, -1),
    )
    sh = SimpleNamespace(final_tickets_count=20, total_cost_yuan=40,
                         hit5_guarantee_prob=0.1, hit4_or_better_prob=0.3,
                         hit3_or_better_prob=0.6, expected_prize_per_day=0,
                         expected_prize_per_draw=2.5, roi_percentage=-50.0)
    rv = SimpleNamespace(target_period=2026301, actual_period=2026302,
                         gold_hits=1, gold_total=1, main_hits=2, main_total=5,
                         top20_hits=5, top20_total=20, pool30_hits=7,
                         pool30_total=30, ranking_auc=0.52)
    result = SimpleNamespace(target_period=2026302, ensemble=ens,
                             comparison_ensemble=None, fusion_mode="borda",
                             comparison_fusion_mode=None, shrinkage=sh,
                             review=rv, warnings=("w1",), elapsed_seconds=1.2)
    s = summarize_result(result)
    assert s["period"] == 2026302
    assert s["borda"]["main_pool"] == [1, 2, 3, 4, 5]
    assert s["borda"]["scores_top10"] == list(range(1, 11))
    assert s["review"]["ranking_auc"] == 0.52
    cfg = ResearchConfig(engine_root=ROOT, output_dir=ROOT,
                         history_path=ROOT / "h.txt", points_path=ROOT / "p.txt")
    md = render_markdown(s, cfg, [1, 2, 3, 4, 5])
    assert "不构成投注建议" in md
    assert "30 码" in md and "AUC" in md


def test_top_scores_empty():
    assert _top_scores(None) == []
    assert _top_scores([0.1, 0.9, 0.5], 2) == [2, 3]


def test_default_target_period_cross_year(tmp_path: Path):
    hist = tmp_path / "h.txt"
    line = _h(2026351, list(range(1, 21))).replace("2026-01-01", "2026-12-31")
    hist.write_text(line + chr(10), encoding="utf-8")
    assert default_target_period(hist) == 2027001


def test_research_cli_rejects_invalid_points():
    import subprocess
    cmd = [sys.executable, "scripts/research_compare.py",
           "--points", " ".join(f"{i:02d}" for i in range(1, 20))]
    out = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    assert out.returncode == 1
    assert "校验失败" in (out.stderr + out.stdout)


def test_assert_period_abort():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        _assert_period(2027001, 2026352)


def test_a_top5_ledger_then_report(tmp_path: Path):
    hist = tmp_path / "h.txt"
    hist.write_text(_h(2026001, list(range(1, 21))) + chr(10), encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({
        "model": "main", "period": 2026001, "core": [1, 2, 3, 4, 5],
        "locked_at": "2026-01-01T10:00:00"}) + chr(10), encoding="utf-8")
    core, source = _a_top5(2026001, hist, snapshot_path=tmp_path / "none.json",
                           ledger_path=ledger, output_root=tmp_path / "out")
    assert core == [1, 2, 3, 4, 5] and source == "ledger"

    ledger.write_text("", encoding="utf-8")
    report = tmp_path / "out" / "2026-01-01" / "daily_report.md"
    report.parent.mkdir(parents=True)
    lines = ["### 6.1 五码核心", "| 号 | 场域 | 理由 |", "|---|---|---|"]
    for n in (7, 8, 9, 10, 11):
        lines.append(f"| **{n:02d}** | 01-10 | x |")
    report.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    core, source = _a_top5(2026001, hist, snapshot_path=tmp_path / "none.json",
                           ledger_path=ledger, output_root=tmp_path / "out")
    assert core == [7, 8, 9, 10, 11] and source == "daily_report"
