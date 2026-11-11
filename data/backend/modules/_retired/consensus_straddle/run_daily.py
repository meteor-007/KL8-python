# -*- coding: utf-8 -*-
"""
三维交集共识定胆与选2冷热对冲每日量化推演执行器 (Consensus Straddle Daily Runner)
========================================================================================

【使用方式】:
  1. 推演下一期出号决策:
     python -m backend.modules._retired.consensus_straddle.run_daily
  2. 样本外无未来信息 30 期实盘对账回测:
     python -m backend.modules._retired.consensus_straddle.run_daily --backtest 30

@author Antigravity Quant Team
@since 2026-09-21
"""

from __future__ import annotations

import argparse
import os
import sys

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.dirname(_CURR_DIR)
_BACKEND_DIR = os.path.dirname(_MODULES_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.modules._retired.consensus_straddle.engine import run_consensus_prediction
from backend.modules._retired.consensus_straddle.reviewer import ConsensusStraddleReviewer


def main() -> None:
    parser = argparse.ArgumentParser(description="三维交集共识定胆与选2冷热对冲量化执行器")
    parser.add_argument("--backtest", type=int, default=0, help="运行样本外滚动回测期数 (例如 30)")
    parser.add_argument("--period", type=int, default=None, help="指定目标预测期号 (默认下一期)")
    args = parser.parse_args()

    if args.backtest > 0:
        reviewer = ConsensusStraddleReviewer()
        reviewer.run_walk_forward_review(n_periods=args.backtest, verbose=True)
    else:
        result = run_consensus_prediction(target_period=args.period)
        print("\n" + "*" * 76)
        print("【三维交集共识与选2冷热对冲 · 操盘手决算总账单】")
        print("*" * 76)
        print(result.summary_report)
        print("*" * 76 + "\n")


if __name__ == "__main__":
    main()
