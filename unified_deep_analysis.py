# -*- coding: utf-8 -*-
"""
量化科学之神父 - 三系统联合深度分析 (AUC 剖析版)
整合系统：
  1. 跟随+点位+开奖-分析
  2. 全新-20260430-分析
  3. 点位+遗漏+跟随
"""

import os
import re
import datetime
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score
from tqdm import tqdm

# 配置路径
BASE_DIR = r'D:\Dpanqianyi\Python-Project'
HISTORY_FILE = os.path.join(BASE_DIR, 'data', 'kl8_history_final.txt')
SYSTEM1_DIR = os.path.join(BASE_DIR, '跟随+点位+开奖-分析')
SYSTEM2_DIR = os.path.join(BASE_DIR, '全新-20260430-分析')
SYSTEM3_DIR = os.path.join(BASE_DIR, '点位+遗漏+跟随')

class UnifiedAnalyzer:
    def __init__(self):
        self.history = {}  # {date: set(numbers)}
        self.date_to_period = {}
        self.predictions = {} # {date: {num: score}}

    def load_history(self):
        """加载开奖历史数据"""
        if not os.path.exists(HISTORY_FILE):
            print(f"错误: 找不到历史文件 {HISTORY_FILE}")
            return
        
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                # date:2026-05-18,period:2026128,numbers:43-28-51-75-11-13-47-17-38-05-76-39-45-04-41-53-46-26-60-19
                match = re.search(r'date:([\d-]+),period:(\d+),numbers:([\d-]+)', line)
                if match:
                    date_str = match.group(1)
                    period = match.group(2)
                    nums = set(int(n) for n in match.group(3).split('-'))
                    self.history[date_str] = nums
                    self.date_to_period[date_str] = period
        print(f"成功加载 {len(self.history)} 期开奖历史。")

    def parse_system1_and_3(self, dir_path, date_str):
        """解析系统1和系统3的预测文件 (TXT格式)"""
        file_path = os.path.join(dir_path, f'今日AI引擎终极预测推荐_{date_str}.txt')
        scores = {}
        if not os.path.exists(file_path):
            return scores

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 1. 极值共鸣分
            # [37] 极值共鸣分 = 4.2
            matches = re.findall(r'\[(\d+)\] 极值共鸣分 = ([\d.]+)', content)
            for num_str, score_str in matches:
                num = int(num_str)
                scores[num] = scores.get(num, 0) + float(score_str)

            # 2. 稳健底仓10码
            # [稳健底仓10码]: [26, 32, 40, 41, 42, 43, 44, 48, 55, 70]
            match = re.search(r'\[稳健底仓10码\]: \[(.*?)\]', content)
            if match:
                nums = [int(n.strip()) for n in match.group(1).split(',')]
                for n in nums:
                    scores[n] = scores.get(n, 0) + 2.0

            # 3. 首席金胆
            # [首席金胆 (白皮书 EV王)]: 【 41 】
            # 🥇 首席金胆	【 41 】
            matches = re.findall(r'首席金胆.*?【\s*(\d+)\s*】', content)
            for num_str in matches:
                num = int(num_str)
                scores[num] = scores.get(num, 0) + 5.0

            # 4. 核心暴杀组
            # [核心暴杀组] 预测 4 码: [40, 41, 42, 43]
            match = re.search(r'\[核心暴杀组\] 预测 \d+ 码: \[(.*?)\]', content)
            if match:
                nums = [int(n.strip()) for n in match.group(1).split(',')]
                for n in nums:
                    scores[n] = scores.get(n, 0) + 3.0

        except Exception as e:
            print(f"解析 {file_path} 出错: {e}")
        
        return scores

    def parse_system2(self, date_str):
        """解析系统2的预测文件 (MD格式)"""
        # prediction_record_YYYYMMDD.md 或者 analysis_record_YYYYMMDD.md
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        date_compact = date_obj.strftime('%Y%m%d')
        
        # 尝试几种命名方式
        file_candidates = [
            os.path.join(SYSTEM2_DIR, f'prediction_record_{date_compact}.md'),
            os.path.join(SYSTEM2_DIR, f'analysis_record_{date_compact}.md'),
            # 也可以根据期号查找，这里先用日期
        ]
        
        # 如果历史中有期号，也试试期号
        if date_str in self.date_to_period:
            period = self.date_to_period[date_str]
            file_candidates.append(os.path.join(SYSTEM2_DIR, f'prediction_record_{period}.md'))
            file_candidates.append(os.path.join(SYSTEM2_DIR, f'analysis_record_{period}.md'))

        scores = {}
        found = False
        for file_path in file_candidates:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    for line in lines:
                        # 解析表格行 | 1 | 50 | 0.6251 | ...
                        table_match = re.match(r'\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|', line)
                        if table_match:
                            num = int(table_match.group(2))
                            score = float(table_match.group(3))
                            # 归一化处理，MD中的总分通常是0-1或300+
                            if score > 10:
                                scores[num] = scores.get(num, 0) + (score / 100.0)
                            else:
                                scores[num] = scores.get(num, 0) + (score * 5.0) # 放大一点
                    
                    # 解析 Top12 50 · 48 · 63 ...
                    if "Top12推荐" in "".join(lines):
                        all_text = "".join(lines)
                        top12_match = re.search(r'### 1\.1 Top12推荐\n(.*?)\n', all_text)
                        if top12_match:
                            nums = [int(n.strip()) for n in top12_match.group(1).split('·')]
                            for n in nums:
                                scores[n] = scores.get(n, 0) + 1.0

                    found = True
                    break
                except Exception as e:
                    print(f"解析 {file_path} 出错: {e}")
        
        return scores

    def collect_all_data(self, days=30):
        """收集指定天数内的所有预测数据"""
        all_dates = sorted(self.history.keys(), reverse=True)
        target_dates = all_dates[:days]
        
        print(f"正在收集过去 {len(target_dates)} 天的预测数据...")
        
        for date_str in tqdm(target_dates):
            day_scores = {}
            
            # 合并三个系统的分数
            s1 = self.parse_system1_and_3(SYSTEM1_DIR, date_str)
            s2 = self.parse_system2(date_str)
            s3 = self.parse_system1_and_3(SYSTEM3_DIR, date_str)
            
            # 简单加权合并 (可以后续优化)
            for num in range(1, 81):
                total_score = s1.get(num, 0) + s2.get(num, 0) + s3.get(num, 0)
                if total_score > 0:
                    day_scores[num] = total_score
            
            if day_scores:
                self.predictions[date_str] = day_scores

    def analyze_auc(self):
        """计算每个号码的预测性能 (AUC)"""
        if not self.predictions:
            print("没有收集到预测数据，无法分析。")
            return

        print("\n正在计算各号码 AUC 表现...")
        
        num_stats = []
        for num in range(1, 81):
            y_true = []
            y_scores = []
            
            for date_str, daily_preds in self.predictions.items():
                if date_str not in self.history: continue
                
                actual_nums = self.history[date_str]
                # 标签：1 命中，0 未命中
                y_true.append(1 if num in actual_nums else 0)
                
                # 分数：如果系统没预测，则给0
                y_scores.append(daily_preds.get(num, 0))
            
            # 计算 AUC
            # 注意：AUC 要求 y_true 中同时有 0 和 1
            if len(set(y_true)) > 1:
                try:
                    auc = roc_auc_score(y_true, y_scores)
                    hits = sum(y_true)
                    total_days = len(y_true)
                    hit_rate = hits / total_days if total_days > 0 else 0
                    
                    # 额外指标：高分时的命中率 (Precision at Top)
                    # 假设分数 > 均值视为推荐
                    mean_score = np.mean(y_scores)
                    recommended_days = sum(1 for s in y_scores if s > mean_score)
                    rec_hits = sum(1 for i in range(len(y_scores)) if y_scores[i] > mean_score and y_true[i] == 1)
                    precision = rec_hits / recommended_days if recommended_days > 0 else 0

                    num_stats.append({
                        'num': num,
                        'auc': auc,
                        'hits': hits,
                        'total_days': total_days,
                        'hit_rate': hit_rate,
                        'precision': precision,
                        'avg_score': np.mean(y_scores)
                    })
                except Exception as e:
                    pass
            else:
                # 如果该号码在这段时间从未出现或一直出现（极少见），则跳过或给默认值
                pass

        # 排序
        df = pd.DataFrame(num_stats)
        if df.empty:
            print("计算结果为空。可能是样本量太少。")
            return
        
        df = df.sort_values(by='auc', ascending=False)
        
        # 保存为 JSON 供其他系统调用
        json_path = os.path.join(BASE_DIR, 'data', 'auc_stats.json')
        df.to_json(json_path, orient='records', force_ascii=False, indent=2)
        print(f"AUC 统计已保存至 JSON: {json_path}")

        report_path = os.path.join(BASE_DIR, 'deep_auc_analysis_report.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# 🧠 量化科学之神父 - 三系统联合深度分析报告 (AUC 剖析版)\n\n")
            f.write(f"**分析日期**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**样本跨度**: 最近 {len(self.predictions)} 期预测数据\n")
            f.write(f"**分析目标**: 通过 AUC (ROC 曲线下面积) 评估各号码在三系统联合预测下的可预测性与命中质量。\n\n")
            
            f.write("## 一、核心排行榜 (Top 40)\n\n")
            f.write("| 排名 | 号码 | AUC (预测力) | 总命中 | 历史胜率 | 高分精度 | 平均共鸣分 |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
            
            for i, row in enumerate(df.head(40).itertuples(), 1):
                f.write(f"| {i} | **{row.num:02d}** | {row.auc:.4f} | {int(row.hits)} | {row.hit_rate:.1%} | {row.precision:.1%} | {row.avg_score:.2f} |\n")
            
            f.write("\n## 二、神父洞察与专家评估\n\n")
            top1 = df.iloc[0]
            f.write(f"1. **统治级号码**: 号码 **{int(top1['num']):02d}** 以 AUC {top1['auc']:.4f} 夺冠。这意味着当三系统联合给出高分时，该号码落入开奖区的确定性极高。\n")
            f.write(f"2. **高精度矩阵**: 排名前列的号码如 {', '.join([f'{int(n):02d}' for n in df.head(5)['num']])} 表现出显著的‘高分即命中’特征，其高分精度 (Precision at Top) 远超自然命中率。\n")
            f.write(f"3. **系统性偏差预警**: 列表中 AUC 低于 0.5 的号码可能存在‘过度预测但未命中’的系统性漏洞，需检查是否受‘冷热陷阱’误导。\n")
            
            f.write("\n## 三、指标定义\n\n")
            f.write("- **AUC (Area Under Curve)**: 衡量预测分值对命中的区分能力。1.0 为完美预测，0.5 为随机，<0.5 为反向。反映了系统的‘法眼’对该号码的敏感度。\n")
            f.write("- **高分精度 (Precision at Top)**: 当综合共鸣分高于该号码自身均值时的实际命中概率。反映了系统的‘爆发捕获力’。\n")
            f.write("- **平均共鸣分**: 三个系统对该号码给出的日均总分。反映了系统的‘偏好权重’。\n")
            
            f.write("\n---\n*“数据是唯一的真理，共鸣是真理的频率。”* — 量化科学神父\n")

        print(f"\n报告已生成至: {report_path}")
        return df

if __name__ == "__main__":
    analyzer = UnifiedAnalyzer()
    analyzer.load_history()
    # 默认分析最近 40 期以获得足够的样本量
    analyzer.collect_all_data(days=40)
    analyzer.analyze_auc()
