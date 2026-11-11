# -*- coding: utf-8 -*-
"""变分神经主动推理独立发车与滚动对账脚本 (Run Daily & Backtest Script)。

【使用方式】:
  1. 预测最新一期:
     python -m backend.modules.active_inference.run_daily
  2. 滚动历史盲测对账 (回测近 30 期):
     python -m backend.modules.active_inference.run_daily --backtest 30

@author Antigravity Quant Team
@since 2026-09-20
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List

# 确保项目路径正确注入
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.dirname(_CURRENT_DIR)
_BACKEND_DIR = os.path.dirname(_MODULES_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)

if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from utils.paths import data_path, get_cache_dir
from modules.kl8_lab.data_io import load_draws, Draw
from modules.active_inference.engine import ActiveInferenceEngine, ActiveInferencePredictionResult

# 配置实战日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ActiveInference.RunDaily")


def run_single_prediction() -> ActiveInferencePredictionResult:
    """对最新开奖下一期进行变分推断出号。"""
    history_file = data_path("kl8_history_final.txt")
    if not os.path.exists(history_file):
        raise FileNotFoundError(f"未找到开奖历史主文件: {history_file}")

    # load_draws 返回的是降序（最新在前），时序分析需要转为升序（最老在前）
    draws_desc: List[Draw] = load_draws(history_file)
    if not draws_desc:
        raise ValueError("历史开奖记录为空！")

    draws_asc = list(reversed(draws_desc))
    latest_draw = draws_asc[-1]
    target_period = str(latest_draw.period + 1)

    print("\n" + "=" * 60)
    print(f">> [变分神经主动推理系统] 正在为第 {target_period} 期推演盘口...")
    print(f"[*] 基础数据：最新历史为第 {latest_draw.period} 期 ({latest_draw.date})，开奖球：{' '.join(f'{b:02d}' for b in latest_draw.numbers)}")
    print("=" * 60 + "\n")

    # 提取纯开奖号码列表
    draws_numbers_asc = [list(d.numbers) for d in draws_asc]

    # 初始化引擎
    cache_dir = os.path.join(get_cache_dir(), "active_inference")
    engine = ActiveInferenceEngine(cache_dir=cache_dir)

    result = engine.run_prediction(all_draws_asc=draws_numbers_asc, target_issue=target_period)

    print("\n" + "*" * 60)
    print("【变分神经主动推理实战操盘总账单】")
    print("*" * 60)
    print(result.summary_report)
    print("*" * 60 + "\n")

    return result


def run_rolling_backtest(backtest_rounds: int = 30) -> None:
    """运行样本外无未来信息滚动回测（Backtest Out-of-Sample）。"""
    history_file = data_path("kl8_history_final.txt")
    draws_desc: List[Draw] = load_draws(history_file)
    draws_asc = list(reversed(draws_desc))

    total_len = len(draws_asc)
    if total_len < backtest_rounds + 50:
        raise ValueError(f"开奖历史样本太少 ({total_len})，无法支撑 {backtest_rounds} 期样本外回测！")

    print("\n" + "=" * 70)
    print(f"[*] [样本外极限回测] 变分主动推理引擎正在复盘对账近 {backtest_rounds} 期...")
    print("=" * 70)

    engine = ActiveInferenceEngine()
    test_start_idx = total_len - backtest_rounds

    keystone_hits_list = []
    top5_hits_list = []
    top12_hits_list = []
    pair_both_hits = 0
    pair_any_hits = 0
    total_pairs_tested = 0

    for idx in range(test_start_idx, total_len):
        train_draws = [list(d.numbers) for d in draws_asc[:idx]]
        actual_draw = draws_asc[idx]
        actual_set = set(actual_draw.numbers)
        target_issue = str(actual_draw.period)

        # 变分推断下一期
        pred = engine.run_prediction(all_draws_asc=train_draws, target_issue=target_issue)

        # 对账统计
        k3_hits = len(set(pred.golden_keystones_3) & actual_set)
        t5_hits = len(set(pred.predicted_top5) & actual_set)
        t12_hits = len(set(pred.predicted_top12) & actual_set)

        keystone_hits_list.append(k3_hits)
        top5_hits_list.append(t5_hits)
        top12_hits_list.append(t12_hits)

        # 对账选2双飞搭档
        for p1, p2, _ in pred.best_pair_bonds[:1]:
            total_pairs_tested += 1
            h = (1 if p1 in actual_set else 0) + (1 if p2 in actual_set else 0)
            if h == 2:
                pair_both_hits += 1
            if h >= 1:
                pair_any_hits += 1

        print(
            f"期号 {target_issue} | "
            f"Keystone 3 码: {k3_hits}/3 | "
            f"Top 5: {t5_hits}/5 | "
            f"Top 12: {t12_hits}/12 | "
            f"首选搭档 ({pred.best_pair_bonds[0][0]:02d},{pred.best_pair_bonds[0][1]:02d}) 命中: {len({pred.best_pair_bonds[0][0], pred.best_pair_bonds[0][1]} & actual_set)}/2"
        )

    # 决算统计指标
    avg_k3 = sum(keystone_hits_list) / len(keystone_hits_list)
    k3_single_rate = avg_k3 / 3.0
    lift = k3_single_rate / 0.25  # 相对 25% 随机基线的提升倍数

    avg_t5 = sum(top5_hits_list) / len(top5_hits_list)
    avg_t12 = sum(top12_hits_list) / len(top12_hits_list)
    pair_both_rate = (pair_both_hits / total_pairs_tested * 100.0) if total_pairs_tested > 0 else 0.0

    print("\n" + "=" * 70)
    print("【变分主动推理系统 - 样本外实战决算总战报】")
    print("=" * 70)
    print(f"[测试期数]: {backtest_rounds} 期")
    print(f"[Keystone 枢纽 3 码平均命中]: {avg_k3:.2f} 码 (单码命中率: {k3_single_rate * 100:.1f}%)")
    print(f"[统计提升度 (Lift)]: {lift:.2f}x (基线: 1.00x，>=1.25x 为超强信标)")
    print(f"[变分 Top 5 平均命中]: {avg_t5:.2f} 码 (期望基准: 1.25 码)")
    print(f"[变分 Top 12 平均命中]: {avg_t12:.2f} 码 (期望基准: 3.00 码)")
    print(f"[黄金选2搭档双全中率]: {pair_both_rate:.1f}% (全中基准: ~6.0%)")
    print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="变分神经主动推理独立运行与对账脚本")
    parser.add_argument("--backtest", type=int, default=0, help="运行近 N 期样本外盲测回测")
    args = parser.parse_args()

    if args.backtest > 0:
        run_rolling_backtest(backtest_rounds=args.backtest)
    else:
        run_single_prediction()


if __name__ == "__main__":
    main()
