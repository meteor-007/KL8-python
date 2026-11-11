# -*- coding: utf-8 -*-
"""全项目共享 pytest fixture（§3.1 / §10.1）。

只提供共享基础设施，不隐藏被测行为：
  · make_draw / make_history —— 用真实 `Draw` 构造确定性历史（最新在前）
  · cfg                     —— 项目根目录 config.yaml 加载出的真实 Config
  · sandbox                 —— tmp_path 内的可写环境（沙箱 cfg + 档案写入助手）
  · write_file              —— 字节级写文件（显式控制换行/BOM，供 data_io 测试）
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:                     # 支持 `pytest` 与 `python -m pytest`
    sys.path.insert(0, str(ROOT))

from backend.core.kl8_lab.config import Config, load_config                          # noqa: E402
from backend.core.kl8_lab.data_io import (Draw, format_numbers_line,                 # noqa: E402
                         format_points_line, sort_draws)

# §2.1 规格示例点位：20 个，拓展后 50 个唯一号（40–58 区间内）
CANONICAL_POINTS: tuple[int, ...] = (
    4, 10, 12, 14, 16, 20, 22, 27, 30, 38, 39, 40,
    54, 59, 62, 65, 70, 74, 75, 80,
)

# 沙箱配置：全部路径落在 tmp_path 内；抓取关闭，测试绝不联网。
SANDBOX_CONFIG_YAML = """\
# 测试沙箱配置（由 tests/conftest.py 生成）
data:
  python_project:
    enabled: true
    dir: "data/shared"
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
"""


def encode_text(text: str, newline: str = "\r\n", bom: bool = False) -> bytes:
    """把文本按指定换行序列编码为字节（测试侧独立实现，不用被测代码）。"""
    body = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
    data = body.encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if bom else data


@dataclass
class Sandbox:
    """tmp_path 内的可写工作区：沙箱 cfg + 共享档案写入助手。"""

    cfg: Config
    root: Path

    # ── 路径 ──────────────────────────────────────────────
    @property
    def shared_history(self) -> Path:
        return self.cfg.shared_history_file

    @property
    def shared_points(self) -> Path:
        return self.cfg.shared_points_file

    @property
    def cache_copy(self) -> Path:
        """read_only 模式下 save_points 的落盘目标（§8.5）。"""
        return self.cfg.cache_dir / "points_copy.txt"

    # ── 写入 ──────────────────────────────────────────────
    def write_file(self, path, text: str, newline: str = "\r\n",
                   bom: bool = False) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(encode_text(text, newline, bom))
        return p

    def write_history(self, draws, newline: str = "\r\n") -> Path:
        """把 Draw 列表写成共享开奖档案（行序即入参顺序）。"""
        body = "\n".join(format_numbers_line(d.date, d.period, list(d.numbers))
                         for d in draws)
        return self.write_file(self.shared_history, body + "\n" if body else "",
                               newline)

    def write_points_archive(self, entries, newline: str = "\r\n") -> Path:
        """把 {period: PointEntry} 写成共享点位档案（按日期降序）。"""
        ordered = sorted(entries.values(),
                         key=lambda e: (e.date or _date.min, e.period), reverse=True)
        body = "\n".join(format_points_line(e.date, e.period, list(e.points))
                         for e in ordered)
        return self.write_file(self.shared_points, body + "\n" if body else "",
                               newline)


# ── fixtures ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def project_root() -> Path:
    return ROOT


@pytest.fixture
def cfg() -> Config:
    """项目根目录 config.yaml 加载出的真实配置（只读使用）。

    注意：load_config 会调用 ensure_dirs()，仅创建已存在的项目子目录。
    """
    return load_config()


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    """隔离的临时工作区：所有读写都在 tmp_path 内。"""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(SANDBOX_CONFIG_YAML, encoding="utf-8")
    conf = load_config(path=str(cfg_file), root=tmp_path)
    conf.shared_dir.mkdir(parents=True, exist_ok=True)
    assert conf.root == tmp_path.resolve()
    assert conf.read_only is True
    assert conf.fetch.enabled is False
    return Sandbox(cfg=conf, root=tmp_path)


@pytest.fixture
def write_file():
    """字节级写文件：write_file(path, text, newline='\\r\\n', bom=False) -> Path。"""
    def _write(path, text: str, newline: str = "\r\n", bom: bool = False) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(encode_text(text, newline, bom))
        return p
    return _write


@pytest.fixture
def make_draw():
    """make_draw(period, date_like, numbers) -> Draw（numbers 去重升序）。"""
    def _make(period: int, d, numbers) -> Draw:
        ds = d if isinstance(d, _date) else _date.fromisoformat(str(d))
        return Draw(period=int(period), date=ds,
                    numbers=tuple(sorted(set(int(x) for x in numbers))))
    return _make


@pytest.fixture
def make_history(make_draw):
    """make_history(rows) -> list[Draw]，行 = (period, 'YYYY-MM-DD', numbers)。

    默认返回**最新在前**（真实档案契约，§2.5 / §9.2）。
    """
    def _make(rows, descending: bool = True) -> list[Draw]:
        draws = [make_draw(p, d, nums) for p, d, nums in rows]
        ordered = sort_draws(draws)
        return ordered if descending else list(reversed(ordered))
    return _make


@pytest.fixture
def canonical_points() -> tuple[int, ...]:
    """§2.1 规格示例点位（20 个）。"""
    return CANONICAL_POINTS
