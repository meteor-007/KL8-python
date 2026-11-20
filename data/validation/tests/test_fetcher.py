# -*- coding: utf-8 -*-
"""kl8/fetcher.py —— 双源解析与降级 + 原子写回（§8.2 / §8.5）。

**禁止真实网络请求**：所有 HTTP 调用都被替换成本地 mock 的 `requests.get`，
或直接 monkeypatch `fetch_from_*` / `fetch_incremental`。

已修复的源码缺陷（用例已转为正常断言）：
  · `write_history()` 曾把 `format_numbers_line(d.period, d.date, ...)` 实参
    顺序写反（签名是 `(date, period, numbers)`），导致写回路径必然抛
    AttributeError。现已修正，相关用例见 test_write_history_backup_and_writeback。
  · `fetch_incremental()` 新增 `dry_run` 参数：为真时只抓取/合并、不写回。
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import kl8.data_io as data_io                                   # noqa: E402
import kl8.fetcher as fetcher                                    # noqa: E402
from kl8.config import load_config                               # noqa: E402
from kl8.data_io import (Draw, ParseReport, format_numbers_line,   # noqa: E402
                         format_points_line, load_draws)

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
  enabled: true
  sources: ["17500", "cwl"]
  timeout_sec: 1
  per_source_limit: 5
report:
  out_dir: "output"
"""


# ── 工具 ──────────────────────────────────────────────────────

def _nums(idx: int) -> tuple[int, ...]:
    return tuple(sorted(((idx * 7 + k * 3) % 80) + 1 for k in range(20)))


def _draw(idx: int, start: int = 2025001) -> Draw:
    return Draw(period=start + idx, date=_date(2025, 1, 1) + timedelta(days=idx),
                numbers=_nums(idx))


def _draws(n: int, start: int = 2025001) -> list[Draw]:
    return [_draw(i, start) for i in range(n)]


def _make_cfg(tmp_path: Path, *, mode: str = "read_only", fetch: bool = True):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(CONFIG_YAML.replace('mode: "read_only"',
                                            f'mode: "{mode}"')
                        .replace("enabled: true\n  sources",
                                 f"enabled: {'true' if fetch else 'false'}\n  sources"),
                        encoding="utf-8")
    return load_config(path=str(cfg_file), root=tmp_path)


def _write_history(path: Path, draws: list[Draw]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(format_numbers_line(d.date, d.period, list(d.numbers))
                     for d in draws)
    path.write_bytes((body + "\n" if body else "").encode("utf-8"))
    return path


def _write_points(path: Path, n: int, start: int = 2025001) -> Path:
    rows = []
    for i in range(n):
        pts = tuple(sorted(((i * 3 + k * 7) % 80) + 1 for k in range(20)))
        rows.append(format_points_line(_date(2025, 1, 1) + timedelta(days=i),
                                       start + i, list(pts)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(rows) + "\n").encode("utf-8"))
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, raise_json=False):
        self.status_code = status_code
        self._payload = payload
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("invalid json payload")
        return self._payload


def _mock_get(monkeypatch, response=None, exc=None, record=None):
    """替换 requests.get；可返回固定响应、抛异常，或记录调用参数。"""
    def _get(url, **kwargs):
        if record is not None:
            record.append((url, kwargs))
        if exc is not None:
            raise exc
        return response
    monkeypatch.setattr(requests, "get", _get)
    return record


# ── 纯解析函数 ────────────────────────────────────────────────

def test_clean_numbers_accepts_all_delimiters():
    raw = ",".join(f"{n:02d}" for n in range(1, 21))
    got = fetcher._clean_numbers(raw)
    assert got == list(range(1, 21))
    assert fetcher._clean_numbers("1-2-3-4-5-6-7-8-9-10-11-12-13-14-15-16-17-18-19-20")
    assert fetcher._clean_numbers(" ".join(str(x) for x in range(61, 81)))


