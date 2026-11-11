# -*- coding: utf-8 -*-
"""
统一配置加载器 (Config Loader)
==============================
从 scoring_config.yaml 加载所有配置参数，替代散落各处的硬编码魔法数字。
使用方式:
    from config import get_config
    cfg = get_config()
    markov_lookback = cfg['markov']['lookback']
"""
import os
import yaml

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, get_config_dir, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
# 2026-10-22 配置路径缺陷修复：原硬编码 `<root>/config/scoring_config.yaml`，
# 但实体文件在 `<root>/backend/config/`，导致每次加载都告警「配置文件不存在」并
# 静默回退到 _defaults() —— 真实 YAML 调参从未生效。改走 paths.get_config_dir()
# （优先 backend/config，回退 root/config），与全库路径中枢保持一致。
CONFIG_FILE = os.path.join(get_config_dir(), 'scoring_config.yaml')

_instance = None


class ConfigLoader:
    """单例配置加载器"""

    def __init__(self, config_path: str = None):
        self._path = config_path or CONFIG_FILE
        self._data = {}
        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            print(f"[ConfigLoader] 警告: 配置文件不存在 {self._path}, 使用默认值")
            self._data = self._defaults()
            return
        with open(self._path, 'r', encoding='utf-8') as f:
            self._data = yaml.safe_load(f) or {}

    def get(self, key_path: str, default=None):
        """
        点号路径访问: get('pentagon.default_weights.MK', 0.3)
        """
        keys = key_path.split('.')
        node = self._data
        for k in keys:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                return default
        return node

    def section(self, section_name: str) -> dict:
        """获取整个配置节"""
        return self._data.get(section_name, {})

    @property
    def raw(self) -> dict:
        return self._data

    @staticmethod
    def _defaults() -> dict:
        """当YAML文件不存在时的最小默认配置

        2026-10-22 一致性修复：原默认值仍带 v3.x 的 MK/EO 两个维度 (已随 v4.0 退役)。
        ScoreComposer 按 `weights.get(dim)` 取 EF/RW/FO 三键、却按 `sum(weights.values())`
        归一化 —— MK(0.30)+EO(0.15) 这两个不参与打分的键会白占 45% 权重份额，
        把三维实际比例稀释成 EF 0.455 / RW 0.182 / FO 0.364。
        现默认值与 YAML、v4.0 三维架构严格一致 (EF 0.40 / RW 0.30 / FO 0.30)。
        """
        return {
            'pentagon': {
                'default_weights': {'EF': 0.40, 'RW': 0.30, 'FO': 0.30},
                'scale_factors': {'EF': 1.0, 'RW': 10.0, 'FO': 0.5},
                'environment_overrides': {
                    'hot_burst': {'EF': 0.50, 'RW': 0.20, 'FO': 0.30},
                    'cold_rebound': {'EF': 0.55, 'RW': 0.25, 'FO': 0.20},
                    'balanced': {'EF': 0.40, 'RW': 0.30, 'FO': 0.30},
                    'trend_accel': {'EF': 0.35, 'RW': 0.30, 'FO': 0.35},
                    'chaotic': {'EF': 0.30, 'RW': 0.45, 'FO': 0.25},
                },
                'volatility_thresholds': {'high': 0.25, 'low': 0.10},
            },
            'markov': {'lookback': 3, 'min_observations': 3, 'prior_strength': 1.0, 'default_prob': 0.25},
            'bayesian': {'prior_alpha': 5.0, 'prior_beta': 15.0, 'likelihood_window': 20, 'decay_factor': 0.7},
            'monte_carlo': {'n_simulations': 5000, 'sampling_mode': 'constrained'},
            'energy_field': {'decay_rate': 0.5, 'diffusion_factor': 0.4, 'lookback': 30, 'neighbor_range': 3, 'neighbor_decay_base': 0.5},
            'environment': {'n_clusters': 5, 'hot_ratio_threshold': 0.55},
            'loss_function': {'method': 'cross_entropy', 'temperature': 0.5, 'max_history_losses': 30},
        }


def get_config() -> ConfigLoader:
    """获取全局配置单例"""
    global _instance
    if _instance is None:
        _instance = ConfigLoader()
    return _instance


def reload_config():
    """强制重新加载配置"""
    global _instance
    _instance = ConfigLoader()
    return _instance
