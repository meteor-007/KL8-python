# -*- coding: utf-8 -*-
"""Compatibility shim: backend.core.datasource_integration_v2 -> backend.modules.datasource.datasource_integration_v2

可被直接执行；启动时注入项目根，避免 ModuleNotFoundError: backend。
"""
from __future__ import annotations

import os
import sys

_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from backend.modules.datasource.datasource_integration_v2 import *  # noqa: F401,F403
