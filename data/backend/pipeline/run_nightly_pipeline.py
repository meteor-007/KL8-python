#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_nightly_pipeline.py — 开奖后自动流水线（非点位预测模块）
================================================================
最新契约 (v6 / 2026-09):
  1. 同步最新开奖数据
  2. **自动**跑所有「不依赖每日点位」的预测模块（16期 / 经典开奖侧 / 高维AI）
  3. 按最优策略做轻量汇总（aggregation，主推口径=sixteen）
  4. **跳过**依赖点位/三高手工录入的模块，等人工更新后再手动执行

需点位（本流水线不自动跑）:
  - 数据源1×2 深层关联、未开点位反弹、点位与遗漏、三高×点位、空间点位(已退役)
  - Hidden Energy / 全量日报研报中强依赖点位的段落（待点位录入后手动全流程）
"""
import os
import sys
import time
import json
import traceback
from datetime import datetime

# 路径自省与环境对齐 (Dual-Root Bootstrap)
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_CURRENT_DIR))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from backend.utils.paths import get_outputs_dir, find_module_script
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pipeline.run_full_pipeline import (
    task0_env_check, task00_validate, task11_fetch, task12_hot_numbers, task13_15_sync,
    task36_formula_jingle, task39_gold_pick2,
    task394_sixteen_period, task395_aggregation, task396_prime_tail, task397_psychological_game,
    task5_verify, task6_cleanup, run_py,
)


# ─── 模块分层：自动(仅开奖) vs 手动(需点位/手工) ───
AUTO_DRAW_ONLY_LABELS = [
    "16期中热 (主推)",
    "顺口溜",
    "定胆选2 / 极简选2",
    "心理博弈",
    "尾数/质合/熵",
    "遗传算法",
    "线性代数",
    "DTW",
    "Transformer",
    "矩阵轮廓",
    "TDA",
    "子系统汇总陈列 (主推=16期)",
]

MANUAL_POINTS_LABELS = [
    "数据源1×2 深层关联",
    "未开点位高压反弹",
    "点位与遗漏",
    "三高×点位",
    "Hidden Energy / 点位强依赖研报段",
]


def _safe_step(label: str, fn):
    """单步容错：失败不中断整条流水线。"""
    try:
        print(f"\n  ▶ {label}")
        fn()
        print(f"  ✅ {label} · 完成")
        return {"label": label, "status": "ok"}
    except Exception as e:
        print(f"  ⚠️ {label} · 跳过: {e}")
        traceback.print_exc()
        return {"label": label, "status": "error", "error": str(e)}


def sync_nightly_static_snapshots(proj_dir: str) -> dict:
    """刷新前端降级静态快照（API 优先 + 静态兜底）。"""
    import shutil
    static_dir = os.path.join(proj_dir, "frontend", "static")
    os.makedirs(static_dir, exist_ok=True)
    results = {}

    try:
        from backend.api.data_service import QuantDataService
        ds = QuantDataService(proj_dir)
        hist = ds.get_evolution_history(limit=100)
        target_path = os.path.join(static_dir, "evolution_history.json")
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
        results["evolution_history.json"] = {"status": "ok", "items": len(hist)}
    except Exception as e:
        results["evolution_history.json"] = {"status": "error", "error": str(e)}

    snapshot_mappings = {
        "prime_tail_analysis.json": os.path.join(proj_dir, "storage", "stats", "prime_tail_entropy_analysis.json"),
        "psychological_game_analysis.json": os.path.join(proj_dir, "storage", "stats", "psychological_game_analysis.json"),
        "psychological_game_backtest_ledger.json": os.path.join(proj_dir, "storage", "reviews", "psychological_game_backtest_ledger.json"),
        "multi_resonance_consensus.json": os.path.join(proj_dir, "storage", "stats", "multi_resonance_consensus.json"),
        "unified_decision_latest.json": os.path.join(get_outputs_dir(), "unified_brain", "unified_decision_latest.json"),
    }

    for fname, src_path in snapshot_mappings.items():
        dst_path = os.path.join(static_dir, fname)
        try:
            if fname == "unified_decision_latest.json" and not os.path.exists(src_path):
                ub_dir = os.path.join(get_outputs_dir(), "unified_brain")
                if os.path.exists(ub_dir):
                    candidates = [f for f in os.listdir(ub_dir)
                                  if f.startswith("unified_decision_202") and f.endswith(".json")]
                    if candidates:
                        candidates.sort()
                        src_path = os.path.join(ub_dir, candidates[-1])

            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)
                results[fname] = {"status": "ok", "source": src_path}
            else:
                results[fname] = {"status": "missing_source", "source": src_path}
        except Exception as e:
            results[fname] = {"status": "error", "error": str(e)}

    return results


def _run_ai_math_models():
    """高维数学与 AI 六大模型（均只依赖开奖历史）。"""
    scripts = [
        ("遗传算法", "run_genetic_daily.py"),
        ("线性代数", "run_linear_algebra_daily.py"),
        ("DTW", "run_dtw_daily.py"),
        ("Transformer", "run_transformer_daily.py"),
        ("矩阵轮廓", "run_matrix_profile_daily.py"),
        ("TDA", "run_tda_daily.py"),
    ]
    out = []
    for label, script in scripts:
        path = find_module_script(script)

        def _runner(p=path, s=script):
            if not os.path.exists(p):
                raise FileNotFoundError(s)
            run_py(p)

        out.append(_safe_step(f"AI · {label}", _runner))
    return out


def task_unified_brain():
    """统一决策主脑：自进化反向校准 + 当期全状态空间推演。

    2026-10-21 结构修复：此函数原先被物理插入 run_nightly_pipeline 函数体中间，
    导致 run_nightly_pipeline 在打印完「[2/4]」后直接结束（隐式 return None），
    阶段 2 的全部预测模块、阶段 3 汇总、前瞻账对账、统一对账与静态快照**从未执行**。
    现移回模块级并置于调用方之前。
    """
    from backend.modules._retired.unified_brain.evolution_engine import UnifiedBrainEvolutionEngine
    from backend.modules._retired.unified_brain.unified_brain import UnifiedDecisionBrain

    evo = UnifiedBrainEvolutionEngine(_PROJ_DIR)
    draws = evo.brain.feature_layer.draws
    target_period = (draws[-1]["period"] + 1) if draws else 2026234
    calib = evo.run_nightly_calibration(target_period)

    brain = UnifiedDecisionBrain(_PROJ_DIR)
    sigma = calib.get("sigma", 2.50)
    lambda_decay = calib.get("lambda_decay", 0.95)
    rule_weights = evo.params.get("rule_weights")
    decision = brain.solve_period(
        target_period=target_period,
        sigma=sigma,
        lambda_decay=lambda_decay,
        rule_weights=rule_weights
    )
    return decision


def run_nightly_pipeline(verbose: bool = True, with_research: bool = False):
    start_t = time.time()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    auto_results = []
    skipped_manual = list(MANUAL_POINTS_LABELS)

    print("=" * 80)
    print("  🌙 K8-QUANT 开奖后自动流水线 v6 — 非点位预测模块全自动")
    print(f"  ⏰ 启动: {now_str}")
    print("  📌 策略: 同步开奖 → 自动跑开奖侧预测 → 汇总；点位类等待手工录入后再跑")
    print(f"  🔬 research 舱: {'ON (--with-research)' if with_research else 'OFF（默认跳过高维AI，减噪）'}")
    print("=" * 80)

    # ── 阶段 1: 同步开奖 ──
    print("\n" + "─" * 70)
    print("  [1/4] 📥 同步最新开奖数据")
    print("─" * 70)
    task0_env_check()
    task00_validate()
    task11_fetch()
    task12_hot_numbers()
    task13_15_sync()

    # ── 阶段 2: 自动 — 经典 + 16期 + 形态（无点位） ──
    print("\n" + "─" * 70)
    print("  [2/4] ⚡ 自动推演 · 仅开奖数据即可的预测模块")
    print("─" * 70)
    print("  将执行:")
    for lab in AUTO_DRAW_ONLY_LABELS:
        print(f"    · {lab}")

    auto_results.append(_safe_step("16期中热 (主推)", task394_sixteen_period))
    auto_results.append(_safe_step("顺口溜", task36_formula_jingle))
    auto_results.append(_safe_step("定胆选2", task39_gold_pick2))
    auto_results.append(_safe_step("心理博弈", task397_psychological_game))
    auto_results.append(_safe_step("尾数/质合/熵", task396_prime_tail))
    auto_results.append(_safe_step("统一决策主脑 (自进化+推演)", task_unified_brain))

    # ── 阶段 3: 自动 — 高维 AI（research，默认跳过）──
    print("\n" + "─" * 70)
    print("  [3/4] 📐 自动推演 · 高维数学与 AI（research 舱）")
    print("─" * 70)
    if with_research:
        auto_results.extend(_run_ai_math_models())
    else:
        print("  ⏭️  已跳过 research 舱（加 --with-research 可启用）")
        for lab, _scr in [
            ("遗传算法", ""), ("线性代数", ""), ("DTW", ""),
            ("Transformer", ""), ("矩阵轮廓", ""), ("TDA", ""),
        ]:
            print(f"    · 跳过 AI · {lab}")

    # 最优策略轻量汇总（主推口径 sixteen，非旧版票权熔炉）
    auto_results.append(_safe_step("子系统汇总陈列 (主推=16期)", task395_aggregation))

    # 前瞻账对账 + 注册表刷新 + 统一对账 settle（补齐与 full 的缺口）
    try:
        from backend.core.module_gate import ModuleGate, reconcile_module_ledger
        from core.master_reviewer import MasterReviewEngine, print_master_review_table
        print("\n  ▶ 前瞻账 reconcile + 复盘对账 + 模块注册表刷新")
        filled = reconcile_module_ledger(limit_periods=400)
        print(f"  ✅ 前瞻账新对账 {filled} 条")
        review_res = MasterReviewEngine(_PROJ_DIR).run_master_review(n_review=100)
        print_master_review_table(review_res)
        _gate = ModuleGate(_PROJ_DIR)
        _reg, _changes = _gate.refresh_from_master_ledger()
        print(f"  ✅ 注册表已刷新；变更 {len(_changes or [])} 条")
    except Exception as e:
        print(f"  ⚠️ 复盘/注册表刷新跳过: {e}")
        review_res = {}

    try:
        from backend.modules.unified_audit.run_daily import run_settle
        print("\n  ▶ 统一对账 settle")
        ua = run_settle()
        print(f"  ✅ 统一对账: {ua.get('status')} {ua.get('message') or ua.get('target_period')}")
    except Exception as e:
        print(f"  ⚠️ 统一对账 settle 跳过: {e}")

    # ── 阶段 4: 点位类明确跳过 ──
    print("\n" + "─" * 70)
    print("  [4/4] ⏸️  以下模块依赖点位/手工录入 — 本流水线不自动执行")
    print("─" * 70)
    for lab in skipped_manual:
        print(f"    ⏳ 待手动: {lab}")
    print("  👉 录入点位/三高后，请在对应驾驶舱或「一键全流程」中手动触发。")

    # 静态快照
    try:
        _snap = sync_nightly_static_snapshots(_PROJ_DIR)
        print(f"\n  💾 静态快照刷新: {list(_snap.keys())}")
    except Exception as e:
        print(f"  ⚠️ 静态快照失败: {e}")

    task6_cleanup()

    elapsed = time.time() - start_t
    ok_n = sum(1 for r in auto_results if r.get("status") == "ok")
    err_n = sum(1 for r in auto_results if r.get("status") == "error")

    print("\n" + "=" * 80)
    print(f"  ✅ 开奖后自动流水线完成 · 耗时 {elapsed:.1f}s · 成功 {ok_n} / 失败 {err_n}")
    print(f"  ⏸  点位类待手动: {len(skipped_manual)} 项")
    print("=" * 80 + "\n")

    return {
        "status": "SUCCESS",
        "finished_at": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "auto_results": auto_results,
        "skipped_manual_points": skipped_manual,
        "review_summary": review_res if isinstance(review_res, dict) else {},
        "policy": "draw_sync_then_auto_non_points_predictors",
    }


if __name__ == "__main__":
    import argparse
    _ap = argparse.ArgumentParser(description="开奖后自动流水线（非点位）")
    _ap.add_argument(
        "--with-research",
        action="store_true",
        help="跑 research 舱高维 AI（默认跳过）",
    )
    _args = _ap.parse_args()
    run_nightly_pipeline(verbose=True, with_research=_args.with_research)
