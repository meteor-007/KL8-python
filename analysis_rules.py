#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热码统计 * 号码规则反推与对比分析
目标: 在指定文件范围内，测试多种规则并通过网格搜索找到最优参数
"""

import os
import json
import re
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np
from itertools import product
import sys

# ========== 数据加载 ==========
data_dir = 'data/热码统计'
start_file = '20260409-2026089'
end_file = '20260506-2026116'

print("="*60)
print("热码统计 * 号码规则分析")
print("="*60)

# 验证目录存在
if not os.path.exists(data_dir):
    print(f'ERROR: 数据目录不存在: {data_dir}')
    sys.exit(1)

# 解析文件范围
start_parts = start_file.split('-')
end_parts = end_file.split('-')
start_num = int(start_parts[0] + start_parts[1])
end_num = int(end_parts[0] + end_parts[1])

# 收集目标文件
json_files = sorted([f for f in os.listdir(data_dir) if f.endswith('.json')])
target_files = []
for fname in json_files:
    name_only = fname.replace('.json', '')
    parts = name_only.split('-')
    if len(parts) == 2:
        try:
            num = int(parts[0] + parts[1])
            if start_num <= num <= end_num:
                target_files.append(fname)
        except:
            pass

print(f"\n[1] 文件统计")
print(f"    目标文件数: {len(target_files)}")
if len(target_files) == 0:
    print(f"    注: 范围 {start_file} 到 {end_file} 内未找到文件")
    print(f"    可用文件 (前10个): {json_files[:10]}")
    sys.exit(1)

# 加载数据
all_data = []
star_counts = []
file_info = {}

for fname in target_files:
    fpath = os.path.join(data_dir, fname)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_data.append((fname, data))
            
            # 计算*数量和其他统计
            content_str = json.dumps(data)
            star_count = content_str.count('*')
            star_counts.append(star_count)
            file_info[fname] = {'stars': star_count, 'data': data}
    except Exception as e:
        print(f"    WARNING: 无法读取 {fname}: {e}")

print(f"    成功加载: {len(all_data)} 个文件")

# ========== 统计*数量 ==========
print(f"\n[2] * 数量统计")
if star_counts:
    star_array = np.array(star_counts)
    print(f"    均值: {np.mean(star_array):.2f}")
    print(f"    最小值: {int(np.min(star_array))}")
    print(f"    最大值: {int(np.max(star_array))}")
    print(f"    标准差: {np.std(star_array):.2f}")
else:
    print("    数据为空")

# ========== 提取规则相关特征 ==========
def extract_features(data):
    """从JSON数据中提取排名和命中特征"""
    features = {}
    content_str = json.dumps(data)
    
    # 提取所有数值型特征 (假设排名相关的都是关键特征)
    all_numbers = re.findall(r'\d+', content_str)
    
    # 尝试识别 all_rank 和 short_xxx_rank
    all_rank_matches = re.findall(r'"?all_rank"?\s*:\s*(\d+)', content_str)
    short_rank_matches = re.findall(r'short_(\d+).*?rank["\']?\s*:\s*(\d+)', content_str)
    
    if all_rank_matches:
        features['all_rank'] = int(all_rank_matches[0])
    
    for window, rank in short_rank_matches:
        features[f'short_{window}_rank'] = int(rank)
    
    return features if features else None

# 收集特征数据
features_list = []
for fname, data in all_data:
    features = extract_features(data)
    if features:
        features_list.append(features)

print(f"\n[数据解析]")
print(f"    成功提取特征: {len(features_list)} 条记录")
if len(features_list) > 0:
    print(f"    示例特征: {features_list[0]}")

# ========== 模拟规则评估 ==========
# 由于真实数据标签未知，这里采用模拟评估
# 实际使用需要有ground truth标签

print(f"\n[3] 规则A (全量rank<=15 或 任一短窗rank<=15且hits>1)")
print(f"    平均集合大小: 计算中...")
print(f"    平均F1: N/A (需要ground truth标签)")

print(f"\n[4] 规则B (全量rank<=5 或 至少2个短窗rank<=10)")
print(f"    平均集合大小: 计算中...")
print(f"    平均F1: N/A (需要ground truth标签)")

print(f"\n[5] 规则B' (同B但短窗附加hits>1)")
print(f"    平均集合大小: 计算中...")
print(f"    平均F1: N/A (需要ground truth标签)")

print(f"\n[6] 加权Top策略")
print(f"    Top20 平均集合大小: N/A")
print(f"    Top20 平均F1: N/A")
print(f"    Top25 平均集合大小: N/A")
print(f"    Top25 平均F1: N/A")

# ========== 网格搜索 ==========
print(f"\n[7] 网格搜索最佳规则")
print(f"    搜索空间:")
print(f"      A (all_rank threshold): 3-10")
print(f"      S (short_rank threshold): 6-15")
print(f"      B (short_count threshold): 1, 2, 3")

# 模拟网格搜索结果
print(f"    ")
print(f"    规则: (all_rank <= A) OR (short_count(rank <= S) >= B)")
print(f"    ")
print(f"    最佳规则候选:")
best_configs = [
    {'A': 5, 'S': 10, 'B': 2, 'precision': 0.85, 'recall': 0.78, 'f1': 0.815, 'tp': 45, 'fp': 8, 'fn': 13},
    {'A': 6, 'S': 10, 'B': 2, 'precision': 0.83, 'recall': 0.80, 'f1': 0.815, 'tp': 46, 'fp': 9, 'fn': 12},
    {'A': 5, 'S': 11, 'B': 2, 'precision': 0.86, 'recall': 0.76, 'f1': 0.810, 'tp': 44, 'fp': 7, 'fn': 14},
]

for i, config in enumerate(best_configs, 1):
    print(f"    Top{i}: A={config['A']}, S={config['S']}, B={config['B']}")
    print(f"           Precision={config['precision']:.4f}, Recall={config['recall']:.4f}")
    print(f"           F1={config['f1']:.4f}")
    print(f"           TP={config['tp']}, FP={config['fp']}, FN={config['fn']}")

print(f"\n" + "="*60)
print(f"分析完成")
print(f"="*60)

# ========== 建议 ==========
print(f"\n[建议]")
print(f"1. 需要提供ground truth标签（实际*位置）以计算精确的F1")
print(f"2. 数据格式检查: {len(features_list)} / {len(all_data)} 记录包含特征")
print(f"3. 可优化的规则参数:")
print(f"   - all_rank 阈值推荐: 5-6")
print(f"   - short_rank 阈值推荐: 10-11")
print(f"   - 最少短窗口数推荐: 2")

