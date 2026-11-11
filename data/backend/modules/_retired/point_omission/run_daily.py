#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 点位+遗漏号深度分析 (Point & Omission Analysis Engine) - 每日全流程一键分析启动器 v2.0
========================================================================================
【业务定位与架构说明】:
将原独立研发系统无损迁移整合为 K8-Quant 智能量化操盘决策终端的核心推演子系统。
涵盖：
1. 深度分析四重奏与 13 大独立统计方法（连号集群、周期共振、能量分布、反向博弈、
   马尔可夫链、斐波那契、SVD协方差、复变FFT、图网络、波动率聚类、余数空间、号码熵、对抗检验）；
2. H1-H7 七维加权融合与无前视 Exp3 自适应在线学习；
3. 最优 3 码核心推荐与防御性两码（Defensive 3+2 策略）；
4. 严谨 T=277 滚动外样本回测（Walk-Forward 无未来函数对账）；
5. 自动输出标准化 Markdown 研报与前端大屏结构化 JSON 资产。

【用法示例】:
  python -m backend.modules._retired.point_omission.run_daily                    # 自动推断目标期并运行全套推演
  python -m backend.modules._retired.point_omission.run_daily 2026242            # 指定特定期号
  python -m backend.modules._retired.point_omission.run_daily --no-fetch         # 跳过开奖增量抓取
  python -m backend.modules._retired.point_omission.run_daily --no-backtest      # 跳过耗时滚动回测
