# -*- coding: utf-8 -*-
"""
B3 Right 质量检查模块 (B3 Right Quality Checker)
功能：评估B3 Right矩阵映射的数据质量，提供降级策略
"""

import collections
from typing import Dict, List, Tuple, Any


class B3RightQualityChecker:
    """
    B3 Right 数据质量检查器
    """
    def __init__(self, data2_by_issue: Dict, history: List[Dict], points_by_issue: Dict):
        self.data2 = data2_by_issue
        self.history = history
        self.points = points_by_issue
        self.quality_threshold = 0.6

    def _resolve_issue(self, target_issue: str) -> str:
        """如果 target_issue 无数据，则 fallback 到 data2 中最新的期号"""
        if target_issue in self.data2:
            return target_issue
        # fallback: 使用 data2 中最新的期号
        if self.data2:
            latest_available = sorted(self.data2.keys())[-1]
            return latest_available
        return target_issue

    def check_data_completeness(self, target_issue: str) -> float:
        resolved = self._resolve_issue(target_issue)
        if resolved not in self.data2:
            return 0.0
        b3_right_data = self.data2[resolved][2]['right']
        if not b3_right_data:
            return 0.0
        if len(b3_right_data) < 3:
            return 0.3
        elif len(b3_right_data) < 5:
            return 0.6
        else:
            return 1.0

    def check_historical_hit_rate(self, target_issue: str, lookback: int = 10) -> float:
        if len(self.history) < lookback:
            return 0.5
        issues = sorted(self.data2.keys())
        if not issues:
            return 0.0
        hit_counts = 0; total_counts = 0
        for i, hist in enumerate(self.history[:lookback]):
            issue = hist['issue']
            if issue in self.data2:
                b3_right_nums = [item[0] for item in self.data2[issue][2]['right']]
                actual_nums = set(hist['numbers'])
                hits = len(set(b3_right_nums) & actual_nums)
                hit_counts += hits; total_counts += len(b3_right_nums)
        if total_counts == 0:
            return 0.0
        hit_rate = hit_counts / total_counts
        if hit_rate >= 0.3: return 1.0
        elif hit_rate >= 0.2: return 0.8
        elif hit_rate >= 0.1: return 0.5
        else: return 0.2

    def check_diversity(self, target_issue: str) -> float:
        resolved = self._resolve_issue(target_issue)
        if resolved not in self.data2:
            return 0.0
        b3_right_data = self.data2[resolved][2]['right']
        if not b3_right_data:
            return 0.0
        nums = [item[0] for item in b3_right_data]
        zone_counts = [0] * 8
        for num in nums:
            zone_idx = (num - 1) // 10
            if 0 <= zone_idx < 8: zone_counts[zone_idx] += 1
        import statistics
        if len(zone_counts) > 1:
            stdev = statistics.stdev(zone_counts)
            mean = statistics.mean(zone_counts)
            if mean > 0:
                cv = stdev / mean
                if cv <= 0.5: return 1.0
                elif cv <= 1.0: return 0.7
                else: return 0.4
        return 0.5

    def check_point_alignment(self, target_issue: str) -> float:
        if target_issue not in self.points:
            return 0.5
        target_points = self.points.get(target_issue, set())
        if not target_points:
            return 0.5
        resolved = self._resolve_issue(target_issue)
        if resolved in self.data2:
            b3_right_nums = [item[0] for item in self.data2[resolved][2]['right']]
            b3_right_set = set(b3_right_nums)
            overlap = len(b3_right_set & target_points)
            if len(b3_right_set) > 0:
                overlap_rate = overlap / len(b3_right_set)
                if overlap_rate <= 0.3: return 1.0
                elif overlap_rate <= 0.5: return 0.7
                else: return 0.3
        return 0.5

    def evaluate_quality(self, target_issue: str) -> Dict:
        completeness = self.check_data_completeness(target_issue)
        hit_rate = self.check_historical_hit_rate(target_issue)
        diversity = self.check_diversity(target_issue)
        point_alignment = self.check_point_alignment(target_issue)
        total_score = (completeness * 0.3 + hit_rate * 0.4 + diversity * 0.2 + point_alignment * 0.1)
        quality_level = "HIGH" if total_score >= 0.7 else "MEDIUM" if total_score >= 0.4 else "LOW"
        return {
            'total_score': round(total_score, 2), 'quality_level': quality_level,
            'details': {'completeness': round(completeness, 2), 'hit_rate': round(hit_rate, 2),
                        'diversity': round(diversity, 2), 'point_alignment': round(point_alignment, 2)},
            'should_use': total_score >= self.quality_threshold,
            'fallback_strategy': 'confidence_score' if total_score < self.quality_threshold else None
        }

    def get_fallback_recommendation(self, history: List[Dict]) -> List[int]:
        from core.strategy_optimizer import plan15_confidence_scoring
        result = plan15_confidence_scoring(history)
        return result.get('top5', [])


def integrate_quality_check(auto_report_module):
    import types
    original_extract = auto_report_module.PredictorEngine.extract_special_5

    def enhanced_extract_special_5(self, pipeline_res):
        data2 = self.dc.data2
        latest_issue = self.dc.latest_issue
        target_issue = str(int(latest_issue) + 1)
        points_by_issue = self.dc.points
        checker = B3RightQualityChecker(data2, self.dc.history, points_by_issue)
        quality_report = checker.evaluate_quality(target_issue)
        print(f"\n[B3 Right质量检查] 总分: {quality_report['total_score']}, 等级: {quality_report['quality_level']}")
        b3_right_nums = []; b3_right_stealth = []
        if quality_report['should_use']:
            if target_issue in data2:
                b3_right_data = data2[target_issue][2]['right']
                b3_right_nums = [item[0] for item in b3_right_data]
            elif latest_issue in data2:
                b3_right_data = data2[latest_issue][2]['right']
                b3_right_nums = [item[0] for item in b3_right_data]
            target_points = points_by_issue.get(target_issue, set())
            b3_right_stealth = [n for n in b3_right_nums if n not in target_points]
        else:
            print(f"  [B3 Right] 质量不佳，切换到备选策略")
            fallback_nums = checker.get_fallback_recommendation(self.dc.history)
            b3_right_nums = fallback_nums[:5]; b3_right_stealth = fallback_nums[:3]
        top_12 = pipeline_res['strat']['conf_score'].get('top12', [])
        special_5 = []
        for n in b3_right_stealth:
            if len(special_5) < 3: special_5.append(n)
        for n in top_12:
            if len(special_5) < 5 and n not in special_5: special_5.append(n)
        return {'final_5': sorted(list(set(special_5[:5]))), 'raw_b3_right': b3_right_nums, 'stealth_nums': b3_right_stealth, 'quality_report': quality_report}

    auto_report_module.PredictorEngine.extract_special_5 = enhanced_extract_special_5
    return auto_report_module

if __name__ == '__main__':
    print("B3 Right Quality Checker - 请通过 auto_generate_daily_report.py 调用")
