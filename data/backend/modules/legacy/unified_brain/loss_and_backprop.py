# -*- coding: utf-8 -*-
"""
loss_and_backprop.py — 内核真自进化与参数反向微调引擎 (True Parameter Backprop & Calibration)
=============================================================================================
【根据上一期真实开奖与概率场残差，自动反向优化物理内核参数】：
  1. Focal Loss (焦点残差损失) 计算：对比 80 维预测概率分布与真实 20 个中奖球；
     - 支持难分样本聚焦参数 gamma、正负样本平衡因子 alpha 与数值防除零 epsilon 保护；
  2. 空间高斯核宽 sigma 自适应梯度与步长推导 (根据开奖号码空间聚类紧密度动态调整，安全边界 [1.5, 3.5])；
  3. 时序衰减半衰率 lambda 自适应梯度与步长推导 (根据跨期重号动量动态调整，安全边界 [0.85, 0.98])；
  4. 操盘手大白话因果追溯与自进化记录生成；
  5. 兼容导出 UnifiedBrainEvolutionEngine 统一自进化引擎。
"""
from __future__ import annotations

import os
import sys
import json
import math
from datetime import datetime
from typing import Dict, List, Set, Any, Tuple, Optional, Union

import numpy as np

# 80 球标准常数
NUM_TOTAL = 80


# =====================================================================
# 1. Focal Loss 焦点残差损失计算核心
# =====================================================================

def calculate_focal_loss(
    predicted_probs: Union[np.ndarray, List[float], Dict[str, float]],
    actual_draw: Union[List[int], Set[int], np.ndarray],
    gamma: float = 2.0,
    alpha: Optional[float] = None,
    eps: float = 1e-7
) -> float:
    """
    计算主脑 80 维预测概率与真实 20 码开奖之间的 Focal Loss 焦点残差损失。
    大白话：专查没猜中的硬骨头！重点关注那些爆冷开出或者意外遗漏的号码，算算主脑错得有多离谱。

    公式定义：
      y_i in {0, 1}, i = 1..80 (20个为1, 60个为0)
      p_i = clip(P(N_i), eps, 1 - eps)
      若 alpha 为 None (标准无偏):
        L_i = - [ y_i * (1 - p_i)^gamma * ln(p_i) + (1 - y_i) * p_i^gamma * ln(1 - p_i) ]
      若 alpha 给定 (平衡因子):
        L_i = - [ alpha * y_i * (1 - p_i)^gamma * ln(p_i) + (1 - alpha) * (1 - y_i) * p_i^gamma * ln(1 - p_i) ]

    :param predicted_probs: 80 维概率向量 (numpy 数组、列表或 {"1": 0.02, ...} 字典)
    :param actual_draw: 真实开奖号码集合或列表 (1-80 范围整数)
    :param gamma: 难分样本聚焦因子 (默认 2.0)
    :param alpha: 正负样本平衡权重 (可选, 如 0.25 或 None)
    :param eps: 数值防溢出保护常数 (默认 1e-7)
    :return: float, 全局 Focal Loss 标量损失
    """
    # 1. 转换并校验预测概率向量 (80 维)
    if isinstance(predicted_probs, dict):
        p_arr = np.array([float(predicted_probs.get(str(i), predicted_probs.get(i, 0.0))) for i in range(1, NUM_TOTAL + 1)], dtype=np.float64)
    elif isinstance(predicted_probs, (list, tuple)):
        p_arr = np.array([float(x) for x in predicted_probs], dtype=np.float64)
    elif isinstance(predicted_probs, np.ndarray):
        p_arr = predicted_probs.astype(np.float64)
    else:
        p_arr = np.full(NUM_TOTAL, 1.0 / NUM_TOTAL, dtype=np.float64)

    if p_arr.shape != (NUM_TOTAL,):
        # 若形状不合，平滑补齐或截断
        fixed_p = np.full(NUM_TOTAL, 1.0 / NUM_TOTAL, dtype=np.float64)
        n_copy = min(len(p_arr), NUM_TOTAL)
        fixed_p[:n_copy] = p_arr[:n_copy]
        p_arr = fixed_p

    # 2. 构造真实 20 码二值标签向量 Y (80 维)
    y_true = np.zeros(NUM_TOTAL, dtype=np.float64)
    if isinstance(actual_draw, (set, list, tuple, np.ndarray)):
        for num in actual_draw:
            try:
                n_int = int(num)
                if 1 <= n_int <= NUM_TOTAL:
                    y_true[n_int - 1] = 1.0
            except Exception:
                pass

    # 3. 数值防下溢与除零保护
    safe_eps = max(1e-15, float(eps))
    p = np.clip(p_arr, safe_eps, 1.0 - safe_eps)
    g = max(0.0, float(gamma))

    # 4. 向量化计算 Focal Loss
    pos_term = ((1.0 - p) ** g) * np.log(p)
    neg_term = (p ** g) * np.log(1.0 - p)

    if alpha is not None:
        a = float(np.clip(alpha, 0.0, 1.0))
        loss_vec = - (a * y_true * pos_term + (1.0 - a) * (1.0 - y_true) * neg_term)
    else:
        loss_vec = - (y_true * pos_term + (1.0 - y_true) * neg_term)

    total_loss = float(np.sum(loss_vec))
    return round(total_loss, 4)


