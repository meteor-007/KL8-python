#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重点点位分析 (空间点位打分与精排) - 每日全流程一键分析引擎 v3.0 (主系统整合版)
=============================================================================
遵循老派量化操盘手大白话执行协议，透明化 4 维空间特征与二级精排机制。
用法：
  python run_points_daily.py [N_REVIEW=30]
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

from core.spatial_points import (
    load_draws_from_file,
    calculate_spatial_point_features,
    rank_spatial_picks,
    walk_forward_evaluate,
    cross_validate_spatial_picks,
    get_region_baseline,
    BASELINE_TOP10,
    BASELINE_CORE5
)
from backend.data_acquisition.daily_points_manager import (
    load_daily_points,
    get_latest_points_entry
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


def run_points_pipeline(n_review: int = 30, verbose: bool = True) -> dict:
    """
    重点点位分析主执行流水线
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

    # 读取 daily_points.txt：今日 20 点位作为精排候选池，历史点位供 Walk-Forward 口径对齐
    all_pts = load_daily_points()
    today_pool = None
    if all_pts:
        # 优先取目标期对应的点位；缺失时回退到最新一条
        target_entry = all_pts.get(str(target_period))
        if target_entry:
            today_pool = target_entry["points"]
        else:
            latest_entry = get_latest_points_entry()
            today_pool = latest_entry["points"] if latest_entry else None
    pools = {int(k): v["points"] for k, v in all_pts.items()}

    # 1. 计算目标期 80 点位空间特征与精排推荐 (基于全量历史，无泄露)
    pts_data = calculate_spatial_point_features(draws, cutoff_idx=m)
    picks = rank_spatial_picks(pts_data, candidate_points=today_pool)

    # 2. Walk-Forward 近 N 期滚动样本外复盘与置信评定（与今日候选池口径对齐）
    wf_eval = walk_forward_evaluate(draws, n_periods=n_review, candidate_pools=pools)
    conf = wf_eval["confidence"]

    # 3. 多维交叉风控与共振打标
    cross_res = cross_validate_spatial_picks(PROJ_DIR, picks)

    result_payload = {
        "timestamp": datetime.now().isoformat(),
        "latest_period": latest_draw["period"],
        "latest_date": latest_draw["date"],
        "target_period": target_period,
        "confidence": conf,
        "picks": picks,
        "walk_forward": wf_eval,
        "cross_validation": cross_res,
    }

    # 4. 落盘预测产物
    out_dir = os.path.join(PROJ_DIR, "outputs", "spatial_points")
    os.makedirs(out_dir, exist_ok=True)
    out_txt = os.path.join(out_dir, "重点点位预测.txt")
    out_json = os.path.join(out_dir, "spatial_points_latest.json")

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"重点点位分析 每日预测 {target_period} (主系统整合版 {datetime.now():%Y-%m-%d %H:%M})\n")
        f.write(f"置信等级: {conf['description']} | OOF Lift: {wf_eval['oof_lift']:.3f}x\n")
        f.write(f"核心五码: {picks['core5_str']}\n")
        f.write(f"精选十码: {picks['ten_str']}\n")
        f.write(f"扩展十五: {picks['ext15_str']}\n")
        if cross_res["kill_conflicts"]:
            f.write(f"⚠️ 杀号撞车预警: {'-'.join(f'{x:02d}' for x in cross_res['kill_conflicts'])}\n")
        if cross_res["resonance_numbers"]:
            f.write(f"✨ 黄金共振共识: {'-'.join(f'{x:02d}' for x in cross_res['resonance_numbers'])}\n")

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result_payload, f, ensure_ascii=False, indent=2)

    # 追加预测日志
    logs_dir = os.path.join(PROJ_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "spatial_points_logs.txt")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 目标期数: {target_period} | 置信等级: {conf['badge']} | OOF Lift: {wf_eval['oof_lift']:.3f}x\n")
        for p_item in picks["top10_details"][:5]:
            reg_s = ",".join(f"{x:02d}" for x in p_item["region"])
            sig_s = "显著" if p_item["is_significant"] else "非显著"
            f.write(f"  点位[{p_item['point']:02d}] 区域[{reg_s}] 得分:{p_item['score']:.4f} p:{p_item['p_value']:.4f} ({sig_s})\n")
        f.write(f"  >> 核心五码: [{picks['core5_str']}] 精选十码: [{picks['ten_str']}]\n")
        f.write("-" * 80 + "\n")

    if verbose:
        banner("🔮 空间重点点位分析 (打分与精排) — 每日操盘报告 (主系统整合版)", C_MAGENTA)
        print(f"  📁 历史库期数: {m} 期 | 最新开奖: {latest_draw['period']} ({latest_draw['date']}) | 🎯 研判目标: {target_period} 期")

        banner("① 置信等级与样本外滚动评估 (Walk-Forward 近 30 期)", C_YELLOW)
        print(f"  🏆 综合置信等级 : {conf['badge']} (z={conf['z_score']})")
        print(f"  📊 Top10 均命中  : {wf_eval['avg_ten_hits']:.2f} / 10 码 | 提升倍数 Lift: {wf_eval['oof_lift']:.3f}x (基线 2.50)")
        print(f"  💎 Core5 均命中  : {wf_eval['avg_core5_hits']:.2f} / 5 码  | 提升倍数 Lift: {wf_eval['core5_lift']:.3f}x (基线 1.25)")
        print(f"  🌐 区域覆盖率    : {wf_eval['avg_region_rate']*100:.1f}% | 理论基线: {wf_eval['baseline_region']*100:.1f}%")

        banner(f"② 今日空间点位精选研判 (目标期: {target_period})", C_GREEN)
        if today_pool:
            print(f"  📌 今日点位候选池 ({len(today_pool)}码): {C_CYAN}{' '.join(f'{x:02d}' for x in today_pool)}{C_RESET}")
        else:
            print(f"  ⚠️ 未读取到今日点位 (daily_points.txt)，本次按全盘 80 号精排")
        print(f"  💎 核心五码 (Core 5) : {C_BOLD}{picks['core5_str']}{C_RESET}")
        print(f"  🎯 精选十码 (Top 10) : {C_CYAN}{picks['ten_str']}{C_RESET}")
        print(f"  🌐 扩展十五 (Ext 15) : {C_GRAY}{picks['ext15_str']}{C_RESET}")
        bal_msg = "✅ 8 分区全域覆盖平衡" if picks["is_zone_balanced"] else f"⚠️ 分区缺失: {' '.join(picks['missing_zones'])}"
        print(f"  🧭 空间均衡状态     : {bal_msg}")

        print(f"\n  {THIN}")
        print("  【一级 Top 10 重点点位区域与显著性检验】")
        for p_item in picks["top10_details"]:
            reg_s = ",".join(f"{x:02d}" for x in p_item["region"])
            sig_s = f"{C_GREEN}✅显著{C_RESET}" if p_item["is_significant"] else f"{C_GRAY}非显著{C_RESET}"
            gap_v = p_item["features"]["gap"]
            freq_v = p_item["features"]["freq"]
            print(f"    点位 [{p_item['point']:02d}] 区域 [{reg_s}] 得分: {p_item['score']:.4f} | p值: {p_item['p_value']:.4f} ({sig_s}) | 遗漏: {gap_v:2d}期 冷热: {freq_v:2d}次")

        banner("③ 多维系统交叉风控与共振提纯", C_CYAN)
        if cross_res["kill_conflicts"]:
            k_str = "-".join(f"{x:02d}" for x in cross_res["kill_conflicts"])
            print(f"  🔴 {C_RED}KillSeeker 杀号撞车预警{C_RESET} : {k_str} (检测到精选号与杀号重叠，建议降低仓位)")
        else:
            print(f"  🟢 {C_GREEN}KillSeeker 交叉安全{C_RESET}     : 精选号码未触发高置信杀号拦截，安全可攻")

        if cross_res["resonance_numbers"]:
            r_str = "-".join(f"{x:02d}" for x in cross_res["resonance_numbers"])
            print(f"  ✨ {C_YELLOW}多系统黄金共振共识{C_RESET}   : {r_str} (与 LSTM / Trinity / 顺口溜多维共识，优先定胆)")
        else:
            print(f"  ℹ️ 多系统共振状态       : 各子系统独立选号，保持多元化分布")

        banner("④ 近 15 期 Walk-Forward 滚动对账明细", C_YELLOW)
        print("   期号     精选十码                 Top10   Core5   区域命中")
        print(f"  {THIN}")
        for r in wf_eval["rows"][-15:]:
            ten_s = " ".join(f"{x:02d}" for x in r["ten"])
            t_col = C_GREEN if r["ten_hits"] >= 3 else (C_YELLOW if r["ten_hits"] == 2 else C_RED)
            c_col = C_GREEN if r["core5_hits"] >= 2 else (C_YELLOW if r["core5_hits"] == 1 else C_RED)
            print(f"   {r['period']}   {ten_s:<26}  {t_col}{r['ten_hits']:>2}/10{C_RESET}   {c_col}{r['core5_hits']:>2}/5{C_RESET}    {r['region_hits']:>2}/10")
        print(f"  {THIN}")

        banner("📋 操盘手一键复制纯文本", C_CYAN)
        print(f"快乐8 目标期 {target_period} 重点点位分析 精选号码")
        print("◎ 核心五码")
        print(", ".join(f"{x:02d}" for x in picks["core5"]))
        print("◎ 精选十码")
        print(", ".join(f"{x:02d}" for x in picks["ten"]))
        print("◎ 扩展十五码")
        print(", ".join(f"{x:02d}" for x in picks["ext15"]))
        print("◎ 置信评级")
        print(f"{conf['badge']} (OOF Lift: {wf_eval['oof_lift']:.3f}x)")
        print(f"\n  📄 预测产物已落盘: {os.path.relpath(out_txt, PROJ_DIR)}")
        banner("重点点位分析完成 ✅", C_GREEN)

    return result_payload


def main():
    n_rev = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30
    run_points_pipeline(n_review=n_rev, verbose=True)


if __name__ == "__main__":
    main()
