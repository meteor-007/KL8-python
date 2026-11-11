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
  python -m backend.modules.sixteen.run_daily [N_REVIEW=30]
"""
import os
import sys
import json
import argparse
from datetime import datetime

# 路径自适应 (模块迁入 backend/modules 后：向上定位项目根)
def _find_project_root(start: str) -> str:
    curr = start
    for _ in range(8):
        if os.path.isdir(os.path.join(curr, "backend")) and os.path.isdir(os.path.join(curr, "frontend")):
            return curr
        if os.path.exists(os.path.join(curr, "GEMINI.md")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return start

_PROJ_DIR = _find_project_root(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ_DIR = _PROJ_DIR

from backend.utils.paths import get_cache_dir, get_reports_dir, get_outputs_dir

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

    # 2. 导出今日研报（仅 storage/reports 与 storage/outputs/reports）
    report_md = engine.generate_report(analysis_res)
    fname = f"sixteen_analysis_report_{target_period}.md"
    for dpath in (get_reports_dir(), os.path.join(get_outputs_dir(), "reports")):
        os.makedirs(dpath, exist_ok=True)
        with open(os.path.join(dpath, fname), "w", encoding="utf-8") as f:
            f.write(report_md)

    # 保存缓存
    cache_dir = os.path.join(get_cache_dir(), "sixteen_period")
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "latest_summary.json"), "w", encoding="utf-8") as f:
        json.dump(analysis_res, f, ensure_ascii=False, indent=2)

    # Excel 同款 16 窗开奖矩阵（xlsx/md/json）
    try:
        from backend.modules.sixteen.excel_window_table import run_excel_window_from_draws
        ew = run_excel_window_from_draws(draws, target_period=target_period, persist=True, analysis_res=analysis_res)
        analysis_res["excel_window_export"] = (ew or {}).get("export_paths") or {}
        if verbose and ew.get("status") == "ok":
            oh = ew.get("one_head") or {}
            print(
                f"  📑 Excel16窗已导出 | 窗口 {ew.get('window_label')} | "
                f"1头(10-19) 合计{oh.get('countifs_total')} "
                f"连冷{oh.get('cold_streak_from_latest')} "
                f"偏冷≤1连续{oh.get('soft_cold_streak_le1')}"
            )
            for k, p in (ew.get("export_paths") or {}).items():
                print(f"     · {k}: {p}")
    except Exception as e:
        if verbose:
            print(f"  [警告] Excel16窗导出失败: {e}")

    # 每日维度看板流水（可追溯）
    try:
        board = analysis_res.get("bucket_dimension_board") or {}
        brief = analysis_res.get("daily_ops_brief") or {}
        ledger_row = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "latest_period": analysis_res.get("latest_period"),
            "target_period": analysis_res.get("target_period"),
            "scoring_version": brief.get("scoring_version"),
            "points_matched": bool((brief.get("points") or {}).get("matched")),
            "points_applied": bool((brief.get("points") or {}).get("points_applied")),
            "tip3": brief.get("tip3"),
            "top5": brief.get("top5"),
            "top12": brief.get("top12"),
            "freq3": (board.get("freq3") or {}).get("count"),
            "freq3_avg21": (board.get("freq3") or {}).get("avg_last21"),
            "freq4_edge": (board.get("freq4_edge_cohort") or {}).get("nums"),
            "freq4_edge_n": (board.get("freq4_edge_cohort") or {}).get("count"),
            "settled_audit": board.get("settled_audit"),
            "verdict": board.get("verdict"),
            "pool_sizes": board.get("pool_sizes") or analysis_res.get("distribution_counts"),
        }
        ledger_path = os.path.join(cache_dir, "dimension_ledger.jsonl")
        # 同目标期覆盖：先读尾部去重再追加
        prev_lines = []
        if os.path.exists(ledger_path):
            with open(ledger_path, "r", encoding="utf-8") as lf:
                prev_lines = [ln for ln in lf if ln.strip()]
            filtered = []
            for ln in prev_lines:
                try:
                    obj = json.loads(ln)
                    if int(obj.get("target_period") or 0) == int(target_period):
                        continue
                except Exception:
                    pass
                filtered.append(ln if ln.endswith("\n") else ln + "\n")
            prev_lines = filtered
        with open(ledger_path, "w", encoding="utf-8") as lf:
            for ln in prev_lines:
                lf.write(ln if ln.endswith("\n") else ln + "\n")
            lf.write(json.dumps(ledger_row, ensure_ascii=False) + "\n")
    except Exception as e:
        if verbose:
            print(f"  [警告] 维度流水写入失败: {e}")

    # 2.5 触发「Excel 同款新方法」全景动力学引擎与高保真报表生成
    folk_res = {}
    folk_prev_res = {}
    try:
        from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine
        from backend.modules.sixteen.folk_excel_builder import FolkExcelBuilder

        folk_engine = FolkSixteenEngine(history_draws=draws)
        folk_res = folk_engine.analyze_window(target_period=target_period)
        folk_txt, folk_latest_txt = folk_engine.save_plain_text_summary(folk_res)

        folk_builder = FolkExcelBuilder()
        folk_xlsx = folk_builder.export_excel(folk_res)

        # 对上一期进行实开对账复盘并生成红框红底 Excel
        prev_period = latest_draw["period"]
        folk_prev_res = folk_engine.analyze_window(target_period=prev_period)
        folk_prev_xlsx = os.path.join(get_reports_dir(), f"sixteen_folk_review_{prev_period}.xlsx")
        folk_builder.export_excel(folk_prev_res, output_xlsx_path=folk_prev_xlsx)

        if verbose:
            print(f"  📑 【新方法】同款 Excel 已生成: {folk_xlsx}")
            print(f"  📋 【新方法】微信分桶已导出: {folk_txt}")
            print(f"  🔍 【新方法】上一期实战复盘已生成: {folk_prev_xlsx}")
    except Exception as e:
        if verbose:
            print(f"  [警告] 新方法引擎执行失败: {e}")

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

        # ── 重点展现：Excel 同款「新方法」六维黄金实战选号看板 ──
        if folk_res and "picks" in folk_res:
            fp = folk_res["picks"]
            g20_str = " ".join(f"{x:02d}" for x in fp["grand_20"])
            e12_str = " ".join(f"{x:02d}" for x in fp["elite_12"])
            g5_str = " ".join(f"{x:02d}" for x in fp["golden_5"])
            g3_str = " ".join(f"{x:02d}" for x in fp["golden_3"])
            pairs_str = " | ".join(f"[{p[0]:02d}-{p[1]:02d}]" for p in fp["top_pairs"])

            print(f"\n{C_GREEN}┌─── [2] ⭐ 16期窗口新方法 (Excel 同款图) 六维黄金选号实操部 ─────{C_RESET}")
            print(f"│  🎯 【20 码大底】(高保真黄底推荐池): {C_BOLD}{C_YELLOW}{g20_str}{C_RESET}")
            print(f"│  🚀 【12 码精选】(主升浪核心攻击梯队): {C_BOLD}{C_CYAN}{e12_str}{C_RESET}")
            print(f"│  👑 【黄金 5 胆】(金银铜铁钻稳健核): {C_BOLD}{C_GREEN}{g5_str}{C_RESET}")
            print(f"│  ⚡ 【最优 3 胆】(极高胜率突破矛头): {C_BOLD}{C_RED}{g3_str}{C_RESET}")
            print(f"│  💎 【选2搭档】: {pairs_str}")
            print(f"│  📌 动力学结构: 出窗抗跌码 5 码 + 剩余冲刺码 15 码 | 012路平衡对冲")
            print(f"{C_GREEN}└{THIN}{C_RESET}")

        # ── 重点展现：16 期滑动窗口开奖位置与号码特征深度解剖 ──
        try:
            from backend.modules.sixteen.sixteen_deep_inspector import SixteenDeepInspector
            deep_insp = SixteenDeepInspector(history_draws=draws)
            deep_summary = deep_insp.generate_plain_analysis_summary(target_period)
            print(f"\n{deep_summary}\n")
        except Exception as e:
            if verbose:
                print(f"  [警告] 16窗深度解剖输出失败: {e}")

        # ── 上一期实战对账决算 ──
        if folk_prev_res and "hit_audit" in folk_prev_res:
            prev_audit = folk_prev_res["hit_audit"]
            prev_p = prev_period
            print(f"\n{C_CYAN}┌─── [3] 昨夜第 {prev_p} 期新方法实开对账总决算 ─────────────────────{C_RESET}")
            print(f"│  昨日实开: {' '.join(f'{x:02d}' for x in prev_audit['actual_draw'])}")
            print(f"│  大底20码: 命中 {C_BOLD}{C_YELLOW}{prev_audit['grand_20_hit_count']}{C_RESET} / 20 码 -> 命中号码: {' '.join(f'{x:02d}' for x in prev_audit['grand_20_hits'])}")
            print(f"│  精选12码: 命中 {C_BOLD}{C_CYAN}{prev_audit['elite_12_hit_count']}{C_RESET} / 12 码 -> 命中号码: {' '.join(f'{x:02d}' for x in prev_audit['elite_12_hits'])}")
            print(f"│  黄金 5胆: 命中 {C_BOLD}{C_GREEN}{prev_audit['golden_5_hit_count']}{C_RESET} / 5 码  -> 命中号码: {' '.join(f'{x:02d}' for x in prev_audit['golden_5_hits'])}")
            print(f"│  最优 3胆: 命中 {C_BOLD}{C_RED}{prev_audit['golden_3_hit_count']}{C_RESET} / 3 码  -> 命中号码: {' '.join(f'{x:02d}' for x in prev_audit['golden_3_hits'])}")
            print(f"{C_CYAN}└{THIN}{C_RESET}")

        stats = review_res["stats"]
        print(f"\n{C_MAGENTA}┌─── [4] 近 {stats['n_periods']} 期 Walk-Forward 滚动样本外对账指标 ────────────{C_RESET}")
        print(f"│  核心金胆命中率: {C_YELLOW}{stats['gold_hit_rate']}%{C_RESET} (Lift: {stats['gold_lift']}x vs 基线 25.0%)")
        print(f"│  次席银胆命中率: {stats['silver_hit_rate']}% (Lift: {stats['silver_lift']}x)")
        print(f"│  中热 5 码均期命中: {C_GREEN}{stats['top5_avg_hits']} 码/期{C_RESET}")
        print(f"│  Top 1 组合中2率: {C_CYAN}{stats['top1_both_rate']}%{C_RESET}")
        print(f"│  Top 1 至少中1率: {stats['top1_one_rate']}%")
        print(f"│  中热号池平均单码命中: {stats['med_pool_hit_rate']}%")
        print(f"{C_MAGENTA}└{THIN}{C_RESET}")

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
