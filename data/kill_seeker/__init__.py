# -*- coding: utf-8 -*-
"""
KillSeeker — KL8 杀号预测子系统
整合于主系统 data/ 中，作为独立模块运行。
核心逻辑: 引擎评分越低 = 越不可能出 = 高置信杀号
目标: 杀号命中率 ≥ 75%
"""
from kill_seeker.core.eval_significance import monte_carlo_kill_baseline, is_above_baseline

__all__ = ["monte_carlo_kill_baseline", "is_above_baseline"]
