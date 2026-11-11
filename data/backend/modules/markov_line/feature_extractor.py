# -*- coding: utf-8 -*-
"""
号码全维度特征提取器 (Feature Extractor)
======================================
负责对单期及全时序开奖序列提取 12 大关键特征：
  1. 和值 (sum_val)
  2. 跨度 (span_val)
  3. 奇偶特征 (odd_count / even_count)
  4. 大小特征 (big_count / small_count)
  5. 质合特征 (prime_count / composite_count)
  6. 尾数香农熵 (tail_entropy)
  7. 平均遗漏值 (mean_omission)
  8. 最大遗漏值 (max_omission)
  9. 重号个数 (repeat_count)
  10. 连号对数 (consecutive_pairs)
  11. 邻号个数 (neighbor_count)
  12. 四区出号分布密度 (zone_density)
"""

from typing import List, Dict, Any, Optional
import math


# 1~80 内的标准质数集合（共22个）
PRIME_SET = {
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
    31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79
}


class DrawFeature:
    """单期开奖特征封装对象"""

    def __init__(
        self,
        issue: str,
        numbers: List[int],
        sum_val: int,
        span_val: int,
        odd_count: int,
        even_count: int,
        big_count: int,
        small_count: int,
        prime_count: int,
        composite_count: int,
        tail_entropy: float,
        mean_omission: float,
        max_omission: int,
        repeat_count: int,
        consecutive_pairs: int,
        neighbor_count: int,
        zone_density: List[int],
    ):
        self.issue = issue
        self.numbers = sorted(numbers)
        self.sum_val = sum_val
        self.span_val = span_val
        self.odd_count = odd_count
        self.even_count = even_count
        self.big_count = big_count
        self.small_count = small_count
        self.prime_count = prime_count
        self.composite_count = composite_count
        self.tail_entropy = tail_entropy
        self.mean_omission = mean_omission
        self.max_omission = max_omission
        self.repeat_count = repeat_count
        self.consecutive_pairs = consecutive_pairs
        self.neighbor_count = neighbor_count
        self.zone_density = zone_density

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化字典"""
        return {
            "issue": self.issue,
            "numbers": self.numbers,
            "sum_val": self.sum_val,
            "span_val": self.span_val,
            "odd_count": self.odd_count,
            "even_count": self.even_count,
            "big_count": self.big_count,
            "small_count": self.small_count,
            "prime_count": self.prime_count,
            "composite_count": self.composite_count,
            "tail_entropy": round(self.tail_entropy, 4),
            "mean_omission": round(self.mean_omission, 2),
            "max_omission": self.max_omission,
            "repeat_count": self.repeat_count,
            "consecutive_pairs": self.consecutive_pairs,
            "neighbor_count": self.neighbor_count,
            "zone_density": self.zone_density,
        }


class FeatureExtractor:
    """全时序特征提取引擎"""

    def __init__(self, total_balls: int = 80):
        """
        初始化特征提取器
        :param total_balls: 号码球总数，快乐8默认为 80
        """
        self.total_balls = total_balls

    def extract_single_draw_basic(
        self,
        issue: str,
        numbers: List[int],
        prev_numbers: Optional[List[int]] = None,
        current_omissions: Optional[Dict[int, int]] = None,
    ) -> DrawFeature:
        """
        提取单期基本与时序特征
        :param issue: 期号字符串
        :param numbers: 当期开奖号码列表
        :param prev_numbers: 上一期开奖号码列表（用于计算重号和邻号）
        :param current_omissions: 截止当期开奖前，各号码的当前遗漏字典 {ball: omit_count}
        :return: DrawFeature 特征对象
        """
        if not numbers:
            raise ValueError(f"期号 {issue} 开奖号码为空，无法提取特征")

        sorted_nums = sorted(numbers)
        num_len = len(sorted_nums)

        # 1. 和值
        sum_val = sum(sorted_nums)

        # 2. 跨度
        span_val = sorted_nums[-1] - sorted_nums[0] if num_len > 1 else 0

        # 3. 奇偶比
        odd_count = sum(1 for n in sorted_nums if n % 2 != 0)
        even_count = num_len - odd_count

        # 4. 大小比 (1~40 为小，41~80 为大)
        mid_point = self.total_balls // 2
        big_count = sum(1 for n in sorted_nums if n > mid_point)
        small_count = num_len - big_count

        # 5. 质合比 (1 既非质数也非合数，按传统彩票统计划归或独立统计，此处严格判定PRIME_SET)
        prime_count = sum(1 for n in sorted_nums if n in PRIME_SET)
        composite_count = num_len - prime_count

        # 6. 尾数香农熵 (0~9 尾数出现频率的离散程度)
        tail_counts = [0] * 10
        for n in sorted_nums:
            tail_counts[n % 10] += 1
        tail_entropy = 0.0
        for cnt in tail_counts:
            if cnt > 0:
                p = cnt / num_len
                tail_entropy -= p * math.log2(p)

        # 7 & 8. 遗漏值统计
        if current_omissions:
            omits = [current_omissions.get(n, 0) for n in sorted_nums]
            mean_omission = float(sum(omits)) / float(num_len) if num_len > 0 else 0.0
            max_omission = max(omits) if omits else 0
        else:
            mean_omission = 0.0
            max_omission = 0

        # 9. 重号个数 (与上一期重叠个数)
        prev_set = set(prev_numbers) if prev_numbers else set()
        repeat_count = len(set(sorted_nums) & prev_set)

        # 10. 连号对数 (相邻号码差值为 1 的对数)
        consecutive_pairs = 0
        for i in range(num_len - 1):
            if sorted_nums[i + 1] - sorted_nums[i] == 1:
                consecutive_pairs += 1

        # 11. 邻号个数 (与上一期某个号码距离为 1，且自身不在上一期号码中)
        neighbor_count = 0
        if prev_set:
            for n in sorted_nums:
                if n not in prev_set:
                    if (n - 1 in prev_set) or (n + 1 in prev_set):
                        neighbor_count += 1

        # 12. 四区出号密度 (1~20, 21~40, 41~60, 61~80)
        zone_density = [0, 0, 0, 0]
        for n in sorted_nums:
            zone_idx = min(3, max(0, (n - 1) // 20))
            zone_density[zone_idx] += 1

        return DrawFeature(
            issue=issue,
            numbers=sorted_nums,
            sum_val=sum_val,
            span_val=span_val,
            odd_count=odd_count,
            even_count=even_count,
            big_count=big_count,
            small_count=small_count,
            prime_count=prime_count,
            composite_count=composite_count,
            tail_entropy=tail_entropy,
            mean_omission=mean_omission,
            max_omission=max_omission,
            repeat_count=repeat_count,
            consecutive_pairs=consecutive_pairs,
            neighbor_count=neighbor_count,
            zone_density=zone_density,
        )

    def extract_full_history(self, history_data_asc: List[Dict[str, Any]]) -> List[DrawFeature]:
        """
        全量提取历史时序特征（必须按期号升序输入，时间从旧到新）
        :param history_data_asc: 按期号升序排列的字典列表 [{'issue': '...', 'numbers': [...]}]
        :return: List[DrawFeature] 特征对象列表
        """
        if not history_data_asc:
            return []

        features: List[DrawFeature] = []
        # 初始化 1~total_balls 的遗漏计数器
        omissions = {ball: 0 for ball in range(1, self.total_balls + 1)}
        prev_nums: Optional[List[int]] = None

        for entry in history_data_asc:
            issue = str(entry.get("issue", ""))
            raw_nums = entry.get("numbers", [])
            if not raw_nums:
                continue

            nums = sorted(int(x) for x in raw_nums)

            # 提取当期特征（使用当期开奖前的遗漏值）
            feat = self.extract_single_draw_basic(
                issue=issue,
                numbers=nums,
                prev_numbers=prev_nums,
                current_omissions=omissions,
            )
            features.append(feat)

            # 更新遗漏表（当期开出的号码归零，未开出的号码 +1）
            drawn_set = set(nums)
            for ball in range(1, self.total_balls + 1):
                if ball in drawn_set:
                    omissions[ball] = 0
                else:
                    omissions[ball] += 1

            prev_nums = nums

        return features
