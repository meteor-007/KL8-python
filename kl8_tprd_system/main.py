#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TPRD v4.0 (Dual-Window Calibrated & Zero-Blind-Spot Edition) 快乐8 智能缩水与双螺旋矩阵系统
主入口 CLI 工具，支持一键推演、滚动外样本回测、开奖增量同步与高阶矩阵生成
"""

import os
import sys
import argparse
from typing import List

# 确保核心包路径在搜索路径中
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from tprd_core.data_sync import sync_latest_draws, load_history, parse_and_append_draw
from tprd_core.features import build_features
from tprd_core.model_v40 import infer_period_v40
from tprd_core.backtest import run_walk_forward_backtest
from tprd_core.matrices import generate_gf4_hypercube_pick5, generate_bibd_pick6
from reporter import format_console_dashboard, format_wechat_copy_text, export_excel_report


def run_predict(data_path: str, output_dir: str, backtest_periods: int = 30):
    print("=" * 72)
    print(" 正在启动 TPRD v4.0 快乐8 全维量化推演引擎...")
    print("=" * 72)

    sync_latest_draws(data_path)
    draws, B = load_history(data_path)
    N = len(draws)
    last_draw = draws[-1]
    last_period = int(last_draw['period'])
    next_period = last_period + 1

    print(f"[DATA] 全量历史账本加载完成: 总计 {N} 期 (历史: {draws[0]['period']} ~ {last_period})")

    # 1. 15维特征张量构造
    print("[FEAT] 正在计算 15 维物理与带符号偏态特征矩阵 (因果无泄漏)...")
    X, road_counts, prime_counts = build_features(B)

    # 2. 滚动外样本回测
    print(f"[TEST] 正在执行近 {backtest_periods} 期严格 Walk-Forward 滚动外样本回测...")
    df_bt, summary = run_walk_forward_backtest(draws, X, B, road_counts, test_periods=backtest_periods)

    print(f"[RESULT] 近 {summary['test_count']} 期均值 -> "
          f"20码: {summary['mean_20']:.2f} (Lift: {summary['lift_20']:.3f}x) | "
          f"25码: {summary['mean_25']:.2f} (Lift: {summary['lift_25']:.3f}x) | "
          f"30码: {summary['mean_30']:.2f} (Lift: {summary['lift_30']:.3f}x)")
    print(f"[RESULT] 选2抽屉4注网格胜率: {summary['p2_win_rate']*100:.2f}% "
          f"(盈亏平衡线 10.53%, Lift: {summary['p2_lift']:.3f}x)")

    # 3. 推演目标最新期
    print(f"\n[INFER] 正在解算第 {next_period} 期双窗口集成概率与空间零盲区守卫...")
    pred = infer_period_v40(N, X, B, road_counts)

    # 4. 打印终端看板
    print("\n" + format_console_dashboard(pred, next_period, last_draw))

    # 5. 打印微信分桶文本
    print("\n" + "=" * 44)
    print(" 【微信社群/客户分发展开文本 (可直接复制)】")
    print("=" * 44)
    print(format_wechat_copy_text(pred, next_period))

    # 6. 打印 DHM-Pro v4.0 选5纯号码版 (30注)
    print("\n" + "=" * 44)
    print(f" 【DHM-Pro v4.0 三阶同心双螺旋 30注选5 (第 {next_period} 期)】")
    print("=" * 44)
    for idx, bet in enumerate(pred['dhm_bets']):
        print(f"第{idx+1:02d}注: " + " ".join(f"{n:02d}" for n in bet))

    # 7. 导出 Excel
    report_file = export_excel_report(next_period, pred, df_bt, output_dir=output_dir)
    print(f"\n[EXPORT] 完整 4-Sheet 实战报表已落盘 -> {os.path.abspath(report_file)}")
    print("=" * 72)
    return pred


def run_custom_matrix(matrix_type: str, balls_str: str, num_bets: int = 25):
    import re
    balls = sorted([int(x) for x in re.split(r'[-\s,]+', balls_str.strip()) if x])
    print(f"\n[MATRIX] 收到自定义输入号码 ({len(balls)} 码): {' '.join(f'{n:02d}' for n in balls)}")

    if matrix_type.lower() == 'gf4':
        if len(balls) < 20:
            raise ValueError(f"GF(4) 矩阵需要至少 20 个号码，当前只有 {len(balls)} 个")
        bets = generate_gf4_hypercube_pick5(balls, num_bets=num_bets)
        print(f"\n【GF(4) 伽罗瓦域正交拉丁超立方选5矩阵 · {len(bets)}注】")
        for idx, b in enumerate(bets):
            print(f"第{idx+1:02d}注: " + " ".join(f"{n:02d}" for n in b))
    elif matrix_type.lower() == 'bibd':
        if len(balls) < 25:
            raise ValueError(f"BIBD 矩阵需要至少 25 个号码，当前只有 {len(balls)} 个")
        groups = generate_bibd_pick6(balls, num_groups=10)
        print(f"\n【BIBD 25码精编 10组 6码组合矩阵 (选6单式/选5复式)】")
        for idx, g in enumerate(groups):
            print(f"第{idx+1:02d}组: " + " ".join(f"{n:02d}" for n in g))
    else:
        print(f"不支持的矩阵类型: {matrix_type}，请选择 gf4 或 bibd")


def main():
    parser = argparse.ArgumentParser(description="TPRD v4.0 快乐8 智能缩水与双螺旋矩阵系统")
    parser.add_argument("--predict", action="store_true", help="推演最新一期实战方案 (默认行为)")
    parser.add_argument("--backtest", type=int, default=0, help="执行指定期数的 Walk-Forward 回测 (如 --backtest 30)")
    parser.add_argument("--sync", action="store_true", help="校验并补齐历史账本")
    parser.add_argument("--add-draw", nargs=3, metavar=('PERIOD', 'DATE', 'NUMBERS'),
                        help="手动录入新开奖号: --add-draw 2026304 2026-11-14 '01 02 ... 80'")
    parser.add_argument("--matrix", type=str, choices=['gf4', 'bibd'], help="运行独立组合矩阵引擎")
    parser.add_argument("--balls", type=str, help="组合矩阵输入的号码序列 (空格或-隔开)")
    parser.add_argument("--data-file", type=str, default=os.path.join(CURRENT_DIR, "data", "kl8_history_final.txt"))
    parser.add_argument("--output-dir", type=str, default=os.path.join(CURRENT_DIR, "output"))

    args = parser.parse_args()

    if args.add_draw:
        p, d, nums = args.add_draw
        parse_and_append_draw(args.data_file, int(p), d, nums)
        print(f"[SYNC] 第 {p} 期开奖号码已成功录入并同步至账本。")
        return

    if args.sync:
        cnt = sync_latest_draws(args.data_file)
        print(f"[SYNC] 账本校验与同步完成，当前共包含 {cnt} 期数据。")
        return

    if args.matrix:
        if not args.balls:
            print("错误: 运行 --matrix 时必须提供 --balls 参数 (例如 --balls '03 07 12 ...')")
            sys.exit(1)
        run_custom_matrix(args.matrix, args.balls)
        return

    # 默认执行预测与回测流水线
    test_p = args.backtest if args.backtest > 0 else 30
    run_predict(args.data_file, args.output_dir, backtest_periods=test_p)


if __name__ == "__main__":
    main()
