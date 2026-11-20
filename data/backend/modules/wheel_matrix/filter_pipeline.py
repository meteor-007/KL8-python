# -*- coding: utf-8 -*-
"""
多级高效缩水过滤管道 (High-Performance Multi-Stage Filter Pipeline)
依据 Gail Howard 第一章《平衡选号》与第四章《负面模式过滤》设计
"""
from typing import List, Tuple, Dict, Any
from .models import LotteryGameSpec, FilterConfig

class FilterPipeline:
    def __init__(self, spec: LotteryGameSpec, config: FilterConfig = None):
        self.spec = spec
        self.config = config or FilterConfig()
        self.mid_point = spec.main_pool // 2

        # 默认黄金和值区间
        if self.config.sum_range is None:
            self.config.sum_range = spec.default_golden_sum_range

        # 默认奇偶比与大小比 (2:4, 3:3, 4:2 选6型 / 2:3, 3:2 选5型)
        if self.config.allowed_odd_counts is None:
            if spec.main_pick == 6:
                self.config.allowed_odd_counts = (2, 3, 4)
            elif spec.main_pick == 5:
                self.config.allowed_odd_counts = (2, 3)
            else:
                self.config.allowed_odd_counts = tuple(range(1, spec.main_pick))

        if self.config.allowed_high_counts is None:
            if spec.main_pick == 6:
                self.config.allowed_high_counts = (2, 3, 4)
            elif spec.main_pick == 5:
                self.config.allowed_high_counts = (2, 3)
            else:
                self.config.allowed_high_counts = tuple(range(1, spec.main_pick))

    def check_ticket(self, ticket: List[int]) -> Tuple[bool, str]:
        """单注校验，返回 (是否通过, 拒绝原因)"""
        # 1. 和值过滤 (Sum Filter)
        s = sum(ticket)
        min_s, max_s = self.config.sum_range
        if not (min_s <= s <= max_s):
            return False, f"和值 {s} 不在黄金区间 [{min_s}, {max_s}] 内"

        # 2. 奇偶比过滤 (Odd-Even Ratio Filter)
        odds = sum(1 for x in ticket if (x & 1))
        if odds not in self.config.allowed_odd_counts:
            return False, f"奇数个数 {odds} (奇偶比 {odds}:{len(ticket)-odds}) 不在允许列表 {self.config.allowed_odd_counts} 内"

        # 3. 大小比过滤 (High-Low Ratio Filter)
        highs = sum(1 for x in ticket if x > self.mid_point)
        if highs not in self.config.allowed_high_counts:
            return False, f"大号个数 {highs} (大小比 {highs}:{len(ticket)-highs}) 不在允许列表 {self.config.allowed_high_counts} 内"

        # 4. 最大连号数过滤 (Consecutive Numbers Filter)
        cons = 1
        max_cons = 1
        for i in range(len(ticket) - 1):
            if ticket[i+1] == ticket[i] + 1:
                cons += 1
                max_cons = max(max_cons, cons)
            else:
                cons = 1
        if max_cons > self.config.max_consecutive:
            return False, f"连号长度 {max_cons} 超过最大限制 {self.config.max_consecutive}"

        # 5. 同尾数过滤 (Same Tail Filter)
        tails = [x % 10 for x in ticket]
        max_tail_count = max(tails.count(t) for t in set(tails))
        if max_tail_count > self.config.max_same_tail:
            return False, f"同尾数最大个数 {max_tail_count} 超过限制 {self.config.max_same_tail}"

        # 6. 算术等差数列负面陷阱过滤 (Arithmetic Progression Anti-Pattern)
        if self.config.exclude_arithmetic_progression and len(ticket) >= 4:
            diffs = [ticket[i+1] - ticket[i] for i in range(len(ticket) - 1)]
            if len(set(diffs)) == 1:
                return False, f"号码呈严格等差数列步长 {diffs[0]}，属于极端低频形态"

        return True, "PASS"

    def filter_tickets(self, tickets: List[List[int]]) -> Dict[str, Any]:
        """批量过滤，返回过滤结果与详细统计报告"""
        passed = []
        rejected = []
        reject_reasons: Dict[str, int] = {}

        for t in tickets:
            ok, reason = self.check_ticket(t)
            if ok:
                passed.append(t)
            else:
                rejected.append({"ticket": t, "reason": reason})
                key = reason.split()[0]
                reject_reasons[key] = reject_reasons.get(key, 0) + 1

        raw_cnt = len(tickets)
        pass_cnt = len(passed)
        reduction_rate = ((raw_cnt - pass_cnt) / max(1, raw_cnt)) * 100.0

        return {
            "raw_count": raw_cnt,
            "passed_count": pass_cnt,
            "reduction_rate_pct": round(reduction_rate, 2),
            "passed_tickets": passed,
            "rejected_tickets": rejected,
            "reject_summary": reject_reasons
        }
