# -*- coding: utf-8 -*-
"""
Pytest global configuration and fixtures for KL8 Quantitative Trading System
"""
import os
import sys
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# 彻底禁用 sys.stdout.reconfigure 和 sys.stderr.reconfigure，防止子模块在导入期意外关闭或重置 pytest 的 capture 临时文件
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure = lambda *args, **kwargs: None
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure = lambda *args, **kwargs: None
