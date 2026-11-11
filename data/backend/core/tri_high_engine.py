# -*- coding: utf-8 -*-
"""Compatibility shim: backend.core.tri_high_engine -> backend.modules.tri_high.tri_high_engine

可被 `python backend/core/tri_high_engine.py` 直接执行（Web 任务入口）。
"""
from __future__ import annotations

import os
import sys

# 直接当脚本跑时，sys.path[0] 是 backend/core/，必须先注入项目根才能 import backend
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from backend.modules.tri_high.tri_high_engine import *  # noqa: F401,F403
from backend.modules.tri_high.tri_high_engine import run_tri_high_pipeline

if __name__ == "__main__":
    run_tri_high_pipeline()
