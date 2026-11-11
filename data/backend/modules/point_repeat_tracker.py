# -*- coding: utf-8 -*-
"""
点位重码追踪与自动更新引擎 (PointRepeatTracker)
==============================================
【业务背景与架构定位】:
本模块专为全量追踪与复盘“点位重码”核心压舱石指标设计。
遵照用户明确指令：
1. 取消从 250 期截断的逻辑，从系统目前已经录入的第一期点位（2025316期）开始，全量覆盖所有已录期（307+期）；
2. 逐期精准核算：
   - 点位重码的个数（当期点位与上期开奖重叠码，大白话：看点位挑中了几个上期落号）；
   - 点位重码出号个数（当期开奖实际开出的重码数，已开奖 100% 刷上图1原版翠绿背景 #00B050）；
   - 点位连重码（点位与上期点位重叠码）；
   - 点位总出号数（20个点位当期中奖总数）；
3. 生成 1:1 像素级复刻图1样式的 Excel 报告 (storage/outputs/reports/点位重码出号追踪表.xlsx)；
4. 随着每日开奖和录入点位，自动追加最新行并上色，彻底免除手动维护。

@author Antigravity Quantitative Trading Team
@since 2026-10-12
"""

import os
import sys
import re
import json
from typing import Dict, List, Optional, Tuple, Any

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# 路径自省与环境对齐
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_CURRENT_DIR))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

LEDGER_PATH = os.path.join(_PROJECT_ROOT, "storage", "reviews", "point_repeat_tracker_ledger.json")
EXCEL_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "storage", "outputs", "reports")
EXCEL_OUTPUT_FILE = os.path.join(EXCEL_OUTPUT_DIR, "点位重码出号追踪表.xlsx")
REPORT_COPY_FILE = os.path.join(_PROJECT_ROOT, "storage", "reports", "点位重码出号追踪表.xlsx")
POINTS_FILE = os.path.join(_PROJECT_ROOT, "storage", "raw", "daily_points.txt")
HISTORY_FILE = os.path.join(_PROJECT_ROOT, "storage", "raw", "kl8_history_final.txt")
TRI_HIGH_FILE = os.path.join(_PROJECT_ROOT, "storage", "points", "tri_high_points.json")


def load_draw_history() -> Dict[str, List[int]]:
    """加载历史开奖号码映射表: {期号: 开奖号码列表}"""
    history: Dict[str, List[int]] = {}
    if not os.path.exists(HISTORY_FILE):
        return history
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            m_iss = re.search(r"period:(\d+)", line)
            m_nums = re.search(r"numbers:([\d-]+)", line)
            if m_iss and m_nums:
                p = m_iss.group(1)
                nums = [int(x) for x in m_nums.group(1).split("-") if x.strip()]
                history[p] = sorted(nums)
    return history


