# -*- coding: utf-8 -*-
"""
单元测试: 综合多期战绩战力榜驱动·选1至选10动态提炼精选器 (BattleRankOptimizer)
========================================================================================

@author czw
@since 2026-11-02
"""
import pytest
from backend.modules.battle_rank_optimizer.optimizer import BattleRankOptimizer
from backend.modules.battle_rank_optimizer.service import BattleRankService


class TestBattleRankOptimizer:
    """
    多期战力排行榜驱动提炼器测试套件
    """

    def setup_method(self):
        self.optimizer = BattleRankOptimizer()
        self.service = BattleRankService()

    def test_calculate_module_weights_multi_period(self):
        """测试 1: 验证多期综合战绩权重计算"""
        records = [
            {"key": "point_suppression", "name": "空间高压反弹", "lift": 1.429, "n_periods": 42},
            {"key": "trinity_top5", "name": "Trinity Top5", "lift": 1.253, "n_periods": 30},
            {"key": "aggregation", "name": "汇总最优3码", "lift": 1.156, "n_periods": 30},
            {"key": "weak_mod", "name": "跑输模块", "lift": 0.85, "n_periods": 20},
        ]
        weights = self.optimizer.calculate_module_weights_multi_period(records)

        assert weights["point_suppression"] > weights["trinity_top5"]
        assert weights["trinity_top5"] > weights["aggregation"]
        assert weights["aggregation"] > weights["weak_mod"]
        assert weights["weak_mod"] < 1.0

    def test_score_current_candidates(self):
        """测试 2: 验证当期号码多期战力打分与特征加成"""
        weights = {
            "trinity_top5": 2.5,
            "normal_mod": 1.0,
        }
        picks = {
            "trinity_top5": [27, 25, 57],
            "normal_mod": [27, 50, 12],
        }
        daily_points = [27, 50]
        tri_high = {"repeat_high": [50]}

        scored = self.optimizer.score_current_candidates(
            current_module_picks=picks,
            module_weights=weights,
            daily_points=daily_points,
            tri_high_features=tri_high,
        )

        assert 27 in scored
        assert scored[27]["score"] > 0
        assert scored[27]["is_point"] is True

    def test_extract_pick1_to_pick10(self):
        """测试 3: 验证选1到选10的提炼完整性与严格递增性"""
        weights = {"m1": 2.0}
        picks = {"m1": [27, 50, 72, 25, 12, 41, 4, 9, 73, 68, 57]}
        scored = self.optimizer.score_current_candidates(picks, weights)

        hierarchy = self.optimizer.extract_pick1_to_pick10(scored)

        for k in range(1, 11):
            key = f"pick{k}"
            assert key in hierarchy
            tier_data = hierarchy[key]
            nums = tier_data["numbers"]
            assert len(nums) == k
            assert len(nums) == len(set(nums))
            assert all(1 <= x <= 80 for x in nums)

        assert hierarchy["pick1"]["leader"] == hierarchy["pick1"]["numbers"][0]

    def test_boundary_empty_inputs(self):
        """测试 4: 边界防守 - 异常或空输入不崩溃"""
        weights = self.optimizer.calculate_module_weights_multi_period([])
        assert weights == {}

        scored = self.optimizer.score_current_candidates({}, {})
        assert scored == {}

        hierarchy = self.optimizer.extract_pick1_to_pick10({})
        for k in range(1, 11):
            key = f"pick{k}"
            assert key in hierarchy
            assert len(hierarchy[key]["numbers"]) == k

    def test_service_pipeline_multi_period(self):
        """测试 5: 服务层多期综合实战账本调用与 Markdown 渲染"""
        records = [
            {"key": "point_suppression", "name": "空间高压反弹", "lift": 1.429, "n_periods": 42, "total_picks": 42, "total_hits": 15, "pooled_rate": 0.3571},
            {"key": "trinity_top5", "name": "Trinity Top5", "lift": 1.253, "n_periods": 30, "total_picks": 150, "total_hits": 47, "pooled_rate": 0.3133},
        ]
        picks = {
            "point_suppression": [23],
            "trinity_top5": [25, 27, 57, 65, 68],
        }
        res = self.service.run_optimization_multi_period(picks, records, [27, 23], {})

        md = self.service.render_markdown_section_multi_period("2026292", res)
        assert "## 🏆 七、综合多期实战战绩排行榜驱动" in md
        assert "【选1 (首选独尊)】" in md
        assert "【选10 (十全大满贯)】" in md
        assert "【快乐8 第 2026292 期" in md
