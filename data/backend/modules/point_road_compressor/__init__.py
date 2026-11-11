# -*- coding: utf-8 -*-
"""
点位012压缩器模块 (PointRoadCompressor)
================================================================================
核心逻辑:
  1. 点位锚定重心 (20码点位)
  2. 正负2划定引力半径 (±1, ±2 邻位展开)
  3. 012路宏观与微观分区偏态建模与动态剪枝过滤
  4. 压缩输出高胜率核心金胆与跨路对冲选2搭档
"""
from __future__ import annotations

from .engine import (
    PointRoadCompressor,
    PointRoadCompressorResult,
    run_compressor_prediction,
)

__all__ = [
    "PointRoadCompressor",
    "PointRoadCompressorResult",
    "run_compressor_prediction",
]
