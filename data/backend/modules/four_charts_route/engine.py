"""
四图走势与012路分路精确推演与回测引擎 (Four Charts Route Precision Engine)

【业务背景与架构定位】:
针对用户核心诉求：基于“图1(012路走势表) + 图2(尾数分布表) + 图3(16期大盘光谱表) + 遗漏动力学(0期连庄/1期隔期跳/2期回踩)”
构建全栈工业级数学量化推演与回测闭环。
彻底告别手工经验编造，全面实现算法化打分、样本外回测与每日历史台账落地。

@author Antigravity Quantitative Trading Team
@since 2026-10-13
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple, Optional, Set
import numpy as np

from backend.utils.history_loader import load_history

logger = logging.getLogger("four_charts_route")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class FourChartsRouteEngine:
    """
    四图走势与分路精确推演引擎
    """

    def __init__(self):
        """
        初始化引擎并加载历史开奖全量数据 (以期号升序组织)
        """
        raw_hist = load_history()
        self.history = []
        for h in raw_hist:
            try:
                period = int(h["issue"])
                nums = sorted([int(x) for x in h["numbers"]])
                if len(nums) == 20:
                    self.history.append({"period": period, "numbers": nums})
            except Exception:
                continue

        # 按期号升序排列 (最早在前，最新在后)
        self.history.sort(key=lambda x: x["period"])
        self.period_map = {item["period"]: item["numbers"] for item in self.history}
        self.all_periods = [item["period"] for item in self.history]

        self.output_dir = os.path.join("storage", "outputs", "four_charts")
        os.makedirs(self.output_dir, exist_ok=True)
        self.ledger_file = os.path.join(self.output_dir, "four_charts_ledger.json")

    def _get_history_slice(self, base_period: int) -> List[Dict[str, Any]]:
        """
        获取截止指定期号的历史切片（严格杜绝未来函数）
        """
        sub_list = [item for item in self.history if item["period"] <= base_period]
        if not sub_list:
            raise ValueError(f"未找到期号 <= {base_period} 的开奖记录")
        return sub_list

    def analyze_period(self, base_period: int) -> Dict[str, Any]:
        """
        核心解算方法：针对指定已开基准期，推演下一期 (base_period + 1) 的分路与号码战队

        // 步骤 1: 提取历史数据与最新开奖切片
        // 步骤 2: 解算图1 (012路走势动力学与均值回归配比)
        // 步骤 3: 解算图2 (尾数波浪动力学与冷热超跌度)
        // 步骤 4: 解算图3 (16期大盘光谱出入窗动能)
        // 步骤 5: 解算遗漏动力学 (0期连庄 / 1期隔期 / 2期回踩)
        // 步骤 6: 80码多因子全息综合打分与三路精锐筛选
        // 步骤 7: 生成结构化决策对象并持久化落盘
        """
        sub_list = self._get_history_slice(base_period)
        n_draws = len(sub_list)
        if n_draws < 30:
            raise ValueError("历史期数不足30期，无法执行四图深度解算")

        target_period = base_period + 1

        # 步骤 1: 提取最近 30 期开奖号码 (最新在最前，即 index 0 为 base_period)
        recent_draws = [sub_list[n_draws - 1 - i]["numbers"] for i in range(min(30, n_draws))]
        last_draw_set = set(recent_draws[0])

        # 步骤 2: 图1 (012路走势动力学)
        # 统计近 16 期各路开出数量
        road_counts_history = {0: [], 1: [], 2: []}
        for d in recent_draws[:16]:
            c0 = sum(1 for x in d if x % 3 == 0)
            c1 = sum(1 for x in d if x % 3 == 1)
            c2 = sum(1 for x in d if x % 3 == 2)
            road_counts_history[0].append(c0)
            road_counts_history[1].append(c1)
            road_counts_history[2].append(c2)

        last_c0 = road_counts_history[0][0]
        last_c1 = road_counts_history[1][0]
        last_c2 = road_counts_history[2][0]

        mean_c0 = float(np.mean(road_counts_history[0]))
        mean_c1 = float(np.mean(road_counts_history[1]))
        mean_c2 = float(np.mean(road_counts_history[2]))

        std_c0 = max(0.1, float(np.std(road_counts_history[0])))
        std_c1 = max(0.1, float(np.std(road_counts_history[1])))
        std_c2 = max(0.1, float(np.std(road_counts_history[2])))

        z_c0 = (last_c0 - mean_c0) / std_c0
        z_c1 = (last_c1 - mean_c1) / std_c1
        z_c2 = (last_c2 - mean_c2) / std_c2

        # 均值回归反弹势能：偏离为负（如上期被严重压制）则反弹势能高；偏离过热（如上期暴冲）则适度抑制
        road_rebound_potential = {
            0: max(0.2, 1.0 - 0.25 * z_c0),
            1: max(0.2, 1.0 - 0.25 * z_c1),
            2: max(0.2, 1.0 - 0.25 * z_c2),
        }

        # 步骤 3: 图2 (尾数波浪分布动力学)
        tail_counts_16 = {t: 0 for t in range(10)}
        for d in recent_draws[:16]:
            for x in d:
                tail_counts_16[x % 10] += 1

        last_tail_counts = {t: 0 for t in range(10)}
        for x in recent_draws[0]:
            last_tail_counts[x % 10] += 1

        tail_wave_score = {}
        for t in range(10):
            t_last = last_tail_counts[t]
            t_mean16 = tail_counts_16[t] / 16.0
            if t_last <= 1 and t_mean16 >= 1.8:
                score = 1.35  # 超跌刹车回弹位
            elif t_last >= 3:
                score = 1.15  # 热尾惯性位
            elif t_mean16 >= 2.0:
                score = 1.10  # 稳健中枢位
            else:
                score = 0.90  # 弱势尾数
            tail_wave_score[t] = score

        # 步骤 4: 图3 (16期大盘光谱出入窗动能)
        freq_16 = {num: 0 for num in range(1, 81)}
        for d in recent_draws[:16]:
            for x in d:
                freq_16[x] += 1

        out_window_draw = set(recent_draws[15]) if len(recent_draws) >= 16 else set()

        # 步骤 5: 遗漏动力学
        omission_dict = {}
        for num in range(1, 81):
            omis = 0
            for d in recent_draws:
                if num in d:
                    break
                omis += 1
            omission_dict[num] = omis

        # 步骤 6: 80 码多因子打分
        scores = {}
        for num in range(1, 81):
            r = num % 3
            t = num % 10
            f16 = freq_16[num]
            omis = omission_dict[num]

            # 基础频次分
            if 3 <= f16 <= 6:
                base_freq_score = 1.0 + (f16 - 3) * 0.1
            elif f16 > 6:
                base_freq_score = 1.25
            elif f16 == 2:
                base_freq_score = 0.90
            else:
                base_freq_score = 0.75

            # 出窗保频抗跌加成
            out_window_bonus = 1.15 if (num in out_window_draw and f16 >= 5) else 1.0

            # 遗漏层乘数
            if omis == 1:
                omis_mult = 1.30  # 隔期跳
            elif omis == 2:
                omis_mult = 1.20  # 温热回踩
            elif omis == 0:
                omis_mult = 1.15  # 连庄重号
            elif omis == 3:
                omis_mult = 1.05
            elif 4 <= omis <= 8:
                omis_mult = 0.95
            else:
                omis_mult = 0.85

            final_score = (
                base_freq_score
                * road_rebound_potential[r]
                * tail_wave_score[t]
                * out_window_bonus
                * omis_mult
            )
            scores[num] = round(float(final_score), 4)

        # 步骤 7: 分路提炼精锐部队
        route_pools = {0: [], 1: [], 2: []}
        for num in range(1, 81):
            r = num % 3
            route_pools[r].append((num, scores[num]))

        for r in [0, 1, 2]:
            route_pools[r].sort(key=lambda x: x[1], reverse=True)

        r0_top = [x[0] for x in route_pools[0][:5]]
        r1_top = [x[0] for x in route_pools[1][:5]]
        r2_top = [x[0] for x in route_pools[2][:5]]

        all_sorted = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top3_overall = [x[0] for x in all_sorted[:3]]

        top8_portfolio = [
            route_pools[0][0][0], route_pools[0][1][0], route_pools[0][2][0],
            route_pools[1][0][0], route_pools[1][1][0], route_pools[1][2][0],
            route_pools[2][0][0], route_pools[2][1][0]
        ]
        top8_portfolio = sorted(list(set(top8_portfolio)))

        repeat_candidates = [(num, scores[num]) for num in last_draw_set]
        repeat_candidates.sort(key=lambda x: x[1], reverse=True)
        repeat_top3 = [x[0] for x in repeat_candidates[:3]]

        pick2_pair = [top3_overall[0], top3_overall[1]]

        result = {
            "base_period": base_period,
            "target_period": target_period,
            "road_dynamics": {
                "last_ratio": f"{last_c0} : {last_c1} : {last_c2}",
                "z_scores": {"0路": round(z_c0, 2), "1路": round(z_c1, 2), "2路": round(z_c2, 2)},
                "expected_direction": {
                    "0": "超跌井喷反弹" if z_c0 < -0.8 else ("高位回落" if z_c0 > 0.8 else "稳健中枢"),
                    "1": "超跌井喷反弹" if z_c1 < -0.8 else ("高位回落" if z_c1 > 0.8 else "稳健中枢"),
                    "2": "超跌井喷反弹" if z_c2 < -0.8 else ("高位回落" if z_c2 > 0.8 else "稳健中枢"),
                }
            },
            "route_teams": {
                "0路精锐5码": r0_top,
                "1路精锐5码": r1_top,
                "2路精锐5码": r2_top,
            },
            "key_recommendations": {
                "尖刀最优3码": top3_overall,
                "黄金8码战队": top8_portfolio,
                "连庄3胆防守": repeat_top3,
                "黄金选2搭档": pick2_pair,
            },
            "scores_top15": [{"num": k, "score": v, "road": k % 3, "tail": k % 10, "omis": omission_dict[k]} for k, v in all_sorted[:15]]
        }

        period_file = os.path.join(self.output_dir, f"four_charts_route_{target_period}.json")
        with open(period_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return result

    def record_and_audit(self, target_period: int) -> Dict[str, Any]:
        """
        审计目标期的实战命中情况，并记录进历史总台账
        """
        if target_period not in self.period_map:
            return {"status": "pending", "message": f"第 {target_period} 期尚未开奖，无法对账"}

        actual_draw = set(self.period_map[target_period])
        pred_file = os.path.join(self.output_dir, f"four_charts_route_{target_period}.json")
        if not os.path.exists(pred_file):
            self.analyze_period(target_period - 1)

        with open(pred_file, "r", encoding="utf-8") as f:
            pred_data = json.load(f)

        r0 = set(pred_data["route_teams"]["0路精锐5码"])
        r1 = set(pred_data["route_teams"]["1路精锐5码"])
        r2 = set(pred_data["route_teams"]["2路精锐5码"])
        top3 = set(pred_data["key_recommendations"]["尖刀最优3码"])
        top8 = set(pred_data["key_recommendations"]["黄金8码战队"])
        pick2 = pred_data["key_recommendations"]["黄金选2搭档"]

        audit_res = {
            "target_period": target_period,
            "actual_draw": sorted(list(actual_draw)),
            "hit_r0": sorted(list(r0.intersection(actual_draw))),
            "hit_r1": sorted(list(r1.intersection(actual_draw))),
            "hit_r2": sorted(list(r2.intersection(actual_draw))),
            "hit_top3": sorted(list(top3.intersection(actual_draw))),
            "hit_top8": sorted(list(top8.intersection(actual_draw))),
            "pick2_pair": pick2,
            "hit_pick2": sum(1 for x in pick2 if x in actual_draw),
            "counts": {
                "r0_hit_count": len(r0.intersection(actual_draw)),
                "r1_hit_count": len(r1.intersection(actual_draw)),
                "r2_hit_count": len(r2.intersection(actual_draw)),
                "top3_hit_count": len(top3.intersection(actual_draw)),
                "top8_hit_count": len(top8.intersection(actual_draw)),
            }
        }

        ledger = {}
        if os.path.exists(self.ledger_file):
            try:
                with open(self.ledger_file, "r", encoding="utf-8") as f:
                    ledger = json.load(f)
            except Exception:
                ledger = {}

        ledger[str(target_period)] = audit_res
        with open(self.ledger_file, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)

        return audit_res

    def run_backtest(self, n_periods: int = 30) -> Dict[str, Any]:
        """
        样本外滚动回测 (Walk-Forward Backtest)
        验证该引擎在最近 n_periods 期的真实实战命中率
        """
        if len(self.all_periods) < n_periods + 35:
            raise ValueError("历史总期数不足以支持回测")

        test_periods = self.all_periods[-n_periods:]
        records = []

        for p in test_periods:
            base_p = p - 1
            self.analyze_period(base_p)
            audit = self.record_and_audit(p)
            records.append(audit)

        top3_hits = [r["counts"]["top3_hit_count"] for r in records]
        top8_hits = [r["counts"]["top8_hit_count"] for r in records]
        pick2_double_hits = sum(1 for r in records if r["hit_pick2"] == 2)
        pick2_single_hits = sum(1 for r in records if r["hit_pick2"] >= 1)

        summary = {
            "backtest_periods": n_periods,
            "start_period": test_periods[0],
            "end_period": test_periods[-1],
            "top3_avg_hit": round(float(np.mean(top3_hits)), 2),
            "top3_hit_rate": round(float(np.mean(top3_hits)) / 3.0, 4),
            "top8_avg_hit": round(float(np.mean(top8_hits)), 2),
            "top8_hit_rate": round(float(np.mean(top8_hits)) / 8.0, 4),
            "pick2_double_hit_rate": round(pick2_double_hits / float(n_periods), 4),
            "pick2_single_hit_rate": round(pick2_single_hits / float(n_periods), 4),
        }

        summary_file = os.path.join(self.output_dir, "backtest_summary.json")
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "records": records}, f, ensure_ascii=False, indent=2)

        return summary
