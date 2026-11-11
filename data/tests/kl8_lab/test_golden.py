# -*- coding: utf-8 -*-
"""§10.3 黄金文件：固定 seed + 固定输入 → 报告文本逐字节比对。

做法：在**合成档案**（固定 seed 生成，不依赖真实数据）上跑完整分析链路，
渲染 Markdown，把**易变字段**（数据新鲜度——依赖运行当天日期）替换为占位符后，
与 `tests/golden/report_<目标期>.md` 逐行比对。

黄金文件由本文件生成并纳入版本管理：

    python tests/test_golden.py --update

**不做**「预测准不准」的断言——那会把测试变成对未来的赌博（§10.4）。
"""
from __future__ import annotations

import argparse
import random
import re
import sys
import tempfile
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest                                                   # noqa: E402

from backend.core.kl8_lab import cli as kl8_main                # noqa: E402
from backend.core.kl8_lab import points_input, report, source                    # noqa: E402
from backend.core.kl8_lab.config import load_config                              # noqa: E402
from backend.core.kl8_lab.data_io import (Draw, format_numbers_line,              # noqa: E402
                         format_points_line)
from backend.core.kl8_lab.points import expand                                   # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
SEED = 42
N_DRAWS = 150
CANONICAL_POINTS = (4, 10, 12, 14, 16, 20, 22, 27, 30, 38, 39, 40,
                    54, 59, 62, 65, 70, 74, 75, 80)

CONFIG_YAML = """\
data:
  python_project:
    enabled: true
    dir: "shared"
    points_file: "daily_points.txt"
    history_file: "kl8_history_final.txt"
    mode: "read_only"
  upload_dir: "data/uploads"
  seed_dir: "data/seed"
  cache_dir: "data/cache"
  state_dir: "data/state"
  log_dir: "data/logs"
fetch:
  enabled: false
report:
  out_dir: "output"
reproducibility:
  seed: 42
"""

# 易变字段：数据新鲜度依赖「运行当天」的日期，逐字节比对前先归一
_STALENESS_RE = re.compile(r"^- \*\*数据新鲜度\*\*：.*$", re.MULTILINE)


def normalize(md: str) -> str:
    return _STALENESS_RE.sub("- **数据新鲜度**：<STALENESS>", md)


# ── 固定输入 ─────────────────────────────────────────────────

def _target_period() -> int:
    return 2025000 + N_DRAWS


def _synthetic_draws() -> list[Draw]:
    """固定 seed 生成的合成开奖（升序期内 20 码）。"""
    rng = random.Random(SEED)
    d0 = _date(2025, 1, 1)
    return [Draw(period=2025001 + i, date=d0 + timedelta(days=i),
                 numbers=tuple(sorted(rng.sample(range(1, 81), 20))))
            for i in range(N_DRAWS)]


def _build_sandbox(root: Path):
    """把固定档案写进沙箱，返回 (cfg, dataset, 目标期)。"""
    cfg_file = root / "config.yaml"
    cfg_file.write_text(CONFIG_YAML, encoding="utf-8")
    cfg = load_config(path=str(cfg_file), root=root)

    shared = cfg.shared_dir
    shared.mkdir(parents=True, exist_ok=True)
    target = _target_period()
    (shared / "kl8_history_final.txt").write_text(
        "".join(format_numbers_line(d.date, d.period, list(d.numbers)) + "\n"
                for d in _synthetic_draws()),
        encoding="utf-8", newline="\r\n")
    (shared / "daily_points.txt").write_text(
        format_points_line(_date(2025, 1, 1) + timedelta(days=N_DRAWS - 1),
                           target, list(CANONICAL_POINTS)) + "\n",
        encoding="utf-8", newline="\r\n")

    ds = source.load_dataset(cfg, allow_fetch=False)
    return cfg, ds, target


def render_golden_text() -> str:
    root = Path(tempfile.mkdtemp(prefix="kl8_golden_"))
    cfg, ds, target = _build_sandbox(root)
    entry = ds.points[target]
    info = points_input.TargetInfo(period=target, date=entry.date,
                                   already_input=True,
                                   existing_points=entry.points)
    ctx = kl8_main._analyze_target(cfg, ds, entry, info)
    return normalize(report.render_markdown(ctx))


def _golden_path() -> Path:
    return GOLDEN_DIR / f"report_{_target_period()}.md"


# ── 用例 ──────────────────────────────────────────────────────

def test_report_golden_is_byte_identical():
    """固定 seed + 固定输入 → 报告与黄金文件逐字节相同（§10.3）。"""
    path = _golden_path()
    if not path.exists():
        pytest.skip(f"黄金文件缺失：{path}（用 python tests/test_golden.py --update 生成）")

    actual = render_golden_text()
    expected = path.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert actual == expected, (
        "报告与黄金文件不一致。若是**有意的**输出变更，请审查 diff 后运行 "
        "`python tests/test_golden.py --update` 更新黄金文件。")


def test_golden_text_is_deterministic():
    """同一输入渲染两次必须完全一致——否则比对本身不可靠（§3.7 可复现）。"""
    assert render_golden_text() == render_golden_text()


def test_golden_is_compliant():
    """黄金文本同样要过 §11.5 合规扫描。"""
    report.assert_compliant(render_golden_text())


def _main() -> int:
    ap = argparse.ArgumentParser(description="生成/更新黄金文件")
    ap.add_argument("--update", action="store_true", help="写入 tests/golden/")
    args = ap.parse_args()

    text = render_golden_text()
    if not args.update:
        print(f"（未写入）渲染 {len(text)} 字符；加 --update 写入 {_golden_path()}")
        return 0

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    _golden_path().write_text(text, encoding="utf-8", newline="\r\n")
    print(f"黄金文件已写入：{_golden_path()}（{len(text)} 字符）")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
