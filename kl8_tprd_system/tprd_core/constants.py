#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TPRD v4.0 (Dual-Window Calibrated & Zero-Blind-Spot Edition)
系统物理常数、子空间划分与特征元数据契约
"""

import numpy as np

# 1. 质数集合与全盘质合指示向量 (1~80, 0号占位)
PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79}
IS_PRIME = np.array([1.0 if n in PRIMES else 0.0 for n in range(81)], dtype=np.float32)

# 2. 012路与四区、尾数属性
ROAD_ID = np.array([n % 3 for n in range(81)], dtype=np.float32)
ZONE_ID = np.array([(n - 1) // 20 if n >= 1 else 0 for n in range(81)], dtype=np.float32)
TAIL_ID = np.array([n % 10 for n in range(81)], dtype=np.int32)

# 3. 六大正交子空间 (012路 × 质合)
SUBSPACES = {
    'S0_P': [n for n in range(1, 81) if n % 3 == 0 and n in PRIMES],      # 0路质数 (1码: 03)
    'S0_C': [n for n in range(1, 81) if n % 3 == 0 and n not in PRIMES],  # 0路合数 (25码)
    'S1_P': [n for n in range(1, 81) if n % 3 == 1 and n in PRIMES],      # 1路质数 (10码)
    'S1_C': [n for n in range(1, 81) if n % 3 == 1 and n not in PRIMES],  # 1路合数 (17码)
    'S2_P': [n for n in range(1, 81) if n % 3 == 2 and n in PRIMES],      # 2路质数 (11码)
    'S2_C': [n for n in range(1, 81) if n % 3 == 2 and n not in PRIMES],  # 2路合数 (16码)
}

# 4. 基准配额契约 (30码 / 25码 / 20码)
BASE_QUOTA_30 = {'S0_P': 1, 'S0_C': 8, 'S1_P': 4, 'S1_C': 6, 'S2_P': 4, 'S2_C': 7}
BASE_QUOTA_25 = {'S0_P': 1, 'S0_C': 7, 'S1_P': 3, 'S1_C': 5, 'S2_P': 3, 'S2_C': 6}
BASE_QUOTA_20 = {'S0_P': 1, 'S0_C': 5, 'S1_P': 3, 'S1_C': 4, 'S2_P': 2, 'S2_C': 5}

# 5. 路数理论期望与质数理论期望
ROAD_MU = {0: 6.50, 1: 6.75, 2: 6.75}
PRIME_MU = 5.50

# 6. 15维标准特征契约清单
FEATURE_NAMES = [
    '当前遗漏(f1)',
    '平滑均值遗漏(f2)',
    '遗漏弹性比(f3)',
    '近5期频次(f4)',
    '近15期频次(f5)',
    '近30期频次(f6)',
    '短期动能比(f7)',
    '邻居引力(f8)',
    '上期重号(f9)',
    '012路属性(f10)',
    '质数指示(f11)',
    '带符号路数净赤字(f12)',
    '质合耦合净赤字(f13)',
    '同尾联动热度(f14)',
    '四区空间象限编码(f15)'
]

# 7. 模型与空间守卫超参数
WEIGHT_SHORT_WINDOW = 0.45    # W=60 敏捷树权重
WEIGHT_LONG_WINDOW = 0.55     # W=240 稳健树权重
SUM_CORRIDOR_MIN = 760        # 20码和值走廊下界 (实测1σ走廊)
SUM_CORRIDOR_MAX = 860        # 20码和值走廊上界
REPEAT_LOCK_20 = 4            # 20码主力池保底热重号数
REPEAT_LOCK_25 = 5            # 25码中底保底热重号数
REPEAT_LOCK_30 = 6            # 30码大底保底热重号数
