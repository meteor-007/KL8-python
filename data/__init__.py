# -*- coding: utf-8 -*-
"""快乐8 / K8-QUANT — 项目根包标记

目录约定（v5.4+）：
- frontend/ : 大屏视图与 js/pages
- backend/  : API、modules、pipeline、横切 core
- storage/  : raw/cache/outputs/reports/reviews 等活数据
- scripts/  : 运维与辅助脚本（ops/ 下放 bat/ps1/服务）
- docs/     : 文档
- deploy/   : Dockerfile / render.yaml
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BACKEND_ROOT = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
