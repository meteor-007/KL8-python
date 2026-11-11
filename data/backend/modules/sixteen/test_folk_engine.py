# -*- coding: utf-8 -*-
import os
import sys

from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine
from backend.modules.sixteen.folk_excel_builder import FolkExcelBuilder

def main():
    engine = FolkSixteenEngine()
    builder = FolkExcelBuilder()

    # 1. 预测最新期 2026263 期
    res263 = engine.analyze_window(target_period=2026263)
    print("=== 2026263 预测结果 ===")
    print("大底20码:", res263['picks']['grand_20'])
    print("精选12码:", res263['picks']['elite_12'])
    print("黄金5胆:", res263['picks']['golden_5'])
    print("最优3胆:", res263['picks']['golden_3'])
    print("选2搭档:", res263['picks']['top_pairs'])

    # 保存文本分桶
    txt_path, latest_txt = engine.save_plain_text_summary(res263)
    print("生成微信分桶文本:", txt_path)

    # 保存 Excel
    xlsx_path = builder.export_excel(res263)
    print("生成 Excel 报表:", xlsx_path)

    # 2. 回测复盘 2026262 期
    res262 = engine.analyze_window(target_period=2026262)
    print("\n=== 2026262 回测复盘 ===")
    audit262 = res262['hit_audit']
    print("实际开出20码:", audit262["actual_draw"])
    print(f"大底20码命中数: {audit262['grand_20_hit_count']}/20, 命中号码: {audit262['grand_20_hits']}")
    print(f"精选12码命中数: {audit262['elite_12_hit_count']}/12, 命中号码: {audit262['elite_12_hits']}")
    print(f"黄金5胆命中数: {audit262['golden_5_hit_count']}/5, 命中号码: {audit262['golden_5_hits']}")
    print(f"最优3胆命中数: {audit262['golden_3_hit_count']}/3, 命中号码: {audit262['golden_3_hits']}")

    xlsx262 = builder.export_excel(res262, 'storage/outputs/reports/test_folk_review_2026262.xlsx')
    print("生成 2026262 复盘 Excel:", xlsx262)

if __name__ == "__main__":
    main()
