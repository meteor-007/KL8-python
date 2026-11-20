# -*- coding: utf-8 -*-
"""daily_all 包装器测试（不实际跑流水线）。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "daily_all", ROOT / "scripts" / "daily_all.py")
daily_all = importlib.util.module_from_spec(spec)
sys.modules["daily_all"] = daily_all
spec.loader.exec_module(daily_all)


def test_read_target_period(tmp_path: Path):
    p = tmp_path / "preflight.json"
    p.write_text(json.dumps({"target": {"period": 2026301}}), encoding="utf-8")
    assert daily_all._read_target_period(p) == 2026301


def test_read_target_period_missing(tmp_path: Path):
    assert daily_all._read_target_period(tmp_path / "none.json") is None


def test_read_target_period_invalid(tmp_path: Path):
    p = tmp_path / "preflight.json"
    p.write_text("not json", encoding="utf-8")
    assert daily_all._read_target_period(p) is None


def test_parser_defaults():
    args = daily_all.build_parser().parse_args(["--points", "01 02"])
    assert args.n == 60
    assert args.dry_run is False
    assert args.no_git is False
    assert args.git_all is False
