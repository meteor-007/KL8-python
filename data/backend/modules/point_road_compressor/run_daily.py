#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
点位012压缩器每日量化推演与样本外实战对账终端 (PointRoadCompressor Daily Runner)
================================================================================
【使用方式】:
  1. 默认执行下一期出号推演与研报落盘:
     python -m backend.modules.point_road_compressor.run_daily
  2. 样本外无未来信息 30 期实盘对账回测:
     python -m backend.modules.point_road_compressor.run_daily --backtest 30
  3. 指定目标期号:
     python -m backend.modules.point_road_compressor.run_daily --period 2026270

@author Antigravity Quant Team
@since 2026-10-11
"""
from __future__ import annotations

import os
import sys
import argparse

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.dirname(_CURR_DIR)
_BACKEND_DIR = os.path.dirname(_MODULES_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from backend.modules.point_road_compressor.engine import PointRoadCompressor


def main() -> None:
    parser = argparse.ArgumentParser(description="点位012压缩推演量化决策终端")
    parser.add_argument("--period", type=str, default=None, help="指定目标预测期号 (默认自动推断下一期)")
    parser.add_argument("--backtest", type=int, default=0, help="运行样本外滚动实战回测期数 (如 30)")
    args = parser.parse_args()

    compressor = PointRoadCompressor()

    if args.backtest > 0:
        compressor.run_walk_forward_review(n_periods=args.backtest, verbose=True)
    else:
        res = compressor.run_prediction(target_period=args.period)
        print("\n" + "═" * 76)
        print(f"  🧬 [PointRoadCompressor] 点位012压缩推演完成！目标期: 第 {res.target_period} 期")
        print("═" * 76)
        top3_s = " ".join(f"{x:02d}" for x in res.top3_gold)
        top5_s = " ".join(f"{x:02d}" for x in res.top5_picks)
        top10_s = " ".join(f"{x:02d}" for x in res.top10_defense)
        pairs_s = " ｜ ".join(f"[{a:02d}-{b:02d}]" for a, b in res.gold_pairs)
        gold_txt = f"【 {res.top3_gold[0]:02d} 】" if res.top3_gold else "—"

        print(f"  👑 至尊压缩金胆 : {gold_txt}")
        print(f"  🌟 最优 3 码锋线 : {top3_s}")
        print(f"  🎯 精选 5 码突击 : {top5_s}")
        print(f"  🛡️ 十全防线大底 : {top10_s}")
        print(f"  💎 跨路对冲选 2 : {pairs_s}")
        print("─" * 76)
        if res.pruned_candidates:
            pruned_show = " ".join(f"{p['number']:02d}({p['road']}路)" for p in res.pruned_candidates[:6])
            print(f"  ✂️ 012 偏态重点剪枝剔除 (避险) : {pruned_show}")
        print("═" * 76 + "\n")


if __name__ == "__main__":
    main()
