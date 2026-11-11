# -*- coding: utf-8 -*-
"""
快乐8 心理博弈论与逆向均值回归独立运行入口 (Psychological Game Daily Runner)
=============================================================================
【业务背景与架构定位】:
本脚本为独立的每日调度与实战运行入口，无需启动 Web 服务即可直接在控制台执行：
1. 运行心理博弈与逆向均值回归推演引擎；
2. 自动生成并在终端打印老派操盘手大白话实战战报；
3. 落盘 storage/stats/psychological_game_analysis.json 与 outputs/reports/psychological_game_report_latest.md。

用法:
    python run_psychological_game_daily.py

@author Antigravity Quantitative Team
@since 2026-09-07
"""

import os
import sys

# 步骤 1: 路径初始化
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

_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = _find_project_root(_DIR)
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR, _DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.core.psychological_game_engine import run_psychological_game_pipeline


def main():
    print("=" * 65)
    print(" 🧠 [K8-QUANT] 心理博弈论与逆向均值回归核心流水线启动")
    print("=" * 65)
    
    result = run_psychological_game_pipeline()
    
    top5_str = "、".join(f"{x:02d}" for x in result.get("top5_assault", []))
    top12_str = " ".join(f"{x:02d}" for x in result.get("top12_balanced", []))
    colds_str = "、".join(f"{x:02d}" for x in result.get("top_cold_spring", []))
    repeats_str = "、".join(f"{x:02d}" for x in result.get("top_healthy_repeats", []))
    target_period = result.get("target_period", "N/A")
    based_period = result.get("based_on_period", "N/A")
    macro = result.get("macro_pendulum", {})

    print("\n" + "#" * 65)
    print(f"  ★ 第 {target_period} 期 【心理博弈 + 逆向均值回归】 操盘手内参速报 ★")
    print(f"  (基于第 {based_period} 期最新实开数据深度推演)")
    print("#" * 65)
    print(f"1. 突击 Top 5 金牌 (大白话: 逆向博弈综合胜率最高的核心胆码):")
    print(f"   >>> 【 {top5_str} 】")
    print(f"2. 稳健大底 Top 12 (大白话: 均值回归防守大网):")
    print(f"   >>> [ {top12_str} ]")
    print(f"3. 弹性冷号突击 (大白话: 绝望点报复性回补冷门):")
    print(f"   >>> 【 {colds_str} 】")
    print(f"4. 单点健康重号 (大白话: 无连号截断阻碍、极易连庄的热号):")
    print(f"   >>> 【 {repeats_str} 】")
    print(f"5. 宏观钟摆态势: {macro.get('target_size_bias', 'N/A')}")
    print("#" * 65)
    print("战报与账本已成功归档至 outputs/reports/ 与 storage/stats/ 目录。\n")


if __name__ == "__main__":
    main()
