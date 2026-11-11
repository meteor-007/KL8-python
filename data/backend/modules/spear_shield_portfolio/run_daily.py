# -*- coding: utf-8 -*-
"""
一胆拖三盾 · 选2组合拳每日推演与实盘调度入口 (Run Daily Entrypoint)
================================================================

【运行入口】:
  - 每日推演：python -m backend.modules.spear_shield_portfolio.run_daily
  - 样本外回测：python -m backend.modules.spear_shield_portfolio.run_daily --backtest 30

@author Antigravity Quant Team & Old-School Quant Trader
@since 2026-09-21
"""

from __future__ import annotations

import os
import sys
import argparse
from datetime import datetime

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.dirname(_CURR_DIR)
_BACKEND_DIR = os.path.dirname(_MODULES_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils.history_loader import load_history
from backend.utils.paths import get_outputs_dir
from backend.data_acquisition.daily_points_manager import load_daily_points
from backend.modules.tri_high.tri_high_engine import TriHighResonanceEngine
from backend.modules.spear_shield_portfolio.engine import SpearShieldPortfolioEngine
from backend.modules.spear_shield_portfolio.reviewer import SpearShieldPortfolioReviewer

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="一胆拖三盾 · 选2组合拳量化子系统")
    parser.add_argument("--backtest", type=int, default=0, help="执行指定期数的样本外滚动回测 (如 30)")
    parser.add_argument("--period", type=int, default=0, help="指定目标预测期号 (默认最新期)")
    args = parser.parse_args()

    if args.backtest > 0:
        reviewer = SpearShieldPortfolioReviewer()
        reviewer.run_walk_forward_review(n_periods=args.backtest, verbose=True)
        return

    # 日常实战推演
    history = load_history()
    if not history:
        print("❌ 错误：无法读取历史开奖数据！")
        sys.exit(1)

    draws_asc = [d["numbers"] for d in reversed(history)]
    latest_record = history[0]
    latest_period = int(latest_record["issue"])
    target_period = args.period if args.period > 0 else (latest_period + 1)

    pts_dict = load_daily_points()
    pts_entry = pts_dict.get(str(target_period)) or {}
    points = pts_entry.get("points", [])

    tri_engine = TriHighResonanceEngine()
    tri_records = {str(r.get("period")): r for r in tri_engine.load_tri_high_records()}
    tri_data = tri_records.get(str(target_period))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    engine = SpearShieldPortfolioEngine()
    result = engine.run_prediction(
        all_draws_asc=draws_asc,
        target_period=target_period,
        daily_points=points,
        tri_high_data=tri_data,
        draw_date=now_str
    )

    # 打印至控制台
    print("\n" + "*" * 76)
    print("【一胆拖三盾 · 选2组合拳 · 操盘手实战总账单】")
    print("*" * 76)
    print(result.report_markdown)
    print("*" * 76 + "\n")

    # 物理落盘
    reports_dir = os.path.join(get_outputs_dir(), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    report_file = os.path.join(reports_dir, f"spear_shield_report_{target_period}.md")
    latest_file = os.path.join(reports_dir, "spear_shield_report_latest.md")

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(result.report_markdown)
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(result.report_markdown)

    print(f"✅ 战报已物理落盘至: {report_file}")


if __name__ == "__main__":
    main()
