# -*- coding: utf-8 -*-
"""数据一致性校验测试。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from tools.data_sync import (apply_copy, apply_sorted, compare, load_history,
                             load_points, summarize)


def _nums(start: int) -> list[int]:
    return list(range(start, start + 20))


def _hist_line(period: int, nums: list[int], date: str = "2026-01-01") -> str:
    return (f"date:{date},period:{period:07d},numbers:"
            + "-".join(f"{n:02d}" for n in nums))


def _pts_line(period: int, nums: list[int], date: str = "2026-01-01") -> str:
    return (f"date:{date},period:{period:07d},points:"
            + " ".join(f"{n:02d}" for n in nums))


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_history_order_insensitive(tmp_path: Path):
    src = tmp_path / "src.txt"
    tgt = tmp_path / "tgt.txt"
    rows = {2026001: _nums(1), 2026002: _nums(2), 2026003: _nums(3)}
    _write(src, [_hist_line(p, n) for p, n in sorted(rows.items(), reverse=True)])
    _write(tgt, [_hist_line(p, n) for p, n in sorted(rows.items())])
    r = compare("history", src, tgt)
    assert r.ok
    assert r.source_latest == 2026003
    assert r.target_latest == 2026003


def test_history_missing_extra_mismatch(tmp_path: Path):
    src = tmp_path / "src.txt"
    tgt = tmp_path / "tgt.txt"
    _write(src, [_hist_line(2026001, _nums(1)), _hist_line(2026002, _nums(2)),
                 _hist_line(2026003, _nums(3)), _hist_line(2026004, _nums(4))])
    _write(tgt, [_hist_line(2026001, _nums(1)), _hist_line(2026002, _nums(2)),
                 _hist_line(2026004, _nums(50)), _hist_line(2026005, _nums(5))])
    r = compare("history", src, tgt)
    assert not r.ok
    assert r.missing == [2026003]
    assert r.extra == [2026005]
    assert r.mismatched == [2026004]


def test_points_compare(tmp_path: Path):
    src = tmp_path / "src.txt"
    tgt = tmp_path / "tgt.txt"
    _write(src, [_pts_line(2026001, _nums(1))])
    _write(tgt, [_pts_line(2026001, _nums(1))])
    assert compare("points", src, tgt).ok
    _write(tgt, [_pts_line(2026001, _nums(2))])
    assert compare("points", src, tgt).mismatched == [2026001]


def test_summarize(tmp_path: Path):
    path = tmp_path / "h.txt"
    _write(path, [_hist_line(2026001, _nums(1)), _hist_line(2026003, _nums(3))])
    s = summarize(path)
    assert s["count"] == 2
    assert s["latest"] == 2026003
    assert s["oldest"] == 2026001


def test_invalid_rows_are_counted(tmp_path: Path):
    from tools.data_sync import scan_invalid
    path = tmp_path / "bad.txt"
    _write(path, [_hist_line(2026001, _nums(1)),
                  "date:2026-01-02,period:2026002,numbers:01-02-03"])
    bad = scan_invalid(path, "history")
    assert len(bad) == 1 and bad[0]["period"] == 2026002
    assert len(load_history(path)) == 1


def test_apply_copy_backup_and_same_file(tmp_path: Path):
    src = tmp_path / "src.txt"
    tgt = tmp_path / "tgt.txt"
    src.write_text("new" + chr(10), encoding="utf-8")
    tgt.write_text("old" + chr(10), encoding="utf-8")
    apply_copy(src, tgt)
    assert tgt.read_text(encoding="utf-8").startswith("new")
    assert any(p.name.startswith("tgt.txt.") and p.name.endswith(".bak")
               for p in tmp_path.iterdir())
    with pytest.raises(ValueError):
        apply_copy(src, src)


def test_apply_sorted_orders_and_backs_up(tmp_path: Path):
    src = tmp_path / "src.txt"
    tgt = tmp_path / "tgt.txt"
    _write(src, [_hist_line(2026002, _nums(2)), _hist_line(2026003, _nums(3)),
                 _hist_line(2026001, _nums(1))])
    tgt.write_text("old" + chr(10), encoding="utf-8")
    assert apply_sorted(src, tgt, "ascending") is True
    text = tgt.read_text(encoding="utf-8")
    periods = [int(line.split("period:")[1].split(",")[0])
               for line in text.splitlines()]
    assert periods == [2026001, 2026002, 2026003]
    assert "\r\n" in tgt.read_bytes().decode("utf-8")
    assert any(p.name.startswith("tgt.txt.") and p.name.endswith(".bak")
               for p in tmp_path.iterdir())
    apply_sorted(src, tgt, "descending")
    periods = [int(line.split("period:")[1].split(",")[0])
               for line in tgt.read_text(encoding="utf-8").splitlines()]
    assert periods == [2026003, 2026002, 2026001]


def test_apply_sorted_points_and_invalid_source(tmp_path: Path):
    src = tmp_path / "src.txt"
    tgt = tmp_path / "tgt.txt"
    _write(src, [_pts_line(2026002, _nums(2)), _pts_line(2026001, _nums(1))])
    apply_sorted(src, tgt, "ascending", kind="points")
    assert [int(line.split("period:")[1].split(",")[0])
            for line in tgt.read_text(encoding="utf-8").splitlines()] == [2026001, 2026002]
    before = tgt.read_text(encoding="utf-8")
    _write(src, [_hist_line(2026001, _nums(1)), "date:2026-01-02,period:2026002,numbers:01-02-03"])
    with pytest.raises(ValueError, match="非法"):
        apply_sorted(src, tgt, "ascending")
    assert tgt.read_text(encoding="utf-8") == before


def test_apply_sorted_normalizes_number_order(tmp_path: Path):
    src = tmp_path / "src.txt"
    tgt = tmp_path / "tgt.txt"
    unsorted = list(range(20, 0, -1))
    _write(src, [_hist_line(2026001, unsorted)])
    assert apply_sorted(src, tgt, "descending", backup=False) is False
    body = tgt.read_text(encoding="utf-8").strip().split("numbers:")[1]
    assert body == "-".join(f"{n:02d}" for n in range(1, 21))


def test_apply_sorted_preserve_delegates(tmp_path: Path):
    src = tmp_path / "src.txt"
    tgt = tmp_path / "tgt.txt"
    src.write_text("a" + chr(10), encoding="utf-8")
    tgt.write_text("b" + chr(10), encoding="utf-8")
    assert apply_sorted(src, tgt, "preserve") is True
    assert tgt.read_text(encoding="utf-8") == "a" + chr(10)


def test_data_sync_cli_exit_codes():
    import json
    import subprocess
    out = subprocess.run([sys.executable, "scripts/data_sync.py", "--json"],
                         cwd=str(ROOT), capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    assert out.returncode in (0, 2)
    payload = json.loads(out.stdout)
    assert (out.returncode == 0) == all(c["ok"] for c in payload["comparisons"])
    frozen = ROOT.parent / "Python-Project" / "data" / "storage" / "raw" / "kl8_history_final.txt"
    blocked = subprocess.run(
        [sys.executable, "scripts/data_sync.py", "--apply", "--kind", "history",
         "--target", str(frozen)], cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    assert blocked.returncode == 1 and "拒绝" in (blocked.stderr + blocked.stdout)
    no_target = subprocess.run(
        [sys.executable, "scripts/data_sync.py", "--apply"], cwd=str(ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert no_target.returncode == 1 and "--target" in (no_target.stderr + no_target.stdout)
