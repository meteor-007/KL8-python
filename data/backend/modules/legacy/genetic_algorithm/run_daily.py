#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 遗传算法自进化号码推演 每日量化研判执行器
=================================================
遵循老派量化操盘手大白话落地执行协议：
1. 玩法：基于全量历史开奖数据，利用遗传算法自适应进化特征权重与实战号码组合。
2. 核心输出：
   - 尖刀金胆 (1 码 / 极高确定性先锋)
   - 黄金选2 (2 码 / 金胆与粘性伴随)
   - 突击主力 (Top 5 / 核心进攻火力)
   - 8区底仓 (Top 12 / 八大区间均衡覆盖)
3. 生成研报与资产并更新缓存。

用法：
  python -m backend.modules.legacy.genetic_algorithm.run_daily [--pop 40] [--gen 25] [--review 30]
"""

import os
import sys
import json
import argparse
from datetime import datetime

# 路径自适应
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

from backend.utils.paths import get_cache_dir, get_outputs_dir, get_reports_dir
from backend.modules.legacy.genetic_algorithm.genetic_engine import GeneticAlgorithmEngine

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run_daily_genetic(pop_size: int = 40, generations: int = 25, review_n: int = 30) -> None:
    """运行每日遗传算法推演与研报生成"""
    print("=" * 70)
    print("🧬 快乐8 遗传算法自进化号码推演引擎 (Genetic Algorithm Daily Runner)")
    print("=" * 70)

    engine = GeneticAlgorithmEngine()
    print(f"📊 [1/4] 加载开奖总库成功，历史总期数: {engine.total_periods} 期")

    print(f"🧬 [2/4] 启动遗传算法种群自进化 (种群={pop_size}, 繁衍={generations}代, 回溯评估=15期)...")
    evo_result = engine.run_evolution(pop_size=pop_size, generations=generations, eval_periods=15)
    best_chrom = evo_result.get("best_chromosome")

    import numpy as np
    prediction = engine.generate_prediction(best_chromosome=np.array(best_chrom, dtype=np.float64))
    prediction["evolution_meta"] = evo_result

    # 保存缓存
    cache_dir = os.path.join(get_cache_dir(), "genetic_algorithm")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "latest_summary.json")
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(prediction, f, ensure_ascii=False, indent=2)

    target_period = prediction["target_period"]
    latest_period = prediction["latest_period"]
    gold_core = prediction["gold_core"]
    gold_pair = prediction["gold_pair"]
    top5 = prediction["top5_assault"]
    top12 = prediction["top12_balanced"]
    weights = prediction["best_weights"]

    print("\n" + "─" * 70)
    print(f"🎯 目标推演期号: 【第 {target_period} 期】 (基准已开期号: {latest_period})")
    print(f"👑 尖刀金胆 (1 码):  {gold_core:02d}")
    print(f"💎 黄金搭档选2 (2 码): [{', '.join(f'{x:02d}' for x in gold_pair)}]")
    print(f"🔥 突击主力 (Top 5):  [{', '.join(f'{x:02d}' for x in top5)}]")
    print(f"🛡️ 8区覆盖底仓 (Top 12): [{', '.join(f'{x:02d}' for x in top12)}]")
    print("─" * 70)
    print("🧬 进化所得最优特征权重占比 (大白话: 机器裁判给各指标的看重程度):")
    for k, v in weights.items():
        print(f"   • {k:<12}: {v*100:5.1f}%")
    print("─" * 70)

    # 步骤 3: 生成独立研报
    print(f"📝 [3/4] 正在生成 Markdown 研报与推演资产...")
    reports_dir = get_reports_dir()
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, f"genetic_algorithm_report_{target_period}.md")

    report_md = f"""# 🧬 快乐8 遗传算法自进化号码推演研报 (第 {target_period} 期)

> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
> **基准开奖期号**: 第 {latest_period} 期  
> **算法模型**: 遗传算法多维特征自适应进化 (GA-Evolution V1.0)  

---

## 一、 核心操盘实战决策 (大白话落地方案)

| 战术层级 | 推荐号码 | 操盘策略说明 (大白话) |
| :--- | :--- | :--- |
| **👑 尖刀金胆 (1 码)** | `{gold_core:02d}` | 适应度综合打分第 1 名，确定性最高的单点突破先锋 |
| **💎 黄金搭档选2 (2 码)** | `{' '.join(f'{x:02d}' for x in gold_pair)}` | 金胆 + 空间共现粘性最高伴随码，双全中极简搭档 |
| **🔥 突击主力 (Top 5)** | `{' '.join(f'{x:02d}' for x in top5)}` | 进化权重打分前 5 强，核心进攻火力群 |
| **🛡️ 8区底仓 (Top 12)** | `{' '.join(f'{x:02d}' for x in top12)}` | 兼顾 8 大物理区间均衡覆盖，防守大本营 |

---

## 二、 遗传算法自适应权重结构 (当前进化代数最优配置)

```json
{json.dumps(weights, ensure_ascii=False, indent=2)}
```

---

## 三、 80 码综合适应度得分天梯榜 (前 20 强)

| 排名 | 号码 | 综合得分 | 战术归属 |
| :---: | :---: | :---: | :--- |
"""
    # 填入前 20 强明细
    top20_items = [item for item in prediction["scores_80"] if item["rank"] <= 20]
    top20_items.sort(key=lambda x: x["rank"])
    for it in top20_items:
        tag = "👑 金胆" if it["is_gold"] else ("🔥 Top5 主力" if it["in_top5"] else ("🛡️ Top12 底仓" if it["in_top12"] else "候选"))
        report_md += f"| 第 {it['rank']:02d} 名 | **{it['number']:02d}** | `{it['score']:.4f}` | {tag} |\n"

    report_md += f"""
---
*本报告由 K8-QUANT 遗传算法自进化引擎自动生成，数据严禁未来函数。*
"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"✅ 研报已写入: {report_path}")

    # 步骤 4: 触发样本外滚动对账
    print(f"📊 [4/4] 正在执行近 {review_n} 期样本外 Walk-Forward 滚动对账...")
    from backend.modules.legacy.genetic_algorithm.service import GeneticServiceMixin
    class DummyService(GeneticServiceMixin):
        def load_history(self, limit=None):
            return engine.history[:limit] if limit else engine.history
    
    srv = DummyService()
    rev = srv.get_genetic_review(n=review_n)
    if rev.get("status") == "success":
        st = rev.get("stats", {})
        print(f"   • 近 {st.get('total_periods')} 期 Top3 平均命中:  {st.get('avg_top3_hit')} 码")
        print(f"   • 金胆单码命中率:       {st.get('gold_hit_rate')}%")
        print(f"   • 选2双全中率:          {st.get('pair_double_rate')}%")

    print("\n🎉 [完成] 遗传算法每日推演与研报生成圆满完成！\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="快乐8 遗传算法每日推演执行器")
    parser.add_argument("--pop", type=int, default=40, help="种群规模 (默认 40)")
    parser.add_argument("--gen", type=int, default=25, help="进化代数 (默认 25)")
    parser.add_argument("--review", type=int, default=30, help="滚动回测期数 (默认 30)")
    args = parser.parse_args()

    run_daily_genetic(pop_size=args.pop, generations=args.gen, review_n=args.review)
