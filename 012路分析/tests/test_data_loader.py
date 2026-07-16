import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.data_loader import DataLoader, KL8Draw


def test_parse_line_and_road(tmp_path):
    p = tmp_path / "h.txt"
    p.write_text(
        "date:2026-07-15,period:2026186,numbers:03-06-09-01-04-07-02-05-08-10-11-12-13-14-15-16-17-18-19-20\n",
        encoding="utf-8",
    )
    loader = DataLoader(history_file=p)
    loader.load()
    assert len(loader.history) == 1
    d = loader.history[0]
    assert d.period == "2026186"
    assert sum(d.road) == 20
    assert d.road[0] >= 3  # 03,06,09 at least
