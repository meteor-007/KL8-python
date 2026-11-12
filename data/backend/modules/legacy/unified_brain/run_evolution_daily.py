#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_evolution_daily.py — 快乐8 统一主脑真自进化与跨模块元学习每日执行器
========================================================================
【大白话控制台输出 · 操盘手实战自进化看板】：
  1. 跨模块 0/1 准入白名单与门禁自进化 (MetaEvolutionEngine)；
  2. 统一主脑物理参数 (高斯核宽 σ、时序衰减 λ) 真实反向残差校准与 90 条口诀赛马 (UnifiedBrainEvolutionEngine)；
  3. 全程遵循老派量化操盘手大白话规范。

用法:
  python -m backend.modules.legacy.unified_brain.run_evolution_daily        # 默认 30 期回测样本外对账与自进化
  python -m backend.modules.legacy.unified_brain.run_evolution_daily 30     # 指定 30 期
  python -m backend.modules.legacy.unified_brain.run_evolution_daily 5      # 快速 5 期
"""
import os
import sys
import argparse

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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.evolution_engine import MetaEvolutionEngine, print_evolution_table
from backend.core.unified_brain.evolution_engine import UnifiedBrainEvolutionEngine


def print_unified_brain_evolution_card(res: dict):
    """打印统一主脑老派量化操盘手大白话自进化看板"""
    rule_stats = res.get("rule_stats", {})
    old_p = res.get("old_params", {})
    new_p = res.get("new_params", {})

    print("\n" + "=" * 80)
    print(f"  🧠 统一主脑物理参数反向校准完成 (Generation {res.get('generation')})")
    print("  🧬 快乐8 统一主脑真自进化引擎 (True Residual Self-Evolution Engine)")
    print("=" * 80)
    print(f"  🎯 目标期号: {res.get('target_period')} | 自进化代数: Generation {res.get('generation')}")
    print(f"  ⏱️ 标定时间: {res.get('calibrated_at')} | 架构: 统一状态空间主脑 (纯物理态无加权)")
    print("-" * 80)
    print(f"  📉 历史对账 Focal Loss 残差损失: {res.get('focal_loss')}")
    print(f"  🌌 空间高斯核宽 σ (看开奖扎堆还是分散): {old_p.get('sigma', 2.50):.2f} ➔ {new_p.get('sigma', res.get('sigma')):.2f}")
    print(f"  ⏱️ 时序衰减率 λ (看昨天的号灵不灵): {old_p.get('lambda_decay', 0.95):.2f} ➔ {new_p.get('lambda_decay', res.get('lambda_decay')):.2f}")
    print("  📜 90条口诀规则赛马 (优胜劣汰赛马制):")
    print(f"     · 🟢 黄金激活态 (晋升 1.25x 放大): {rule_stats.get('promoted_count', 0)} 条")
    if res.get("promoted_rules"):
        print(f"       (明星口诀: {', '.join('#' + str(x) for x in res['promoted_rules'][:6])})")
    print(f"     · 🟡 达标稳定态 (基准 1.00x 表决): {rule_stats.get('active_count', 0)} 条")
    print(f"     · 🟠 观察降权态 (降权 0.60x 观察): {rule_stats.get('demoted_count', 0)} 条")
    print(f"     · 🔴 静音淘汰态 (一票静音 0.00x): {rule_stats.get('muted_count', 0)} 条")
    if res.get("muted_rules"):
        print(f"       (冷宫口诀: {', '.join('#' + str(x) for x in res['muted_rules'][:4])})")
    print("-" * 80)
    print("  💡 操盘手大白话自进化因果清单:")
    for r in res.get("rationales", []):
        print(f"    · {r}")
    print("-" * 80)
    print("  💾 进化资产落盘:")
    print("    · 参数状态: backend/config/unified_brain_params.json")
    print("    · 统一账本: storage/evolution/unified_evolution_ledger.json")
    print("    · 最新研报: outputs/reports/evolution_report_latest.md")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="快乐8 统一主脑每日自进化执行器")
    parser.add_argument("n_review", nargs="?", default="30", help="样本外对账期数 (默认 30)")
    args = parser.parse_args()

    n = int(args.n_review) if args.n_review.isdigit() else 30

    # 1. 执行 0/1 准入白名单与门禁自进化 (Legacy Meta Gatekeeper)
    engine = MetaEvolutionEngine(_PROJ_DIR)
    rec = engine.run_evolution(n_review=n)
    print_evolution_table(rec)

    # 2. 执行统一决策主脑真实反向残差自进化 (Focal Loss + σ/λ 物理自适应 + 90条口诀赛马)
    target_period = rec.get("target_period", 2026234)
    calib_engine = UnifiedBrainEvolutionEngine(_PROJ_DIR)
    calib_res = calib_engine.run_nightly_calibration(target_period=target_period, window=n)

    # 3. 操盘手大白话看板输出
    print_unified_brain_evolution_card(calib_res)


if __name__ == "__main__":
    main()
