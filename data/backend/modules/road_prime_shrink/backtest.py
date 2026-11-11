# -*- coding: utf-8 -*-
"""
快乐8 决策树 012路 × 质合缩水系统滚动前瞻实战回测引擎 (Walk-Forward Backtest)
================================================================================
【设计规范与反幻觉红线】:
1. 严格样本外 (Out-Of-Sample) 滚动前瞻测试，每一期预测时仅使用该期之前的开奖数据，绝对杜绝未来数据泄露；
2. 逐期对账官方实开 20 码，真实统计 Top3、Top5、30 码实战大底及黄金选2搭档命中表现；
3. 输出提升度 (Lift = 实际命中率 ÷ 25% 随机基线) 与全量对账报表。

@author Antigravity Quant Team
@since 2026-10-23
"""

from __future__ import annotations

import os
import sys
import json
import logging
from typing import Dict, List, Any

# 保证根路径可被正确引用
_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURR_DIR, "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.modules.road_prime_shrink.run_daily import load_raw_history
from backend.modules.road_prime_shrink.tree_engine import TreeRoadPrimeShrinkEngine
from backend.utils.paths import get_outputs_dir

logger = logging.getLogger("k8quant.road_prime_shrink.backtest")


def run_walk_forward_backtest(n_periods: int = 50) -> Dict[str, Any]:
    """
    执行最近 n_periods 期的滚动前瞻回测
    """
    history_file = os.path.join(_PROJECT_ROOT, "storage", "raw", "kl8_history_final.txt")
    records = load_raw_history(history_file)
    # 按期号从小到大排序
    records.sort(key=lambda x: str(x.get("period", "")))

    total_records = len(records)
    if total_records < n_periods + 50:
        raise ValueError(f"历史数据量不足进行 {n_periods} 期前瞻回测")

    test_start_idx = total_records - n_periods
    logger.info(f"开启最近 {n_periods} 期滚动前瞻回测 (期号: {records[test_start_idx]['period']} ~ {records[-1]['period']})")

    results_per_draw = []
    tot_top3_hits = 0
    tot_top5_hits = 0
    tot_top20_hits = 0
    tot_top25_hits = 0
    tot_top30_hits = 0
    pick2_double_hits = 0
    total_pick2_evals = 0

    top30_hit_dist: Dict[int, int] = {k: 0 for k in range(0, 21)}
    top25_hit_dist: Dict[int, int] = {k: 0 for k in range(0, 21)}
    top20_hit_dist: Dict[int, int] = {k: 0 for k in range(0, 21)}

    for idx in range(test_start_idx, total_records):
        target_item = records[idx]
        target_period = str(target_item["period"])
        actual_draw = sorted(target_item["numbers"])
        actual_set = set(actual_draw)

        # 严格样本外切片：仅使用 target_item 之前的所有历史数据进行特征提取和训练
        train_slice = records[:idx]
        engine = TreeRoadPrimeShrinkEngine(train_slice, train_window=100)
        inference = engine.execute_inference()

        top3 = inference["top3_gold"]
        top5 = inference["top5_gold"]
        top20 = inference["top20_core_base"]
        top25 = inference["top25_mid_base"]
        top30 = inference["top30_large_base"]
        pairs = inference["pick2_pairs"]

        # 计算实际命中情况
        hits_3 = [x for x in top3 if x in actual_set]
        hits_5 = [x for x in top5 if x in actual_set]
        hits_20 = [x for x in top20 if x in actual_set]
        hits_25 = [x for x in top25 if x in actual_set]
        hits_30 = [x for x in top30 if x in actual_set]

        n_hit3 = len(hits_3)
        n_hit5 = len(hits_5)
        n_hit20 = len(hits_20)
        n_hit25 = len(hits_25)
        n_hit30 = len(hits_30)

        tot_top3_hits += n_hit3
        tot_top5_hits += n_hit5
        tot_top20_hits += n_hit20
        tot_top25_hits += n_hit25
        tot_top30_hits += n_hit30

        top20_hit_dist[n_hit20] = top20_hit_dist.get(n_hit20, 0) + 1
        top25_hit_dist[n_hit25] = top25_hit_dist.get(n_hit25, 0) + 1
        top30_hit_dist[n_hit30] = top30_hit_dist.get(n_hit30, 0) + 1

        # 验证选2搭档 (3组搭档中是否有双全中)
        pair_hits_detail = []
        for p in pairs:
            p_nums = p["pair"]
            is_double = (p_nums[0] in actual_set) and (p_nums[1] in actual_set)
            pair_hits_detail.append({
                "pair": p_nums,
                "hits": [x for x in p_nums if x in actual_set],
                "double_hit": is_double,
            })
            total_pick2_evals += 1
            if is_double:
                pick2_double_hits += 1

        record_res = {
            "period": target_period,
            "actual_draw": actual_draw,
            "hit_top3": n_hit3,
            "hit_top3_nums": hits_3,
            "hit_top5": n_hit5,
            "hit_top5_nums": hits_5,
            "hit_top20": n_hit20,
            "hit_top20_nums": hits_20,
            "hit_top25": n_hit25,
            "hit_top25_nums": hits_25,
            "hit_top30": n_hit30,
            "hit_top30_nums": hits_30,
            "pairs": pair_hits_detail,
        }
        results_per_draw.append(record_res)

    # 总体统计指标核算
    avg_top3_hit = round(tot_top3_hits / n_periods, 3)
    rate_top3 = round(tot_top3_hits / (n_periods * 3), 4)
    lift_top3 = round(rate_top3 / 0.25, 3)

    avg_top5_hit = round(tot_top5_hits / n_periods, 3)
    rate_top5 = round(tot_top5_hits / (n_periods * 5), 4)
    lift_top5 = round(rate_top5 / 0.25, 3)

    avg_top20_hit = round(tot_top20_hits / n_periods, 3)
    rate_top20 = round(tot_top20_hits / (n_periods * 20), 4)
    lift_top20 = round(rate_top20 / 0.25, 3)

    avg_top25_hit = round(tot_top25_hits / n_periods, 3)
    rate_top25 = round(tot_top25_hits / (n_periods * 25), 4)
    lift_top25 = round(rate_top25 / 0.25, 3)

    avg_top30_hit = round(tot_top30_hits / n_periods, 3)
    rate_top30 = round(tot_top30_hits / (n_periods * 30), 4)
    lift_top30 = round(rate_top30 / 0.25, 3)

    pick2_double_rate = round(pick2_double_hits / total_pick2_evals * 100, 2)
    pick2_lift = round((pick2_double_hits / total_pick2_evals) / 0.0601, 3)

    summary = {
        "n_periods": n_periods,
        "period_range": f"{records[test_start_idx]['period']} ~ {records[-1]['period']}",
        "top3_metrics": {
            "avg_hits": avg_top3_hit,
            "theory_random_baseline": 0.75,
            "hit_rate": f"{rate_top3 * 100:.2f}%",
            "lift": lift_top3,
        },
        "top5_metrics": {
            "avg_hits": avg_top5_hit,
            "theory_random_baseline": 1.25,
            "hit_rate": f"{rate_top5 * 100:.2f}%",
            "lift": lift_top5,
        },
        "top20_core_metrics": {
            "avg_hits": avg_top20_hit,
            "theory_random_baseline": 5.00,
            "hit_rate": f"{rate_top20 * 100:.2f}%",
            "lift": lift_top20,
            "max_hit": max(r["hit_top20"] for r in results_per_draw),
            "min_hit": min(r["hit_top20"] for r in results_per_draw),
            "rate_ge6_hits": f"{round(sum(1 for r in results_per_draw if r['hit_top20'] >= 6) / n_periods * 100, 2)}%",
            "hit_distribution": {f"{k}码": v for k, v in sorted(top20_hit_dist.items()) if v > 0},
        },
        "top25_mid_metrics": {
            "avg_hits": avg_top25_hit,
            "theory_random_baseline": 6.25,
            "hit_rate": f"{rate_top25 * 100:.2f}%",
            "lift": lift_top25,
            "max_hit": max(r["hit_top25"] for r in results_per_draw),
            "min_hit": min(r["hit_top25"] for r in results_per_draw),
            "rate_ge7_hits": f"{round(sum(1 for r in results_per_draw if r['hit_top25'] >= 7) / n_periods * 100, 2)}%",
            "hit_distribution": {f"{k}码": v for k, v in sorted(top25_hit_dist.items()) if v > 0},
        },
        "top30_large_base_metrics": {
            "avg_hits": avg_top30_hit,
            "theory_random_baseline": 7.50,
            "hit_rate": f"{rate_top30 * 100:.2f}%",
            "lift": lift_top30,
            "max_hit": max(r["hit_top30"] for r in results_per_draw),
            "min_hit": min(r["hit_top30"] for r in results_per_draw),
            "rate_ge8_hits": f"{round(sum(1 for r in results_per_draw if r['hit_top30'] >= 8) / n_periods * 100, 2)}%",
            "hit_distribution": {f"{k}码": v for k, v in sorted(top30_hit_dist.items()) if v > 0},
        },
        "pick2_metrics": {
            "total_pair_evals": total_pick2_evals,
            "double_hits_count": pick2_double_hits,
            "double_hit_rate": f"{pick2_double_rate}%",
            "theory_random_baseline": "6.01%",
            "lift": pick2_lift,
        },
        "results_recent_10": results_per_draw[-10:],
    }

    # 落盘持久化
    out_dir = os.path.join(get_outputs_dir(), "predictions")
    reports_dir = os.path.join(get_outputs_dir(), "reports")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    json_path = os.path.join(out_dir, "tree_shrink_backtest.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 生成 Markdown 对账报表
    md_path = os.path.join(reports_dir, "tree_shrink_backtest_report.md")
    md_content = generate_markdown_report(summary, results_per_draw)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"\n[OK] 滚动前瞻回测完成！已落盘至: {json_path} 及 {md_path}")
    return summary


