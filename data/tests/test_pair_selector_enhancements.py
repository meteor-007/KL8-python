# -*- coding: utf-8 -*-
import unittest
from backend.modules.trinity.pair_selector import PairSelector


class TestPairSelectorEnhancements(unittest.TestCase):
    def setUp(self):
        # 构造简单历史开奖用于测试
        self.history = [
            {"period": "2026300", "numbers": [1, 2, 3, 4, 5, 10, 11, 12, 20, 21, 22, 30, 31, 32, 40, 41, 50, 60, 70, 80]},
            {"period": "2026299", "numbers": [1, 2, 6, 7, 8, 10, 11, 13, 20, 21, 23, 30, 31, 33, 40, 42, 51, 61, 71, 79]},
            {"period": "2026298", "numbers": [1, 2, 9, 14, 15, 10, 11, 16, 20, 21, 24, 30, 31, 34, 40, 43, 52, 62, 72, 78]},
        ] * 10  # 30 期模拟
        self.selector = PairSelector(self.history)

    def test_dantuo_plan_generation(self):
        """测试 1胆3拖/1胆4拖 资金管理方案生成"""
        res = self.selector.select_optimal_pick2(
            ef_scores={1: 10.0, 2: 9.0, 10: 8.0},
            trinity_top5=[1, 2, 10, 20, 30],
            trinity_top12=[1, 2, 10, 20, 30, 40, 50, 60, 70, 80, 11, 21],
        )
        self.assertIn('dantuo_plan', res)
        dantuo = res['dantuo_plan']
        self.assertIsNotNone(dantuo['banker'])
        self.assertEqual(len(dantuo['drags_3']), 3)
        self.assertEqual(len(dantuo['drags_4']), 4)
        self.assertEqual(len(dantuo['combos_4']), 4)
        self.assertEqual(dantuo['cost_4_drag'], 8)
        self.assertNotIn(dantuo['banker'], dantuo['drags_4'], "定胆不应包含在拖码中")

    def test_cooldown_anti_streak(self):
        """测试防死守冷冻熔断换马机制"""
        # 第一次选择最优
        res1 = self.selector.select_optimal_pick2(
            ef_scores={1: 10.0, 2: 9.0, 10: 8.0},
            trinity_top5=[1, 2, 10, 20, 30],
        )
        first_pick = res1['optimal_pick2']

        # 将第一次选出的组合加入近期推荐列表，测试换马
        res2 = self.selector.select_optimal_pick2(
            ef_scores={1: 10.0, 2: 9.0, 10: 8.0, 20: 7.5, 30: 7.0},
            trinity_top5=[1, 2, 10, 20, 30],
            recent_recommended_pairs=[first_pick],
        )
        second_pick = res2['optimal_pick2']
        self.assertNotEqual(first_pick, second_pick, "处于冷却期的组合不应被再次推选为冠军对 (应触发换马)")

    def test_no_hardcoded_12_24_fallback(self):
        """测试无可用候选时动态保底，坚决废除硬编码 (12, 24)"""
        res = self.selector.select_optimal_pick2(
            high_conf_kills=[12, 24],  # 假定 12, 24 是绝对杀号
            recent_recommended_pairs=[(12, 24)],
        )
        self.assertNotEqual(res['optimal_pick2'], (12, 24), "绝不应回退至被杀号/硬编码的 (12, 24)")


if __name__ == '__main__':
    unittest.main()
