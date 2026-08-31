#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跟随分析 (重复号追踪与多窗条件跟随) - 每日全流程一键分析推演引擎 v3.0 (主系统整合版)
=================================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 重复号追踪 (Top 5 主候选) ── 大白话：昨天开出的 20 个号里，谁在历史上"连庄再开"概率最高。
2. 综合推演 (Top 6 搭档跟随) ── 大白话：排除昨天已开号码，按单双号伙伴跟随率选出最该被带出的号码。
3. 条件跟随 (Top 8 多窗软融合) ── 大白话：挑出昨天最强 Top 5 黄金搭档，查多窗口(100/200/300/500期)历史跟随规律。
4. 黄金共振交集 ── 大白话：既被重复号看中、又被推演/跟随看中的共振焦点码。
用法：
  python run_follow_daily.py [N_REVIEW=30]
"""
import os
import sys
import json
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

from core.follow_analysis import (
    load_draws_from_history,
    calculate_history_repeat_avg,
    repeat_analysis,
    inference_top6,
    conditional_follow,
    daily_follow_picks,
    walk_forward_evaluate,
    cross_validate_follow_picks,
    BASELINE_REPEAT_TOP5,
    BASELINE_INFERENCE_TOP6,
    BASELINE_FOLLOW_TOP8
)

# 颜色控制
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


def run_follow_pipeline(n_review: int = 30, verbose: bool = True) -> dict:
    """
    跟随分析主执行流水线
    """
    history_file = os.path.join(PROJ_DIR, "kl8_history_final.txt")
    if not os.path.exists(history_file):
        history_file = os.path.join(PROJ_DIR, "storage", "raw", "kl8_history_final.txt")

    draws = load_draws_from_history(history_file)
    if not draws:
        raise RuntimeError(f"无法读取历史开奖数据: {history_file}")

    m = len(draws)
    latest_draw = draws[-1]
    target_period = latest_draw["period"] + 1

    # 1. 提炼目标期三路选号与交集 (严格基于截至最新期的全量历史，无未来函数)
    picks = daily_follow_picks(draws, cutoff_idx=m)
    if not picks:
        raise RuntimeError("无法完成目标期跟随分析推演")

    # 2. Walk-Forward 滚动样本外对账与置信评定
    wf_eval = walk_forward_evaluate(draws, n_periods=n_review)
    conf = wf_eval["confidence"]

    # 3. 多维交叉风控与共振打标
    cross_res = cross_validate_follow_picks(PROJ_DIR, picks)

    result_payload = {
        "timestamp": datetime.now().isoformat(),
        "latest_period": latest_draw["period"],
        "latest_date": latest_draw["date"],
        "target_period": target_period,
        "confidence": conf,
        "picks": picks,
        "walk_forward": wf_eval,
        "cross_validation": cross_res
    }

    # 4. 落盘预测产物
    out_dir = os.path.join(PROJ_DIR, "outputs", "follow_analysis")
    os.makedirs(out_dir, exist_ok=True)
    out_txt = os.path.join(out_dir, "跟随分析预测.txt")
    out_json = os.path.join(out_dir, "follow_latest.json")

    rep = picks["repeat"]
    inf = picks["inference"]
    cf = picks["conditional"]

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"跟随分析 每日预测 {target_period} (主系统整合版 {datetime.now():%Y-%m-%d %H:%M})\n")
        f.write(f"置信评级: {conf['badge']} ({conf['description']}) | 近30期重复号Lift: {wf_eval['rep_lift']:.3f}x\n")
        f.write(f"重复号Top5 (主候选): {rep['top5_str']}\n")
        f.write(f"综合推演Top6 (搭档跟随): {inf['top6_str']}\n")
        f.write(f"条件跟随Top8 (多窗软融合): {cf['top8_str']}\n")
        f.write(f"双重交集确认: {picks['resonance_str']}\n")
        if cross_res["kill_conflicts"]:
            f.write(f"⚠️ 杀号撞车预警: {'-'.join(f'{x:02d}' for x in cross_res['kill_conflicts'])}\n")
        if cross_res["resonance_numbers"]:
            f.write(f"✨ 黄金共振号码: {'-'.join(f'{x:02d}' for x in cross_res['resonance_numbers'])}\n")

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result_payload, f, ensure_ascii=False, indent=2)

    # 5. 追加运行日志
    logs_dir = os.path.join(PROJ_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "follow_analysis_logs.txt")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 目标期数: {target_period} | 置信: {conf['badge']} | 重复Lift: {wf_eval['rep_lift']:.3f}x | 推演Lift: {wf_eval['inf_lift']:.3f}x | 跟随Lift: {wf_eval['cf_lift']:.3f}x\n")
        f.write(f"  >> 重复Top5: [{rep['top5_str']}] 推演Top6: [{inf['top6_str']}] 跟随Top8: [{cf['top8_str']}] 交集: [{picks['resonance_str']}]\n")
        f.write("-" * 80 + "\n")

    if verbose:
        banner("🔗 跟随分析 (重复号追踪与多窗条件跟随) — 每日操盘报告 (主系统整合版)", C_MAGENTA)
        print(f"  📁 历史库期数: {m} 期 | 最新开奖: {latest_draw['period']} ({latest_draw['date']}) | 🎯 研判目标: {target_period} 期")
        print(f"  🎯 核心策略: 重复号追踪(主候选) + 综合推演(伙伴跟随) + 条件跟随(多窗交集软融合) | 单码基线 25%")

        banner(f"① 置信等级与样本外滚动评估 (Walk-Forward 近 {n_review} 期)", C_YELLOW)
        print(f"  🏆 综合置信等级 : {conf['badge']} ({conf['description']})")
        print(f"  🔁 重复号Top5   : 均命中 {wf_eval['avg_rep_hits']:.2f} / 5 码  | 期望 {BASELINE_REPEAT_TOP5:.2f} | Lift: {C_BOLD}{wf_eval['rep_lift']:.3f}x{C_RESET} (z={wf_eval['rep_z']:.2f})")
        print(f"  🧮 综合推演Top6 : 均命中 {wf_eval['avg_inf_hits']:.2f} / 6 码  | 期望 {BASELINE_INFERENCE_TOP6:.2f} | Lift: {wf_eval['inf_lift']:.3f}x (z={wf_eval['inf_z']:.2f})")
        print(f"  🌐 条件跟随Top8 : 均命中 {wf_eval['avg_cf_hits']:.2f} / 8 码  | 期望 {BASELINE_FOLLOW_TOP8:.2f} | Lift: {wf_eval['cf_lift']:.3f}x (z={wf_eval['cf_z']:.2f})")
        print(f"  💡 操盘手内幕提醒: 重复号为唯一具有持续正向超额特征通道，综合推演与条件跟随作对冲对照，理性组合配置。")

        banner(f"② 今日跟随精选研判 (目标期: {target_period})", C_GREEN)
        print(f"  ┌─ 🔁 重复号 Top 5 (主候选 · 连庄追踪) ──────────")
        for i, n in enumerate(rep["top5"], 1):
            print(f"  │  #{i} [{n:02d}] 历史自重复率 Lift = {rep['rates'][n]:.3f}x")
        print(f"  │  全历史平均连庄 {rep['hist_avg_repeat']:.1f} 个/期 | 最近一期连庄 {rep['last_repeat']} 个")
        print(f"  └───────────────────────────────────────────────")

        print(f"  ┌─ 🧮 综合推演 Top 6 (搭档跟随 · 排除上期已开) ──")
        print(f"  │  {C_CYAN}{inf['top6_str']}{C_RESET}")
        print(f"  └───────────────────────────────────────────────")

        print(f"  ┌─ 🌐 条件跟随 Top 8 (多窗口RRF跨条件软融合) ───")
        print(f"  │  {C_YELLOW}{cf['top8_str']}{C_RESET}")
        print(f"  └───────────────────────────────────────────────")

        if picks["resonance_intersection"]:
            print(f"  ⭐ {C_BOLD}{C_GREEN}黄金共振双重交集确认号: {picks['resonance_str']}{C_RESET} (多维度强共鸣，重点关注)")
        else:
            print(f"  ⭐ 黄金共振双重交集: 无")

        banner("③ 条件跟随多窗明细 (上期Top5黄金共现对 -> 历史下一期跟随)", C_CYAN)
        for ci in cf["cond_info"]:
            pair_s = ci["pair_str"]
            i3_s = ci["inter3_str"]
            print(f"  条件对 [{pair_s}] 历史共现 {ci['historical_occ']} 次 ➔ >=3 窗交集跟随: {C_BOLD}{i3_s}{C_RESET}")

        banner(f"④ 近 {len(wf_eval['rows'])} 期命中率复盘流水", C_YELLOW)
        print(f"   {'期号':^8} │ {'重复Top5':^10} │ {'推演Top6':^10} │ {'跟随Top8':^10} │ {'交集确认'}")
        print("  " + THIN)
        for r in wf_eval["rows"][-15:]:
            r_hit_s = f"{r['rep_hits']}/5"
            i_hit_s = f"{r['inf_hits']}/6"
            c_hit_s = f"{r['cf_hits']}/8"
            inter_s = "-".join(f"{x:02d}" for x in r["inter_hit_nums"]) if r["inter_hit_nums"] else "无"
            print(f"   {r['period']:^8} │ {r_hit_s:^10} │ {i_hit_s:^10} │ {c_hit_s:^10} │ {inter_s}")
        print("  " + THIN)
        print(f"  📊 均值汇总: 重复Top5 {wf_eval['avg_rep_hits']:.2f}/5 (Lift={wf_eval['rep_lift']:.2f}x) | 推演Top6 {wf_eval['avg_inf_hits']:.2f}/6 (Lift={wf_eval['inf_lift']:.2f}x) | 跟随Top8 {wf_eval['avg_cf_hits']:.2f}/8 (Lift={wf_eval['cf_lift']:.2f}x)")

        if cross_res["resonance_numbers"]:
            banner("⑤ 跨系统多维共振交叉确认", C_MAGENTA)
            print(f"  ✨ 跨系统多维共振号码: {' '.join(f'[{x:02d}]' for x in cross_res['resonance_numbers'])}")
        if cross_res["kill_conflicts"]:
            print(f"  ⚠️ 杀号池撞车预警号码: {' '.join(f'[{x:02d}]' for x in cross_res['kill_conflicts'])}")

        print(f"\n  📄 预测结果已落盘: {os.path.relpath(out_txt, PROJ_DIR)}")
        banner("跟随分析推演圆满完成 ✅", C_GREEN)

    return result_payload


def main():
    n_review = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30
    run_follow_pipeline(n_review=n_review, verbose=True)


if __name__ == "__main__":
    main()
