# -*- coding: utf-8 -*-
"""
马尔可夫链与特征直线校准每日推演入口 (Markov Line Daily Runner)
============================================================
供流水线调度与 CLI 命令行直接触发：
    python -m backend.modules.markov_line.run_daily
"""

import os
import sys

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.modules.markov_line.service import run_markov_line_pipeline


def main():
    print("=" * 75)
    print(" 📐 [K8-QUANT] 马尔可夫链与特征直线校准推演引擎启动")
    print("=" * 75)
    result = run_markov_line_pipeline()

    top5_str = "、".join(f"{x:02d}" for x in result["top5_gold"])
    top12_str = " ".join(f"{x:02d}" for x in result["top12_elite"])
    prim_s = result["predicted_primary_state"]
    line_cal = result["straight_line_calibration"]

    print(f"★ 最新实际开奖: 第 {result['latest_issue']} 期 | 目标预测期号: 第 {result['target_issue']} 期 ★")
    print(f"1. 👑 金胆 Top 5: 【 {top5_str} 】")
    print(f"2. 🛡️ 核心大底 Top 12: [ {top12_str} ]")
    print(f"3. 🧭 下期首选宏观形态: 状态 {prim_s['state_id']} (概率: {prim_s['probability']*100:.1f}%)")
    print(f"   - 和值区间: {prim_s['sum_level']} | 奇偶偏向: {prim_s['odd_level']} | 动能态势: {prim_s['momentum_level']}")
    print(f"4. 📏 P-P 图直线检验: R^2 = {line_cal['r_squared']} | KS 统计量 = {line_cal['ks_statistic']} | 直线化判定: {'✅ 严格成直线' if line_cal['is_straight'] else '⚠️ 拟合微调'}")
    print(f"5. 🚀 强反弹拐点 Top 3: " + ", ".join(f"[{s['target_id']:02d}号: 强度{s['rebound_strength']}]" for s in result["top_rebound_signals"][:3]))
    print("=" * 75)


if __name__ == "__main__":
    main()
