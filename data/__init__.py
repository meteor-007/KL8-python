# -*- coding: utf-8 -*-
"""快乐8 数据分析系统 — 前后端模块化标准版
目录结构已规范化重构：
- frontend/ : 前端大屏与可视化组件
- backend/  : 后端 API、核心算法、数据采集、流水线、审计风控等 10 大功能模块
- storage/  : 数据持久化与资产存储中心
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BACKEND_ROOT = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
