# -*- coding: utf-8 -*-
"""
纯血统遗漏最值业务服务层 (Pure Omission MinMax Service)
================================================================================
彻底剥离点位依赖，为系统流水线提供纯内生推演服务

@author czw
@since 2026-10-31
"""
from typing import Dict, Any, Optional
from .engine import PureOmissionMinMaxEngine, run_pure_omission_resonance


class OmissionMinMaxService:
    """
    纯内生遗漏最值业务服务
    """

    def __init__(self):
        self.engine = PureOmissionMinMaxEngine()

    def get_period_analysis(self, period: str = "2026290") -> Dict[str, Any]:
        """
        获取指定期的纯内生分析结果
        """
        return self.engine.analyze_pure_matrix(period)

    def execute_daily(self, period: str = "2026290") -> Dict[str, Any]:
        """
        执行每日独立推演并落盘
        """
        return run_pure_omission_resonance(period)
