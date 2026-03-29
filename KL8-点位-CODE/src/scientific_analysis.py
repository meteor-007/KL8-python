import os
import math
import re
import numpy as np
from collections import defaultdict

BASE_DIR = r"D:\Dpanqianyi\Python-Project\KL8-点位-CODE\src"
DATA_FILE = os.path.join(BASE_DIR, "data", "daily_points.txt")
SUM_DIR = os.path.join(BASE_DIR, "data-sum")

# ==============================================================================
# 第一步：严格按照规格处理数据并按要求展示 (数据矩阵分布)
# ==============================================================================

def parse_group_line(line_str):
    """
    智能矩阵解析器：将单行数据解析为两个固定位置的矩阵行 (每行最大 4 列)
    保留空位的占位以确保矩阵的位置不发生变动，不够号码的补充空位。
    支持手动调整数据防止错位：
    1. 使用 " | " 或者双空格 "  " 隔开第一矩阵和第二矩阵的数据以明确保边界。
    2. 使用 "-" 或 "." 占位符。
    """
    if "→" in line_str:
        line_str = line_str.split("→", 1)[1].strip()
    else:
        line_str = line_str.strip()

    # 1. 明确的竖线分隔符
    if "|" in line_str:
        parts = line_str.split("|", 1)
        m1 = parts[0].split()
        m2 = parts[1].split()
    # 2. 视觉极客写法：使用两个及以上连续空格隔离
    elif re.search(r'\s{2,}', line_str):
        parts = re.split(r'\s{2,}', line_str, maxsplit=1)
        m1 = parts[0].split()
        m2 = parts[1].split()
    # 3. 默认无标识处理法：前4个切给矩阵一，剩下的给矩阵二
    else:
        tokens = line_str.split()
        m1 = tokens[:4]
        m2 = tokens[4:8]
        
    # 清理非数字的常见标点符号将其视为空字符串
    m1 = [x if x not in {".", "-", "_"} else "" for x in m1]
    m2 = [x if x not in {".", "-", "_"} else "" for x in m2]

    # 不足4个号码的用此空字符串补齐，保证数据矩阵形状严格锁定为 4x4 （每排4个槽位不变）
    m1 = m1[:4] + [""] * (4 - len(m1))
    m2 = m2[:4] + [""] * (4 - len(m2))
    
    return m1, m2

def demo_parsing():
    """
    全真模拟你的示例需求一与二，确保满足“第一个矩阵就是... 第二个矩阵就是...”打印特征
    """
    print("\n---------------- 用户示例一模拟测试 ----------------")
    data1 = [
        "19→25 55 43 41 62 48 21 20",
        "20→16 43 75 04 51 65 69 13",
        "21→14 75 03 04 43 60 03 65",
        "22→04 75 14 63 18 19 20 22"
    ]
    m1_list, m2_list = [], []
    for line in data1:
        m1, m2 = parse_group_line(line)
        m1_list.append(m1)
        m2_list.append(m2)
    
    print("那么第一个矩阵就是：")
    for row in m1_list:
        print(" ".join(f"{x:>2}" if x else "  " for x in row).rstrip())
    print("第二个矩阵就是")
    for row in m2_list:
        print(" ".join(f"{x:>2}" if x else "  " for x in row).rstrip())

    print("\n---------------- 用户示例二模拟测试 ----------------")
    print("场景描述：为防止少数据读错位，采用双空格排版或占位符方式将 17与51 切开")
    data2 = [
        "16→51 13 76 69 38 47 17 03",
        "17→79 80 17  51 74"  # 注意这里：17 与 51 之间使用了两个空格
    ]
    m1_list2, m2_list2 = [], []
    for line in data2:
        m1, m2 = parse_group_line(line)
        m1_list2.append(m1)
        m2_list2.append(m2)
        
    print("那么第一个矩阵就是：")
    for row in m1_list2:
        print(" ".join(f"{x:>2}" if x else "  " for x in row).rstrip())
    print("\n那么第二个矩阵就是：")
    for row in m2_list2:
        print(" ".join(f"{x:>2}" if x else "  " for x in row).rstrip())
    print("-" * 52)


