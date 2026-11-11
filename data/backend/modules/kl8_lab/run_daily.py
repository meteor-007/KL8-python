#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""点位+遗漏号深度分析（kl8_lab）· 每日一键运行脚本

由菜单模块「点位×遗漏号深度分析舱」的【一键深度分析】按钮异步触发，
也可手工执行：

    python run_kl8_lab_daily.py                 # 完整分析 + 60 期滚动外样本回测
    python run_kl8_lab_daily.py --no-backtest   # 只出当日分析（快）
    python run_kl8_lab_daily.py --backtest 120  # 指定回测窗口期数
    python run_kl8_lab_daily.py --period 2026234
    python run_kl8_lab_daily.py --fetch         # 先联网增量补开奖再分析

产物（outputs/kl8_lab/）：
    latest_summary.json      —— 驾驶舱快照（缺失字段一律 null，不填占位数字）
    backtest_summary.json    —— 样本外回测与显著性（BH-FDR）
    reports/kl8_lab_*.md     —— 逐期研报
    <date>/daily_report.md   —— 原项目按日期目录布局，保留兼容

退出码：0 = 有统计显著信号；2 = 无显著信号（退化分支，**正常结果**）；1 = 错误。
"""
import argparse
import os
import sys

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


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.core.kl8_lab import service            # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="点位+遗漏号深度分析 · 每日运行")
    ap.add_argument("--period", type=int, default=None, help="指定分析期号（默认自动推断下一期）")
    ap.add_argument("--backtest", type=int, default=60, help="滚动外样本回测窗口期数（0=跳过）")
    ap.add_argument("--no-backtest", action="store_true", help="跳过回测")
    ap.add_argument("--fetch", action="store_true", help="分析前先联网增量补开奖")
    ap.add_argument("--methods", default=None, help="只跑部分方法（调试用，逗号分隔，不写在线权重）")
    args = ap.parse_args(argv)

    n = 0 if args.no_backtest else int(args.backtest or 0)
    methods = [m.strip() for m in args.methods.split(",") if m.strip()] if args.methods else None

    print("=" * 66)
    print("🔮 点位 × 遗漏号 深度分析（kl8_lab）· 每日运行")
    print("=" * 66)
    try:
        payload = service.run_daily(period=args.period, backtest_n=n,
                                    allow_fetch=args.fetch, methods=methods)
    except Exception as exc:
        print(f"❌ 运行失败：{exc}")
        return 1

    tgt = payload.get("target") or {}
    ds = (payload.get("dataset") or {}).get("health") or {}
    print(f"目标期       : {tgt.get('period')}（{tgt.get('date')}）")
    print(f"点位/拓展    : {tgt.get('points_count')} 个 / {tgt.get('expanded_count')} 个")
    print(f"点位档案     : {ds.get('points_count')} 期    开奖档案: {ds.get('draws_count')} 期"
          f"    可配对: {ds.get('pairable_count')} 期")
    top5 = (payload.get("top5") or {}).get("core") or []
    print(f"五码核心     : {' '.join(f'{n:02d}' for n in top5) if top5 else '（空）'}")
    dfn = (payload.get("picks52") or {}).get("defensive") or []
    print(f"两码备防     : {' '.join(f'{n:02d}' for n in dfn) if dfn else '（空）'}")
    deg = payload.get("degradation") or {}
    print(f"退化状态     : {'⚠️ 全部方法未通过随机基线检验' if deg.get('degraded') else '未触发退化分支'}")
    if deg.get("module_notes"):
        print(f"数据不足模块 : {'; '.join(deg['module_notes'])}")
    bt = payload.get("backtest") or {}
    if bt.get("available"):
        sysr = bt.get("system") or {}
        print(f"回测 T={sysr.get('T')} 均值={sysr.get('mean_hits')} lift={sysr.get('lift')} "
              f"q={sysr.get('q_value')} → {sysr.get('verdict')}")
    print(f"研报         : {payload.get('report_file')}")
    print("=" * 66)
    return 2 if deg.get("degraded") else 0


if __name__ == "__main__":
    sys.exit(main())
