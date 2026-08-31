#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
16期中热号频次动态推演与组合决策 每日量化研判执行器
=============================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 玩法：快乐8 16期滑动窗口大盘冷热光谱分析与出窗进窗动态动量推演。
2. 频次分桶 (1~8+次)：
   - 1次、2次 (冷号/温冷)
   - 3次、4次、5次、6次 (中热黄金号池，主力出号区间)
   - 7次、8+次 (超热极值号，过载透支防追高)
3. 出窗与进窗动态推演：
   - 16期前开出的号（出窗号）：若下期不开则频次减 1；若开出则频次保持。
   - 16期前未开出的号：若下期开出则频次加 1；若不开则频次保持。
4. 中热号智能组合决策：
   - 输出中热首席金银铜胆、Top 5 选2黄金组合、选3精推与 5 码防线。
5. 样本外无未来函数复盘：
   - 滚动近 N 期对账命中率与 Lift 提升倍数。

用法：
  python run_sixteen_daily.py [N_REVIEW=30]
"""
import os
import sys
import json
import argparse
from datetime import datetime

# 路径自适应 (Dual-Root Bootstrap)
_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ_DIR = _PROJ_DIR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.core.sixteen_period.sixteen_engine import (
    SixteenPeriodEngine,
    run_single_period_analysis,
    load_draws_from_file,
    WINDOW_SIZE,
    BASE_SINGLE,
    BASE_PAIR
)
from backend.core.sixteen_period.sixteen_reviewer import SixteenPeriodReviewer

# 颜色与排版
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"
C_GRAY = "\033[90m"

LINE = "═" * 76
THIN = "─" * 76


def banner(txt: str, color: str = C_CYAN):
    print(f"\n{color}{LINE}")
    print(f"  {txt}")
    print(f"{LINE}{C_RESET}")


def run_sixteen_pipeline(n_review: int = 30, verbose: bool = True) -> dict:
    """
    16期中热频次推演主执行流水线
    """
    draws = load_draws_from_file()
    if not draws:
        raise RuntimeError("无法读取历史开奖数据 kl8_history_final.txt")

    m = len(draws)
    latest_draw = draws[-1]
    target_period = latest_draw["period"] + 1

    if verbose:
        banner("🔥 16期中热号频次动态推演与组合决策引擎 (K8-Quant Modular Edition)")
        print(f"  📁 历史开奖: {m} 期 | 最新开奖: {latest_draw['period']} 期 ({latest_draw['date']}) | 🎯 目标研判: {target_period} 期")
        print(f"  🎲 核心原理: 16期滑动大盘光谱 (1~8+次) + 动态出窗进窗推演 + 中热号组合 (3~6次)")

    # 1. 运行最新一期分析推演
    engine = SixteenPeriodEngine(draws)
    analysis_res = engine.analyze_at_index(m - 1)

    # 2. 导出今日研报
    report_md = engine.generate_report(analysis_res)
    for sub in ["reports", os.path.join("outputs", "reports")]:
        dpath = os.path.join(PROJ_DIR, sub)
        os.makedirs(dpath, exist_ok=True)
        fname = f"sixteen_analysis_report_{target_period}.md"
        with open(os.path.join(dpath, fname), "w", encoding="utf-8") as f:
            f.write(report_md)

    # 保存缓存
    cache_dir = os.path.join(PROJ_DIR, "cache", "sixteen_period")
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "latest_summary.json"), "w", encoding="utf-8") as f:
        json.dump(analysis_res, f, ensure_ascii=False, indent=2)

    # 3. 运行 Walk-Forward 滚动样本外复盘
    reviewer = SixteenPeriodReviewer(draws)
    review_res = reviewer.run_walk_forward_review(n_periods=n_review)

    with open(os.path.join(cache_dir, "latest_review.json"), "w", encoding="utf-8") as f:
        json.dump(review_res, f, ensure_ascii=False, indent=2)

    if verbose:
        gold = analysis_res["gold_dan"]
        silver = analysis_res["silver_dan"]
        bronze = analysis_res["bronze_dan"]
        top5 = analysis_res["medium_top5"]
        top5_str = " ".join(f"{x:02d}" for x in top5)
        top5_pairs = analysis_res["top5_pairs"]
        dist = analysis_res["distribution_counts"]
        med_cnt = analysis_res["medium_hot_total_count"]
        out_p = analysis_res["outgoing_period"]

        print(f"\n{C_YELLOW}┌─── [1] 16期大盘冷热光谱分布 (对齐 1~8+ 频次分桶) ───────────{C_RESET}")
        print(f"│  1次: {dist.get('1',0):2d}码 | 2次: {dist.get('2',0):2d}码 | 3次: {dist.get('3',0):2d}码 | 4次: {dist.get('4',0):2d}码")
        print(f"│  5次: {dist.get('5',0):2d}码 | 6次: {dist.get('6',0):2d}码 | 7次: {dist.get('7',0):2d}码 | 8+次: {dist.get('8+',0):2d}码")
        print(f"│  ★ 中热黄金候选池 (3~6次): 共 {med_cnt} 码 (大盘主力产出区间)")
        print(f"{C_YELLOW}└{THIN}{C_RESET}")

        print(f"\n{C_CYAN}┌─── [2] 今日中热定胆与核心防线 ─────────────────────────{C_RESET}")
        print(f"│  👑 首席中热金胆: {C_BOLD}{C_YELLOW}{gold:02d}{C_RESET}")
        print(f"│  🥈 次席中热银胆: {silver:02d} | 🥉 三席铜胆: {bronze:02d}")
        print(f"│  🛡️ 中热精选 5 码防线: {C_GREEN}{top5_str}{C_RESET}")
        print(f"│  📋 出窗参考期: 第 {out_p} 期 (16期前开奖，该期号码若明日不开则减1次)")
        print(f"{C_CYAN}└{THIN}{C_RESET}")

        print(f"\n{C_MAGENTA}┌─── [3] Top 5 选2 黄金组合 (以中热金银胆为核) ────────────────{C_RESET}")
        for idx, p in enumerate(top5_pairs, 1):
            flag = "★ 金胆核" if p["has_gold"] else ("☆ 银胆核" if p["has_silver"] else "✔ 中热共振")
            print(f"│  Top {idx}: [{p['pair_str']}] | 评分: {p['score']} | 16期共现: {p['co_count']}次 | {flag}")
        print(f"{C_MAGENTA}└{THIN}{C_RESET}")

        stats = review_res["stats"]
        print(f"\n{C_GREEN}┌─── [4] 近 {stats['n_periods']} 期 Walk-Forward 滚动样本外对账指标 ────────────{C_RESET}")
        print(f"│  核心金胆命中率: {C_YELLOW}{stats['gold_hit_rate']}%{C_RESET} (Lift: {stats['gold_lift']}x vs 基线 25.0%)")
        print(f"│  次席银胆命中率: {stats['silver_hit_rate']}% (Lift: {stats['silver_lift']}x)")
        print(f"│  中热 5 码均期命中: {C_GREEN}{stats['top5_avg_hits']} 码/期{C_RESET} (Lift: {stats['top5_lift']}x vs 基线 1.25)")
        print(f"│  Top 1 组合中2率: {C_CYAN}{stats['top1_both_rate']}%{C_RESET} (Lift: {stats['top1_both_lift']}x vs 基线 6.01%)")
        print(f"│  Top 1 至少中1率: {stats['top1_one_rate']}% (基线 43.99%)")
        print(f"│  中热号池平均单码命中: {stats['med_pool_hit_rate']}%")
        print(f"{C_GREEN}└{THIN}{C_RESET}")

        print(f"\n  ✅ 研报已成功持久化至 reports/sixteen_analysis_report_{target_period}.md")

    return {
        "analysis": analysis_res,
        "review": review_res
    }


def main():
    parser = argparse.ArgumentParser(description="16期中热频次动态推演与组合决策每日量化研判")
    parser.add_argument("n_review", nargs="?", type=int, default=30, help="滚动复盘期数 (默认30)")
    parser.add_argument("--quiet", action="store_true", help="静默模式")
    args = parser.parse_args()

    run_sixteen_pipeline(n_review=args.n_review, verbose=not args.quiet)


if __name__ == "__main__":
    main()