# ==============================================================================
# 第二步：在新的严格 4x4 数据矩阵分布情况下，衔接下盘的所有原定预测运算系统
# ==============================================================================

def load_matrix_file(file_path):
    """
    加载数据文件，将其按 4x4 区块组织解析为 `blocks_m1` (左侧第一矩阵集群) 和 `blocks_m2` (右侧第二矩阵集群)。
    根据用户的设定："我将原来的data数据文件一分为2，实际是两套数据" -> 现在这个函数用于加载独立的单套数据。
    """
    blocks_m1 = []
    blocks_m2 = []
    if not os.path.exists(file_path):
        return blocks_m1, blocks_m2
        
    curr_m1, curr_m2 = [], []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): 
                # 解析遇到空行，代表一个区块结束，存入后重开一个块
                if curr_m1 or curr_m2:
                    blocks_m1.append(curr_m1)
                    blocks_m2.append(curr_m2)
                    curr_m1, curr_m2 = [], []
                continue
                
            # 执行带有矩阵隔离逻辑的解析器
            r1, r2 = parse_group_line(line)
            curr_m1.append(r1)
            curr_m2.append(r2)
            
            # 每个方阵强制约束最大 4 排
            if len(curr_m1) == 4:
                blocks_m1.append(curr_m1)
                blocks_m2.append(curr_m2)
                curr_m1, curr_m2 = [], []
                
    if curr_m1 or curr_m2:
        blocks_m1.append(curr_m1)
        blocks_m2.append(curr_m2)
    return blocks_m1, blocks_m2

def load_daily_sensors_separated(date_str):
    """提取矩阵中的所有真实验证数字，按 data1 和 data2 两套数据集严格独立返回"""
    dir_name = "".join(date_str.split("-"))
    file1 = os.path.join(SUM_DIR, dir_name, f"{dir_name}-data1.txt")
    file2 = os.path.join(SUM_DIR, dir_name, f"{dir_name}-data2.txt")
    
    def extract_from(f):
        # 我们直接保留矩阵的原始空间区块形态，不再扁平化
        b1, b2 = load_matrix_file(f)
        return b1 + b2 # 返回所有 4x4 区块集合

    return extract_from(file1), extract_from(file2)

def load_all_matrix_history(target_suffix):
    """提取过去所有日期该数据套系（如 data1.txt）完整的时序号码记录"""
    history = []
    if not os.path.exists(SUM_DIR):
        return history
    
    date_dirs = sorted([d for d in os.listdir(SUM_DIR) if os.path.isdir(os.path.join(SUM_DIR, d)) and d.isdigit()])
    for date_str in date_dirs:
        f_path = os.path.join(SUM_DIR, date_str, f"{date_str}-{target_suffix}.txt")
        b1, b2 = load_matrix_file(f_path)
        nums = []
        for block in b1 + b2:
            for row in block:
                nums.extend([int(x) for x in row if x and x.isdigit()])
        if nums:
            # 格式化日期形式
            fmt_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            history.append({"date": fmt_date, "nums": nums})
    
    return history

def analyze_entropy(history, label, window=5):
    print(f"\n[维一/热力学] {label} - 香农熵(发散度)演化:")
    if len(history) < window: 
        print(f"  > 历史窗口不足 {window} 期，跳过")
        return
    recent = history[-window:]
    freq = defaultdict(int)
    total_elements = 0
    for r in recent:
        for num in r["nums"]: 
            freq[num] += 1
            total_elements += 1
    if total_elements == 0: return
    entropy = sum(- (c/total_elements) * math.log2(c/total_elements) for c in freq.values())
    print(f"  > 近期 {window} 维度总香农熵: {entropy:.4f} (反应所排矩阵位置号码的分散混乱度)")

