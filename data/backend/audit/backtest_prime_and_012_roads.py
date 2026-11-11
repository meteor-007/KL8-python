# -*- coding: utf-8 -*-
"""
快乐8 质合数与012路好码全方位滚动回测对账引擎 (Walk-Forward Rolling Backtester)
====================================================================================
【业务背景与架构定位】:
本模块专为严格验证“质合数小池塘”、“孪生质数连体雷达”与“012路好码理论”三大算法的真实实战威力打造：
1. 样本外滚动机制 (Walk-Forward):
   - 在历史第 i 期，绝不窥探未来任何数据 (Strict No-Lookahead Bias)；
   - 仅利用第 i 期及之前的开奖历史推演第 i-1 期 (即未来一期)；
   - 逐期对账实际开奖号码，记录真实命中红白账单。

2. 全方位多维评价指标:
   - 方案三 (质数VIP池 Top5): 平均每期命中球数、单码实际命中率、相对大盘基线(25.0%)的提升度 (Lift)、命中>=2码/3码覆盖率；
   - 方案四 (孪生连体质数): 选2双全中率、中1率、相对独立随机双中基线 (6.01%) 的提升倍数；
   - 012路各路精选好码: 0路先锋、1路极品、2路中枢各自的实战单码命中率与稳定性；
   - 跨路对冲搭档: 跨路选2组合的真实双中率与对冲回避率。

@author Antigravity Quantitative Team
@since 2026-09-04
"""

import os
import sys
import collections
from typing import List, Dict, Any, Tuple

