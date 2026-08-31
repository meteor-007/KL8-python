# -*- coding: utf-8 -*-
"""
快乐8 熵控优化引擎 (Entropy-Based Optimization Engine - Layer E)
============================================================
1. 信息熵评估: 计算号码出现的 Shannon Entropy，识别规律性。
2. 互信息矩阵: 计算号码间的 Mutual Information，识别协同效应。
3. mRMR 筛选: 最大化相关性，最小化冗余度 (Max-Relevance Min-Redundancy)。
4. 动态对冲: 基于全系统熵值波动调整预测激进程度。
"""
import math
import collections
import os
import numpy as np

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
HISTORY_FILE = os.path.join(_PROJ, 'kl8_history_final.txt')

def load_history(limit=100):
    """v2.2: 委托给 utils.history_loader，保持返回格式 list[list[int]] 不变。"""
    from utils.history_loader import load_history as _load
    data = _load(limit=limit)
    return [h['numbers'] for h in data]

def calculate_shannon_entropy(series):
    """计算序列的香农熵"""
    if not series: return 0
    counts = collections.Counter(series)
    total = len(series)
    ent = -sum((c/total) * math.log2(c/total) for c in counts.values())
    return ent

def get_number_entropy_scores(history):
    """计算每个号码的遗漏间隔熵"""
    scores = {}
    for num in range(1, 81):
        gaps = []
        last_idx = -1
        for i, draw in enumerate(reversed(history)):
            if num in draw:
                if last_idx != -1:
                    gaps.append(i - last_idx)
                last_idx = i
        
        if len(gaps) < 3:
            scores[num] = 4.0 # 高熵，不确定性大
        else:
            ent = calculate_shannon_entropy(gaps)
            scores[num] = ent
    return scores

def calculate_mutual_information(num1, num2, history):
    """
    计算两个号码间的互信息 (标准四项公式)

    数学依据: Cover & Thomas《信息论基础》定理2.2
    MI(X,Y) = Σ_{x∈{0,1}, y∈{0,1}} P(x,y) * log2(P(x,y) / (P(x)*P(y)))

    必须计算 (1,1), (1,0), (0,1), (0,0) 四项, 否则MI估计有偏。
    """
    total = len(history)
    if total == 0:
        return 0.0
    p1 = sum(1 for d in history if num1 in d) / total
    p2 = sum(1 for d in history if num2 in d) / total
    p12 = sum(1 for d in history if num1 in d and num2 in d) / total

    # 联合分布四项
    p_x1_y1 = p12
    p_x1_y0 = p1 - p12
    p_x0_y1 = p2 - p12
    p_x0_y0 = 1.0 - p1 - p2 + p12

    mi = 0.0
    eps = 1e-12
    for p_xy, p_x, p_y in [
        (p_x1_y1, p1, p2),
        (p_x1_y0, p1, 1.0 - p2),
        (p_x0_y1, 1.0 - p1, p2),
        (p_x0_y0, 1.0 - p1, 1.0 - p2),
    ]:
        if p_xy > eps and p_x > eps and p_y > eps:
            mi += p_xy * math.log2(p_xy / (p_x * p_y))
    return mi

def mrmr_optimize(candidate_pool, history, top_k=12):
    """
    Max-Relevance Min-Redundancy 优化
    Relevance: 号码本身的得分 (此处暂用 1/Entropy)
    Redundancy: 号码间的互信息
    """
    if not candidate_pool: return []
    
    entropies = get_number_entropy_scores(history)
    relevance = {n: (1.0 / (entropies.get(n, 1.0) + 1e-9)) for n in candidate_pool}
    
    selected = []
    remaining = list(candidate_pool)
    
    # 第一个选 Relevance 最高的
    first = max(remaining, key=lambda n: relevance[n])
    selected.append(first)
    remaining.remove(first)
    
    while len(selected) < top_k and remaining:
        best_score = -float('inf')
        best_num = None
        
        for n in remaining:
            rel = relevance[n]
            red = sum(calculate_mutual_information(n, s, history) for s in selected) / len(selected)
            score = rel - red
            if score > best_score:
                best_score = score
                best_num = n
        
        if best_num:
            selected.append(best_num)
            remaining.remove(best_num)
        else:
            break
            
    return selected

def get_full_entropy_scores(history):
    """计算全量号码的熵控得分 (1-80)"""
    # 1. 计算遗漏熵
    ent_scores = get_number_entropy_scores(history)
    
    # 2. 转换为得分 (1/Entropy) 并归一化到 0-1
    max_ent = max(ent_scores.values()) if ent_scores else 1.0
    scores = {n: (1.0 - ent_scores.get(n, max_ent)/max_ent) for n in range(1, 81)}
    
    # 3. 增强：互信息惩罚 (Redundancy Reduction)
    # 选取前 20 个高得分号码进行互信息对冲
    top_candidates = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)[:20]
    for n in top_candidates:
        red = sum(calculate_mutual_information(n, s, history) for s in top_candidates if s != n)
        scores[n] -= red * 0.5 # 惩罚项
        
    return scores

def run_entropy_optimization(history):
    """执行熵控优化全流程"""
    # 兼容历史数据格式 (可以是 dict 列表或 int 列表)
    if history and isinstance(history[0], dict):
        hist_lists = [h['numbers'] for h in history]
    else:
        hist_lists = history

    # 1. 初始候选池 (基于 Layer A 的初步筛选)
    try:
        from core.feature_optimizer import get_all_layer_a_scores
        # get_all_layer_a_scores 期望 dict 记录(访问 h['issue']), 这里需传原始 dict 列表而非 int 列表
        a_scores = get_all_layer_a_scores(history if history and isinstance(history[0], dict) else None)
        base_pool = [n for n, s in sorted(a_scores.items(), key=lambda x: -x[1])[:30]]
    except Exception:
        f20 = collections.Counter(n for d in hist_lists[:20] for n in d)
        base_pool = [n for n, c in f20.most_common(30)]
    
    # 2. mRMR 提纯
    optimized_12 = mrmr_optimize(base_pool, hist_lists, top_k=12)

    # system_entropy: 使用最近20期聚合数据 (单期20号样本量过小, 噪声极大)
    # 统计学依据: 样本量 >= 400 (20期*20号) 才能保证Shannon熵估计的稳定性
    agg_window = hist_lists[:20] if len(hist_lists) >= 20 else hist_lists
    system_entropy = calculate_shannon_entropy([n for d in agg_window for n in d])

    return {
        "optimized_top12": optimized_12,
        "optimized_top5": optimized_12[:5],
        "system_entropy": system_entropy
    }

if __name__ == "__main__":
    hist = load_history(100)
    res = run_entropy_optimization(hist)
    print(f"熵控优化结果: {res['optimized_top12']}")
