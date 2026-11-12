# -*- coding: utf-8 -*-
"""
快乐8 遗传算法自进化推演模块 (Genetic Algorithm Module)
=====================================================
【业务背景与架构定位】:
本模块专为快乐8全量历史数据打造，通过模拟生物进化（选择、交叉、变异、精英保留）
在多维历史特征空间中自适应搜索最优打分权重与最佳实战号码组合。

@author Antigravity Quantitative Team
@since 2026-09-11
"""
from backend.modules.legacy.genetic_algorithm.genetic_engine import GeneticAlgorithmEngine
from backend.modules.legacy.genetic_algorithm.service import GeneticServiceMixin

__all__ = ["GeneticAlgorithmEngine", "GeneticServiceMixin"]
