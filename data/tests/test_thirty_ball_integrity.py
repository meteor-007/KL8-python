# -*- coding: utf-8 -*-
"""
30 码大底数据诚信守护测试（2026-10-12 整改）

守护的规则（每条对应本次整改发现的真实问题）：
  1. 产线成员必须逐字等于被回测的策略函数输出（杜绝"宣称冠军算法、实际跑另一套"）；
  2. 任意目标期重放无未来函数穿透（窗口一律按 period < target 截断）；
  3. 文案禁语：显著提升/翻倍拉升/充分验证/~10%+/理论均值 等无检验支撑或口径错误的措辞；
  4. 缺票池/点位可运行，source_stats 如实标注，不编造输入；
  5. benchmark 产物缺失/损坏/显式推荐三种来源路径行为正确且可审计。
"""
import os
import sys
import random
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.modules.spear_shield_portfolio.thirty_ball_benchmark import (
    PeriodRecord,
    STRATEGY_REGISTRY,
    DEFAULT_STRATEGY_ID,
)
from backend.modules.spear_shield_portfolio.thirty_ball_engine import ThirtyBallEngine

FORBIDDEN_PHRASES = ["显著提升", "翻倍拉升", "充分验证", "~10%+", "理论均值", "发生率: ~"]


def _build_synthetic_history(n_draws: int = 120, start_period: int = 2026100, seed: int = 12345):
    rng = random.Random(seed)
    records = []
    period = start_period
    for _ in range(n_draws):
        nums = set(rng.sample(range(1, 81), 20))
        records.append(PeriodRecord(
            period=period,
            numbers=nums,
            raw_str="-".join(f"{n:02d}" for n in sorted(nums)),
        ))
        period += 1
    return records


def _make_engine() -> ThirtyBallEngine:
    eng = ThirtyBallEngine()
    # 指向不存在的产物 → 走 default_fallback 路径
    eng._benchmark_artifact_path = os.path.join(PROJ_DIR, "storage", "outputs", "__no_such_benchmark__.json")
    # 测试内不落盘
    eng._persist = lambda *a, **k: None
    return eng


class TestThirtyBallIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = _build_synthetic_history()
        cls.replay_target = cls.history[-5].period  # 其后还有 4 期开奖, 专测未来函数

    def test_01_no_future_leak(self):
        """对历史期重放: 含"未来"开奖的完整历史与截断历史必须产出完全一致的成员。"""
        eng = _make_engine()
        full = eng.generate(self.replay_target, history=self.history, strategy_id=DEFAULT_STRATEGY_ID)
        truncated = [r for r in self.history if r.period < self.replay_target]
        pre_only = eng.generate(self.replay_target, history=truncated, strategy_id=DEFAULT_STRATEGY_ID)
        self.assertEqual(full.picks, pre_only.picks, "目标期之后的数据泄漏进了选号")
        self.assertEqual(full.top10_core, pre_only.top10_core)
        self.assertEqual(full.source_stats["base_period"], self.replay_target - 1)

    def test_02_membership_equals_benchmark_strategy(self):
        """无票/无点位时, 成员必须等于注册表策略函数在同一段历史上调用的输出。"""
        eng = _make_engine()
        res = eng.generate(self.replay_target, history=self.history, strategy_id=DEFAULT_STRATEGY_ID)
        pre = [r for r in self.history if r.period < self.replay_target]
        expected = sorted(STRATEGY_REGISTRY[DEFAULT_STRATEGY_ID][1](pre, len(pre)))
        self.assertEqual(res.picks, expected)

    def test_03_forbidden_marketing_phrases(self):
        """文案禁语: 不得出现无检验支撑的显著性措辞与写死的发生率。"""
        eng = _make_engine()
        res = eng.generate(self.replay_target, history=self.history, strategy_id=DEFAULT_STRATEGY_ID)
        for phrase in FORBIDDEN_PHRASES:
            self.assertNotIn(phrase, res.quick_copy_text, f"文案出现禁语: {phrase}")

    def test_04_missing_inputs_are_honest(self):
        """缺票池/点位可运行, source_stats 两项 False, 不编造输入。"""
        eng = _make_engine()
        res = eng.generate(self.replay_target, history=self.history, strategy_id=DEFAULT_STRATEGY_ID)
        self.assertFalse(res.source_stats["has_lanes_vote"])
        self.assertFalse(res.source_stats["has_daily_points"])
        self.assertEqual(res.source_stats["total_voted_count"], 0)
        self.assertEqual(len(res.picks), 30)

    def test_05_portfolio_structure(self):
        """恰好 30 个唯一号码 (成员集合层面的硬保证)。"""
        eng = _make_engine()
        res = eng.generate(self.replay_target, history=self.history, strategy_id=DEFAULT_STRATEGY_ID)
        self.assertEqual(len(res.picks), 30)
        self.assertEqual(len(set(res.picks)), 30)
        self.assertTrue(all(1 <= b <= 80 for b in res.picks))

    def test_05b_strategy7_zone_cap(self):
        """方案 7 (原打分器可回测版) 的 8 分区约束: 每区 ≥2 保底、补齐上限 5。"""
        eng = _make_engine()
        pre = [r for r in self.history if r.period < self.replay_target]
        picks = STRATEGY_REGISTRY["strategy_7_statistical_blend"][1](pre, len(pre))
        self.assertEqual(len(picks), 30)
        zone_count: dict = {}
        for b in picks:
            zone_count[(b - 1) // 10] = zone_count.get((b - 1) // 10, 0) + 1
        self.assertTrue(all(c <= 5 for c in zone_count.values()), f"方案7 单区超 5 码: {zone_count}")
        self.assertTrue(all(c >= 2 for c in zone_count.values()), f"方案7 有分区低于保底 2 码: {zone_count}")

    def test_06_determinism(self):
        """同输入两次调用结果一致。"""
        eng = _make_engine()
        r1 = eng.generate(self.replay_target, history=self.history, strategy_id=DEFAULT_STRATEGY_ID)
        r2 = eng.generate(self.replay_target, history=self.history, strategy_id=DEFAULT_STRATEGY_ID)
        self.assertEqual(r1.picks, r2.picks)
        self.assertEqual(r1.quick_copy_text, r2.quick_copy_text)

    def test_07_empty_pre_history_raises(self):
        """目标期之前无任何历史必须显式报错, 不许静默编造。"""
        eng = _make_engine()
        with self.assertRaises(ValueError):
            eng.generate(self.history[0].period, history=self.history, strategy_id=DEFAULT_STRATEGY_ID)

    def test_08_broken_artifact_falls_back(self):
        """产物缺失 → 回退默认方案并标注 default_fallback (可审计)。"""
        eng = _make_engine()
        res = eng.generate(self.replay_target, history=self.history)
        self.assertEqual(res.source_stats["strategy_id"], DEFAULT_STRATEGY_ID)
        self.assertEqual(res.source_stats["strategy_source"], "default_fallback")

    def test_09_artifact_recommended_is_used(self):
        """产物 recommended 决定成员算法, 且 strategy_source 标注为 artifact。"""
        alt_sid = next(s for s in STRATEGY_REGISTRY if s != DEFAULT_STRATEGY_ID)
        eng = _make_engine()
        eng._benchmark_artifact = lambda: {"recommended": alt_sid, "strategies": [], "baseline": {"p_ge11": 0.056}}
        res = eng.generate(self.replay_target, history=self.history)
        self.assertEqual(res.source_stats["strategy_id"], alt_sid)
        self.assertEqual(res.source_stats["strategy_source"], "artifact")

    def test_10_votes_do_not_change_membership(self):
        """票池/点位只改展示排序, 绝不改成员集合。"""
        eng = _make_engine()
        base = eng.generate(self.replay_target, history=self.history, strategy_id=DEFAULT_STRATEGY_ID)
        # 尾部号拿最高票 → 展示排序应翻转, 但成员不变
        votes = {b: i + 1 for i, b in enumerate(base.picks)}
        pts = base.picks[:20]
        boosted = eng.generate(
            self.replay_target, lanes_vote=votes, daily_points=pts,
            history=self.history, strategy_id=DEFAULT_STRATEGY_ID,
        )
        self.assertEqual(boosted.picks, base.picks, "票池/点位改变了大底成员")
        self.assertNotEqual(boosted.top10_core, base.top10_core, "票池应改变展示排序")
        self.assertTrue(boosted.source_stats["has_lanes_vote"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
