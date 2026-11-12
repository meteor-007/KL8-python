# -*- coding: utf-8 -*-
"""数据解析、编码与 CRLF 字节级往返（§2.1 / §2.2 / §8.2 / §8.4）。

§10.2 对应用例：test_crlf_roundtrip_bytes、test_atomic_write_interrupt。
"""
from __future__ import annotations

import dataclasses
import os
from datetime import date

import pytest

from kl8.data_io import (DRAW_SIZE, POINTS_SIZE, Draw, ParseReport, detect_newline,
                         draws_to_text, format_numbers_line, format_points_line,
                         load_draws, load_points_archive, parse_line,
                         points_to_text, read_text, sort_draws, write_text_atomic)


# ── 两段锚定解析：日期里的 '-' 不得被当作号码分隔符 ────────────

def test_parse_line_draw_anchors_date_before_splitting():
    """v1.0 缺陷：整行分词会把 date:2026-06-10 切碎。"""
    line = ("date:2026-06-10,period:2026151,numbers:"
            "12-24-44-36-06-49-70-10-73-03-52-21-04-45-37-38-77-41-42-78")
    parsed = parse_line(line)
    assert parsed is not None
    d, period, nums = parsed
    assert d == date(2026, 6, 10)
    assert period == 2026151
    assert len(nums) == DRAW_SIZE
    assert nums == sorted(nums)                       # 升序
    assert nums == [3, 4, 6, 10, 12, 21, 24, 36, 37, 38, 41, 42, 44, 45, 49,
                    52, 70, 73, 77, 78]
    assert len(set(nums)) == DRAW_SIZE


def test_parse_line_points_payload_uses_spaces(canonical_points):
    line = format_points_line(date(2026, 6, 11), 2026152, list(canonical_points))
    assert line.startswith("date:2026-06-11,period:2026152,points:")
    d, period, nums = parse_line(line)
    assert (d, period) == (date(2026, 6, 11), 2026152)
    assert nums == sorted(canonical_points)
    assert len(nums) == POINTS_SIZE


def test_parse_line_tolerates_mixed_payload_separators():
    line = "date:2026-06-10,period:2026151,numbers:01 02，03、04;05-06|07\t08"
    assert parse_line(line)[2] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_parse_line_requires_period_and_payload_anchors():
    assert parse_line("date:2026-01-01,points:01 02 03") is None      # 无 period
    assert parse_line("period:2026001") is None                      # 无 payload
    assert parse_line("开奖记录 01 02 03") is None
    assert parse_line("") is None


def test_parse_line_filters_out_of_range_and_duplicates():
    d, period, nums = parse_line("date:2026-01-01,period:2026001,numbers:01 01 81 0 05")
    assert (d, period, nums) == (date(2026, 1, 1), 2026001, [1, 5])


def test_parse_line_returns_none_date_for_impossible_date():
    """日期字段畸形：只丢日期，不丢整行（用于标记而非丢弃期次）。"""
    d, period, nums = parse_line(
        "date:2026-13-45,period:2026001,numbers:01-02-03-04-05-06-07-08-09-10"
        "-11-12-13-14-15-16-17-18-19-20")
    assert d is None
    assert period == 2026001 and len(nums) == 20


# ── load_draws：排序、畸形行、重复期号 ────────────────────────

def test_load_draws_sorts_desc_and_counts_malformed(tmp_path, write_file):
    good_old = format_numbers_line(date(2026, 1, 1), 2026001, list(range(1, 21)))
    good_new = format_numbers_line(date(2026, 1, 2), 2026002, list(range(21, 41)))
    nineteen = format_numbers_line(date(2026, 1, 3), 2026003, list(range(1, 20)))
    text = "\n".join([good_old, "", "这不是一行有效记录", nineteen, good_new])
    path = write_file(tmp_path / "history.txt", text)

    rep = ParseReport()
    draws = load_draws(str(path), rep)

    assert [d.period for d in draws] == [2026002, 2026001]     # 日期降序
    assert rep.total_lines == 4
    assert rep.blank_lines == 1
    assert rep.parsed == 2
    assert rep.malformed == 2
    assert len(rep.malformed_details) == 2
    assert "第3行" in rep.malformed_details[0]
    assert "第4行" in rep.malformed_details[1]
    assert all(len(d.numbers) == DRAW_SIZE for d in draws)


def test_load_draws_keeps_first_line_for_duplicate_period(tmp_path, write_file):
    first = format_numbers_line(date(2026, 1, 5), 2026005, list(range(1, 21)))
    second = format_numbers_line(date(2026, 1, 5), 2026005, list(range(41, 61)))
    path = write_file(tmp_path / "dup.txt", first + "\n" + second + "\n")

    draws = load_draws(str(path))
    assert len(draws) == 1
    assert draws[0].numbers == tuple(range(1, 21))


