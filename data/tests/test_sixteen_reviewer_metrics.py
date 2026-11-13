# -*- coding: utf-8 -*-
"""16 期中热复盘器 · 指标口径回归测试

守的是一条口径：**lift 的分母必须按篮子实际长度算**，不能按字段名里的数字算。

背景（已修复的真实缺陷）：
操盘轨的 `top5` / `top12` 早已是「兼容旧字段」，内容其实都是 tip3 那 3 个号
（sixteen_engine: `top5 = list(tip3)` / `top12 = list(tip3)`）。
复盘器却仍按 5 码 / 12 码计算期望命中，分母被放大到 1.25 / 3.0，
把一个 0.78 码 / 3 码 = 1.04x 的中性结果，渲染成了 top5 0.62x、top12 0.26x。
读者会以为操盘轨「只有随机的四分之一」，实际上它与随机持平。
"""
import os
import sys
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.modules.sixteen.sixteen_reviewer import SixteenPeriodReviewer  # noqa: E402

_BASKETS = ("ops_top5", "ops_top12", "ops_tip3")


class TestReviewerMetricCaliber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = SixteenPeriodReviewer().run_walk_forward_review(n_periods=10)
        cls.rows = cls.result["rows"]
        cls.stats = cls.result["stats"]

    def test_lift_matches_actual_basket_size(self):
        """lift 必须等于 命中总数 ÷ (实际篮子长度之和 × 25%)。"""
        n = len(self.rows)
        self.assertGreater(n, 0, "复盘没有样本，测试无意义")
        for key in _BASKETS:
            hits = sum(r[f"{key}_hits"] for r in self.rows)
            expected = sum(len(r[key]) for r in self.rows) * 0.25
            want = round(hits / expected, 2) if expected else None
            self.assertEqual(
                self.stats.get(f"{key}_lift"), want,
                f"{key}_lift 与「按实际篮子长度」重算的结果不符 —— "
                f"检查是否又改回了写死的 1.25 / 3.0 / 0.75 分母")

    def test_basket_size_reported(self):
        """必须把实际篮子大小一并输出，否则读者无法判断 lift 的分母是什么。"""
        for key in _BASKETS:
            self.assertIn(f"{key}_basket_size", self.stats)
            self.assertGreater(self.stats[f"{key}_basket_size"], 0)

    def test_compat_fields_are_tip3_sized(self):
        """当前 top5 / top12 是兼容字段，长度应与 tip3 一致；若将来恢复独立大底，
        本用例会失败，提醒同时复核上面的 lift 口径（而不是直接删掉它）。"""
        for key in ("ops_top5", "ops_top12"):
            for r in self.rows:
                self.assertEqual(
                    len(r[key]), len(r["ops_tip3"]),
                    f"{key} 与 tip3 长度不一致，说明独立大底已恢复，请复核 lift 分母口径")


if __name__ == "__main__":
    unittest.main(verbosity=2)