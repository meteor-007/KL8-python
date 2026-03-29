# -*- coding: utf-8 -*-
"""
deep_analysis.py

A new module for advanced, data-driven analysis of lottery number patterns.
This moves beyond simple heuristics to incorporate statistical and time-series analysis.
"""

import numpy as np
import pandas as pd
from collections import Counter, defaultdict
import math

def get_full_history_df(historical_snapshots):
    """
    Converts the historical snapshot dictionary into a pandas DataFrame for easier analysis.

    Args:
        historical_snapshots (dict): A dictionary with date strings as keys and lists of winning numbers as values.
                                     Example: {'2026-03-24': ['02', '03', ...], ...}

    Returns:
        pd.DataFrame: A DataFrame where the index is a DatetimeIndex, and each column represents a number from 01 to 80.
                      The cell value is 1 if the number was drawn on that date, 0 otherwise.
    """
    if not historical_snapshots:
        return pd.DataFrame()

    # Convert date strings to datetime objects for time-series analysis
    dates = sorted(pd.to_datetime(historical_snapshots.keys()))
    
    # Create a mapping from date to its numbers
    data_map = {pd.to_datetime(k): v for k, v in historical_snapshots.items()}

    # Initialize a DataFrame with all possible numbers as columns
    all_numbers = [f"{n:02d}" for n in range(1, 81)]
    df = pd.DataFrame(0, index=dates, columns=all_numbers)

    # Populate the DataFrame
    for date, numbers in data_map.items():
        df.loc[date, numbers] = 1
    
    return df

def analyze_number_trends(history_df, number):
    """
    Performs a detailed time-series analysis for a single number.

    Args:
        history_df (pd.DataFrame): The DataFrame of historical draws.
        number (str): The number to analyze (e.g., '05').

    Returns:
        dict: A dictionary containing key trend metrics for the number.
    """
    if history_df.empty or number not in history_df.columns:
        return {
            "total_appearances": 0,
            "overall_frequency": 0,
            "last_10_freq": 0,
            "last_30_freq": 0,
            "current_omission": 0, # 当前遗漏
            "max_omission": 0, # 最大遗漏
            "avg_cycle": 0, # 平均出现周期
            "is_hot": False, # 是否为热号
        }

    series = history_df[number]
    
    # Calculate Omission (遗漏)
    appearances = series[series == 1]
    omission_periods = appearances.index.to_series().diff().dt.days.dropna() - 1
    max_omission = omission_periods.max() if not omission_periods.empty else len(series)
    current_omission = (series.index.max() - appearances.index.max()).days if not appearances.empty else len(series)

    # Calculate frequencies
    total_appearances = series.sum()
    overall_frequency = total_appearances / len(series) if len(series) > 0 else 0
    
    # Rolling frequencies for trend detection
    last_10_draws = series.tail(10)
    last_30_draws = series.tail(30)
    last_10_freq = last_10_draws.mean()
    last_30_freq = last_30_draws.mean()

    # Determine if a number is "hot" (e.g., frequency in last 30 days is significantly above average)
    is_hot = last_30_freq > (overall_frequency * 1.5)

    return {
        "total_appearances": int(total_appearances),
        "overall_frequency": f"{overall_frequency:.2%}",
        "last_10_freq": f"{last_10_freq:.2%}",
        "last_30_freq": f"{last_30_freq:.2%}",
        "current_omission": int(current_omission),
        "max_omission": int(max_omission) if pd.notna(max_omission) else int(current_omission),
        "avg_cycle": f"{omission_periods.mean():.2f}" if not omission_periods.empty else "N/A",
        "is_hot": is_hot,
    }

def find_number_associations(history_df, lookback=30):
    """
    Finds associations between numbers. For each number, determines which numbers are most likely to appear with it or after it.
    This uses a simplified Apriori-like logic.

    Args:
        history_df (pd.DataFrame): The DataFrame of historical draws.
        lookback (int): The number of recent draws to consider for the analysis.

    Returns:
        dict: A dictionary where each key is a number, and the value is another dict
              containing 'accompanying' and 'following' number suggestions.
              e.g., {'05': {'accompanying': ['12', '34'], 'following': ['08', '21']}}
    """
    if history_df.empty:
        return {}

    df = history_df.tail(lookback)
    all_numbers = df.columns
    association_rules = {}

    for num in all_numbers:
        # Find numbers that frequently appear in the SAME draw
        draws_with_num = df[df[num] == 1]
        if draws_with_num.empty:
            continue
        
        # Calculate co-occurrence (Accompanying numbers)
        co_occurrence = draws_with_num.sum().sort_values(ascending=False)
        co_occurrence = co_occurrence.drop(num, errors='ignore') # Drop the number itself
        accompanying_top_3 = co_occurrence[co_occurrence > 0].head(3).index.tolist()

        # Find numbers that frequently appear in the NEXT draw
        following_counts = Counter()
        for date in draws_with_num.index:
            next_date = date + pd.Timedelta(days=1)
            if next_date in df.index:
                following_draw_numbers = df.loc[next_date][df.loc[next_date] == 1].index.tolist()
                following_counts.update(following_draw_numbers)
        
        following_top_3 = [item[0] for item in following_counts.most_common(3)]
        
        if accompanying_top_3 or following_top_3:
            association_rules[num] = {
                "accompanying": accompanying_top_3,
                "following": following_top_3
            }
            
    return association_rules

