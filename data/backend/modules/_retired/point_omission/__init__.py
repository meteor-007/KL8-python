# -*- coding: utf-8 -*-
"""
快乐8 点位+遗漏号深度分析系统 (Point & Omission Analysis System)
============================================================
将原独立研发系统无缝桥接到 K8-Quant 智能操盘决策体系中。
包含深度分析四重奏、13大统计特征模块（连号集群、周期共振、能量分布、反向博弈、
马尔可夫、斐波那契、SVD协方差、复变FFT、图网络、波动率聚类、余数空间、号码熵、对抗检验）、
无前视Exp3在线学习、防御性两码与严谨T=277滚动外样本回测。
"""
import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

# 确保 kl8 命名空间可用
try:
    import kl8
except ImportError:
    pass

__version__ = "2.0.0"
__all__ = ["__version__"]
