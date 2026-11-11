# -*- coding: utf-8 -*-
"""
run_aggregation_daily.py — 快乐8 终审共识与数据汇总复盘每日调度入口
==================================================================
"""
import os
import sys
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 双根引导 (Dual-Root Bootstrap)
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

DATA_DIR = _PROJ_DIR

from daily_run_guard import guard_daily_run, mark_daily_run_done
from core.aggregation.consensus_engine import ConsensusEngine


def main():
    parser = argparse.ArgumentParser(description="快乐8 终审共识与数据汇总复盘")
    parser.add_argument("--review-n", type=int, default=100, help="Walk-Forward 回测期数 (C1/C3: 默认100期, <100挂'样本不足'水印)")
    parser.add_argument("--force", action="store_true", help="强制重跑")
    args = parser.parse_args()

    engine = ConsensusEngine(DATA_DIR)
    draws = engine.load_draws()
    if not draws:
        print("❌ 无法读取开奖历史")
        sys.exit(1)

    target_period = draws[-1]["period"] + 1
    if not args.force and guard_daily_run("数据汇总复盘", period=target_period):
        return

    print(f"\n{'='*70}")
    print(f"🚀 启动【子系统汇总陈列】独立宪法模式 — 目标期号: {target_period}")
    print(f"{'='*70}")

    result = engine.run_aggregation(n_review=args.review_n)
    
    print(f"\n✅ 汇总陈列完成！ mode={result.get('mode')} constitution={result.get('constitution')}")
    print(f"  · 参与陈列: {result['subsystems_count']} 路")
    for sys_name, num_list in result['subsystems_detail'].items():
        print(f"    - {sys_name:<10}: " + "-".join(f"{x:02d}" for x in num_list))
    
    prim = result.get("primary_recommendation") or {}
    print(f"\n  · 🎯 主推荐(=sixteen Top5): " + "-".join(f"{x:02d}" for x in result.get('consensus_dan_pool') or []))
    if prim.get("missing"):
        print("  · ⚠️ sixteen 产物缺失")
    print(f"  · 🛡️ 8区覆盖诊断: " + ("通过 ✅" if result['eight_zones_status']['full_coverage'] else "缺区: " + str(result['eight_zones_status']['miss_zones'])))
    print(f"  · 📎 频次参考 Top10: " + "-".join(f"{x:02d}" for x in result.get('freq_top10_reference') or result.get('stable_top10') or []))
    print(f"  · 📄 战报: outputs/aggregation/{result['report_file']}")
    print(f"{'='*70}\n")

    mark_daily_run_done("数据汇总复盘", period=target_period)


if __name__ == "__main__":
    main()
