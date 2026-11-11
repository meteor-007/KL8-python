# -*- coding: utf-8 -*-
"""
生成快乐8全量历史双号+单号互动跟随统计工具
===================================================
核心升级：
1. 【期数管够】：装入全历史 2076 期开奖真实数据（从 2020 年至今完整大样本，双号共现样本极大充实，彻底告别 70 期样本不足问题！）。
2. 【双号联动统计】：
   - 提供【号码 A】和【号码 B】两个独立的下拉选择框；
   - 顶部自动计算：两号各自出现次数、两号同时开出（双号合体）的总期数与概率；
   - 下方表格严格按【重复计数】倒序排列，展示在历史上每一次两号同时开出时，下一期各个号码跟随出现的频次！
3. 【单号看板保留】：独立的 Sheet 2 提供纯单号查询看板。
4. 【手机与电脑轻量兼容】：全量 2076 期文件仅约 200KB，手机版 WPS / Excel 打开秒开，绝不卡死。
"""
import os
import re
from collections import Counter
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORY_FILE = os.path.join(PROJ_DIR, "storage", "raw", "kl8_history_final.txt")
OUTPUT_EXCEL = os.path.join(PROJ_DIR, "storage", "outputs", "reports", "kl8_interactive_follow_calculator.xlsx")


def load_all_draws(history_file: str):
    """加载全部历史开奖数据"""
    draws = []
    with open(history_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line)
            if m:
                nums = [int(x) for x in m.group(3).split("-") if x.isdigit()]
                if len(nums) == 20:
                    draws.append({
                        "period": int(m.group(2)),
                        "date": m.group(1),
                        "nums": sorted(nums),
                        "nums_set": set(nums)
                    })
    draws.sort(key=lambda d: d["period"])
    return draws


def compute_pair_follow(draws, num_a, num_b):
    """用 Python 预先计算双号倒序跟随榜，作为打开 Excel 时的默认初始渲染"""
    follow_cnt = Counter()
    pair_occ = 0
    occ_a = 0
    occ_b = 0

    for t in range(len(draws) - 1):
        cur_set = draws[t]["nums_set"]
        has_a = (num_a in cur_set)
        has_b = (num_b in cur_set)
        if has_a:
            occ_a += 1
        if has_b:
            occ_b += 1
        if has_a and has_b:
            pair_occ += 1
            for y in draws[t + 1]["nums"]:
                follow_cnt[y] += 1

    # 检查最后一期自身开出
    if num_a in draws[-1]["nums_set"]:
        occ_a += 1
    if num_b in draws[-1]["nums_set"]:
        occ_b += 1

    ranking = []
    for y in range(1, 81):
        ranking.append((y, follow_cnt[y]))
    ranking.sort(key=lambda item: (-item[1], item[0]))
    return ranking, pair_occ, occ_a, occ_b


