#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 顺口溜（口诀规律与组合带出）每日全流程分析工具 v2.5
======================================================
原理（大白话）：找"顺口溜"规律——某期开出某几个号码后，下期大概率带出另外几个号码。
口诀规则库：90 条经过 FDR-BH 多重检验与样本外 (OOF) 筛选的精英口诀。
用法：
    python run_jingle_daily.py [N=30]
"""
import os
import sys
import re
import csv
from datetime import datetime

# 保证根目录与 backend 在 sys.path (Dual-Root Bootstrap)
_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ = _PROJ_DIR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.formula_jingle.jingle_engine import (
    load_jingle_rules,
    fired_rules,
    predict_jingle,
    save_jingle_prediction,
    at_least_one_baseline,
    BASELINE_PAIR,
    BASELINE_TRIPLE,
)
from core.formula_jingle.jingle_reviewer import review_jingle
from core.formula_jingle.jingle_cross_validator import cross_validate_jingle
from utils.paths import data_path

# ANSI 终端色彩
LINE = "═" * 74
THIN = "─" * 74


def banner(text: str):
    print("\n" + LINE)
    print(f"  {text}")
    print(LINE)


def load_draws_from_history() -> list:
    """加载历史开奖数据，按期号升序返回 [(issue:int, date:str, nums:list[int])]"""
    hist_file = data_path("kl8_history_final.txt")
    if not os.path.exists(hist_file):
        hist_file = os.path.join(PROJ, "kl8_history_final.txt")

    draws = []
    if os.path.exists(hist_file):
        with open(hist_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line)
                if m:
                    nums = [int(x) for x in m.group(3).split("-") if x.isdigit()]
                    if len(nums) == 20:
                        draws.append((int(m.group(2)), m.group(1), nums))
    draws.sort(key=lambda x: x[0])
    return draws


def main():
    n_review = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30
    banner(f"顺口溜口诀规律与组合带出分析 (v2.5 落地整合版) | 复盘期数={n_review}")

    draws = load_draws_from_history()
    if not draws:
        print("  ❌ 未能加载开奖历史数据，请检查 kl8_history_final.txt")
        sys.exit(1)

    rules, meta = load_jingle_rules()
    if not rules:
        print("  ❌ 未能加载口诀库 rules/口诀表_stats.json")
        sys.exit(1)

    latest = draws[-1]
    l_issue, l_date, l_nums = latest
    val_end_period = int(str(meta.get("val_end_period", "2026210")))

    print(f"  📁 历史数据: 共 {len(draws)} 期 (最新开奖: {l_issue} 期, 日期: {l_date})")
    print(f"  📜 口诀规则: 共 {len(rules)} 条精英规则 (FDR+样本外双重检验, 提炼截止期: {val_end_period})")

    # 阶段 1: 近 N 期复盘对账
    review_res = review_jingle(draws, rules, n=n_review, sel_cut=val_end_period)
    banner(f"① 近 {n_review} 期对账复盘（用上一期触发口诀 → 对照本期实开）")
    
    pairs = review_res.get("pairs", [])
    if pairs:
        print("   触发期     目标期   触发口诀数  推荐码            中N/个  至少一中  双双中/触发  单中/触发")
        print("  " + THIN)
        for p in pairs:
            rec_s = " ".join(f"{x:02d}" for x in p["recommended"]) or "—"
            flag = "✅" if p["at_least_one"] else "❌"
            pp = f"{p['np_ok']}/{p['np_fire']}"
            pt = f"{p['nt_ok']}/{p['nt_fire']}"
            print(f"   {p['trigger_issue']}  → {p['target_issue']}     {p['fired_count']:>4}        {rec_s:<24}  {p['hit_count']:>2}    {flag}      {pp:<7} {pt}")
        print("  " + THIN)

        m = review_res.get("metrics", {})
        print(f"  📊 触发期 {m.get('valid_trigger_periods', 0)} 期 / 共触发 {m.get('total_rules_fired', 0)} 条口诀（平均每期推荐 {m.get('avg_rec_per_period', 0):.1f} 码）")
        print(f"     「至少一中」命中率: {m.get('at_least_one_rate', 0)*100:.1f}% | 理论随机基线 ≈ {m.get('baseline_rate', 0)*100:.1f}% | 综合 Lift={m.get('overall_lift', 1.0):.2f}x")
        print(f"     平均单期命中: {m.get('avg_hit_per_period', 0):.2f} 码")

        p_stat = m.get("pair_stats", {})
        if p_stat.get("fires", 0) > 0:
            print(f"     两号齐出规则: 命中 {p_stat['hits']}/{p_stat['fires']} = {p_stat['rate']*100:.1f}% | 理论基线 6.0% | Lift={p_stat['lift']:.2f}x")

        t_stat = m.get("triple_stats", {})
        if t_stat.get("fires", 0) > 0:
            print(f"     单号带出规则: 命中 {t_stat['hits']}/{t_stat['fires']} = {t_stat['rate']*100:.1f}% | 理论基线 25.0% | Lift={t_stat['lift']:.2f}x")

        # 分层打印
        for seg_name, s in m.get("segments", {}).items():
            print(f"  📌 {seg_name}: 触发 {s['periods']} 期 / 触发 {s['fired_rules']} 条 | 至少一中 {s['at_least_one_rate']*100:.1f}% vs 基线 {s['baseline_rate']*100:.1f}% (Lift={s['lift']:.2f}x)")
    else:
        print(f"  ⚠️ 近 {n_review} 期无口诀触发记录")

    # 阶段 2: 今日预测
    banner(f"② 今日口诀触发扫描（基于最新期 {l_issue} 触发 → 预测目标期）")
    pred_res = predict_jingle(draws, rules)
    fired_details = pred_res.get("fired_details", [])

    if fired_details:
        print("   口诀ID  规则类型    触发组合        推荐带出号码    OOF命中率   OOF_Lift   样本外触发/命中")
        print("  " + THIN)
        for d in fired_details:
            tr_s = " ".join(f"{x:02d}" for x in d["trigger"])
            pd_s = " ".join(f"{x:02d}" for x in d["predict"])
            print(f"   #{d['rule_id']:<6} {d['kind_name']:<8} [{tr_s:<11}] → [{pd_s:<11}]   {d['oof_hit_rate']*100:>6.1f}%    {d['oof_lift']:>5.2f}x     {d['triggers_oof']}/{d['hits_oof']}")
        print("  " + THIN)
    else:
        print("  ⚠️ 今日最新开奖号码未触发任何口诀规则。")

    # 阶段 3: 综合推荐码与交叉风控
    banner(f"③ 综合推荐码与交叉风控核验 (目标期: {pred_res['target_issue']})")
    top_nums = pred_res.get("recommended_numbers", [])
    k_count = len(top_nums)
    base_pct = pred_res.get("at_least_one_baseline", 0.0) * 100

    print(f"  🎯 口诀加权推荐码: " + (" ".join(f"{n:02d}" for n in top_nums) if top_nums else "无"))
    print(f"     推荐 {k_count} 码 | 「至少命中1码」理论随机基线期望 ≈ {base_pct:.1f}%")

    if top_nums:
        cross_res = cross_validate_jingle(top_nums, target_issue=pred_res["target_issue"])
        print("\n  🛡️ 交叉风控审计明细:")
        for t in cross_res.get("detailed_tags", []):
            tag_str = " ".join(f"[{tag['label']} - {tag['desc']}]" for tag in t["tags"])
            print(f"     号码 {t['number']:02d} -> {tag_str}")

        if cross_res.get("clash_numbers"):
            clash_str = " ".join(f"{x:02d}" for x in cross_res["clash_numbers"])
            print(f"  ⚠️ 重点警示: 号码 [{clash_str}] 属于高置信杀号，请调低或剔除其投入！")

        if cross_res.get("all_resonance"):
            res_str = " ".join(f"{x:02d}" for x in cross_res["all_resonance"])
            print(f"  🌟 强共振金码: 号码 [{res_str}] 获得定金选2/LSTM深度时序共同共识推荐！")

    # 阶段 4: 落盘
    saved_files = save_jingle_prediction(pred_res)
    if saved_files:
        print(f"\n  📄 预测报告已成功保存至:")
        for f in saved_files:
            print(f"     - {os.path.relpath(f, PROJ)}")

    # 阶段 5: 最终纯文本
    banner("④ 📋 最终可复制纯文本（操盘速查）")
    print(f"快乐8 目标期 {pred_res['target_issue']} 顺口溜口诀 精选号码")
    print(f"◎ 触发口诀推荐码（共 {k_count} 码）:")
    print("  " + (", ".join(f"{n:02d}" for n in top_nums) if top_nums else "无"))
    print(f"◎ 重点口诀明细:")
    for d in fired_details[:4]:
        tr_s = " ".join(f"{x:02d}" for x in d["trigger"])
        pd_s = " ".join(f"{x:02d}" for x in d["predict"])
        print(f"  - 触发 [{tr_s}] → 推荐 [{pd_s}] (OOF: {d['oof_hit_rate']*100:.1f}%, Lift: {d['oof_lift']:.2f}x)")
    print(f"◎ 理论期望: 至少一中期望 ≈ {base_pct:.1f}% (超几何随机基线)")
    banner("顺口溜口诀分析执行完成 ✅")


if __name__ == "__main__":
    main()
