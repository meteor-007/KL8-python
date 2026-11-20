# -*- coding: utf-8 -*-
"""
时序趋势与走势形态分析引擎 (Skip State & Pattern Recognition Engine)
依据 Gail Howard 第二章《趋势是你的朋友》设计
"""
import numpy as np
from typing import List, Dict, Any, Optional
from .models import DrawRecord, LotteryGameSpec

class TrendEngine:
    def __init__(self, spec: LotteryGameSpec):
        self.spec = spec
        self.num_balls = spec.main_pool
        self.history_draws: List[DrawRecord] = []
        self.skip_histories: Dict[int, List[int]] = {i: [] for i in range(1, self.num_balls + 1)}
        self.current_skips: np.ndarray = np.zeros(self.num_balls + 1, dtype=int)

    def load_history(self, draws: List[DrawRecord]):
        self.history_draws = draws
        self.skip_histories = {i: [] for i in range(1, self.num_balls + 1)}
        self.current_skips = np.zeros(self.num_balls + 1, dtype=int)

        for d in draws:
            hit_set = set(d.main_balls)
            for ball in range(1, self.num_balls + 1):
                if ball in hit_set:
                    self.skip_histories[ball].append(int(self.current_skips[ball]))
                    self.current_skips[ball] = 0
                else:
                    self.current_skips[ball] += 1

    def analyze_ball(self, ball: int) -> Dict[str, Any]:
        history = self.skip_histories[ball]
        curr = int(self.current_skips[ball])
        total_hits = len(history)
        expected_hits = len(self.history_draws) * (self.spec.main_pick / self.spec.main_pool) if self.history_draws else 1.0
        
        hit_ratio = (total_hits / max(0.001, expected_hits)) * 100.0
        mean_skip = float(np.mean(history)) if history else float(self.spec.main_pool / self.spec.main_pick)
        median_skip = float(np.median(history)) if history else mean_skip

        # 1. 双底 / 三倍底形态识别 (Double / Triple Bottom)
        double_bottom = False
        triple_bottom = False
        if len(history) >= 2:
            last_1 = history[-1]
            last_2 = history[-2]
            if abs(last_1 - curr) <= 1 and curr <= 7:
                double_bottom = True
                if len(history) >= 3 and abs(last_2 - last_1) <= 1:
                    triple_bottom = True

        # 2. 50期 / 10期 短期动量
        recent_10_hits = 0
        recent_50_hits = 0
        if self.history_draws:
            recent_10 = self.history_draws[-10:]
            recent_50 = self.history_draws[-50:]
            recent_10_hits = sum(1 for d in recent_10 if ball in d.main_balls)
            recent_50_hits = sum(1 for d in recent_50 if ball in d.main_balls)

        # 3. 相邻号 / 斜连号特征 (与上期开奖号的邻近关系)
        last_draw_balls = self.history_draws[-1].main_balls if self.history_draws else []
        is_repeat = ball in last_draw_balls
        is_neighbor = any(abs(ball - b) == 1 for b in last_draw_balls)

        return {
            "ball": ball,
            "current_skip": curr,
            "mean_skip": round(mean_skip, 2),
            "median_skip": round(median_skip, 2),
            "total_hits": total_hits,
            "hit_ratio_pct": round(hit_ratio, 1),
            "recent_10_hits": recent_10_hits,
            "recent_50_hits": recent_50_hits,
            "is_double_bottom": double_bottom,
            "is_triple_bottom": triple_bottom,
            "is_repeat": is_repeat,
            "is_neighbor": is_neighbor
        }

    def get_all_features(self) -> Dict[int, Dict[str, Any]]:
        return {b: self.analyze_ball(b) for b in range(1, self.num_balls + 1)}
