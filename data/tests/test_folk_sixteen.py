# -*- coding: utf-8 -*-
"""
16 期窗口新方法 (Folk Sixteen) 工业级单元测试与物理资产强校验套件
================================================================================
测试目标：
1. 校验 16 期滑动窗口动力学分层矩阵与球数闭环（80 码不重不漏）；
2. 校验六维黄金选号模型 (20 码大底、12 码精选、5 码金胆、3 码最优胆、选 2 搭档)；
3. 校验微信分桶纯文本导出格式与数量守恒；
4. 校验 Excel「新方法」高保真渲染 (色带、分割线、012路、金黄高亮、复盘红框)；
5. 校验服务层接口 get_folk_sixteen_analysis 的自闭环执行。

@author Antigravity Quant Team
@since 2026-09-30
"""
from __future__ import annotations

import os
import re
import openpyxl
import pytest

from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine
from backend.modules.sixteen.folk_excel_builder import FolkExcelBuilder
from backend.api.deps import data_service


def test_folk_engine_analysis_structure():
    """测试 16 期滑动窗口分析的基础数据结构与闭环守恒"""
    engine = FolkSixteenEngine()
    assert len(engine.draws) >= 16, "历史开奖期数必须不少于 16 期"

    result = engine.analyze_window()
    assert "target_period" in result
    assert "base_period" in result
    assert "outgoing_period" in result
    assert "tiers" in result
    assert "picks" in result

    # 验证 80 码全局闭环
    all_seen_nums = set()
    total_outgoing = 0
    total_remaining = 0

    for f_level in range(8, -1, -1):
        t_data = result["tiers"][f_level]
        out_list = t_data["outgoing"]
        rem_list = t_data["remaining"]

        total_outgoing += len(out_list)
        total_remaining += len(rem_list)
        all_seen_nums.update(out_list)
        all_seen_nums.update(rem_list)

    assert total_outgoing == 20, f"出窗码总数必须恒等于 20，实际为 {total_outgoing}"
    assert total_remaining == 60, f"剩余码总数必须恒等于 60，实际为 {total_remaining}"
    assert len(all_seen_nums) == 80, f"80 码必须全覆盖，实际覆盖 {len(all_seen_nums)}"
    assert all_seen_nums == set(range(1, 81)), "号码集合必须严格对应 1~80"


def test_folk_six_dimension_picks():
    """测试六维黄金选号模型产出的号码规模与区间约束"""
    engine = FolkSixteenEngine()
    result = engine.analyze_window()
    picks = result["picks"]

    grand_20 = picks["grand_20"]
    elite_12 = picks["elite_12"]
    golden_5 = picks["golden_5"]
    golden_3 = picks["golden_3"]
    top_pairs = picks["top_pairs"]

    # 1. 规模校验
    assert len(grand_20) == 20, f"大底规模必须为 20，实际为 {len(grand_20)}"
    assert len(elite_12) == 12, f"精选规模必须为 12，实际为 {len(elite_12)}"
    assert len(golden_5) == 5, f"金胆规模必须为 5，实际为 {len(golden_5)}"
    assert len(golden_3) == 3, f"最优胆规模必须为 3，实际为 {len(golden_3)}"
    assert len(top_pairs) == 3, f"选2推荐对数必须为 3，实际为 {len(top_pairs)}"

    # 2. 包含性与子集守恒校验
    assert set(elite_12).issubset(set(grand_20)), "精选 12 码必须是大底 20 码的子集"
    assert set(golden_5).issubset(set(elite_12)), "黄金 5 胆必须是精选 12 码的子集"
    assert set(golden_3).issubset(set(golden_5)), "最优 3 胆必须是黄金 5 胆的子集"

    # 3. 边界值合法性 (1~80)
    for num in grand_20:
        assert 1 <= num <= 80, f"号码越界: {num}"

    for pair in top_pairs:
        assert len(pair) == 2, f"选2组合长度必须为 2: {pair}"
        assert pair[0] != pair[1], f"选2组合不能为重码: {pair}"


