# -*- coding: utf-8 -*-
"""特征工程:每期 -> 80维 one-hot;滑动窗口构造序列样本(无未来泄露)。"""
import numpy as np
import config


def draw_vector(draw):
    v = np.zeros(config.NUM_CLASSES, dtype=np.float32)
    for n in draw.numbers:
        if 1 <= n <= config.NUM_CLASSES:
            v[n - 1] = 1.0
    return v


def zone_counts(draw):
    """8区计数 01-10..71-80"""
    c = [0] * 8
    for n in draw.numbers:
        c[(n - 1) // 10] += 1
    return np.asarray(c, dtype=np.float32)


def tail_counts(draw):
    c = [0] * 10
    for n in draw.numbers:
        c[n % 10] += 1
    return np.asarray(c, dtype=np.float32)


def build_dataset(draws, seq_len=None, val_ratio=None):
    """返回 X(样本,seq,80), y_ball(样本,80), y_zone(样本,8), y_tail(样本,10)
       序列 i 的标签 = 第 i 期(序列末尾下一期)的开奖。无未来泄露。"""
    seq_len = seq_len or config.SEQ_LEN
    val_ratio = val_ratio if val_ratio is not None else config.VAL_SPLIT
    n = len(draws)
    if n <= seq_len + 2:
        return None
    X, yb, yz, yt = [], [], [], []
    for i in range(seq_len, n - 1):
        X.append(np.stack([draw_vector(d) for d in draws[i - seq_len:i]]))
        yb.append(draw_vector(draws[i]))
        yz.append(zone_counts(draws[i]))
        yt.append(tail_counts(draws[i]))
    X = np.asarray(X, dtype=np.float32)
    yb = np.asarray(yb, dtype=np.float32)
    yz = np.asarray(yz, dtype=np.float32) / 20.0
    yt = np.asarray(yt, dtype=np.float32) / 20.0
    cut = max(1, int(len(X) * (1 - val_ratio)))
    tr = (X[:cut], yb[:cut], yz[:cut], yt[:cut])
    va = (X[cut:], yb[cut:], yz[cut:], yt[cut:])
    return tr, va


def recent_features(draws, seq_len=None):
    """为下一个目标期构造最后一张输入图(seq_len, 80)。"""
    seq_len = seq_len or config.SEQ_LEN
    return np.stack([draw_vector(d) for d in draws[-seq_len:]]) if len(draws) >= seq_len else None