# 步骤 1: 路径与环境配置
_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = os.path.dirname(_DIR)
_ROOT_DIR = os.path.dirname(_PROJ_DIR)
for p in [_ROOT_DIR, _PROJ_DIR, _DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.utils.history_loader import load_history

PRIME_SET = {
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
    31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79
}

TWIN_PAIRS = [
    (3, 5), (5, 7), (11, 13), (17, 19),
    (29, 31), (41, 43), (59, 61), (71, 73)
]


class RollingQuantBacktester:
    """
    质数合数与 012 路好码全方位滚动回测器
    """

    def __init__(self, history_limit: int = 1500):
        self.all_history = load_history(limit=history_limit)
        self.total_records = len(self.all_history)

    def run_backtest(self, test_periods: int = 100) -> Dict[str, Any]:
        """
        执行严格无未来函数的滚动样本外对账
        
        @param test_periods 回测滚动的期数 (如最近 100 期或 200 期)
        @return 全方位回测决算指标字典
        """
        if self.total_records < test_periods + 50:
            test_periods = max(10, self.total_records - 50)

        # 统计账本容器
        # 1. 方案三 (质数池 Top 5)
        p3_hits_dist = collections.Counter()  # 命中0个, 1个, 2个...
        p3_total_hits = 0
        p3_total_recs = test_periods * 5

        # 2. 方案四 (孪生连体 Top 1)
        p4_double_hits = 0  # 选2双全中
        p4_single_hits = 0  # 选2中1
        p4_zero_hits = 0    # 选2中0
        p4_twin_hit_records = []

        # 3. 012路各路好码统计
        r0_hits = 0
        r0_total_picks = 0
        r1_hits = 0
        r1_total_picks = 0
        r2_hits = 0
        r2_total_picks = 0

        # 4. 跨路对冲选2搭档
        cross_double_hits = 0
        cross_single_hits = 0
        cross_zero_hits = 0

        # 逐期回测：从第 test_periods - 1 到 0 倒序滚动
        # 对于每个 index，i 代表未来验证期，i+1 代表当期可用的最后历史截面
        for idx in range(test_periods - 1, -1, -1):
            target_draw = self.all_history[idx]               # 未来真实开奖 (用于验证)
            available_history = self.all_history[idx + 1 :]    # 当期可用历史 (严防偷看未来)

            actual_nums = set(target_draw.get("numbers", []))
            target_issue = str(target_draw.get("issue") or target_draw.get("period") or "")

            # -------------------------------------------------------------
            # A. 运行方案三：质数小池塘 Top 5 算法
            # -------------------------------------------------------------
            prime_scores = self._calc_prime_pool_at_point(available_history)
            prime_top5 = [x[0] for x in prime_scores[:5]]
            hit_p3 = sum(1 for n in prime_top5 if n in actual_nums)
            p3_hits_dist[hit_p3] += 1
            p3_total_hits += hit_p3

            # -------------------------------------------------------------
            # B. 运行方案四：孪生质数连体雷达 Top 1 搭档
            # -------------------------------------------------------------
            best_twin = self._calc_twin_radar_at_point(available_history)
            t1, t2 = best_twin
            t_hit = (1 if t1 in actual_nums else 0) + (1 if t2 in actual_nums else 0)
            if t_hit == 2:
                p4_double_hits += 1
                p4_twin_hit_records.append({
                    "period": target_issue,
                    "pair": f"{t1:02d}-{t2:02d}",
                    "result": "双全中"
                })
            elif t_hit == 1:
                p4_single_hits += 1
            else:
                p4_zero_hits += 1

            # -------------------------------------------------------------
            # C. 运行 012 路好码评分算法
            # -------------------------------------------------------------
            good_r0, good_r1, good_r2, best_cross = self._calc_012_goods_at_point(available_history)
            
            # 0路好码 Top 5 命中情况
            r0_picks = [x[0] for x in good_r0[:5]]
            r0_hits += sum(1 for n in r0_picks if n in actual_nums)
            r0_total_picks += len(r0_picks)

            # 1路好码 Top 4 命中情况
            r1_picks = [x[0] for x in good_r1[:4]]
            r1_hits += sum(1 for n in r1_picks if n in actual_nums)
            r1_total_picks += len(r1_picks)

            # 2路好码 Top 5 命中情况
            r2_picks = [x[0] for x in good_r2[:5]]
            r2_hits += sum(1 for n in r2_picks if n in actual_nums)
            r2_total_picks += len(r2_picks)

            # 跨路对冲搭档命中情况
            c1, c2 = best_cross
            c_hit = (1 if c1 in actual_nums else 0) + (1 if c2 in actual_nums else 0)
            if c_hit == 2:
                cross_double_hits += 1
            elif c_hit == 1:
                cross_single_hits += 1
            else:
                cross_zero_hits += 1

        # -------------------------------------------------------------
        # 全方位决算指标汇总 (严格数学基线对账)
        # -------------------------------------------------------------
        # 1. 方案三质数 Top5
        p3_avg_hit = round(p3_total_hits / float(test_periods), 2)
        p3_hit_rate = round((p3_total_hits / float(p3_total_recs)) * 100.0, 2)
        p3_lift = round(p3_hit_rate / 25.0, 2)  # 相对大盘 25% 的提升度
        p3_hit_ge1_rate = round(((test_periods - p3_hits_dist[0]) / float(test_periods)) * 100.0, 2)
        p3_hit_ge2_rate = round((sum(p3_hits_dist[k] for k in range(2, 6)) / float(test_periods)) * 100.0, 2)

        # 2. 方案四孪生质数选2
        p4_double_rate = round((p4_double_hits / float(test_periods)) * 100.0, 2)
        p4_single_rate = round((p4_single_hits / float(test_periods)) * 100.0, 2)
        p4_at_least_one = round(((p4_double_hits + p4_single_hits) / float(test_periods)) * 100.0, 2)
        # 理论随机选2双中率: 20/80 * 19/79 = 6.01%
        p4_lift = round(p4_double_rate / 6.01, 2)

        # 3. 012路各路好码单码命中率
        r0_rate = round((r0_hits / float(r0_total_picks)) * 100.0, 2) if r0_total_picks > 0 else 0.0
        r1_rate = round((r1_hits / float(r1_total_picks)) * 100.0, 2) if r1_total_picks > 0 else 0.0
        r2_rate = round((r2_hits / float(r2_total_picks)) * 100.0, 2) if r2_total_picks > 0 else 0.0
        r0_lift = round(r0_rate / 25.0, 2)
        r1_lift = round(r1_rate / 25.0, 2)
        r2_lift = round(r2_rate / 25.0, 2)

        # 4. 跨路选2搭档
        cross_double_rate = round((cross_double_hits / float(test_periods)) * 100.0, 2)
        cross_single_rate = round((cross_single_hits / float(test_periods)) * 100.0, 2)
        cross_lift = round(cross_double_rate / 6.01, 2)

        return {
            "test_periods": test_periods,
            "sample_range": f"从第 {self.all_history[test_periods-1].get('issue')} 期 至 第 {self.all_history[0].get('issue')} 期",
            "prime_top5_metrics": {
                "avg_hits_per_period": p3_avg_hit,
                "single_hit_rate": p3_hit_rate,
                "lift_over_baseline": p3_lift,
                "hit_ge1_rate": p3_hit_ge1_rate,
                "hit_ge2_rate": p3_hit_ge2_rate,
                "hits_distribution": dict(p3_hits_dist)
            },
            "twin_prime_metrics": {
                "double_hit_count": p4_double_hits,
                "double_hit_rate": p4_double_rate,
                "single_hit_count": p4_single_hits,
                "single_hit_rate": p4_single_rate,
                "at_least_one_rate": p4_at_least_one,
                "lift_over_random": p4_lift,
                "double_hit_history": p4_twin_hit_records
            },
            "road_012_good_metrics": {
                "r0_hit_rate": r0_rate,
                "r0_lift": r0_lift,
                "r1_hit_rate": r1_rate,
                "r1_lift": r1_lift,
                "r2_hit_rate": r2_rate,
                "r2_lift": r2_lift
            },
            "cross_pair_metrics": {
                "double_hit_count": cross_double_hits,
                "double_hit_rate": cross_double_rate,
                "single_hit_rate": cross_single_rate,
                "lift_over_random": cross_lift
            }
        }

    def _calc_prime_pool_at_point(self, history: List[Dict[str, Any]]) -> List[Tuple[int, float]]:
        """在指定时间截面上计算 22 个质数的动能评分"""
        total = len(history)
        sample30 = history[:30]
        f30 = collections.Counter()
        for r in sample30:
            for n in r.get("numbers", []):
                f30[n] += 1

        omissions = {}
        for p in PRIME_SET:
            omit = -1
            for idx, r in enumerate(history):
                if p in set(r.get("numbers", [])):
                    omit = idx
                    break
            omissions[p] = omit if omit != -1 else total

        scores = []
        for p in sorted(list(PRIME_SET)):
            omit = omissions[p]
            f = f30[p]
            # 引入防深冷陷阱衰减: 遗漏超过8期后弹性收益衰减
            if 3 <= omit <= 7:
                reb = (omit / 4.0) * 15.0
            elif omit >= 8:
                reb = (8.0 / omit) * 15.0  # 防冷号死睡
            else:
                reb = 5.0
            momentum = (f / 7.5) * 35.0
            total_score = round(reb + momentum, 2)
            scores.append((p, total_score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _calc_twin_radar_at_point(self, history: List[Dict[str, Any]]) -> Tuple[int, int]:
        """在指定时间截面上计算紧绷度最高的孪生质数搭档"""
        total = len(history)
        best_pair = (29, 31)
        max_tension = -1.0

        for pair in TWIN_PAIRS:
            n1, n2 = pair
            last_hit_idx = -1
            intervals = []
            for idx, r in enumerate(history):
                nums = set(r.get("numbers", []))
                if n1 in nums and n2 in nums:
                    if last_hit_idx != -1:
                        intervals.append(idx - last_hit_idx)
                    else:
                        current_omit = idx
                    last_hit_idx = idx

            if last_hit_idx == -1:
                current_omit = total

            avg_interval = (sum(intervals) / float(len(intervals))) if intervals else 16.6
            tension = current_omit / (avg_interval if avg_interval > 0 else 16.6)
            if tension > max_tension:
                max_tension = tension
                best_pair = pair

        return best_pair

    def _calc_012_goods_at_point(self, history: List[Dict[str, Any]]) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]], List[Tuple[int, float]], Tuple[int, int]]:
        """在指定时间截面上评估 012 路好码与跨路对冲搭档"""
        latest_nums = set(history[0].get("numbers", [])) if history else set()
        sample30 = history[:30]
        f30 = collections.Counter()
        for r in sample30:
            for n in r.get("numbers", []):
                f30[n] += 1

        omissions = {}
        for num in range(1, 81):
            omit = -1
            for idx, r in enumerate(history):
                if num in set(r.get("numbers", [])):
                    omit = idx
                    break
            omissions[num] = omit if omit != -1 else len(history)

        def score_pool(road_rem: int):
            pool = [n for n in range(1, 81) if n % 3 == road_rem]
            res = []
            for n in pool:
                omit = omissions[n]
                freq = f30[n]
                is_neighbor = (n - 1 in latest_nums) or (n + 1 in latest_nums)
                n_boost = 1.25 if is_neighbor else 1.0
                rep_boost = 1.15 if n in latest_nums else 1.0
                reb = (omit / 4.0) if omit <= 8 else (8.0 / omit)
                score = round((freq * 1.5 + reb * 5.0) * n_boost * rep_boost, 2)
                res.append((n, score))
            res.sort(key=lambda x: x[1], reverse=True)
            return res

        g0 = score_pool(0)
        g1 = score_pool(1)
        g2 = score_pool(2)

        # 选跨路对冲搭档
        b0 = g0[0][0] if g0 else 24
        b2 = next((x[0] for x in g2 if x[0] in PRIME_SET), 47)
        cross_pair = (b0, b2)

        return g0, g1, g2, cross_pair


