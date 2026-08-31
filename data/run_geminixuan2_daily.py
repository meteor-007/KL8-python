#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini 选2预测 (K8-Quant 智能选2与金银铜胆量化推演) - 每日全流程一键分析推演引擎 v3.0 (主系统整合版)
=================================================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 算子1 空间张力 (spatial) —— 8大区间真空(0个)重仓填坑 / 过载(≥5个)做空
2. 算子2 尾数信息熵 (tail)   —— 尾数全灭补偿 / 极值做空 / 连续2期锁死防接飞刀
3. 算子3 马尔可夫扩散 (diffuse) —— 大热号群热惯性向 ±1、±2 边码渗透溢出
4. 算子4 共现社区 (community) —— 近期共现帮派评分 + 对子号(11-77)异象杀补
5. 算子5 动量 (momentum) —— 上期热号火炉不熄延续性加分

产出决策：
- 💎 首席金胆 Top 1 / 🥈 次席银胆 Top 2 / 🥉 强力铜胆 Top 3
- 🎯 核心 4 码主推组 (Core 4)
- 🛡️ 终极 5 码防线组 (Def 5)
- 🚫 铁血纪律区 (做空/坚决排除)
- ⚡ 今日物理异象 (空间真空/过载/尾数湮灭)

用法：
  python run_geminixuan2_daily.py [N_REVIEW=30]
