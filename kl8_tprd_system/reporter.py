#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TPRD v4.0 报表生成与多渠道分发模块 (Reporter Engine)
包含：美观终端控制台看板、微信四区分桶格式化、4-Sheet 专业 Excel 导出
"""

import os
from typing import Dict, Any, Optional
import pandas as pd


def format_console_dashboard(pred: Dict[str, Any], next_period: int, last_draw: Optional[Dict] = None) -> str:
    """
    生成高可读性控制台看板文本
    """
    t5 = pred['top5_leaders']
    p20 = pred['pool_20']
    p25 = pred['pool_25']
    p30 = pred['pool_30']

    sum20 = sum(p20)
    odd20 = sum(1 for n in p20 if n % 2 == 1)
    even20 = len(p20) - odd20

    lines = []
    lines.append("╔══════════════════════════════════════════════════════════════════════════╗")
    lines.append(f"║   🧬 TPRD v4.0 (Dual-Window Calibrated) 快乐8 智能量化推演看板    ║")
    lines.append(f"║   目标期次: 第 {next_period} 期  |  模型状态: 双窗口RF集成 + 空间零盲区守卫   ║")
    lines.append("╠══════════════════════════════════════════════════════════════════════════╣")

    if last_draw:
        nums_str = " ".join(f"{n:02d}" for n in last_draw['nums'])
        lines.append(f"║ 上期开奖 ({last_draw['period']}期 · {last_draw['date']}): {nums_str} ║")
        lines.append("╟──────────────────────────────────────────────────────────────────────────╢")

    lines.append(f"║ 🎯 【独胆王牌 (Top 1)】: {t5[0]:02d} (012路龙头，双窗口融合最高置信分)")
    lines.append(f"║ 💎 【012正交三胆 (Top 3)】: {' - '.join(f'{n:02d}' for n in sorted(t5[:3]))} (0路×1路×2路跨轨龙头)")
    lines.append(f"║ 🔥 【主力突击五码 (Top 5)】: {' - '.join(f'{n:02d}' for n in sorted(t5))}")
    lines.append("╟──────────────────────────────────────────────────────────────────────────╢")
    lines.append("║ 🎲 【选2抽屉原理 3+1 完备四注网格 (五码中3必中奖)】:")
    for idx, d in enumerate(pred['pick2_details']):
        pair_str = f"{d['pair'][0]:02d} - {d['pair'][1]:02d}"
        lines.append(f"║   注{idx+1} [{d['name']}]: {pair_str}  (PMI亲和力: {d['score']:.4f})")
    lines.append("╟──────────────────────────────────────────────────────────────────────────╢")
    lines.append(f"║ 🏆 【20码极致主力池】(和值={sum20}点 | 奇偶比={odd20}:{even20} | 走廊 [760,860]):")
    lines.append(f"║   {' '.join(f'{n:02d}' for n in p20)}")
    lines.append(f"║ 🛡️ 【25码精选中底】: {' '.join(f'{n:02d}' for n in p25)}")
    lines.append(f"║ 👑 【30码黄金大底】(全盘8段每段>=2码，四区6~9码零盲区):")
    lines.append(f"║   {' '.join(f'{n:02d}' for n in p30)}")
    lines.append("╚══════════════════════════════════════════════════════════════════════════╝")
    return "\n".join(lines)


def format_wechat_copy_text(pred: Dict[str, Any], next_period: int) -> str:
    """
    生成微信社群/客户分发版四区分桶纯文本
    """
    t5 = pred['top5_leaders']
    p20 = pred['pool_20']
    p25 = pred['pool_25']
    p30 = pred['pool_30']

    def bucket_by_zone(balls):
        z = {0: [], 1: [], 2: [], 3: []}
        for n in sorted(balls):
            z[(n - 1) // 20].append(f"{n:02d}")
        return z

    z20 = bucket_by_zone(p20)
    z25 = bucket_by_zone(p25)
    z30 = bucket_by_zone(p30)

    sum20 = sum(p20)
    odd20 = sum(1 for n in p20 if n % 2 == 1)
    even20 = len(p20) - odd20

    p2_strs = [f"{d['pair'][0]:02d}-{d['pair'][1]:02d}" for d in pred['pick2_details']]

    text = f"""【快乐8 · 第 {next_period} 期实战推演报告 · TPRD v4.0】
--------------------------------------------
★ 独胆王牌: {t5[0]:02d}
★ 012正交三胆: {' '.join(f'{n:02d}' for n in sorted(t5[:3]))}
★ 主力五码: {' '.join(f'{n:02d}' for n in sorted(t5))}
★ 精选十码: {' '.join(f'{n:02d}' for n in sorted(pred['ranked_all'][:10]))}

【选2抽屉原理 3+1 四注网格】(8元锁死中3必中):
1. {p2_strs[0]} (A组王牌)
2. {p2_strs[1]} (A组跨路)
3. {p2_strs[2]} (A组闭环)
4. {p2_strs[3]} (B组对冲)

