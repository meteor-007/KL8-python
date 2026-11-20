# -*- coding: utf-8 -*-
"""校准 / 覆盖 / 报告协议工具测试。"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calibration import brier, log_loss, summary
from tools.coverage import summarize as cover_summary
from tools.report_audit import check_text


def test_calibration_perfect_and_baseline():
    assert brier([(1.0, 1), (0.0, 0)]) == pytest.approx(0.0)
    assert log_loss([(1.0, 1), (0.0, 0)]) < 1e-6
    base = summary([(0.25, 1), (0.25, 0)])
    assert base["brier_baseline"] == pytest.approx(0.1875)
    assert base["brier"] == pytest.approx(0.3125)  # 小样本方差不等于理论基线


def test_calibration_rejects_invalid():
    with pytest.raises(ValueError):
        brier([(1.5, 1)])
    with pytest.raises(ValueError):
        brier([(0.3, 2)])


def test_coverage_balanced_zero_variance():
    res = cover_summary(16, 5, 80)
    assert res["expected_hits"] == pytest.approx(20.0)
    assert res["appearances_min"] == 1
    assert res["appearances_max"] == 1
    assert res["variance"] == pytest.approx(0.0, abs=1e-12)
    for t in res["tickets"]:
        assert len(t) == 5 and len(set(t)) == 5


def test_coverage_reduces_variance():
    res = cover_summary(8, 5, 80)
    assert res["variance"] < res["independent_variance"]
    assert 0 < res["variance_reduction"] < 1


def test_report_audit_fields():
    text = ("lift=1.02，95%CI [0.9,1.1]，p=0.4，T=60，"
            "MDE=+10%，随机基准 25%，不构成投注建议。")
    assert check_text(text) == []
    missing = check_text("lift=1.02，不构成投注建议。")
    assert "ci" in missing and "p_value" in missing and "mde" in missing