def main():
    print("=" * 65)
    print(" 🧬 启动质合数与 012 路好码全方位滚动样本外实战回测对账")
    print("=" * 65)

    backtester = RollingQuantBacktester(history_limit=1800)
    
    for periods in [50, 100, 200]:
        print(f"\n--- 正在执行近 {periods} 期严格 Walk-Forward 滚动实测 ---")
        res = backtester.run_backtest(test_periods=periods)
        
        p3 = res["prime_top5_metrics"]
        p4 = res["twin_prime_metrics"]
        r = res["road_012_good_metrics"]
        cr = res["cross_pair_metrics"]

        print(f"■ 测试样本区间: {res['sample_range']} (共实测 {periods} 期)")
        print(f"■ 【方案三: 22质数池 Top 5 金牌对账】:")
        print(f"   - 平均每期命中: {p3['avg_hits_per_period']} 个 / 5码")
        print(f"   - 单码实际命中率: {p3['single_hit_rate']}% (大盘基线 25.0% | 提升度 Lift: {p3['lift_over_baseline']}x)")
        print(f"   - 命中 >= 1码覆盖率: {p3['hit_ge1_rate']}%")
        print(f"   - 命中 >= 2码覆盖率: {p3['hit_ge2_rate']}%")
        print(f"   - 命中分布: 0中={p3['hits_distribution'].get(0,0)}期, 1中={p3['hits_distribution'].get(1,0)}期, 2中={p3['hits_distribution'].get(2,0)}期, 3中={p3['hits_distribution'].get(3,0)}期, 4中={p3['hits_distribution'].get(4,0)}期")

        print(f"\n■ 【方案四: 8对孪生质数连体雷达 选2实测对账】:")
        print(f"   - 选2双全中次数: {p4['double_hit_count']} 次 (双全中率: {p4['double_hit_rate']}%)")
        print(f"   - 相对理论随机基线(6.01%) 提升倍数: {p4['lift_over_random']}x")
        print(f"   - 选2中1次数: {p4['single_hit_count']} 次 (中1率: {p4['single_hit_rate']}%)")
        print(f"   - 至少中1码防守胜率: {p4['at_least_one_rate']}%")

        print(f"\n■ 【012路好码实战对账 (单码命中率)】:")
        print(f"   - 0路先锋好码命中率: {r['r0_hit_rate']}% (提升度 Lift: {r['r0_lift']}x)")
        print(f"   - 1路极品好码命中率: {r['r1_hit_rate']}% (提升度 Lift: {r['r1_lift']}x)")
        print(f"   - 2路中枢好码命中率: {r['r2_hit_rate']}% (提升度 Lift: {r['r2_lift']}x)")

        print(f"\n■ 【跨路对冲选2搭档 (0路合数 + 2路质数)】:")
        print(f"   - 双全中率: {cr['double_hit_rate']}% (提升度 Lift: {cr['lift_over_random']}x)")
        print(f"   - 至少中1码对冲覆盖率: {cr['double_hit_rate'] + cr['single_hit_rate']:.2f}%")
        print("-" * 65)

    # 落盘持久化回测账本
    import json
    out_file = os.path.join(_ROOT_DIR, "storage", "reviews", "prime_012_backtest_ledger.json")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    full_200 = backtester.run_backtest(test_periods=200)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(full_200, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 全方位回测决算账本已落盘: {out_file}")


if __name__ == "__main__":
    main()