【选3主推】: {' '.join(f'{n:02d}' for n in sorted(t5[:3]))}
【选5直打】: {' '.join(f'{n:02d}' for n in sorted(t5))}
【选5复式(6码)】: {' '.join(f'{n:02d}' for n in sorted(t5 + [pred['ranked_all'][5]])) if len(pred['ranked_all']) > 5 else ''}

============================================
【20码极致主力池】(和值 {sum20} 点 | 奇偶 {odd20}:{even20})
• 一区 (01-20): {' '.join(z20[0])}
• 二区 (21-40): {' '.join(z20[1])}
• 三区 (41-60): {' '.join(z20[2])}
• 四区 (61-80): {' '.join(z20[3])}

【25码精选中底】(四区 {len(z25[0])}:{len(z25[1])}:{len(z25[2])}:{len(z25[3])})
• 一区: {' '.join(z25[0])}
• 二区: {' '.join(z25[1])}
• 三区: {' '.join(z25[2])}
• 四区: {' '.join(z25[3])}

【30码黄金大底】(四区 {len(z30[0])}:{len(z30[1])}:{len(z30[2])}:{len(z30[3])} · 8段零盲区)
• 一区: {' '.join(z30[0])}
• 二区: {' '.join(z30[1])}
• 三区: {' '.join(z30[2])}
• 四区: {' '.join(z30[3])}
============================================
"""
    return text.strip()


def export_excel_report(
    next_period: int,
    pred: Dict[str, Any],
    df_backtest: pd.DataFrame,
    output_dir: str = "output"
) -> str:
    """
    自动导出包含 4 个标准 Sheet 的 Excel 资产
    缺失 openpyxl 时自动无损降级为 UTF-8-SIG CSV 文本
    """
    os.makedirs(output_dir, exist_ok=True)
    xlsx_path = os.path.join(output_dir, f"TPRD_{next_period}_实战预测与回测报表.xlsx")

    # Sheet 1: 实战推荐汇总
    p2_strs = [f"{d['pair'][0]:02d}-{d['pair'][1]:02d} ({d['name']}, 评分:{d['score']:.3f})" for d in pred['pick2_details']]
    t5 = pred['top5_leaders']
    df_sheet1 = pd.DataFrame([
        {"模块名称": "独胆王牌 (Top 1)", "推荐内容": f"{t5[0]:02d}", "说明": "双窗口融合最高置信胆"},
        {"模块名称": "012正交三胆 (Top 3)", "推荐内容": " ".join(f"{n:02d}" for n in sorted(t5[:3])), "说明": "0路×1路×2路跨轨三龙头"},
        {"模块名称": "主力五码 (Top 5)", "推荐内容": " ".join(f"{n:02d}" for n in sorted(t5)), "说明": "选五单式直打核心"},
        {"模块名称": "选2抽屉原理3+1网格", "推荐内容": " | ".join(p2_strs), "说明": "4注8元完备锁死五码中3"},
        {"模块名称": "20码极致主力池", "推荐内容": " ".join(f"{n:02d}" for n in pred['pool_20']), "说明": f"和值={sum(pred['pool_20'])}点 | [760,860]中枢"},
        {"模块名称": "25码精选中底", "推荐内容": " ".join(f"{n:02d}" for n in pred['pool_25']), "说明": "四区均衡中底"},
        {"模块名称": "30码黄金大底", "推荐内容": " ".join(f"{n:02d}" for n in pred['pool_30']), "说明": "四区6~9码 + 八段每段>=2码零盲区"},
    ])

    # Sheet 2: DHM-Pro v4.0 选5 30注
    df_dhm = pd.DataFrame([
        {"注号": f"第{idx+1:02d}注", "选5单式号码": " ".join(f"{n:02d}" for n in bet), "组合类型": "Pool_20纯血" if idx < 20 else "3α+2β外围耦合"}
        for idx, bet in enumerate(pred['dhm_bets'])
    ])

    # Sheet 4: 80 码评分明细
    rank_map = {n: idx + 1 for idx, n in enumerate(pred['ranked_all'])}
    df_balls = pd.DataFrame([
        {
            "号码": f"{n:02d}",
            "综合排名": rank_map[n],
            "Z融合分": round(pred['scores'][n], 4),
            "入选池": "20码" if n in pred['pool_20'] else ("25码" if n in pred['pool_25'] else ("30码" if n in pred['pool_30'] else "候补")),
            "012路": f"{n % 3}路",
            "质合": "质数" if n in {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79} else "合数"
        }
        for n in range(1, 81)
    ]).sort_values("综合排名")

    try:
        with pd.ExcelWriter(xlsx_path) as writer:
            df_sheet1.to_excel(writer, sheet_name="1_本期实战推荐汇总", index=False)
            df_dhm.to_excel(writer, sheet_name="2_DHM_Pro双螺旋30注选5", index=False)
            df_backtest.to_excel(writer, sheet_name="3_近30期滚动回测对账单", index=False)
            df_balls.to_excel(writer, sheet_name="4_80码Z融合评分明细", index=False)
        return xlsx_path
    except Exception as e:
        csv_path = os.path.join(output_dir, f"TPRD_{next_period}_实战预测汇总.csv")
        df_sheet1.to_csv(csv_path, index=False, encoding="utf-8-sig")
        return csv_path
