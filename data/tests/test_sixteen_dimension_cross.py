# -*- coding: utf-8 -*-
"""16 期窗口维度交叉研究 · 回归测试

守住三条口径：
1. 维度分类正确：1~80 中质数 22、合数 57、1 为中性；尾数每类 8 个；012 路 26/27/27。
2. 交叉矩阵完备：行(出现次数 0~8+) × 列(剩余次数分桶) 的号码总数必须等于 80。
3. 约束优化可行：选出的号码必须满足 尾数覆盖≥8、012 路 6~8、质数 4~8。
"""
import os
import sys
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.modules.sixteen.dimension_cross import (  # noqa: E402
    PRIMES_1_80,
    PRIME_COUNT,
    COMPOSITE_COUNT,
    THEORY_TAIL_COUNT,
    THEORY_ROAD_COUNT,
    OMISSION_BUCKETS,
    FREQ_ROWS,
    tail_class,
    road_class,
    prime_class,
    omission_bucket,
    freq_bucket,
    compute_ball_profiles,
    build_cross_matrix,
    build_dimension_profile,
    select_optimal_picks,
    analyze_dimension_cross,
    run_dimension_arbitrage,
    CONSTRAINTS,
)
from backend.modules.sixteen.sixteen_engine import (  # noqa: E402
    load_draws_from_file,
    WINDOW_SIZE,
    NUM_TOTAL,
)


class TestDimensionClassification(unittest.TestCase):
    def test_prime_table(self):
        self.assertEqual(PRIME_COUNT, 22)
        self.assertEqual(COMPOSITE_COUNT, 57)
        self.assertIn(2, PRIMES_1_80)
        self.assertIn(79, PRIMES_1_80)
        self.assertNotIn(1, PRIMES_1_80)
        self.assertNotIn(4, PRIMES_1_80)

    def test_prime_class(self):
        self.assertEqual(prime_class(1), "neutral")
        self.assertEqual(prime_class(2), "prime")
        self.assertEqual(prime_class(49), "composite")  # 7x7
        self.assertEqual(prime_class(79), "prime")

    def test_road_class(self):
        self.assertEqual(road_class(3), 0)
        self.assertEqual(road_class(1), 1)
        self.assertEqual(road_class(2), 2)
        self.assertEqual(road_class(80), 2)

    def test_tail_class(self):
        self.assertEqual(tail_class(80), 0)
        self.assertEqual(tail_class(7), 7)
        self.assertEqual(tail_class(19), 9)

    def test_theory_baseline(self):
        self.assertEqual(THEORY_TAIL_COUNT, 8)
        self.assertEqual(THEORY_ROAD_COUNT, {"0": 26, "1": 27, "2": 27})

    def test_omission_bucket(self):
        self.assertEqual(omission_bucket(0), "0")
        self.assertEqual(omission_bucket(2), "2")
        self.assertEqual(omission_bucket(4), "3-4")
        self.assertEqual(omission_bucket(10), "8-11")
        self.assertEqual(omission_bucket(99), "16+")

    def test_freq_bucket(self):
        self.assertEqual(freq_bucket(0), "0")
        self.assertEqual(freq_bucket(7), "7")
        self.assertEqual(freq_bucket(8), "8+")
        self.assertEqual(freq_bucket(16), "8+")


class TestProfilesAndMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draws = load_draws_from_file()
        cls.profiles = compute_ball_profiles(cls.draws, len(cls.draws) - 1)

    def test_profiles_count_and_fields(self):
        self.assertEqual(len(self.profiles), NUM_TOTAL)
        required = {
            "number", "freq_16", "window_remaining", "omission",
            "omission_bucket", "recent_8_hits", "is_outgoing",
            "tail", "road012", "prime_class", "midhot_score", "rebound_score",
            "max_omission", "avg_omission", "max_streak",
        }
        for p in self.profiles:
            self.assertTrue(required.issubset(p.keys()), f"缺字段: {required - set(p.keys())}")

    def test_freq_sum_equals_window_size(self):
        total = sum(p["freq_16"] for p in self.profiles)
        self.assertEqual(total, WINDOW_SIZE * 20)

    def test_window_remaining_complement(self):
        for p in self.profiles:
            self.assertEqual(p["window_remaining"], WINDOW_SIZE - p["freq_16"])

    def test_matrix_complete(self):
        cm = build_cross_matrix(self.profiles)
        self.assertEqual(cm["rows"], FREQ_ROWS)
        self.assertEqual(len(cm["cols"]), len(OMISSION_BUCKETS))
        total = sum(
            cell["count"]
            for row in cm["matrix"].values()
            for cell in row.values()
        )
        self.assertEqual(total, NUM_TOTAL)

    def test_matrix_cells_have_numbers(self):
        cm = build_cross_matrix(self.profiles)
        for row in FREQ_ROWS:
            for col, _, _ in OMISSION_BUCKETS:
                cell = cm["matrix"][row][col]
                self.assertEqual(len(cell["nums"]), cell["count"])

    def test_quadrants_cover(self):
        cm = build_cross_matrix(self.profiles)
        quads = cm["quadrants"]
        self.assertEqual(
            set(quads.keys()),
            {"hot_short_omission", "hot_long_omission", "cold_short_omission", "cold_long_omission"},
        )
        for q in quads.values():
            self.assertEqual(q["count"], len(q["nums"]))


class TestDimensionProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draws = load_draws_from_file()
        cls.profiles = compute_ball_profiles(cls.draws, len(cls.draws) - 1)

    def test_tail_rows_complete(self):
        prof = build_dimension_profile(self.profiles, pool_name="全80码")
        self.assertEqual(len(prof["tail"]), 10)
        self.assertEqual(sum(t["count"] for t in prof["tail"]), NUM_TOTAL)

    def test_road_rows_complete(self):
        prof = build_dimension_profile(self.profiles, pool_name="全80码")
        self.assertEqual(len(prof["road"]), 3)
        self.assertEqual(sum(r["count"] for r in prof["road"]), NUM_TOTAL)

    def test_prime_split(self):
        prof = build_dimension_profile(self.profiles, pool_name="全80码")
        p = prof["prime"]
        self.assertEqual(p["prime"]["count"], PRIME_COUNT)
        self.assertEqual(p["composite"]["count"], COMPOSITE_COUNT)
        self.assertEqual(p["neutral"]["count"], 1)

    def test_midhot_pool_filter(self):
        prof = build_dimension_profile(
            self.profiles, pool_name="中热池",
            pool_filter=lambda x: 3 <= x["freq_16"] <= 6,
        )
        self.assertGreater(prof["pool_size"], 0)
        self.assertEqual(
            sum(t["count"] for t in prof["tail"]), prof["pool_size"],
        )


class TestOptimalPicks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draws = load_draws_from_file()
        cls.profiles = compute_ball_profiles(cls.draws, len(cls.draws) - 1)
        cls.result = select_optimal_picks(cls.profiles, restarts=25)

    def test_pick_size(self):
        self.assertEqual(len(self.result["picks"]), CONSTRAINTS["pick_size"])

    def test_unique(self):
        self.assertEqual(len(set(self.result["picks"])), len(self.result["picks"]))

    def test_constraints_satisfied(self):
        detail = self.result["constraint_detail"]
        self.assertGreaterEqual(detail["tail_coverage"], CONSTRAINTS["min_tail_coverage"])
        self.assertEqual(detail["road_violation"], 0)
        self.assertEqual(detail["prime_violation"], 0)
        self.assertTrue(self.result["feasible"])

    def test_score_positive(self):
        self.assertGreater(self.result["total_midhot_score"], 0)


class TestArbitrage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draws = load_draws_from_file()
        cls.result = run_dimension_arbitrage(
            cls.draws, n_periods=30, pick_size=12, restarts=10,
        )

    def test_status(self):
        self.assertEqual(self.result["status"], "ok")

    def test_three_tracks(self):
        self.assertEqual(
            set(self.result["tracks"].keys()),
            {"momentum", "constrained", "rebound"},
        )

    def test_track_fields(self):
        for name, tr in self.result["tracks"].items():
            for key in ("avg_hits", "hit_rate_pct", "lift", "t", "p", "significant"):
                self.assertIn(key, tr, f"{name} 缺 {key}")

    def test_records_count(self):
        self.assertEqual(len(self.result["records"]), self.result["n_periods"])

    def test_verdict_is_string(self):
        self.assertIsInstance(self.result["verdict"], str)
        self.assertGreater(len(self.result["verdict"]), 0)


class TestAnalyzeEntryPoint(unittest.TestCase):
    def test_payload_keys(self):
        draws = load_draws_from_file()
        res = analyze_dimension_cross(draws)
        self.assertEqual(res["status"], "ok")
        for key in (
            "cross_matrix", "dimension_profile", "dimension_profile_all",
            "optimal_picks", "momentum_baseline", "theory",
        ):
            self.assertIn(key, res)

    def test_theory_block(self):
        draws = load_draws_from_file()
        res = analyze_dimension_cross(draws)
        self.assertEqual(res["theory"]["prime_count_1_80"], 22)
        self.assertEqual(res["theory"]["composite_count_1_80"], 57)


if __name__ == "__main__":
    unittest.main()
