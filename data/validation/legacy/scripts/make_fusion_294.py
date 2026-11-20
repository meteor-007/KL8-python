# -*- coding: utf-8 -*-
"""
Updater to create scripts/fusion_engine_294.py from scripts/fusion_engine_293.py
with period 2026294 parameters and data sources.
"""
import sys

with open("scripts/fusion_engine_293.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update module docstring & author date
code = code.replace("快乐8 第 2026293 期", "快乐8 第 2026294 期")
code = code.replace("@since 2026-11-03", "@since 2026-11-04")

# 2. Update Period Constants
old_consts = """TOTAL_BALL_COUNT: int = 80
TARGET_PERIOD: int = 2026293
PREVIOUS_PERIOD: int = 2026292
PREVIOUS_DRAW_DATE: str = "2026-11-02"
TARGET_PREDICT_DATE: str = "2026-11-03"

PREV_DRAW_NUMBERS: Tuple[int, ...] = (
    2, 5, 10, 17, 22, 25, 26, 36, 43, 45, 50, 51, 52, 57, 62, 64, 68, 70, 71, 75
)"""

new_consts = """TOTAL_BALL_COUNT: int = 80
TARGET_PERIOD: int = 2026294
PREVIOUS_PERIOD: int = 2026293
PREVIOUS_DRAW_DATE: str = "2026-11-03"
TARGET_PREDICT_DATE: str = "2026-11-04"

PREV_DRAW_NUMBERS: Tuple[int, ...] = (
    19, 23, 25, 34, 39, 42, 43, 44, 45, 48, 53, 54, 56, 57, 62, 73, 74, 75, 77, 78
)"""

code = code.replace(old_consts, new_consts)

# 3. Update walk-forward backtest range from 283~292 to 284~293
code = code.replace(
    "periods_list = list(range(2026292 - window + 1, 2026293))",
    "periods_list = list(range(2026293 - window + 1, 2026294))"
)

# 4. In extract_excel_data, update file paths and sheet reading for 294
old_extract_start = """    path_dw = os.path.join(file_dir, "快八293期点位图.xls")
    path_zd = os.path.join(file_dir, "快八293期找胆图.xls")"""

new_extract_start = """    path_dw_294 = os.path.join(file_dir, "2026294(1).xls")
    path_dw = path_dw_294 if os.path.exists(path_dw_294) else os.path.join(file_dir, "快八293期点位图.xls")
    path_fx_294 = os.path.join(file_dir, "2026294.xls")
    path_zd = os.path.join(file_dir, "快八293期找胆图.xls")"""

code = code.replace(old_extract_start, new_extract_start)

# Update point map reading for 294: rows 8826 to 8845
old_dw_read = """    points_293: List[int] = []
    for r in range(8796, 8816):
        val = sh_dw.cell_value(r, 10)
        points_293.append(int(float(val)))

    dw_repeat_high: List[int] = []
    for c in range(11, sh_dw.ncols):
        v = sh_dw.cell_value(8817, c)
        if v != "":
            dw_repeat_high.append(int(float(v)))

    dw_edge_high: List[int] = []
    for c in range(11, sh_dw.ncols):
        v = sh_dw.cell_value(8818, c)
        if v != "":
            dw_edge_high.append(int(float(v)))

    dw_cold_high: List[int] = []
    for c in range(11, sh_dw.ncols):
        v = sh_dw.cell_value(8819, c)
        if v != "":
            dw_cold_high.append(int(float(v)))"""

new_dw_read = """    points_293: List[int] = []
    dw_row_start = 8826 if os.path.exists(os.path.join(file_dir, "2026294(1).xls")) else 8796
    for r in range(dw_row_start, dw_row_start + 20):
        val = sh_dw.cell_value(r, 10)
        try:
            points_293.append(int(float(val)))
        except (ValueError, TypeError):
            pass

    dw_repeat_high: List[int] = []
    rep_row = dw_row_start + 21
    for c in range(11, sh_dw.ncols):
        v = sh_dw.cell_value(rep_row, c)
        if v != "":
            try:
                dw_repeat_high.append(int(float(v)))
            except (ValueError, TypeError):
                pass

    dw_edge_high: List[int] = []
    edg_row = dw_row_start + 22
    for c in range(11, sh_dw.ncols):
        v = sh_dw.cell_value(edg_row, c)
        if v != "":
            try:
                dw_edge_high.append(int(float(v)))
            except (ValueError, TypeError):
                pass

    dw_cold_high: List[int] = []
    cld_row = dw_row_start + 23
    for c in range(11, sh_dw.ncols):
        v = sh_dw.cell_value(cld_row, c)
        if v != "":
            try:
                dw_cold_high.append(int(float(v)))
            except (ValueError, TypeError):
                pass"""

code = code.replace(old_dw_read, new_dw_read)

# Save to scripts/fusion_engine_294.py
with open("scripts/fusion_engine_294.py", "w", encoding="utf-8") as f:
    f.write(code)

print("scripts/fusion_engine_294.py updated successfully!")
