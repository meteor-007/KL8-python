# -*- coding: utf-8 -*-
"""
快乐8 决策树驱动的 012路 × 质合特征推演与智能缩水系统 (TPRD Module v1.0)
================================================================================
【业务背景与架构定位】:
本模块基于机器学习决策树（Decision Tree / AI海选团），深度结合快乐8全盘80码的
「012路余数守恒」与「质数合数空间正交性」，实现高信噪比的大盘特征学习与精准缩水。

@author Antigravity Quant Team
@since 2026-10-23
"""

from backend.modules.road_prime_shrink.tree_engine import TreeRoadPrimeShrinkEngine

__all__ = ["TreeRoadPrimeShrinkEngine"]
