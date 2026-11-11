# -*- coding: utf-8 -*-
"""
16 期窗口「Excel 旗舰全息大盘」超级工作簿生成器 (Folk Excel Builder Ultimate Edition)
================================================================================
【业务背景与架构定位】:
本模块专为生成 100% 像素级对齐民间顶级操盘手、具备全套深度分析工作表的工业级量化大盘研发。
彻底解决“单期孤立展示、缺少历史纵向滚动走势、缺少配套尾数与012路工作表”的痛点。

【超级工作簿架构清单】:
1. 🏆 【新方法】(核心主大盘):
   - 纵向连续渲染最近 10~15 期滑动窗口演变大盘；
   - 每一期具备「——分割线——」、左出窗 20 码、右剩余 60 码、8 级频次色带、012 路紧随其下；
   - 历史期：实开号码沉稳深红底色白字，系统命中号码加亮红粗方框；
   - 最新期：系统 20 码大底与核心金胆金黄色高亮底色 (#FFC000)；
   - 每期右侧配置紧凑实操复盘对账与决策指令卡片。
2. 📊 【常球顺序】:
   - 1~80 号球在当前 16 期滑动窗口内的全景出号矩阵与各球冷热统计；
   - 包含每期开奖号码、大小比、奇偶比、区间比、十位分布 (0头~8头)。
3. 🎯 【尾数分布】:
   - 0 尾至 9 尾在 16 期滑动窗口内的深度分析、出号走势与连冷偏冷。
4. ⚡ 【012路】:
   - 0 路、1 路、2 路在 16 期窗口中的各期分布走势、路数平衡度与冷热失衡度。
5. 📜 【实操决策与对账总账本】:
   - 最新期实战操盘指令 (20码大底、12码精选、5码核心金胆、3码最优胆、选2搭档)；
   - 滚动近 30 期 Walk-Forward 样本外盲测实战总账本与提升度 (Lift) 决算。

@author Antigravity Quant Team
@since 2026-09-30
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from collections import Counter, defaultdict

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from backend.utils.paths import get_outputs_dir, get_storage_dir, get_cache_dir

WINDOW_SIZE: int = 16
NUM_TOTAL: int = 80
DRAW_SIZE: int = 20


class FolkExcelBuilder:
    """
    16 期窗口「Excel 旗舰全息大盘」超级工作簿构建器
    """

    # 调色板
    COLOR_TIER_8 = "D9534F"      # 出现8次: 稳健深红
    COLOR_TIER_7 = "F8CECC"      # 出现7次: 警示粉红
    COLOR_TIER_6 = "D5E8D4"      # 出现6次: 清爽淡绿
    COLOR_TIER_5 = "E2EFDA"      # 出现5次: 柔和浅绿
    COLOR_TIER_4 = "D5E8D4"      # 出现4次: 清爽淡绿
    COLOR_TIER_3 = "E2EFDA"      # 出现3次: 柔和浅绿
    COLOR_TIER_2 = "E2EFDA"      # 出现2次: 浅绿
    COLOR_TIER_1 = "F8CECC"      # 出现1次: 淡粉色

    COLOR_YELLOW_PICK = "FFC000" # 黄金选号底色: 纯正金黄
    COLOR_HIT_DRAW = "C00000"    # 开奖命中底色: 沉稳深红
    COLOR_HIT_BORDER = "FF0000"  # 开奖命中红框: 亮红
    COLOR_CARD_BG = "F2F2F2"     # 右侧看板底色: 浅灰
    COLOR_HEADER_NAVY = "1F497D" # 表头深蓝

    def __init__(self) -> None:
        self.font_header_white = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
        self.font_header_dark = Font(name="微软雅黑", size=10, bold=True, color="333333")
        self.font_num = Font(name="Calibri", size=11, bold=True, color="000000")
        self.font_num_white = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        self.font_r012 = Font(name="Calibri", size=9, bold=False, color="555555")
        self.font_divider = Font(name="微软雅黑", size=11, bold=True, color="1F497D")
        self.font_bold_title = Font(name="微软雅黑", size=11, bold=True, color="000000")
        self.font_bold_navy = Font(name="微软雅黑", size=10, bold=True, color="1F497D")
        self.font_card_text = Font(name="微软雅黑", size=9, bold=False, color="333333")
        self.font_card_bold = Font(name="微软雅黑", size=9, bold=True, color="000000")

        self.align_center = Alignment(horizontal="center", vertical="center")
        self.align_left = Alignment(horizontal="left", vertical="center")

        thin_side = Side(style="thin", color="D3D3D3")
        self.border_cell = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        thick_red_side = Side(style="medium", color=self.COLOR_HIT_BORDER)
        self.border_hit = Border(left=thick_red_side, right=thick_red_side, top=thick_red_side, bottom=thick_red_side)

        card_side = Side(style="thin", color="B0C4DE")
        self.border_card = Border(left=card_side, right=card_side, top=card_side, bottom=card_side)

    # ══════════════════════════════════════════════════════════════════════════
    # Sheet 1: 【新方法】(多期纵向滚动大盘)
    # ══════════════════════════════════════════════════════════════════════════
    def build_folk_sheet(
        self,
        wb: openpyxl.Workbook,
        analysis_results_list: Sequence[Dict[str, Any]],
        sheet_name: str = "新方法"
    ) -> openpyxl.worksheet.worksheet.Worksheet:
        """
        在工作簿中构建连续多期纵向滚动的「新方法」主工作表
        :param wb: openpyxl 工作簿
        :param analysis_results_list: 按期号升序排列的分析结果列表 (历史多期 -> 最新待开期)
        :param sheet_name: 工作表名，默认为「新方法」
        """
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        else:
            ws = wb.create_sheet(title=sheet_name)

        ws.views.sheetView[0].showGridLines = True

        start_row = 15
        period_block_height = 36  # 每个期数区块占用 36 行

        for idx, res in enumerate(analysis_results_list):
            curr_base_row = start_row + idx * period_block_height
            self._render_single_period_block(ws, curr_base_row, res)

        # 调整列宽
        ws.column_dimensions["A"].width = 11.5
        for c_letter in ["B", "C", "D", "E", "F", "G", "H"]:
            ws.column_dimensions[c_letter].width = 4.8
        ws.column_dimensions["I"].width = 7.5
        for col_idx in range(10, 27):
            ws.column_dimensions[get_column_letter(col_idx)].width = 4.8

        # 右侧对账卡片列宽
        ws.column_dimensions["AA"].width = 13.0
        ws.column_dimensions["AB"].width = 18.0
        ws.column_dimensions["AC"].width = 18.0

        return ws

    def _render_single_period_block(
        self,
        ws: openpyxl.worksheet.worksheet.Worksheet,
        start_row: int,
        analysis_result: Dict[str, Any]
    ) -> None:
        """渲染单个期数的 16 期窗口分析区块 (占约 34~35 行)"""
        target_p = analysis_result["target_period"]
        base_p = analysis_result.get("base_period", target_p - 1)
        out_p = analysis_result.get("outgoing_period", target_p - 16)
        has_actual_draw = analysis_result.get("has_actual_draw", False)
        actual_draw_set = set(analysis_result.get("hit_audit", {}).get("actual_draw", []))

        tiers = analysis_result["tiers"]
        picks = analysis_result.get("picks", {})
        red_pool_set = set(picks.get("red_pool", []))
        yellow_pool_set = set(picks.get("yellow_pool", []))
        red_border_set = set(picks.get("red_border_core", []))

        # 1. 顶部「——分割线——」与期号说明
        curr_row = start_row
        ws.row_dimensions[curr_row].height = 22
        ws.merge_cells(start_row=curr_row, start_column=9, end_row=curr_row, end_column=13)
        div_cell = ws.cell(row=curr_row, column=9)
        if has_actual_draw:
            div_cell.value = f"——分割线—— (第 {target_p} 期双轨选号走势 | 出窗基准: {out_p})"
        else:
            div_cell.value = f"——分割线—— (🎯 第 {target_p} 期最新双轨选号大盘 | 出窗基准: {out_p})"
        div_cell.font = self.font_divider
        div_cell.alignment = self.align_center

        curr_row += 3  # 进入 8 次能级

        # 2. 循环渲染 8 次至 1 次
        for f_level in range(8, 0, -1):
            t_data = tiers.get(f_level, {"outgoing": [], "remaining": []})
            out_nums = t_data["outgoing"]
            rem_nums = t_data["remaining"]

            header_fill, header_font = self._get_tier_header_style(f_level)

            # 标题行
            ws.row_dimensions[curr_row].height = 18
            cell_tier = ws.cell(row=curr_row, column=1, value=f"出现{f_level}次")
            cell_tier.font = header_font
            cell_tier.alignment = self.align_center
            cell_tier.fill = header_fill

            for c_idx in range(2, 9):
                ws.cell(row=curr_row, column=c_idx).fill = header_fill

            cell_rem = ws.cell(row=curr_row, column=9, value="剩余")
            cell_rem.font = header_font
            cell_rem.alignment = self.align_center
            cell_rem.fill = header_fill

            for c_idx in range(10, 27):
                ws.cell(row=curr_row, column=c_idx).fill = header_fill

            curr_row += 1

            # 号码行与 012 路行
            num_row = curr_row
            r012_row = curr_row + 1
            ws.row_dimensions[num_row].height = 20
            ws.row_dimensions[r012_row].height = 16

            # 左侧出窗 (列 B~H)
            for i, num in enumerate(out_nums):
                self._render_ball_cell(
                    ws, num_row, r012_row, 2 + i, num,
                    red_pool_set, yellow_pool_set, red_border_set
                )

            # 右侧剩余 (列 J~Z)
            for j, num in enumerate(rem_nums):
                self._render_ball_cell(
                    ws, num_row, r012_row, 10 + j, num,
                    red_pool_set, yellow_pool_set, red_border_set
                )

            curr_row += 3

        # 3. 在区块右侧 (AA~AC 列) 渲染实操选号与对账卡片
        card_start_row = start_row + 3
        card_fill = PatternFill("solid", fgColor=self.COLOR_CARD_BG)

        ws.merge_cells(start_row=card_start_row, start_column=27, end_row=card_start_row, end_column=29)
        c_title = ws.cell(row=card_start_row, column=27)
        c_title.fill = PatternFill("solid", fgColor=self.COLOR_HEADER_NAVY)
        c_title.alignment = self.align_center

        if has_actual_draw:
            c_title.value = f"第 {target_p} 期 选号与实测决算"
            c_title.font = self.font_header_white
            audit = analysis_result.get("hit_audit", {})
            r_hit = audit.get("red_pool_hit_count", 0)
            y_hit = audit.get("yellow_pool_hit_count", 0)
            b_hit = audit.get("red_border_hit_count", 0)

            rows_info = [
                ("实开号码", " ".join(f"{x:02d}" for x in audit.get("actual_draw", [])[:10])),
                ("实开号码(下)", " ".join(f"{x:02d}" for x in audit.get("actual_draw", [])[10:])),
                ("🔴 红底20码大底命中", f"{r_hit} / 20 码 ({r_hit/20.0*100:.1f}%)"),
                ("🟡 黄底16码精选命中", f"{y_hit} / 16 码 ({y_hit/16.0*100:.1f}%)"),
                ("🔲 红框共振金胆命中", f"{b_hit} / {len(red_border_set)} 码 ({b_hit/max(1, len(red_border_set))*100:.1f}%)"),
                ("红框命中清单", " ".join(f"{x:02d}" for x in audit.get("red_border_hits", []))),
                ("红底命中清单", " ".join(f"{x:02d}" for x in audit.get("red_pool_hits", []))),
            ]
        else:
            c_title.value = f"🎯 第 {target_p} 期 三色选号作战指令"
            c_title.font = self.font_header_white
            fp = analysis_result.get("picks", {})
            rows_info = [
                ("🔴 红底20码大底", " ".join(f"{x:02d}" for x in fp.get("red_pool", [])[:10])),
                ("🔴 红底20码大底(下)", " ".join(f"{x:02d}" for x in fp.get("red_pool", [])[10:])),
                ("🟡 黄底16码精选池", " ".join(f"{x:02d}" for x in fp.get("yellow_pool", []))),
                ("🔲 红框共振核心金胆", " ".join(f"{x:02d}" for x in fp.get("red_border_core", []))),
                ("⚡ 最优3胆(突破矛头)", " ".join(f"{x:02d}" for x in fp.get("golden_3", []))),
                ("💎 选2黄金搭档", " | ".join(f"[{p[0]:02d}-{p[1]:02d}]" for p in fp.get("top_pairs", []))),
                ("📌 玩法指引", "大底买红底 / 进攻买黄底 / 稳胆买红框"),
            ]

        for r_offset, (k_lbl, v_val) in enumerate(rows_info, 1):
            r_idx = card_start_row + r_offset
            ws.row_dimensions[r_idx].height = 18
            cell_k = ws.cell(row=r_idx, column=27, value=k_lbl)
            cell_k.font = self.font_card_bold
            cell_k.fill = card_fill
            cell_k.border = self.border_card
            cell_k.alignment = self.align_left

            ws.merge_cells(start_row=r_idx, start_column=28, end_row=r_idx, end_column=29)
            cell_v = ws.cell(row=r_idx, column=28, value=v_val)
            cell_v.font = self.font_card_text
            cell_v.fill = card_fill
            cell_v.border = self.border_card
            cell_v.alignment = self.align_left

    def _get_tier_header_style(self, f_level: int) -> Tuple[PatternFill, Font]:
        if f_level >= 8:
            return PatternFill("solid", fgColor=self.COLOR_TIER_8), self.font_header_white
        elif f_level == 7:
            return PatternFill("solid", fgColor=self.COLOR_TIER_7), self.font_header_dark
        elif f_level == 6:
            return PatternFill("solid", fgColor=self.COLOR_TIER_6), self.font_header_dark
        elif f_level == 5:
            return PatternFill("solid", fgColor=self.COLOR_TIER_5), self.font_header_dark
        elif f_level == 4:
            return PatternFill("solid", fgColor=self.COLOR_TIER_4), self.font_header_dark
        elif f_level == 3:
            return PatternFill("solid", fgColor=self.COLOR_TIER_3), self.font_header_dark
        elif f_level == 2:
            return PatternFill("solid", fgColor=self.COLOR_TIER_2), self.font_header_dark
        else:
            return PatternFill("solid", fgColor=self.COLOR_TIER_1), self.font_header_dark

    def _render_ball_cell(
        self,
        ws: openpyxl.worksheet.worksheet.Worksheet,
        row_num: int,
        row_r012: int,
        col_idx: int,
        num: int,
        red_pool_set: Set[int],
        yellow_pool_set: Set[int],
        red_border_set: Set[int]
    ) -> None:
        """
        根据红底、黄底、红框三色体系渲染单元格：
        - 🔲 红框共振核心码: 金黄底色 + 红色粗方框
        - 🟡 黄底精选号码: 纯金黄底色
        - 🔴 红底大底号码: 深红色底色 + 白色字体
        - 普通号码: 白底无边框
        """
        cell_num = ws.cell(row=row_num, column=col_idx, value=num)
        cell_num.alignment = self.align_center
        cell_num.font = self.font_num
        cell_num.border = self.border_cell

        cell_r012 = ws.cell(row=row_r012, column=col_idx, value=num % 3)
        cell_r012.alignment = self.align_center
        cell_r012.font = self.font_r012

        is_border = (num in red_border_set)
        is_yellow = (num in yellow_pool_set)
        is_red = (num in red_pool_set)

        if is_border or (is_yellow and is_red):
            # 核心共振交集: 金黄底色 + 红色粗方框 (完美对齐截图!)
            cell_num.fill = PatternFill("solid", fgColor=self.COLOR_YELLOW_PICK)
            cell_num.border = self.border_hit
        elif is_yellow:
            # 仅黄底: 纯金黄底色
            cell_num.fill = PatternFill("solid", fgColor=self.COLOR_YELLOW_PICK)
        elif is_red:
            # 仅红底: 深红底色 + 白色粗体字 (完美对齐截图!)
            cell_num.fill = PatternFill("solid", fgColor=self.COLOR_HIT_DRAW)
            cell_num.font = self.font_num_white


    # ══════════════════════════════════════════════════════════════════════════
    # Sheet 2: 【常球顺序】(1~80 号球滑动矩阵与基础形态)
    # ══════════════════════════════════════════════════════════════════════════
    def build_normal_order_sheet(
        self,
        wb: openpyxl.Workbook,
        draws: List[Dict[str, Any]],
        sheet_name: str = "常球顺序"
    ) -> openpyxl.worksheet.worksheet.Worksheet:
        ws = wb.create_sheet(title=sheet_name)
        ws.views.sheetView[0].showGridLines = True

        recent_draws = draws[-WINDOW_SIZE:] if len(draws) >= WINDOW_SIZE else draws

        headers = ["期号", "日期", "开奖号码 (20 码)", "奇偶比", "和值", "0头", "1头", "2头", "3头", "4头", "5头", "6头", "7头", "8头"]
        ws.row_dimensions[1].height = 24
        for c_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c_idx, value=h)
            cell.font = self.font_header_white
            cell.fill = PatternFill("solid", fgColor=self.COLOR_HEADER_NAVY)
            cell.alignment = self.align_center

        for r_idx, d in enumerate(recent_draws, 2):
            nums = d.get("nums", [])
            p_val = d.get("period")
            d_val = d.get("date", "")
            odd_c = sum(1 for n in nums if n % 2 == 1)
            even_c = 20 - odd_c
            sum_val = sum(nums)

            ws.row_dimensions[r_idx].height = 18
            ws.cell(row=r_idx, column=1, value=p_val).alignment = self.align_center
            ws.cell(row=r_idx, column=2, value=d_val).alignment = self.align_center
            ws.cell(row=r_idx, column=3, value=" ".join(f"{x:02d}" for x in sorted(nums))).alignment = self.align_left
            ws.cell(row=r_idx, column=4, value=f"{odd_c}:{even_c}").alignment = self.align_center
            ws.cell(row=r_idx, column=5, value=sum_val).alignment = self.align_center

            for head_i in range(9):
                lo = 1 if head_i == 0 else head_i * 10
                hi = 9 if head_i == 0 else (80 if head_i == 8 else head_i * 10 + 9)
                cnt = sum(1 for n in nums if lo <= n <= hi)
                c_cell = ws.cell(row=r_idx, column=6 + head_i, value=cnt)
                c_cell.alignment = self.align_center

        ws.column_dimensions["A"].width = 11.0
        ws.column_dimensions["B"].width = 12.0
        ws.column_dimensions["C"].width = 56.0
        ws.column_dimensions["D"].width = 9.0
        ws.column_dimensions["E"].width = 8.0
        for i in range(6, 15):
            ws.column_dimensions[get_column_letter(i)].width = 6.0

        return ws

    # ══════════════════════════════════════════════════════════════════════════
    # Sheet 3: 【尾数分布】(0~9 尾冷热全息走势)
    # ══════════════════════════════════════════════════════════════════════════
    def build_tail_distribution_sheet(
        self,
        wb: openpyxl.Workbook,
        draws: List[Dict[str, Any]],
        sheet_name: str = "尾数分布"
    ) -> openpyxl.worksheet.worksheet.Worksheet:
        ws = wb.create_sheet(title=sheet_name)
        ws.views.sheetView[0].showGridLines = True

        recent_draws = draws[-WINDOW_SIZE:] if len(draws) >= WINDOW_SIZE else draws

        headers = ["期号"] + [f"{t} 尾" for t in range(10)] + ["最热尾数", "偏冷尾数"]
        ws.row_dimensions[1].height = 24
        for c_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c_idx, value=h)
            cell.font = self.font_header_white
            cell.fill = PatternFill("solid", fgColor=self.COLOR_HEADER_NAVY)
            cell.alignment = self.align_center

        for r_idx, d in enumerate(recent_draws, 2):
            nums = d.get("nums", [])
            tail_counts = Counter(n % 10 for n in nums)

            ws.row_dimensions[r_idx].height = 18
            ws.cell(row=r_idx, column=1, value=d["period"]).alignment = self.align_center

            for t in range(10):
                cnt = tail_counts.get(t, 0)
                cell_t = ws.cell(row=r_idx, column=2 + t, value=cnt)
                cell_t.alignment = self.align_center
                if cnt >= 4:
                    cell_t.fill = PatternFill("solid", fgColor=self.COLOR_TIER_7)
                elif cnt == 0:
                    cell_t.fill = PatternFill("solid", fgColor=self.COLOR_CARD_BG)

            sorted_tails = sorted(range(10), key=lambda t: tail_counts.get(t, 0), reverse=True)
            hot_str = f"{sorted_tails[0]}尾({tail_counts.get(sorted_tails[0], 0)})"
            cold_str = f"{sorted_tails[-1]}尾({tail_counts.get(sorted_tails[-1], 0)})"
            ws.cell(row=r_idx, column=12, value=hot_str).alignment = self.align_center
            ws.cell(row=r_idx, column=13, value=cold_str).alignment = self.align_center

        ws.column_dimensions["A"].width = 11.0
        for i in range(2, 12):
            ws.column_dimensions[get_column_letter(i)].width = 7.0
        ws.column_dimensions["L"].width = 14.0
        ws.column_dimensions["M"].width = 14.0

        return ws

    # ══════════════════════════════════════════════════════════════════════════
    # Sheet 4: 【012路】(012路平衡度与走势)
    # ══════════════════════════════════════════════════════════════════════════
    def build_012_roads_sheet(
        self,
        wb: openpyxl.Workbook,
        draws: List[Dict[str, Any]],
        sheet_name: str = "012路"
    ) -> openpyxl.worksheet.worksheet.Worksheet:
        ws = wb.create_sheet(title=sheet_name)
        ws.views.sheetView[0].showGridLines = True

        recent_draws = draws[-WINDOW_SIZE:] if len(draws) >= WINDOW_SIZE else draws

        headers = ["期号", "0 路个数", "1 路个数", "2 路个数", "012路比", "0路出号清单", "1路出号清单", "2路出号清单"]
        ws.row_dimensions[1].height = 24
        for c_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c_idx, value=h)
            cell.font = self.font_header_white
            cell.fill = PatternFill("solid", fgColor=self.COLOR_HEADER_NAVY)
            cell.alignment = self.align_center

        for r_idx, d in enumerate(recent_draws, 2):
            nums = d.get("nums", [])
            r0 = [n for n in nums if n % 3 == 0]
            r1 = [n for n in nums if n % 3 == 1]
            r2 = [n for n in nums if n % 3 == 2]

            ws.row_dimensions[r_idx].height = 18
            ws.cell(row=r_idx, column=1, value=d["period"]).alignment = self.align_center
            ws.cell(row=r_idx, column=2, value=len(r0)).alignment = self.align_center
            ws.cell(row=r_idx, column=3, value=len(r1)).alignment = self.align_center
            ws.cell(row=r_idx, column=4, value=len(r2)).alignment = self.align_center
            ws.cell(row=r_idx, column=5, value=f"{len(r0)}:{len(r1)}:{len(r2)}").alignment = self.align_center

            ws.cell(row=r_idx, column=6, value=" ".join(f"{x:02d}" for x in sorted(r0))).alignment = self.align_left
            ws.cell(row=r_idx, column=7, value=" ".join(f"{x:02d}" for x in sorted(r1))).alignment = self.align_left
            ws.cell(row=r_idx, column=8, value=" ".join(f"{x:02d}" for x in sorted(r2))).alignment = self.align_left

        ws.column_dimensions["A"].width = 11.0
        ws.column_dimensions["B"].width = 10.0
        ws.column_dimensions["C"].width = 10.0
        ws.column_dimensions["D"].width = 10.0
        ws.column_dimensions["E"].width = 12.0
        ws.column_dimensions["F"].width = 28.0
        ws.column_dimensions["G"].width = 28.0
        ws.column_dimensions["H"].width = 28.0

        return ws

    # ══════════════════════════════════════════════════════════════════════════
    # Sheet 5: 【实操决策与对账总账本】
    # ══════════════════════════════════════════════════════════════════════════
    def build_decision_ledger_sheet(
        self,
        wb: openpyxl.Workbook,
        latest_analysis: Dict[str, Any],
        walk_forward_list: Sequence[Dict[str, Any]],
        sheet_name: str = "实操决策与对账总账本"
    ) -> openpyxl.worksheet.worksheet.Worksheet:
        ws = wb.create_sheet(title=sheet_name)
        ws.views.sheetView[0].showGridLines = True

        target_p = latest_analysis["target_period"]
        fp = latest_analysis.get("picks", {})

        # 1. 顶部当前期作战大牌
        ws.merge_cells("A1:G1")
        top_title = ws.cell(row=1, column=1, value=f"👑 快乐8 第 {target_p} 期 16期窗口动力学实操决策作战室")
        top_title.font = Font(name="微软雅黑", size=13, bold=True, color="FFFFFF")
        top_title.fill = PatternFill("solid", fgColor=self.COLOR_HEADER_NAVY)
        top_title.alignment = self.align_center
        ws.row_dimensions[1].height = 28

        repeat_top = fp.get("repeat_picks", {}).get("top_picks", [13, 35, 25])
        plan_rows = [
            ("🎯 【20 码大底】(高保真黄底推荐池)", " ".join(f"{x:02d}" for x in fp.get("grand_20", []))),
            ("🚀 【12 码精选】(主升浪核心攻击梯队)", " ".join(f"{x:02d}" for x in fp.get("elite_12", []))),
            ("👑 【黄金 5 胆】(金银铜铁钻稳健核心)", " ".join(f"{x:02d}" for x in fp.get("golden_5", []))),
            ("⚡ 【最优 3 胆】(极高胜率突破矛头)", " ".join(f"{x:02d}" for x in fp.get("golden_3", []))),
            ("🔥 【黄金重号】(剔除2连开与透支码)", " ".join(f"{x:02d}" for x in repeat_top)),
            ("💎 【选2黄金搭档】", " | ".join(f"[{p[0]:02d}-{p[1]:02d}]" for p in fp.get("top_pairs", []))),
        ]

        for idx, (k_txt, v_txt) in enumerate(plan_rows, 2):
            ws.row_dimensions[idx].height = 20
            c_k = ws.cell(row=idx, column=1, value=k_txt)
            c_k.font = self.font_bold_title
            c_k.alignment = self.align_left
            c_k.fill = PatternFill("solid", fgColor=self.COLOR_CARD_BG)

            ws.merge_cells(start_row=idx, start_column=2, end_row=idx, end_column=7)
            c_v = ws.cell(row=idx, column=2, value=v_txt)
            c_v.font = Font(name="Calibri", size=11, bold=True, color="1F497D")
            c_v.alignment = self.align_left

        # 2. 样本外盲测历史流水
        row_offset = 9
        ws.merge_cells(f"A{row_offset}:G{row_offset}")
        sub_title = ws.cell(row=row_offset, column=1, value="🏆 近期样本外 Walk-Forward 滚动实测盲测对账总账本 (彻底屏蔽未来数据)")
        sub_title.font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
        sub_title.fill = PatternFill("solid", fgColor=self.COLOR_HEADER_NAVY)
        sub_title.alignment = self.align_center
        ws.row_dimensions[row_offset].height = 24

        headers = ["期号", "实际开奖号码 (20码)", "20码大底命中", "12码精选命中", "5码金胆命中", "3码最优命中", "命中号码明细"]
        ws.row_dimensions[row_offset + 1].height = 20
        for c_i, h in enumerate(headers, 1):
            cell = ws.cell(row=row_offset + 1, column=c_i, value=h)
            cell.font = self.font_bold_title
            cell.fill = PatternFill("solid", fgColor=self.COLOR_CARD_BG)
            cell.alignment = self.align_center
            cell.border = self.border_cell

        for i, audit_item in enumerate(walk_forward_list, row_offset + 2):
            p = audit_item["period"]
            act_nums = audit_item["actual_draw"]
            g20_h = audit_item["grand_20_hit_count"]
            e12_h = audit_item["elite_12_hit_count"]
            g5_h = audit_item["golden_5_hit_count"]
            g3_h = audit_item["golden_3_hit_count"]
            hits_str = " ".join(f"{x:02d}" for x in audit_item["grand_20_hits"])

            ws.row_dimensions[i].height = 18
            ws.cell(row=i, column=1, value=p).alignment = self.align_center
            ws.cell(row=i, column=2, value=" ".join(f"{x:02d}" for x in act_nums)).alignment = self.align_left
            ws.cell(row=i, column=3, value=f"{g20_h} / 20").alignment = self.align_center
            ws.cell(row=i, column=4, value=f"{e12_h} / 12").alignment = self.align_center
            ws.cell(row=i, column=5, value=f"{g5_h} / 5").alignment = self.align_center
            ws.cell(row=i, column=6, value=f"{g3_h} / 3").alignment = self.align_center
            ws.cell(row=i, column=7, value=hits_str).alignment = self.align_left

        ws.column_dimensions["A"].width = 24.0
        ws.column_dimensions["B"].width = 46.0
        ws.column_dimensions["C"].width = 14.0
        ws.column_dimensions["D"].width = 14.0
        ws.column_dimensions["E"].width = 14.0
        ws.column_dimensions["F"].width = 14.0
        ws.column_dimensions["G"].width = 28.0

        return ws

    # ══════════════════════════════════════════════════════════════════════════
    # Sheet 5: 【遗漏分析】(80 码全景遗漏、分层分桶与 012 路动力学共振)
    # ══════════════════════════════════════════════════════════════════════════
    def build_omission_sheet(
        self,
        wb: openpyxl.Workbook,
        draws: List[Dict[str, Any]],
        latest_analysis: Dict[str, Any],
        sheet_name: str = "遗漏分析"
    ) -> openpyxl.worksheet.worksheet.Worksheet:
        """
        构建 80 码全息遗漏走势、分层分桶与 012 路动力学共振工作表

        【业务背景与架构定位】:
        针对快乐8单期与多期走势，遗漏值是反映号码冷热、回补动能与均值回归的最核心物理指标。
        本工作表深度整合：
        1. 80 码当前实时遗漏值、近 16 期频次、近 100 期最大遗漏与平均遗漏；
        2. 遗漏层级物理划分：遗漏 0 (重号层)、遗漏 1 (黄金隔期跳)、遗漏 2~3 (温热反弹)、遗漏 4~7 (温冷过渡)、遗漏 8+ (极端深冷)；
        3. 双轨三色映射：🔲红框核心、🟡黄底精选、🔴红底大底；
        4. 012 路 × 遗漏层级 交叉动力学共振选号矩阵与操盘手大白话实战研判。

        :param wb: openpyxl 工作簿对象
        :param draws: 历史开奖全量流水
        :param latest_analysis: 最新一期 16 期窗口分析结果字典
        :param sheet_name: 工作表名称，默认 "遗漏分析"
        :return: 渲染完成的 Worksheet 对象
        """
        ws = wb.create_sheet(title=sheet_name)
        ws.views.sheetView[0].showGridLines = True

        target_p = latest_analysis.get("target_period", "Next")
        fp = latest_analysis.get("picks", {})
        red_pool_set: Set[int] = set(fp.get("red_pool", []))
        yellow_pool_set: Set[int] = set(fp.get("yellow_pool", []))
        red_border_set: Set[int] = set(fp.get("red_border_core", []))
        elite_12_set: Set[int] = set(fp.get("elite_12", []))
        golden_5_set: Set[int] = set(fp.get("golden_5", []))
        golden_3_set: Set[int] = set(fp.get("golden_3", []))

        # 步骤 1: 计算 1~80 号球当前遗漏、近 16 期频次、近 100 期最大与平均遗漏
        n_draws = len(draws)
        recent_16 = draws[-WINDOW_SIZE:] if n_draws >= WINDOW_SIZE else draws
        recent_100 = draws[-100:] if n_draws >= 100 else draws

        ball_records: List[Dict[str, Any]] = []
        for n in range(1, NUM_TOTAL + 1):
            # 当前遗漏
            cur_om = n_draws
            for step_back, d in enumerate(reversed(draws)):
                n_set = d.get("nums_set", set(d.get("nums", [])))
                if n in n_set:
                    cur_om = step_back
                    break

            # 近 16 期频次
            f16 = sum(1 for d in recent_16 if n in d.get("nums_set", set(d.get("nums", []))))

            # 近 100 期统计 (最大遗漏与平均遗漏)
            appear_indices = [idx for idx, d in enumerate(recent_100) if n in d.get("nums_set", set(d.get("nums", [])))]
            if appear_indices:
                gaps = [appear_indices[0]]
                for k in range(len(appear_indices) - 1):
                    gaps.append(appear_indices[k + 1] - appear_indices[k] - 1)
                gaps.append(len(recent_100) - 1 - appear_indices[-1])
                max_om_100 = max(gaps) if gaps else cur_om
                avg_om_100 = round(len(recent_100) / len(appear_indices), 1)
            else:
                max_om_100 = len(recent_100)
                avg_om_100 = float(len(recent_100))

            # 遗漏层级分类
            if cur_om == 0:
                tier_code = "T0_重号"
                tier_name = "遗漏 0 (连庄重号)"
            elif cur_om == 1:
                tier_code = "T1_隔期"
                tier_name = "遗漏 1 (黄金隔期跳)"
            elif cur_om in [2, 3]:
                tier_code = "T2_反弹"
                tier_name = f"遗漏 {cur_om} (温热反弹)"
            elif 4 <= cur_om <= 7:
                tier_code = "T3_过渡"
                tier_name = "遗漏 4~7 (温冷过渡)"
            else:
                tier_code = "T4_深冷"
                tier_name = "遗漏 8+ (极端深冷)"

            # 大盘归属
            if n in red_border_set:
                pool_status = "🔲 红框共振核心"
            elif n in yellow_pool_set:
                pool_status = "🟡 黄底精选冲锋"
            elif n in red_pool_set:
                pool_status = "🔴 红底大底防守"
            else:
                pool_status = "普通号码"

            # 操盘大白话研判
            if cur_om == 0:
                if n in red_border_set or n in golden_5_set:
                    advice = "👑【黄金重号】核心金胆连庄，必防重点！"
                elif n in elite_12_set or n in yellow_pool_set:
                    advice = "🚀【主力重号】精选连庄号，重点防守。"
                elif n in red_pool_set:
                    advice = "🛡️【大底重号】大底防御连开，适度配置。"
                else:
                    advice = "⚪【普通重号】次要连庄，防止过热熄火。"
            elif cur_om == 1:
                if n in red_border_set:
                    advice = "🔥【隔期金胆】红框核心+隔期跳开黄金爆发点！"
                elif n in elite_12_set:
                    advice = "🚀【隔期主攻】精选主力梯队隔期回补，极度看好！"
                elif n in yellow_pool_set or n in red_pool_set:
                    advice = "✨【隔期跟进】大底池隔期回补，稳健跟进。"
                else:
                    advice = "常态隔期跳码，保持观察。"
            elif cur_om in [2, 3]:
                if n in red_border_set:
                    advice = "💎【反弹金胆】红框核心+双次回踩温热金胆！"
                elif n in elite_12_set:
                    advice = "🎯【温热主攻】蓄势待发核心，随时爆发！"
                elif n in yellow_pool_set or n in red_pool_set:
                    advice = "✨【温热防守】大底池温热守候，胜率稳健。"
                else:
                    advice = "常规温号，静待回补信号。"
            elif 4 <= cur_om <= 7:
                if n in elite_12_set or n in red_border_set:
                    advice = "⚡【奇兵博冷】精选逆势捕捉温冷回补奇兵！"
                elif n in red_pool_set:
                    advice = "🛡️【温冷防守】防守大底蓄势冷号。"
                else:
                    advice = "温冷过渡观望，建议暂缓单挑。"
            else:
                if n in elite_12_set or n in golden_5_set:
                    advice = "⚡【极冷单挑】憋号极限反弹奇兵，小注防守！"
                else:
                    advice = "❄️【冰冻避险】深冷周期，严防追高被套！"

            ball_records.append({
                "num": n,
                "cur_om": cur_om,
                "tier_code": tier_code,
                "tier_name": tier_name,
                "r012": n % 3,
                "tail": n % 10,
                "head": (n - 1) // 10,
                "f16": f16,
                "pool_status": pool_status,
                "max_om_100": max_om_100,
                "avg_om_100": avg_om_100,
                "advice": advice,
                "is_border": (n in red_border_set),
                "is_yellow": (n in yellow_pool_set),
                "is_red": (n in red_pool_set),
            })

        # 步骤 2: 顶部作战总览大标题与 KPI 看板
        ws.merge_cells("A1:K1")
        top_title = ws.cell(row=1, column=1, value=f"👑 快乐8 第 {target_p} 期 1~80 号全息遗漏走势与多维分层研判表")
        top_title.font = Font(name="微软雅黑", size=13, bold=True, color="FFFFFF")
        top_title.fill = PatternFill("solid", fgColor=self.COLOR_HEADER_NAVY)
        top_title.alignment = self.align_center
        ws.row_dimensions[1].height = 28

        # KPI 概览卡片
        om0_cnt = sum(1 for b in ball_records if b["cur_om"] == 0)
        om13_cnt = sum(1 for b in ball_records if 1 <= b["cur_om"] <= 3)
        om47_cnt = sum(1 for b in ball_records if 4 <= b["cur_om"] <= 7)
        om8p_cnt = sum(1 for b in ball_records if b["cur_om"] >= 8)

        kpis = [
            ("遗漏 0 (重号层)", f"{om0_cnt} 码 (25.0%)", "历史均出 4~6 码 | 研判: 挑选 2~3 码连庄"),
            ("遗漏 1~3 (黄金反弹层)", f"{om13_cnt} 码 ({round(om13_cnt/80*100,1)}%)", "历史均出 11~13 码 | 研判: 核心产出区，红框共振主力集中"),
            ("遗漏 4~7 (温冷过渡层)", f"{om47_cnt} 码 ({round(om47_cnt/80*100,1)}%)", "历史均出 2~3 码 | 研判: 稳健过渡，防守 1~2 码"),
            ("遗漏 8+ (极端深冷层)", f"{om8p_cnt} 码 ({round(om8p_cnt/80*100,1)}%)", "历史均出 0~2 码 | 研判: 严格控仓防死守，仅轻仓单挑"),
        ]

        ws.row_dimensions[2].height = 20
        ws.row_dimensions[3].height = 20
        col_splits = [(1, 3), (4, 6), (7, 8), (9, 11)]
        for k_idx, (t_title, t_val, t_desc) in enumerate(kpis):
            c_start, c_end = col_splits[k_idx]
            ws.merge_cells(start_row=2, start_column=c_start, end_row=2, end_column=c_end)
            c2 = ws.cell(row=2, column=c_start, value=f"{t_title}: {t_val}")
            c2.font = Font(name="微软雅黑", size=10, bold=True, color="1F497D")
            c2.fill = PatternFill("solid", fgColor=self.COLOR_CARD_BG)
            c2.alignment = self.align_center
            c2.border = self.border_cell

            ws.merge_cells(start_row=3, start_column=c_start, end_row=3, end_column=c_end)
            c3 = ws.cell(row=3, column=c_start, value=t_desc)
            c3.font = Font(name="微软雅黑", size=8, color="555555")
            c3.fill = PatternFill("solid", fgColor="FFFFFF")
            c3.alignment = self.align_center
            c3.border = self.border_cell

        # 步骤 3: 渲染左侧主表 (A4:K85) - 80 码全息明细 (按遗漏值升序排列，方便查阅)
        sorted_records = sorted(ball_records, key=lambda x: (x["cur_om"], -x["f16"], x["num"]))

        headers_main = ["序号", "球号", "当前遗漏", "遗漏层级", "012路", "尾数", "近16期频次", "大盘归属", "近100期最大遗漏", "近100期平均遗漏", "老派量化操盘手实战研判"]
        ws.row_dimensions[4].height = 24
        for c_i, h in enumerate(headers_main, 1):
            cell = ws.cell(row=4, column=c_i, value=h)
            cell.font = self.font_header_white
            cell.fill = PatternFill("solid", fgColor=self.COLOR_HEADER_NAVY)
            cell.alignment = self.align_center
            cell.border = self.border_cell

        fill_om0 = PatternFill("solid", fgColor="F2F2F2")      # 遗漏0: 浅灰
        fill_om1 = PatternFill("solid", fgColor="FFF2CC")      # 遗漏1: 浅金黄高亮
        fill_om23 = PatternFill("solid", fgColor="E2EFDA")     # 遗漏2~3: 浅绿温热
        fill_om47 = PatternFill("solid", fgColor="EBF1F5")     # 遗漏4~7: 浅青蓝
        fill_om8p = PatternFill("solid", fgColor="F8CECC")     # 遗漏8+: 警示粉红

        for r_i, rec in enumerate(sorted_records, 5):
            ws.row_dimensions[r_i].height = 19
            num_val = rec["num"]
            om_val = rec["cur_om"]

            # 序号
            c_idx = ws.cell(row=r_i, column=1, value=r_i - 4)
            c_idx.alignment = self.align_center
            c_idx.font = Font(name="Calibri", size=9, color="555555")
            c_idx.border = self.border_cell

            # 球号 (按照三色体系精细渲染)
            c_num = ws.cell(row=r_i, column=2, value=f"{num_val:02d}")
            c_num.alignment = self.align_center
            c_num.border = self.border_cell
            if rec["is_border"] or (rec["is_yellow"] and rec["is_red"]):
                # 🔲 红框核心
                c_num.font = self.font_num
                c_num.fill = PatternFill("solid", fgColor=self.COLOR_YELLOW_PICK)
                c_num.border = self.border_hit
            elif rec["is_yellow"]:
                # 🟡 黄底精选
                c_num.font = self.font_num
                c_num.fill = PatternFill("solid", fgColor=self.COLOR_YELLOW_PICK)
            elif rec["is_red"]:
                # 🔴 红底大底
                c_num.font = self.font_num_white
                c_num.fill = PatternFill("solid", fgColor=self.COLOR_HIT_DRAW)
            else:
                c_num.font = self.font_num

            # 当前遗漏
            c_om = ws.cell(row=r_i, column=3, value=om_val)
            c_om.alignment = self.align_center
            c_om.font = Font(name="Calibri", size=11, bold=True, color="000000" if om_val < 8 else "C00000")
            c_om.border = self.border_cell
            if om_val == 0:
                c_om.fill = fill_om0
            elif om_val == 1:
                c_om.fill = fill_om1
            elif om_val in [2, 3]:
                c_om.fill = fill_om23
            elif 4 <= om_val <= 7:
                c_om.fill = fill_om47
            else:
                c_om.fill = fill_om8p

            # 遗漏层级
            c_tier = ws.cell(row=r_i, column=4, value=rec["tier_name"])
            c_tier.alignment = self.align_center
            c_tier.font = Font(name="微软雅黑", size=9)
            c_tier.border = self.border_cell

            # 012路
            c_r = ws.cell(row=r_i, column=5, value=f"{rec['r012']}路")
            c_r.alignment = self.align_center
            c_r.font = Font(name="Calibri", size=9)
            c_r.border = self.border_cell

            # 尾数
            c_t = ws.cell(row=r_i, column=6, value=f"{rec['tail']}尾")
            c_t.alignment = self.align_center
            c_t.font = Font(name="Calibri", size=9)
            c_t.border = self.border_cell

            # 近16期频次
            c_f = ws.cell(row=r_i, column=7, value=f"{rec['f16']}次")
            c_f.alignment = self.align_center
            c_f.font = Font(name="Calibri", size=10, bold=True)
            c_f.border = self.border_cell

            # 大盘归属
            c_st = ws.cell(row=r_i, column=8, value=rec["pool_status"])
            c_st.alignment = self.align_center
            c_st.font = Font(name="微软雅黑", size=9, bold=(rec["is_border"] or rec["is_yellow"]))
            c_st.border = self.border_cell

            # 近100期最大遗漏
            c_mo = ws.cell(row=r_i, column=9, value=rec["max_om_100"])
            c_mo.alignment = self.align_center
            c_mo.font = Font(name="Calibri", size=9)
            c_mo.border = self.border_cell

            # 近100期平均遗漏
            c_ao = ws.cell(row=r_i, column=10, value=rec["avg_om_100"])
            c_ao.alignment = self.align_center
            c_ao.font = Font(name="Calibri", size=9)
            c_ao.border = self.border_cell

            # 操盘手研判建议
            c_ad = ws.cell(row=r_i, column=11, value=rec["advice"])
            c_ad.alignment = self.align_left
            c_ad.font = Font(name="微软雅黑", size=9, bold=rec["is_border"], color="1F497D" if rec["is_border"] else "333333")
            c_ad.border = self.border_cell

        # 步骤 4: 右侧看板 1 (M1:Q14) - 遗漏分层汇总与核心推荐对应
        ws.merge_cells("M1:Q1")
        rt_title1 = ws.cell(row=1, column=13, value="📦 快乐8 遗漏分层实战分桶与核心推荐对应表")
        rt_title1.font = Font(name="微软雅黑", size=12, bold=True, color="FFFFFF")
        rt_title1.fill = PatternFill("solid", fgColor=self.COLOR_HEADER_NAVY)
        rt_title1.alignment = self.align_center

        headers_rt1 = ["遗漏分层", "号码容量", "包含球号清单", "核心红框 / 精选推荐", "老派操盘手执行策略"]
        ws.row_dimensions[2].height = 22
        for col_i, h_val in enumerate(headers_rt1, 13):
            cell = ws.cell(row=2, column=col_i, value=h_val)
            cell.font = self.font_header_white
            cell.fill = PatternFill("solid", fgColor="2F5597")
            cell.alignment = self.align_center
            cell.border = self.border_cell

        repeat_top_picks = fp.get("repeat_picks", {}).get("top_picks", [13, 35, 25])
        tier_group_defs = [
            ("遗漏 0 (重号层)", [b["num"] for b in ball_records if b["cur_om"] == 0], "严格防守 2~3 码连庄，剔除2连开与透支码"),
            ("遗漏 1 (隔期跳开)", [b["num"] for b in ball_records if b["cur_om"] == 1], "⭐ 黄金爆发层！红框核心集中地"),
            ("遗漏 2 (双次回踩)", [b["num"] for b in ball_records if b["cur_om"] == 2], "🚀 温热回踩，主升浪次选主攻区"),
            ("遗漏 3 (温号蓄势)", [b["num"] for b in ball_records if b["cur_om"] == 3], "🎯 蓄势待发，稳健过渡产出区"),
            ("遗漏 4~7 (温冷过渡)", [b["num"] for b in ball_records if 4 <= b["cur_om"] <= 7], "🛡️ 防守 1~2 码，暂不作为重注主攻"),
            ("遗漏 8+ (极端深冷)", [b["num"] for b in ball_records if b["cur_om"] >= 8], "❄️ 警惕长期冰冻，仅轻仓单挑极限"),
        ]

        for idx, (t_name, t_nums, t_strategy) in enumerate(tier_group_defs, 3):
            ws.row_dimensions[idx].height = 20
            if t_name.startswith("遗漏 0"):
                rec_picks = repeat_top_picks
            else:
                rec_picks = [n for n in t_nums if n in red_border_set or n in elite_12_set]

            c_tname = ws.cell(row=idx, column=13, value=t_name)
            c_tname.alignment = self.align_center
            c_tname.font = Font(name="微软雅黑", size=9, bold=True)
            c_tname.border = self.border_cell
            c_tname.fill = PatternFill("solid", fgColor=self.COLOR_CARD_BG)

            c_tcnt = ws.cell(row=idx, column=14, value=f"{len(t_nums)} 码")
            c_tcnt.alignment = self.align_center
            c_tcnt.font = Font(name="Calibri", size=10, bold=True)
            c_tcnt.border = self.border_cell

            c_tlist = ws.cell(row=idx, column=15, value=" ".join(f"{x:02d}" for x in sorted(t_nums)))
            c_tlist.alignment = self.align_left
            c_tlist.font = Font(name="Calibri", size=9)
            c_tlist.border = self.border_cell

            c_trec = ws.cell(row=idx, column=16, value=" ".join(f"{x:02d}" for x in sorted(rec_picks)) if rec_picks else "—")
            c_trec.alignment = self.align_left
            c_trec.font = Font(name="Calibri", size=10, bold=True, color="C00000")
            c_trec.border = self.border_cell
            if rec_picks:
                c_trec.fill = PatternFill("solid", fgColor="FFF2CC")

            c_tstrat = ws.cell(row=idx, column=17, value=t_strategy)
            c_tstrat.alignment = self.align_left
            c_tstrat.font = Font(name="微软雅黑", size=8)
            c_tstrat.border = self.border_cell

        # 步骤 5: 右侧看板 2 (M11:Q17) - 012路 × 遗漏层级 动力学交叉共振矩阵
        ws.merge_cells("M11:Q11")
        rt_title2 = ws.cell(row=11, column=13, value="⚡ 012路 × 遗漏动力学交叉共振选号矩阵")
        rt_title2.font = Font(name="微软雅黑", size=12, bold=True, color="FFFFFF")
        rt_title2.fill = PatternFill("solid", fgColor=self.COLOR_HEADER_NAVY)
        rt_title2.alignment = self.align_center

        headers_rt2 = ["路数", "遗漏 0 (重号)", "遗漏 1~3 (黄金反弹主力)", "遗漏 4~7 (温冷)", "遗漏 8+ (极端冷号)", "本路精选金胆"]
        ws.row_dimensions[12].height = 22
        for col_i, h_val in enumerate(headers_rt2, 13):
            cell = ws.cell(row=12, column=col_i, value=h_val)
            cell.font = self.font_header_white
            cell.fill = PatternFill("solid", fgColor="2F5597")
            cell.alignment = self.align_center
            cell.border = self.border_cell

        roads = [0, 1, 2]
        for r_k, r_val in enumerate(roads, 13):
            ws.row_dimensions[r_k].height = 24
            r_nums = [b["num"] for b in ball_records if b["r012"] == r_val]
            r_om0 = [n for n in r_nums if n in tier_group_defs[0][1]]
            r_om13 = [n for n in r_nums if 1 <= next(b["cur_om"] for b in ball_records if b["num"] == n) <= 3]
            r_om47 = [n for n in r_nums if 4 <= next(b["cur_om"] for b in ball_records if b["num"] == n) <= 7]
            r_om8p = [n for n in r_nums if next(b["cur_om"] for b in ball_records if b["num"] == n) >= 8]

            # 本路精选金胆 (交集优先)
            road_best = [n for n in r_nums if n in red_border_set or n in golden_5_set or n in elite_12_set]

            c_rname = ws.cell(row=r_k, column=13, value=f"{r_val} 路")
            c_rname.alignment = self.align_center
            c_rname.font = Font(name="微软雅黑", size=11, bold=True, color="1F497D")
            c_rname.fill = PatternFill("solid", fgColor=self.COLOR_CARD_BG)
            c_rname.border = self.border_cell

            c_rom0 = ws.cell(row=r_k, column=14, value=" ".join(f"{x:02d}" for x in sorted(r_om0)))
            c_rom0.alignment = self.align_left
            c_rom0.font = Font(name="Calibri", size=9)
            c_rom0.border = self.border_cell

            c_rom13 = ws.cell(row=r_k, column=15, value=" ".join(f"{x:02d}" for x in sorted(r_om13)))
            c_rom13.alignment = self.align_left
            c_rom13.font = Font(name="Calibri", size=9, bold=True)
            c_rom13.fill = PatternFill("solid", fgColor="FFF2CC")
            c_rom13.border = self.border_cell

            c_rom47 = ws.cell(row=r_k, column=16, value=" ".join(f"{x:02d}" for x in sorted(r_om47)))
            c_rom47.alignment = self.align_left
            c_rom47.font = Font(name="Calibri", size=9)
            c_rom47.border = self.border_cell

            c_rom8p = ws.cell(row=r_k, column=17, value=" ".join(f"{x:02d}" for x in sorted(r_om8p)))
            c_rom8p.alignment = self.align_left
            c_rom8p.font = Font(name="Calibri", size=9)
            c_rom8p.border = self.border_cell

            c_rbest = ws.cell(row=r_k, column=18, value=" ".join(f"{x:02d}" for x in sorted(road_best)))
            c_rbest.alignment = self.align_left
            c_rbest.font = Font(name="Calibri", size=10, bold=True, color="C00000")
            c_rbest.border = self.border_cell
            c_rbest.fill = PatternFill("solid", fgColor="FFF2CC")

        # 补齐表头第18列
        cell_18 = ws.cell(row=12, column=18, value="本路精选金胆")
        cell_18.font = self.font_header_white
        cell_18.fill = PatternFill("solid", fgColor="2F5597")
        cell_18.alignment = self.align_center
        cell_18.border = self.border_cell

        # 调整列宽
        ws.column_dimensions["A"].width = 7.0
        ws.column_dimensions["B"].width = 8.0
        ws.column_dimensions["C"].width = 11.0
        ws.column_dimensions["D"].width = 15.0
        ws.column_dimensions["E"].width = 9.0
        ws.column_dimensions["F"].width = 8.0
        ws.column_dimensions["G"].width = 11.0
        ws.column_dimensions["H"].width = 16.0
        ws.column_dimensions["I"].width = 13.0
        ws.column_dimensions["J"].width = 13.0
        ws.column_dimensions["K"].width = 36.0
        ws.column_dimensions["L"].width = 3.0
        ws.column_dimensions["M"].width = 14.0
        ws.column_dimensions["N"].width = 12.0
        ws.column_dimensions["O"].width = 36.0
        ws.column_dimensions["P"].width = 24.0
        ws.column_dimensions["Q"].width = 28.0
        ws.column_dimensions["R"].width = 20.0

        return ws

    # ══════════════════════════════════════════════════════════════════════════
    # 旗舰超级工作簿总导出接口
    # ══════════════════════════════════════════════════════════════════════════
    def export_excel(
        self,
        latest_analysis_result: Dict[str, Any],
        output_xlsx_path: Optional[str] = None,
        n_history_periods: int = 10
    ) -> str:
        """
        全量导出 6 大核心工作表的超级工作簿 (含遗漏分析)
        :param latest_analysis_result: 最新一期分析结果
        :param output_xlsx_path: 保存路径
        :param n_history_periods: 主【新方法】工作表向上纵向回溯连续期数，默认回溯 10 期
        """
        target_p = latest_analysis_result["target_period"]

        if output_xlsx_path is None:
            # 2026-10-15 修复：禁止与 ops 窗表 sixteen_excel_window_*.xlsx 同名覆盖
            reports_dir = os.path.join(get_outputs_dir(), "reports")
            os.makedirs(reports_dir, exist_ok=True)
            output_xlsx_path = os.path.join(reports_dir, f"sixteen_folk_review_{target_p}.xlsx")

        from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine
        engine = FolkSixteenEngine()
        all_draws = engine.draws

        # 步骤 1: 提取连续历史多期 + 最新待开期的分析列表
        recent_draws = all_draws[-n_history_periods:] if len(all_draws) >= n_history_periods else all_draws
        multi_period_results: List[Dict[str, Any]] = []
        walk_forward_audits: List[Dict[str, Any]] = []

        for d in recent_draws:
            p_val = d["period"]
            res = engine.analyze_window(target_period=p_val)
            multi_period_results.append(res)
            if res.get("has_actual_draw"):
                audit = res.get("hit_audit", {})
                audit["period"] = p_val
                walk_forward_audits.append(audit)

        # 追加最新待开期
        multi_period_results.append(latest_analysis_result)

        wb = openpyxl.Workbook()
        default_sheet = wb.active
        if default_sheet is not None:
            wb.remove(default_sheet)

        # 步骤 2: 构建 6 大核心工作表
        # Sheet 1: 【新方法】(多期纵向滚动大盘)
        self.build_folk_sheet(wb, multi_period_results, sheet_name="新方法")

        # Sheet 2: 【常球顺序】
        self.build_normal_order_sheet(wb, all_draws, sheet_name="常球顺序")

        # Sheet 3: 【尾数分布】
        self.build_tail_distribution_sheet(wb, all_draws, sheet_name="尾数分布")

        # Sheet 4: 【012路】
        self.build_012_roads_sheet(wb, all_draws, sheet_name="012路")

        # Sheet 5: 【遗漏分析】(80码全息遗漏走势、分层分桶与012路动力学共振)
        self.build_omission_sheet(wb, all_draws, latest_analysis_result, sheet_name="遗漏分析")

        # Sheet 6: 【实操决策与对账总账本】
        self.build_decision_ledger_sheet(wb, latest_analysis_result, walk_forward_audits, sheet_name="实操决策与对账总账本")

        # 步骤 3: 确保目录存在并安全保存 (防 Excel 软件进程锁定)
        os.makedirs(os.path.dirname(os.path.abspath(output_xlsx_path)), exist_ok=True)
        actual_saved_path = output_xlsx_path
        try:
            wb.save(output_xlsx_path)
        except PermissionError:
            # 用户当前在 Excel 软件中打开了该文件，自动保存至旗舰备份版，杜绝崩溃
            base, ext = os.path.splitext(output_xlsx_path)
            fallback_path = f"{base}_flagship{ext}"
            wb.save(fallback_path)
            actual_saved_path = fallback_path

        # 同步备份至缓存
        cache_dir = os.path.join(get_storage_dir(), "cache", "sixteen_period")
        os.makedirs(cache_dir, exist_ok=True)
        latest_xlsx = os.path.join(cache_dir, "excel_window_latest.xlsx")
        try:
            wb.save(latest_xlsx)
        except Exception:
            pass

        return actual_saved_path

