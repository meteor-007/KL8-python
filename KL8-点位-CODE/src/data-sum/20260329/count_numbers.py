#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统计两个数据文件中号码出现次数
"""
import re
from collections import Counter

def extract_numbers_from_file(filepath):
    """从文件中提取所有号码"""
    numbers = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # 提取所有数字（保持两位数格式）
            found = re.findall(r'\b(\d{2})\b', content)
            numbers.extend([int(n) for n in found])
    except FileNotFoundError:
        print(f"文件不存在：{filepath}")
    return numbers

def main():
    # 读取两个文件（使用绝对路径）
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data1_path = os.path.join(base_dir, '20260328-data1.txt')
    data2_path = os.path.join(base_dir, '20260328-data2.txt')
    
    data1_numbers = extract_numbers_from_file(data1_path)
    data2_numbers = extract_numbers_from_file(data2_path)
    
    # 合并所有号码
    all_numbers = data1_numbers + data2_numbers
    
    # 统计出现次数
    counter = Counter(all_numbers)
    
    # 按出现次数排序（从高到低）
    sorted_stats = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    
    print("=" * 60)
    print("20260328 期数据文件号码出现次数统计（从高到低）")
    print("=" * 60)
    print(f"data1.txt 号码总数：{len(data1_numbers)}")
    print(f"data2.txt 号码总数：{len(data2_numbers)}")
    print(f"合计号码总数：{len(all_numbers)}")
    print("=" * 60)
    print(f"{'号码':<8} {'出现次数':<10} {'频率':<10}")
    print("-" * 60)
    
    for number, count in sorted_stats:
        frequency = (count / len(all_numbers)) * 100
        print(f"{number:02d}        {count:<10} {frequency:>5.2f}%")
    
    print("=" * 60)
    print(f"不同号码数量：{len(counter)}")
    print("=" * 60)
    
    # 输出前 10 个最热号码
    print("\n🔥 最热号码 TOP 10:")
    for i, (number, count) in enumerate(sorted_stats[:10], 1):
        print(f"  {i}. 号码 {number:02d} - 出现 {count} 次")

if __name__ == '__main__':
    main()
