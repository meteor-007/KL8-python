# -*- coding: utf-8 -*-
"""kl8/source.py —— 四级数据源调度与降级（§2.6 / §8.1）。

本文件自包含：全部用例在 tmp_path 沙箱内构造档案，**不联网、不触碰共享档案**。
抓取分支一律用 monkeypatch 替换 `kl8.fetcher.fetch_incremental`。

覆盖的降级链：
  ① 共享目录存在且完整          → points_source == draws_source == "① 共享目录"
  ② 共享目录缺开奖 → 抓取成功   → draws_source == "② 联网抓取"
  ③ 抓取抛异常 / 抓取关闭       → 降级到 "③ uploads" / "③ seed"
  ④ 仍缺                     → 来源标记为 "缺失"，不抛异常
"""
from __future__ import annotations

import sys
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.kl8_lab import source                                        # noqa: E402
from backend.core.kl8_lab.config import load_config                            # noqa: E402
from backend.core.kl8_lab.data_io import (Draw, ParseReport, PointEntry,        # noqa: E402
                         format_numbers_line, format_points_line)
import backend.core.kl8_lab.fetcher as fetcher_module                           # noqa: E402

POINTS_NAME = "daily_points.txt"
HISTORY_NAME = "kl8_history_final.txt"

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
  enabled: __FETCH__
  sources: ["17500", "cwl"]
  timeout_sec: 1
  per_source_limit: 5
report:
  out_dir: "output"