def test_load_draws_handles_missing_trailing_newline(tmp_path, write_file):
    line = format_numbers_line(date(2026, 1, 1), 2026001, list(range(1, 21)))
    path = write_file(tmp_path / "noeol.txt", line)
    draws = load_draws(str(path))
    assert len(draws) == 1 and draws[0].period == 2026001


def test_load_draws_reads_bom_file(tmp_path, write_file):
    """编码：utf-8-sig 静默剥离 BOM。"""
    line = format_numbers_line(date(2026, 1, 1), 2026001, list(range(1, 21)))
    path = write_file(tmp_path / "bom.txt", line + "\n", bom=True)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")

    text = read_text(str(path))
    assert not text.startswith("\ufeff")
    assert load_draws(str(path))[0].period == 2026001


def test_load_points_archive_requires_exactly_20(tmp_path, write_file):
    good = format_points_line(date(2026, 1, 2), 2026002, list(range(1, 21)))
    short = format_points_line(date(2026, 1, 1), 2026001, list(range(1, 19)))
    path = write_file(tmp_path / "points.txt", good + "\n" + short + "\n")

    rep = ParseReport()
    entries = load_points_archive(str(path), rep)
    assert list(entries) == [2026002]
    assert rep.parsed == 1 and rep.malformed == 1
    assert entries[2026002].date == date(2026, 1, 2)


def test_format_lines_roundtrip_through_parse_line(canonical_points):
    pl = format_points_line(date(2026, 6, 11), 2026152, list(canonical_points))
    assert pl.count(",") == 2                         # 三段锚定：date/period/payload
    assert parse_line(pl)[2] == sorted(canonical_points)

    nl = format_numbers_line(date(2026, 6, 10), 2026151, [1, 2, 3, 4, 5, 6, 7, 8,
                                                          9, 10, 11, 12, 13, 14,
                                                          15, 16, 17, 18, 19, 20])
    assert "-" in nl.split("numbers:")[1]             # 开奖用短横线
    assert parse_line(nl)[2] == list(range(1, 21))


def test_format_points_line_with_none_date():
    line = format_points_line(None, 2026152, list(range(1, 21)))
    assert line.startswith("date:,period:2026152,points:01 ")
    d, period, nums = parse_line(line)
    assert d is None and period == 2026152 and len(nums) == 20


# ── 写回：换行契约与字节级往返 ────────────────────────────────

def test_detect_newline_variants():
    assert detect_newline("a\r\nb\r\n") == "\r\n"
    assert detect_newline("a\rb\r") == "\r"
    assert detect_newline("a\nb\n") == "\n"
    assert detect_newline("abc") == "\n"              # 无换行时默认


def test_read_text_preserves_newlines(tmp_path, write_file):
    path = write_file(tmp_path / "crlf.txt", "a\nb\n", newline="\r\n")
    text = read_text(str(path))
    assert text == "a\r\nb\r\n"
    assert text.count("\r\n") == 2


def test_crlf_roundtrip_bytes(tmp_path, write_file, canonical_points):
    """§10.2：读 CRLF → 写回 → 字节级完全相同。"""
    rows = [
        format_points_line(date(2026, 6, 11), 2026152, list(canonical_points)),
        format_points_line(date(2026, 6, 10), 2026151, list(range(1, 21))),
    ]
    path = write_file(tmp_path / "daily_points.txt", "\n".join(rows) + "\n",
                      newline="\r\n")
    before = path.read_bytes()
    assert before.count(b"\r\n") == 2
    assert b"\r\r\n" not in before
    assert b"\n" not in before.replace(b"\r\n", b"")   # 纯 CRLF，无裸 LF

    text = read_text(str(path))
    assert detect_newline(text) == "\r\n"

    write_text_atomic(str(path), text, newline="\r\n")
    after = path.read_bytes()

    assert after == before                            # 字节级契约
    assert after.count(b"\r\n") == 2
    assert b"\r\r\n" not in after
    assert len(after) == len(before)
    assert not (tmp_path / "daily_points.txt.tmp").exists()

    entries = load_points_archive(str(path))
    assert sorted(entries) == [2026151, 2026152]
    assert entries[2026152].points == tuple(sorted(canonical_points))


def test_crlf_roundtrip_via_draws_to_text(tmp_path, write_file, make_history):
    draws = make_history([
        (2026001, date(2026, 1, 1), list(range(1, 21))),
        (2026002, date(2026, 1, 2), list(range(21, 41))),
    ])
    path = tmp_path / "history.txt"
    write_text_atomic(str(path), draws_to_text(draws) + "\n", newline="\r\n")
    before = path.read_bytes()

    text = read_text(str(path))
    write_text_atomic(str(path), text, newline="\r\n")
    assert path.read_bytes() == before
    assert [d.period for d in load_draws(str(path))] == [2026002, 2026001]


