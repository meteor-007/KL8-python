# -*- coding: utf-8 -*-
"""数据完整性 + 条件功效报告测试。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.integrity_power_report import (bias_power, frequency_audit,
                                             missing_periods, period_continuity,
                                             power_table)


def test_period_continuity_detects_gaps():
    c = period_continuity({2026001, 2026002, 2026004, 2025001})
    assert c["2026"]["missing"] == [2026003]
    assert c["2025"]["missing_count"] == 0


def test_power_table_mde_and_monotonicity():
    p = power_table(3, 2, 300)
    assert abs(p["mde_lift_at_planned"] - 0.1083) < 0.002
    powers = [r["power_conditional"] for r in p["rows"]]
    assert powers == sorted(powers)
    assert 0.25 < next(r["power_conditional"] for r in p["rows"] if r["lift"] == 0.05) < 0.40
    assert next(r["required_periods_80pct"] for r in p["rows"] if r["lift"] == 0.05) > 1000


def test_bias_power_increases_with_sample_and_bias():
    small = bias_power(300, 0.05)
    large = bias_power(2123, 0.05)
    strong = bias_power(2123, 0.20)
    assert large["power"] > small["power"]
    assert strong["power"] > large["power"]
    assert small["zcrit_bonferroni"] > 3.0

def test_missing_periods_reports_gap_inside_points_range():
    history = {2025349, 2025350, 2025351, 2025352}
    points = {2025349, 2025350, 2025352}
    assert missing_periods(history, points) == [2025351]
    assert missing_periods(history, set()) == []


def test_frequency_audit_reports_counts_and_chi2():
    hist = {
        1: ("2026-01-01", frozenset(range(1, 21))),
        2: ("2026-01-02", frozenset(range(1, 21))),
    }
    audit = frequency_audit(hist)
    assert audit["periods"] == 2
    assert audit["expected"] == 0.5
    assert audit["chi2"] >= 0
    assert len(audit["top"]) == 8
