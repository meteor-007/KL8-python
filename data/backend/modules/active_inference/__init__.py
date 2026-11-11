# -*- coding: utf-8 -*-
"""变分神经主动推理模块 (Active Inference Graph Inference Module)。

基于变分自由能原理、FlyWire 先验图谱、拓扑弹性重连、ACT-UCA 优化与 Keystone 枢纽中心性。
"""

from .engine import ActiveInferenceEngine, ActiveInferencePredictionResult
from .graph_prior import GraphPriorBuilder
from .dynamic_rewire import DynamicRewirer
from .free_energy_cavi import FreeEnergyOptimizer, FreeEnergyOptimizationResult
from .keystone import KeystoneExtractor, KeystoneExtractionResult

__all__ = [
    "ActiveInferenceEngine",
    "ActiveInferencePredictionResult",
    "GraphPriorBuilder",
    "DynamicRewirer",
    "FreeEnergyOptimizer",
    "FreeEnergyOptimizationResult",
    "KeystoneExtractor",
    "KeystoneExtractionResult",
]
