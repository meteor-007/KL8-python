# -*- coding: utf-8 -*-
"""自主学习模块"""
try:
    from backend.learning.autonomous_learner import AutonomousLearner, quick_learn
except ImportError:
    from .autonomous_learner import AutonomousLearner, quick_learn

__all__ = ["AutonomousLearner", "quick_learn"]
