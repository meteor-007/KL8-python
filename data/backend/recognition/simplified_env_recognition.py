# -*- coding: utf-8 -*-
"""简化版环境识别模块 — 迁移至 recognition/ 子树"""
import collections
import math
import statistics
from typing import Dict, List, Tuple, Any

# 5类环境
ENVIRONMENT_CLASSES = {
    0: {'name': '热号爆发期', 'desc': '热号集中，趋势明显', 'weights': {'EF': 0.50, 'RW': 0.20, 'FO': 0.30}},
    1: {'name': '冷号反弹期', 'desc': '冷号开始反弹', 'weights': {'EF': 0.55, 'RW': 0.25, 'FO': 0.20}},
    2: {'name': '平衡震荡期', 'desc': '各区间分布均匀', 'weights': {'EF': 0.40, 'RW': 0.30, 'FO': 0.30}},
    3: {'name': '趋势加速期', 'desc': '规律加速显现', 'weights': {'EF': 0.35, 'RW': 0.30, 'FO': 0.35}},
    4: {'name': '混沌随机期', 'desc': '规律混乱', 'weights': {'EF': 0.30, 'RW': 0.45, 'FO': 0.25}}
}

DEFAULT_STRATEGY = {
    'description': '各区间分布均匀，无明显趋势',
    'weights': {'EF': 0.40, 'RW': 0.30, 'FO': 0.30},
    'top5_count': 5, 'top12_count': 12,
    'use_b3_right': True, 'b3_right_quality_threshold': 0.6
}

def recognize_environment(history: List[Dict]) -> Tuple[int, str, float, Dict]:
    """
    基于规则的5类环境识别
    返回: (env_class, env_name, confidence, strategy_config)
    """
    if not history or len(history) < 10:
        return (2, '平衡震荡期', 0.5, DEFAULT_STRATEGY)

    # 特征1: 热号集中度
    f10 = collections.Counter(n for h in history[:10] for n in h['numbers'])
    hot_ratio = sum(1 for n, f in f10.items() if f >= 3) / 80.0

    # 特征2: 冷号密度
    cold_ratio = sum(1 for n in range(1, 81) if sum(1 for h in history[:10] if n in h['numbers']) <= 1) / 80.0

    # 特征3: 区间熵
    zone_counts = [0] * 8
    for h in history[:10]:
        for n in h['numbers']:
            zone_counts[(n - 1) // 10] += 1
    total_zone = sum(zone_counts)
    if total_zone > 0:
        probs = [z / total_zone for z in zone_counts if z > 0]
        entropy = -sum(p * math.log(p) for p in probs if p > 0)
        max_entropy = math.log(8)
        norm_entropy = entropy / max_entropy if max_entropy > 0 else 0.5
    else:
        norm_entropy = 0.5

    # 特征4: 趋势连续性 (连续同方向)
    trend_strength = 0.0
    for n in range(1, 81):
        seq = [1 if n in h['numbers'] else 0 for h in history[:10]]
        runs = 1
        for i in range(1, len(seq)):
            if seq[i] == seq[i - 1]:
                runs += 1
            else:
                runs = 1
        if runs >= 4:
            trend_strength += 1
    trend_strength /= 80.0

    # 决策树（阈值修正：快乐8每期抽20/80=25%，10期中单号期望出现2.5次，
    # P(>=3) ≈ 0.47，所以 hot_ratio 期望值 ≈ 0.47，原阈值0.30过低导致几乎总判为"热号爆发"）
    # 修正: hot_ratio > 0.55 才判为热号爆发 (需显著超出随机基线)
    if hot_ratio > 0.55:
        return (0, '热号爆发期', hot_ratio, {
            'description': '热号集中，趋势明显', 'weights': {'EF': 0.50, 'RW': 0.20, 'FO': 0.30},
            'top5_count': 7, 'top12_count': 14, 'use_b3_right': True, 'b3_right_quality_threshold': 0.6
        })
    elif cold_ratio > 0.35 and hot_ratio < 0.12:
        return (1, '冷号反弹期', cold_ratio, {
            'description': '冷号开始反弹', 'weights': {'EF': 0.55, 'RW': 0.25, 'FO': 0.20},
            'top5_count': 3, 'top12_count': 10, 'use_b3_right': False, 'b3_right_quality_threshold': 0.5
        })
    elif norm_entropy > 0.85:
        return (2, '平衡震荡期', norm_entropy, DEFAULT_STRATEGY)
    elif trend_strength > 0.20 and hot_ratio > 0.18:
        return (3, '趋势加速期', trend_strength, {
            'description': '规律加速显现', 'weights': {'EF': 0.35, 'RW': 0.30, 'FO': 0.35},
            'top5_count': 5, 'top12_count': 12, 'use_b3_right': True, 'b3_right_quality_threshold': 0.7
        })
    else:
        return (4, '混沌随机期', 0.5, {
            'description': '规律混乱', 'weights': {'EF': 0.30, 'RW': 0.45, 'FO': 0.25},
            'top5_count': 5, 'top12_count': 12, 'use_b3_right': True, 'b3_right_quality_threshold': 0.4
        })
