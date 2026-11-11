# -*- coding: utf-8 -*-
"""
线性代数空间投影量化分析独立执行入口 (Linear Algebra Daily Runner)
================================================================
【业务背景与架构定位】:
支持独立控制台运行与夜间流水线批处理调用，输出实战战报并落盘数据。

用法:
    python backend/modules/linear_algebra/run_daily.py

@author K8-Quant Linear Algebra Team
@since 2026-09-11
"""
import os
import sys

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

from backend.modules._retired.linear_algebra.service import run_linear_algebra_pipeline


def main():
    print("=" * 70)
    print(" 📐 [K8-QUANT] 线性代数空间投影推演引擎 (Linear Algebra Engine) 启动")
    print("=" * 70)

    result = run_linear_algebra_pipeline()

    target_issue = result.get("target_issue", "N/A")
    latest_issue = result.get("latest_issue", "N/A")
    top5_str = "、".join(f"{x:02d}" for x in result.get("top3_gold") or result.get("top5_gold", []))
    top12_str = " ".join(f"{x:02d}" for x in result.get("top3_gold") or result.get("top12_elite", []))

    print("\n" + "#" * 70)
    print(f"  ★ 第 {target_issue} 期 【线性代数空间投影量化推演】 操盘手内参 ★")
    print(f"  (基于第 {latest_issue} 期最新实开与全量 {result.get('total_historical_draws', 0)} 期矩阵空间分解)")
    print("#" * 70)
    print(f"1. 👑 金胆 Top 5 (大白话: 空间投影能量共振最高的金胆):")
    print(f"   >>> 【 {top5_str} 】")
    print(f"2. 🛡️ 核心大底 Top 12 (大白话: SVD主成分+余弦镜像稳健大网):")
    print(f"   >>> [ {top12_str} ]")
    print(f"3. 💎 黄金搭档选2 (大白话: 协方差共现最高、死活粘在一起的搭档):")
    for p in result.get("gold_pairs", [])[:3]:
        print(f"   >>> 搭档 【{p['pair']}】 (共振打分: {p['affinity_score']}分, 历史同开: {p['cooccur_count']}次)")
    print(f"4. 🧬 历史最相似镜像 (Top 1):")
    if result.get("top_historical_matches"):
        top1_m = result["top_historical_matches"][0]
        overlap_str = "、".join(f"{x:02d}" for x in top1_m.get("overlap_with_top12", [])) or "无"
        print(f"   >>> 历史第 {top1_m['target_issue']} 期走势切片，余弦相似度: {top1_m['similarity_pct']}%，当年后继开奖与当期Top12重合: 【{overlap_str}】")
    print("#" * 70)
    print("✅ 研报与推演数据已成功持久化至 storage/outputs/ 与 frontend/static/ 目录。\n")


if __name__ == "__main__":
    main()
