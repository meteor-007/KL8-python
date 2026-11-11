"""
四图走势分路精确引擎每日运行与回测执行器

@author Antigravity Quantitative Trading Team
@since 2026-10-13
"""

import argparse
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from backend.modules.four_charts_route.engine import FourChartsRouteEngine


def main():
    parser = argparse.ArgumentParser(description="四图走势与012路分路精确推演引擎")
    parser.add_argument("--target_period", type=int, default=None, help="目标推演期号 (例如 2026272)")
    parser.add_argument("--backtest", type=int, default=30, help="执行回测期数 (默认 30 期)")
    parser.add_argument("--audit_last", action="store_true", help="是否对账上一期")
    args = parser.parse_args()

    engine = FourChartsRouteEngine()
    latest_draw_period = max(engine.all_periods)

    if args.target_period is None:
        target_p = latest_draw_period + 1
    else:
        target_p = args.target_period

    base_p = target_p - 1
    print(f"======================================================================")
    print(f"📊 快乐8 四图走势与012路分路精确推演引擎 (Four Charts Route Engine)")
    print(f"======================================================================")
    print(f"基准开奖期号: 第 {base_p} 期 ｜ 目标推演期号: 第 {target_p} 期")

    # 1. 执行目标期推演
    result = engine.analyze_period(base_p)
    print("\n【一、012路走势动力学诊断 (图1)】")
    print(f"• 上期出号比例: {result['road_dynamics']['last_ratio']}")
    print(f"• 偏离度 Z-Score: {result['road_dynamics']['z_scores']}")
    print(f"• 均值回归研判: 0路({result['road_dynamics']['expected_direction']['0']}), 1路({result['road_dynamics']['expected_direction']['1']}), 2路({result['road_dynamics']['expected_direction']['2']})")

    print("\n【二、分路精确战队推荐】")
    for r_name, r_codes in result["route_teams"].items():
        print(f"• {r_name}: {r_codes}")

    print("\n【三、全盘核心战队】")
    print(f"• 尖刀最优 3 码: {result['key_recommendations']['尖刀最优3码']}")
    print(f"• 黄金 8 码战队: {result['key_recommendations']['黄金8码战队']}")
    print(f"• 连庄 3 胆防守: {result['key_recommendations']['连庄3胆防守']}")
    print(f"• 黄金选2搭档:   {result['key_recommendations']['黄金选2搭档']}")

    # 2. 如果开启了 audit_last，对账基准期
    if args.audit_last or base_p <= latest_draw_period:
        print(f"\n======================================================================")
        print(f"🔍 正在执行第 {base_p} 期实盘对账与总账本更新...")
        audit = engine.record_and_audit(base_p)
        if audit.get("status") != "pending":
            print(f"• 实际开出号码: {audit['actual_draw']}")
            print(f"• 0路精锐命中: {audit['hit_r0']} ({audit['counts']['r0_hit_count']}/5)")
            print(f"• 1路精锐命中: {audit['hit_r1']} ({audit['counts']['r1_hit_count']}/5)")
            print(f"• 2路精锐命中: {audit['hit_r2']} ({audit['counts']['r2_hit_count']}/5)")
            print(f"• 尖刀最优3码命中: {audit['hit_top3']} ({audit['counts']['top3_hit_count']}/3)")
            print(f"• 黄金8码命中: {audit['hit_top8']} ({audit['counts']['top8_hit_count']}/8)")
            print(f"• 选2搭档命中: {audit['hit_pick2']}/2")

    # 3. 如果需要回测
    if args.backtest > 0:
        print(f"\n======================================================================")
        print(f"📈 正在启动近 {args.backtest} 期样本外严格滚动回测 (Walk-Forward Backtest)...")
        summary = engine.run_backtest(n_periods=args.backtest)
        print(f"• 回测期数: {summary['start_period']} ~ {summary['end_period']} (共 {summary['backtest_periods']} 期)")
        print(f"• 尖刀最优3码 平均每期命中: {summary['top3_avg_hit']} 码 (单码命中率: {summary['top3_hit_rate']*100:.1f}%)")
        print(f"• 黄金8码战队 平均每期命中: {summary['top8_avg_hit']} 码 (单码命中率: {summary['top8_hit_rate']*100:.1f}%)")
        print(f"• 选2搭档 双全中率: {summary['pick2_double_hit_rate']*100:.1f}% ｜ 至少中一率: {summary['pick2_single_hit_rate']*100:.1f}%")
        print(f"• 结果已持久化: storage/outputs/four_charts/backtest_summary.json")

    print(f"======================================================================\n")


if __name__ == "__main__":
    main()