def test_clean_numbers_rejects_wrong_size_and_filters_out_of_range():
    assert fetcher._clean_numbers("") is None
    assert fetcher._clean_numbers(" ".join(str(x) for x in range(1, 20))) is None
    # 81 越界被丢弃 → 只剩 19 个有效号 → None
    assert fetcher._clean_numbers(" ".join(str(x) for x in range(1, 20)) + " 81") is None
    # 21 个有效号同样不合格；重复号不算数
    raw = " ".join(str(x) for x in range(1, 22))
    assert fetcher._clean_numbers(raw) is None
    dup = " ".join(str(x) for x in range(1, 21)) + " 1"
    assert fetcher._clean_numbers(dup) == list(range(1, 21))


def test_parse_date_supported_formats():
    assert fetcher._parse_date("2025-01-02") == _date(2025, 1, 2)
    assert fetcher._parse_date("2025/01/02") == _date(2025, 1, 2)
    assert fetcher._parse_date("20250102") == _date(2025, 1, 2)
    assert fetcher._parse_date("2025-01-02(四) 21:30") == _date(2025, 1, 2)
    assert fetcher._parse_date("not-a-date") is None
    assert fetcher._parse_date("") is None
    assert fetcher._parse_date(None) is None


# ── 17500 源（本地 mock 响应）─────────────────────────────────