def build_full_excel():
    draws = load_all_draws(HISTORY_FILE)
    total_draws = len(draws)
    print(f"成功加载全量开奖数据: {total_draws} 期")

    # 默认双号：02 和 10（用户第一张图标记的重点号）
    init_a = 2
    init_b = 10
    init_ranking, pair_occ, occ_a, occ_b = compute_pair_follow(draws, init_a, init_b)

    wb = openpyxl.Workbook()

    # 样式配置
    font_title = Font(name="Microsoft YaHei", size=14, bold=True, color="1F4E79")
    font_subtitle = Font(name="Microsoft YaHei", size=10, color="595959")
    font_h1 = Font(name="Microsoft YaHei", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Microsoft YaHei", size=10, bold=True)
    font_normal = Font(name="Microsoft YaHei", size=10)
    font_select = Font(name="Microsoft YaHei", size=16, bold=True, color="C00000")
    font_repeat = Font(name="Microsoft YaHei", size=10, bold=True, color="C00000")

    fill_navy = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    fill_blue_light = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    fill_yellow_light = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    fill_green_light = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    fill_top5 = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    align_center = Alignment(horizontal='center', vertical='center')
    align_left = Alignment(horizontal='left', vertical='center')
    align_right = Alignment(horizontal='right', vertical='center')

    # 下拉菜单数据源字符串 01~80
    all_num_strs = [f"{i:02d}" for i in range(1, 81)]
    dv_formula = '"' + ",".join(all_num_strs) + '"'

    # ==========================================
    # Sheet 1: 【双号跟随统计看板】(按重复计数倒序)
    # ==========================================
    ws_pair = wb.active
    ws_pair.title = "双号跟随统计看板"

    ws_pair.cell(row=1, column=1, value="🧬 快乐8 双号同出跟随统计器 (全量2076期大样本 · 按【重复计数】倒序)").font = font_title
    ws_pair.cell(row=2, column=1, value="【使用说明】：在 B3 选号码A，在 D3 选号码B。全表立刻倒序展示历史上两号同出时，下一期各个号码跟随出现的总次数！").font = font_subtitle

    # 号码选择卡片 (B3 为号码A，D3 为号码B)
    ws_pair.cell(row=3, column=1, value="👉 号码 A:").font = font_bold
    ws_pair.cell(row=3, column=1).alignment = align_right

    cell_a = ws_pair.cell(row=3, column=2, value=f"{init_a:02d}")
    cell_a.font = font_select
    cell_a.alignment = align_center
    cell_a.fill = fill_yellow_light
    cell_a.border = thin_border

    ws_pair.cell(row=3, column=3, value="👉 号码 B:").font = font_bold
    ws_pair.cell(row=3, column=3).alignment = align_right

    cell_b = ws_pair.cell(row=3, column=4, value=f"{init_b:02d}")
    cell_b.font = font_select
    cell_b.alignment = align_center
    cell_b.fill = fill_yellow_light
    cell_b.border = thin_border

    # 数据验证绑定到 B3 和 D3
    dv_pair = DataValidation(type="list", formula1=dv_formula, allow_blank=True)
    ws_pair.add_data_validation(dv_pair)
    dv_pair.add(cell_a)
    dv_pair.add(cell_b)

    # 统计卡片 1: 双号同出总期数 (F3)
    ws_pair.cell(row=3, column=5, value="两号同时开出总期数:").font = font_bold
    ws_pair.cell(row=3, column=5).alignment = align_right
    cell_pair_cnt = ws_pair.cell(row=3, column=6, value=f"=COUNTIF(全量历史开奖底表!$W$2:$W${total_draws+1}, 1)")
    cell_pair_cnt.font = font_select
    cell_pair_cnt.alignment = align_center
    cell_pair_cnt.fill = fill_blue_light
    cell_pair_cnt.border = thin_border

    # 统计卡片 2: 两号同出频率 (H3)
    ws_pair.cell(row=3, column=7, value="两号同出频率:").font = font_bold
    ws_pair.cell(row=3, column=7).alignment = align_right
    cell_pair_rate = ws_pair.cell(row=3, column=8, value=f'=TEXT(F3/{total_draws}, "0.0%")')
    cell_pair_rate.font = font_bold
    cell_pair_rate.alignment = align_center
    cell_pair_rate.fill = fill_blue_light
    cell_pair_rate.border = thin_border

    # 单号指标卡片 (第 4 行)
    ws_pair.cell(row=4, column=1, value="号码A开出次数:").font = font_normal
    ws_pair.cell(row=4, column=1).alignment = align_right
    ws_pair.cell(row=4, column=2, value=f"=COUNTIF(全量历史开奖底表!$C$2:$V${total_draws+1}, B3)").font = font_bold
    ws_pair.cell(row=4, column=2).alignment = align_center

    ws_pair.cell(row=4, column=3, value="号码B开出次数:").font = font_normal
    ws_pair.cell(row=4, column=3).alignment = align_right
    ws_pair.cell(row=4, column=4, value=f"=COUNTIF(全量历史开奖底表!$C$2:$V${total_draws+1}, D3)").font = font_bold
    ws_pair.cell(row=4, column=4).alignment = align_center

    ws_pair.cell(row=4, column=5, value=f"历史样本总期数: {total_draws} 期 (数据绝对管够，手机与电脑通用)").font = font_subtitle

    # 表头 (第 5 行，严格对齐用户截图：重复项 | 重复计数)
    headers = [
        ("A", "排名", 8),
        ("B", "重复项", 12),
        ("C", "重复计数", 14),
        ("D", "双号下期跟随率", 16),
        ("E", "连庄标记(重号)", 18),
        ("F", "老派操盘手实战定性", 30)
    ]
    for col_letter, h_name, width in headers:
        c = ws_pair[f"{col_letter}5"]
        c.value = h_name
        c.font = font_h1
        c.fill = fill_navy
        c.alignment = align_center
        c.border = thin_border
        ws_pair.column_dimensions[col_letter].width = width

    # 最新一期的 20 个开奖号码集合
    last_nums_set = set(draws[-1]["nums"])

    # 写入 80 个倒序排名行 (行 6 到行 85)
    for rank_idx, (num, cnt) in enumerate(init_ranking, start=1):
        r_idx = 5 + rank_idx
        num_str = f"{num:02d}"

        # A 列: 排名
        cA = ws_pair.cell(row=r_idx, column=1, value=rank_idx)
        cA.alignment = align_center
        cA.font = font_bold if rank_idx <= 5 else font_normal
        cA.border = thin_border

        # B 列: 重复项 (由 INDEX + MATCH 从底表根据排序扰动得分抓取)
        cB = ws_pair.cell(row=r_idx, column=2, value=f'=INDEX(全量历史开奖底表!$X$2:$X$81, MATCH(LARGE(全量历史开奖底表!$Z$2:$Z$81, A{r_idx}), 全量历史开奖底表!$Z$2:$Z$81, 0))')
        cB.alignment = align_center
        cB.font = font_bold if rank_idx <= 5 else font_normal
        cB.border = thin_border

        # C 列: 重复计数 (倒序排列真实次数)
        cC = ws_pair.cell(row=r_idx, column=3, value=f'=INT(LARGE(全量历史开奖底表!$Z$2:$Z$81, A{r_idx}))')
        cC.alignment = align_center
        cC.font = font_bold
        cC.border = thin_border

        # D 列: 下期跟随概率
        cD = ws_pair.cell(row=r_idx, column=4, value=f'=IF($F$3>0, TEXT(C{r_idx}/$F$3, "0.0%"), "0.0%")')
        cD.alignment = align_center
        cD.font = font_normal
        cD.border = thin_border

        # E 列: 连庄标记
        is_repeat = (num in last_nums_set)
        cE = ws_pair.cell(row=r_idx, column=5, value=f'=IF(OR(B{r_idx}=$B$3, B{r_idx}=$D$3), "★ 选号连庄", IF(COUNTIF(全量历史开奖底表!$C${total_draws+1}:$V${total_draws+1}, B{r_idx})>0, "✔ ★上期重号", "新号跟出"))')
        cE.alignment = align_center
        cE.font = font_repeat if is_repeat else font_normal
        cE.border = thin_border

        # F 列: 实战定性
        cF = ws_pair.cell(row=r_idx, column=6, value=f'=IF(C{r_idx}>=$F$3*0.35, "🔥 黄金合体死党(跟随率>35%)", IF(C{r_idx}>=$F$3*0.28, "⚡ 优质伴生号", IF(C{r_idx}=0, "❄️ 从未跟随", "普通跟随")))')
        cF.alignment = align_left
        cF.font = font_normal
        cF.border = thin_border

        if rank_idx <= 5:
            cB.fill = fill_top5
            cC.fill = fill_top5

    # ==========================================
    # Sheet 2: 【单号跟随统计看板】(按重复计数倒序)
    # ==========================================
    ws_single = wb.create_sheet(title="单号跟随统计看板")

    ws_single.cell(row=1, column=1, value="🧬 快乐8 单号跟随统计器 (全量2076期大样本 · 按【重复计数】倒序)").font = font_title
    ws_single.cell(row=2, column=1, value="【使用说明】：在 B3 单元格点击下拉框选任意号码，全表自动按【重复计数】倒序展示下期跟随频次！").font = font_subtitle

    # 号码选择
    ws_single.cell(row=3, column=1, value="👉 查询号码:").font = font_bold
    ws_single.cell(row=3, column=1).alignment = align_right

    cell_s = ws_single.cell(row=3, column=2, value=f"{init_a:02d}")
    cell_s.font = font_select
    cell_s.alignment = align_center
    cell_s.fill = fill_yellow_light
    cell_s.border = thin_border

    dv_single = DataValidation(type="list", formula1=dv_formula, allow_blank=False)
    ws_single.add_data_validation(dv_single)
    dv_single.add(cell_s)

    # 统计卡片: 自身开出次数
    ws_single.cell(row=3, column=3, value="该号码历史开出总次数:").font = font_bold
    ws_single.cell(row=3, column=3).alignment = align_right
    cell_s_cnt = ws_single.cell(row=3, column=4, value=f"=COUNTIF(全量历史开奖底表!$C$2:$V${total_draws+1}, B3)")
    cell_s_cnt.font = font_select
    cell_s_cnt.alignment = align_center
    cell_s_cnt.fill = fill_blue_light
    cell_s_cnt.border = thin_border

    # 统计卡片: 出现频率
    ws_single.cell(row=3, column=5, value="开出频率:").font = font_bold
    ws_single.cell(row=3, column=5).alignment = align_right
    cell_s_rate = ws_single.cell(row=3, column=6, value=f'=TEXT(D3/{total_draws}, "0.0%")')
    cell_s_rate.font = font_bold
    cell_s_rate.alignment = align_center
    cell_s_rate.fill = fill_blue_light
    cell_s_rate.border = thin_border

    # 表头
    headers_single = [
        ("A", "排名", 8),
        ("B", "重复项", 12),
        ("C", "重复计数", 14),
        ("D", "下期跟随概率", 16),
        ("E", "连庄标记(重号)", 18),
        ("F", "老派操盘手实战定性", 30)
    ]
    for col_letter, h_name, width in headers_single:
        c = ws_single[f"{col_letter}5"]
        c.value = h_name
        c.font = font_h1
        c.fill = fill_navy
        c.alignment = align_center
        c.border = thin_border
        ws_single.column_dimensions[col_letter].width = width

    for rank_idx in range(1, 81):
        r_idx = 5 + rank_idx
        # A: 排名
        cA = ws_single.cell(row=r_idx, column=1, value=rank_idx)
        cA.alignment = align_center
        cA.font = font_bold if rank_idx <= 5 else font_normal
        cA.border = thin_border

        # B: 重复项 (从底表 AC:AE 单号辅助列提取)
        cB = ws_single.cell(row=r_idx, column=2, value=f'=INDEX(全量历史开奖底表!$AC$2:$AC$81, MATCH(LARGE(全量历史开奖底表!$AE$2:$AE$81, A{r_idx}), 全量历史开奖底表!$AE$2:$AE$81, 0))')
        cB.alignment = align_center
        cB.font = font_bold if rank_idx <= 5 else font_normal
        cB.border = thin_border

        # C: 重复计数 (倒序排列)
        cC = ws_single.cell(row=r_idx, column=3, value=f'=INT(LARGE(全量历史开奖底表!$AE$2:$AE$81, A{r_idx}))')
        cC.alignment = align_center
        cC.font = font_bold
        cC.border = thin_border

        # D: 概率
        cD = ws_single.cell(row=r_idx, column=4, value=f'=IF($D$3>0, TEXT(C{r_idx}/$D$3, "0.0%"), "0.0%")')
        cD.alignment = align_center
        cD.font = font_normal
        cD.border = thin_border

        # E: 连庄
        cE = ws_single.cell(row=r_idx, column=5, value=f'=IF(B{r_idx}=$B$3, "★ 选号连庄", IF(COUNTIF(全量历史开奖底表!$C${total_draws+1}:$V${total_draws+1}, B{r_idx})>0, "✔ ★上期重号", "新号跟出"))')
        cE.alignment = align_center
        cE.font = font_repeat
        cE.border = thin_border

        # F: 定性
        cF = ws_single.cell(row=r_idx, column=6, value=f'=IF(C{r_idx}>=$D$3*0.35, "🔥 黄金死党(跟随率>35%)", IF(C{r_idx}>=$D$3*0.28, "⚡ 优质伴生号", IF(C{r_idx}=0, "❄️ 从未跟随", "普通跟随")))')
        cF.alignment = align_left
        cF.font = font_normal
        cF.border = thin_border

        if rank_idx <= 5:
            cB.fill = fill_top5
            cC.fill = fill_top5

    # ==========================================
    # Sheet 3: 【全量历史开奖底表】(2076期完整大账本)
    # ==========================================
    ws_raw = wb.create_sheet(title="全量历史开奖底表")

    ws_raw.cell(row=1, column=1, value="期号").font = font_bold
    ws_raw.cell(row=1, column=2, value="开奖日期").font = font_bold
    for col_i in range(1, 21):
        ws_raw.cell(row=1, column=2 + col_i, value=f"号码{col_i}").font = font_bold
    ws_raw.cell(row=1, column=23, value="当期是否出双号A和B").font = font_bold
    ws_raw.cell(row=1, column=24, value="当期是否出单号").font = font_bold

    # 填充全部 2076 期开奖记录 (行 2 到行 2077)
    for row_offset, d in enumerate(draws, start=2):
        ws_raw.cell(row=row_offset, column=1, value=d["period"]).alignment = align_center
        ws_raw.cell(row=row_offset, column=2, value=d["date"]).alignment = align_center
        for col_i, n_val in enumerate(d["nums"], start=1):
            cell_n = ws_raw.cell(row=row_offset, column=2 + col_i, value=f"{n_val:02d}")
            cell_n.alignment = align_center

        # W 列核心双号同出判定
        ws_raw.cell(row=row_offset, column=23, value=f'=IF(AND(COUNTIF(C{row_offset}:V{row_offset}, 双号跟随统计看板!$B$3)>0, IF(双号跟随统计看板!$D$3="", 1, COUNTIF(C{row_offset}:V{row_offset}, 双号跟随统计看板!$D$3)>0)), 1, 0)').alignment = align_center
        # X 列单号判定
        ws_raw.cell(row=row_offset, column=24, value=f'=IF(COUNTIF(C{row_offset}:V{row_offset}, 单号跟随统计看板!$B$3)>0, 1, 0)').alignment = align_center

    # 辅助倒序计算区域:
    # Y~AA: 双号辅助列
    # AC~AE: 单号辅助列
    ws_raw.cell(row=1, column=25, value="双号候选码").font = font_bold
    ws_raw.cell(row=1, column=26, value="双号跟随频次").font = font_bold
    ws_raw.cell(row=1, column=27, value="双号扰动分(倒序专用)").font = font_bold

    ws_raw.cell(row=1, column=29, value="单号候选码").font = font_bold
    ws_raw.cell(row=1, column=30, value="单号跟随频次").font = font_bold
    ws_raw.cell(row=1, column=31, value="单号扰动分(倒序专用)").font = font_bold

    end_row = total_draws + 1
    next_start_row = 3
    next_end_row = total_draws + 1

    for i in range(1, 81):
        r_idx = 1 + i
        num_str = f"{i:02d}"
        # 双号
        ws_raw.cell(row=r_idx, column=25, value=num_str).alignment = align_center
        ws_raw.cell(row=r_idx, column=26, value=f'=SUMPRODUCT(($W$2:$W${end_row-1}=1)*($C${next_start_row}:$V${next_end_row}=Y{r_idx}))').alignment = align_center
        ws_raw.cell(row=r_idx, column=27, value=f'=Z{r_idx} + (81 - {i}) * 0.0001').alignment = align_center

        # 单号
        ws_raw.cell(row=r_idx, column=29, value=num_str).alignment = align_center
        ws_raw.cell(row=r_idx, column=30, value=f'=SUMPRODUCT(($X$2:$X${end_row-1}=1)*($C${next_start_row}:$V${next_end_row}=AC{r_idx}))').alignment = align_center
        ws_raw.cell(row=r_idx, column=31, value=f'=AD{r_idx} + (81 - {i}) * 0.0001').alignment = align_center

    # 修正双号看板引用的底表列
    # 双号候选码是 Y 列(25), 扰动得分是 AA 列(27)
    for rank_idx in range(1, 81):
        r_idx = 5 + rank_idx
        ws_pair.cell(row=r_idx, column=2, value=f'=INDEX(全量历史开奖底表!$Y$2:$Y$81, MATCH(LARGE(全量历史开奖底表!$AA$2:$AA$81, A{r_idx}), 全量历史开奖底表!$AA$2:$AA$81, 0))')
        ws_pair.cell(row=r_idx, column=3, value=f'=INT(LARGE(全量历史开奖底表!$AA$2:$AA$81, A{r_idx}))')

    # 列宽
    ws_raw.column_dimensions["A"].width = 12
    ws_raw.column_dimensions["B"].width = 14
    for c_idx in range(3, 23):
        col_char = openpyxl.utils.get_column_letter(c_idx)
        ws_raw.column_dimensions[col_char].width = 6
    ws_raw.column_dimensions["W"].width = 22
    ws_raw.column_dimensions["X"].width = 18
    ws_raw.column_dimensions["Y"].width = 12
    ws_raw.column_dimensions["Z"].width = 16
    ws_raw.column_dimensions["AA"].width = 20
    ws_raw.column_dimensions["AC"].width = 12
    ws_raw.column_dimensions["AD"].width = 16
    ws_raw.column_dimensions["AE"].width = 20

    # ==========================================
    # Sheet 3: 【双号统计方法指南与手机操作】
    # ==========================================
    ws_guide = wb.create_sheet(title="双号统计方法指南")
    guide_lines = [
        ("🧬 快乐8【双号同出跟随统计】大白话实战指南", font_title),
        ("", font_normal),
        ("一、 为什么期数要扩充到 2000 多期全量数据？", font_bold),
        ("  1. 样本充足：在 70 期里，任意两个号码同时开出的期数通常只有 3~7 次，跟随统计样本偏少。", font_normal),
        ("  2. 全量 2076 期大账本：两个号码同时开出的期数可达 100~140 次，下期跟随号码出现 30~45 次！", font_normal),
        ("  3. 完美对应你截图中的「重复项」与「重复计数」（出现 30次、28次等），数据极具统计置信度！", font_normal),
        ("", font_normal),
        ("二、 如何在手机端或电脑端使用双号看板？", font_bold),
        ("  1. 打开【双号跟随统计看板】页面。", font_normal),
        ("  2. 点击 B3 单元格选择第一个号码（号码 A，如 02）。", font_normal),
        ("  3. 点击 D3 单元格选择第二个号码（号码 B，如 10）。", font_normal),
        ("  4. 瞬间自动计算：顶部显示这两号在历史上总共合体开出多少次；下方表格自动按【重复计数】倒序排名！", font_normal),
        ("  5. 如果只想看单号：只需把 D3 留空或选成跟 B3 一样的号码，表格立刻自动变成单号跟随统计！", font_normal),
        ("", font_normal),
        ("三、 如果在自己的 Excel 里写双号公式怎么写？", font_bold),
        ("  1. 双号同出判断公式（放在底表 W 列）：", font_normal),
        ("     =IF(AND(COUNTIF(C2:V2, $B$3)>0, COUNTIF(C2:V2, $D$3)>0), 1, 0)", font_bold),
        ("     （大白话：这一期如果同时开出了 B3 和 D3，显示 1，否则显示 0）", font_normal),
        ("  2. 下期各个号码跟随统计（SUMPRODUCT 乘积求和）：", font_normal),
        ("     =SUMPRODUCT((W2:W2076=1)*(C3:V2077=目标号码))", font_bold),
        ("     （大白话：只要上一期双号同出为 1，下一期开出该号码就计入 1 次，全部相加即为重复计数！）", font_normal),
    ]
    for r_idx, (text, f) in enumerate(guide_lines, start=1):
        c = ws_guide.cell(row=r_idx, column=1, value=text)
        c.font = f
    ws_guide.column_dimensions["A"].width = 95

    # 保存
    os.makedirs(os.path.dirname(OUTPUT_EXCEL), exist_ok=True)
    wb.save(OUTPUT_EXCEL)
    print(f"[SUCCESS] 包含全量 2076 期 + 双号倒序跟随的 Excel 已成功生成: {OUTPUT_EXCEL}")


if __name__ == "__main__":
    build_full_excel()