def analyze_mutual_information(history, label):
    print(f"\n[维二/量子拓扑] {label} - 空间矩阵内粒子强纠缠锁定对:")
    if not history: return
    co_mat = np.zeros((81, 81))
    freq = np.zeros(81)
    for record in history:
        for n in record["nums"]:
            if n <= 0 or n > 80: continue  # 容错：跳过因手误输入的超界无效号码
            freq[n] += 1
            for o in record["nums"]:
                if o <= 0 or o > 80: continue
                if n != o: co_mat[n][o] += 1
    entanglements = []
    for i in range(1, 81):
        for j in range(i+1, 81):
            if co_mat[i][j] >= 3:
                p_i, p_j, p_ij = freq[i]/len(history), freq[j]/len(history), co_mat[i][j]/len(history)
                lift = p_ij / (p_i * p_j) if p_i*p_j>0 else 0
                if lift > 1.5: entanglements.append((i, j, co_mat[i][j], lift))
    
    sorted_ent = sorted(entanglements, key=lambda x: x[3], reverse=True)[:3]
    if not sorted_ent:
        print("  > 矩阵内无极端频繁出没纠缠对。")
        return
    for i, j, m, l in sorted_ent:
        print(f"  > 粒子集对({i:02d}, {j:02d}) 同频出现在您的排版下达 {int(m)} 次 | 物理关联提升度:{l:.2f}")

def load_daily_points():
    """读取历史的官方开出数据（原基础数据）"""
    history = []
    if not os.path.exists(DATA_FILE): return history
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "points:" in line:
                date_str = line.split("points:")[0].replace("date:", "").replace(",", "").strip()
                nums = [int(n) for n in line.split("points:")[1].split()]
                history.append({"date": date_str, "nums": nums})
    history.sort(key=lambda x: x["date"])
    return history

def sensor_fusion_analysis(date_str, actual_nums):
    print(f"\n[功能还原分析 3]：基于新矩阵数据源的系统击中正确率核验")
    s1, s2 = load_daily_sensors_separated(date_str)
    actual_set = set(actual_nums)
    
    def evaluate(blocks, label):
        print(f"\n  >>> 【独立分析：{label}】 <<<")
        if not blocks:
            print("    [空] 该数据源未加载或无有效矩阵元。")
            return
            
        for b_idx, block in enumerate(blocks):
            total_elements = 0
            hits_info = []
            
            for r_idx, row in enumerate(block):
                for c_idx, val in enumerate(row):
                    if val and val.isdigit():
                        total_elements += 1
                        if int(val) in actual_set:
                            # 记录精准的击中位置
                            hits_info.append(f"[{val}]@排{r_idx+1}-列{c_idx+1}")
                            
            if total_elements > 0:
                sens = len(hits_info) / total_elements
                if sens > 0:
                    print(f"    阵列块 {b_idx+1} [命中率: {sens*100:.1f}%] -> 矩阵点位分布: {', '.join(hits_info)}")

    evaluate(s1, "数据集一 (data1.txt)")
    evaluate(s2, "数据集二 (data2.txt)")

def compare_blocks(blocksA, blocksB, matrix_name):
    # 此处逻辑严格对齐：绝对的空间位置判断！
    hits = defaultdict(list)
    for b_idx in range(min(len(blocksA), len(blocksB))):
        for r_idx in range(min(len(blocksA[b_idx]), len(blocksB[b_idx]))):
            rowA = blocksA[b_idx][r_idx]
            rowB = blocksB[b_idx][r_idx]
            
            for c_idx in range(min(len(rowA), len(rowB))):
                if rowA[c_idx] and rowB[c_idx] and rowA[c_idx] == rowB[c_idx]:
                     hits[rowA[c_idx]].append(f"区{b_idx+1}-排{r_idx+1}-列{c_idx+1}")
                     
    if hits:
        print(f"\n  ({matrix_name}) 发现坐标系绝对共振点:")
        for num, pos in sorted(hits.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"    ★ 阵列重叠数: {num} 👉 重叠坐标为: {', '.join(pos)}")
    else:
        print(f"\n  ({matrix_name}) 无同位坐标重叠")

