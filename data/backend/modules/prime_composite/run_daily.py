# -*- coding: utf-8 -*-
"""
快乐8 质合数量化推演与尾数香农熵独立运行入口 (Prime Composite & Tail Daily Runner)
================================================================================
【业务背景与架构定位】:
本脚本为独立的每日调度与实战运行入口，无需启动 Web 服务即可直接在控制台执行：
1. 运行方案二、三、四三合一计算引擎；
2. 自动生成并在终端打印老派操盘手大白话推演战报；
3. 更新 storage/stats/prime_tail_entropy_analysis.json 与 outputs/reports/prime_composite_tail_report_latest.md。

用法:
    python run_prime_composite_daily.py

@author Antigravity Quantitative Team
@since 2026-09-03
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

from backend.core.prime_composite_engine import run_prime_tail_analysis_pipeline


def main():
    print("=" * 65)
    print(" [K8-QUANT] 质合数量化推演与尾数香农熵核心流水线启动")
    print("=" * 65)
    
    consensus = run_prime_tail_analysis_pipeline()
    
    takeaways = consensus.get("summary_takeaways", {})
    target_period = consensus.get("target_period", "N/A")
    based_period = consensus.get("based_on_period", "N/A")
    top5_primes = takeaways.get("top5_prime_gold", [])
    top5_str = "、".join(f"{x:02d}" for x in top5_primes)
    twin_label = takeaways.get("recommended_twin_label", "N/A")
    entropy_val = takeaways.get("shannon_entropy", 0.0)
    entropy_desc = takeaways.get("entropy_status_desc", "N/A")

    print("\n" + "#" * 65)
    print(f"  ★ 第 {target_period} 期 【质数合数 + 尾数香农熵】 操盘手内参速报 ★")
    print(f"  (基于第 {based_period} 期最新实开数据分析推演)")
    print("#" * 65)
    print(f"1. 质数 VIP 小池塘金牌 Top 5 (大白话：22个质数里最强5胆):")
    print(f"   >>> 【 {top5_str} 】")
    print(f"2. 孪生质数最强连体搭档 (大白话：相差为2、憋到极限要双飞的组合):")
    print(f"   >>> 【 {twin_label} 】")
    print(f"3. 尾数香农熵诊断:")
    print(f"   >>> 熵值 {entropy_val} (理论上限 3.3219) | {entropy_desc}")
    print("#" * 65)
    print("战报与账本已成功归档至 outputs/reports/ 与 storage/stats/ 目录。\n")


if __name__ == "__main__":
    main()
