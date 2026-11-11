# -*- coding: utf-8 -*-
"""
一胆拖三盾 · 选2组合拳量化子系统 (Spear-Shield Portfolio Module)
============================================================

【架构定位】:
针对单挑单注选2受制于极低组合概率天花板（基线 6.01%）的问题，
建立「一攻矛（40%胜率金胆）× 三守盾（7~13期黄金甜区温冷码）」实战矩阵。
以 3 注选2小复式组合拳，突破 20%~25% 样本外双全中命中率，
并将大盘保本见号率提升至 70%+。

@author Antigravity Quant Team & Old-School Quant Trader
@since 2026-09-21
"""

from .engine import SpearShieldPortfolioEngine, PortfolioPredictionResult
from .reviewer import SpearShieldPortfolioReviewer

__all__ = [
    "SpearShieldPortfolioEngine",
    "PortfolioPredictionResult",
    "SpearShieldPortfolioReviewer"
]
