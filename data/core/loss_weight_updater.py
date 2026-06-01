# -*- coding: utf-8 -*-
"""
Loss Function 回溯比对权重更新 + Hurst系数估计
================================================
实现技术白皮书中描述的 Cross-Entropy Loss + Softmax 权重更新机制,
以及正确的多尺度 R/S 分析 Hurst 系数估计。
"""
import os
import json
import math
import collections
import numpy as np
from typing import Dict, List, Tuple, Optional

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOSS_HISTORY_FILE = os.path.join(_PROJ, 'cache', 'loss_history.json')


# ══════════════════════════════════════════════════════════════════
#  核心模块一: Loss Function 回溯比对权重更新
# ══════════════════════════════════════════════════════════════════

def compute_cross_entropy_loss(prediction_probs: Dict[int, float],
                                actual_numbers: List[int],
                                num_total: int = 80) -> float:
    """
    计算交叉熵损失
    
    Args:
        prediction_probs: 各号码的预测概率 {1: 0.3, 2: 0.1, ...}
        actual_numbers: 实际开奖号码列表
        num_total: 号码总数 (默认80)
    
    Returns:
        交叉熵损失值 (越小越好)
    """
    actual_set = set(actual_numbers)
    loss = 0.0
    for n in range(1, num_total + 1):
        y = 1.0 if n in actual_set else 0.0
        p = np.clip(prediction_probs.get(n, 0.25), 1e-15, 1 - 1e-15)
        loss -= y * np.log(p) + (1 - y) * np.log(1 - p)
    return loss / num_total


def compute_mse_loss(prediction_probs: Dict[int, float],
                     actual_numbers: List[int],
                     num_total: int = 80) -> float:
    """计算均方误差损失"""
    actual_set = set(actual_numbers)
    loss = 0.0
    for n in range(1, num_total + 1):
        y = 1.0 if n in actual_set else 0.0
        p = prediction_probs.get(n, 0.25)
        loss += (y - p) ** 2
    return loss / num_total


def softmax_weight_update(losses: Dict[str, float],
                          temperature: float = 0.5) -> Dict[str, float]:
    """
    Softmax权重更新: Loss越小 → 新权重越大
    
    公式: W_k^(t+1) = exp(-Loss_k / τ) / Σ exp(-Loss_j / τ)
    
    Args:
        losses: 各算子的损失值 {'markov': 0.8, 'energy': 0.6, ...}
        temperature: 温度系数 (越小权重差异越大)
    
    Returns:
        更新后的权重字典 (和为1)
    """
    if not losses:
        return {}
    
    exp_vals = {}
    for name, loss in losses.items():
        exp_vals[name] = math.exp(-loss / temperature)
    
    total = sum(exp_vals.values())
    if total == 0:
        # 全部Loss为0时等权
        n = len(losses)
        return {name: 1.0 / n for name in losses}
    
    weights = {name: val / total for name, val in exp_vals.items()}
    return weights


