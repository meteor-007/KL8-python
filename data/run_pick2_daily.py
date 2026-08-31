#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定金选2 快乐8 每日全流程一键分析引擎 v5.0 (主系统整合版)
=============================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 玩法：快乐8 "选二定胆配对" = 押 金胆 (单码) + 与它配对的 2 码组合。
2. 双重金胆法：💎 加权Z金胆 (温号池中精选) + 🥇 热号金胆 (近20期最热号码)。
3. 组合配对：以金胆为核，按条件共现强度与金胆得分排序生成 Top 5 组合。
4. 样本外复盘：逐期防未来函数滚动推演，对账金胆命中率与组合中2率。

用法：
  python run_pick2_daily.py [N_REVIEW=30]
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

from core.gold_pick2 import (
    load_draws_from_file,
    calculate_gold_pick2_features,
    walk_forward_evaluate_pick2,
    cross_validate_pick2_picks,
    BASE_SINGLE,
    BASE_PAIR
)

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


def run_pick2_pipeline(n_review: int = 30, verbose: bool = True) -> dict:
    """
    定金选2 每日主执行流水线
    """
    history_file = os.path.join(PROJ_DIR, "kl8_history_final.txt")
    if not os.path.exists(history_file):
        history_file = os.path.join(PROJ_DIR, "storage", "raw", "kl8_history_final.txt")

    draws = load_draws_from_file(history_file)
    if not draws:
        raise RuntimeError(f"无法读取历史开奖数据: {history_file}")

    m = len(draws)
    latest_draw = draws[-1]
    target_period = latest_draw["period"] + 1

    if verbose:
        banner("💎 定金选2 快乐8 每日量化决策推演 (主系统深度整合版 v5.0)")
        print(f"  📁 历史开奖: {m} 期 | 最新开奖: {latest_draw['period']} 期 ({latest_draw['date']}) | 🎯 目标研判: {target_period} 期")
        print(f"  🎲 玩法核心: 选二定胆配对 | 理论基线: 单码 25.0% | 选2组合 6.01%")

    # 1. 目标期核心推演 (严格基于全量历史，无未来数据泄露)
    pred = calculate_gold_pick2_features(draws, cutoff_idx=m)
    golden = pred["golden"]
    hot = pred["hot"]
    top5_golden = pred["top5_golden"]
    top5_hot = pred["top5_hot"]
    warm = pred["warm"]
    gap = pred["gap"]

    # 2. Walk-Forward 滚动样本外复盘对账与置信度计算
    wf_res = walk_forward_evaluate_pick2(draws, n_review=n_review)
    stats = wf_res["stats"]
    conf = stats.get("confidence", {})

    # 3. 主系统多维模型交叉风控
    cross_flags = cross_validate_pick2_picks(PROJ_DIR, golden, hot, top5_golden)

    result_payload = {
        "timestamp": datetime.now().isoformat(),
        "latest_period": latest_draw["period"],
        "latest_date": latest_draw["date"],
        "target_period": target_period,
        "golden": golden,
        "hot": hot,
        "confidence": conf,
        "warm_pool": warm,
        "gap": gap,
        "top5_golden": top5_golden,
        "top5_hot": top5_hot,
        "walk_forward": wf_res,
        "cross_validation": cross_flags,
        "stats": stats
    }

    # 4. 落盘预测资产
    out_dir = os.path.join(PROJ_DIR, "outputs", "gold_pick2")
    os.makedirs(out_dir, exist_ok=True)
    out_txt = os.path.join(out_dir, f"定金选2预测_{target_period}.txt")
    out_latest_txt = os.path.join(out_dir, "定金选2预测_最新.txt")
    out_json = os.path.join(out_dir, "gold_pick2_latest.json")

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("定金选2 每日量化预测 (主系统整合版)\n")
        f.write(f"生成时间: {datetime.now():%Y-%m-%d %H:%M} | 目标期号: {target_period}\n")
        f.write(f"置信等级: {conf.get('description', 'N/A')}\n")
        f.write(f"💎 核心金胆: {golden:02d} (遗漏 {gap[golden]} 期) | 🥇 热号金胆: {hot:02d} (遗漏 {gap[hot]} 期)\n")
        f.write("=" * 60 + "\n")
        f.write("Top 5 黄金配对组合 (以金胆为核):\n")
        for idx, p in enumerate(top5_golden, 1):
            mark = " (与热号重叠)" if p["is_hot_overlap"] else ""
            f.write(f"  Top{idx}: [{p['pair_str']}] 权重: {p['weight']:.4f}{mark}\n")
        f.write("-" * 60 + "\n")
        f.write(f"近 {stats.get('n_periods', 0)} 期复盘: 金胆命中率 {stats.get('golden_hit_rate', 0)}% (Lift={stats.get('golden_lift', 0)}x) | "
                f"Top1组合中2率 {stats.get('top1_both_rate', 0)}% (Lift={stats.get('top1_both_lift', 0)}x)\n")

    # 复制最新一份
    with open(out_latest_txt, "w", encoding="utf-8") as f:
        with open(out_txt, "r", encoding="utf-8") as src:
            f.write(src.read())

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result_payload, f, ensure_ascii=False, indent=2)

    if verbose:
        # 控制台打印
        banner("② 置信评级与样本外显著性 (Walk-Forward OOF)", C_YELLOW)
        print(f"  近 {stats.get('n_periods', 0)} 期金胆命中: {stats.get('golden_hit_count', 0)}/{stats.get('n_periods', 0)} = {stats.get('golden_hit_rate', 0)}% | "
              f"Lift = {stats.get('golden_lift', 0)}x (基线 25.0%) | {conf.get('badge', '')} {conf.get('title', '')}")
        print(f"  热号金胆命中: {stats.get('hot_hit_count', 0)}/{stats.get('n_periods', 0)} = {stats.get('hot_hit_rate', 0)}% | Lift = {stats.get('hot_lift', 0)}x")
        print(f"  Top1 组合中2: {stats.get('top1_both_count', 0)}/{stats.get('n_periods', 0)} = {stats.get('top1_both_rate', 0)}% | "
              f"Lift = {stats.get('top1_both_lift', 0)}x (基线 6.01%) | 至少中1: {stats.get('top1_one_rate', 0)}%")
        print(f"  温号池 (遗漏4-8期) 平均命中率: {stats.get('warm_pool_hit_rate', 0)}%")

        banner(f"③ 今日量化决策研判 {target_period} 期", C_GREEN)
        print(f"  💎 核心金胆: {C_BOLD}{golden:02d}{C_RESET} (温号池加权Z最高, 当前遗漏 {gap[golden]} 期)")
        print(f"  🥇 热号金胆: {C_BOLD}{hot:02d}{C_RESET} (近20期最热号码, 当前遗漏 {gap[hot]} 期)")
        print(f"  ♨️ 温号池候选 ({len(warm)}个): {' '.join(f'{x:02d}' for x in warm)}")
        print(f"  🛡️ 主系统交叉风控: {cross_flags['safety_audit']}")
        print("  " + THIN)
        print("  Top 5 黄金配对组合 (以金胆为核，条件共现 + 金胆分):")
        for idx, p in enumerate(top5_golden, 1):
            overlap_tag = f" {C_YELLOW}★ 与热胆重叠{C_RESET}" if p["is_hot_overlap"] else ""
            print(f"    Top{idx}: [{C_BOLD}{p['pair_str']}{C_RESET}] (搭档 {p['partner']:02d}, 近期共现 {p['co_count']} 次, 评分 {p['weight']:.4f}){overlap_tag}")

        print("  " + THIN)
        print("  热号金胆配对参考 (旁证辅助):")
        for idx, p in enumerate(top5_hot, 1):
            print(f"    Top{idx}: [{p['pair_str']}] (搭档 {p['partner']:02d}, 评分 {p['weight']:.4f})")

        banner(f"④ 近 {min(15, len(wf_res['rows']))} 期实战复盘流水对账", C_CYAN)
        print(f"  {'期号':^8} │ {'金胆':^6} │ {'热胆':^6} │ {'金胆命中':^8} │ {'热胆命中':^8} │ {'Top1组合':^11} │ {'中2/中1':^8} │ {'温号池':^8}")
        print("  " + THIN)
        for r in wf_res["rows"][:15]:
            g_mark = "✅命中" if r["golden_hit"] else "❌未中"
            h_mark = "✅命中" if r["hot_hit"] else "❌未中"
            combo_mark = "🎉中2" if r["top1_both"] else ("·中1" if r["top1_one"] else "—")
            warm_str = f"{r['warm_hits']}/{r['warm_total']}"
            print(f"  {r['period']:^8} │  {r['golden']:02d}   │  {r['hot']:02d}   │ {g_mark:^8} │ {h_mark:^8} │ [{r['top1_str']}] │ {combo_mark:^8} │ {warm_str:^8}")

        banner("✅ 定金选2 全流程推演圆满完成！", C_GREEN)
        print(f"  📄 预测研报已落盘: outputs/gold_pick2/定金选2预测_{target_period}.txt\n")

    return result_payload


def main():
    parser = argparse.ArgumentParser(description="定金选2 快乐8 每日分析推演")
    parser.add_argument("n_review", nargs="?", type=int, default=30, help="Walk-Forward 复盘期数 (默认: 30)")
    args = parser.parse_args()

    try:
        run_pick2_pipeline(n_review=args.n_review, verbose=True)
    except Exception as e:
        print(f"{C_RED}❌ 执行异常: {e}{C_RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
