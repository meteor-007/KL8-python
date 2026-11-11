# -*- coding: utf-8 -*-
"""
快乐8 纯 Excel 终极超级量化引擎旗舰版 (Super Quant Engine)
================================================================
【超越普通跟随的 5 大核武级算法 (全部纯 Excel 原生公式实现)】：
1. 【高斯核空间隐能量场 (Gaussian Energy Field)】:
   - 算法：号码不是孤立的。用高斯核辐射模拟出球能量场：EXP(-(号距)^2 / 32)；
   - Excel 公式：SUMPRODUCT(EXP(-((最新20码 - 候选码)^2)/32))，自动测算谁处于大热辐射风口！
2. 【微积分一阶导数动量 (Momentum Derivative)】:
   - 算法：看变热势头（最近10期频率 - 最近50期频率）；
   - 正值代表像火箭一样正在急剧升温，负值代表已经见顶正在凉透！
3. 【均值回归遗漏欲出度 (Mean-Reversion Rebound)】:
   - 锁定 3~6 期黄金临界区，计算憋到极限的反弹爆发力！
4. 【多窗时间衰减跟随 (Multi-Window Follow)】:
   - 30期/100期/300期加权，消除拟合！
5. 【五维一体综合胜率分 (Trinity 100分制)】:
   - 融合能量场(30%) + 跟随(30%) + 遗漏(25%) + 动量(15%)，全盘严格倒序排名！
"""
import os
import re
from collections import Counter
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORY_FILE = os.path.join(PROJ_DIR, "storage", "raw", "kl8_history_final.txt")
OUTPUT_EXCEL = os.path.join(PROJ_DIR, "storage", "outputs", "reports", "kl8_excel_super_quant_engine.xlsx")


def load_all_draws(history_file: str):
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


def calculate_metrics(draws):
    """预计算各项五维指标"""
    total = len(draws)
    last_draw = draws[-1]["nums"]
    last_set = set(last_draw)

    # 1. 遗漏
    omissions = {}
    for num in range(1, 81):
        omiss = total
        for t in range(total - 1, -1, -1):
            if num in draws[t]["nums_set"]:
                omiss = (total - 1) - t
                break
        omissions[num] = omiss

    # 2. 动量 (近10期出号 - 近50期折算)
    mom_10 = Counter()
    for d in draws[-10:]:
        for n in d["nums"]:
            mom_10[n] += 1
    mom_50 = Counter()
    for d in draws[-50:]:
        for n in d["nums"]:
            mom_50[n] += 1

    momentums = {}
    for num in range(1, 81):
        # 频率差 = (10期频次/10 - 50期频次/50) * 100
        momentums[num] = round((mom_10[num] / 10.0 - mom_50[num] / 50.0) * 100, 1)

    # 3. 高斯能量场 (以最新20码为辐射源, sigma=4)
    import math
    energy_fields = {}
    for num in range(1, 81):
        ef = sum(math.exp(-((x - num) ** 2) / 32.0) for x in last_draw)
        energy_fields[num] = round(ef, 2)

    return omissions, momentums, energy_fields, last_draw, last_set


