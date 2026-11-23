# -*- coding: utf-8 -*-
"""试验登记（研究自由度）测试。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.trials import TrialRegistry, expected_max_z


def test_expected_max_z_monotonic():
    assert expected_max_z(1) == 0.0
    z11 = expected_max_z(11)
    z36 = expected_max_z(36)
    assert 1.0 < z11 < 2.2
    assert z11 < z36 < 3.0


def test_add_is_idempotent_and_summary(tmp_path: Path):
    reg = TrialRegistry(tmp_path / "trials.jsonl")
    reg.add("T1", "fam", "method", "one", result={"z": 1.2, "q": 0.4})
    reg.add("T2", "fam", "method", "two", result={"z": 0.3, "q": 0.8})
    reg.add("T1", "fam", "method", "duplicate")
    assert len(reg.load()) == 2
    s = reg.summary(alpha=0.05)
    assert s["total"] == 2
    f = s["families"]["fam"]
    assert f["N"] == 2
    assert f["observed_best_z"] == 1.2
    assert abs(f["bonferroni_alpha"] - 0.025) < 1e-12


def test_registration_split_before_after(tmp_path: Path):
    reg = TrialRegistry(tmp_path / "trials.jsonl")
    reg.add("A", "f", "method", "before", created_at="2026-01-01T00:00:00",
            result={"z": 1.0})
    reg.add("B", "f", "method", "after", created_at="2026-02-01T00:00:00",
            result={"z": 2.0})
    reg_path = tmp_path / "active.json"
    reg_path.write_text(json.dumps({"registration_id": "X",
                                    "created_at": "2026-01-15T00:00:00"}),
                        encoding="utf-8")
    r = reg.registration_summary(reg_path)
    assert r["trials_before_registration"] == 1
    assert r["trials_after_registration"] == 1
    assert r["after_ids"] == ["B"]
    assert r["clean"] is False
    assert r["expected_max_z"] == 0.0