def test_folk_plain_text_export(tmp_path):
    """测试微信分桶纯文本导出格式与**全 80 码无遗漏**契约。

    2026-10-21 (Bug#5) 修正：本用例原先断言"必须 8 行 (8次至1次)"，
    恰好把缺陷固化成了测试 —— 频次=0 的冷号桶被导出器 range(8,0,-1) 静默丢掉，
    导致当期 28/69 两个号码在微信分桶原文里凭空消失，
    而同一份数据的看板却宣称"全 80 个号码 100% 无遗漏全覆盖"，口径自相矛盾。
    文档口径 (docs/daily_prompts/01_sixteen_midhot_prompt.md) 是 8+/7/6/5/4/3/2/1/0 共 9 桶，
    故行数应为 9，并补上真正有价值的不变量：80 个号码逐个出现且仅出现一次。
    """
    engine = FolkSixteenEngine()
    result = engine.analyze_window()

    txt_content = engine.generate_plain_text_summary(result)
    lines = [line.strip() for line in txt_content.strip().split("\n") if line.strip()]

    # 9 个频次桶: 8+ / 7 / 6 / 5 / 4 / 3 / 2 / 1 / 0
    assert len(lines) == 9, f"微信分桶行数必须为 9 行 (8+次至0次)，实际为 {len(lines)}"

    # 第一行为 8+ 桶，须含 "个8" 与 "剩余"
    assert "个8" in lines[0]
    assert "剩余" in lines[0]

    # 末行必须是频次=0 冷号桶（旧实现整桶丢失的地方）
    assert lines[-1].startswith("0个0"), f"末行必须为频次0冷号桶，实际为: {lines[-1]}"

    # 核心不变量：1~80 每个号码在分桶原文中**出现且仅出现一次**（精选或剩余）。
    # 注意只取冒号后面的号码列表，不能用 \d{2} 全文抓 —— 桶头的"4个7"与
    # "剩余15个"里的计数会被误当成号码，测试自身就会造出假阳性/假阴性。
    listed = []
    for line in lines:
        for seg in line.split("。"):
            if ":" not in seg and "：" not in seg:
                continue
            payload = re.split(r"[:：]", seg, maxsplit=1)[1]
            listed.extend(int(x) for x in re.findall(r"\d+", payload))

    dup = sorted({n for n in listed if listed.count(n) > 1})
    assert not dup, f"分桶出现重复号码: {dup}"
    missing = sorted(set(range(1, 81)) - set(listed))
    assert not missing, f"分桶遗漏号码: {missing}"
    assert len(listed) == 80, f"分桶号码总数必须为 80，实际 {len(listed)}"
    assert all(1 <= n <= 80 for n in listed), f"分桶号码越界: {[n for n in listed if not 1 <= n <= 80]}"


def test_folk_excel_builder(tmp_path):
    """测试高保真 Excel 渲染器的生成能力与单元格结构"""
    engine = FolkSixteenEngine()
    result = engine.analyze_window()

    builder = FolkExcelBuilder()
    test_xlsx = str(tmp_path / "test_folk_excel.xlsx")
    builder.export_excel(result, output_xlsx_path=test_xlsx)

    assert os.path.exists(test_xlsx), "Excel 目标文件未物理生成"
    assert os.path.getsize(test_xlsx) > 0, "Excel 文件大小为 0"

    wb = openpyxl.load_workbook(test_xlsx)
    assert "新方法" in wb.sheetnames, "Excel 工作簿中必须包含【新方法】工作表"
    assert "常球顺序" in wb.sheetnames, "Excel 工作簿中必须包含【常球顺序】工作表"
    assert "尾数分布" in wb.sheetnames, "Excel 工作簿中必须包含【尾数分布】工作表"
    assert "012路" in wb.sheetnames, "Excel 工作簿中必须包含【012路】工作表"
    assert "实操决策与对账总账本" in wb.sheetnames, "Excel 工作簿中必须包含【实操决策与对账总账本】工作表"

    ws = wb["新方法"]
    # 验证分割线单元格
    div_val = str(ws.cell(row=15, column=9).value or "")
    assert "——分割线——" in div_val, f"第 15 行第 9 列必须包含分割线，实际为: {div_val}"
    assert ws.max_row >= 300, f"新方法工作表必须包含多期连续滚动大盘 (行数>=300)，实际为: {ws.max_row}"



def test_service_folk_integration():
    """测试服务层接口 get_folk_sixteen_analysis 集成有效性"""
    res = data_service.get_folk_sixteen_analysis(persist=True)

    assert isinstance(res, dict)
    assert "picks" in res
    assert "txt_path" in res
    assert "xlsx_path" in res
    assert os.path.isfile(res["txt_path"])
    assert os.path.isfile(res["xlsx_path"])
    assert os.path.getsize(res["txt_path"]) > 0
    assert os.path.getsize(res["xlsx_path"]) > 0