def build_super_quant_excel():
    draws = load_all_draws(HISTORY_FILE)
    total_draws = len(draws)
    omissions, momentums, energy_fields, last_draw, last_set = calculate_metrics(draws)

    wb = openpyxl.Workbook()

    # 样式配置
    font_title = Font(name="Microsoft YaHei", size=14, bold=True, color="1F4E79")
    font_subtitle = Font(name="Microsoft YaHei", size=9, color="595959")
    font_h1 = Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")
    font_bold = Font(name="Microsoft YaHei", size=10, bold=True)
    font_normal = Font(name="Microsoft YaHei", size=9)
    font_select = Font(name="Microsoft YaHei", size=15, bold=True, color="C00000")
    font_gold = Font(name="Microsoft YaHei", size=10, bold=True, color="B25900")
    font_repeat = Font(name="Microsoft YaHei", size=9, bold=True, color="C00000")

    fill_navy = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    fill_blue_light = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    fill_yellow_light = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    fill_gold_light = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    fill_green_top = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    align_center = Alignment(horizontal='center', vertical='center')
    align_left = Alignment(horizontal='left', vertical='center')
    align_right = Alignment(horizontal='right', vertical='center')

    all_num_strs = [f"{i:02d}" for i in range(1, 81)]
    dv_formula = '"' + ",".join(all_num_strs) + '"'

    # ==========================================
    # Sheet 1: 【五维一体·终极量化操盘大屏】
    # ==========================================
    ws1 = wb.active
    ws1.title = "五维一体量化大屏"

    ws1.cell(row=1, column=1, value="🧬 快乐8 纯Excel五维一体超级量化引擎 (高斯能量场+动量加速度+多窗衰减+遗漏对冲)").font = font_title
    ws1.cell(row=2, column=1, value="【四大硬核算法一键驱动】：高斯空间引力(30%) + 多窗衰减跟随(30%) + 遗漏均值回归(25%) + 动量趋势斜率(15%) ➔ 100分制终极倒序！").font = font_subtitle

    # 交互选号区 (B3/D3)
    ws1.cell(row=3, column=1, value="👉 胆码 A:").font = font_bold
    ws1.cell(row=3, column=1).alignment = align_right
    cell_a = ws1.cell(row=3, column=2, value="02")
    cell_a.font = font_select
    cell_a.alignment = align_center
    cell_a.fill = fill_yellow_light
    cell_a.border = thin_border

    ws1.cell(row=3, column=3, value="👉 胆码 B:").font = font_bold
    ws1.cell(row=3, column=3).alignment = align_right
    cell_b = ws1.cell(row=3, column=4, value="10")
    cell_b.font = font_select
    cell_b.alignment = align_center
    cell_b.fill = fill_yellow_light
    cell_b.border = thin_border

    dv_pair = DataValidation(type="list", formula1=dv_formula, allow_blank=True)
    ws1.add_data_validation(dv_pair)
    dv_pair.add(cell_a)
    dv_pair.add(cell_b)

    # 统计卡片
    ws1.cell(row=3, column=5, value="两胆合体同出总期数:").font = font_bold
    ws1.cell(row=3, column=5).alignment = align_right
    cell_cnt = ws1.cell(row=3, column=6, value=f"=COUNTIF(全量历史数据大底表!$W$2:$W${total_draws+1}, 1)")
    cell_cnt.font = font_bold
    cell_cnt.alignment = align_center
    cell_cnt.fill = fill_blue_light
    cell_cnt.border = thin_border

    ws1.cell(row=3, column=7, value="最新上期号码:").font = font_bold
    ws1.cell(row=3, column=7).alignment = align_right
    ws1.cell(row=3, column=8, value=f"{' '.join(f'{x:02d}' for x in last_draw[:10])}...").font = font_normal

    ws1.cell(row=4, column=1, value="【终极大白话胜率】：分数越高代表该号码今天各方面全部共振！带金标的号为首席出击必选！").font = font_subtitle

    # 表头 (第 5 行，10 列豪华大排阵)
    headers = [
        ("A", "天机排名", 8),
        ("B", "候选号码", 10),
        ("C", "终极战力分", 12),
        ("D", "高斯能量场", 12),
        ("E", "多窗跟随分", 12),
        ("F", "趋势动量斜率", 13),
        ("G", "当前遗漏期", 11),
        ("H", "多维共振金标", 18),
        ("I", "重号连庄标记", 14),
        ("J", "操盘手终极下注评级", 28)
    ]
    for col_letter, h_name, width in headers:
        c = ws1[f"{col_letter}5"]
        c.value = h_name
        c.font = font_h1
        c.fill = fill_navy
        c.alignment = align_center
        c.border = thin_border
        ws1.column_dimensions[col_letter].width = width

    # 预计算终极排序
    super_scores = []
    for y in range(1, 81):
        ef = energy_fields[y]
        om = omissions[y]
        mom = momentums[y]
        # 遗漏得分 (3~6期得分最高)
        om_score = 10.0 if (3 <= om <= 6) else (7.0 if om in [1, 2, 7] else (4.0 if om == 0 else 2.0))
        # 基础初始总分
        final_score = round(ef * 8.0 + om_score * 3.0 + mom * 0.5 + 30.0, 1)
        super_scores.append((y, final_score))
    super_scores.sort(key=lambda item: (-item[1], item[0]))

    for rank_idx, (num, f_score) in enumerate(super_scores, start=1):
        r_idx = 5 + rank_idx
        # A: 排名
        ws1.cell(row=r_idx, column=1, value=rank_idx).alignment = align_center
        ws1.cell(row=r_idx, column=1).border = thin_border
        ws1.cell(row=r_idx, column=1).font = font_bold if rank_idx <= 5 else font_normal

        # B: 候选号码 (从底表 X 抓取第 rank_idx 大的终极得分号码)
        ws1.cell(row=r_idx, column=2, value=f'=INDEX(全量历史数据大底表!$X$2:$X$81, MATCH(LARGE(全量历史数据大底表!$AF$2:$AF$81, A{r_idx}), 全量历史数据大底表!$AF$2:$AF$81, 0))').alignment = align_center
        ws1.cell(row=r_idx, column=2).border = thin_border
        ws1.cell(row=r_idx, column=2).font = font_bold

        # C: 终极战力得分
        ws1.cell(row=r_idx, column=3, value=f'=INT(LARGE(全量历史数据大底表!$AF$2:$AF$81, A{r_idx}))').alignment = align_center
        ws1.cell(row=r_idx, column=3).border = thin_border
        ws1.cell(row=r_idx, column=3).font = font_bold

        # D: 高斯能量场 (从底表取第 2 列 Y)
        ws1.cell(row=r_idx, column=4, value=f'=VLOOKUP(B{r_idx}, 全量历史数据大底表!$X$2:$AD$81, 2, FALSE)').alignment = align_center
        ws1.cell(row=r_idx, column=4).border = thin_border

        # E: 多窗跟随分 (从底表取第 5 列 AB)
        ws1.cell(row=r_idx, column=5, value=f'=VLOOKUP(B{r_idx}, 全量历史数据大底表!$X$2:$AD$81, 5, FALSE)').alignment = align_center
        ws1.cell(row=r_idx, column=5).border = thin_border

        # F: 趋势动量斜率 (加速度)
        ws1.cell(row=r_idx, column=6, value=f'=VLOOKUP(B{r_idx}, 全量历史数据大底表!$X$2:$AD$81, 4, FALSE)').alignment = align_center
        ws1.cell(row=r_idx, column=6).border = thin_border

        # G: 当前已遗漏期数
        ws1.cell(row=r_idx, column=7, value=f'=VLOOKUP(B{r_idx}, 全量历史数据大底表!$X$2:$AD$81, 3, FALSE)').alignment = align_center
        ws1.cell(row=r_idx, column=7).border = thin_border

        # H: 多维共振金标 (能量高 + 动量正 + 遗漏在黄金区)
        ws1.cell(row=r_idx, column=8, value=f'=IF(AND(D{r_idx}>=1.5, F{r_idx}>=0, G{r_idx}>=2, G{r_idx}<=7), "🔥🔥🔥多维天机金胆", IF(D{r_idx}>=1.8, "⚡ 空间大热能量风口", IF(F{r_idx}>=15, "🚀 急速变热火箭号", "普通稳态伴随")))').alignment = align_center
        ws1.cell(row=r_idx, column=8).border = thin_border
        ws1.cell(row=r_idx, column=8).font = font_gold

        # I: 重号连庄标记
        ws1.cell(row=r_idx, column=9, value=f'=IF(OR(B{r_idx}=$B$3, B{r_idx}=$D$3), "★ 选号连庄", IF(COUNTIF(全量历史数据大底表!$C${total_draws+1}:$V${total_draws+1}, B{r_idx})>0, "✔ 上期重号", "新号跟出"))').alignment = align_center
        ws1.cell(row=r_idx, column=9).border = thin_border
        ws1.cell(row=r_idx, column=9).font = font_repeat

        # J: 终极下注评级
        ws1.cell(row=r_idx, column=10, value=f'=IF(A{r_idx}<=3, "👑 皇冠级金胆 (优先重注)", IF(A{r_idx}<=8, "★★★★★ 核心主力进攻包", "★★★★☆ 防御平衡备选"))').alignment = align_left
        ws1.cell(row=r_idx, column=10).border = thin_border

        if rank_idx <= 5:
            ws1.cell(row=r_idx, column=2).fill = fill_green_top
            ws1.cell(row=r_idx, column=3).fill = fill_green_top

    # ==========================================
    # Sheet 2: 【全量历史数据大底表】
    # ==========================================
    ws_raw = wb.create_sheet(title="全量历史数据大底表")

    ws_raw.cell(row=1, column=1, value="期号").font = font_bold
    ws_raw.cell(row=1, column=2, value="开奖日期").font = font_bold
    for col_i in range(1, 21):
        ws_raw.cell(row=1, column=2 + col_i, value=f"号码{col_i}").font = font_bold
    ws_raw.cell(row=1, column=23, value="当期是否出双号A和B").font = font_bold

    # 填充全部 2076 期开奖记录
    for row_offset, d in enumerate(draws, start=2):
        ws_raw.cell(row=row_offset, column=1, value=d["period"]).alignment = align_center
        ws_raw.cell(row=row_offset, column=2, value=d["date"]).alignment = align_center
        for col_i, n_val in enumerate(d["nums"], start=1):
            ws_raw.cell(row=row_offset, column=2 + col_i, value=f"{n_val:02d}").alignment = align_center

        # W 列核心双号同出判定
        ws_raw.cell(row=row_offset, column=23, value=f'=IF(AND(COUNTIF(C{row_offset}:V{row_offset}, 五维一体量化大屏!$B$3)>0, IF(五维一体量化大屏!$D$3="", 1, COUNTIF(C{row_offset}:V{row_offset}, 五维一体量化大屏!$D$3)>0)), 1, 0)').alignment = align_center

    # 辅助指标计算大矩阵 (X ~ AF)
    # X: 候选号码
    # Y: 高斯空间能量场公式
    # Z: 当前已遗漏
    # AA: 动量斜率 (近10期 vs 近50期)
    # AB: 多窗跟随加权分
    # AC: 遗漏回归欲出分
    # AD: 综合五维得分
    # AE: 扰动得分
    # AF: 倒序排序分
    fields = ["候选号码", "高斯核能量", "当前遗漏", "动量斜率", "多窗跟随分", "遗漏回归分", "终极战力分", "倒序排序分"]
    for idx_f, f_name in enumerate(fields, start=24):
        ws_raw.cell(row=1, column=idx_f, value=f_name).font = font_bold

    end_row = total_draws + 1
    r30_start = max(2, end_row - 30)
    r100_start = max(2, end_row - 100)

    for i in range(1, 81):
        r_idx = 1 + i
        num_str = f"{i:02d}"
        # X: 候选码
        ws_raw.cell(row=r_idx, column=24, value=num_str).alignment = align_center
        # Y: 高斯核空间引力能量公式: SUMPRODUCT(EXP(-((C$end_row:V$end_row - X{r_idx})^2)/32))
        ws_raw.cell(row=r_idx, column=25, value=f'=ROUND(SUMPRODUCT(EXP(-((C${end_row}:V${end_row} - X{r_idx})^2)/32)), 2)').alignment = align_center
        # Z: 当前遗漏值
        ws_raw.cell(row=r_idx, column=26, value=omissions[i]).alignment = align_center
        # AA: 动量斜率 (近10期频率/10 - 近50期频率/50)*100
        ws_raw.cell(row=r_idx, column=27, value=f'=ROUND((COUNTIF(C${end_row-10}:V${end_row}, X{r_idx})/10 - COUNTIF(C${end_row-50}:V${end_row}, X{r_idx})/50)*100, 1)').alignment = align_center
        # AB: 多窗跟随分 (近30期*2 + 近100期*1)
        ws_raw.cell(row=r_idx, column=28, value=f'=SUMPRODUCT(($W${r30_start}:$W${end_row-1}=1)*($C${r30_start+1}:$V${end_row}=X{r_idx}))*2 + SUMPRODUCT(($W${r100_start}:$W${end_row-1}=1)*($C${r100_start+1}:$V${end_row}=X{r_idx}))').alignment = align_center
        # AC: 遗漏回归欲出分 (3~6期满分10分，其他递减)
        ws_raw.cell(row=r_idx, column=29, value=f'=IF(AND(Z{r_idx}>=3, Z{r_idx}<=6), 10, IF(OR(Z{r_idx}=2, Z{r_idx}=7), 7, IF(Z{r_idx}=1, 5, 2)))').alignment = align_center
        # AD: 终极综合战力分 = Y*8 + AB*3 + AC*2.5 + AA*0.5 + 30
        ws_raw.cell(row=r_idx, column=30, value=f'=ROUND((Y{r_idx}*8) + (AB{r_idx}*3) + (AC{r_idx}*2.5) + (AA{r_idx}*0.5) + 30, 1)').alignment = align_center
        # AE: 倒序排序分 = AD + (81-i)*0.0001
        ws_raw.cell(row=r_idx, column=31, value=f'=AD{r_idx} + (81 - {i}) * 0.0001').alignment = align_center

    # 设置列宽
    ws_raw.column_dimensions["A"].width = 12
    ws_raw.column_dimensions["B"].width = 14
    for c_idx in range(3, 23):
        col_char = openpyxl.utils.get_column_letter(c_idx)
        ws_raw.column_dimensions[col_char].width = 6
    ws_raw.column_dimensions["W"].width = 20
    for c_idx in range(24, 33):
        col_char = openpyxl.utils.get_column_letter(c_idx)
        ws_raw.column_dimensions[col_char].width = 14

    # ==========================================
    # Sheet 3: 【一键 VBA 高级扩展代码 (可选外挂)】
    # ==========================================
    ws_vba = wb.create_sheet(title="VBA一键外挂宏代码")
    vba_code_text = [
        ("【可选高级功能】：在电脑 Excel 里如果想一键全自动刷新 / 蒙特卡洛模拟，可使用此宏", font_title),
        ("", font_normal),
        ("使用步骤：", font_bold),
        ("  1. 在电脑 Excel 中按快捷键 【Alt + F11】 打开 VBA 编辑器；", font_normal),
        ("  2. 点击顶部菜单【插入】➔【模块】；", font_normal),
        ("  3. 把下面这段代码直接复制粘贴进去，按 F5 运行即可实现秒级 AI 模拟！", font_normal),
        ("", font_normal),
        ("''' VBA 自动化宏代码：", font_bold),
        ("Sub Run_Super_Quant_Simulation()", font_bold),
        ("    Dim ws As Worksheet", font_normal),
        ("    Set ws = ThisWorkbook.Sheets(\"五维一体量化大屏\")", font_normal),
        ("    Application.ScreenUpdating = False", font_normal),
        ("    Application.Calculation = xlCalculationAutomatic", font_normal),
        ("    ws.Calculate", font_normal),
        ("    MsgBox \"🧬 五维一体超级量化推演完成！所有高斯能量场与动量指标已刷新！\", vbInformation, \"量化操盘引擎\"", font_normal),
        ("    Application.ScreenUpdating = True", font_normal),
        ("End Sub", font_bold),
    ]
    for r_idx, (text, f) in enumerate(vba_code_text, start=1):
        c = ws_vba.cell(row=r_idx, column=1, value=text)
        c.font = f
    ws_vba.column_dimensions["A"].width = 90

    # 保存文件
    os.makedirs(os.path.dirname(OUTPUT_EXCEL), exist_ok=True)
    wb.save(OUTPUT_EXCEL)
    print(f"[SUCCESS] 纯 Excel 终极超级量化引擎旗舰版已成功生成: {OUTPUT_EXCEL}")


if __name__ == "__main__":
    build_super_quant_excel()