"""


# ── 构造工具（测试侧独立实现，不调用 source.py 内部函数）────────

def _draw(idx: int, start: int = 2025001) -> Draw:
    nums = tuple(sorted(((idx * 7 + k * 3) % 80) + 1 for k in range(20)))
    return Draw(period=start + idx, date=_date(2025, 1, 1) + timedelta(days=idx),
                numbers=nums)


def _draws(n: int, start: int = 2025001) -> list[Draw]:
    return [_draw(i, start) for i in range(n)]


def _point(idx: int, start: int = 2025001) -> PointEntry:
    pts = tuple(sorted(((idx * 3 + k * 7) % 80) + 1 for k in range(20)))
    return PointEntry(period=start + idx, date=_date(2025, 1, 1) + timedelta(days=idx),
                      points=pts)


def _points_map(n: int, start: int = 2025001) -> dict[int, PointEntry]:
    out = {p.period: p for p in (_point(i, start) for i in range(n))}
    return out


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _write_history(path: Path, draws: list[Draw]) -> Path:
    body = "\n".join(format_numbers_line(d.date, d.period, list(d.numbers))
                     for d in draws)
    return _write_text(path, body + "\n" if body else "")


def _write_points(path: Path, entries: dict[int, PointEntry]) -> Path:
    ordered = sorted(entries.values(),
                     key=lambda e: (e.date or _date.min, e.period), reverse=True)
    body = "\n".join(format_points_line(e.date, e.period, list(e.points))
                     for e in ordered)
    return _write_text(path, body + "\n" if body else "")


def _make_cfg(tmp_path: Path, *, fetch: bool = False, mode: str = "read_only",
              project_dir: str = "shared"):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        CONFIG_YAML.replace("__FETCH__", "true" if fetch else "false")
                   .replace('dir: "shared"', f'dir: "{project_dir}"'),
        encoding="utf-8")
    return load_config(path=str(cfg_file), root=tmp_path)


def _sandbox(tmp_path: Path, *, fetch: bool = False, mode: str = "read_only"):
    """共享目录就绪的沙箱：3 期开奖 + 3 期点位（可严格配对）。"""
    cfg = _make_cfg(tmp_path, fetch=fetch, mode=mode)
    cfg.shared_dir.mkdir(parents=True, exist_ok=True)
    _write_history(cfg.shared_history_file, _draws(3))
    _write_points(cfg.shared_points_file, _points_map(3))
    return cfg


def _never_fetch(monkeypatch, flag: list | None = None):
    """替换抓取入口：任何调用都记为失败信号（用于断言"不该联网"）。"""
    def _fake(cfg, base=None):
        if flag is not None:
            flag.append(True)
        raise AssertionError("测试禁止真实/隐式抓取：应走本地兜底")
    monkeypatch.setattr(fetcher_module, "fetch_incremental", _fake)


# ── ① 共享目录 ────────────────────────────────────────────────

def test_load_shared_returns_archive(tmp_path):
    cfg = _sandbox(tmp_path)
    draws, points, rep = source.load_shared(cfg)

    assert draws is not None and len(draws) == 3
    assert points is not None and len(points) == 3
    assert isinstance(rep, ParseReport) and rep.malformed == 0
    # 开奖档案契约：最新在前
    assert [d.period for d in draws] == [2025003, 2025002, 2025001]
    # 同一 ParseReport 累计两个档案：3 期开奖 + 3 期点位
    assert rep.parsed == 6 and rep.total_lines == 6 and rep.blank_lines == 0


def test_load_shared_missing_files_returns_none(tmp_path):
    cfg = _make_cfg(tmp_path)
    cfg.shared_dir.mkdir(parents=True, exist_ok=True)      # 目录在、文件不在

    draws, points, rep = source.load_shared(cfg)
    assert draws is None and points is None
    assert isinstance(rep, ParseReport)


def test_load_dataset_prefers_shared(tmp_path, monkeypatch):
    _never_fetch(monkeypatch)                              # 不应触发抓取
    cfg = _sandbox(tmp_path, fetch=True)
    ds = source.load_dataset(cfg)

    assert len(ds.draws) == 3 and len(ds.points) == 3
    assert ds.health.draws_source == "① 共享目录"
    assert ds.health.points_source == "① 共享目录"
    assert ds.health.pairable_count == 3
    assert ds.latest_draw().period == 2025003
    assert ds.latest_points().period == 2025003


def test_load_dataset_only_points_in_shared_uses_fallback_draws(tmp_path, monkeypatch):
    """点位在共享目录、开奖缺失 → 开奖走 ③，点位仍标 ①。"""
    cfg = _make_cfg(tmp_path, fetch=False)
    cfg.shared_dir.mkdir(parents=True, exist_ok=True)
    _write_points(cfg.shared_points_file, _points_map(3))
    _write_history(cfg.upload_dir / HISTORY_NAME, _draws(4))

    ds = source.load_dataset(cfg)
    assert len(ds.draws) == 4
    assert ds.health.draws_source == "③ uploads"
    assert ds.health.points_source == "① 共享目录"
    assert ds.health.pairable_count == 3                   # 只有前 3 期能配对


# ── ② 抓取分支 ────────────────────────────────────────────────

def test_load_dataset_fetch_when_shared_missing(tmp_path, monkeypatch):
    """① 缺开奖 → ② 抓取成功 → draws_source 标 "② 联网抓取"。"""
    calls: list = []

    def _fake_fetch(cfg, base=None):
        calls.append(cfg)
        return _draws(5)

    monkeypatch.setattr(fetcher_module, "fetch_incremental", _fake_fetch)

    cfg = _make_cfg(tmp_path, fetch=True)
    cfg.shared_dir.mkdir(parents=True, exist_ok=True)
    _write_points(cfg.shared_points_file, _points_map(3))   # 点位仍在共享目录

    ds = source.load_dataset(cfg)
    assert calls, "共享目录缺开奖时必须尝试抓取"
    assert calls[0] is cfg
    assert len(ds.draws) == 5
    assert ds.health.draws_source == "② 联网抓取"
    assert ds.health.points_source == "① 共享目录"
    assert ds.health.pairable_count == 3


def test_load_dataset_fetch_exception_degrades_to_uploads(tmp_path, monkeypatch):
    """② 抛异常 → 降级 ③ uploads（不得向上冒泡）。"""
    def _boom(cfg, base=None):
        raise RuntimeError("模拟双源均不可用")

    monkeypatch.setattr(fetcher_module, "fetch_incremental", _boom)

    cfg = _make_cfg(tmp_path, fetch=True)
    _write_history(cfg.upload_dir / HISTORY_NAME, _draws(6))
    _write_points(cfg.upload_dir / POINTS_NAME, _points_map(6))

    ds = source.load_dataset(cfg)                          # 不抛异常
    assert len(ds.draws) == 6 and len(ds.points) == 6
    assert ds.health.draws_source == "③ uploads"
    assert ds.health.points_source == "③ uploads"
    assert ds.health.pairable_count == 6


def test_load_dataset_fetch_returns_none_degrades_to_seed(tmp_path, monkeypatch):
    """② 返回 None → 降级 ③ seed。"""
    monkeypatch.setattr(fetcher_module, "fetch_incremental",
                        lambda cfg, base=None: None)

    cfg = _make_cfg(tmp_path, fetch=True)
    _write_history(cfg.seed_dir / HISTORY_NAME, _draws(2))
    _write_points(cfg.seed_dir / POINTS_NAME, _points_map(2))

    ds = source.load_dataset(cfg)
    assert ds.health.draws_source == "③ seed"
    assert ds.health.points_source == "③ seed"
    assert ds.health.pairable_count == 2


def test_load_dataset_fetch_disabled_never_calls_network(tmp_path, monkeypatch):
    _never_fetch(monkeypatch)
    cfg = _make_cfg(tmp_path, fetch=False)
    _write_history(cfg.seed_dir / HISTORY_NAME, _draws(3))

    ds = source.load_dataset(cfg)
    assert ds.health.draws_source == "③ seed"
    assert ds.health.points_source == "缺失"


def test_load_dataset_prefers_uploads_over_seed(tmp_path, monkeypatch):
    _never_fetch(monkeypatch)
    cfg = _make_cfg(tmp_path, fetch=False)
    _write_history(cfg.seed_dir / HISTORY_NAME, _draws(2))
    _write_history(cfg.upload_dir / HISTORY_NAME, _draws(5))

    ds = source.load_dataset(cfg)
    assert len(ds.draws) == 5
    assert ds.health.draws_source == "③ uploads"


def test_load_dataset_all_missing_is_empty_not_crash(tmp_path, monkeypatch):
    _never_fetch(monkeypatch)
    cfg = _make_cfg(tmp_path, fetch=False)

    ds = source.load_dataset(cfg)
    assert ds.draws == [] and ds.points == {}
    assert ds.latest_draw() is None and ds.latest_points() is None
    assert ds.health.draws_source == "缺失"
    assert ds.health.points_source == "缺失"


def test_load_dataset_shared_dir_disabled(tmp_path, monkeypatch):
    """python_project.enabled=False → 完全跳过 ①。"""
    _never_fetch(monkeypatch)
    cfg = _make_cfg(tmp_path, fetch=False)
    _write_history(cfg.shared_history_file, _draws(3))     # 文件在但被禁用
    _write_history(cfg.seed_dir / HISTORY_NAME, _draws(1))

    cfg.data._data["python_project"]["enabled"] = False
    ds = source.load_dataset(cfg)
    assert len(ds.draws) == 1
    assert ds.health.draws_source == "③ seed"


def test_load_dataset_unreadable_shared_file_degrades(tmp_path, monkeypatch):
    """共享档案编码损坏 → _try_load 捕获 UnicodeDecodeError → 降级 ③。"""
    _never_fetch(monkeypatch)
    cfg = _make_cfg(tmp_path, fetch=False)
    cfg.shared_dir.mkdir(parents=True, exist_ok=True)
    cfg.shared_history_file.write_bytes(b"\xff\xfe\x00\x00\x01\x02\x03")
    _write_history(cfg.seed_dir / HISTORY_NAME, _draws(2))

    ds = source.load_dataset(cfg)
    assert len(ds.draws) == 2
    assert ds.health.draws_source == "③ seed"


# ── load_history_only ────────────────────────────────────────

def test_load_history_only_shared(tmp_path):
    cfg = _sandbox(tmp_path)
    draws, src = source.load_history_only(cfg, allow_fetch=False)
    assert len(draws) == 3 and src == "① 共享目录"


def test_load_history_only_fetch(tmp_path, monkeypatch):
    monkeypatch.setattr(fetcher_module, "fetch_incremental",
                        lambda cfg, base=None: _draws(4))
    cfg = _make_cfg(tmp_path, fetch=True)
    draws, src = source.load_history_only(cfg)
    assert len(draws) == 4 and src == "② 联网抓取"


def test_load_history_only_seed(tmp_path, monkeypatch):
    _never_fetch(monkeypatch)
    cfg = _make_cfg(tmp_path, fetch=False)
    _write_history(cfg.seed_dir / HISTORY_NAME, _draws(2))
    draws, src = source.load_history_only(cfg)
    assert len(draws) == 2 and src == "③ seed"


# ── 体检 ──────────────────────────────────────────────────────

def test_health_check_counts_flags_and_render():
    draws = _draws(5)                                      # 2025001..2025005
    pts = _points_map(3)                                   # 2025001..2025003
    pts[2025009] = PointEntry(period=2025009, date=_date(2025, 1, 20),
                              points=pts[2025001].points)
    # 重复日期：与 2025002 同日期
    pts[2025003] = PointEntry(period=2025003, date=pts[2025002].date,
                              points=pts[2025003].points)

    health = source.health_check(draws, pts, ParseReport(malformed=2),
                                 points_source="① 共享目录",
                                 draws_source="① 共享目录")

    assert health.points_count == 4
    assert health.draws_count == 5
    assert health.pairable_count == 3
    assert health.points_only == [2025009]
    assert health.dirty == [2025009]
    assert health.draws_only_count == 2
    assert health.malformed == 2
    assert health.duplicate_dates == {_date(2025, 1, 2).isoformat(): 2}
    assert health.points_source == "① 共享目录"

    text = health.render()
    assert "可严格配对期数" in text and "格式畸形行" in text


def test_health_check_detects_date_inversion():
    pts = _points_map(3)                                   # 日期递增
    # 让更老的期号拥有更新的日期 → 降序排列时出现"日期倒挂"
    pts[2025001] = PointEntry(period=2025001, date=_date(2025, 1, 9),
                              points=pts[2025001].points)
    health = source.health_check(_draws(3), pts)
    assert health.inversions == [2025001]


def test_health_check_inversions_empty_when_dates_monotone():
    health = source.health_check(_draws(4), _points_map(4))
    assert health.inversions == []
    assert health.duplicate_dates == {}


# ── Dataset 契约 ──────────────────────────────────────────────

def test_dataset_history_before_is_strict(tmp_path):
    cfg = _sandbox(tmp_path)
    ds = source.load_dataset(cfg)

    hist = ds.history_before(2025002)
    assert [d.period for d in hist] == [2025001]
    assert 2025002 not in {d.period for d in hist}
    assert ds.history_before(2026001) == ds.draws             # 全部严格小于
    assert ds.history_before(2025001) == []


def test_dataset_pairable_is_ascending_and_consistent(tmp_path):
    cfg = _make_cfg(tmp_path)
    cfg.shared_dir.mkdir(parents=True, exist_ok=True)
    _write_history(cfg.shared_history_file, list(reversed(_draws(4))))
    _write_points(cfg.shared_points_file, _points_map(4))
    ds = source.load_dataset(cfg)

    pairs = ds.pairable()
    assert [p for p, _, _ in pairs] == [2025001, 2025002, 2025003, 2025004]
    for period, draw, entry in pairs:
        assert draw.period == period == entry.period
    assert ds.health.pairable_count == len(pairs)


# ── §11.3 遗漏期（有开奖、无点位）──────────────────────────────

def test_missing_points_periods_flags_gap(tmp_path):
    """点位档案起点之后、有开奖却无点位的期，必须被识别为遗漏期。"""
    cfg = _sandbox(tmp_path)
    pts = _points_map(5)
    pts.pop(2025003)                              # 第 3 期漏录入
    _write_history(cfg.shared_history_file, _draws(5))
    _write_points(cfg.shared_points_file, pts)

    ds = source.load_dataset(cfg, allow_fetch=False)
    assert ds.missing_points_periods() == [2025003]
    # 遗漏期不参与配对
    assert [p for p, _d, _e in ds.pairable()] == \
        [2025001, 2025002, 2025004, 2025005]


def test_missing_points_periods_ignores_draws_before_archive_start(tmp_path):
    """点位档案起点之前的开奖不算遗漏（那本就没有点位档案）。"""
    cfg = _sandbox(tmp_path)
    pts = _points_map(6, start=2025010)           # 覆盖 2025010..2025015
    _write_history(cfg.shared_history_file, _draws(15))   # 2025001..2025015
    _write_points(cfg.shared_points_file, pts)

    ds = source.load_dataset(cfg, allow_fetch=False)
    # 2025001..2025009 早于点位档案起点 → 不算遗漏
    assert ds.missing_points_periods() == []

    pts.pop(2025013)                              # 档案中途漏一期
    _write_points(cfg.shared_points_file, pts)
    ds = source.load_dataset(cfg, allow_fetch=False)
    assert ds.missing_points_periods() == [2025013]


def test_backtest_counts_missing_points_as_skipped(tmp_path):
    """§11.3：遗漏期必须计入「跳过期数」，不能静默消失。"""
    from backend.core.kl8_lab import replay

    cfg = _sandbox(tmp_path)
    draws = _draws(40)
    pts = _points_map(40)
    pts.pop(2025030)                              # 第 30 期漏录入
    _write_history(cfg.shared_history_file, draws)
    _write_points(cfg.shared_points_file, pts)

    ds = source.load_dataset(cfg, allow_fetch=False)
    bt = replay.run_backtest(cfg, ds, all_periods=True, warmup=10)

    assert bt.missing_points == 1
    assert bt.skipped == 11                       # 10 期预热不足 + 1 期遗漏期
    assert 2025030 not in [r.period for r in bt.records]
    assert bt.T + bt.skipped == 40