def analyze_matrix_hot_zones(expert_data, historical_snapshots):
    """
    Analyzes the historical performance of each cell in the expert matrices to identify "hot zones".

    Args:
        expert_data (dict): The complete expert data history (e.g., `ed1` or `ed2`).
        historical_snapshots (dict): The history of actual winning numbers.

    Returns:
        pd.DataFrame: A DataFrame where index is a multi-index of (block_id, row_id) and columns
                      are column_ids. Values are the hit rate for that cell.
                      e.g., index=(B1-L, 0), columns=[0,1,2,3], values=[0.25, 0.1, ...]
    """
    from main_workflow import get_expert_matrix_sets

    all_dates = sorted(expert_data.keys())
    
    hits = Counter()
    total = Counter()

    for date in all_dates:
        actual_draw = historical_snapshots.get(date, set())
        if not actual_draw:
            continue
        
        matrices = get_expert_matrix_sets(expert_data, date)
        
        for i, block in enumerate(matrices):
            for m_sub_idx, m_sub_name in enumerate(['L', 'R']): # Left/Right sub-matrices
                matrix_id = f"B{i+1}-{m_sub_name}"
                for r_idx in range(4):
                    row = block[r_idx]
                    sub_row = row[0:4] if m_sub_idx == 0 else row[4:8]
                    for c_idx, val in enumerate(sub_row):
                        if val:
                            cell_id = (matrix_id, r_idx, c_idx)
                            total[cell_id] += 1
                            if val.zfill(2) in actual_draw:
                                hits[cell_id] += 1
    
    # Create a DataFrame from the counters
    if not total:
        return pd.DataFrame()

    df_data = []
    for cell_id, total_count in total.items():
        hit_count = hits.get(cell_id, 0)
        hit_rate = hit_count / total_count
        df_data.append({
            "matrix_id": cell_id[0],
            "row": cell_id[1],
            "col": cell_id[2],
            "hit_rate": hit_rate,
            "total_count": total_count
        })

    return pd.DataFrame(df_data)

# === 💎 顶级数据专家·矩阵动力学扩展 (Advanced Matrix Dynamics) ===

def calculate_matrix_metrics(matrix_block, actual_draw_history=None, prev_matrix_block=None):
    """
    计算 4x4 矩阵的深度动力学指标。
    
    Args:
        matrix_block (list): 4x4 的号码列表 (str)
        actual_draw_history (list): 近期开奖号码集合列表 (sets of str)
        prev_matrix_block (list): 上一期的 4x4 矩阵块
        
    Returns:
        dict: 包含 Energy, Stability, Centroid, Entropy 等指标
    """
    nums = [n.zfill(2) for r in matrix_block for n in r if n]
    if not nums:
        return {"energy": 0, "stability": 0, "centroid": (0,0), "entropy": 0, "density": 0}

    density = len(nums) / 16.0
    
    # 1. 能量计算 (Energy): 密度 * 历史命中动量
    energy = density * 10.0 # 基础分
    if actual_draw_history:
        for i, draw in enumerate(reversed(actual_draw_history[-5:])):
            weight = (i + 1) / 5.0 # 时间权重
            hits = len([n for n in nums if n in draw])
            energy += (hits * weight * 3.0)

    # 2. 稳定性计算 (Stability): 与上一期号码的重合度 (Jaccard)
    stability = 0
    if prev_matrix_block:
        prev_nums = set([n.zfill(2) for r in prev_matrix_block for n in r if n])
        curr_nums = set(nums)
        if prev_nums or curr_nums:
            intersection = len(prev_nums.intersection(curr_nums))
            union = len(prev_nums.union(curr_nums))
            stability = intersection / union if union > 0 else 0

    # 3. 质心计算 (Centroid): 计算号码在 4x4 网格中的平均分布重心
    r_sum, c_sum, count = 0, 0, 0
    for r in range(4):
        for c in range(4):
            if matrix_block[r][c]:
                r_sum += r; c_sum += c; count += 1
    centroid = (r_sum / count, c_sum / count) if count > 0 else (1.5, 1.5)

    # 4. 结构熵 (Structural Entropy)
    counts = Counter(nums)
    probs = [c/len(nums) for c in counts.values()]
    entropy = -sum(p * math.log2(p) for p in probs) if probs else 0

    return {
        "energy": round(energy, 2),
        "stability": round(stability, 2),
        "centroid": (round(centroid[0], 2), round(centroid[1], 2)),
        "entropy": round(entropy, 2),
        "density": round(density, 2),
        "count": len(nums)
    }

def analyze_matrix_correlations(expert_data_1, expert_data_2, last_n=20):
    """
    分析两个数据源矩阵之间的耦合度 (Cross-Manifold Coupling/Correlation)
    """
    dates = sorted(expert_data_1.keys())[-last_n:]
    correlations = defaultdict(int)
    
    for dt in dates:
        m1_latest = expert_data_1.get(dt, {})
        m2_latest = expert_data_2.get(dt, {})
        
        # 简化逻辑：如果两个源在同一位置(SI-idx)都填了号，记录一次“耦合”
        for si in set(m1_latest.keys()).intersection(m2_latest.keys()):
            n1 = set([x for x in m1_latest[si] if x])
            n2 = set([x for x in m2_latest[si] if x])
            if n1.intersection(n2):
                correlations[si] += 1
                
    return correlations

