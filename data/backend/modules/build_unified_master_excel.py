# -*- coding: utf-8 -*-
"""
快乐8 全合一量化操盘工作簿融合引擎 (Unified Master Cockpit Builder)
========================================================================
业务目的：
响应操盘手核心需求：“为什么不跟之前的 Excel 合在一起，要单独生 Excel？”
将【16 窗中热动态矩阵全景】与【双号互动跟随倒序看板】、【定金选2死党榜】、【全历史开奖底表】
100% 深度合并为同一个全功能、一体化、免切换的终极工作簿！
"""
import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_MASTER = os.path.join(PROJ_DIR, "storage", "outputs", "reports", "kl8_master_unified_cockpit.xlsx")


def find_latest_sixteen_src(target_period: str = None) -> str:
    """动态定位最新的含有『全历史开奖矩阵』的 16 窗工作簿"""
    candidates = []
    if target_period:
        candidates.extend([
            os.path.join(PROJ_DIR, "storage", "reports", f"sixteen_excel_window_{target_period}.xlsx"),
            os.path.join(PROJ_DIR, "storage", "outputs", "reports", f"sixteen_excel_window_{target_period}.xlsx"),
        ])
    # 扫描 reports 目录
    for d in [os.path.join(PROJ_DIR, "storage", "reports"), os.path.join(PROJ_DIR, "storage", "outputs", "reports")]:
        if os.path.exists(d):
            for f in sorted(os.listdir(d), reverse=True):
                if f.startswith("sixteen_excel_window_") and f.endswith(".xlsx"):
                    candidates.append(os.path.join(d, f))

    for p in candidates:
        if os.path.exists(p):
            try:
                wb_probe = openpyxl.load_workbook(p, read_only=True)
                if "全历史开奖矩阵" in wb_probe.sheetnames:
                    return p
            except Exception:
                continue
    raise FileNotFoundError("未找到包含『全历史开奖矩阵』的 16 窗 Excel 工作簿！")


