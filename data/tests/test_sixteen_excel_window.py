# -*- coding: utf-8 -*-
"""
Excel 同款 16 窗开奖矩阵与多维大盘全景单测 (单 Sheet 模式)
=============================================================
涵盖：1头口径、尾数分布、遗漏计算、频次桶分布、单 Sheet 终极全景工作表
"""
import pytest
from backend.modules.sixteen.excel_window_table import (
    HEAD_DEFS,
    ZONE_DEFS,
    TAIL_DEFS,
    WINDOW_SIZE,
    build_excel_window_table,
    export_excel_workbook,
    render_window_markdown,
)
from backend.modules.sixteen.sixteen_engine import load_draws_from_file


def test_head_defs_one_head_is_10_19_not_zone1():
    heads = {n: (lo, hi) for n, lo, hi in HEAD_DEFS}
    assert heads["1头"] == (10, 19)
    assert heads["0头"] == (1, 9)


def test_tail_defs():
    tails = {n: t for n, t in TAIL_DEFS}
    assert len(tails) == 10
    assert tails["0尾"] == 0
    assert tails["9尾"] == 9


def test_excel_window_matches_latest_16():
    draws = load_draws_from_file()
    assert len(draws) >= WINDOW_SIZE
    table = build_excel_window_table(draws, window_size=WINDOW_SIZE, history_tail=None)
    assert table["status"] == "ok"
    assert len(table["window_rows"]) == WINDOW_SIZE
    assert len(table["matrix_rows"]) == len(draws)
    assert table["matrix_rows"][0]["period"] == draws[0]["period"]
    assert table["window_end_period"] == draws[-1]["period"]
    assert table["window_start_period"] == draws[-WINDOW_SIZE]["period"]

    total_1h = sum(1 for r in table["window_rows"] for n in r["nums"] if 10 <= n <= 19)
    assert table["one_head"]["countifs_total"] == total_1h

    tail0 = next(s for s in table["tail_stats"] if s["name"] == "0尾")
    actual_tail0 = sum(1 for r in table["window_rows"] for n in r["nums"] if n % 10 == 0)
    assert tail0["countifs_total"] == actual_tail0

    balls_80 = table.get("balls_80")
    assert balls_80 is not None
    assert len(balls_80["balls"]) == 80
    assert len(balls_80["bucket_stats"]) == 9


def test_excel_export_two_sheets_panoramic(tmp_path):
    draws = load_draws_from_file()
    table = build_excel_window_table(draws, window_size=WINDOW_SIZE, history_tail=None)
    md = render_window_markdown(table)
    assert "1头" in md and "10-19" in md
    assert "尾数分布" in md
    assert "频次桶分布" in md

    xlsx = tmp_path / "test_two_sheets.xlsx"
    export_excel_workbook(table, str(xlsx), include_full_matrix=True)
    assert xlsx.exists() and xlsx.stat().st_size > 50_000

    from openpyxl import load_workbook
    wb = load_workbook(str(xlsx), read_only=True)
    sheet_names = wb.sheetnames
    assert len(sheet_names) == 2
    assert sheet_names[0] == "16窗量化操盘看板"
    assert table.get("walk_forward_30") is not None
    assert len(table["walk_forward_30"]["records"]) == 30

    ws1 = wb["16窗量化操盘看板"]
    # Sheet 1 包含 16 期数据 + 3 行聚合统计 + 从 A22 开始的完整分析看板 + 30期盲测总账本 (约 200 行，单屏直接垂直滚动)
    assert ws1.max_row >= 195
    assert ws1.max_column >= 61

    ws2 = wb["全历史开奖矩阵"]
    assert ws2.max_row >= len(draws) + 1
    wb.close()



