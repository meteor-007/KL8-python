# -*- coding: utf-8 -*-
"""
16 期窗口新方法 Walk-Forward 样本外滚动严苛对账测试 (零未来函数)
"""
import sys
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

def run_walk_forward_test(n_periods: int = 30):
    full_engine = FolkSixteenEngine()
    draws = full_engine.draws
    total_draws = len(draws)

    if total_draws < 50:
        print("数据量不足以进行滚动回测")
        return

    # 最近 n_periods 期的期号 (例如最近 30 期)
    test_indices = list(range(total_draws - n_periods, total_draws))

    grand_20_hits = []
    elite_12_hits = []
    golden_5_hits = []
    golden_3_hits = []

    print(f"\n{'='*75}")
    print(f"📊 16期窗口新方法 (Folk 16) 滚动 {n_periods} 期样本外实战盲测总账本")
    print(f"{'='*75}")
    print(f"  期号   | 实际开出20码 | 20大底命中 | 12精选命中 | 5金胆命中 | 3最优命中")
    print(f"{'-'*75}")

    for idx in test_indices:
        target_p = draws[idx]["period"]
        # 截断历史，物理屏蔽当前期及未来期数据
        past_draws = draws[:idx]
        engine_blind = FolkSixteenEngine(history_draws=past_draws)

        res = engine_blind.analyze_window(target_period=target_p)
        actual_set = draws[idx]["nums_set"]

        g20 = res["picks"]["grand_20"]
        e12 = res["picks"]["elite_12"]
        g5 = res["picks"]["golden_5"]
        g3 = res["picks"]["golden_3"]

        hit_20 = len(set(g20).intersection(actual_set))
        hit_12 = len(set(e12).intersection(actual_set))
        hit_5 = len(set(g5).intersection(actual_set))
        hit_3 = len(set(g3).intersection(actual_set))

        grand_20_hits.append(hit_20)
        elite_12_hits.append(hit_12)
        golden_5_hits.append(hit_5)
        golden_3_hits.append(hit_3)

        print(f" {target_p} |   20 码     |   {hit_20:02d} / 20   |   {hit_12:02d} / 12   |  {hit_5} / 5     |  {hit_3} / 3")

    avg_20 = np.mean(grand_20_hits)
    avg_12 = np.mean(elite_12_hits)
    avg_5 = np.mean(golden_5_hits)
    avg_3 = np.mean(golden_3_hits)

    rate_20 = avg_20 / 20.0
    rate_12 = avg_12 / 12.0
    rate_5 = avg_5 / 5.0
    rate_3 = avg_3 / 3.0

    lift_20 = rate_20 / 0.25
    lift_12 = rate_12 / 0.25
    lift_5 = rate_5 / 0.25
    lift_3 = rate_3 / 0.25

    print(f"{'='*75}")
    print(f"🏆 样本外 {n_periods} 期综合实测决算：")
    print(f"  • 大底 20 码：均期命中 {avg_20:.2f} 码 (单码胜率 {rate_20*100:.1f}%, 提升度 Lift: {lift_20:.2f}x)")
    print(f"  • 精选 12 码：均期命中 {avg_12:.2f} 码 (单码胜率 {rate_12*100:.1f}%, 提升度 Lift: {lift_12:.2f}x)")
    print(f"  • 核心 5 胆 ：均期命中 {avg_5:.2f} 码 (单码胜率 {rate_5*100:.1f}%, 提升度 Lift: {lift_5:.2f}x)")
    print(f"  • 最优 3 胆 ：均期命中 {avg_3:.2f} 码 (单码胜率 {rate_3*100:.1f}%, 提升度 Lift: {lift_3:.2f}x)")
    print(f"{'='*75}\n")

if __name__ == "__main__":
    run_walk_forward_test(30)