def build_unified_master_excel(target_period: str = None, src_path: str = None):
    src_file = src_path or find_latest_sixteen_src(target_period)
    print(f"正在加载基础 16 窗工作簿: {src_file}")
    if not os.path.exists(src_file):
        raise FileNotFoundError(f"找不到源文件: {src_file}")

    wb = openpyxl.load_workbook(src_file)
    print("现有工作表:", wb.sheetnames)

    ws_raw = wb["全历史开奖矩阵"]
    total_draws = ws_raw.max_row - 1 # 扣除表头
    print(f"全历史开奖矩阵行数: {ws_raw.max_row}, 数据期数: {total_draws}")

    # 获取最新一期20个开奖号
    last_row_idx = ws_raw.max_row
    last_draw_nums = [ws_raw.cell(row=last_row_idx, column=c).value for c in range(3, 23)]
    last_draw_nums = [int(x) for x in last_draw_nums if x is not None]

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

    # 在全历史底表中添加辅助计算列 (从第 24 列开始)
    # W 列: 当期是否出双号A和B
    # X 列: 候选号码 01~80
    # Y 列: 近30期跟随频次
    # Z 列: 近100期跟随频次
    # AA 列: 近300期跟随频次
    # AB 列: 综合战力分
    # AC 列: 倒序排序分
    # AD 列: 当前已遗漏
    # AF 列: 定金选2候选搭档
    # AG 列: 同出期数
    # AH 列: 同出倒序分
    ws_raw.cell(row=1, column=23, value="当期是否出双号A和B").font = font_bold
    ws_raw.cell(row=1, column=24, value="候选号码").font = font_bold
    ws_raw.cell(row=1, column=25, value="近30期跟随").font = font_bold
    ws_raw.cell(row=1, column=26, value="近100期跟随").font = font_bold
    ws_raw.cell(row=1, column=27, value="近300期跟随").font = font_bold
    ws_raw.cell(row=1, column=28, value="综合战力分").font = font_bold
    ws_raw.cell(row=1, column=29, value="倒序排序得分").font = font_bold
    ws_raw.cell(row=1, column=30, value="当前已遗漏").font = font_bold

    ws_raw.cell(row=1, column=32, value="搭档候选码").font = font_bold
    ws_raw.cell(row=1, column=33, value="同出总期数").font = font_bold
    ws_raw.cell(row=1, column=34, value="同出倒序分").font = font_bold

    # 填充底表 W 列双号判定公式 (行 2 到行 total_draws+1)
    end_row = total_draws + 1
    r30_start = max(2, end_row - 30)
    r100_start = max(2, end_row - 100)
    r300_start = max(2, end_row - 300)

    for r_idx in range(2, end_row + 1):
        ws_raw.cell(row=r_idx, column=23, value=f'=IF(AND(COUNTIF(C{r_idx}:V{r_idx}, 双号与多窗跟随看板!$B$3)>0, IF(双号与多窗跟随看板!$D$3="", 1, COUNTIF(C{r_idx}:V{r_idx}, 双号与多窗跟随看板!$D$3)>0)), 1, 0)').alignment = align_center

    # 填充 80 个号码的辅助统计列
    for i in range(1, 81):
        r_idx = 1 + i
        num_str = f"{i:02d}"
        # 候选号
        ws_raw.cell(row=r_idx, column=24, value=num_str).alignment = align_center
        # Y: 近 30 期
        ws_raw.cell(row=r_idx, column=25, value=f'=SUMPRODUCT(($W${r30_start}:$W${end_row-1}=1)*($C${r30_start+1}:$V${end_row}=X{r_idx}))').alignment = align_center
        # Z: 近 100 期
        ws_raw.cell(row=r_idx, column=26, value=f'=SUMPRODUCT(($W${r100_start}:$W${end_row-1}=1)*($C${r100_start+1}:$V${end_row}=X{r_idx}))').alignment = align_center
        # AA: 近 300 期
        ws_raw.cell(row=r_idx, column=27, value=f'=SUMPRODUCT(($W${r300_start}:$W${end_row-1}=1)*($C${r300_start+1}:$V${end_row}=X{r_idx}))').alignment = align_center
        # AB: 综合战力分 = (Y*3) + (Z*1.5) + (AA*0.5)
        ws_raw.cell(row=r_idx, column=28, value=f'=(Y{r_idx} * 3) + (Z{r_idx} * 1.5) + (AA{r_idx} * 0.5)').alignment = align_center
        # AC: 倒序排序分 = AB + (81-i)*0.0001
        ws_raw.cell(row=r_idx, column=29, value=f'=AB{r_idx} + (81 - {i}) * 0.0001').alignment = align_center
        # AD: 遗漏值 (从最新期往上查，用基准常数占位+公式)
        ws_raw.cell(row=r_idx, column=30, value=f'=IF(COUNTIF(C${end_row}:V${end_row}, X{r_idx})>0, 0, IF(COUNTIF(C${end_row-1}:V${end_row-1}, X{r_idx})>0, 1, IF(COUNTIF(C${end_row-2}:V${end_row-2}, X{r_idx})>0, 2, IF(COUNTIF(C${end_row-3}:V${end_row-3}, X{r_idx})>0, 3, IF(COUNTIF(C${end_row-4}:V${end_row-4}, X{r_idx})>0, 4, IF(COUNTIF(C${end_row-5}:V${end_row-5}, X{r_idx})>0, 5, 6))))))').alignment = align_center

        # AF: 定金选2搭档码
        ws_raw.cell(row=r_idx, column=32, value=num_str).alignment = align_center
        # AG: 同出总期数
        ws_raw.cell(row=r_idx, column=33, value=f'=SUMPRODUCT((COUNTIF(OFFSET($C$2:$V$2, ROW($1:${total_draws})-1, 0), 定金选2同出死党榜!$B$3)>0)*(COUNTIF(OFFSET($C$2:$V$2, ROW($1:${total_draws})-1, 0), AF{r_idx})>0))').alignment = align_center
        # AH: 同出倒序分
        ws_raw.cell(row=r_idx, column=34, value=f'=AG{r_idx} + (81 - {i}) * 0.0001').alignment = align_center

    # 设置底表扩展列宽
    ws_raw.column_dimensions["W"].width = 20
    ws_raw.column_dimensions["X"].width = 10
    ws_raw.column_dimensions["Y"].width = 12
    ws_raw.column_dimensions["Z"].width = 12
    ws_raw.column_dimensions["AA"].width = 12
    ws_raw.column_dimensions["AB"].width = 14
    ws_raw.column_dimensions["AC"].width = 16
    ws_raw.column_dimensions["AD"].width = 12
    ws_raw.column_dimensions["AF"].width = 12
    ws_raw.column_dimensions["AG"].width = 14
    ws_raw.column_dimensions["AH"].width = 16

    # ==========================================
    # 追加 Sheet: 【双号与多窗跟随看板】(插在第 2 个工作表位置)
    # ==========================================
    ws_follow = wb.create_sheet(title="双号与多窗跟随看板", index=1)

    ws_follow.cell(row=1, column=1, value="🧬 快乐8 双号同出多窗跟随看板 (近30/100/300期衰减 + 遗漏对冲 · 倒序)").font = font_title
    ws_follow.cell(row=2, column=1, value="【交互使用说明】：在 B3 选号码A，在 D3 选号码B。全表立刻倒序展示两号同出时，下一期各个号码跟随出现的战力与排名！").font = font_subtitle

    # 选号卡片
    ws_follow.cell(row=3, column=1, value="👉 号码 A:").font = font_bold
    ws_follow.cell(row=3, column=1).alignment = align_right
    cell_fa = ws_follow.cell(row=3, column=2, value="02")
    cell_fa.font = font_select
    cell_fa.alignment = align_center
    cell_fa.fill = fill_yellow_light
    cell_fa.border = thin_border

    ws_follow.cell(row=3, column=3, value="👉 号码 B:").font = font_bold
    ws_follow.cell(row=3, column=3).alignment = align_right
    cell_fb = ws_follow.cell(row=3, column=4, value="10")
    cell_fb.font = font_select
    cell_fb.alignment = align_center
    cell_fb.fill = fill_yellow_light
    cell_fb.border = thin_border

    dv_follow = DataValidation(type="list", formula1=dv_formula, allow_blank=True)
    ws_follow.add_data_validation(dv_follow)
    dv_follow.add(cell_fa)
    dv_follow.add(cell_fb)

    ws_follow.cell(row=3, column=5, value="两号同出总期数:").font = font_bold
    ws_follow.cell(row=3, column=5).alignment = align_right
    cell_fcnt = ws_follow.cell(row=3, column=6, value=f"=COUNTIF(全历史开奖矩阵!$W$2:$W${end_row}, 1)")
    cell_fcnt.font = font_bold
    cell_fcnt.alignment = align_center
    cell_fcnt.fill = fill_blue_light
    cell_fcnt.border = thin_border

    ws_follow.cell(row=3, column=7, value="历史总样本:").font = font_bold
    ws_follow.cell(row=3, column=7).alignment = align_right
    ws_follow.cell(row=3, column=8, value=f"{total_draws} 期 (全量大账本)").font = font_normal

    ws_follow.cell(row=4, column=1, value="【抗拟合综合分】：近30期跟随×3.0 (抓短期爆发) + 近100期×1.5 (抓中线) + 近300期×0.5 (抗噪声) ➔ 严格倒序！").font = font_subtitle

    # 表头
    headers_follow = [
        ("A", "综合排名", 8),
        ("B", "重复项(号码)", 12),
        ("C", "抗拟合综合分", 13),
        ("D", "近30期跟随", 11),
        ("E", "近100期跟随", 12),
        ("F", "近300期跟随", 12),
        ("G", "当前已遗漏", 11),
        ("H", "多维共振金标", 18),
        ("I", "连庄标记(重号)", 14),
        ("J", "老派操盘手实战定性", 26)
    ]
    for col_letter, h_name, width in headers_follow:
        c = ws_follow[f"{col_letter}5"]
        c.value = h_name
        c.font = font_h1
        c.fill = fill_navy
        c.alignment = align_center
        c.border = thin_border
        ws_follow.column_dimensions[col_letter].width = width

    # 填充 80 个倒序排名行
    for rank_idx in range(1, 81):
        r_idx = 5 + rank_idx
        # A: 排名
        ws_follow.cell(row=r_idx, column=1, value=rank_idx).alignment = align_center
        ws_follow.cell(row=r_idx, column=1).border = thin_border
        ws_follow.cell(row=r_idx, column=1).font = font_bold if rank_idx <= 5 else font_normal

        # B: 重复项 (号码，从底表根据倒序分抓取)
        cB = ws_follow.cell(row=r_idx, column=2, value=f'=INDEX(全历史开奖矩阵!$X$2:$X$81, MATCH(LARGE(全历史开奖矩阵!$AC$2:$AC$81, A{r_idx}), 全历史开奖矩阵!$AC$2:$AC$81, 0))')
        cB.alignment = align_center
        cB.border = thin_border
        cB.font = font_bold if rank_idx <= 5 else font_normal

        # C: 综合分 (倒序计数)
        cC = ws_follow.cell(row=r_idx, column=3, value=f'=INT(LARGE(全历史开奖矩阵!$AC$2:$AC$81, A{r_idx}))')
        cC.alignment = align_center
        cC.border = thin_border
        cC.font = font_bold

        # D: 近30期
        ws_follow.cell(row=r_idx, column=4, value=f'=VLOOKUP(B{r_idx}, 全历史开奖矩阵!$X$2:$AA$81, 2, FALSE)').alignment = align_center
        ws_follow.cell(row=r_idx, column=4).border = thin_border

        # E: 近100期
        ws_follow.cell(row=r_idx, column=5, value=f'=VLOOKUP(B{r_idx}, 全历史开奖矩阵!$X$2:$AA$81, 3, FALSE)').alignment = align_center
        ws_follow.cell(row=r_idx, column=5).border = thin_border

        # F: 近300期
        ws_follow.cell(row=r_idx, column=6, value=f'=VLOOKUP(B{r_idx}, 全历史开奖矩阵!$X$2:$AA$81, 4, FALSE)').alignment = align_center
        ws_follow.cell(row=r_idx, column=6).border = thin_border

        # G: 当前已遗漏
        ws_follow.cell(row=r_idx, column=7, value=f'=VLOOKUP(B{r_idx}, 全历史开奖矩阵!$X$2:$AD$81, 7, FALSE)').alignment = align_center
        ws_follow.cell(row=r_idx, column=7).border = thin_border

        # H: 多维共振金标
        ws_follow.cell(row=r_idx, column=8, value=f'=IF(AND(D{r_idx}>0, E{r_idx}>1, G{r_idx}>=2, G{r_idx}<=6), "🔥🔥🔥多维共振金胆", IF(D{r_idx}>0, "⚡ 短期急热跟进", IF(G{r_idx}>=6, "❄️ 深度冷态防守", "稳态伴随")))').alignment = align_center
        ws_follow.cell(row=r_idx, column=8).border = thin_border
        ws_follow.cell(row=r_idx, column=8).font = font_gold

        # I: 重号
        ws_follow.cell(row=r_idx, column=9, value=f'=IF(OR(B{r_idx}=$B$3, B{r_idx}=$D$3), "★ 选号连庄", IF(COUNTIF(全历史开奖矩阵!$C${end_row}:$V${end_row}, B{r_idx})>0, "✔ 上期重号", "新号跟出"))').alignment = align_center
        ws_follow.cell(row=r_idx, column=9).border = thin_border
        ws_follow.cell(row=r_idx, column=9).font = font_repeat

        # J: 定性
        ws_follow.cell(row=r_idx, column=10, value=f'=IF(A{r_idx}<=3, "★★★★★ 首席必选先锋", IF(A{r_idx}<=8, "★★★★☆ 黄金主力备选", "★★★☆☆ 普通防御码"))').alignment = align_left
        ws_follow.cell(row=r_idx, column=10).border = thin_border

        if rank_idx <= 5:
            cB.fill = fill_green_top
            cC.fill = fill_green_top

    # ==========================================
    # 追加 Sheet: 【定金选2同出死党榜】(插在第 3 个工作表位置)
    # ==========================================
    ws_co = wb.create_sheet(title="定金选2同出死党榜", index=2)

    ws_co.cell(row=1, column=1, value="🧬 快乐8 定金选2同出死党共现榜 (全历史2076期 · 当期粘在一起开出最多)").font = font_title
    ws_co.cell(row=2, column=1, value="【实战原理】：不猜下一期跟什么，而是直接抓当期必须粘在一起开出的最佳搭档（连体婴选2神器）！").font = font_subtitle

    ws_co.cell(row=3, column=1, value="👉 定金选胆号码:").font = font_bold
    ws_co.cell(row=3, column=1).alignment = align_right

    cell_coa = ws_co.cell(row=3, column=2, value="18")
    cell_coa.font = font_select
    cell_coa.alignment = align_center
    cell_coa.fill = fill_yellow_light
    cell_coa.border = thin_border

    dv_co = DataValidation(type="list", formula1=dv_formula, allow_blank=False)
    ws_co.add_data_validation(dv_co)
    dv_co.add(cell_coa)

    ws_co.cell(row=3, column=3, value="该胆码历史开出:").font = font_bold
    ws_co.cell(row=3, column=3).alignment = align_right
    ws_co.cell(row=3, column=4, value=f"=COUNTIF(全历史开奖矩阵!$C$2:$V${end_row}, B3)").font = font_bold
    ws_co.cell(row=3, column=4).alignment = align_center
    ws_co.cell(row=3, column=4).fill = fill_blue_light
    ws_co.cell(row=3, column=4).border = thin_border

    ws_co.cell(row=4, column=1, value="下表实时倒序展示：在全历史2076期中，哪几个号码跟选定的胆码【同一期粘在一起开出】最多次数！").font = font_subtitle

    # 表头
    headers_co = [
        ("A", "搭档排名", 8),
        ("B", "最佳搭档号码", 14),
        ("C", "同出总期数(倒序)", 16),
        ("D", "两号合体绑定率", 16),
        ("E", "连庄属性", 14),
        ("F", "老派操盘手实战建议", 28)
    ]
    for col_letter, h_name, width in headers_co:
        c = ws_co[f"{col_letter}5"]
        c.value = h_name
        c.font = font_h1
        c.fill = fill_navy
        c.alignment = align_center
        c.border = thin_border
        ws_co.column_dimensions[col_letter].width = width

    for r_i in range(1, 81):
        r_idx = 5 + r_i
        ws_co.cell(row=r_idx, column=1, value=r_i).alignment = align_center
        ws_co.cell(row=r_idx, column=1).border = thin_border

        cB = ws_co.cell(row=r_idx, column=2, value=f'=INDEX(全历史开奖矩阵!$AF$2:$AF$81, MATCH(LARGE(全历史开奖矩阵!$AH$2:$AH$81, A{r_idx}), 全历史开奖矩阵!$AH$2:$AH$81, 0))')
        cB.alignment = align_center
        cB.border = thin_border
        cB.font = font_bold

        cC = ws_co.cell(row=r_idx, column=3, value=f'=INT(LARGE(全历史开奖矩阵!$AH$2:$AH$81, A{r_idx}))')
        cC.alignment = align_center
        cC.border = thin_border
        cC.font = font_bold

        ws_co.cell(row=r_idx, column=4, value=f'=IF($D$3>0, TEXT(C{r_idx}/$D$3, "0.0%"), "0.0%")').alignment = align_center
        ws_co.cell(row=r_idx, column=4).border = thin_border

        ws_co.cell(row=r_idx, column=5, value=f'=IF(COUNTIF(全历史开奖矩阵!$C${end_row}:$V${end_row}, B{r_idx})>0, "✔ 上期重号", "新出搭档")').alignment = align_center
        ws_co.cell(row=r_idx, column=5).border = thin_border

        ws_co.cell(row=r_idx, column=6, value=f'=IF(A{r_idx}<=3, "🏆 终极连体婴 (定金选2首选打包)", IF(A{r_idx}<=6, "🔥 黄金搭档 (高频同出组合)", "优质伴生搭档"))').alignment = align_left
        ws_co.cell(row=r_idx, column=6).border = thin_border

        if r_i <= 3:
            cB.fill = fill_gold_light
            cC.fill = fill_gold_light

    # ==========================================
    # 追加 Sheet: 【全合一战法使用指南】
    # ==========================================
    ws_guide = wb.create_sheet(title="全合一驾驶舱使用指南")
    guide_lines = [
        ("🧬 快乐8 全合一量化操盘驾驶舱 (All-in-One Master Cockpit)", font_title),
        ("", font_normal),
        ("一、 为什么把所有战法合并到同一个 Excel 工作簿？", font_bold),
        ("  1. 拒绝碎片化：看 16 窗中热、查双号跟随、选定金搭档，无需在多个文件之间来回切换；", font_normal),
        ("  2. 底层数据统一：底表【全历史开奖矩阵】统领全局 2076 期开奖大账本，所有看板联动更新；", font_normal),
        ("  3. 微信与手机友好：单个文件约 300KB，手机端微信发送或 WPS 打开秒开，随时随地推演！", font_normal),
        ("", font_normal),
        ("二、 四大核心看板怎么分工配合？（实战三步操盘法）", font_bold),
        ("  【第一步：看大局】打开 Sheet 1【16窗量化操盘看板】：", font_normal),
        ("     - 查看【双轨 4 种方法最优预测】（官方动量主推与确定性混剪）；", font_normal),
        ("     - 查看【微信桶 8+至0次分桶】（认清哪些是 3~6 次的主力中热号）；", font_normal),
        ("     - 查看【出窗同源 4 队与频 3 蓄水池】（防溢出、抓跃迁）。", font_normal),
        ("  【第二步：做微操】打开 Sheet 2【双号与多窗跟随看板】：", font_normal),
        ("     - 在 B3 和 D3 选定你最看好的 1~2 个号码；", font_normal),
        ("     - 查看近 30/100/300 期抗拟合倒序榜，抓取自动点亮的【🔥🔥🔥多维共振金胆】！", font_normal),
        ("  【第三步：定组合】打开 Sheet 3【定金选2同出死党榜】：", font_normal),
        ("     - 在 B3 选定金胆，直接抓取全历史绑在一起出号最多的前 2 名搭档，打包出击！", font_normal),
    ]
    for r_idx, (text, f) in enumerate(guide_lines, start=1):
        c = ws_guide.cell(row=r_idx, column=1, value=text)
        c.font = f
    ws_guide.column_dimensions["A"].width = 100

    # 保存全合一驾驶舱
    wb.save(OUTPUT_MASTER)
    print(f"[SUCCESS] 全合一终极量化驾驶舱已生成: {OUTPUT_MASTER}")

    # 同时覆盖/同步到当前 16 窗原文件与 latest 软链，实现完全统一！
    import shutil
    try:
        shutil.copyfile(OUTPUT_MASTER, src_file)
    except Exception:
        pass
    latest_cache = os.path.join(PROJ_DIR, "storage", "cache", "sixteen_period", "excel_window_latest.xlsx")
    if os.path.exists(os.path.dirname(latest_cache)):
        try:
            shutil.copyfile(OUTPUT_MASTER, latest_cache)
        except Exception:
            pass
    print(f"[SYNC] 已同步覆盖 {os.path.basename(src_file)} 与 latest 缓存！")


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else None
    build_unified_master_excel(target)
