#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2x 模块: TPRD v4.0 快乐8 智能量化缩水与双螺旋矩阵系统
集成至 backend.modules 包中
"""

import sys
import os
from pathlib import Path

# 将顶级工程包目录加入搜索路径
_TPRD_ROOT = Path("D:/project/Python-Project/kl8_tprd_system").resolve()
if str(_TPRD_ROOT) not in sys.path:
    sys.path.insert(0, str(_TPRD_ROOT))

from tprd_core.model_v40 import infer_period_v40
from tprd_core.matrices import (
    generate_drawer_pick2, generate_dhm_pro_v40,
    generate_gf4_hypercube_pick5, generate_bibd_pick6
)
from tprd_core.data_sync import load_history, sync_latest_draws
from tprd_core.features import build_features

__all__ = [
    "infer_period_v40",
    "generate_drawer_pick2",
    "generate_dhm_pro_v40",
    "generate_gf4_hypercube_pick5",
    "generate_bibd_pick6",
    "load_history",
    "sync_latest_draws",
    "build_features"
]
