#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_daily.py — 逐模块逐期复盘子系统执行器
================================================================================
用法:
    python -m backend.modules.daily_review.run_daily harvest [期号] [日期]
        # 开奖前: 把各模块当期推荐号码收割进追加式前瞻账
    python -m backend.modules.daily_review.run_daily review [期号]
        # 开奖后: 输出该期逐模块命中明细 (md + json)
    python -m backend.modules.daily_review.run_daily settle [期号]
        # 开奖后: 先补对账(actual/hits) 再复盘, 一步到位

约定: 期号省略时, harvest 推断"最新开奖 + 1", review/settle 取"最新已开奖期"。
"""
import argparse
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from backend.modules.daily_review.harvester import harvest
from backend.modules.daily_review.reviewer import review_period


def main() -> int:
    parser = argparse.ArgumentParser(description="逐模块逐期复盘子系统")
    parser.add_argument("action", choices=["harvest", "review", "settle"],
                        help="harvest=开奖前收割; review=开奖后复盘; settle=补对账后复盘")
    parser.add_argument("period", nargs="?", default=None, help="期号 (省略则自动推断)")
    parser.add_argument("date", nargs="?", default=None, help="日期 YYYY-MM-DD (仅 harvest 用)")
    parser.add_argument("--refresh", default=None,
                        help="harvest 专用: 逗号分隔的模块 id, 显式重收其同期旧账(口径修正)")
    args = parser.parse_args()

    if args.action == "harvest":
        refresh_ids = [x.strip() for x in (args.refresh or "").split(",") if x.strip()]
        res = harvest(args.period, args.date, verbose=True, refresh_ids=refresh_ids or None)
        return 0 if res.get("status") == "ok" else 1

    if args.action == "settle":
        from backend.core.module_gate import reconcile_module_ledger
        filled = reconcile_module_ledger(limit_periods=400)
        print("  🔄 前瞻账对账补充 %d 条" % filled)

    res = review_period(args.period, verbose=True)
    return 0 if res.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())