def generate_markdown_report(summary: Dict[str, Any], results: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append(f"# 快乐8 决策树 012路 × 质合缩水系统前瞻滚动回测对账报告")
    lines.append(f"> 测试周期: 最近 **{summary['n_periods']} 期** ({summary['period_range']}) | 测试口径: **严格样本外 (Out-Of-Sample)** 逐期滚动前瞻")
    lines.append("")
    lines.append("## 一、 多梯度投资组合战绩总决算卡")
    lines.append("| 投资组合 / 维度 | 单期平均命中 | 理论随机基准 | 单码实际命中率 | 提升度 Lift (超额收益) | 操盘手评级 |")
    lines.append("|---|:---:|:---:|:---:|:---:|:---:|")

    t3 = summary["top3_metrics"]
    t5 = summary["top5_metrics"]
    t20 = summary["top20_core_metrics"]
    t25 = summary["top25_mid_metrics"]
    t30 = summary["top30_large_base_metrics"]
    p2 = summary["pick2_metrics"]

    lines.append(f"| **尖刀三胆 (Top3)** | **{t3['avg_hits']} 码** | 0.75 码 | {t3['hit_rate']} | **{t3['lift']}x** | {'🔥强效信标' if t3['lift'] >= 1.05 else '稳健'} |")
    lines.append(f"| **主力五胆 (Top5)** | **{t5['avg_hits']} 码** | 1.25 码 | {t5['hit_rate']} | **{t5['lift']}x** | {'🔥强效信标' if t5['lift'] >= 1.05 else '稳健'} |")
    lines.append(f"| **🔥 20 码极致主力** | **{t20['avg_hits']} 码** | 5.00 码 | {t20['hit_rate']} | **{t20['lift']}x** | {'🔥超额收敛' if t20['lift'] >= 1.02 else '达标'} |")
    lines.append(f"| **🎯 25 码精选进阶** | **{t25['avg_hits']} 码** | 6.25 码 | {t25['hit_rate']} | **{t25['lift']}x** | {'🔥高性价比' if t25['lift'] >= 1.02 else '达标'} |")
    lines.append(f"| **🛡️ 30 码黄金大底** | **{t30['avg_hits']} 码** | 7.50 码 | {t30['hit_rate']} | **{t30['lift']}x** | {'🔥高防守大底' if t30['avg_hits'] >= 8.0 else '达标'} |")
    lines.append(f"| **跨路对冲选2搭档** | 双中 **{p2['double_hits_count']} 次** | 6.01% 基线 | {p2['double_hit_rate']} | **{p2['lift']}x** | {'🔥超额进攻' if p2['lift'] >= 1.1 else '达标'} |")

    lines.append("")
    lines.append("## 二、 20码 / 25码 / 30码 命中分布与单期极值")
    lines.append(f"- **20 码主力**: 平均 **{t20['avg_hits']} 码** | 最高 **{t20['max_hit']} 码** | 最低 **{t20['min_hit']} 码** | $\\ge 6$ 码命中率: **{t20['rate_ge6_hits']}**")
    lines.append(f"- **25 码精选**: 平均 **{t25['avg_hits']} 码** | 最高 **{t25['max_hit']} 码** | 最低 **{t25['min_hit']} 码** | $\\ge 7$ 码命中率: **{t25['rate_ge7_hits']}**")
    lines.append(f"- **30 码大底**: 平均 **{t30['avg_hits']} 码** | 最高 **{t30['max_hit']} 码** | 最低 **{t30['min_hit']} 码** | $\\ge 8$ 码命中率: **{t30['rate_ge8_hits']}**")

    lines.append("")
    lines.append("## 三、 最近 10 期实战逐期真实对账单")
    lines.append("| 期号 | 官方实开 20 码摘要 | 20码主力命中 | 25码精选命中 | 30码大底命中 | 选2搭档双中情况 |")
    lines.append("|:---:|:---|:---:|:---:|:---:|:---|")
    for r in results[-10:]:
        d_str = " ".join(f"{x:02d}" for x in r["actual_draw"][:6]) + "..."
        p_hit_list = [f"{p['pair'][0]:02d}-{p['pair'][1]:02d}双全中🎯" for p in r["pairs"] if p["double_hit"]]
        p_str = "、".join(p_hit_list) if p_hit_list else "未双中"
        lines.append(f"| {r['period']} | {d_str} | **{r.get('hit_top20', 0)} 码** | **{r.get('hit_top25', 0)} 码** | **{r['hit_top30']} 码** | {p_str} |")

    return "\n".join(lines)


if __name__ == "__main__":
    n = 30
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        n = int(sys.argv[1])
    res = run_walk_forward_backtest(n_periods=n)
    print("\n" + generate_markdown_report(res, res["results_recent_10"]))
