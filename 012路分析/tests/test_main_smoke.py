import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_backtest_exits_zero():
    hist = ROOT.parent / "data" / "kl8_history_final.txt"
    if not hist.exists():
        import pytest
        pytest.skip("no history file")
    r = subprocess.run(
        [sys.executable, "main.py", "--backtest", "5", "--no-ml"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert r.returncode == 0, r.stderr[-500:]
