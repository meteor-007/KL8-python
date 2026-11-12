# -*- coding: utf-8 -*-
"""
跟随分析 (重复号追踪与多窗条件跟随) 模块包
"""
from core.follow_analysis.follow_engine import (
    load_draws_from_history,
    bayesian_smooth,
    calculate_history_repeat_avg,
    repeat_analysis,
    inference_top6,
    conditional_follow,
    daily_follow_picks,
    BASE_RATE,
    BASELINE_REPEAT_TOP5,
    BASELINE_INFERENCE_TOP6,
    BASELINE_FOLLOW_TOP8
)
from core.follow_analysis.follow_reviewer import (
    walk_forward_evaluate,
    evaluate_confidence
)
from core.follow_analysis.follow_cross_validator import (
    cross_validate_follow_picks
)

__all__ = [
    "load_draws_from_history",
    "bayesian_smooth",
    "calculate_history_repeat_avg",
    "repeat_analysis",
    "inference_top6",
    "conditional_follow",
    "daily_follow_picks",
    "walk_forward_evaluate",
    "evaluate_confidence",
    "cross_validate_follow_picks",
    "BASE_RATE",
    "BASELINE_REPEAT_TOP5",
    "BASELINE_INFERENCE_TOP6",
    "BASELINE_FOLLOW_TOP8",
]