def load_daily_points() -> Dict[str, Dict[str, Any]]:
    """加载每日点位全量映射表: {期号: {date, points}}"""
    points: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(POINTS_FILE):
        return points
    with open(POINTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            m_date = re.search(r"date:([\d-]+)", line)
            m_iss = re.search(r"period:(\d+)", line)
            m_pts = re.search(r"points:([\d\s]+)", line)
            if m_iss and m_pts:
                p = m_iss.group(1)
                d_str = m_date.group(1) if m_date else ""
                nums = [int(x) for x in m_pts.group(1).split() if x.strip()]
                points[p] = {
                    "date": d_str,
                    "points": sorted(nums)
                }
    return points


def load_tri_high_data() -> Dict[str, Dict[str, Any]]:
    """加载三高点位数据: {期号: 数据字典}"""
    result: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(TRI_HIGH_FILE):
        return result
    try:
        with open(TRI_HIGH_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
            records = d.get("records", [])
            for r in records:
                p = str(r.get("period", ""))
                if p:
                    result[p] = r
    except Exception as e:
        print(f"[WARN] 读取三高数据异常: {e}")
    return result


def find_previous_period(period_str: str, available_periods: List[str]) -> Optional[str]:
    """
    工业级自适应查找前一期期号：
    1. 优先使用二分/数值逆序匹配小于当前期号的最大有效历史期号（100% 免疫跨年、断期与跳号）；
    2. 兜底回退至索引前序或算术减一。
    """
    if not available_periods:
        return None

    try:
        target_int = int(period_str)
        # 从已有期号列表中寻找满足 int(x) < target_int 的最大期号
        candidates = [p for p in available_periods if int(p) < target_int]
        if candidates:
            # 候选列表中按数值最大的即为直接前驱期
            return max(candidates, key=lambda x: int(x))
    except Exception:
        pass

    # 兜底：直接列表索引查找
    try:
        idx = available_periods.index(period_str)
        if idx > 0:
            return available_periods[idx - 1]
    except ValueError:
        pass

    return None


def calculate_full_history_ledger() -> List[Dict[str, Any]]:
    """
    全量计算从库里最早录入的第一期点位开始的所有追踪记录：
    1. 收集 daily_points.txt 中的所有期号；
    2. 按数值/时序升序严格排序；
    3. 逐期计算重码集合、重码数、当期出号、命中率；
    4. 返回完整结构化账本列表。
    """
    points_dict = load_daily_points()
    history_map = load_draw_history()
    tri_high_map = load_tri_high_data()

    if not points_dict:
        return []

    # 排序所有点位期号 (例如 2025316 -> 2026271)
    sorted_periods = sorted(points_dict.keys(), key=lambda x: int(x))
    history_sorted_keys = sorted(history_map.keys(), key=lambda x: int(x))

    ledger: List[Dict[str, Any]] = []

    for idx, p in enumerate(sorted_periods):
        pts_info = points_dict[p]
        curr_pts = pts_info["points"]
        p_date = pts_info["date"]
        
        # 确定上一期号（优先在开奖历史中匹配前一期）
        prev_p = find_previous_period(p, history_sorted_keys)
        if not prev_p and idx > 0:
            prev_p = sorted_periods[idx - 1]

        prev_draw = history_map.get(prev_p, []) if prev_p else []
        prev_pts = points_dict.get(prev_p, {}).get("points", []) if prev_p else []

        is_drawn = p in history_map
        curr_draw = history_map.get(p, [])

        # 核心指标 1: 点位重码（当期点位与上期开奖重叠，彩票标准重号/落号）
        repeat_nums = sorted([n for n in curr_pts if n in prev_draw])
        repeat_count = len(repeat_nums)

        # 核心指标 2: 点位连重码（当期点位与上期点位重叠）
        conn_repeat_nums = sorted([n for n in curr_pts if n in prev_pts])
        conn_repeat_count = len(conn_repeat_nums)

        # 三高自选重码 (若当期有录入)
        user_repeat_high = []
        if p in tri_high_map:
            user_repeat_high = tri_high_map[p].get("repeat_high", [])

        # 当期出号计算
        if is_drawn and curr_draw:
            hit_repeat = sorted([n for n in repeat_nums if n in curr_draw])
            hit_repeat_count = len(hit_repeat)
            hit_rate = round(hit_repeat_count / max(repeat_count, 1) * 100, 1) if repeat_count > 0 else 0.0

            hit_conn = sorted([n for n in conn_repeat_nums if n in curr_draw])
            hit_conn_count = len(hit_conn)

            total_pts_hits = sorted([n for n in curr_pts if n in curr_draw])
            total_pts_hit_count = len(total_pts_hits)

            item = {
                "period": p,
                "date": p_date,
                "prev_period": prev_p,
                "points_count": len(curr_pts),
                "repeat_count": repeat_count,
                "repeat_numbers": repeat_nums,
                "hit_count": hit_repeat_count,
                "hit_numbers": hit_repeat,
                "hit_rate": hit_rate,
                "conn_repeat_count": conn_repeat_count,
                "conn_repeat_numbers": conn_repeat_nums,
                "conn_hit_count": hit_conn_count,
                "conn_hit_numbers": hit_conn,
                "total_pts_hit_count": total_pts_hit_count,
                "total_pts_hits": total_pts_hits,
                "user_repeat_high": user_repeat_high,
                "is_drawn": True,
                "status": "已开奖"
            }
        else:
            # 待开奖最新期 (如 2026271)
            item = {
                "period": p,
                "date": p_date,
                "prev_period": prev_p,
                "points_count": len(curr_pts),
                "repeat_count": repeat_count,
                "repeat_numbers": repeat_nums,
                "hit_count": None,
                "hit_numbers": [],
                "hit_rate": None,
                "conn_repeat_count": conn_repeat_count,
                "conn_repeat_numbers": conn_repeat_nums,
                "conn_hit_count": None,
                "conn_hit_numbers": [],
                "total_pts_hit_count": None,
                "total_pts_hits": [],
                "user_repeat_high": user_repeat_high,
                "is_drawn": False,
                "status": "待开奖"
            }
        ledger.append(item)

    return ledger


def export_full_fig1_excel(ledger: List[Dict[str, Any]]) -> str:
    """
    1:1 像素级复刻图1样式的全量 Excel 表格渲染器：
    - 容纳全部已录入点位期号（从 2025316 开始，307+ 期）；
    - 关键核心两列保持与图1完全一致：
      - 列 C: 点位重码的个数（青色表头 #33CCCC）
      - 列 D: 点位重码出号个数（已开奖数据单元格 100% 刷上图1原版翠绿高亮 #00B050）
    - 增设辅助核算列：出号明细、点位连重码、20码总中奖数。
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "点位重码全量追踪"

    # 网格线开启
    ws.views.sheetView[0].showGridLines = True

    # 字体
    font_header = Font(name="微软雅黑", size=11, bold=True, color="000000")
    font_bold = Font(name="微软雅黑", size=11, bold=True, color="000000")
    font_regular = Font(name="微软雅黑", size=10, bold=False, color="000000")
    font_pending = Font(name="微软雅黑", size=10, bold=False, color="7F7F7F")

    # 边框
    border_side = Side(style="thin", color="000000")
    cell_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)

    # 填充色定义
    fill_col_seq = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    fill_col_b_header = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid") # 淡蓝浅灰
    fill_col_c_header = PatternFill(start_color="33CCCC", end_color="33CCCC", fill_type="solid") # 图1原版青蓝 #33CCCC
    fill_col_d_header = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid") # 白底
    fill_col_e_header = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid") # 图1原版黄色 #FFF2CC
    fill_col_other_header = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") # 浅绿

    # 图1核心高亮绿色 (#00B050)
    fill_green_data = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
    fill_sub_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    fill_pending_data = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # 表头清单
    headers = [
        ("A1", "序号", fill_col_seq),
        ("B1", "期数", fill_col_b_header),
        ("C1", "点位重码\n的个数", fill_col_c_header),
        ("D1", "点位重码\n出号个数", fill_col_d_header),
        ("E1", "点位重码\n出号明细", fill_col_e_header),
        ("F1", "点位连重码\n(与上期点位)", fill_col_other_header),
        ("G1", "点位连重码\n出号个数", fill_col_other_header),
        ("H1", "点位总出号数\n(20码中奖)", fill_col_b_header),
        ("I1", "开奖状态/说明", fill_col_seq),
    ]

    ws.row_dimensions[1].height = 42
    for cell_pos, text, fill_color in headers:
        c = ws[cell_pos]
        c.value = text
        c.font = font_header
        c.alignment = align_center
        c.fill = fill_color
        c.border = cell_border

    # 列宽
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 13
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 24
    ws.column_dimensions["F"].width = 15
    ws.column_dimensions["G"].width = 14
    ws.column_dimensions["H"].width = 15
    ws.column_dimensions["I"].width = 18

    # 逐行填入全量数据
    curr_row = 2
    for idx, item in enumerate(ledger, 1):
        p_full = str(item["period"])
        is_drawn = item["is_drawn"]
        
        ws.row_dimensions[curr_row].height = 22

        # A: 序号
        cA = ws.cell(row=curr_row, column=1, value=idx)
        cA.font = font_regular
        cA.alignment = align_center
        cA.border = cell_border

        # B: 期数 (加粗居中，类型防御)
        p_val = int(p_full) if str(p_full).isdigit() else str(p_full)
        cB = ws.cell(row=curr_row, column=2, value=p_val)
        cB.font = font_bold
        cB.alignment = align_center
        cB.border = cell_border

        # C: 点位重码的个数
        cC = ws.cell(row=curr_row, column=3, value=item["repeat_count"])
        cC.font = font_regular
        cC.alignment = align_center
        cC.border = cell_border

        # D: 点位重码出号个数 (图1原版翠绿高亮列！)
        cD = ws.cell(row=curr_row, column=4)
        cD.alignment = align_center
        cD.border = cell_border

        # E: 出号明细
        cE = ws.cell(row=curr_row, column=5)
        cE.alignment = align_center
        cE.border = cell_border

        # F: 点位连重码
        cF = ws.cell(row=curr_row, column=6, value=item["conn_repeat_count"])
        cF.font = font_regular
        cF.alignment = align_center
        cF.border = cell_border

        # G: 连重码出号
        cG = ws.cell(row=curr_row, column=7)
        cG.alignment = align_center
        cG.border = cell_border

        # H: 点位总出号数 (20码命中)
        cH = ws.cell(row=curr_row, column=8)
        cH.alignment = align_center
        cH.border = cell_border

        # I: 状态
        cI = ws.cell(row=curr_row, column=9)
        cI.alignment = align_center
        cI.border = cell_border

        if is_drawn:
            # 填入出号数并刷上翠绿高亮！
            cD.value = item["hit_count"]
            cD.font = font_bold
            cD.fill = fill_green_data

            hit_nums_str = " ".join(f"{x:02d}" for x in item["hit_numbers"]) if item["hit_numbers"] else "无开出"
            cE.value = hit_nums_str
            cE.font = font_regular

            cG.value = item["conn_hit_count"]
            cG.font = font_bold
            cG.fill = fill_sub_green

            cH.value = item["total_pts_hit_count"]
            cH.font = font_bold

            cI.value = f"已开奖 ({item['date']})"
            cI.font = font_regular
        else:
            # 最新未开奖期
            cD.value = ""
            cD.font = font_pending
            cD.fill = fill_pending_data

            rep_candidates = " ".join(f"{x:02d}" for x in item["repeat_numbers"])
            cE.value = f"预选重码: {rep_candidates}" if rep_candidates else "待开奖"
            cE.font = font_pending

            cG.value = ""
            cG.fill = fill_pending_data

            cH.value = ""
            cH.fill = fill_pending_data

            cI.value = "今晚21:30开奖自动回填"
            cI.font = font_pending

        curr_row += 1

    # 保存 Excel (安全防御：防止 Windows 下 Excel 软件独占锁定导致 PermissionError 崩溃)
    os.makedirs(EXCEL_OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(REPORT_COPY_FILE), exist_ok=True)
    for target_path in [EXCEL_OUTPUT_FILE, REPORT_COPY_FILE]:
        try:
            wb.save(target_path)
        except PermissionError:
            print(f"[WARN] 文件正在被其他程序占用: {target_path}，转存至备用文件...")
            backup_path = target_path.replace(".xlsx", "_backup.xlsx")
            wb.save(backup_path)

    return EXCEL_OUTPUT_FILE


def sync_and_update_tracker(target_period: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    全量更新与同步驱动函数：
    1. 计算自最早录入期起的全量账本；
    2. 持久化存储到 JSON 账本；
    3. 导出全量 1:1 图1风格 Excel。
    """
    ledger = calculate_full_history_ledger()
    if not ledger:
        return []

    # 持久化存储
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)

    # 导出 Excel
    export_full_fig1_excel(ledger)

    return ledger


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="点位重码全量追踪与自动更新引擎")
    parser.add_argument("--period", type=str, default="2026271", help="目标期号")
    args = parser.parse_args()

    print("================================================================================")
    print(" [*] 点位重码全量追踪与自动更新引擎 (PointRepeatTracker) 启动")
    print("================================================================================")
    updated_ledger = sync_and_update_tracker(target_period=args.period)
    
    first_p = updated_ledger[0]["period"] if updated_ledger else "N/A"
    last_p = updated_ledger[-1]["period"] if updated_ledger else "N/A"
    print(f"[OK] 账本全量同步完毕！共计追踪 {len(updated_ledger)} 期点位数据")
    print(f"     起止范围: 第 {first_p} 期  至  第 {last_p} 期")
    print("--------------------------------------------------------------------------------")
    print(f"{'序号':^6} | {'期号':^8} | {'重码数':^8} | {'出号数(绿底)':^14} | {'明细 / 状态'}")
    print("--------------------------------------------------------------------------------")
    # 展示前 3 期和后 8 期
    sample_items = updated_ledger[:3] + updated_ledger[-8:]
    for r in sample_items:
        p = r["period"]
        rc = r["repeat_count"]
        hc = r["hit_count"] if r["is_drawn"] else "待开奖"
        st = " ".join(f"{x:02d}" for x in r.get("hit_numbers", [])) if r["is_drawn"] else "今晚开奖自动回填"
        print(f"{'':^6} | {p:^8} | {rc:^8} | {str(hc):^14} | {st}")
    print("--------------------------------------------------------------------------------")
    print("图1风格全量 Excel 报表已生成:")
    print(f"   -> {EXCEL_OUTPUT_FILE}")
    print("================================================================================")
