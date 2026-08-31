# -*- coding: utf-8 -*-
"""
顺口溜口诀规律与组合带出系统 (Formula Jingle Subsystem)
======================================================
核心功能：
1. 90条精英口诀匹配（两号齐出 pair_pair / 单号带出 triple_single）
2. OOF加权聚合选码与超几何自适应期望基线
3. 近N期真·样本外无未来函数对账与分层Lift审计
4. 与KillSeeker杀号/选2/LSTM交叉风险核验
"""
from .jingle_engine import (
    load_jingle_rules,
    fired_rules,
    at_least_one_baseline,
    predict_jingle,
    save_jingle_prediction,
    BASELINE_PAIR,
    BASELINE_TRIPLE,
)
from .jingle_reviewer import review_jingle
from .jingle_cross_validator import cross_validate_jingle

__all__ = [
    "load_jingle_rules",
    "fired_rules",
    "at_least_one_baseline",
    "predict_jingle",
    "save_jingle_prediction",
    "review_jingle",
    "cross_validate_jingle",
    "BASELINE_PAIR",
    "BASELINE_TRIPLE",
]
