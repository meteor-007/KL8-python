# -*- coding: utf-8 -*-
"""
快乐8 数据分析系统 — 后端核心业务包 (Backend Package)
===================================================
双根引导 (Dual-Root Bootstrap): 自动将 backend/ 与项目根目录注入 sys.path，
兼容顶层包直接引用 (from core.xxx / from utils.xxx) 与绝对引用 (from backend.core.xxx)。
"""
import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in [_BACKEND_DIR, _PROJECT_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
