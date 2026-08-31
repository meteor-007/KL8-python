#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KL8 数据源集成处理系统 v2.0
============================
与v4.1热码统计集成，统一处理数据源1和2

核心功能：
1. 加载并清理数据源1/2的号码推荐
2. 使用v4.1热码统计进行交叉验证
3. 生成融合后的最终号码推荐
4. 计算号码的综合评分与命中概率

Author: 数据分析专家
Date: 2026-05-14
Version: 2.0
"""

import os
import sys
import json
import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import Counter
from dataclasses import dataclass, asdict

# ── 项目路径 ──
import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
DATA_FILE = os.path.join(_PROJ, '跟随+点位+开奖数据.xlsx')
HISTORY_FILE = os.path.join(_PROJ, 'kl8_history_final.txt')
OUTPUT_DIR = os.path.join(_PROJ, 'reports')

sys.path.insert(0, _PROJ)

NUM_TOTAL = 80


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════

@dataclass
class NumberRecommendation:
    """号码推荐对象"""
    number: int
    source1_score: float = 0.0         # 数据源1的评分
    source2_score: float = 0.0         # 数据源2的评分
    hotcode_v41: bool = False          # 是否在v4.1热码中
    combined_score: float = 0.0        # 综合评分
    rank: int = 0                      # 综合排名
    
    def to_dict(self):
        return {
            'number': self.number,
            'source1_score': round(self.source1_score, 4),
            'source2_score': round(self.source2_score, 4),
            'hotcode_v41': self.hotcode_v41,
            'combined_score': round(self.combined_score, 4),
            'rank': self.rank
        }


@dataclass
class DataSourceAnalysis:
    """数据源分析结果"""
    period: str
    date: str
    source1_numbers: List[int]
    source2_numbers: List[int]
    hotcode_v41_numbers: List[int]
    combined_recommendations: List[NumberRecommendation]
    top5_numbers: List[int]
    top12_numbers: List[int]


# ═══════════════════════════════════════════════════════════════
# 数据加载
# ═══════════════════════════════════════════════════════════════

def load_hotcode_v41() -> Set[int]:
    """
    加载v4.1热码统计
    """
    try:
        from data_acquisition.generate_hot_excel import (
            load_history, build_hot_windows, build_focus_hot_pool
        )
        history = load_history()
        hot_windows = build_hot_windows(history)
        hot_numbers = build_focus_hot_pool(hot_windows)
        return set(hot_numbers)
    except Exception as e:
        print(f"[警告] 加载热码v4.1失败: {e}")
        return set()


def load_datasource_from_excel(period: str) -> Tuple[List[int], List[int]]:
    """
    从Excel加载数据源1和2的号码推荐
    
    Args:
        period: 期号（格式：2026120）
    
    Returns:
        (source1_numbers, source2_numbers)
    """
    if not os.path.exists(DATA_FILE):
        print(f"[错误] 找不到数据文件: {DATA_FILE}")
        return [], []
    
    try:
        # 读取跟随号码统计表
        df = pd.read_excel(DATA_FILE, sheet_name='跟随号码统计', header=None)
        header_row = 0

        # 同一期号可能对应"数据1"/"数据2"两个列, 按表头中的"数据1"/"数据2"区分
        col_idx1 = -1
        col_idx2 = -1
        for col in range(df.shape[1]):
            cell_value = str(df.iloc[header_row, col])
            if period not in cell_value:
                continue
            if '数据2' in cell_value:
                col_idx2 = col
            elif '数据1' in cell_value and col_idx1 < 0:
                col_idx1 = col

        if col_idx1 < 0 and col_idx2 < 0:
            print(f"[警告] 找不到期号 {period} 的数据")
            return [], []

        def _extract(col_idx: int) -> List[int]:
            nums = []
            for row in range(1, df.shape[0]):
                cell_value = str(df.iloc[row, col_idx]).strip()
                if cell_value and cell_value != 'nan' and '*' in cell_value:
                    num_str = cell_value.replace('*', '').strip()
                    if num_str:
                        try:
                            nums.append(int(num_str))
                        except:
                            pass
            return nums

        numbers = _extract(col_idx1) if col_idx1 >= 0 else []
        source2 = _extract(col_idx2) if col_idx2 >= 0 else []
        return numbers, source2
    
    except Exception as e:
        print(f"[错误] 加载Excel数据失败: {e}")
        return [], []


def load_hot_numbers_from_excel(period: str) -> List[int]:
    """
    从热码统计文件加载v4.1热码
    """
    try:
        import openpyxl
        from openpyxl.utils import get_column_letter
        
        hot_dir = os.path.join(_PROJ, '热码统计')
        
        # 查找最新的热码统计文件
        import glob
        hot_files = glob.glob(os.path.join(hot_dir, '*热码统计.xlsx'))
        
        if not hot_files:
            print(f"[警告] 找不到热码统计文件")
            return []
        
        # 使用最新的文件
        latest_file = max(hot_files, key=os.path.getctime)
        
        # 加载并提取星标号码
        df = pd.read_excel(latest_file, sheet_name='Sheet1')
        
        # 第一列是全量窗口的号码
        col1 = df.iloc[1:, 0].astype(str).str.strip()
        stars = [int(n.replace('*', '')) for n in col1 
                if '*' in str(n) and str(n) != 'nan']
        
        return stars
    
    except Exception as e:
        print(f"[警告] 加载热码Excel失败: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# 号码推荐融合与评分
# ═══════════════════════════════════════════════════════════════

def calculate_combined_score(source1_z: float, source2_z: float, 
                            is_hotcode: bool, weights: Dict = None) -> float:
    """
    计算综合评分 (使用 Z-score 标准化对齐)
    
    Args:
        source1_z: 数据源1评分 (Z-score)
        source2_z: 数据源2评分 (Z-score)
        is_hotcode: 是否在v4.1热码中
        weights: 权重配置
    
    Returns:
        综合评分 (0-1)
    """
    if weights is None:
        weights = {
            'source1': 0.30,
            'source2': 0.30,
            'hotcode': 0.40
        }
    
    # 极高阶前瞻算法完整性: 使用Z-score而不是简单的 / 100
    # 我们将 Z-score 映射到 Sigmoid 区间 [0, 1]
    import math
    s1 = 1.0 / (1.0 + math.exp(-source1_z)) if source1_z != 0 else 0.5
    s2 = 1.0 / (1.0 + math.exp(-source2_z)) if source2_z != 0 else 0.5
    sh = 1.0 if is_hotcode else 0.0
    
    combined = (s1 * weights['source1'] + 
                s2 * weights['source2'] + 
                sh * weights['hotcode'])
    
    return combined


def merge_datasources(source1_nums: List[int], source2_nums: List[int], 
                     hotcode_nums: Set[int]) -> List[NumberRecommendation]:
    """
    融合两个数据源和热码
    
    Args:
        source1_nums: 数据源1的号码（带评分信息）
        source2_nums: 数据源2的号码（带评分信息）
        hotcode_nums: v4.1热码
    
    Returns:
        融合后的推荐列表
    """
    all_numbers = set(source1_nums) | set(source2_nums) | hotcode_nums
    
    # 极高阶前瞻算法完整性: Z-score 标准化对齐
    import numpy as np
    
    # 提取原始分并计算 Z-score
    raw_s1 = {}
    for num in source1_nums:
        rank_pos = source1_nums.index(num) + 1
        raw_s1[num] = max(0, 100 - rank_pos * 5)
    s1_vals = list(raw_s1.values())
    s1_mean = np.mean(s1_vals) if s1_vals else 0
    s1_std = np.std(s1_vals) if s1_vals and np.std(s1_vals) > 0 else 1
    
    raw_s2 = {}
    for num in source2_nums:
        rank_pos = source2_nums.index(num) + 1
        raw_s2[num] = max(0, 100 - rank_pos * 5)
    s2_vals = list(raw_s2.values())
    s2_mean = np.mean(s2_vals) if s2_vals else 0
    s2_std = np.std(s2_vals) if s2_vals and np.std(s2_vals) > 0 else 1

    recommendations = []
    
    for num in sorted(all_numbers):
        # 使用 Z-score
        source1_score = raw_s1.get(num, 0)
        source1_z = (source1_score - s1_mean) / s1_std if source1_score > 0 else -1.0
        
        source2_score = raw_s2.get(num, 0)
        source2_z = (source2_score - s2_mean) / s2_std if source2_score > 0 else -1.0
        
        is_hotcode = num in hotcode_nums
        
        # 计算综合评分
        combined_score = calculate_combined_score(
            source1_z, source2_z, is_hotcode
        )
        
        rec = NumberRecommendation(
            number=num,
            source1_score=source1_score,
            source2_score=source2_score,
            hotcode_v41=is_hotcode,
            combined_score=combined_score
        )
        recommendations.append(rec)
    
    # 按综合评分排序
    recommendations.sort(key=lambda x: (-x.combined_score, x.number))
    
    # 设置排名
    for i, rec in enumerate(recommendations, 1):
        rec.rank = i
    
    return recommendations


# ═══════════════════════════════════════════════════════════════
# 主分析流程
# ═══════════════════════════════════════════════════════════════

def analyze_datasources_integrated(period: str, date: str) -> DataSourceAnalysis:
    """
    完整的数据源集成分析流程
    
    Args:
        period: 期号
        date: 日期
    
    Returns:
        分析结果
    """
    # 1. 加载数据
    source1_nums, source2_nums = load_datasource_from_excel(period)
    hotcode_nums = set(load_hot_numbers_from_excel(period))
    
    if not hotcode_nums:
        # 备用方案：使用v4.1逻辑生成热码
        hotcode_nums = load_hotcode_v41()
    
    print(f"\n【{period}期 - {date}】")
    print(f"  数据源1: {len(source1_nums)}个号码")
    print(f"  数据源2: {len(source2_nums)}个号码")
    print(f"  v4.1热码: {len(hotcode_nums)}个号码")
    
    # 2. 融合推荐
    recommendations = merge_datasources(source1_nums, source2_nums, hotcode_nums)
    
    # 3. 提取Top-N
    top5 = [rec.number for rec in recommendations[:5]]
    top12 = [rec.number for rec in recommendations[:12]]
    
    return DataSourceAnalysis(
        period=period,
        date=date,
        source1_numbers=source1_nums,
        source2_numbers=source2_nums,
        hotcode_v41_numbers=sorted(hotcode_nums),
        combined_recommendations=recommendations,
        top5_numbers=top5,
        top12_numbers=top12
    )


# ═══════════════════════════════════════════════════════════════
# 报告生成
# ═══════════════════════════════════════════════════════════════

def generate_datasource_integration_report(analysis: DataSourceAnalysis) -> str:
    """生成数据源集成分析报告"""
    
    report = f"""
