# -*- coding: utf-8 -*-
"""
双层LSTM 特征工程模块 (Feature Engineering)
==========================================
- 单期编码: 80维 0/1 独热向量 (One-hot Representation)
- 分区特征: 8分区频次 (01-10..71-80) 归一化
- 尾数特征: 10尾数频次 (尾0..尾9) 归一化
- 样本构建: 严格时序滑动窗口 (Sliding Window)，杜绝任何未来信息泄露
"""
from typing import List, Tuple, Optional
import numpy as np
from . import config
from .data_loader import KL8Draw


def draw_vector(draw: KL8Draw) -> np.ndarray:
    """将一期开奖转为 80 维 0/1 向量"""
    v = np.zeros(config.NUM_CLASSES, dtype=np.float32)
    for n in draw.numbers:
        if 1 <= n <= config.NUM_CLASSES:
            v[n - 1] = 1.0
    return v


def zone_counts(draw: KL8Draw) -> np.ndarray:
    """计算 8 区计数 (01-10, 11-20, ..., 71-80)"""
    c = [0] * 8
    for n in draw.numbers:
        idx = (n - 1) // 10
        if 0 <= idx < 8:
            c[idx] += 1
    return np.asarray(c, dtype=np.float32)


def tail_counts(draw: KL8Draw) -> np.ndarray:
    """计算 10 尾数计数 (尾0, 尾1, ..., 尾9)"""
    c = [0] * 10
    for n in draw.numbers:
        c[n % 10] += 1
    return np.asarray(c, dtype=np.float32)


def build_dataset(
    draws: List[KL8Draw],
    seq_len: Optional[int] = None,
    val_ratio: Optional[float] = None
) -> Optional[Tuple[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
                    Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]]:
    """
    构造训练集与验证集:
    返回:
      Train: (X_tr, y_ball_tr, y_zone_tr, y_tail_tr)
      Val:   (X_va, y_ball_va, y_zone_va, y_tail_va)
    保证: 序列 i 的标签是第 i 期（序列末尾的下一期），绝无未来信息泄露。
    """
    seq_len = seq_len or config.SEQ_LEN
    val_ratio = val_ratio if val_ratio is not None else config.VAL_SPLIT
    n = len(draws)
    if n <= seq_len + 2:
        return None

    X, yb, yz, yt = [], [], [], []
    for i in range(seq_len, n):
        # 过去 seq_len 期作为输入
        seq_draws = draws[i - seq_len:i]
        X.append(np.stack([draw_vector(d) for d in seq_draws]))
        # 当前第 i 期作为预测目标 (Ground Truth)
        yb.append(draw_vector(draws[i]))
        yz.append(zone_counts(draws[i]))
        yt.append(tail_counts(draws[i]))

    X = np.asarray(X, dtype=np.float32)
    yb = np.asarray(yb, dtype=np.float32)
    yz = np.asarray(yz, dtype=np.float32) / 20.0  # 归一化到 0~1 区间
    yt = np.asarray(yt, dtype=np.float32) / 20.0  # 归一化到 0~1 区间

    total_samples = len(X)
    cut = max(1, int(total_samples * (1.0 - val_ratio)))
    
    tr = (X[:cut], yb[:cut], yz[:cut], yt[:cut])
    va = (X[cut:], yb[cut:], yz[cut:], yt[cut:])
    return tr, va


def recent_features(draws: List[KL8Draw], seq_len: Optional[int] = None) -> Optional[np.ndarray]:
    """
    为下一个未知目标期构造最近一个序列特征 (seq_len, 80)
    """
    seq_len = seq_len or config.SEQ_LEN
    if len(draws) < seq_len:
        return None
    return np.stack([draw_vector(d) for d in draws[-seq_len:]])