def test_fetch_from_17500_parses_payload(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    payload = {"list": [
        {"qihao": "2025002", "opencode": ",".join(f"{n:02d}" for n in _nums(1)),
         "opentime": "2025-01-02 21:30:00"},
        {"qihao": "2025001", "opencode": "-".join(f"{n:02d}" for n in _nums(0)),
         "opentime": "20250101"},
    ]}
    rec: list = []
    _mock_get(monkeypatch, _FakeResponse(200, payload), record=rec)

    got = fetcher.fetch_from_17500(cfg)
    assert [d.period for d in got] == [2025002, 2025001]
    assert got[0].date == _date(2025, 1, 2)
    assert got[1].numbers == _nums(0)
    assert rec and rec[0][1]["timeout"] == 1               # 尊重配置超时

    # 显式关闭真实网络：本次调用只命中 mock
    assert rec[0][0] == fetcher.URL_17500


def test_fetch_from_17500_skips_malformed_records(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    good = ",".join(f"{n:02d}" for n in _nums(0))
    payload = {"list": [
        {"qihao": None, "opencode": good, "opentime": "2025-01-01"},
        {"qihao": "2025002", "opencode": "01 02 03", "opentime": "2025-01-02"},
        {"qihao": "2025003", "opencode": good, "opentime": "bad-date"},
        {"qihao": "2025004", "opencode": good, "opentime": "2025-01-04"},
    ]}
    _mock_get(monkeypatch, _FakeResponse(200, payload))

    got = fetcher.fetch_from_17500(cfg)
    assert [d.period for d in got] == [2025004]


def test_fetch_from_17500_http_error_returns_empty(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    _mock_get(monkeypatch, _FakeResponse(503, None))
    assert fetcher.fetch_from_17500(cfg) == []


def test_fetch_from_17500_network_exception_returns_empty(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    _mock_get(monkeypatch, exc=requests.ConnectionError("offline"))
    assert fetcher.fetch_from_17500(cfg) == []


def test_fetch_from_17500_bad_json_returns_empty(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    _mock_get(monkeypatch, _FakeResponse(200, None, raise_json=True))
    assert fetcher.fetch_from_17500(cfg) == []


# ── CWL 源（本地 mock 响应）───────────────────────────────────

def test_fetch_from_cwl_uses_kjhyjsx_then_red(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    payload = {"result": [
        {"code": "2025002", "kjhyjsx": ",".join(f"{n:02d}" for n in _nums(1)),
         "date": "2025-01-02"},
        # 无 kjhyjsx → 回退 red
        {"code": "2025001", "red": " ".join(f"{n:02d}" for n in _nums(0)),
         "date": "2025/01/01"},
        {"code": "2025003", "red": "01 02 03", "date": "2025-01-03"},
    ]}
    _mock_get(monkeypatch, _FakeResponse(200, payload))

    got = fetcher.fetch_from_cwl(cfg)
    assert [d.period for d in got] == [2025002, 2025001]
    assert got[1].numbers == _nums(0)


def test_fetch_from_cwl_http_error_and_exception(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    _mock_get(monkeypatch, _FakeResponse(500, None))
    assert fetcher.fetch_from_cwl(cfg) == []

    _mock_get(monkeypatch, exc=TimeoutError("timeout"))
    assert fetcher.fetch_from_cwl(cfg) == []


# ── 多源降级 ──────────────────────────────────────────────────

def test_fetch_from_sources_falls_back_to_second(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    monkeypatch.setattr(fetcher, "fetch_from_17500",
                        lambda c: [])                   # 第一源空
    monkeypatch.setattr(fetcher, "fetch_from_cwl", lambda c: _draws(3))

    got, src = fetcher.fetch_from_sources(cfg)
    assert len(got) == 3 and src == "cwl"


def test_fetch_from_sources_unknown_name_is_skipped(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    cfg.fetch._data["sources"] = ["bogus", "17500"]
    monkeypatch.setattr(fetcher, "fetch_from_17500", lambda c: _draws(1))

    got, src = fetcher.fetch_from_sources(cfg)
    assert len(got) == 1 and src == "17500"


def test_fetch_from_sources_all_fail(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    monkeypatch.setattr(fetcher, "fetch_from_17500", lambda c: [])
    monkeypatch.setattr(fetcher, "fetch_from_cwl", lambda c: [])

    assert fetcher.fetch_from_sources(cfg) == ([], "")


def test_fetch_from_sources_first_exception_then_second_ok(tmp_path, monkeypatch):
    """单源内部异常已被各自 except 吞掉：第一源返回 []，第二源仍生效。"""
    cfg = _make_cfg(tmp_path)
    bad = _FakeResponse(200, {"list": None})
    calls: list = []

    def _get(url, **kwargs):
        calls.append(url)
        if url == fetcher.URL_17500:
            raise requests.ConnectionError("offline")
        return bad

    monkeypatch.setattr(requests, "get", _get)
    monkeypatch.setattr(fetcher, "URL_CWL", "https://example.invalid/cwl")

    got, src = fetcher.fetch_from_sources(cfg)
    assert got == [] and src == ""
    assert len(calls) == 2                                 # 两个源都被尝试


# ── 增量抓取（mock 数据源）────────────────────────────────────

def test_fetch_incremental_merges_dedups_and_writes(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    base = _draws(3)                                       # 2025001..3
    got = _draws(5)                                        # 2025001..5（前 3 期重复）
    monkeypatch.setattr(fetcher, "fetch_from_sources", lambda c: (got, "17500"))

    written: list = []
    monkeypatch.setattr(fetcher, "write_history",
                        lambda c, d, **kw: written.append(list(d)) or (c.cache_dir / "x"))

    merged = fetcher.fetch_incremental(cfg, base=base)
    assert [d.period for d in merged] == [2025005, 2025004, 2025003, 2025002, 2025001]
    assert len({d.period for d in merged}) == 5            # 无重复
    assert len(written) == 1 and len(written[0]) == 5       # 只有新增期才写回
    assert cfg.shared_history_file.exists() is False        # read_only 不碰共享档案


def test_fetch_incremental_no_fresh_periods_skips_write(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    base = _draws(3)
    monkeypatch.setattr(fetcher, "fetch_from_sources",
                        lambda c: (_draws(3), "17500"))    # 全是已有期

    written: list = []
    monkeypatch.setattr(fetcher, "write_history",
                        lambda c, d, **kw: written.append(d))
    merged = fetcher.fetch_incremental(cfg, base=base)
    assert len(merged) == 3 and written == []


def test_fetch_incremental_sources_down_returns_base(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    base = _draws(4)
    monkeypatch.setattr(fetcher, "fetch_from_sources", lambda c: ([], ""))

    merged = fetcher.fetch_incremental(cfg, base=base)
    assert [d.period for d in merged] == [d.period for d in base]
    assert isinstance(merged, list) and merged == base      # 抓取失败 → 交付本地数据


def test_fetch_incremental_no_source_no_base_returns_none(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    monkeypatch.setattr(fetcher, "fetch_from_sources", lambda c: ([], ""))
    assert fetcher.fetch_incremental(cfg) is None


def test_fetch_incremental_write_failure_keeps_memory_result(tmp_path, monkeypatch):
    """写回失败（OSError/RuntimeError）→ 仅在内存中使用，不向上冒泡。"""
    cfg = _make_cfg(tmp_path)
    monkeypatch.setattr(fetcher, "fetch_from_sources", lambda c: (_draws(5), "17500"))

    def _boom(c, d, **kw):
        raise OSError("磁盘只读")

    monkeypatch.setattr(fetcher, "write_history", _boom)
    merged = fetcher.fetch_incremental(cfg)
    assert len(merged) == 5

    def _boom2(c, d, **kw):
        raise RuntimeError("写回后复核失败")

    monkeypatch.setattr(fetcher, "write_history", _boom2)
    assert len(fetcher.fetch_incremental(cfg)) == 5


def test_local_history_prefers_shared_then_cache(tmp_path):
    cfg = _make_cfg(tmp_path)
    _write_history(cfg.cache_dir / "history_copy.txt", _draws(2))
    assert len(fetcher._local_history(cfg)) == 2           # 回退到本项目副本

    _write_history(cfg.shared_history_file, _draws(4))
    assert len(fetcher._local_history(cfg)) == 4           # 共享档案优先


def test_get_latest_issue_and_date(tmp_path):
    cfg = _make_cfg(tmp_path)
    assert fetcher.get_latest_issue_and_date(cfg) == (0, None)
    _write_history(cfg.shared_history_file, list(reversed(_draws(3))))
    period, d = fetcher.get_latest_issue_and_date(cfg)
    assert period == 2025003 and d == _date(2025, 1, 3)


# ── 写回路由与只读纪律（§8.5）────────────────────────────────

def test_target_path_routing(tmp_path):
    cfg_ro = _make_cfg(tmp_path / "ro", mode="read_only")
    assert fetcher._target_path(cfg_ro) == cfg_ro.cache_dir / "history_copy.txt"
    assert fetcher._target_path(cfg_ro) != cfg_ro.shared_history_file

    cfg_rw = _make_cfg(tmp_path / "rw", mode="read_write")
    assert cfg_rw.read_only is False
    assert fetcher._target_path(cfg_rw) == cfg_rw.shared_history_file


def test_readonly_default_real_config():
    """项目根 config.yaml 默认 read_only，写回目标落在本项目副本。"""
    cfg = load_config()
    assert cfg.data.python_project.mode == "read_only"
    assert cfg.read_only is True
    target = fetcher._target_path(cfg)
    assert target != cfg.shared_history_file
    assert target.parent == cfg.cache_dir
    assert (cfg.shared_dir / "kl8_history_final.txt") in (
        cfg.shared_history_file,)


def test_readonly_default_shared_file_untouched(tmp_path, monkeypatch):
    """read_only 下走完整抓取+写回流程，共享档案字节与 mtime 不变。"""
    cfg = _make_cfg(tmp_path, mode="read_only")
    shared = _write_history(cfg.shared_history_file, _draws(3))
    shared_points = _write_points(cfg.shared_points_file, 3)
    before = (_sha256(shared), shared.stat().st_mtime_ns,
              _sha256(shared_points), shared_points.stat().st_mtime_ns)

    monkeypatch.setattr(fetcher, "fetch_from_sources", lambda c: (_draws(6), "17500"))

    targets: list = []
    real_target_path = fetcher._target_path

    def _stub_write(c, draws, **kw):
        """替代真实写回，只记录路由目标（验证 read_only 下不碰共享档案）。"""
        path = real_target_path(c)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"stub\n")
        targets.append(path)
        return path

    monkeypatch.setattr(fetcher, "write_history", _stub_write)

    merged = fetcher.fetch_incremental(cfg)
    assert len(merged) == 6
    assert targets and targets[0] == cfg.cache_dir / "history_copy.txt"
    assert targets[0] != shared

    after = (_sha256(shared), shared.stat().st_mtime_ns,
             _sha256(shared_points), shared_points.stat().st_mtime_ns)
    assert before == after, "read_only 模式不得触碰共享档案"


def test_readwrite_mode_targets_shared_only_when_explicit(tmp_path):
    cfg = _make_cfg(tmp_path, mode="read_write")
    assert fetcher._target_path(cfg) == cfg.shared_history_file


# ── 原子写 ────────────────────────────────────────────────────

def test_atomic_write_interrupt_keeps_original_bytes(tmp_path, monkeypatch):
    """写入过程抛异常 → 原文件字节不变，且不留 .tmp 残留。"""
    target = tmp_path / "shared_history.txt"
    original = b"date:2025-01-01,period:2025001,numbers:01-02-03\r\n"
    target.write_bytes(original)
    tmp_file = Path(str(target) + ".tmp")
    new_text = "date:2025-01-02,period:2025002,numbers:04-05-06\n"

    def _boom(*args, **kwargs):
        raise OSError("模拟写入中断")

    # ① fsync 阶段失败：数据已写入 .tmp 但从未替换原文件
    monkeypatch.setattr(data_io.os, "fsync", _boom)
    with pytest.raises(OSError):
        data_io.write_text_atomic(str(target), new_text)
    assert target.read_bytes() == original
    assert not tmp_file.exists()

    # ② os.replace 阶段失败：同样不得破坏原文件
    monkeypatch.setattr(data_io.os, "fsync", lambda fd: None)
    monkeypatch.setattr(data_io.os, "replace", _boom)
    with pytest.raises(OSError):
        data_io.write_text_atomic(str(target), new_text)
    assert target.read_bytes() == original
    assert not tmp_file.exists()

    # ③ 目标文件原本不存在时中断 → 不得留下半成品
    fresh = tmp_path / "fresh.txt"
    with pytest.raises(OSError):
        data_io.write_text_atomic(str(fresh), new_text)
    assert not fresh.exists()
    assert not Path(str(fresh) + ".tmp").exists()


def test_atomic_write_success_preserves_declared_newline(tmp_path):
    target = tmp_path / "out.txt"
    data_io.write_text_atomic(str(target), "a\nb\nc\n", newline="\r\n")
    assert target.read_bytes() == b"a\r\nb\r\nc\r\n"


def test_write_history_backup_and_writeback(tmp_path, monkeypatch):
    """写回前备份、写回后复核、read_only 只写本项目副本（写回路径已修复）。"""
    cfg = _make_cfg(tmp_path, mode="read_only")
    target = cfg.cache_dir / "history_copy.txt"
    _write_history(target, _draws(2))
    before = target.read_bytes()

    written = fetcher.write_history(cfg, _draws(4))
    assert written == target
    assert cfg.shared_history_file.exists() is False
    backups = list((cfg.cache_dir / "backup").glob("history_copy_*.bak"))
    assert backups and backups[0].read_bytes() == before
    assert len(load_draws(str(target), ParseReport())) == 4
    assert target.read_bytes().count(b"\r\n") == 4          # 显式 CRLF


def test_fetch_incremental_real_writeback_end_to_end(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path, mode="read_only")
    monkeypatch.setattr(fetcher, "fetch_from_sources", lambda c: (_draws(5), "17500"))

    merged = fetcher.fetch_incremental(cfg)
    assert len(merged) == 5
    copy_path = cfg.cache_dir / "history_copy.txt"
    assert copy_path.exists()
    assert len(load_draws(str(copy_path))) == 5
    assert cfg.shared_history_file.exists() is False


def test_fetch_incremental_dry_run_skips_writeback(tmp_path, monkeypatch):
    """dry_run=True 只抓取并合并到内存，绝不落盘；False 才真正写回（§8.2）。"""
    cfg = _make_cfg(tmp_path, mode="read_only")
    monkeypatch.setattr(fetcher, "fetch_from_sources", lambda c: (_draws(5), "17500"))

    merged = fetcher.fetch_incremental(cfg, dry_run=True)
    assert len(merged) == 5
    assert not (cfg.cache_dir / "history_copy.txt").exists()
    assert cfg.shared_history_file.exists() is False

    fetcher.fetch_incremental(cfg)                     # dry_run=False → 真正写回
    assert (cfg.cache_dir / "history_copy.txt").exists()


# ── 读本地历史（get_latest_issue_and_date 的底座）──────────────

def test_local_history_ignores_unreadable_file(tmp_path):
    cfg = _make_cfg(tmp_path)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    (cfg.cache_dir / "history_copy.txt").write_bytes(b"\xff\xfe\x00bad")
    assert fetcher._local_history(cfg) == []


# ── §8.5 共享写回保护 ─────────────────────────────────────────

def test_write_shared_aborts_when_archive_changed_externally(tmp_path):
    """写回前 hash 不一致（对方已改）→ 放弃本轮写回，共享档案保持对方版本。"""
    cfg = _make_cfg(tmp_path, mode="read_write")
    shared = _write_history(cfg.shared_history_file, _draws(3))
    stale_hash = data_io.file_hash(shared)

    _write_history(cfg.shared_history_file, _draws(4))      # 对方追加了一期
    target = fetcher.write_history(cfg, _draws(5), expect_hash=stale_hash)

    assert target == cfg.shared_history_file
    assert len(load_draws(str(cfg.shared_history_file))) == 4     # 未被我们覆盖
    assert not (cfg.cache_dir / "history_copy.txt").exists()      # 也未降级写副本


def test_write_shared_falls_back_to_copy_on_permission_error(tmp_path, monkeypatch):
    """共享文件被占用（PermissionError）→ 退避重试后降级写本项目副本。"""
    monkeypatch.setattr("time.sleep", lambda *_a: None)           # 跳过退避等待
    cfg = _make_cfg(tmp_path, mode="read_write")
    shared = _write_history(cfg.shared_history_file, _draws(2))

    real_write = data_io.write_text_atomic

    def _deny(path, content, newline="\r\n"):
        if Path(path) == cfg.shared_history_file:
            raise PermissionError("[WinError 5] 拒绝访问")
        return real_write(path, content, newline)

    monkeypatch.setattr(data_io, "write_text_atomic", _deny)

    target = fetcher.write_history(cfg, _draws(4))

    assert target == cfg.cache_dir / "history_copy.txt"
    assert len(load_draws(str(target))) == 4
    assert len(load_draws(str(shared))) == 2                      # 共享档案未被改动


def test_write_shared_succeeds_when_hash_matches(tmp_path):
    cfg = _make_cfg(tmp_path, mode="read_write")
    shared = _write_history(cfg.shared_history_file, _draws(3))
    expect = data_io.file_hash(shared)

    target = fetcher.write_history(cfg, _draws(5), expect_hash=expect)

    assert target == shared
    assert len(load_draws(str(shared))) == 5


def test_reconcile_warns_only_when_shared_periods_shrink(tmp_path):
    """§8.5 对账：期数较上次运行减少才告警。"""
    from kl8 import observability

    state = tmp_path / "state"
    observability.write_heartbeat(state, {"shared_history_periods": 100})

    shrink = observability.reconcile(state, "shared_history_periods", 90)
    assert shrink and "疑似被外部覆盖" in shrink
    assert observability.reconcile(state, "shared_history_periods", 100) == ""
    assert observability.reconcile(state, "shared_history_periods", 120) == ""
    assert observability.reconcile(state, "never_seen_key", 1) == ""
