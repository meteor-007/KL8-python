import os
import sys
from collections import defaultdict

def parse_file(filepath):
    """解析带有 '行号→号码' 格式的文件，返回 {line_num: set(numbers)} 字典"""
    data = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if '→' in line:
                parts = line.split('→')
                line_idx = int(parts[0].strip())
                nums_str = parts[1].strip()
                if nums_str:
                    nums = set(nums_str.split())
                    data[line_idx] = nums
                else:
                    data[line_idx] = set()
    return data

def compare_data(file_old, file_new):
    """对比新旧文件，输出每一行的变化及终极总结"""
    print(f"📊 {os.path.basename(file_old)} vs {os.path.basename(file_new)} 综合对比报告\n")
    print("="*50)
    
    old_data = parse_file(file_old)
    new_data = parse_file(file_new)
    
    vanished_counts = defaultdict(int)
    erupted_counts = defaultdict(int)
    
    max_line = max(max(old_data.keys(), default=0), max(new_data.keys(), default=0))
    
    print("📋 [逐行对比详细结果]")
    for i in range(1, max_line + 1):
        old_nums = old_data.get(i, set())
        new_nums = new_data.get(i, set())
        
        # 都不存在内容时忽略
        if not old_nums and not new_nums:
            continue
            
        vanished = old_nums - new_nums
        erupted = new_nums - old_nums
        
        # 记录频次
        for n in vanished: vanished_counts[n] += 1
        for n in erupted: erupted_counts[n] += 1
        
        if vanished or erupted:
            print(f"--- 第 {i} 行 ---")
            print(f"  旧数据: {' '.join(sorted(old_nums))} ")
            print(f"  新数据: {' '.join(sorted(new_nums))} ")
            if vanished: print(f"  ❌ 消失的号码: {' '.join(sorted(vanished))}")
            if erupted: print(f"  ✅ 新晋的号码: {' '.join(sorted(erupted))}")
    
    print("\n" + "="*50)
    print("🎯 [宏观动能与热点统计]")
    
    print("\n🔻 [高频消失断崖号] (上一期有，本期突然消失 且出现频率>=2)")
    sorted_vanished = sorted(vanished_counts.items(), key=lambda x: x[1], reverse=True)
    for num, count in sorted_vanished:
        if count >= 2:
            print(f"  - 号码 {num} : 消失了 {count} 次")
            
    print("\n🔺 [新晋爆发动能号] (本期突然出现，上一期没有 且出现频率>=2)")
    sorted_erupted = sorted(erupted_counts.items(), key=lambda x: x[1], reverse=True)
    for num, count in sorted_erupted:
        if count >= 2:
            print(f"  - 号码 {num} : 新增了 {count} 次")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        # Default test run if no args
        base_dir = r"D:\Dpanqianyi\Python-Project\KL8-点位-CODE\src\data-sum"
        f1 = os.path.join(base_dir, "20260323", "20260323-data.txt")
        f2 = os.path.join(base_dir, "20260324", "20260324-data.txt")
        compare_data(f1, f2)
    else:
        compare_data(sys.argv[1], sys.argv[2])
