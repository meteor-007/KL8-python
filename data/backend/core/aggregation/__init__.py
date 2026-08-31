# -*- coding: utf-8 -*-
"""
core.aggregation — 快乐8 终审共识与数据汇总复盘子系统
"""
from .consensus_engine import ConsensusEngine
from .stable_evaluator import top_freq_in_window, walk_forward_stable
from .proxy_generator import generate_proxy_signals

__all__ = ["ConsensusEngine", "top_freq_in_window", "walk_forward_stable", "generate_proxy_signals"]