"""
import os
import sys
from pathlib import Path

_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ_DIR = _PROJ_DIR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gemini_pick2.engine import (
    load_draws,
    daily_picks,
    oof_stats,
    get_confidence_badge,
    run_daily_pipeline,
    BASE_SINGLE,
    W,
    NUM
)

# 终端色彩控制
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_GOLD = "\033[38;5;220m"
C_PURPLE = "\033[95m"
LINE = "═" * 74
THIN = "─" * 74


def print_banner(txt: str):
    print(f"\n{C_CYAN}{LINE}{C_RESET}")
    print(f"  {C_BOLD}{txt}{C_RESET}")
    print(f"{C_CYAN}{LINE}{C_RESET}")


def main():
    n_review = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    print_banner("💎 Gemini 选2预测 K8-Quant 快乐8 每日量化研判 (主系统整合版)")

    draws = load_draws()
    if not draws:
        print(f"{C_RED}❌ 无法加载开奖历史数据{C_RESET}")
        return

    by = {d["period"]: d for d in draws}
    m = len(draws)
    latest = draws[-1]
    target = latest["period"] + 1

    print(f"  📁 历史总库: {C_BOLD}{m}{C_RESET} 期 | 最新开奖: {C_CYAN}{latest['period']}{C_RESET} ({latest['date']}) | 🎯 目标研判: {C_GOLD}{target}{C_RESET}")
    print(f"  🧮 5大底层算子: 空间张力 0.28 / 尾数熵 0.22 / 马尔可夫扩散 0.24 / 共现社区 0.16 / 动量延续 0.10")
    print(f"  🎲 理论随机基线: 单码胆 25.0% | 3胆至少中1=57.8% | 核心4码期望 1.0/期 | 终极5码期望 1.25/期")

    # 1. 样本外无泄露滚动推演 + 今日预测
    lo = max(0, m - n_review)
    pred = {}
    for t in range(lo, m):
        p = daily_picks(draws, t)
        if p:
            pred[draws[t]["period"]] = p
    today = daily_picks(draws, m)
    print(f"  ✅ 样本外滚动计算已完成: 近 {len(pred)} 期历史对账 + 目标第 {target} 期决策")

    # 2. 置信评估
    st = oof_stats(draws, n_review)
    lvl, z, lift = get_confidence_badge(st["gold"] / max(st["n"], 1), st["n"])
    print_banner("② 置信评估与 5 大算子自省 (Walk-Forward 严格样本外)")
    print(f"  👑 首席金胆: {st['gold']}/{st['n']} = {st['gold']/st['n']*100:.1f}% | Lift = {C_BOLD}{lift:.2f}x{C_RESET} (随机25.0%) | {lvl}")
    print(f"  🥈 银胆命中: {st['silver']/st['n']*100:.1f}% | 🥉 铜胆命中: {st['bronze']/st['n']*100:.1f}% | 3胆至少中1: {st['any']/st['n']*100:.1f}% (基线57.8%)")
    print(f"  🎯 核心4码均命中: {st['c4']/st['n']:.2f}/期 (期望 1.0) | 🛡️ 终极5码均命中: {st['d5']/st['n']:.2f}/期 (期望 1.25)")
    print(f"  {THIN}")
    print("  算子自省 (各算子独立Top1单码命中率 vs 25% 随机基准):")
    for op, weight in W.items():
        op_hit = st["op_hit"].get(op, 0)
        op_tot = max(st["op_n"].get(op, 1), 1)
        hr = op_hit / op_tot
        mark = f"{C_GREEN}✅ 有效{C_RESET}" if hr >= 0.25 * 1.05 else (f"{C_YELLOW}⚠️ 持平{C_RESET}" if hr >= 0.25 else f"{C_RED}❌ 疲软{C_RESET}")
        print(f"    {op:<12} (权{weight:.2f}): {op_hit}/{op_tot} = {hr*100:.1f}%  {mark}")

    # 3. 昨期复盘
    prev = pred.get(latest["period"])
    if prev:
        act = latest["nums"]
        hits = [d for d in prev["dans"] if d in act]
        print_banner(f"③ 昨期对账复盘 第 {latest['period']} 期")
        print(f"  真实开奖: {'-'.join(f'{x:02d}' for x in sorted(act))}")
        print(f"  昨期推荐: 金{prev['gold']:02d} 银{prev['silver']:02d} 铜{prev['bronze']:02d} | 核心4码: {'-'.join(f'{x:02d}' for x in prev['core4'])} | 终极5码: {'-'.join(f'{x:02d}' for x in prev['def5'])}")
        dan_str = f"{C_GREEN}✅ 命中 {'、'.join(f'{d:02d}' for d in hits)}{C_RESET}" if hits else f"{C_RED}❌ 未命中{C_RESET}"
        print(f"  对账实测: 三胆 {dan_str} | 核心4码中 {len(set(prev['core4']) & act)} | 终极5码中 {len(set(prev['def5']) & act)}")

    # 4. 今日异象与最新预测
    p = today
    print_banner(f"④ 目标预测 第 {target} 期核心决策阵列")
    print("  [今日空间与尾数物理异象]")
    if p["anomalies"]:
        for kind, desc in p["anomalies"][:4]:
            print(f"    ⚡ {C_YELLOW}{kind}{C_RESET}: {desc}")
    else:
        print("    温和期，无显著极端真空/过载异象")
    print(f"  {THIN}")
    print(f"  💎 {C_GOLD}首席金胆 Top 1: {p['gold']:02d}{C_RESET} | 🥈 {C_CYAN}次席银胆 Top 2: {p['silver']:02d}{C_RESET} | 🥉 {C_PURPLE}强力铜胆 Top 3: {p['bronze']:02d}{C_RESET}")
    print(f"  🎯 核心 4 码主推组: {C_BOLD}{'-'.join(f'{x:02d}' for x in p['core4'])}{C_RESET} (疏散方差压缩, 期望中 1.0)")
    print(f"  🛡️ 终极 5 码防线组: {C_BOLD}{'-'.join(f'{x:02d}' for x in p['def5'])}{C_RESET} (底仓防线, 期望中 1.25)")
    print(f"  {THIN}")
    if p["kill"]:
        print(f"  🚫 {C_RED}铁血纪律区 (坚决做空):{C_RESET} 过载/极值透支号码 {'-'.join(f'{x:02d}' for x in p['kill'][:20])} 共 {len(p['kill'])} 码")
    else:
        print("  🚫 铁血纪律区: 今日无过载/极值做空信号")

    # 5. 落盘
    run_daily_pipeline(n_review=n_review)
    print_banner("🎉 Gemini 选2预测推演圆满完成！")


if __name__ == "__main__":
    main()
