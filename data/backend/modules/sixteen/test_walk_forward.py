# -*- coding: utf-8 -*-
"""通用严格无未来函数样本外回测对账脚本"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.abspath("."))
from backend.modules.sixteen.sixteen_engine import SixteenPeriodEngine, load_draws_from_file

def run_test(target_period_str: str = "2026247"):
    draws = load_draws_from_file()

    target_idx = None
    for i, d in enumerate(draws):
        if str(d.get("period")) == str(target_period_str):
            target_idx = i
            break

    if target_idx is None:
        print(f"未找到期号 {target_period_str}")
        return

    actual_draw = draws[target_idx]
    actual_period = actual_draw["period"]
    actual_date = actual_draw.get("date", "")
    actual_nums = sorted(list(set(actual_draw.get("sorted_nums") or actual_draw.get("nums") or [])))
    actual_set = set(actual_nums)

    # 物理严格截断：只给引擎 target_idx 之前的数据
    history_draws = draws[:target_idx]
    latest_in_history = history_draws[-1]["period"]
    latest_date = history_draws[-1].get("date", "")

    engine = SixteenPeriodEngine(history_draws)
    res = engine.analyze_at_index(len(history_draws) - 1)

    print("=" * 60)
    print(f"【严格样本外对账：完全物理屏蔽 {actual_period} 及未来数据】")
    print(f"已知历史截止期：第 {latest_in_history} 期（{latest_date}）")
    print(f"预测目标期号  ：第 {res.get('target_period')} 期（第 {actual_period} 期）")
    print(f"实际开奖 20 码：{' '.join(f'{x:02d}' for x in actual_nums)}")
    print("=" * 60)

    # 1. 方法 1: 动量先锋最优 3 码
    tip3 = res.get("ops_tip3") or res.get("medium_top5") or []
    tip3_hits = [n for n in tip3 if n in actual_set]
    print(f"【方法 1 · 动量先锋最优 3 码】: {' '.join(f'{x:02d}' for x in tip3)}")
    print(f"   -> 实际命中: {len(tip3_hits)}/3 码 ({' '.join(f'{x:02d}' for x in tip3_hits) or '无'}) 命中率 {len(tip3_hits)/len(tip3)*100:.1f}%")

    # 2. 方法 2: 确定性混剪 6 码
    m2 = res.get("method2") or {}
    six = m2.get("six") or res.get("ops_method2_six") or []
    six_hits = [n for n in six if n in actual_set]
    print(f"\n【方法 2 · 确定性混剪 6 码】: {' '.join(f'{x:02d}' for x in six)}")
    print(f"   -> 实际命中: {len(six_hits)}/6 码 ({' '.join(f'{x:02d}' for x in six_hits) or '无'}) 命中率 {len(six_hits)/len(six)*100:.1f}%")

    # 3. 方法 3: 高斯遗漏回补 3 胆
    gold = res.get("gold_dan")
    silver = res.get("silver_dan")
    bronze = res.get("bronze_dan")
    dans = [n for n in [gold, silver, bronze] if n is not None]
    dan_hits = [n for n in dans if n in actual_set]
    g_str = f"{gold:02d}" if gold else "—"
    s_str = f"{silver:02d}" if silver else "—"
    b_str = f"{bronze:02d}" if bronze else "—"
    print(f"\n【方法 3 · 高斯回补 3 胆】: 金胆[{g_str}] 银胆[{s_str}] 铜胆[{b_str}]")
    print(f"   -> 实际命中: {len(dan_hits)}/3 码 ({' '.join(f'{x:02d}' for x in dan_hits) or '无'})")

    # 4. 方法 4: 16窗动量×回补双飞选2
    pairs = res.get("pick2_pairs") or []
    print(f"\n【方法 4 · 16窗动量×回补双飞选 2】(前 4 组):")
    for p in pairs[:4]:
        pair_nums = p.get("pair") or []
        hit_cnt = sum(1 for n in pair_nums if n in actual_set)
        hit_nums = [n for n in pair_nums if n in actual_set]
        status = "★★★ 双全中! ★★★" if hit_cnt == 2 else (f"中 1 码 ({' '.join(f'{x:02d}' for x in hit_nums)})" if hit_cnt == 1 else "挂")
        print(f"   - 组合 {p.get('pair_str')} [{p.get('kind', '')}]: {status}")

    # 5. 频次桶精选池
    fbp = res.get("freq_bucket_picks") or {}
    all_picks = fbp.get("all_picks") or []
    all_pick_hits = [n for n in all_picks if n in actual_set]
    print(f"\n【频次桶实战精选池】(共推荐 {len(all_picks)} 码): {' '.join(f'{x:02d}' for x in all_picks)}")
    print(f"   -> 实际命中: {len(all_pick_hits)}/{len(all_picks)} 码 命中率 {len(all_pick_hits)/len(all_picks)*100:.1f}% (基准 25.0%)")

    print("\n--- 各频次桶命中明细 ---")
    for bk in fbp.get("buckets") or []:
        p_nums = bk.get("picks") or []
        r_nums = bk.get("rests") or []
        p_hits = [n for n in p_nums if n in actual_set]
        r_hits = [n for n in r_nums if n in actual_set]
        if bk.get("pool_size", 0) > 0:
            print(f"  {bk['freq_label']} (总{bk['pool_size']}码): 精选{len(p_nums)}中{len(p_hits)} ({' '.join(f'{x:02d}' for x in p_hits) or '—'}) | 剩余{len(r_nums)}中{len(r_hits)} ({' '.join(f'{x:02d}' for x in r_hits) or '—'})")

    # 6. 出窗号动态验证
    out_draw = draws[target_idx - 16] if target_idx >= 16 else None
    if out_draw:
        out_period = out_draw["period"]
        out_nums = set(out_draw.get("sorted_nums") or out_draw.get("nums") or [])
        out_hits = out_nums & actual_set
        print(f"\n【出窗号动态验证】(第 {out_period} 期开出的 20 码在当期的留存):")
        print(f"   -> 20 码出窗号在第 {actual_period} 期连庄开出 {len(out_hits)} 个: {' '.join(f'{x:02d}' for x in sorted(list(out_hits)))}")

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "2026247"
    run_test(p)
