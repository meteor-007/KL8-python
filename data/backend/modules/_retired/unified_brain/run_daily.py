# -*- coding: utf-8 -*-
"""
run_unified_brain_daily.py — 快乐8 全栈统一决策主脑每日独立执行入口
====================================================================
【命令行交互与资产推演】：
  1. 支持 --target_period, --force, --sigma, --lambda_decay, --kill_size, --temperature 参数；
  2. 自动加载自进化内核最新物理参数；
  3. 纯内存调用 UnifiedDecisionBrain 进行 80 维状态空间概率解算；
  4. 导出 outputs/unified_brain/unified_decision_{period}.json 与 Markdown 战报；
  5. 以老派量化操盘手大白话在控制台打印清晰严密的层级化作战决策。
"""
import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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

from backend.core.unified_brain.unified_brain import UnifiedDecisionBrain, BRAIN_OUTPUT_DIR
from backend.core.unified_brain.loss_and_backprop import UnifiedBrainEvolutionEngine


def parse_args():
    parser = argparse.ArgumentParser(
        description="快乐8 全栈统一决策解算主脑 (老派量化操盘手实战推演中枢)"
    )
    parser.add_argument(
        "--target_period",
        type=int,
        default=None,
        help="待推演的目标期号 (例如 2026234)，默认自动推算为最新开奖+1",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新解算并覆盖已有落盘决策资产",
    )
    parser.add_argument(
        "--sigma",
        type=float,
        default=None,
        help="空间高斯核宽 σ (默认读取自进化参数，范围 1.5~4.0)",
    )
    parser.add_argument(
        "--lambda_decay",
        type=float,
        default=None,
        help="时序衰减率 λ (默认读取自进化参数，范围 0.85~0.98)",
    )
    parser.add_argument(
        "--kill_size",
        type=int,
        default=None,
        help="硬雷区防守规模 (默认读取自进化参数，通常 15 码)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="玻尔兹曼热力学温度 T (默认 1.0)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("\n" + "=" * 80)
    print("  🧬 快乐8 全栈统一决策主脑 (Unified Quantum Master Decision Brain)")
    print("  【老派量化操盘手实战推演中枢 · 彻底废除线性加权 · 纯物理状态空间解算】")
    print("=" * 80)

    # 1. 初始化自进化引擎与读取当前进化代数参数
    data_root = _PROJ_DIR
    evo_engine = UnifiedBrainEvolutionEngine(data_root)
    evo_params = evo_engine.params

    # 2. 确定目标期号
    history = evo_engine.brain.feature_layer.draws
    # 2026-10-21 P2 整改：原 `if history else 2026233` 会在空库时编造一个期号继续解算落盘。
    # 统一走 backend.utils.periods（内部取 max，升序/降序两种约定都不会错位一期）。
    from backend.utils.periods import latest_period
    latest_period_val = latest_period(history)
    target_period = args.target_period if args.target_period is not None else (latest_period_val + 1)

    # 3. 确定物理超参数 (命令行参数 > 自进化参数 > 默认兜底)
    sigma = args.sigma if args.sigma is not None else float(evo_params.get("sigma", 2.50))
    lambda_decay = args.lambda_decay if args.lambda_decay is not None else float(evo_params.get("lambda_decay", 0.95))
    kill_size = args.kill_size if args.kill_size is not None else int(evo_params.get("kill_size", 15))
    temperature = args.temperature if args.temperature is not None else float(evo_params.get("temperature", 1.00))

    json_asset_path = os.path.join(BRAIN_OUTPUT_DIR, f"unified_decision_{target_period}.json")
    report_asset_path = os.path.join(BRAIN_OUTPUT_DIR, f"unified_decision_report_{target_period}.md")

    print(f"  🎯 推演目标期号: 第 {target_period} 期 | 历史最新期: 第 {latest_period_val} 期")
    print(f"  🧬 自进化代数: Generation {evo_params.get('generation', 1)} | 上次残差 Loss: {evo_params.get('last_loss', 0.0):.4f}")
    print(f"  ⚙️ 物理状态参数: 高斯核宽 σ={sigma:.2f} (看扩散) | 时序衰减 λ={lambda_decay:.2f} (看势头) | 雷区深度={kill_size}码")
    print("-" * 80)

    # 4. 执行统一主脑解算
    brain = UnifiedDecisionBrain(data_root)
    res = brain.solve_period(
        target_period=target_period,
        sigma=sigma,
        lambda_decay=lambda_decay,
        kill_size=kill_size,
        temperature=temperature
    )

    radar = res.get("radar_features", {})

    # 5. 打印操盘手战报
    print("\n  📊 【五大物理维度战力雷达评分 (大白话战况)】")
    print(f"     ⏱️ 时序惯性 (看冷热势头) : {radar.get('time_inertia', 0.0):5.1f} / 100")
    print(f"     🌐 空间能量 (蹭聚类热度) : {radar.get('spatial_energy', 0.0):5.1f} / 100")
    print(f"     📜 形态规则 (老经验形态) : {radar.get('rule_activation', 0.0):5.1f} / 100")
    print(f"     🔗 拓扑共现 (找搭档跟班) : {radar.get('topological_energy', 0.0):5.1f} / 100")
    print(f"     🛡️ 防守强度 (踩刹车防守) : {radar.get('defense_strength', 0.0):5.1f} / 100")
    print("-" * 80)

    print("  👑 【一脉相承 · 层级化实战决策部署】")
    print("-" * 80)
    print(f"  💎 1. 尖刀核心金胆 (第一王牌)     : 【 {str(res['gold_single']).zfill(2)} 】 (80维物理概率第一最高峰)")
    print(f"  👑 2. 极简选2 · 黄金搭档 (连体伴随): [ {str(res['gold_pair'][0]).zfill(2)} - {str(res['gold_pair'][1]).zfill(2)} ] (共现粘性最大搭档)")
    top3 = res.get("top3_gold") or res.get("top5") or []
    print(f"  🌟 3. 最优 3 码 (主口径)           : {' - '.join(str(x).zfill(2) for x in top3)}")
    print(f"  🚫 4. 硬防守绝对禁区 (踩雷一票否决): {res['killed_count']} 码 ({' '.join(str(x).zfill(2) for x in res['killed_numbers'])})")
    print("=" * 80)
    print(f"  ✨ 结构化数据资产: {json_asset_path}")
    print(f"  📝 操盘手实战研报: {report_asset_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
