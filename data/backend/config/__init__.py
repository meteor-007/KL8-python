# -*- coding: utf-8 -*-
"""配置管理模块"""
try:
    from backend.config.config_loader import ConfigLoader, get_config
except ImportError:
    from .config_loader import ConfigLoader, get_config

__all__ = ["ConfigLoader", "get_config"]
