# -*- coding: utf-8 -*-
"""
最佳号码记分板决策引擎 (Best Number Scoreboard)
依据 Gail Howard 第四章第12节《最佳号码记分板》设计
"""
from typing import List, Dict, Any, Tuple
from .models import LotteryGameSpec
from .trend_engine import TrendEngine

class ScoreboardEngine:
    def __init__(self, spec: LotteryGameSpec, weights: Dict[str, float] = None):
        self.spec = spec
        self.weights = weights or {
            "golden_skip": 0.35,      # 0~5期黄金遗漏区
            "pattern_bottom": 0.25,   # 双底/三倍底形态
            "momentum_50": 0.20,      # 50期冷热回归动量
            "neighbor_affinity": 0.20 # 邻号与斜连号
        }

    def evaluate(self, trend_engine: TrendEngine) -> Dict[str, Any]:
        features_map = trend_engine.get_all_features()
        scored_balls = []

        for ball, feat in features_map.items():
            curr_skip = feat["current_skip"]
            score = 0.0

            # 1. 遗漏时序评分 (0~5期遗漏获得高斯衰减优选分)
            if curr_skip == 0:
                score += self.weights["golden_skip"] * 85.0   # 重号 (约12%概率)
            elif 1 <= curr_skip <= 3:
                score += self.weights["golden_skip"] * 100.0  # 1~3期黄金最高发区
            elif 4 <= curr_skip <= 6:
                score += self.weights["golden_skip"] * 75.0   # 4~6期次优区
            elif 7 <= curr_skip <= 10:
                score += self.weights["golden_skip"] * 45.0
            else:
                score += self.weights["golden_skip"] * max(5.0, 30.0 - (curr_skip - 10) * 3.0)

            # 2. 形态评分 (双底 / 三倍底反弹)
            if feat["is_triple_bottom"]:
                score += self.weights["pattern_bottom"] * 100.0
            elif feat["is_double_bottom"]:
                score += self.weights["pattern_bottom"] * 85.0
            else:
                score += self.weights["pattern_bottom"] * 20.0

            # 3. 中期动量与均值回归评分 (50期热度)
            exp_50 = 50.0 * (self.spec.main_pick / self.spec.main_pool)
            ratio_50 = feat["recent_50_hits"] / max(1.0, exp_50)
            if 0.8 <= ratio_50 <= 1.3:
                score += self.weights["momentum_50"] * 100.0 # 适度温热号最佳
            elif ratio_50 > 1.3:
                score += self.weights["momentum_50"] * 70.0  # 过热需警惕
            else:
                score += self.weights["momentum_50"] * 40.0  # 偏冷

            # 4. 邻号牵引
            if feat["is_neighbor"]:
                score += self.weights["neighbor_affinity"] * 100.0
            elif feat["is_repeat"]:
                score += self.weights["neighbor_affinity"] * 80.0
            else:
                score += self.weights["neighbor_affinity"] * 30.0

            scored_balls.append({
                "ball": ball,
                "score": round(score, 2),
                "features": feat
            })

        # 按得分从高到低排序
        scored_balls.sort(key=lambda x: x["score"], reverse=True)

        # 分级号码池
        # Tier 1 (胆码候选): 前 2 个最高分
        # Tier 2 (拖码优选): 接下来的 10~14 个号
        # Tier 3 (冷态排除): 剩余低分号
        tier_1 = [item["ball"] for item in scored_balls[:2]]
        tier_2 = [item["ball"] for item in scored_balls[2:14]]
        tier_3 = [item["ball"] for item in scored_balls[14:]]

        return {
            "scoreboard": scored_balls,
            "tier_1_bankers": tier_1,
            "tier_2_pool": sorted(tier_2),
            "tier_3_excluded": sorted(tier_3),
            "combined_candidate_pool": sorted(tier_1 + tier_2)
        }
