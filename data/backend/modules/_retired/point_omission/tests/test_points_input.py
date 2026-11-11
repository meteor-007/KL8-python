# -*- coding: utf-8 -*-
"""点位解析鲁棒性与录入契约（§8.3 / §8.4 / §2.1）。

覆盖 §10.2 的 test_parse_points_separators / test_parse_points_excel_multiline /
test_validate_core_points / test_period_cross_year / test_period_no_holiday_assumption。
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from kl8.data_io import (POINTS_SIZE, PointEntry, load_points_archive,
                         parse_points_input, validate_core_points)
from kl8.points_input import (MAX_INDEX_IN_YEAR, TargetInfo, entry_from_raw,
                              infer_target, next_period_after, save_points)

SEPARATORS = [" ", ",", "、", "-", ";", "\n", "\t", "，", "；", "|"]


def _text(points, sep: str) -> str:
    return sep.join(f"{x:02d}" for x in points)


# ── 7 种分隔符混排 → 同一结果 ─────────────────────────────────

@pytest.mark.parametrize("sep", SEPARATORS)
def test_parse_single_separator_families(canonical_points, sep):
    got = parse_points_input(_text(canonical_points, sep))
    assert got == sorted(canonical_points)
    assert len(got) == POINTS_SIZE


def test_parse_seven_separators_all_equal(canonical_points):
    """空格/逗号/顿号/连字符/分号/换行/制表符 7 种 → 同一解析结果。"""
    seven = [" ", ",", "、", "-", ";", "\n", "\t"]
    results = [parse_points_input(_text(canonical_points, s)) for s in seven]
    assert all(r == sorted(canonical_points) for r in results)
    assert len({tuple(r) for r in results}) == 1


def test_parse_mixed_separators_in_one_input(canonical_points):
    raw = ("  04\t10\r\n12  ,14 、16，20 ;22-27  30\n\n"
           "38；39|40\t54 59,62 、65-70 \r\n 74 75;80   ")
    assert parse_points_input(raw) == sorted(canonical_points)
    assert validate_core_points(parse_points_input(raw))[0] is True


def test_parse_excel_multiline_paste(canonical_points):
    """Excel 直接复制粘贴：多行 + 行内制表符 + 首尾空白 + 中间空行。"""
    vals = [f"{x:02d}" for x in canonical_points]
    lines = ["  ".join(vals[0:5]),
             "\t".join(vals[5:10]),
             "",
             "  " + " ".join(vals[10:15]) + "  ",
             "\t".join(vals[15:20])]
    raw = "\r\n".join(lines) + "\r\n\r\n"
    got = parse_points_input(raw)
    assert got == sorted(canonical_points)
    assert len(got) == 20
    assert validate_core_points(got)[0] is True


# ── 解析的清洗规则 ────────────────────────────────────────────

def test_parse_deduplicates_and_sorts():
    assert parse_points_input("04 04 10 10 10 12 05") == [4, 5, 10, 12]
    assert parse_points_input("80 40 01") == [1, 40, 80]


def test_parse_drops_out_of_range_and_non_numeric_tokens():
    """越界与非法 token 被静默丢弃（随后由 validate 报数量异常）。"""
    assert parse_points_input("0 81 82 abc 01 02 100") == [1, 2]
    assert parse_points_input("01 02 03 900") == [1, 2, 3]


def test_parse_empty_inputs():
    assert parse_points_input("") == []
    assert parse_points_input("   \n\t \r\n ") == []
    assert parse_points_input("abc,def") == []


def test_parse_required_20_from_19_tokens(canonical_points):
    """19 个号码的输入解析出 19 个 → 必须被契约拒绝。"""
    got = parse_points_input(_text(canonical_points[:19], " "))
    assert len(got) == 19
    ok, msg = validate_core_points(got)
    assert ok is False and "19" in msg


# ── 录入契约校验 ──────────────────────────────────────────────

def test_validate_accepts_exactly_20(canonical_points):
    ok, msg = validate_core_points(list(canonical_points))
    assert ok is True and msg == "校验通过"
    assert validate_core_points(tuple(canonical_points))[0] is True


def test_validate_rejects_19_and_21(canonical_points):
    ok19, msg19 = validate_core_points(list(canonical_points[:19]))
    assert ok19 is False and "19" in msg19 and "20" in msg19
    ok21, msg21 = validate_core_points(list(canonical_points) + [3])
    assert ok21 is False and "21" in msg21 and "20" in msg21


def test_validate_rejects_duplicates(canonical_points):
    dup = list(canonical_points)
    dup[1] = dup[0]                                    # 20 个元素但有一个重复
    assert len(dup) == 20
    ok, msg = validate_core_points(dup)
    assert ok is False and "重复" in msg


def test_validate_rejects_zero_and_81(canonical_points):
    zero = [0] + list(canonical_points[1:])
    ok0, msg0 = validate_core_points(zero)
    assert ok0 is False and "越界" in msg0 and "[0]" in msg0

    over = list(canonical_points)
    over[0] = 81
    ok81, msg81 = validate_core_points(over)
    assert ok81 is False and "越界" in msg81 and "[81]" in msg81


def test_validate_rejects_non_list():
    ok, msg = validate_core_points("04 10 12")
    assert ok is False and "列表" in msg


# ── 期号推进：跨年与休市缺口 ──────────────────────────────────

def test_period_same_year_increment():
    assert next_period_after(2026150, date(2026, 9, 10)) == 2026151
    assert next_period_after(2026242, date(2026, 12, 31)) == 2026243
    assert next_period_after(2026001, date(2026, 1, 2)) == 2026002


def test_period_cross_year_resets_to_001():
    """§10.2：2026242 → 2027001；绝不允许 2026243 这种裸 +1。"""
    assert next_period_after(2026242, date(2027, 1, 1)) == 2027001
    assert next_period_after(2026351, date(2027, 1, 1)) == 2027001
    assert next_period_after(2026120, date(2027, 1, 1)) == 2027001


def test_period_year_index_cap_falls_back_to_new_year():
    """MAX_INDEX_IN_YEAR(999) 溢出分支（已修复）：期号必须单调递增。

    修复后兜底为 `(year + 1) * 1000 + 1`，故 2026999 在年内序号耗尽时
    推进到下一年的第 1 期（2027001），绝不倒退。
    """
    assert MAX_INDEX_IN_YEAR == 999
    got = next_period_after(2026999, date(2026, 12, 31))
    assert isinstance(got, int)
    assert got == 2027001                             # 溢出 → 新年首期，不倒退
    assert got > 2026999                              # 期号单调递增

    # 未溢出时仍严格 +1
    for index in (1, 150, 242, 351, 998):
        assert next_period_after(2026000 + index, date(2026, 12, 31)) == 2026000 + index + 1


def test_period_no_holiday_assumption():
    """不内置节假日日历：休市造成的期号缺口不被视为错误（§8.3）。"""
    # 春节缺口：2026119（腊月）之后是 2026120
    assert next_period_after(2026119, date(2026, 2, 20)) == 2026120
    # 国庆缺口：日期跳了 5 天，期号仍只 +1
    assert next_period_after(2026280, date(2026, 10, 8)) == 2026281
    # 期号本身不连续也不影响推断（以日期年份判定）
    assert next_period_after(2026999 - 1, date(2026, 12, 30)) == 2026999


# ── infer_target：用真实沙箱档案 ──────────────────────────────

@pytest.fixture
def sandbox_history(sandbox, make_history):
    """沙箱共享档案：最新一期 2026242 / 2026-09-09（与真实档案一致）。"""
    draws = make_history([
        (2026241, date(2026, 9, 8), list(range(1, 21))),
        (2026242, date(2026, 9, 9), list(range(21, 41))),
    ])
    sandbox.write_history(draws)
    return draws


def test_infer_target_from_latest_draw(sandbox, sandbox_history):
    info = infer_target(sandbox.cfg, sandbox_history, {})
    assert isinstance(info, TargetInfo)
    assert info.period == 2026243                     # 同年 +1，不得跨年
    assert info.date == date(2026, 9, 10)
    assert info.period_str == "2026243"
    assert info.already_input is False
    assert info.existing_points == ()
    assert "2026243" in info.render()


def test_infer_target_marks_already_input(sandbox, sandbox_history):
    existing = PointEntry(period=2026243, date=date(2026, 9, 10),
                          points=tuple(sorted(range(1, 21))))
    info = infer_target(sandbox.cfg, sandbox_history, {2026243: existing})
    assert info.already_input is True
    assert info.existing_points == existing.points
    assert "该期点位已存在" in info.render()


def test_infer_target_cross_year(make_history, sandbox):
    """最新一期在 12-31 → 目标期号为跨年的 2027001。"""
    draws = make_history([(2026242, date(2026, 12, 31), list(range(1, 21)))])
    info = infer_target(sandbox.cfg, draws, {})
    assert info.period == 2027001
    assert info.date == date(2027, 1, 1)


def test_infer_target_without_draws_uses_points_archive(sandbox):
    pts = {2026242: PointEntry(period=2026242, date=date(2026, 9, 9),
                               points=tuple(sorted(range(1, 21))))}
    info = infer_target(sandbox.cfg, [], pts)
    assert info.period == 2026243 and info.date == date(2026, 9, 10)


# ── 非交互录入 end-to-end（沙箱，写副本，不碰共享档案）─────────

def test_entry_from_raw_writes_cache_copy_with_crlf(sandbox, sandbox_history,
                                                    canonical_points):
    raw = _text(canonical_points, " ")
    result, info = entry_from_raw(sandbox.cfg, raw)

    assert result["status"] == "ok"
    assert result["action"] == "created"
    assert result["period"] == 2026243                 # 沿用推断出的目标期
    assert result["date"] == "2026-09-10"
    assert result["points"] == sorted(canonical_points)
    assert result["total_records"] == 1

    target = sandbox.cache_copy
    assert target.exists(), "read_only 模式必须写本项目副本"
    assert not sandbox.shared_points.exists(), "默认只读，绝不写共享档案"

    blob = target.read_bytes()
    assert b"\r\n" in blob and b"\r\r\n" not in blob
    assert blob.count(b"\r\n") == 1

    back = load_points_archive(str(target))
    assert list(back) == [2026243]
    assert back[2026243].points == tuple(sorted(canonical_points))
    assert back[2026243].date == date(2026, 9, 10)


def test_entry_from_raw_second_write_updates(sandbox, sandbox_history,
                                             canonical_points):
    entry_from_raw(sandbox.cfg, _text(canonical_points, " "))
    other = [x for x in range(1, 81) if x not in canonical_points][:20]
    result, _ = entry_from_raw(sandbox.cfg, _text(other, ","))
    assert result["status"] == "ok"
    assert result["action"] == "updated"
    assert result["total_records"] == 1
    back = load_points_archive(str(sandbox.cache_copy))
    assert back[2026243].points == tuple(sorted(other))


def test_entry_from_raw_rejects_invalid_without_writing(sandbox, sandbox_history,
                                                        canonical_points):
    result, info = entry_from_raw(sandbox.cfg, _text(canonical_points[:19], " "))
    assert result["status"] == "error"
    assert "19" in result["message"]
    assert info.period == 2026243
    assert not sandbox.cache_copy.exists()


def test_entry_from_raw_explicit_period_and_date(sandbox, sandbox_history,
                                                 canonical_points):
    result, _ = entry_from_raw(sandbox.cfg, _text(canonical_points, "、"),
                               period=2026244, d=date(2026, 9, 11))
    assert result["status"] == "ok"
    assert result["period"] == 2026244
    assert result["date"] == "2026-09-11"
    assert result["points_str"] == " ".join(f"{x:02d}" for x in sorted(canonical_points))


def test_save_points_validates_before_writing(sandbox, canonical_points):
    bad = save_points(sandbox.cfg, 2026243, date(2026, 9, 10),
                      [0] + list(canonical_points[1:]))
    assert bad["status"] == "error" and "越界" in bad["message"]
    assert not sandbox.cache_copy.exists()

    good = save_points(sandbox.cfg, 2026243, date(2026, 9, 10), list(canonical_points))
    assert good["status"] == "ok" and good["action"] == "created"
    assert sandbox.cache_copy.exists()

    skipped = save_points(sandbox.cfg, 2026243, date(2026, 9, 10),
                          list(canonical_points), overwrite=False)
    assert skipped["status"] == "skipped" and "已存在" in skipped["message"]


def test_roundtrip_parse_axis(sandbox, sandbox_history, canonical_points):
    """解析 → 校验 → 落盘 的完整链路，落盘行可被再次解析（两段锚定）。"""
    entry_from_raw(sandbox.cfg, _text(canonical_points, "\n"))
    text = sandbox.cache_copy.read_bytes().decode("utf-8")
    line = text.strip()
    assert line.startswith("date:2026-09-10,period:2026243,points:")
    # 日期里的 '-' 不会污染号码分词
    assert line.count("date:") == 1
    recovered = load_points_archive(str(sandbox.cache_copy))[2026243]
    assert len(recovered.points) == 20
    assert tuple(sorted(canonical_points)) == recovered.points