╔════════════════════════════════════════════════════════════════╗
║              数据源v2.0集成分析报告（v4.1热码）               ║
╚════════════════════════════════════════════════════════════════╝

【期号信息】
  期号: {analysis.period}
  日期: {analysis.date}

【数据源构成】
  数据源1: {len(analysis.source1_numbers)}个号码 - {analysis.source1_numbers}
  数据源2: {len(analysis.source2_numbers)}个号码 - {analysis.source2_numbers}
  v4.1热码: {len(analysis.hotcode_v41_numbers)}个号码

【融合推荐】
  总推荐数: {len(analysis.combined_recommendations)}个号码
  Top 5: {analysis.top5_numbers}
  Top 12: {analysis.top12_numbers}

【详细排名】
"""
    
    for i, rec in enumerate(analysis.combined_recommendations[:20], 1):
        hotcode_flag = "⭐" if rec.hotcode_v41 else "  "
        report += f"  {i:2d}. {rec.number:2d} {hotcode_flag} "
        report += f"综合:{rec.combined_score:.3f} "
        report += f"源1:{rec.source1_score:.1f} 源2:{rec.source2_score:.1f}\n"
    
    report += f"\n【融合策略】\n"
    report += f"  权重配置: 源1=30% 源2=30% v4.1热码=40%\n"
    report += f"  v4.1热码占比: {len([r for r in analysis.combined_recommendations[:12] if r.hotcode_v41])}/12\n"
    report += f"\n{'='*64}\n"
    
    return report


# ═══════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════

def main():
    print("\n" + "="*70)
    print("  KL8 数据源集成处理系统 v2.0 (with v4.1热码)")
    print("="*70)
    
    # 分析最近的5期
    try:
        from data_acquisition.generate_hot_excel import load_history
        history = load_history()
        
        for record in history[:5]:
            period = record['period']
            date = record['date']
            
            try:
                analysis = analyze_datasources_integrated(period, date)
                print(generate_datasource_integration_report(analysis))
            except Exception as e:
                print(f"[错误] 分析 {period} 失败: {e}")
    
    except Exception as e:
        print(f"[错误] 执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