class LossBasedWeightUpdater:
    """
    Loss Function 回溯比对权重更新器
    
    工作流程:
    1. 记录上一期各算子的预测概率向量
    2. 开奖后, 计算各算子的交叉熵损失
    3. 用Softmax权重更新公式调整各算子权重
    4. 将新权重持久化, 供下次预测使用
    """
    
    def __init__(self):
        self._loss_history = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        if os.path.exists(LOSS_HISTORY_FILE):
            try:
                with open(LOSS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f).get('records', [])
            except Exception:
                return []
        return []
    
    def _save_history(self):
        os.makedirs(os.path.dirname(LOSS_HISTORY_FILE), exist_ok=True)
        try:
            from config import get_config
            cfg = get_config()
            max_records = cfg.get('loss_function.max_history_losses', 30)
        except Exception:
            max_records = 30
        
        self._loss_history = self._loss_history[-max_records:]
        with open(LOSS_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({'records': self._loss_history}, f, ensure_ascii=False, indent=2)
    
    def record_predictions(self, period: str, algo_predictions: Dict[str, Dict[int, float]]):
        """
        记录预测概率向量 (在开奖前调用)
        
        Args:
            period: 期号
            algo_predictions: 各算子的预测概率 {'markov': {1: 0.3, ...}, 'bayesian': {...}, ...}
        """
        record = {
            'period': period,
            'predictions': {name: {str(n): round(p, 6) for n, p in probs.items()}
                           for name, probs in algo_predictions.items()},
            'losses': {},
            'weights': {}
        }
        self._loss_history.append(record)
        self._save_history()
    
    def update_with_actual(self, period: str, actual_numbers: List[int]) -> Dict[str, float]:
        """
        用实际开奖结果更新Loss和权重 (在开奖后调用)
        
        Args:
            period: 期号
            actual_numbers: 实际开奖号码
        
        Returns:
            更新后的权重字典
        """
        try:
            from config import get_config
            cfg = get_config()
            temperature = cfg.get('loss_function.temperature', 0.5)
            method = cfg.get('loss_function.method', 'cross_entropy')
        except Exception:
            temperature = 0.5
            method = 'cross_entropy'
        
        # 找到该期号的预测记录
        target_record = None
        for record in self._loss_history:
            if record['period'] == period:
                target_record = record
                break
        
        if target_record is None:
            return {}
        
        # 计算各算子Loss
        losses = {}
        loss_fn = compute_cross_entropy_loss if method == 'cross_entropy' else compute_mse_loss
        for algo_name, pred_dict in target_record['predictions'].items():
            probs = {int(n): p for n, p in pred_dict.items()}
            loss = loss_fn(probs, actual_numbers)
            losses[algo_name] = round(loss, 6)
        
        # Softmax权重更新
        new_weights = softmax_weight_update(losses, temperature)
        
        # 记录
        target_record['losses'] = losses
        target_record['weights'] = {k: round(v, 4) for k, v in new_weights.items()}
        self._save_history()
        
        print(f"[Loss更新] 期号{period}:")
        for name, loss in sorted(losses.items(), key=lambda x: x[1]):
            w = new_weights.get(name, 0)
            print(f"  {name:15s}: Loss={loss:.4f} → Weight={w:.2%}")
        
        return new_weights
    
    def get_current_weights(self) -> Dict[str, float]:
        """获取最新的权重 (来自最近一次Loss更新)"""
        for record in reversed(self._loss_history):
            if record.get('weights'):
                return record['weights']
        return {}  # 无历史记录时返回空, 调用方使用默认权重
    
    def get_recent_performance(self, lookback: int = 10) -> Dict[str, Dict]:
        """获取各算子近N期的Loss统计"""
        recent = [r for r in self._loss_history if r.get('losses')][-lookback:]
        if not recent:
            return {}
        
        stats = {}
        for record in recent:
            for name, loss in record['losses'].items():
                if name not in stats:
                    stats[name] = {'losses': [], 'weights': []}
                stats[name]['losses'].append(loss)
                if name in record.get('weights', {}):
                    stats[name]['weights'].append(record['weights'][name])
        
        result = {}
        for name, data in stats.items():
            losses = data['losses']
            weights = data['weights']
            result[name] = {
                'avg_loss': round(sum(losses) / len(losses), 4),
                'min_loss': round(min(losses), 4),
                'max_loss': round(max(losses), 4),
                'avg_weight': round(sum(weights) / len(weights), 4) if weights else 0,
                'n_periods': len(losses)
            }
        return result


# ══════════════════════════════════════════════════════════════════
#  核心模块二: Hurst 系数估计 (多尺度 R/S 回归修正版)
# ══════════════════════════════════════════════════════════════════

def estimate_hurst_coefficient(series: List[float],
                                min_scale: int = 10,
                                n_scales: int = 5) -> float:
    """
    Hurst 系数的多尺度 R/S 分析估计 — 修正版
    
    原理:
      经典R/S分析法: 在多个时间尺度n下计算 R(n)/S(n),
      然后通过 log(R/S) ~ H * log(n) 回归估计Hurst指数H。
      
      H < 0.5: 均值回复 (反持续)
      H = 0.5: 随机游走
      H > 0.5: 趋势持续
      
    修正点:
      - 旧版: 仅用单点 log(R/S)/log(n), 仅在n→∞时成立, 短序列偏差大
      - 新版: 多尺度回归, 使用至少5个不同尺度, 更稳健
    
    Args:
        series: 时间序列数据 (如各期命中数)
        min_scale: 最小尺度
        n_scales: 尺度数量
    
    Returns:
        Hurst系数 (0-1之间)
    """
    try:
        from config import get_config
        cfg = get_config()
        min_len = cfg.get('hurst.min_series_length', 150)
        cfg_scales = cfg.get('hurst.n_scales', 5)
        n_scales = max(n_scales, cfg_scales)
    except Exception:
        min_len = 150
    
    # 物理锁死防线红线四：150期以下默认0.5
    if len(series) < 150:
        return 0.5
    
    arr = np.array(series, dtype=float)
    n_total = len(arr)
    
    scales = [5, 10, 20, 30, 40, 60]
    scales = [s for s in scales if s < n_total]
    
    if len(scales) < 3:
        return 0.5
    
    log_ns = []
    log_rs = []
    
    for n in scales:
        if n < 2 or n >= n_total:
            continue
        
        # 将序列分为 n_total // n 个子段, 计算平均 R/S
        n_subsegments = n_total // n
        if n_subsegments < 1:
            continue
        
        rs_values = []
        for seg in range(n_subsegments):
            segment = arr[seg * n : (seg + 1) * n]
            if len(segment) < 2:
                continue
            
            mean = segment.mean()
            deviations = segment - mean
            cumdev = np.cumsum(deviations)
            R = cumdev.max() - cumdev.min()
            S = np.sqrt(np.mean(deviations ** 2))
            
            if S > 0:
                rs_values.append(R / S)
        
        if rs_values:
            avg_rs = np.mean(rs_values)
            log_ns.append(math.log(n))
            log_rs.append(math.log(avg_rs))
    
    if len(log_ns) < 3:
        return 0.5
    
    # 线性回归: log(R/S) = H * log(n) + c
    log_ns = np.array(log_ns)
    log_rs = np.array(log_rs)
    
    # 最小二乘法
    n_pts = len(log_ns)
    sum_x = log_ns.sum()
    sum_y = log_rs.sum()
    sum_xy = (log_ns * log_rs).sum()
    sum_x2 = (log_ns ** 2).sum()
    
    denominator = n_pts * sum_x2 - sum_x ** 2
    if abs(denominator) < 1e-10:
        return 0.5
    
    H = (n_pts * sum_xy - sum_x * sum_y) / denominator
    
    # 限制在合理范围 [0.20, 0.80] (神父防线红线四)
    H = max(0.20, min(0.80, H))
    
    return round(H, 4)


# ══════════════════════════════════════════════════════════════════
#  便利函数: 将五维一体评分转为概率分布
# ══════════════════════════════════════════════════════════════════

def scores_to_probabilities(scores: Dict[int, float], temperature: float = 1.0) -> Dict[int, float]:
    """
    将评分转为概率分布 (Softmax归一化)
    
    确保所有概率之和为1, 且每个概率在(0,1)区间,
    便于Loss Function计算交叉熵。
    
    Args:
        scores: 各号码的评分 {1: 5.2, 2: 3.1, ...}
        temperature: 温度系数 (越高分布越平坦)
    
    Returns:
        概率分布 {1: 0.015, 2: 0.008, ...}
    """
    if not scores:
        return {n: 1.0 / 80 for n in range(1, 81)}
    
    exp_scores = {}
    for n, s in scores.items():
        exp_scores[n] = math.exp(s / temperature)
    
    total = sum(exp_scores.values())
    if total == 0:
        return {n: 1.0 / 80 for n in range(1, 81)}
    
    probs = {n: val / total for n, val in exp_scores.items()}
    
    # 补全未在scores中的号码 (给极小概率)
    for n in range(1, 81):
        if n not in probs:
            probs[n] = 1e-6
    
    # 重新归一化
    total = sum(probs.values())
    probs = {n: p / total for n, p in probs.items()}
    
    return probs


if __name__ == '__main__':
    # 测试Loss Function更新
    updater = LossBasedWeightUpdater()
    
    # 模拟: 假设3个算子的预测
    test_preds = {
        'markov': {n: 0.3 if n in [5, 12, 23, 34, 45] else 0.2 for n in range(1, 81)},
        'energy': {n: 0.35 if n in [5, 17, 28, 39, 50] else 0.18 for n in range(1, 81)},
        'bayesian': {n: 0.28 if n in [5, 12, 50, 67, 78] else 0.22 for n in range(1, 81)},
    }
    
    # 转为概率分布
    for name in test_preds:
        scores = test_preds[name]
        total = sum(scores.values())
        test_preds[name] = {n: s / total for n, s in scores.items()}
    
    updater.record_predictions('2026133', test_preds)
    
    # 模拟开奖
    actual = [5, 12, 17, 23, 34, 39, 45, 50, 55, 60, 65, 67, 70, 72, 75, 78, 10, 15, 20, 25]
    new_weights = updater.update_with_actual('2026133', actual)
    
    print(f"\n更新后权重: {new_weights}")
    
    # 测试Hurst系数
    import random
    test_series = [random.randint(0, 5) for _ in range(100)]
    H = estimate_hurst_coefficient(test_series)
    print(f"\n测试序列Hurst系数: {H}")