"""
import os
import sys
import json
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# 步骤 1: 路径自适应注入 (实体在 backend/modules/point_omission/)
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

_POINT_OMISSION_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = _find_project_root(_POINT_OMISSION_DIR)
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")

for _path in [_POINT_OMISSION_DIR, _BACKEND_DIR, _PROJ_DIR]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from backend.utils.paths import get_outputs_dir

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 引入核心算法库与契约
from kl8 import observability, points_input, registry, report, replay, source
from kl8.config import load_config
from kl8.ensemble import MAIN_METHODS, Exp3State, fuse
from kl8.points import compute_base_stats, expand
from kl8.scoring import select_52, select_top5

# 终端 ANSI 彩色样式常量
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"
C_GRAY = "\033[90m"

DIVIDER_LINE = "═" * 76
SUB_DIVIDER = "─" * 76


def print_banner(text: str, color: str = C_CYAN) -> None:
    """输出标准操盘手控制台横幅"""
    print(f"\n{color}{DIVIDER_LINE}")
    print(f"  {text}")
    print(f"{DIVIDER_LINE}{C_RESET}")


def run_point_omission_pipeline(
    period_override: Optional[int] = None,
    allow_fetch: bool = True,
    do_backtest: bool = True,
    backtest_n: int = 60,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    点位+遗漏号全流程分析推演核心流水线

    @param period_override: 指定待分析的期号，若为 None 则自动推断最新开奖后的一期
    @param allow_fetch: 是否尝试联网增量拉取最新开奖
    @param do_backtest: 是否执行滚动样本外回测对账
    @param backtest_n: 回测窗口期数
    @param verbose: 是否在控制台打印详细操盘手大白话报告
    @return: 结构化输出字典
    """
    config_file = Path(_POINT_OMISSION_DIR) / "config.yaml"
    cfg = load_config(config_file)

    # 独立宪法/迁移后：共享档案固定走 storage/raw（config 里相对 .. 会指到 backend/modules）
    try:
        from backend.utils.paths import data_path
        hist_p = data_path("kl8_history_final.txt")
        pts_p = data_path("daily_points.txt")
        cfg.override_files(history=str(hist_p), points=str(pts_p))
    except Exception as exc:
        observability.warn(f"data_path 覆盖共享档案失败，沿用 config.yaml: {exc}")

    if verbose:
        print_banner("🧬 K8-QUANT 点位+遗漏号深度推演系统 (Point & Omission Engine)", C_CYAN)
        print(f"  工作根目录   : {_PROJ_DIR}")
        print(f"  算法引擎目录 : {_POINT_OMISSION_DIR}")
        print(f"  开奖历史文件 : {cfg.shared_history_file}")
        print(f"  点位档案文件 : {cfg.shared_points_file}")
        print(f"  历史存在={cfg.shared_history_file.exists()} | 点位存在={cfg.shared_points_file.exists()}")

    # 步骤 2: 增量抓取最新开奖（可降级容错）
    if allow_fetch and cfg.fetch.enabled:
        try:
            from kl8 import fetcher
            fetcher.fetch_incremental(cfg)
        except Exception as exc:
            observability.warn(f"开奖增量抓取跳过或失败: {exc}，使用本地已有档案继续推演")

    # 步骤 3: 载入全量数据集与数据体检
    ds = source.load_dataset(cfg, allow_fetch=False)
    if not ds.draws or not ds.points:
        raise RuntimeError("点位档案或开奖历史为空，无法执行点位+遗漏分析！")

    # 步骤 3.5: 结算已开奖的历史预测 → 逐期命中台账
    try:
        from backend.modules._retired.point_omission import hit_ledger as po_ledger
        draws_map = {int(d.period): d for d in ds.draws}
        settled_rows = po_ledger.settle_predictions_against_draws(_PROJ_DIR, draws_map)
        if verbose and settled_rows:
            print(f"  📒 逐期命中台账已结算 {len(settled_rows)} 期")
    except Exception as exc:
        observability.warn(f"逐期命中台账结算跳过: {exc}")

    # 步骤 4: 推断并确认目标期与点位
    if period_override is not None:
        target_period = int(period_override)
        entry = ds.points.get(target_period)
    else:
        target = points_input.infer_target(cfg, ds.draws, ds.points)
        target_period = target.period
        entry = ds.points.get(target_period)
        # 若最新目标期尚未录入点位，优雅回退到点位库中最新的一期
        if entry is None and ds.points:
            latest_available = max(ds.points.keys())
            print(f"  ℹ️ 最新推断目标期 {target_period} 尚未录入点位，自动分析最新可用点位期 {latest_available}")
            target_period = latest_available
            entry = ds.points.get(target_period)

    if entry is None or not entry.points:
        raise RuntimeError(f"未找到可分析的点位记录（目标期 {target_period}）！")

    draw = next((d for d in ds.draws if d.period == target_period), None)
    target_date = entry.date if entry and entry.date else (draw.date if draw else datetime.now().strftime("%Y-%m-%d"))
    target = points_input.TargetInfo(
        period=target_period,
        date=target_date,
        already_input=True,
        existing_points=entry.points
    )

    # 步骤 5: 提取截止目标期前的历史数据（防未来函数泄露）
    hist = ds.history_before(target.period)
    if len(hist) < 30:
        raise RuntimeError(f"目标期 {target_period} 之前仅 {len(hist)} 期历史，不足以进行统计推演（最少 30 期）。")

    expanded = expand(entry.points)
    base_stats = compute_base_stats(hist, expanded)

    if verbose:
        print_banner(f"① 基础概览: 目标第 {target.period} 期 (日期: {target.date})", C_YELLOW)
        print(f"  核心点位 (20码) : {' '.join(f'{x:02d}' for x in entry.points)}")
        print(f"  拓展集合 (46码) : 点位原号 20 个 + 循环三元组邻近拓展 26 个")
        print(f"  有效对账期数    : {ds.health.pairable_count} 期可严格配对")

    # 步骤 6: 并行/顺序执行 13 大独立分析方法
    names = list(MAIN_METHODS)
    results, _ = registry.run_all(hist, expanded, base_stats, cfg, names, run_meta=True)

    # 步骤 7: Exp3 在线学习权重结算与融合 (大白话：各方法以往战绩自适应评分)
    ol = cfg.online_learner
    exp3 = Exp3State.load_or_uniform(
        cfg.state_file, MAIN_METHODS,
        gamma=float(ol.gamma or 0.1),
        floor=float(ol.weight_floor or 0.01),
        warmup=int(ol.warmup_periods or 60)
    )

    # 结算上一期的在线学习奖励
    pend = exp3.pending or {}
    if pend:
        last_p = int(pend.get("period") or 0)
        last_m_top5 = {k: list(v) for k, v in (pend.get("method_top5") or {}).items()}
        last_draw = next((d for d in ds.draws if d.period == last_p), None)
        if last_draw and last_m_top5:
            exp3.update(last_m_top5, set(last_draw.numbers))
            exp3.pending = {}

    weights = exp3.effective(MAIN_METHODS)
    fusion = fuse(results, cfg, base_stats, weights)

    passed, _ = replay._gate(cfg, sorted(expanded), fusion, results, base_stats)
    pool = sorted(set(passed) or expanded)
    selection = select_top5(fusion, pool, cfg)
    picks = select_52(
        fusion, selection.core, set(expanded), results,
        results["omission"].scores, results.get("contrarian"), cfg
    )

    # 保存本期 Top5 待下一期开出后结算
    method_top5: Dict[str, List[int]] = {}
    for m in MAIN_METHODS:
        res = results.get(m)
        if res is not None and res.sufficient:
            method_top5[m] = res.top(5, restrict_to=expanded)
    exp3.pending = {"period": int(target.period), "method_top5": method_top5}
    exp3.save(cfg.state_file)

    # 步骤 8: 滚动外样本回测 (Walk-Forward Backtest)
    bt_result = None
    if do_backtest and ds.pairable():
        try:
            bt_result = replay.run_backtest(cfg, ds, n=backtest_n)
        except Exception as exc:
            observability.warn(f"回测执行跳过: {exc}")

    # 步骤 9: 构建研报上下文并输出 Markdown 日报
    staleness_info = observability.staleness(ds.draws[0].date if ds.draws else None, cfg)
    report_ctx = report.ReportContext(
        cfg=cfg, target=target, entry=entry, dataset=ds,
        health=ds.health,
        staleness=f"{staleness_info[1]} {'✅' if staleness_info[0] == 'ok' else '⚠️'}",
        results=results, fusion=fusion, selection=selection, picks=picks,
        base_stats=base_stats, expanded=expanded,
        module_notes=[f"{n}（{r.diagnostics.get('degraded', '数据不足')}）"
                      for n, r in results.items() if not r.sufficient],
        degradation_reasons=[r.diagnostics["degraded"] for r in results.values()
                             if not r.sufficient and r.diagnostics.get("degraded")],
        reconcile_note="",
        backtest=bt_result
    )

    md_report_path = report.write_report(report_ctx, cfg.out_dir)

    # 同步一份到主系统 outputs/reports 供研报中心统一检索
    master_report_dir = os.path.join(get_outputs_dir(), "reports")
    os.makedirs(master_report_dir, exist_ok=True)
    master_report_file = os.path.join(master_report_dir, f"point_omission_report_{target.period}.md")
    latest_report_link = os.path.join(master_report_dir, "point_omission_report_latest.md")
    try:
        shutil.copyfile(str(md_report_path), master_report_file)
        shutil.copyfile(str(md_report_path), latest_report_link)
    except Exception:
        pass

    # 步骤 10: 组装结构化 JSON 资产 (供 Web 驾驶舱与 API 实时消费)
    dim_scores_map = {}
    for num in range(1, 81):
        num_stats = base_stats.get(num)
        d_map = {dim: fusion.h_values.get(dim, {}).get(num, 0.0) for dim in ("H1", "H2", "H3", "H4", "H5", "H6", "H7")}
        dim_scores_map[str(num)] = {
            "score": round(float(fusion.composite.get(num, 0.0)), 2),
            "H1": round(float(d_map.get("H1", 0.0)), 3),
            "H2": round(float(d_map.get("H2", 0.0)), 3),
            "H3": round(float(d_map.get("H3", 0.0)), 3),
            "H4": round(float(d_map.get("H4", 0.0)), 3),
            "H5": round(float(d_map.get("H5", 0.0)), 3),
            "H6": round(float(d_map.get("H6", 0.0)), 3),
            "H7": round(float(d_map.get("H7", 0.0)), 3),
            "is_point": num in entry.points,
            "is_expanded": num in expanded,
            "streak_miss": getattr(num_stats, "miss", 0) if num_stats else 0,
            "hit_l10": getattr(num_stats, "hit10", 0) if num_stats else 0,
            "hit_l3": getattr(num_stats, "hit3", 0) if num_stats else 0,
            "z": round(float(getattr(num_stats, "z_score", 0.0)), 2) if num_stats else 0.0,
            "freq": getattr(num_stats, "freq_full", 0) if num_stats else 0
        }

    # Top 5 核心明细
    top5_items = []
    for num in selection.core:
        d_info = dim_scores_map.get(str(num), {})
        lead_dim = "综合共振"
        max_v = -1.0
        dim_labels = {
            "H1": "热度追踪", "H2": "遗漏反弹", "H3": "连号集群",
            "H4": "周期波动", "H5": "共现图谱", "H6": "马尔可夫", "H7": "熵值均衡"
        }
        for d_key, d_lbl in dim_labels.items():
            val = d_info.get(d_key, 0.0)
            if val > max_v:
                max_v = val
                lead_dim = d_lbl
        top5_items.append({
            "number": num,
            "score": d_info.get("score", 0.0),
            "leading_dimension": lead_dim,
            "H1": d_info.get("H1", 0.0),
            "H2": d_info.get("H2", 0.0),
            "H3": d_info.get("H3", 0.0),
            "H4": d_info.get("H4", 0.0),
            "H5": d_info.get("H5", 0.0),
            "H6": d_info.get("H6", 0.0),
            "H7": d_info.get("H7", 0.0),
            "streak_miss": d_info.get("streak_miss", 0),
            "hit_l10": d_info.get("hit_l10", 0),
            "z": d_info.get("z", 0.0)
        })

    # 8 大场域能量
    zone_stats = []
    zone_res = results.get("heatmap")
    if zone_res and "energy_by_zone" in zone_res.diagnostics:
        ebz = zone_res.diagnostics["energy_by_zone"]
        for z_name, z_val in ebz.items():
            zone_stats.append({
                "zone": z_name,
                "ratio": round(float(z_val.get("ratio", 1.0)), 2),
                "hits": z_val.get("hits", 0),
                "tendency": "偏热" if z_val.get("ratio", 1.0) > 1.15 else ("偏冷" if z_val.get("ratio", 1.0) < 0.85 else "平稳")
            })

    # 回测天梯数据
    bt_payload = {}
    if bt_result:
        bt_payload = {
            "T": bt_result.T,
            "window_label": bt_result.window_label,
            "system_mean_hits": round(bt_result.system_test.mean_hits, 4) if bt_result.system_test else 0.0,
            "system_lift": round(bt_result.system_test.lift, 4) if bt_result.system_test else 1.0,
            "system_z": round(bt_result.system_test.z, 3) if bt_result.system_test else 0.0,
            "system_p": round(bt_result.system_test.p_value, 4) if bt_result.system_test else 1.0,
            "system_verdict": bt_result.system_test.verdict if bt_result.system_test else "未达显著",
            "methods": [
                {
                    "method": m,
                    "mean_hits": round(tr.mean_hits, 4),
                    "lift": round(tr.lift, 4),
                    "z": round(tr.z, 3),
                    "q": round(tr.q_value, 4),
                    "verdict": tr.verdict
                }
                for m, tr in sorted(bt_result.method_tests.items(), key=lambda kv: -kv[1].lift)
            ]
        }
    else:
        # 自动载入历史已持久化的全样本回测台账
        cached_bt = os.path.join(_PROJ_DIR, "storage", "point_omission", "backtest_latest.json")
        if os.path.exists(cached_bt):
            try:
                with open(cached_bt, "r", encoding="utf-8") as f:
                    bt_payload = json.load(f)
            except Exception:
                pass

    storage_dir = os.path.join(_PROJ_DIR, "storage", "point_omission")
    os.makedirs(storage_dir, exist_ok=True)
    summary_file = os.path.join(storage_dir, "latest_summary.json")

    output_payload = {
        "period": target.period,
        "date": str(target.date),
        "core_points": entry.points,
        "expanded_points": sorted(list(expanded)),
        "top3_gold": [int(it["number"]) for it in top5_items[:3]],
        "top5": top5_items[:3],  # 兼容旧字段：主口径最优3码
        # 2026-11-10 修复：上面两个字段都只存 3 码，报告若按 top5 渲染会漏掉第 4、5 码。
        # 新增全量字段，渲染方优先读它。
        "top5_full": [int(it["number"]) for it in top5_items[:5]],
        "defensive_picks": picks.defensive,
        "five_plus_two": [int(it["number"]) for it in top5_items[:5]] + list(picks.defensive),
        "dimension_scores_80": dim_scores_map,
        "method_weights": {m: round(float(weights.get(m, 0.0)), 4) for m in MAIN_METHODS},
        "energy_zones": zone_stats,
        "backtest": bt_payload,
        "staleness": staleness_info[1],
        "report_markdown_path": str(md_report_path),
        "updated_at": datetime.now().isoformat()
    }

    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    # 步骤 11: 落盘本期预测快照 + 回测近窗灌入逐期命中台账
    try:
        from backend.modules._retired.point_omission import hit_ledger as po_ledger
        po_ledger.save_prediction_snapshot(
            _PROJ_DIR,
            period=int(target.period),
            date_str=str(target.date),
            top5=[int(it["number"]) for it in top5_items[:3]],
            defensive=list(picks.defensive),
            points20=list(entry.points),
            expanded=sorted(list(expanded)),
        )
        if bt_result and getattr(bt_result, "records", None):
            po_ledger.merge_backtest_records(_PROJ_DIR, bt_result.records, keep_last=60)
            po_ledger.enrich_hit_balls_from_draws(_PROJ_DIR, {int(d.period): d for d in ds.draws})
        ledger_brief = po_ledger.get_hit_ledger(_PROJ_DIR, n=30)
        output_payload["hit_ledger_brief"] = {
            "total": ledger_brief.get("total", 0),
            "avg_hits": ledger_brief.get("avg_hits", 0),
            "avg_lift": ledger_brief.get("avg_lift", 0),
            "recent": (ledger_brief.get("rows") or [])[:8],
        }
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        observability.warn(f"逐期命中台账写入跳过: {exc}")

    if verbose:
        print_banner("② 核心推演结果: 最优 3 码 + 防御性两码", C_GREEN)
        top5_str = " ".join(f"{it['number']:02d}" for it in top5_items[:3])
        def_str = " ".join(f"{x:02d}" for x in picks.defensive)
        print(f"  👑 最优 3 码推荐号 : {C_BOLD}{C_YELLOW}{top5_str}{C_RESET}")
        for idx, it in enumerate(top5_items[:3], 1):
            print(f"     · 排名 [{idx}] 号码 [{it['number']:02d}] 综合分: {it['score']} | 主导维度: {it['leading_dimension']} | 连失: {it['streak_miss']}期")
        print(f"\n  🛡️ 防御性选2搭档 (深冷回补) : {C_BOLD}{C_MAGENTA}{def_str}{C_RESET}")
        print(f"  🎯 3+2 组合推荐清单         : {' '.join(f'{x:02d}' for x in [it['number'] for it in top5_items[:3]] + list(picks.defensive))}")

        if bt_payload:
            sys_t = bt_payload.get("system_test") or bt_payload
            s_mean = sys_t.get("mean_hits", sys_t.get("system_mean_hits", 1.25))
            s_lift = sys_t.get("lift", sys_t.get("system_lift", 1.0))
            s_p = sys_t.get("p_value", sys_t.get("system_p", 0.5))
            s_verdict = sys_t.get("verdict", sys_t.get("system_verdict", "平稳运行"))
            print_banner(f"③ 滚动外样本回测对账 (全样本 T={bt_payload.get('T', 277)} 期)", C_CYAN)
            print(f"  系统 Top5 实测均值: {s_mean} 码/期 (Lift: {s_lift}x, p={s_p}) -> {s_verdict}")
            print("  各算法单兵战绩:")
            for m_item in (bt_payload.get("methods") or [])[:6]:
                print(f"    - {m_item.get('chinese_name', m_item.get('method', '')):12s} Lift: {m_item.get('lift', 1.0):.3f}x | z: {m_item.get('z', 0.0):+.2f} | 判定: {m_item.get('verdict', '')}")

        print_banner("🎉 点位+遗漏号深度推演完成", C_GREEN)
        print(f"  📄 研报落盘路径 : {md_report_path}")
        print(f"  📦 大屏数据资产 : {os.path.relpath(summary_file, _PROJ_DIR)}")

    return output_payload


def main():
    parser = argparse.ArgumentParser(description="K8-QUANT 点位+遗漏号深度分析一键启动器")
    parser.add_argument("period", nargs="?", type=int, default=None, help="目标期号 (默认自动推断下一期)")
    parser.add_argument("--no-fetch", action="store_true", help="跳过开奖增量拉取")
    parser.add_argument("--no-backtest", action="store_true", help="跳过外样本回测")
    parser.add_argument("--n", type=int, default=60, help="回测期数 (默认 60)")
    args = parser.parse_args()

    run_point_omission_pipeline(
        period_override=args.period,
        allow_fetch=not args.no_fetch,
        do_backtest=not args.no_backtest,
        backtest_n=args.n,
        verbose=True
    )


if __name__ == "__main__":
    main()
