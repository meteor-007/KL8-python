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
_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
DATA_DIR = _PROJ_DIR

from daily_run_guard import guard_daily_run, mark_daily_run_done
from core.aggregation.consensus_engine import ConsensusEngine


def main():
    parser = argparse.ArgumentParser(description="快乐8 终审共识与数据汇总复盘")
    parser.add_argument("--review-n", type=int, default=30, help="Walk-Forward 回测期数")
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
    print(f"🚀 启动【数据汇总复盘】终审大团长引擎 — 目标期号: {target_period}")
    print(f"{'='*70}")

    result = engine.run_aggregation(n_review=args.review_n)
    
    print(f"\n✅ 终审复盘完成！")
    print(f"  · 参与系统: {result['subsystems_count']} 路")
    for sys_name, num_list in result['subsystems_detail'].items():
        print(f"    - {sys_name:<10}: " + "-".join(f"{x:02d}" for x in num_list))
    
    print(f"\n  · 🎯 精英共识定胆池 ({len(result['consensus_dan_pool'])}码): " + "-".join(f"{x:02d}" for x in result['consensus_dan_pool']))
    print(f"  · 🛡️ 8区覆盖状态: " + ("全域覆盖通过 ✅" if result['eight_zones_status']['full_coverage'] else "缺区: " + str(result['eight_zones_status']['miss_zones'])))
    print(f"  · 🌟 Stable Top10 高频稳健号: " + "-".join(f"{x:02d}" for x in result['stable_top10']))
    print(f"  · 📈 诚实回测提升度 (Lift): 稳定号={result['walk_forward']['stable_lift']}x | 4路共识={result['walk_forward']['proxy_consensus_lift']}x")
    print(f"  · 📄 终审战报已生成: outputs/aggregation/{result['report_file']}")
    print(f"{'='*70}\n")

    mark_daily_run_done("数据汇总复盘", period=target_period)


if __name__ == "__main__":
    main()
