#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TPRD v4.0 Core Package
"""

from .constants import (
    PRIMES, IS_PRIME, ROAD_ID, ZONE_ID, TAIL_ID,
    SUBSPACES, BASE_QUOTA_30, BASE_QUOTA_25, BASE_QUOTA_20,
    FEATURE_NAMES
)
from .data_sync import sync_latest_draws, load_history, parse_and_append_draw
from .features import build_features
from .matrices import (
    generate_drawer_pick2, generate_dhm_pro_v40,
    generate_gf4_hypercube_pick5, generate_bibd_pick6
)
from .model_v40 import infer_period_v40
from .backtest import run_walk_forward_backtest

__all__ = [
    "PRIMES", "IS_PRIME", "ROAD_ID", "ZONE_ID", "TAIL_ID",
    "SUBSPACES", "BASE_QUOTA_30", "BASE_QUOTA_25", "BASE_QUOTA_20",
    "FEATURE_NAMES",
    "sync_latest_draws", "load_history", "parse_and_append_draw",
    "build_features",
    "generate_drawer_pick2", "generate_dhm_pro_v40",
    "generate_gf4_hypercube_pick5", "generate_bibd_pick6",
    "infer_period_v40",
    "run_walk_forward_backtest"
]
