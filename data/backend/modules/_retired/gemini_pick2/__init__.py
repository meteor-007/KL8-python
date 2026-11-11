# -*- coding: utf-8 -*-
"""
Gemini 选2预测 — K8-Quant 智能选2与金银铜胆量化子系统
整合于主系统 data/ 中。
核心逻辑: 空间张力、尾数信息熵、马尔可夫扩散、共现社区、动量 5大特征算子透明打分与选2推演。
"""
from .engine import (
    daily_picks,
    oof_stats,
    load_draws,
    run_daily_pipeline,
    get_latest_summary,
    get_walk_forward_review
)
