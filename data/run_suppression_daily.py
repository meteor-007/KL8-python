#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
未开点位反弹追踪 (Point Suppression Engine) - 每日全流程一键分析引擎 v2.0 (主系统整合版)
=====================================================================================
遵循老派量化操盘手大白话执行协议，透明化弹簧压制回补、能量外溢蹭热度与影子替身牵引机制。
用法：
  python run_suppression_daily.py [N_REVIEW=30]
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

from core.point_suppression import (
    PointSuppressionAnalyzer,
    load_draws_from_file,
    get_active_suppression_state,
    evaluate_suppression_walk_forward,
    cross_validate_suppression_picks,
    SINGLE_BASE,
    REGION_BASE
)

# ANSI 颜色
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


def run_suppression_pipeline(n_review: int = 30, verbose: bool = True) -> dict:
    """
    未开点位反弹追踪主执行流水线
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

    # 1. 挖掘历史特征与模式 (弹簧压制分布、能量外溢率、影子替身伴生矩阵)
    analyzer = PointSuppressionAnalyzer(draws)
    patterns = analyzer.analyze_historical_patterns(train_len=m)

    # 2. 获取当前落空号码状态，并用 AI海选反弹团 打分
    active_supp = get_active_suppression_state(draws, cutoff_idx=m)
    ranked_candidates = analyzer.score_unhit_candidates(draws, active_supp, patterns)

    # 3. 严格 Walk-Forward 近 N 期滚动无未来函数样本外评估
    wf_eval = evaluate_suppression_walk_forward(draws, test_window=n_review)
    conf = wf_eval["confidence"]

    # 4. 跨系统多维交叉风控
    cross_res = cross_validate_suppression_picks(PROJ_DIR, ranked_candidates)

    top3_candidates = ranked_candidates[:3]
    top3_nums = [c["num"] for c in top3_candidates]
    top1 = ranked_candidates[0] if ranked_candidates else None

    result_payload = {
        "timestamp": datetime.now().isoformat(),
        "latest_period": latest_draw["period"],
        "latest_date": latest_draw["date"],
        "target_period": target_period,
        "confidence": conf,
        "top1": top1,
        "top3_candidates": top3_candidates,
        "all_candidates": ranked_candidates,
        "walk_forward": wf_eval,
        "cross_validation": cross_res,
        "patterns_summary": {
            "spill_stats": patterns["spill_stats"],
            "total_surrogates_mapped": len(patterns["surrogate_map"])
        }
    }

    # 5. 落盘预测产物
    out_dir = os.path.join(PROJ_DIR, "outputs", "point_suppression")
    os.makedirs(out_dir, exist_ok=True)
    out_txt = os.path.join(out_dir, "未开点位反弹预测.txt")
    out_json = os.path.join(out_dir, "suppression_latest.json")
    out_md = os.path.join(out_dir, f"未开点位反弹分析_{datetime.now():%Y%m%d}_T{target_period}.md")

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"未开点位反弹追踪 每日预测 {target_period} (主系统整合版 {datetime.now():%Y-%m-%d %H:%M})\n")
        f.write(f"置信等级: {conf['description']} | 区域Lift: {wf_eval['top1_region_lift']:.3f}x\n")
        f.write(f"最新开奖: {latest_draw['period']}期 ({latest_draw['date']})\n")
        f.write(f"反弹Top3金胆: {'-'.join(f'{x:02d}' for x in top3_nums)}\n")
        if top1:
            f.write(f"首重反弹胆: {top1['num']:02d} (压制{top1['k_suppression']}期, 得分{top1['score']}, 评级:{top1['confidence']})\n")
        f.write("-" * 60 + "\n")
        for idx, c in enumerate(ranked_candidates[:6], 1):
            f.write(f"[{idx}] 号码 {c['num']:02d} | 压制: {c['k_suppression']}期 | 得分: {c['score']} | 共振: {c['res']}路 | 评级: {c['confidence']}\n")

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result_payload, f, ensure_ascii=False, indent=2)

    with open(out_md, "w", encoding="utf-8") as f:
        f.write(f"# 🪞 未开点位高压反弹与空间关联分析报告\n\n")
        f.write(f"- **目标期号**: {target_period} 期\n")
        f.write(f"- **最新开奖**: {latest_draw['period']} 期 ({latest_draw['date']})\n")
        f.write(f"- **置信评级**: {conf['description']} (z={wf_eval['z_score']:.2f})\n")
        f.write(f"- **样本外表现 (近{wf_eval['n_periods']}期)**: Top1单码命中率 {wf_eval['top1_single_rate']*100:.1f}% (Lift={wf_eval['top1_single_lift']:.2f}x), Top1区域命中率 {wf_eval['top1_region_rate']*100:.1f}% (Lift={wf_eval['top1_region_lift']:.2f}x)\n\n")
        f.write(f"## 🎯 核心反弹推荐 (Top 1~3)\n\n")
        for idx, c in enumerate(top3_candidates, 1):
            f.write(f"{idx}. **号码 {c['num']:02d}** (压制 {c['k_suppression']} 期 / 评分 {c['score']} / {c['confidence']})\n")
            f.write(f"   - 7路共振信号: {','.join(c['sigs'])}\n")
            f.write(f"   - 三号区范围: {','.join(f'{x:02d}' for x in c['region'])}\n")
            if c.get("surr_list"):
                surr_str_md = ", ".join(f"{s['surrogate_num']:02d}(胜率{s['prob']*100:.1f}%,Lift={s['lift']}x)" for s in c['surr_list'])
                f.write(f"   - 伴生影子替身: {surr_str_md}\n\n")

    if verbose:
        banner(f"🪞 未开点位反弹追踪 (Point Suppression) 每日决策报告 (目标 {target_period} 期)")
        print(f"  {C_GRAY}数据基准: 历史 {m} 期 | 最新开奖 {latest_draw['period']} 期 ({latest_draw['date']}){C_RESET}")
        print(f"  {C_BOLD}置信等级: {conf['description']}{C_RESET}")
        print(f"  {C_CYAN}样本外近 {wf_eval['n_periods']} 期对账:{C_RESET} Top1单码命中率 {C_GREEN}{wf_eval['top1_single_rate']*100:.1f}%{C_RESET} (Lift={wf_eval['top1_single_lift']:.2f}x) | Top1区域命中率 {C_GREEN}{wf_eval['top1_region_rate']*100:.1f}%{C_RESET} (Lift={wf_eval['top1_region_lift']:.2f}x)")

        print(f"\n{C_YELLOW}┌─── 🎯 今日未开高压反弹精选 Top 3 金胆 ─────────────────────────┐{C_RESET}")
        for idx, c in enumerate(top3_candidates, 1):
            color = C_GREEN if c["conf_grade"] == "S" else (C_YELLOW if c["conf_grade"] == "A" else C_GRAY)
            print(f"│  {color}[{idx}] 号码 {c['num']:02d}{C_RESET} │ 压制 {c['k_suppression']} 期 │ 得分: {c['score']} │ 共振: {c['res']}路 │ {c['confidence']}")
            if c.get("surr_list"):
                surr_str = ", ".join(f"{s['surrogate_num']:02d}(Lift {s['lift']}x)" for s in c["surr_list"])
                print(f"│      └─ 🪞 影子替身伴生: {surr_str}")
        print(f"{C_YELLOW}└────────────────────────────────────────────────────────────────┘{C_RESET}")

        print(f"\n{C_MAGENTA}┌─── 🔗 跨系统共振与交叉风控标签 ────────────────────────────────┐{C_RESET}")
        for item in cross_res.get("cross_items", [])[:4]:
            print(f"│  号码 {item['num']:02d} (得分 {item['score']}) ➔ {' | '.join(item['tags'])}")
        print(f"{C_MAGENTA}└────────────────────────────────────────────────────────────────┘{C_RESET}")

        print(f"\n  💾 预测结果已输出至:")
        print(f"     • {out_txt}")
        print(f"     • {out_json}")
        print(f"     • {out_md}\n")

    return result_payload


def main():
    n_review = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    run_suppression_pipeline(n_review=n_review, verbose=True)


if __name__ == "__main__":
    main()
