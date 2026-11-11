# -*- coding: utf-8 -*-
"""
点位重码全量追踪引擎自动化单元测试 (TestPointRepeatTracker)
==========================================================
验证点位重码账本从目前最早录入点位期号（2025316）开始全量核算、
覆盖全部 307+ 期点位数据、Excel 生成与图1绿色高亮样式。
"""

import os
import sys
import pytest
import openpyxl

# 加入项目路径
_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_DIR)
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from backend.modules.point_repeat_tracker import (
    load_daily_points,
    load_draw_history,
    calculate_full_history_ledger,
    sync_and_update_tracker,
    EXCEL_OUTPUT_FILE,
    LEDGER_PATH
)


def test_points_coverage_from_earliest():
    """测试覆盖范围：必须从目前已录入的最早一期（2025316）开始，覆盖300+期"""
    points_dict = load_daily_points()
    assert len(points_dict) >= 300
    sorted_periods = sorted(points_dict.keys(), key=lambda x: int(x))
    
    # 最早录入期必须是 2025316
    assert sorted_periods[0] == "2025316"
    # 最新录入期必须包含 2026271
    assert "2026271" in sorted_periods


def test_full_history_ledger_calculation():
    """测试全量账本计算：从最早点位期连续核算至最新期"""
    ledger = calculate_full_history_ledger()
    assert len(ledger) >= 300
    
    # 首期为最早录入点位
    assert ledger[0]["period"] == "2025316"
    # 最后一期为最新点位期，状态合规
    assert int(ledger[-1]["period"]) >= 2026271
    if ledger[-1]["is_drawn"]:
        assert ledger[-1]["hit_count"] is not None
    else:
        assert ledger[-1]["hit_count"] is None

    # 中间已开奖期验证
    drawn_items = [x for x in ledger if x["is_drawn"]]
    assert len(drawn_items) >= 290
    for item in drawn_items[:5]:
        assert item["hit_count"] is not None
        assert isinstance(item["hit_count"], int)
        assert item["hit_count"] >= 0


def test_sync_and_update_full_excel():
    """测试端到端全量同步与Excel生成"""
    ledger = sync_and_update_tracker(target_period="2026271")
    assert len(ledger) >= 300
    assert os.path.exists(LEDGER_PATH)
    assert os.path.exists(EXCEL_OUTPUT_FILE)


def test_excel_styling_and_green_fill():
    """测试生成的 Excel 表头与图1同款绿色高亮样式"""
    wb = openpyxl.load_workbook(EXCEL_OUTPUT_FILE, data_only=True)
    ws = wb.active

    # 验证表头文字
    assert "序号" in str(ws.cell(1, 1).value)
    assert "期数" in str(ws.cell(1, 2).value)
    assert "点位重码" in str(ws.cell(1, 3).value)
    assert "出号个数" in str(ws.cell(1, 4).value)

    # 验证行数：表头1行 + 307期数据 >= 308行
    assert ws.max_row >= 308

    # 检查已开奖行（如第2行对应2025316期）出号个数单元格背景是否为绿色
    col_d_fill_rgb = ws.cell(2, 4).fill.start_color.rgb
    assert "00B050" in str(col_d_fill_rgb)
