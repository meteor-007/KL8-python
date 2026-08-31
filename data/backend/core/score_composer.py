# -*- coding: utf-8 -*-
"""
统一评分组合器 (Score Composer)
================================
将多通道评分统一为 EF/RW/FO 三维融合 (自学习解锁后可用):
  - 旧 trinity 审计 (audit/v3_trinity_audit.py, 已归档)
  - 置信度评分 (core/strategy_optimizer.py plan15)
  - ~~深度命中率优化~~ (已归档 archive/deprecated，Walk-Forward 替代)

统一后的评分管线:
  原始分数 -> 量纲归一化 -> Loss权重加权 -> 环境自适应 -> 最终排名

使用方式:
    from core.score_composer import ScoreComposer
    composer = ScoreComposer()
    final_scores = composer.compose(raw_scores_dict, environment_info)
    top20 = composer.get_top(final_scores, k=20)
"""
import os
import math
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
COMPOSED_SCORES_FILE = os.path.join(_PROJ, 'cache', 'composed_scores.json')


class ScoreComposer:
    """
    统一评分组合器
    
    设计原则:
      1. 单一入口: 所有算子输出汇入此模块, 不再分散到多个评分逻辑
      2. 量纲归一化: 不同算子输出的分数范围差异大, 必须归一化后才能比较
      3. Loss驱动权重: 权重不是静态的, 由历史Loss动态调整
      4. 环境自适应: 不同环境(热号爆发/冷号反弹/平衡/趋势/混沌)下权重不同
    """
    
    def __init__(self):
        self._config = self._load_config()
        self._loss_weights = self._load_loss_weights()
        self._learner_weights = self._load_learner_weights()
    
    def _load_config(self) -> dict:
        """加载配置"""
        try:
            from config import get_config
            cfg = get_config()
            return {
                'default_weights': cfg.section('pentagon').get('default_weights', {
                    'EF': 0.40, 'RW': 0.30, 'FO': 0.30
                }),
                'scale_factors': cfg.section('pentagon').get('scale_factors', {
                    'EF': 1.0, 'RW': 10.0, 'FO': 0.5
                }),
                'env_overrides': cfg.section('pentagon').get('environment_overrides', {}),
                'vol_thresholds': cfg.section('pentagon').get('volatility_thresholds', {
                    'high': 0.25, 'low': 0.10
                }),
            }
        except Exception:
            return {
                'default_weights': {'EF': 0.40, 'RW': 0.30, 'FO': 0.30},
                'scale_factors': {'EF': 1.0, 'RW': 10.0, 'FO': 0.5},
                'env_overrides': {},
                'vol_thresholds': {'high': 0.25, 'low': 0.10},
            }
    
    def _load_loss_weights(self) -> Optional[Dict[str, float]]:
        """从Loss更新器获取动态权重 (门控未解锁时不加载)"""
        try:
            from core.learning_gate import is_learning_enabled
            if not is_learning_enabled():
                return None
        except Exception:
            pass
        try:
            from core.loss_weight_updater import LossBasedWeightUpdater
            updater = LossBasedWeightUpdater()
            weights = updater.get_current_weights()
            if weights:
                return weights
        except Exception:
            pass
        return None

    def _load_learner_weights(self) -> Optional[Dict[str, float]]:
        """从 AutonomousLearner 读取闭环学习权重 (门控未解锁时不加载)"""
        try:
            from core.learning_gate import is_learning_enabled
            if not is_learning_enabled():
                return None
        except Exception:
            pass
        try:
            learner_state_file = os.path.join(_PROJ, 'cache', 'learner_state.json')
            if os.path.exists(learner_state_file):
                with open(learner_state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                pw = state.get('pentagon_weights', {})
                if pw and all(k in pw for k in ('EF', 'RW', 'FO')):
                    return pw
        except Exception:
            pass
        return None
    
    @staticmethod
    def _normalize_minmax(scores: Dict[int, float]) -> Dict[int, float]:
        """Min-Max归一化到 [0, 1]"""
        if not scores:
            return {}
        vals = list(scores.values())
        mn, mx = min(vals), max(vals)
        if mx == mn:
            return {k: 0.5 for k in scores}
        return {k: (v - mn) / (mx - mn) for k, v in scores.items()}
    
    @staticmethod
    def _normalize_zscore(scores: Dict[int, float]) -> Dict[int, float]:
        """Z-Score归一化 (允许负值, 保留相对差异)"""
        if not scores:
            return {}
        vals = np.array(list(scores.values()))
        mean, std = vals.mean(), vals.std()
        if std < 1e-10:
            return {k: 0.0 for k in scores}
        return {k: (v - mean) / std for k, v in scores.items()}
    
    @staticmethod
    def _normalize_percentile(scores: Dict[int, float]) -> Dict[int, float]:
        """百分位归一化: 转为排名百分比"""
        if not scores:
            return {}
        sorted_items = sorted(scores.items(), key=lambda x: x[1])
        n = len(sorted_items)
        return {item[0]: rank / max(n - 1, 1) for rank, item in enumerate(sorted_items)}
    
    def compose(self,
                raw_scores: Dict[str, Dict[int, float]],
                environment: str = 'balanced',
                volatility: float = 0.15,
                normalize_method: str = 'percentile') -> Dict[int, float]:
        """
        统一评分组合
        
        Args:
            raw_scores: 各维度的原始评分 (v4.0: 仅EF/RW/FO三维, MK/EO已移除)
                {
                    'EF': {1: 5.2, 2: 3.1, ...},      # 隐能量场分数(蹭热度)
                    'RW': {1: 0.45, 2: 0.12, ...},    # 遗漏Sigmoid分数(抓冷门)
                    'FO': {1: 8, 2: 5, ...},           # 特征优化层Counter分数(找周期)
                }
            environment: 当前环境类型
                'hot_burst' | 'cold_rebound' | 'balanced' | 'trend_accel' | 'chaotic'
            volatility: 当前波动率 (用于微调权重)
            normalize_method: 归一化方法 'minmax' | 'zscore' | 'percentile'
        
        Returns:
            最终综合评分 {1: 7.32, 2: 4.51, ...}
        """
        # -- Step 1: 量纲归一化 --
        norm_fn = {
            'minmax': self._normalize_minmax,
            'zscore': self._normalize_zscore,
            'percentile': self._normalize_percentile,
        }.get(normalize_method, self._normalize_percentile)
        
        normalized = {}
        for dim, scores in raw_scores.items():
            if scores:
                normalized[dim] = norm_fn(scores)
            else:
                # 空维度会以恒定 0.5 污染综合分, 必须显式告警而非静默
                logger.warning(f"[ScoreComposer] 维度 {dim} 得分为空, 已填充中性值 0.5")
                normalized[dim] = {n: 0.5 for n in range(1, 81)}
        
        # -- Step 2: 确定权重 --
        # 优先级: learner闭环权重 > Loss动态权重 > 环境自适应权重 > 默认权重
        if self._learner_weights:
            weights = dict(self._learner_weights)
        elif self._loss_weights:
            # v4.0: MK/EO已移除, 仅映射EF/RW/FO三维
            # _loss_weights 键为 energy/bayesian/feature，raw_scores 键为 EF/RW/FO
            dim_to_loss = {
                'EF': 'energy', 'RW': 'bayesian', 'FO': 'feature',
            }
            weights = {}
            for dim in raw_scores:
                loss_key = dim_to_loss.get(dim, dim)
                weights[dim] = (
                    self._loss_weights.get(loss_key, 0)
                    or self._loss_weights.get(dim, 0)
                )
            
            total_w = sum(weights.values())
            if total_w < 0.01:
                weights = self._get_env_weights(environment)
            else:
                weights = {k: v / total_w for k, v in weights.items()}
        else:
            weights = self._get_env_weights(environment)
        
        # -- Step 3: 波动率微调 --
        vol_thresholds = self._config.get('vol_thresholds', {'high': 0.25, 'low': 0.10})
        # v4.0: 高波动加RW减EF, 低波动加EF减RW
        if volatility > vol_thresholds.get('high', 0.25):
            if 'RW' in weights and 'EF' in weights:
                delta = min(0.05, (volatility - vol_thresholds['high']) * 0.3)
                weights['RW'] = weights.get('RW', 0.3) + delta
                weights['EF'] = max(0.15, weights.get('EF', 0.4) - delta)
        elif volatility < vol_thresholds.get('low', 0.10):
            if 'EF' in weights and 'RW' in weights:
                delta = min(0.05, (vol_thresholds['low'] - volatility) * 0.3)
                weights['EF'] = weights.get('EF', 0.4) + delta
                weights['RW'] = max(0.10, weights.get('RW', 0.3) - delta)
        
        # 归一化权重
        total_w = sum(weights.values())
        if total_w > 0:
            weights = {k: v / total_w for k, v in weights.items()}
        
        # -- Step 4: 加权求和 --
        final_scores = {}
        for n in range(1, 81):
            score = 0.0
            for dim, norm_scores in normalized.items():
                w = weights.get(dim, 0)
                score += w * norm_scores.get(n, 0.0)
            final_scores[n] = round(score, 6)
        
        # 保存组合结果
        self._save_composed(final_scores, weights, environment, volatility)
        
        return final_scores
    
    def _get_env_weights(self, environment: str) -> Dict[str, float]:
        """获取环境自适应权重"""
        overrides = self._config.get('env_overrides', {})
        if environment in overrides:
            return dict(overrides[environment])
        return dict(self._config.get('default_weights', {
            'EF': 0.40, 'RW': 0.30, 'FO': 0.30
        }))
    
    def get_top(self, scores: Dict[int, float], k: int = 20) -> List[int]:
        """获取Top-K号码 (分数降序, 号码升序)"""
        return sorted(scores, key=lambda n: (-scores[n], n))[:k]
    
    def get_golden_silver(self,
                          scores: Dict[int, float],
                          golden_k: int = 5,
                          silver_k: int = 10) -> Dict[str, List[int]]:
        """
        生成金胆/银胆号码
        """
        top_all = self.get_top(scores, k=silver_k)
        return {
            'golden': top_all[:golden_k],
            'silver': top_all[golden_k:silver_k]
        }
    
    def _save_composed(self, scores: Dict[int, float], weights: Dict[str, float],
                       environment: str, volatility: float):
        """持久化组合结果"""
        os.makedirs(os.path.dirname(COMPOSED_SCORES_FILE), exist_ok=True)
        data = {
            'scores': {str(n): s for n, s in sorted(scores.items())},
            'weights': weights,
            'environment': environment,
            'volatility': round(volatility, 4),
            'top20': self.get_top(scores, 20),
        }
        try:
            with open(COMPOSED_SCORES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def get_confidence_report(self, scores: Dict[int, float]) -> Dict:
        """
        生成置信度报告
        """
        vals = np.array(list(scores.values()))
        
        top5 = sorted(scores.values(), reverse=True)[:5]
        concentration = sum(top5) / vals.sum() if vals.sum() > 0 else 0
        
        cv = vals.std() / vals.mean() if vals.mean() > 0 else 0
        
        spread = vals.max() - vals.min()
        
        if cv > 0.5 and concentration > 0.15:
            level = 'HIGH'
            desc = '信号强, Top号码显著领先'
        elif cv > 0.2:
            level = 'MEDIUM'
            desc = '信号中等, 需结合环境判断'
        else:
            level = 'LOW'
            desc = '信号弱, 号码间差异小, 谨慎参考'
        
        return {
            'level': level,
            'description': desc,
            'concentration': round(concentration, 4),
            'cv': round(cv, 4),
            'spread': round(spread, 4),
            'top5_share': round(concentration, 2),
        }


def quick_compose(energy_scores: Dict[int, float],
                  omission_scores: Dict[int, float],
                  feature_scores: Dict[int, float],
                  environment: str = 'balanced',
                  volatility: float = 0.15) -> Tuple[Dict[int, float], Dict]:
    """
    快速组合入口 (v4.0: 三维架构EF/RW/FO, MK/EO已移除)
    """
    composer = ScoreComposer()
    
    raw = {
        'EF': energy_scores,
        'RW': omission_scores,
        'FO': feature_scores,
    }
    
    final = composer.compose(raw, environment, volatility)
    report = composer.get_confidence_report(final)
    
    return final, report


if __name__ == '__main__':
    import random
    
    ef = {n: random.random() * 10 for n in range(1, 81)}
    rw = {n: random.random() for n in range(1, 81)}
    fo = {n: random.randint(1, 15) for n in range(1, 81)}
    
    final, report = quick_compose(ef, rw, fo, 'balanced', 0.15)
    
    composer = ScoreComposer()
    top20 = composer.get_top(final, 20)
    gs = composer.get_golden_silver(final)
    
    print(f"Top20: {top20}")
    print(f"金胆: {gs['golden']}")
    print(f"银胆: {gs['silver']}")
    print(f"置信度: {report}")