def compute_loss_gradients(
    predicted_probs: np.ndarray,
    actual_draw: Union[List[int], Set[int]],
    gamma: float = 2.0,
    alpha: Optional[float] = None,
    eps: float = 1e-7
) -> np.ndarray:
    """
    计算 Focal Loss 对 80 维预测概率 P 的解析梯度向量 dL/dP。
    :return: shape (80,), float64
    """
    p = np.clip(predicted_probs.astype(np.float64), eps, 1.0 - eps)
    y = np.zeros(NUM_TOTAL, dtype=np.float64)
    for n in actual_draw:
        if 1 <= int(n) <= NUM_TOTAL:
            y[int(n) - 1] = 1.0

    g = float(gamma)
    grad = np.zeros(NUM_TOTAL, dtype=np.float64)

    for i in range(NUM_TOTAL):
        pi = p[i]
        yi = y[i]
        if yi == 1.0:
            # 正样本导数: d/dp [ -(1-p)^g * ln(p) ] = (1-p)^g * [ g*ln(p)/(1-p) - 1/p ]
            grad_pos = ((1.0 - pi) ** g) * (g * np.log(pi) / (1.0 - pi + eps) - 1.0 / pi)
            grad[i] = (alpha * grad_pos) if alpha is not None else grad_pos
        else:
            # 负样本导数: d/dp [ -p^g * ln(1-p) ] = - [ g*p^(g-1)*ln(1-p) - p^g/(1-p) ]
            grad_neg = - (g * (pi ** max(0.0, g - 1.0)) * np.log(1.0 - pi) - (pi ** g) / (1.0 - pi))
            grad[i] = ((1.0 - alpha) * grad_neg) if alpha is not None else grad_neg

    return grad


# =====================================================================
# 2. 空间与时序物理残差统计指标
# =====================================================================

def calculate_spatial_dispersion(actual_nums: List[int]) -> float:
    """
    计算真实开奖 20 码在 1~80 空间中的平均相邻跨度 d_bar (空间紧密度)。
    大白话：看看开出的号码是挤在一块（扎堆），还是散落在全盘（分散）。
    理论随机期望值约 4.0。
    """
    clean_nums = sorted([int(x) for x in actual_nums if 1 <= int(x) <= NUM_TOTAL])
    if len(clean_nums) < 2:
        return 4.0
    diffs = [clean_nums[i + 1] - clean_nums[i] for i in range(len(clean_nums) - 1)]
    return float(np.mean(diffs))


def calculate_repeat_count(actual_nums: List[int], prev_nums: Optional[List[int]]) -> int:
    """
    统计当期真实开奖与上一期的重号个数 R。
    大白话：看看昨天开出的号今天又重开了几个（重号惯性）。
    理论随机期望值约为 20 * 20 / 80 = 5 个。
    """
    if not prev_nums:
        return 5
    s_cur = set(int(x) for x in actual_nums if 1 <= int(x) <= NUM_TOTAL)
    s_prev = set(int(x) for x in prev_nums if 1 <= int(x) <= NUM_TOTAL)
    return len(s_cur & s_prev)


# =====================================================================
# 3. 超参数自适应演进与安全边界保护
# =====================================================================