def test_crlf_roundtrip_via_points_to_text(tmp_path, canonical_points):
    from kl8.data_io import PointEntry
    entries = {
        2026242: PointEntry(period=2026242, date=date(2026, 9, 9),
                            points=tuple(sorted(canonical_points))),
        2026241: PointEntry(period=2026241, date=date(2026, 9, 8),
                            points=tuple(sorted(range(1, 21)))),
    }
    path = tmp_path / "archive.txt"
    write_text_atomic(str(path), points_to_text(entries) + "\n", newline="\r\n")
    before = path.read_bytes()
    assert before.count(b"\r\n") == 2                 # 两行，最新在前

    text = read_text(str(path))
    write_text_atomic(str(path), text, newline="\r\n")
    assert path.read_bytes() == before
    back = load_points_archive(str(path))
    assert sorted(back) == [2026241, 2026242]
    assert back[2026242].points == tuple(sorted(canonical_points))


def test_lf_input_is_normalized_to_crlf_by_default(tmp_path, write_file):
    """写回默认 newline='\\r\\n'：LF 源会按契约规范化为 CRLF（非字节往返）。

    说明：data_io 只保证「CRLF 进 → CRLF 出」；LF 源需调用方传
    newline=detect_newline(text) 才能保持原位。此处固化该既有行为。
    """
    path = write_file(tmp_path / "lf.txt", "a\nb\n", newline="\n")
    assert path.read_bytes() == b"a\nb\n"

    text = read_text(str(path))
    write_text_atomic(str(path), text)                # 默认 CRLF
    assert path.read_bytes() == b"a\r\nb\r\n"

    # 显式使用 detect_newline 时保持 LF 原位
    path2 = write_file(tmp_path / "lf2.txt", "a\nb\n", newline="\n")
    t2 = read_text(str(path2))
    write_text_atomic(str(path2), t2, newline=detect_newline(t2))
    assert path2.read_bytes() == b"a\nb\n"


def test_write_text_atomic_writes_utf8_without_bom(tmp_path):
    path = tmp_path / "out" / "f.txt"
    write_text_atomic(str(path), "date:2026-01-01,period:2026001,points:01\n")
    blob = path.read_bytes()
    assert not blob.startswith(b"\xef\xbb\xbf")
    assert blob.decode("utf-8") == "date:2026-01-01,period:2026001,points:01\r\n"


def test_atomic_write_interrupt_keeps_original_bytes(tmp_path, write_file, monkeypatch):
    """§8.2：写盘中途失败 → 原文件字节不变，且不残留 .tmp。"""
    path = write_file(tmp_path / "daily_points.txt",
                      "date:2026-06-10,period:2026151,points:01\n", newline="\r\n")
    before = path.read_bytes()

    def boom(*args, **kwargs):
        raise OSError("模拟替换失败")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_text_atomic(str(path), "date:2026-06-11,period:2026152,points:02\n")

    assert path.read_bytes() == before
    assert not (tmp_path / "daily_points.txt.tmp").exists()


# ── sort_draws / Draw 契约 ────────────────────────────────────

def test_sort_draws_is_date_first_then_period(make_draw):
    a = make_draw(2026001, date(2026, 1, 5), range(1, 21))
    b = make_draw(2026002, date(2026, 1, 5), range(21, 41))     # 同日期更大期号
    c = make_draw(2026003, date(2026, 1, 6), range(1, 21))
    ordered = sort_draws([a, b, c])
    assert [d.period for d in ordered] == [2026003, 2026002, 2026001]


def test_draw_helper_properties():
    d = Draw(period=2026152, date=date(2026, 6, 11), numbers=(1, 2, 3))
    assert d.period_str == "2026152"
    assert d.year == 2026
    assert d.index_in_year == 152
    assert d.numbers_set == frozenset({1, 2, 3})
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.period = 1                                   # frozen dataclass


# ── 真实共享档案（只读复核，不写入）─────────────────────────

def test_real_shared_archives_are_crlf_and_parse(cfg):
    """用项目 config.yaml 解析出的真实档案复核换行与排序契约（只读）。"""
    assert cfg.read_only is True                      # §8.5 默认只读
    if not cfg.shared_history_file.exists():
        pytest.skip("共享开奖档案不存在，跳过只读复核")

    text = read_text(str(cfg.shared_history_file))
    assert detect_newline(text) == "\r\n"             # §8.4 实测纯 CRLF
    assert "\r\r\n" not in text

    draws = load_draws(str(cfg.shared_history_file))
    assert len(draws) > 0
    assert all(len(d.numbers) == DRAW_SIZE for d in draws)
    dates = [d.date for d in draws]
    assert dates == sorted(dates, reverse=True)        # §2.3 以日期降序
    assert all(d.period % 1000 >= 1 for d in draws)    # 年内序号从 001 起

    if cfg.shared_points_file.exists():
        ptext = read_text(str(cfg.shared_points_file))
        assert detect_newline(ptext) == "\r\n"
        entries = load_points_archive(str(cfg.shared_points_file))
        assert entries
        assert all(len(e.points) == POINTS_SIZE for e in entries.values())
        assert all(e.date is not None for e in entries.values())
