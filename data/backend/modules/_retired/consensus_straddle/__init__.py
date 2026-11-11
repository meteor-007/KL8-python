# -*- coding: utf-8 -*-
"""三维交集共识与冷热对冲选2量化引擎包 (Consensus Straddle Engine Package)。"""
from backend.modules._retired.consensus_straddle.engine import (
    ConsensusStraddleEngine,
    ConsensusPredictionResult,
    run_consensus_prediction,
)

__all__ = [
    "ConsensusStraddleEngine",
    "ConsensusPredictionResult",
    "run_consensus_prediction",
]
