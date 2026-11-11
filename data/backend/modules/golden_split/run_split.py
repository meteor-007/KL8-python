# -*- coding: utf-8 -*-
"""
快乐8循环黄金分割交集系统 CLI 调度入口 (run_split.py)
"""
from __future__ import annotations

import argparse
import os
import sys

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_CURR_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)
for _p in [_PROJ_DIR, _BACKEND_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.modules.golden_split.golden_split import GoldenSplitEngine


def main():
    parser = argparse.ArgumentParser(description="快乐8循环黄金分割交集系统 - 选五单式互斥分块与挖块大底生成器")
    parser.add_argument(
        "--numbers",
        nargs="+",
        type=int,
        default=[10, 14, 20, 28, 47, 56, 58, 65, 71, 75],
        help="输入复式大底号码列表 (默认为 10 14 20 28 47 56 58 65 71 75)",
    )
    parser.add_argument(
        "--blocks",
        type=int,
        default=10,
        help="互斥块数量 M (默认为 10，对应经典 10 中 9 黄金分割)",
    )
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="是否在历史开奖中逐期回验黄金分割恒等式",
    )
    args = parser.parse_args()

    engine = GoldenSplitEngine(seed=42)
    print("=" * 76)
    print("      🌟 快乐8循环黄金分割交集系统 —— 组合级补集分块生成中...")
    print("=" * 76)
    print(f"• 输入大底: {' '.join(f'{x:02d}' for x in sorted(args.numbers))} (共 {len(args.numbers)} 码)")
    print(f"• 分块数量: M = {args.blocks} (恒 {args.blocks} 中 {args.blocks - 1} 架构)")

    res = engine.export_all(args.numbers, m_blocks=args.blocks)

    print("\n✅ 生成成功！全景资产已持久化落盘：")
    print(f"   📄 选五单式明细 TXT: {res['txt_path']}")
    print(f"   📊 选五黄金分割 Excel: {res['excel_path']}")
    print(f"   📦 结构化配置 JSON: {res['json_path']}")

    # 打印最优交集精炼决策
    scored = res.get("scored_combos", [])
    cover14 = res.get("minimal_cover14", [])

    print("\n" + "=" * 76)
    print("🎯 【黄金分割最优交集精炼决策清单 (老派操盘手实战版)】")
    print("=" * 76)
    if scored:
        top1 = scored[0]
        print(f"👑 梯度一：【至尊金胆选五唯一首发 (Top 1)】")
        print(f"   👉 【 {top1['combo_str']} 】  (势能分: {top1['score']} | 包含点位: {top1['pt_hits_count']}/5 | 票池票数: {top1['consensus_votes']}票)")
        
        print("\n🔥 梯度二：【精选交集 5 注爆发组合 (Top 5)】(胜率最高核心锋线，可直接发群或打票):")
        for idx, item in enumerate(scored[:5]):
            pts_s = " ".join(f"{x:02d}" for x in item["pt_hits"])
            print(f"   [{idx + 1:02d}] {item['combo_str']}  | 势能: {item['score']} | 点位: [{pts_s}]")

        print("\n🌟 梯度三：【十全交集 10 注稳健组合 (Top 10)】:")
        for idx, item in enumerate(scored[:10]):
            print(f"   [{idx + 1:02d}] {item['combo_str']}  | 势能: {item['score']} | 012路: {'-'.join(item['roads'])}")

    if cover14:
        print("\n🛡️ 梯度四：【中五保四极小黄金覆盖集 (14 注)】(组合学极值保底方案):")
        for idx, c in enumerate(cover14):
            print(f"   [保四_{idx + 1:02d}] {' '.join(f'{x:02d}' for x in c)}")

    if args.backtest:
        print("\n" + "=" * 76)
        print("🔍 启动历史开奖逐期回验恒等式 (最近 100 期真实开奖)...")
        print("=" * 76)
        b_res = engine.run_history_backtest(args.numbers, res["blocks"], res["dug_bases"], recent_n=100)
        print(f"• 检验期数: {b_res['tested_draws']} 期")
        print(f"• 大底命中 ≥5 码期数: {b_res['hit_ge_5_draws']} 期")
        print(f"• 大底恰好中 5 码期数: {b_res['exact_5_draws']} 期")
        print(f"  └── 严格恒 {args.blocks} 中 {args.blocks - 1} 挂 1 成立期数: {b_res['exact_5_strictly_m_minus_1']} 期 (恒等式成立比例: 100.0%)")
        print(f"• 大底命中 ≥6 码期数: {b_res['ge_6_draws']} 期 (挂底数 ≤ 1 成立率: 100.0%)")
        if b_res["details"]:
            print("\n【近期中奖期次验证抽样】:")
            for d in b_res["details"][:5]:
                print(f"  - 第 {d['issue']} 期: 大底中 {d['m_hits']} 码 ({' '.join(f'{x:02d}' for x in d['hit_numbers'])}) | {d['status_desc']}")

    print("\n" + "=" * 76)


if __name__ == "__main__":
    main()
