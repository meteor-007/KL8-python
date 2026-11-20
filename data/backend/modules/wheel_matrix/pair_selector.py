# -*- coding: utf-8 -*-
"""
极简选2黄金搭档决策引擎 (Pair Selector)
依据 Gail Howard 伴侣数共现规律、黄金跨度与双底形态设计
"""
from typing import List, Dict, Tuple, Any
from collections import defaultdict
from .models import LotteryGameSpec, DrawRecord

class PairSelector:
    def __init__(self, spec: LotteryGameSpec):
        self.spec = spec
        self.mid_point = spec.main_pool // 2

    def select_best_pairs(
        self,
        draws: List[DrawRecord],
        scored_balls: List[Dict[str, Any]],
        top_n_candidates: int = 10
    ) -> List[Dict[str, Any]]:
        # 1. 统计全历史数对共现频次 (Co-occurrence Frequency)
        pair_counts = defaultdict(int)
        for d in draws:
            balls = d.main_balls
            for i in range(len(balls)):
                for j in range(i + 1, len(balls)):
                    p = (min(balls[i], balls[j]), max(balls[i], balls[j]))
                    pair_counts[p] += 1

        # 2. 候选球池
        candidates = [b["ball"] for b in scored_balls[:top_n_candidates]]
        score_lookup = {b["ball"]: b["score"] for b in scored_balls}
        feature_lookup = {b["ball"]: b["features"] for b in scored_balls}

        evaluated_pairs = []
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                b1, b2 = candidates[i], candidates[j]
                p = (min(b1, b2), max(b1, b2))
                co_hits = pair_counts[p]
                s1 = score_lookup[b1]
                s2 = score_lookup[b2]
                f1 = feature_lookup[b1]
                f2 = feature_lookup[b2]

                # 奇偶平衡加分 (1奇1偶 +10分)
                odd_bonus = 10.0 if ((b1 % 2) != (b2 % 2)) else 0.0

                # 大小平衡加分 (1大1小 +10分)
                hl_bonus = 10.0 if ((b1 <= self.mid_point and b2 > self.mid_point) or (b2 <= self.mid_point and b1 > self.mid_point)) else 0.0

                # 黄金跨度加分 (跨度在 8~20 区间 +10分)
                span = abs(b1 - b2)
                span_bonus = 10.0 if (8 <= span <= 20) else (5.0 if 4 <= span <= 24 else 0.0)

                # 双底同频跳出加分
                sync_bottom_bonus = 12.0 if (f1.get("is_double_bottom") and f2.get("is_double_bottom")) else 0.0

                total_pair_score = (s1 + s2) / 2.0 + co_hits * 4.5 + odd_bonus + hl_bonus + span_bonus + sync_bottom_bonus

                evaluated_pairs.append({
                    "pair": list(p),
                    "score": round(total_pair_score, 2),
                    "co_hits": co_hits,
                    "span": span,
                    "b1_score": s1,
                    "b2_score": s2,
                    "b1_skip": f1.get("current_skip", 0),
                    "b2_skip": f2.get("current_skip", 0),
                    "type": "黄金跨度平衡对" if hl_bonus > 0 and odd_bonus > 0 else "双底共振核心对"
                })

        evaluated_pairs.sort(key=lambda x: x["score"], reverse=True)
        return evaluated_pairs[:5]