def positional_overlap(date1, date2):
    print(f"\n[功能还原分析 4]：基于 {date1} 与 {date2} 各套双数据源的时空叠加坐标验证")
    d1 = "".join(date1.split("-"))
    d2 = "".join(date2.split("-"))
    
    for suffix in ["data1.txt", "data2.txt"]:
        f1 = os.path.join(SUM_DIR, d1, f"{d1}-{suffix}")
        f2 = os.path.join(SUM_DIR, d2, f"{d2}-{suffix}")
        if not os.path.exists(f1) or not os.path.exists(f2): 
            continue
            
        b1_m1, b1_m2 = load_matrix_file(f1)
        b2_m1, b2_m2 = load_matrix_file(f2)
        print(f"\n >>> 【贯穿对比数据集: {suffix}】 <<<")
        compare_blocks(b1_m1, b2_m1, "从第一矩阵内扫描")
        compare_blocks(b1_m2, b2_m2, "从第二矩阵内扫描")

if __name__ == "__main__":
    demo_parsing()
    
    print("\n========================================================")
    print(" >>> 科学分析维度全线迁移至【独立各套矩阵体系】执行 <<< ")
    print("========================================================")
    
    # 获取矩阵体系独立的时空历史数据
    data1_historical = load_all_matrix_history("data1")
    data2_historical = load_all_matrix_history("data2")
    
    print("\n============ 【数据集一 (data1) 核心矩阵属性透视】 ============")
    if data1_historical:
        analyze_entropy(data1_historical, "data1内源")
        analyze_mutual_information(data1_historical, "data1内源")
    
    print("\n============ 【数据集二 (data2) 核心矩阵属性透视】 ============")
    if data2_historical:
        analyze_entropy(data2_historical, "data2内源")
        analyze_mutual_information(data2_historical, "data2内源")
    
    print("\n============ 【命中实测对比情况】 ============")
    history = load_daily_points()
    if history:
         # 智能对齐：寻找本地 data-sum 中存在的、最新的、且已开奖的数据进行比对
         valid_date = None
         valid_nums = None
         available_dirs = set(d for d in os.listdir(SUM_DIR) if os.path.isdir(os.path.join(SUM_DIR, d)) and d.isdigit())
         for h in reversed(history):
             str_date = h["date"].replace("-", "")
             if str_date in available_dirs:
                 valid_date = h["date"]
                 valid_nums = h["nums"]
                 break
                 
         if valid_date:
             print(f"  [系统感知] 自动匹配到最新已有预测矩阵并且已开奖的日期：{valid_date}")
             sensor_fusion_analysis(valid_date, valid_nums)
         else:
             print("  [提示] 找不到同时存在预测矩阵和官方出奖的同期数据进行核验。")
    
    print("\n============ 【时空拓扑：位置物理学比对】 ============")
    # 自动选取目前库里最后两天（即最新的两天）的矩阵进行物理座标叠加
    date_dirs = sorted([d for d in os.listdir(SUM_DIR) if os.path.isdir(os.path.join(SUM_DIR, d)) and d.isdigit()])
    if len(date_dirs) >= 2:
        d1, d2 = date_dirs[-2], date_dirs[-1]
        fmt_d1 = f"{d1[:4]}-{d1[4:6]}-{d1[6:8]}"
        fmt_d2 = f"{d2[:4]}-{d2[4:6]}-{d2[6:8]}"
        positional_overlap(fmt_d1, fmt_d2)
    else:
        print("  [提示] 矩阵库内存量不足两天，无法完成基于时空的跨日重叠比对。")
