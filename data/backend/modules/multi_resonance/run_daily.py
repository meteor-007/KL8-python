# -*- coding: utf-8 -*-
"""
快乐8 终审多维共振联合会诊与样本外回测独立执行器
===================================================
用法:
  python run_multi_resonance_daily.py           (推演目标期共识并生成研报)
  python run_multi_resonance_daily.py --backtest 50   (运行近50期严格样本外滚动回测)
"""

import os
import sys
import json

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
for p in [_BACKEND_DIR, _PROJ_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.core.multi_resonance_engine import (
    MultiResonanceConsensusEngine,
    run_multi_resonance_pipeline
)


def main():
    args = sys.argv[1:]
    engine = MultiResonanceConsensusEngine()

    if "--backtest" in args:
        idx = args.index("--backtest")
        n = int(args[idx + 1]) if len(args) > idx + 1 and args[idx + 1].isdigit() else 50
        print(f"\n=================================================================")
        print(f" 🧬 启动终审多维共振引擎 · 近 {n} 期严格 Walk-Forward 滚动实测对账")
        print(f"=================================================================")
        bt = engine.run_walk_forward_backtest(test_periods=n)
        g5 = bt["golden_core_5"]
        r12 = bt["resonance_12"]
        p = bt["best_pair"]

        print(f"■ 测试样本区间: {bt['sample_range']} (共实测 {n} 期)")
        print(f"■ 【多维共振至尊金胆 Top 5 决算】:")
        print(f"   - 平均每期命中: {g5['avg_hits_per_period']} 个 / 5码")
        print(f"   - 单码实际命中率: {g5['single_hit_rate']}% (大盘基线 25.0% | 提升度 Lift: {g5['lift_over_random']}x)")
        print(f"   - 至少中 1 码覆盖率: {g5['hit_ge1_rate']}%")
        print(f"   - 命中 >= 2 码爆发率: {g5['hit_ge2_rate']}%")
        print(f"   - 命中分布: 0中={g5['distribution'].get(0,0)}期, 1中={g5['distribution'].get(1,0)}期, 2中={g5['distribution'].get(2,0)}期, 3中={g5['distribution'].get(3,0)}期, 4中={g5['distribution'].get(4,0)}期")

        print(f"\n■ 【多维共振 12 码实战大底 决算】:")
        print(f"   - 平均每期命中: {r12['avg_hits_per_period']} 个 / 12码")
        print(f"   - 单码实际命中率: {r12['single_hit_rate']}% (大盘基线 25.0% | 提升度 Lift: {r12['lift_over_random']}x)")

        print(f"\n■ 【共振选2王牌搭档 决算】:")
        print(f"   - 选2双全中次数: {p['double_hit_count']} 次 (双全中率: {p['double_hit_rate']}%)")
        print(f"   - 相对理论随机基线(6.01%) 提升倍数: {p['lift_over_random']}x")
        print(f"   - 至少中 1 码对冲率: {p['at_least_one_rate']}%")
        print(f"=================================================================\n")
        return

    # 默认执行推演流水线
    print("\n=================================================================")
    print(" 🧬 启动终审多维共振联合会诊流水线 (方向 B)")
    print("=================================================================")
    res = run_multi_resonance_pipeline()
    take = res.get("summary_takeaways", {})

    print(f"\n#################################################################")
    print(f"  ★ 第 {res.get('target_period')} 期 【多维共振终审会诊】 实战操盘速报 ★")
    print(f"  (基于第 {res.get('based_on_period')} 期最新实开数据 · 5大流派专家联合出诊)")
    print(f"#################################################################")
    print(f"1. 🌟 多维共振至尊金胆 Top 5 (大白话: 5位专家共同举手最高票):")
    print(f"   >>> 【 {take.get('golden_core_5_str')} 】")
    print(f"2. 🎯 多维共振 12 码实战大底:")
    print(f"   >>> 【 {take.get('resonance_12_str')} 】")
    print(f"3. 🔗 共振选2跨路攻守搭档:")
    print(f"   >>> 【 {take.get('best_resonance_pair')} 】")
    print(f"#################################################################")
    print(f"研报与数据账本已归档至 outputs/reports/ 与 storage/stats/ 目录。\n")


if __name__ == "__main__":
    main()