def adapt_hyperparameters(
    current_params: Dict[str, Any],
    actual_nums: List[int],
    prev_nums: Optional[List[int]] = None,
    focal_loss: Optional[float] = None,
    sigma_bounds: Tuple[float, float] = (1.50, 3.50),
    lambda_bounds: Tuple[float, float] = (0.85, 0.98),
    sigma_step: float = 0.05,
    lambda_step: float = 0.01,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    根据物理残差自适应反向微调空间高斯核宽 sigma 与时序衰减率 lambda。
    大白话：根据昨天的扎堆程度和重号表现，自动调节今天的能量扩散范围与历史记忆强度。

    :param current_params: 当前参数字典 {"sigma": 2.5, "lambda_decay": 0.95, ...}
    :param actual_nums: 上期真实 20 码开奖
    :param prev_nums: 上上期真实开奖 (用于计算重号)
    :param focal_loss: 上期 Focal Loss 损失值
    :param sigma_bounds: 空间核宽安全边界 [min, max], 默认 [1.50, 3.50]
    :param lambda_bounds: 时序衰减安全边界 [min, max], 默认 [0.85, 0.98]
    :param sigma_step: 核宽微调单步步长 (默认 0.05)
    :param lambda_step: 时序衰减微调单步步长 (默认 0.01)
    :return: (new_params_dict, rationales_list)
    """
    cur_sigma = float(current_params.get("sigma", 2.50))
    cur_lambda = float(current_params.get("lambda_decay", 0.95))
    rationales: List[str] = []

    # 1. 空间高斯核宽 sigma 动态微调 (看号码扎堆还是分散)
    mean_diff = calculate_spatial_dispersion(actual_nums)
    sig_min, sig_max = sigma_bounds

    if mean_diff < 3.65:
        # 号码局部聚集 (平均间距 < 3.65)，收紧核宽提高峰值分辨率
        new_sigma = max(sig_min, round(cur_sigma - sigma_step, 2))
        rationales.append(
            f"🌌 上期号码高度局部聚集 (平均间距 {mean_diff:.2f} < 3.65)，空间高斯核宽自适应收紧 (大白话：开奖号扎堆，缩小核宽精准聚焦): {cur_sigma:.2f} ➔ {new_sigma:.2f}"
        )
    elif mean_diff > 3.95:
        # 号码全盘分散 (平均间距 > 3.95)，展宽视野平滑覆盖
        new_sigma = min(sig_max, round(cur_sigma + sigma_step, 2))
        rationales.append(
            f"🌌 上期号码全盘扩散分散 (平均间距 {mean_diff:.2f} > 3.95)，空间高斯核宽自适应展宽 (大白话：开奖号分散，放宽视野平滑覆盖): {cur_sigma:.2f} ➔ {new_sigma:.2f}"
        )
    else:
        new_sigma = cur_sigma
        rationales.append(
            f"🌌 上期空间分布平稳均衡 (平均间距 {mean_diff:.2f})，空间核宽保持稳定: {new_sigma:.2f}"
        )

    # 强制安全边界约束
    new_sigma = float(np.clip(new_sigma, sig_min, sig_max))

    # 2. 时序半衰衰减率 lambda 动态微调 (看重号灵不灵)
    repeat_count = calculate_repeat_count(actual_nums, prev_nums)
    lam_min, lam_max = lambda_bounds

    if repeat_count >= 6:
        # 重号爆发，时序惯性极大
        new_lambda = min(lam_max, round(cur_lambda + lambda_step, 2))
        rationales.append(
            f"⏱️ 上期重号高达 {repeat_count} 个 (时序惯性强)，时序半衰记忆率调高 (大白话：昨天开出的号今天还爱出，加重昨天记忆): {cur_lambda:.2f} ➔ {new_lambda:.2f}"
        )
    elif repeat_count <= 3:
        # 重号极少，大盘跳空变盘
        new_lambda = max(lam_min, round(cur_lambda - lambda_step, 2))
        rationales.append(
            f"⏱️ 上期重号仅 {repeat_count} 个 (惯性减弱变盘)，时序半衰记忆率调低 (大白话：大盘跳空变盘，减少对昨天的迷信): {cur_lambda:.2f} ➔ {new_lambda:.2f}"
        )
    else:
        new_lambda = cur_lambda
        rationales.append(
            f"⏱️ 上期重号 {repeat_count} 个符合常态，时序衰减率维持: {new_lambda:.2f}"
        )

    # 强制安全边界约束
    new_lambda = float(np.clip(new_lambda, lam_min, lam_max))

    # 3. 组装新参数
    new_params = dict(current_params)
    new_params["sigma"] = round(new_sigma, 2)
    new_params["lambda_decay"] = round(new_lambda, 2)
    if focal_loss is not None:
        new_params["last_loss"] = round(float(focal_loss), 4)

    return new_params, rationales


# =====================================================================
# 4. 模块导出与向后兼容绑定
# =====================================================================

def __getattr__(name: str):
    """延迟兼容导入 UnifiedBrainEvolutionEngine 避免循环引用"""
    if name == "UnifiedBrainEvolutionEngine":
        from .evolution_engine import UnifiedBrainEvolutionEngine
        return UnifiedBrainEvolutionEngine
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
