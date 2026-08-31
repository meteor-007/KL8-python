#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 热码统计深度分析系统 v1.0
===================================
核心能力：
1. 热码持续性分析 — 号码在不同窗口中的热度延续能力
2. 热码转换矩阵 — 号码在"热/温/冷"状态间的马尔可夫转移概率
3. 热码预测力评估 — 星标热码对下期命中的回测验证
4. 热码衰退检测 — 从热到冷的衰退周期与临界点识别
5. 热码聚集效应 — 热码的空间聚集(段位)与共振模式
6. 冷码觉醒预测 — 冷码回温的早期信号检测
7. 滑动窗口动态分析 — 不同窗口长度的信息增益比较
8. 热码深度分析报告生成

Author: 资深研发与数据分析专家
Date: 2026-05-13
"""

import os
import sys
import json
import collections
import datetime
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict
import warnings
warnings.filterwarnings('ignore')

# ── 项目路径 ──
import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
HISTORY_FILE = os.path.join(_PROJ, 'kl8_history_final.txt')
HOT_DIR = os.path.join(_PROJ, '热码统计')
REPORT_DIR = os.path.join(_PROJ, 'reports')

NUM_TOTAL = 80
NUM_PICK = 20
WINDOWS = [("全量", None), ("50期", 50), ("25期", 25), ("10期", 10)]

# ── 热度分级阈值 ──
HOT_THRESHOLD_PCT = 75    # 前25%为热码
WARM_THRESHOLD_PCT = 50   # 25%-50%为温码
# 50%以后为冷码


# ═══════════════════════════════════════════════════════════════
# 数据加载层
# ═══════════════════════════════════════════════════════════════

def load_history() -> List[Dict[str, Any]]:
    """加载历史开奖数据（最新在前）"""
    data = []
    if not os.path.exists(HISTORY_FILE):
        print(f"[错误] 未找到历史文件: {HISTORY_FILE}")
        return data
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if 'numbers:' not in line:
                continue
            parts = line.split(',')
            data.append({
                'date': parts[0].split(':')[1],
                'period': parts[1].split(':')[1],
                'numbers': [int(n) for n in parts[2].split(':')[1].strip().split('-')]
            })
    return data


def rank_with_ties(values: Dict[int, int]) -> Dict[int, int]:
    """带并列排名的排序引擎"""
    ranked = sorted(values.items(), key=lambda item: (-item[1], item[0]))
    result = {}
    prev_value, prev_rank = None, 0
    for index, (number, value) in enumerate(ranked, start=1):
        if value == prev_value:
            result[number] = prev_rank
        else:
            result[number] = index
            prev_rank = index
            prev_value = value
    return result


def build_hot_windows(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """构建四个统计窗口的数据"""
    hist = records[::-1]  # 反转为旧在前
    result = {}
    for label, window in WINDOWS:
        subset = hist if window is None else hist[-window:]
        counts = collections.Counter(n for r in subset for n in r["numbers"])
        ranks = rank_with_ties({n: counts.get(n, 0) for n in range(1, 81)})
        window_size = len(subset)
        expected = max(window_size * 0.25, 1e-9)
        rows = []
        for number in range(1, 81):
            hits = counts.get(number, 0)
            rows.append({
                "number": number,
                "hits": hits,
                "rank": ranks[number],
                "ratio": round(hits / expected * 100, 1)
            })
        rows.sort(key=lambda item: (item["rank"], item["number"]))
        result[label] = rows
    return result


def build_focus_hot_pool(hot_windows: Dict[str, List[Dict[str, Any]]]) -> List[int]:
    """官方加权共振星标算法"""
    by_window = {
        label: {item["number"]: item for item in rows}
        for label, rows in hot_windows.items()
    }
    focus_raw = {}
    for number in range(1, 81):
        all_info = by_window["全量"][number]
        s50 = by_window["50期"][number]
        s25 = by_window["25期"][number]
        s10 = by_window["10期"][number]
        
        short_top5 = sum(1 for item in (s50, s25, s10) if item["rank"] <= 5)
        short_top10 = sum(1 for item in (s50, s25, s10) if item["rank"] <= 10)
        short_ratio_avg = (s50["ratio"] + s25["ratio"] + s10["ratio"]) / 3.0
        short_ratio_peak = max(s50["ratio"], s25["ratio"], s10["ratio"])
        all_bonus = max(0.0, 36.0 - all_info["rank"])
        
        focus_raw[number] = (
            short_top5 * 22.0
            + short_top10 * 8.0
            + short_ratio_avg * 0.36
            + short_ratio_peak * 0.20
            + all_bonus * 1.6
            + all_info["ratio"] * 0.14
        )
    
    focus_pool = sorted(range(1, 81), key=lambda n: (-focus_raw[n], n))[:36]
    return focus_pool


def classify_temperature(rank: int, total: int = 80) -> str:
    """根据排名分类热度：热/温/冷"""
    if rank <= total * 0.25:
        return "热"
    elif rank <= total * 0.50:
        return "温"
    else:
        return "冷"


# ═══════════════════════════════════════════════════════════════
# 分析引擎层
# ═══════════════════════════════════════════════════════════════

class HotNumberDeepAnalyzer:
    """热码深度分析引擎"""
    
    def __init__(self, history: List[Dict[str, Any]]):
        self.history = history  # 最新在前
        self.hist_chrono = history[::-1]  # 旧在前（时间正序）
        self.total_periods = len(history)
        
        # 预计算每期的热码统计（滑动窗口）
        self._precompute_sliding_stats()
    
    def _precompute_sliding_stats(self):
        """预计算滑动窗口统计数据"""
        print("[预计算] 构建滑动窗口统计矩阵...")
        
        # 为每个时间点计算4个窗口的统计
        self.sliding_stats = {}  # period -> {window_label -> {number -> {hits, rank, ratio}}}
        
        # 只计算最近200期（性能考虑）
        max_compute = min(self.total_periods, 200)
        
        for i in range(self.total_periods - max_compute, self.total_periods):
            period = self.hist_chrono[i]['period']
            # 从开头到第i期的数据
            subset = self.hist_chrono[:i+1]
            
            window_data = {}
            for label, window in WINDOWS:
                w_subset = subset if window is None else subset[-window:]
                counts = collections.Counter(n for r in w_subset for n in r["numbers"])
                ranks = rank_with_ties({n: counts.get(n, 0) for n in range(1, 81)})
                w_size = len(w_subset)
                expected = max(w_size * 0.25, 1e-9)
                
                num_map = {}
                for number in range(1, 81):
                    hits = counts.get(number, 0)
                    num_map[number] = {
                        "hits": hits,
                        "rank": ranks[number],
                        "ratio": round(hits / expected * 100, 1)
                    }
                window_data[label] = num_map
            
            self.sliding_stats[period] = window_data
        
        print(f"[完成] 已预计算 {len(self.sliding_stats)} 期滑动统计")
    
    # ── 分析1: 热码持续性分析 ──
    def analyze_persistence(self, recent_n: int = 30) -> Dict[str, Any]:
        """
        分析号码在连续期数中保持"热码"状态的能力
        持续性越强，说明该号码有稳定的出现规律
        """
        print("\n[分析1] 热码持续性分析...")
        
        periods_to_analyze = list(self.sliding_stats.keys())[-recent_n:]
        
        # 统计每个号码在"10期窗口"中连续保持Top20的次数
        persistence_data = {}
        for number in range(1, 81):
            consecutive_hot = 0
            max_consecutive = 0
            current_consecutive = 0
            hot_counts = 0
            
            for period in periods_to_analyze:
                if period not in self.sliding_stats:
                    continue
                rank_10 = self.sliding_stats[period]["10期"][number]["rank"]
                is_hot = rank_10 <= 20
                
                if is_hot:
                    hot_counts += 1
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                else:
                    current_consecutive = 0
            
            persistence_data[number] = {
                "hot_frequency": hot_counts,
                "hot_rate": round(hot_counts / len(periods_to_analyze) * 100, 1),
                "max_consecutive_hot": max_consecutive,
                "persistence_score": round(
                    hot_counts * 0.4 + max_consecutive * 3.0, 1
                )
            }
        
        # 按持续性评分排序
        sorted_persistence = sorted(
            persistence_data.items(),
            key=lambda x: (-x[1]["persistence_score"], x[0])
        )
        
        top_persistent = sorted_persistence[:15]
        bottom_persistent = sorted_persistence[-10:]
        
        return {
            "analysis_window": f"最近{recent_n}期",
            "top_persistent_numbers": [
                {"number": n, **d} for n, d in top_persistent
            ],
            "least_persistent_numbers": [
                {"number": n, **d} for n, d in bottom_persistent
            ],
            "persistence_distribution": {
                "high_persistence (>60%热)": sum(
                    1 for _, d in persistence_data.items() if d["hot_rate"] > 60
                ),
                "medium_persistence (30-60%)": sum(
                    1 for _, d in persistence_data.items() if 30 <= d["hot_rate"] <= 60
                ),
                "low_persistence (<30%)": sum(
                    1 for _, d in persistence_data.items() if d["hot_rate"] < 30
                ),
            },
            "all_data": persistence_data
        }
    
    # ── 分析2: 热码状态转移矩阵 ──
    def analyze_transition_matrix(self, recent_n: int = 100) -> Dict[str, Any]:
        """
        构建"热→热"、"热→温"、"热→冷"等状态转移概率矩阵
        使用马尔可夫链建模
        """
        print("[分析2] 热码状态转移矩阵构建...")
        
        states = ["热", "温", "冷"]
        transition_counts = {s1: {s2: 0 for s2 in states} for s1 in states}
        number_transitions = {n: {s1: {s2: 0 for s2 in states} for s1 in states} for n in range(1, 81)}
        
        periods_list = list(self.sliding_stats.keys())[-recent_n:]
        
        for i in range(len(periods_list) - 1):
            period = periods_list[i]
            next_period = periods_list[i + 1]
            
            for number in range(1, 81):
                current_state = classify_temperature(
                    self.sliding_stats[period]["10期"][number]["rank"]
                )
                next_state = classify_temperature(
                    self.sliding_stats[next_period]["10期"][number]["rank"]
                )
                
                transition_counts[current_state][next_state] += 1
                number_transitions[number][current_state][next_state] += 1
        
        # 转换为概率
        transition_probs = {}
        for s1 in states:
            total = sum(transition_counts[s1].values())
            transition_probs[s1] = {}
            for s2 in states:
                transition_probs[s1][s2] = round(
                    transition_counts[s1][s2] / total * 100, 1
                ) if total > 0 else 0
        
        # 找出具有异常转移模式的号码（如热→冷概率异常高的"衰退信号"号码）
        anomaly_numbers = []
        for number in range(1, 81):
            hot_total = sum(number_transitions[number]["热"].values())
            if hot_total >= 5:  # 至少5次热码状态才有统计意义
                hot_to_cold = number_transitions[number]["热"]["冷"] / hot_total
                hot_to_hot = number_transitions[number]["热"]["热"] / hot_total
                if hot_to_cold > 0.5:  # 热→冷概率超过50%，衰退信号
                    anomaly_numbers.append({
                        "number": number,
                        "hot_to_cold_rate": round(hot_to_cold * 100, 1),
                        "hot_to_hot_rate": round(hot_to_hot * 100, 1),
                        "signal": "衰退预警"
                    })
                elif hot_to_hot > 0.7:  # 热→热概率超过70%，强持续
                    anomaly_numbers.append({
                        "number": number,
                        "hot_to_cold_rate": round(hot_to_cold * 100, 1),
                        "hot_to_hot_rate": round(hot_to_hot * 100, 1),
                        "signal": "强持续热码"
                    })
        
        anomaly_numbers.sort(key=lambda x: -x["hot_to_hot_rate"])
        
        return {
            "analysis_window": f"最近{recent_n}期",
            "transition_matrix": transition_probs,
            "anomaly_numbers": anomaly_numbers[:20],
            "key_insight": (
                f"热码保持热度概率: {transition_probs['热']['热']}%, "
                f"热转温: {transition_probs['热']['温']}%, "
                f"热转冷: {transition_probs['热']['冷']}%"
            )
        }
    
    # ── 分析3: 热码预测力评估 ──
    def analyze_predictive_power(self, recent_n: int = 50) -> Dict[str, Any]:
        """
        回测评估：上一期的星标热码（Focus Pool 36码）在下一期中的命中表现
        对比基准：随机选取36码的期望命中率
        """
        print("[分析3] 热码预测力回测评估...")
        
        periods_list = list(self.sliding_stats.keys())[-recent_n:]
        
        results = []
        for i in range(len(periods_list) - 1):
            period = periods_list[i]
            next_period = periods_list[i + 1]
            
            # 构建当前期的Focus Pool
            current_windows = {}
            for label, _ in WINDOWS:
                current_windows[label] = self.sliding_stats[period][label]
            
            # 转换格式以适配build_focus_hot_pool
            formatted_windows = {}
            for label, num_map in current_windows.items():
                rows = [
                    {"number": n, **info}
                    for n, info in num_map.items()
                ]
                rows.sort(key=lambda item: (item["rank"], item["number"]))
                formatted_windows[label] = rows
            
            focus_pool = set(build_focus_hot_pool(formatted_windows))
            
            # 下一期实际开奖号码
            next_record = next(
                (r for r in self.history if r['period'] == next_period), None
            )
            if next_record is None:
                continue
            
            actual_numbers = set(next_record['numbers'])
            hits = focus_pool & actual_numbers
            hit_count = len(hits)
            
            # 随机基准: 从80中选36，期望命中 = 36 * 20 / 80 = 9
            expected_random = 9.0
            
            results.append({
                "period": period,
                "next_period": next_period,
                "focus_pool_size": len(focus_pool),
                "hits": hit_count,
                "hit_numbers": sorted(hits),
                "expected_random": expected_random,
                "advantage": round(hit_count - expected_random, 2),
                "hit_rate": round(hit_count / 20 * 100, 1),
                "focus_hit_rate": round(hit_count / len(focus_pool) * 100, 1)
            })
        
        # 统计汇总
        if results:
            avg_hits = np.mean([r["hits"] for r in results])
            avg_advantage = np.mean([r["advantage"] for r in results])
            win_rate = sum(1 for r in results if r["advantage"] > 0) / len(results) * 100
            
            # 各排名段命中率
            top5_stats = self._analyze_rank_prediction(periods_list, "10期", 5, recent_n)
            top10_stats = self._analyze_rank_prediction(periods_list, "10期", 10, recent_n)
            top20_stats = self._analyze_rank_prediction(periods_list, "10期", 20, recent_n)
        else:
            avg_hits = avg_advantage = win_rate = 0
            top5_stats = top10_stats = top20_stats = {}
        
        return {
            "analysis_window": f"最近{recent_n}期回测",
            "total_tested": len(results),
            "focus_pool_performance": {
                "avg_hits_per_period": round(avg_hits, 2),
                "random_baseline": 9.0,
                "avg_advantage": round(avg_advantage, 2),
                "beat_random_rate": round(win_rate, 1),
                "max_hits": max((r["hits"] for r in results), default=0),
                "min_hits": min((r["hits"] for r in results), default=0),
            },
            "rank_segment_performance": {
                "Top5_in_10window": top5_stats,
                "Top10_in_10window": top10_stats,
                "Top20_in_10window": top20_stats,
            },
            "recent_10_periods": results[-10:]
        }
    
    def _analyze_rank_prediction(self, periods_list: list, window: str, 
                                  top_k: int, recent_n: int) -> Dict[str, Any]:
        """分析特定窗口TopK号码的下期命中情况"""
        hits_list = []
        for i in range(len(periods_list) - 1):
            period = periods_list[i]
            next_period = periods_list[i + 1]
            
            # 获取Top K号码
            num_map = self.sliding_stats[period][window]
            top_k_nums = sorted(num_map.keys(), key=lambda n: (num_map[n]["rank"], n))[:top_k]
            top_k_set = set(top_k_nums)
            
            next_record = next(
                (r for r in self.history if r['period'] == next_period), None
            )
            if next_record is None:
                continue
            
            actual = set(next_record['numbers'])
            hit_count = len(top_k_set & actual)
            hits_list.append(hit_count)
        
        if not hits_list:
            return {}
        
        expected = top_k * 20 / 80  # 随机基准
        return {
            "avg_hits": round(np.mean(hits_list), 2),
            "random_baseline": round(expected, 2),
            "advantage": round(np.mean(hits_list) - expected, 2),
            "hit_rate": round(np.mean(hits_list) / 20 * 100, 1),
            "best_hit": max(hits_list),
            "worst_hit": min(hits_list),
        }
    
    # ── 分析4: 热码衰退检测 ──
    def analyze_decay_detection(self, recent_n: int = 30) -> Dict[str, Any]:
        """
        检测从热码衰退的号码：近期排名快速下降
        识别衰退早期信号，避免追热陷阱
        """
        print("[分析4] 热码衰退检测...")
        
        periods_list = list(self.sliding_stats.keys())[-recent_n:]
        if len(periods_list) < 5:
            return {"error": "数据不足，至少需要5期"}
        
        decay_signals = []
        
        for number in range(1, 81):
            # 跟踪最近N期在10期窗口中的排名变化
            ranks = []
            for period in periods_list:
                if period in self.sliding_stats:
                    ranks.append(self.sliding_stats[period]["10期"][number]["rank"])
            
            if len(ranks) < 5:
                continue
            
            # 计算排名趋势（正=排名下降=衰退）
            recent_5_avg = np.mean(ranks[-5:])
            earlier_5_avg = np.mean(ranks[:5]) if len(ranks) >= 10 else np.mean(ranks[:min(5, len(ranks))])
            
            rank_change = recent_5_avg - earlier_5_avg
            
            # 检测曾经热（排名<=20）但现在衰退（排名>40）的号码
            was_hot = any(r <= 20 for r in ranks[:max(1, len(ranks)//2)])
            now_cold = ranks[-1] > 40 if ranks else False
            rapid_decay = rank_change > 15
            
            if was_hot and (now_cold or rapid_decay):
                decay_signals.append({
                    "number": number,
                    "current_rank_10": ranks[-1],
                    "earlier_avg_rank": round(earlier_5_avg, 1),
                    "recent_avg_rank": round(recent_5_avg, 1),
                    "rank_change": round(rank_change, 1),
                    "signal_strength": "强" if rank_change > 25 else "中" if rank_change > 15 else "弱",
                    "decay_type": "断崖式" if rank_change > 30 else "渐进式"
                })
        
        decay_signals.sort(key=lambda x: -x["rank_change"])
        
        return {
            "analysis_window": f"最近{recent_n}期",
            "decay_signals": decay_signals[:20],
            "total_decaying": len(decay_signals),
            "insight": (
                f"检测到 {len(decay_signals)} 个衰退信号号码，"
                f"其中强信号 {sum(1 for d in decay_signals if d['signal_strength']=='强')} 个"
            )
        }
    
    # ── 分析5: 热码聚集效应 ──
    def analyze_clustering_effect(self, recent_n: int = 50) -> Dict[str, Any]:
        """
        分析热码在号码空间(1-80)中的聚集现象
        段位分析：1-10, 11-20, ..., 71-80
        以及热码间的共振模式
        """
        print("[分析5] 热码聚集效应分析...")
        
        periods_list = list(self.sliding_stats.keys())[-recent_n:]
        
        # 段位定义
        segments = {f"{i*10+1}-{(i+1)*10}": list(range(i*10+1, (i+1)*10+1)) 
                    for i in range(8)}
        
        # 统计每期热码在段位上的分布
        segment_distributions = []
        co_occurrence = np.zeros((80, 80), dtype=int)
        
        for period in periods_list:
            if period not in self.sliding_stats:
                continue
            
            # 获取10期窗口的Top20热码
            num_map = self.sliding_stats[period]["10期"]
            hot_nums = sorted(num_map.keys(), key=lambda n: (num_map[n]["rank"], n))[:20]
            
            # 段位分布
            seg_dist = {}
            for seg_name, seg_nums in segments.items():
                overlap = len(set(hot_nums) & set(seg_nums))
                seg_dist[seg_name] = overlap
            segment_distributions.append(seg_dist)
            
            # 共现矩阵
            for i_idx, n1 in enumerate(hot_nums):
                for n2 in hot_nums[i_idx+1:]:
                    co_occurrence[n1-1][n2-1] += 1
                    co_occurrence[n2-1][n1-1] += 1
        
        # 段位聚集分析
        avg_segment_dist = {}
        for seg_name in segments:
            values = [d.get(seg_name, 0) for d in segment_distributions]
            avg_segment_dist[seg_name] = {
                "avg_count": round(np.mean(values), 2),
                "max_count": max(values) if values else 0,
                "hot_rate": round(sum(1 for v in values if v >= 3) / max(len(values), 1) * 100, 1),
                "expected": 2.5  # 20热码/8段 = 2.5
            }
        
        # 找出最强共现对
        top_pairs = []
        for i in range(80):
            for j in range(i+1, 80):
                if co_occurrence[i][j] > 0:
                    top_pairs.append({
                        "num1": i+1,
                        "num2": j+1,
                        "co_occurrence": co_occurrence[i][j],
                        "co_rate": round(co_occurrence[i][j] / max(len(periods_list), 1) * 100, 1)
                    })
        
        top_pairs.sort(key=lambda x: -x["co_occurrence"])
        
        # 找出聚集热点段位
        hot_segments = sorted(
            avg_segment_dist.items(),
            key=lambda x: -x[1]["avg_count"]
        )
        
        return {
            "analysis_window": f"最近{recent_n}期",
            "segment_analysis": {
                name: data for name, data in hot_segments
            },
            "hottest_segment": hot_segments[0][0] if hot_segments else "N/A",
            "coldest_segment": hot_segments[-1][0] if hot_segments else "N/A",
            "top_co_occurrence_pairs": top_pairs[:15],
            "cluster_insight": (
                f"最聚集段位: {hot_segments[0][0]} (均值{hot_segments[0][1]['avg_count']}), "
                f"最稀疏段位: {hot_segments[-1][0]} (均值{hot_segments[-1][1]['avg_count']})"
            )
        }
    
    # ── 分析6: 冷码觉醒预测 ──
    def analyze_cold_awakening(self, recent_n: int = 50) -> Dict[str, Any]:
        """
        检测冷码回温的早期信号
        基于以下指标：
        1. 连续冷码期数达到极值后的回弹概率
        2. 近期命中频率微升（ratio从低位上升）
        3. 多窗口一致性：50期/25期/10期窗口中同时出现回温迹象
        """
        print("[分析6] 冷码觉醒预测...")
        
        periods_list = list(self.sliding_stats.keys())[-recent_n:]
        if len(periods_list) < 10:
            return {"error": "数据不足"}
        
        awakening_signals = []
        
        for number in range(1, 81):
            # 获取近期的ratio趋势
            ratios_10 = []
            ratios_25 = []
            for period in periods_list:
                if period in self.sliding_stats:
                    ratios_10.append(self.sliding_stats[period]["10期"][number]["ratio"])
                    ratios_25.append(self.sliding_stats[period]["25期"][number]["ratio"])
            
            if len(ratios_10) < 10:
                continue
            
            current_ratio_10 = ratios_10[-1]
            current_ratio_25 = ratios_25[-1] if ratios_25 else 0
            
            # 10期窗口当前排名
            current_rank = self.sliding_stats[periods_list[-1]]["10期"][number]["rank"]
            
            # 判断是否为冷码（10期排名>40）
            if current_rank <= 40:
                continue  # 不是冷码，跳过
            
            # 冷码觉醒信号评估
            signals = 0
            signal_details = []
            
            # 信号1: ratio从极低位置回升
            if len(ratios_10) >= 5:
                recent_5_avg = np.mean(ratios_10[-5:])
                earlier_5_avg = np.mean(ratios_10[-10:-5]) if len(ratios_10) >= 10 else np.mean(ratios_10[:5])
                if recent_5_avg > earlier_5_avg and recent_5_avg > 50:
                    signals += 2
                    signal_details.append(f"10期ratio回升({earlier_5_avg:.0f}→{recent_5_avg:.0f})")
            
            # 信号2: 25期窗口排名优于10期窗口（长期优于短期=正在回温）
            rank_25 = self.sliding_stats[periods_list[-1]]["25期"][number]["rank"]
            if rank_25 < current_rank - 10:
                signals += 2
                signal_details.append(f"25期排名({rank_25})远优于10期({current_rank})")
            
            # 信号3: 50期窗口仍在Top40
            rank_50 = self.sliding_stats[periods_list[-1]]["50期"][number]["rank"]
            if rank_50 <= 40:
                signals += 1
                signal_details.append(f"50期排名({rank_50})仍在Top40")
            
            # 信号4: 全量排名不差
            rank_all = self.sliding_stats[periods_list[-1]]["全量"][number]["rank"]
            if rank_all <= 50:
                signals += 1
                signal_details.append(f"全量排名({rank_all})≤50")
            
            # 信号5: 近3期有出现记录
            recent_3_hits = 0
            for r in self.history[:3]:
                if number in r['numbers']:
                    recent_3_hits += 1
            if recent_3_hits >= 1:
                signals += 1
                signal_details.append(f"近3期出现{recent_3_hits}次")
            
            if signals >= 3:
                awakening_signals.append({
                    "number": number,
                    "current_rank_10": current_rank,
                    "rank_25": rank_25,
                    "rank_50": rank_50,
                    "rank_all": rank_all,
                    "signal_score": signals,
                    "signal_details": signal_details,
                    "awakening_probability": round(
                        min(signals / 7 * 100, 85), 1
                    )
                })
        
        awakening_signals.sort(key=lambda x: -x["signal_score"])
        
        return {
            "analysis_window": f"最近{recent_n}期",
            "awakening_candidates": awakening_signals[:20],
            "total_candidates": len(awakening_signals),
            "high_confidence": [
                s for s in awakening_signals if s["signal_score"] >= 5
            ],
            "insight": (
                f"检测到 {len(awakening_signals)} 个冷码觉醒候选，"
                f"高置信度 {len([s for s in awakening_signals if s['signal_score'] >= 5])} 个"
            )
        }
    
    # ── 分析7: 滑动窗口信息增益 ──
    def analyze_window_information_gain(self, recent_n: int = 50) -> Dict[str, Any]:
        """
        比较不同窗口(10/25/50/全量)对下期命中的预测增益
        找出最优窗口组合
        """
        print("[分析7] 滑动窗口信息增益分析...")
        
        periods_list = list(self.sliding_stats.keys())[-recent_n:]
        
        window_hit_rates = {label: [] for label, _ in WINDOWS}
        
        for i in range(len(periods_list) - 1):
            period = periods_list[i]
            next_period = periods_list[i + 1]
            
            next_record = next(
                (r for r in self.history if r['period'] == next_period), None
            )
            if next_record is None:
                continue
            
            actual = set(next_record['numbers'])
            
            for label, _ in WINDOWS:
                num_map = self.sliding_stats[period][label]
                top20 = sorted(num_map.keys(), key=lambda n: (num_map[n]["rank"], n))[:20]
                hit_count = len(set(top20) & actual)
                window_hit_rates[label].append(hit_count)
        
        # 计算各窗口的平均命中
        window_performance = {}
        for label, hits in window_hit_rates.items():
            if hits:
                window_performance[label] = {
                    "avg_hits": round(np.mean(hits), 2),
                    "random_baseline": 5.0,  # 20*20/80
                    "advantage": round(np.mean(hits) - 5.0, 2),
                    "hit_rate": round(np.mean(hits) / 20 * 100, 1),
                    "std": round(np.std(hits), 2),
                    "sharpe_like": round(
                        (np.mean(hits) - 5.0) / max(np.std(hits), 0.01), 2
                    )
                }
        
        # 找出最优窗口
        best_window = max(
            window_performance.items(),
            key=lambda x: x[1]["advantage"]
        ) if window_performance else ("N/A", {})
        
        # 多窗口融合测试（取多个窗口Top的交集/并集）
        fusion_results = {}
        for strategy_name, strategy_fn in [
            ("交集_Top20_10期与25期", lambda p: set(
                sorted(self.sliding_stats[p]["10期"].keys(), key=lambda n: (self.sliding_stats[p]["10期"][n]["rank"], n))[:20]
            ) & set(
                sorted(self.sliding_stats[p]["25期"].keys(), key=lambda n: (self.sliding_stats[p]["25期"][n]["rank"], n))[:20]
            )),
            ("并集_Top10_10期与25期", lambda p: set(
                sorted(self.sliding_stats[p]["10期"].keys(), key=lambda n: (self.sliding_stats[p]["10期"][n]["rank"], n))[:10]
            ) | set(
                sorted(self.sliding_stats[p]["25期"].keys(), key=lambda n: (self.sliding_stats[p]["25期"][n]["rank"], n))[:10]
            )),
        ]:
            fusion_hits = []
            for i in range(len(periods_list) - 1):
                period = periods_list[i]
                next_period = periods_list[i + 1]
                next_record = next(
                    (r for r in self.history if r['period'] == next_period), None
                )
                if next_record is None:
                    continue
                actual = set(next_record['numbers'])
                try:
                    selected = strategy_fn(period)
                    hit_count = len(selected & actual)
                    fusion_hits.append({
                        "hits": hit_count,
                        "pool_size": len(selected),
                        "efficiency": round(hit_count / max(len(selected), 1) * 100, 1)
                    })
                except:
                    pass
            
            if fusion_hits:
                fusion_results[strategy_name] = {
                    "avg_hits": round(np.mean([h["hits"] for h in fusion_hits]), 2),
                    "avg_pool_size": round(np.mean([h["pool_size"] for h in fusion_hits]), 1),
                    "avg_efficiency": round(np.mean([h["efficiency"] for h in fusion_hits]), 1),
                }
        
        return {
            "analysis_window": f"最近{recent_n}期",
            "single_window_performance": window_performance,
            "best_single_window": best_window[0],
            "fusion_strategies": fusion_results,
            "insight": (
                f"最优单窗口: {best_window[0]} "
                f"(平均命中{best_window[1].get('avg_hits', 'N/A')}, "
                f"优势{best_window[1].get('advantage', 'N/A')})"
            )
        }
    
    # ── 分析8: 号码频率分布正态性检验 ──
    def analyze_frequency_distribution(self, window: int = 50) -> Dict[str, Any]:
        """
        分析指定窗口内号码出现频率的分布特征
        检验是否符合理论二项分布，识别显著偏离的号码
        """
        print("[分析8] 号码频率分布正态性检验...")
        
        hist = self.hist_chrono
        subset = hist[-window:] if window <= len(hist) else hist
        
        counts = collections.Counter(n for r in subset for n in r["numbers"])
        
        # 理论分布：每期20/80=0.25概率
        n_periods = len(subset)
        p_theory = 0.25
        expected_hits = n_periods * p_theory
        std_theory = np.sqrt(n_periods * p_theory * (1 - p_theory))
        
        # 计算每个号码的Z-score
        z_scores = {}
        for number in range(1, 81):
            observed = counts.get(number, 0)
            z = (observed - expected_hits) / std_theory if std_theory > 0 else 0
            z_scores[number] = {
                "observed": observed,
                "expected": round(expected_hits, 1),
                "z_score": round(z, 2),
                "deviation": round((observed - expected_hits) / expected_hits * 100, 1),
                "significance": "极显著" if abs(z) > 2.576 else 
                               "显著" if abs(z) > 1.96 else
                               "边际显著" if abs(z) > 1.645 else "不显著"
            }
        
        # 极端偏离号码
        significantly_hot = sorted(
            [(n, d) for n, d in z_scores.items() if d["z_score"] > 1.96],
            key=lambda x: -x[1]["z_score"]
        )
        significantly_cold = sorted(
            [(n, d) for n, d in z_scores.items() if d["z_score"] < -1.96],
            key=lambda x: x[1]["z_score"]
        )
        
        # 整体分布正态性检验 (Shapiro-Wilk近似)
        observed_freqs = [counts.get(n, 0) for n in range(1, 81)]
        from scipy import stats as scipy_stats
        try:
            shapiro_stat, shapiro_p = scipy_stats.shapiro(observed_freqs)
            normality = {
                "test": "Shapiro-Wilk",
                "statistic": round(shapiro_stat, 4),
                "p_value": round(shapiro_p, 4),
                "is_normal": shapiro_p > 0.05,
                "interpretation": "符合正态" if shapiro_p > 0.05 else "显著偏离正态"
            }
        except ImportError:
            normality = {"test": "Shapiro-Wilk", "note": "scipy未安装，跳过正态性检验"}
        
        return {
            "window": f"{window}期",
            "n_periods": n_periods,
            "expected_hits_per_number": round(expected_hits, 1),
            "std_per_number": round(std_theory, 2),
            "normality_test": normality,
            "significantly_hot_numbers": [
                {"number": n, **d} for n, d in significantly_hot[:10]
            ],
            "significantly_cold_numbers": [
                {"number": n, **d} for n, d in significantly_cold[:10]
            ],
            "distribution_stats": {
                "mean": round(np.mean(observed_freqs), 2),
                "std": round(np.std(observed_freqs), 2),
                "min": min(observed_freqs),
                "max": max(observed_freqs),
                "range": max(observed_freqs) - min(observed_freqs),
                "cv": round(np.std(observed_freqs) / np.mean(observed_freqs) * 100, 1)
            }
        }
    
    # ── 综合报告生成 ──
    def generate_full_report(self) -> str:
        """生成完整的深度分析报告"""
        print("\n" + "=" * 60)
        print("  快乐8 热码统计深度分析系统 v1.0")
        print("=" * 60)
        
        # 执行所有分析
        persistence = self.analyze_persistence(recent_n=30)
        transition = self.analyze_transition_matrix(recent_n=100)
        predictive = self.analyze_predictive_power(recent_n=50)
        decay = self.analyze_decay_detection(recent_n=30)
        clustering = self.analyze_clustering_effect(recent_n=50)
        awakening = self.analyze_cold_awakening(recent_n=50)
        window_info = self.analyze_window_information_gain(recent_n=50)
        freq_dist = self.analyze_frequency_distribution(window=50)
        
        # 构建报告
        latest = self.history[0]
        report_lines = [
            f"# 快乐8 热码统计深度分析报告",
            f"**生成时间：** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**数据范围：** 第{self.hist_chrono[0]['period']}期 ~ 第{latest['period']}期 (共{self.total_periods}期)",
            f"**最新开奖：** 第{latest['period']}期 ({latest['date']}) - {'-'.join(f'{n:02d}' for n in latest['numbers'])}",
            f"",
            f"---",
            f"",
            f"## 一、热码持续性分析 ({persistence['analysis_window']})",
            f"",
            f"### 1.1 高持续性号码（连续多期保持热码状态）",
            f"",
            f"| 号码 | 热码频率 | 热码率 | 最大连续热期 | 持续性评分 |",
            f"|:----:|:-------:|:------:|:----------:|:---------:|",
        ]
        
        for item in persistence["top_persistent_numbers"][:10]:
            report_lines.append(
                f"| {item['number']:02d} | {item['hot_frequency']} | {item['hot_rate']}% | "
                f"{item['max_consecutive_hot']} | {item['persistence_score']} |"
            )
        
        report_lines.extend([
            f"",
            f"### 1.2 持续性分布",
            f"",
            f"- 高持续性号码(>60%时间热): **{persistence['persistence_distribution']['high_persistence (>60%热)']}** 个",
            f"- 中等持续性(30-60%): **{persistence['persistence_distribution']['medium_persistence (30-60%)']}** 个",
            f"- 低持续性(<30%): **{persistence['persistence_distribution']['low_persistence (<30%)']}** 个",
            f"",
            f"---",
            f"",
            f"## 二、热码状态转移矩阵 ({transition['analysis_window']})",
            f"",
            f"### 2.1 全局转移概率",
            f"",
            f"| 当前状态 | → 热 | → 温 | → 冷 |",
            f"|:-------:|:----:|:----:|:----:|",
        ])
        
        for s1 in ["热", "温", "冷"]:
            probs = transition["transition_matrix"][s1]
            report_lines.append(
                f"| {s1} | {probs['热']}% | {probs['温']}% | {probs['冷']}% |"
            )
        
        report_lines.extend([
            f"",
            f"> **核心洞察：** {transition['key_insight']}",
            f"",
            f"### 2.2 异常转移模式号码",
            f"",
            f"| 号码 | 热→热率 | 热→冷率 | 信号类型 |",
            f"|:----:|:------:|:------:|:-------:|",
        ])
        
        for item in transition["anomaly_numbers"][:10]:
            report_lines.append(
                f"| {item['number']:02d} | {item['hot_to_hot_rate']}% | {item['hot_to_cold_rate']}% | {item['signal']} |"
            )
        
        report_lines.extend([
            f"",
            f"---",
            f"",
            f"## 三、热码预测力评估 ({predictive['analysis_window']})",
            f"",
            f"### 3.1 Focus Pool (36码) 回测表现",
            f"",
            f"| 指标 | 数值 |",
            f"|:----:|:----:|",
            f"| 平均命中数 | {predictive['focus_pool_performance']['avg_hits_per_period']} |",
            f"| 随机基准 | {predictive['focus_pool_performance']['random_baseline']} |",
            f"| 平均优势 | {predictive['focus_pool_performance']['avg_advantage']} |",
            f"| 胜随机概率 | {predictive['focus_pool_performance']['beat_random_rate']}% |",
            f"| 最高命中 | {predictive['focus_pool_performance']['max_hits']} |",
            f"| 最低命中 | {predictive['focus_pool_performance']['min_hits']} |",
            f"",
            f"### 3.2 各排名段预测效果",
            f"",
            f"| 排名段 | 平均命中 | 随机基准 | 优势 | 命中率 |",
            f"|:-----:|:-------:|:-------:|:----:|:-----:|",
        ])
        
        for seg_name, seg_data in predictive["rank_segment_performance"].items():
            if seg_data:
                report_lines.append(
                    f"| {seg_name} | {seg_data['avg_hits']} | {seg_data['random_baseline']} | "
                    f"{seg_data['advantage']} | {seg_data['hit_rate']}% |"
                )
        
        report_lines.extend([
            f"",
            f"---",
            f"",
            f"## 四、热码衰退检测 ({decay['analysis_window']})",
            f"",
            f"> {decay['insight']}",
            f"",
            f"| 号码 | 当前排名 | 早期均值排名 | 近期均值排名 | 排名变化 | 信号强度 | 衰退类型 |",
            f"|:----:|:-------:|:----------:|:----------:|:-------:|:-------:|:-------:|",
        ])
        
        for item in decay["decay_signals"][:15]:
            report_lines.append(
                f"| {item['number']:02d} | {item['current_rank_10']} | {item['earlier_avg_rank']} | "
                f"{item['recent_avg_rank']} | +{item['rank_change']} | {item['signal_strength']} | {item['decay_type']} |"
            )
        
        report_lines.extend([
            f"",
            f"---",
            f"",
            f"## 五、热码聚集效应 ({clustering['analysis_window']})",
            f"",
            f"> {clustering['cluster_insight']}",
            f"",
            f"### 5.1 段位分布",
            f"",
            f"| 段位 | 平均热码数 | 理论值 | 热码超标率 |",
            f"|:---:|:---------:|:-----:|:---------:|",
        ])
        
        for seg_name, seg_data in clustering["segment_analysis"].items():
            report_lines.append(
                f"| {seg_name} | {seg_data['avg_count']} | {seg_data['expected']} | {seg_data['hot_rate']}% |"
            )
        
        report_lines.extend([
            f"",
            f"### 5.2 最强共现号码对",
            f"",
            f"| 号码A | 号码B | 共现次数 | 共现率 |",
            f"|:-----:|:-----:|:-------:|:-----:|",
        ])
        
        for pair in clustering["top_co_occurrence_pairs"][:10]:
            report_lines.append(
                f"| {pair['num1']:02d} | {pair['num2']:02d} | {pair['co_occurrence']} | {pair['co_rate']}% |"
            )
        
        report_lines.extend([
            f"",
            f"---",
            f"",
            f"## 六、冷码觉醒预测 ({awakening['analysis_window']})",
            f"",
            f"> {awakening['insight']}",
            f"",
            f"| 号码 | 10期排名 | 25期排名 | 50期排名 | 全量排名 | 信号分 | 觉醒概率 | 信号详情 |",
            f"|:----:|:-------:|:-------:|:-------:|:-------:|:-----:|:-------:|:-------:|",
        ])
        
        for item in awakening["awakening_candidates"][:15]:
            details_str = "; ".join(item["signal_details"][:3])
            report_lines.append(
                f"| {item['number']:02d} | {item['current_rank_10']} | {item['rank_25']} | "
                f"{item['rank_50']} | {item['rank_all']} | {item['signal_score']} | "
                f"{item['awakening_probability']}% | {details_str} |"
            )
        
        report_lines.extend([
            f"",
            f"---",
            f"",
            f"## 七、滑动窗口信息增益 ({window_info['analysis_window']})",
            f"",
            f"> 最优单窗口: **{window_info['best_single_window']}**",
            f"",
            f"### 7.1 单窗口Top20预测效果",
            f"",
            f"| 窗口 | 平均命中 | 随机基准 | 优势 | 命中率 | 标准差 | 夏普比率 |",
            f"|:---:|:-------:|:-------:|:---:|:-----:|:-----:|:-------:|",
        ])
        
        for label, perf in window_info["single_window_performance"].items():
            report_lines.append(
                f"| {label} | {perf['avg_hits']} | {perf['random_baseline']} | "
                f"{perf['advantage']} | {perf['hit_rate']}% | {perf['std']} | {perf['sharpe_like']} |"
            )
        
        report_lines.extend([
            f"",
            f"---",
            f"",
            f"## 八、号码频率分布检验 ({freq_dist['window']})",
            f"",
            f"### 8.1 分布特征",
            f"",
            f"| 统计量 | 值 |",
            f"|:-----:|:--:|",
            f"| 期数 | {freq_dist['n_periods']} |",
            f"| 每号期望命中 | {freq_dist['expected_hits_per_number']} |",
            f"| 标准差 | {freq_dist['std_per_number']} |",
            f"| 观测均值 | {freq_dist['distribution_stats']['mean']} |",
            f"| 观测标准差 | {freq_dist['distribution_stats']['std']} |",
            f"| 极差 | {freq_dist['distribution_stats']['range']} |",
            f"| 变异系数 | {freq_dist['distribution_stats']['cv']}% |",
        ])
        
        if "statistic" in freq_dist["normality_test"]:
            report_lines.extend([
                f"| 正态性检验(W) | {freq_dist['normality_test']['statistic']} |",
                f"| 正态性p值 | {freq_dist['normality_test']['p_value']} |",
                f"| 正态性判定 | {freq_dist['normality_test']['interpretation']} |",
            ])
        
        report_lines.extend([
            f"",
            f"### 8.2 显著偏热号码 (Z > 1.96, α=0.05)",
            f"",
            f"| 号码 | 观测 | 期望 | Z值 | 偏差% | 显著性 |",
            f"|:----:|:---:|:---:|:---:|:----:|:-----:|",
        ])
        
        for item in freq_dist["significantly_hot_numbers"]:
            report_lines.append(
                f"| {item['number']:02d} | {item['observed']} | {item['expected']} | "
                f"{item['z_score']} | {item['deviation']}% | {item['significance']} |"
            )
        
        report_lines.extend([
            f"",
            f"### 8.3 显著偏冷号码 (Z < -1.96, α=0.05)",
            f"",
            f"| 号码 | 观测 | 期望 | Z值 | 偏差% | 显著性 |",
            f"|:----:|:---:|:---:|:---:|:----:|:-----:|",
        ])
        
        for item in freq_dist["significantly_cold_numbers"]:
            report_lines.append(
                f"| {item['number']:02d} | {item['observed']} | {item['expected']} | "
                f"{item['z_score']} | {item['deviation']}% | {item['significance']} |"
            )
        
        # ── 综合研判 ──
        report_lines.extend([
            f"",
            f"---",
            f"",
            f"## 九、综合研判与策略建议",
            f"",
            f"### 9.1 热码核心池推荐",
            f"",
        ])
        
        # 综合各分析维度的推荐
        # 高持续性 + 强转移概率 + 高预测力 => 核心热码
        core_hot = [item["number"] for item in persistence["top_persistent_numbers"][:10]]
        sustained_hot = [item["number"] for item in transition["anomaly_numbers"] 
                        if item["signal"] == "强持续热码"][:5]
        
        core_pool = list(set(core_hot) | set(sustained_hot))[:12]
        core_pool.sort()
        
        report_lines.append(
            f"**核心热码池 (高持续性+强转移):** `{' '.join(f'{n:02d}' for n in core_pool)}`"
        )
        
        # 衰退预警
        decay_nums = [item["number"] for item in decay["decay_signals"][:5]]
        report_lines.extend([
            f"",
            f"**衰退预警号码 (建议回避):** `{' '.join(f'{n:02d}' for n in decay_nums)}`",
            f"",
        ])
        
        # 冷码觉醒
        awakening_nums = [item["number"] for item in awakening["high_confidence"][:8]]
        report_lines.append(
            f"**冷码觉醒候选 (可适度跟进):** `{' '.join(f'{n:02d}' for n in awakening_nums)}`"
        )
        
        # 聚集段位
        report_lines.extend([
            f"",
            f"**最聚集段位:** {clustering['hottest_segment']} — 该区间选号可优先考虑",
            f"**最稀疏段位:** {clustering['coldest_segment']} — 该区间可能存在冷码觉醒机会",
            f"",
            f"### 9.2 最优窗口策略",
            f"",
            f"基于信息增益分析，**{window_info['best_single_window']}** 窗口具有最高预测价值。"
            f"建议以该窗口排名为基础，结合25期窗口做交叉验证。",
            f"",
            f"### 9.3 风险提示",
            f"",
            f"1. 热码预测力的统计优势虽然存在，但幅度有限，不可过度依赖单一维度",
            f"2. 衰退检测为滞后指标，实际衰退可能早于信号出现",
            f"3. 冷码觉醒为前瞻信号，置信度需通过后续开奖验证",
            f"4. 号码分布的正态性检验结果（{freq_dist['normality_test'].get('interpretation', 'N/A')}）"
            f"提示随机性仍然占主导地位",
            f"",
            f"---",
            f"*报告由热码深度分析系统 v1.0 自动生成*",
            f"*分析引擎: 资深研发与数据分析专家*",
        ])
        
        report_text = "\n".join(report_lines)
        
        # 保存报告
        os.makedirs(REPORT_DIR, exist_ok=True)
        report_filename = f"热码深度分析_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.md"
        report_path = os.path.join(REPORT_DIR, report_filename)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(f"\n✅ 深度分析报告已保存: {report_path}")
        
        # 同时保存JSON数据
        json_filename = f"热码深度分析_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json"
        json_path = os.path.join(REPORT_DIR, json_filename)
        
        json_data = {
            "generated_at": datetime.datetime.now().isoformat(),
            "total_periods": self.total_periods,
            "persistence": persistence,
            "transition": transition,
            "predictive": predictive,
            "decay": decay,
            "clustering": clustering,
            "awakening": awakening,
            "window_info": window_info,
            "freq_dist": freq_dist,
        }
        
        # 移除不可序列化的all_data
        if "all_data" in json_data.get("persistence", {}):
            del json_data["persistence"]["all_data"]
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"✅ 分析数据已保存: {json_path}")
        
        return report_text


# ═══════════════════════════════════════════════════════════════
# 主执行入口
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  快乐8 热码统计深度分析系统 v1.0")
    print("  资深研发与数据分析专家")
    print("=" * 60)
    
    # 加载历史数据
    history = load_history()
    if not history:
        print("[错误] 无法加载历史数据，程序退出")
        return
    
    print(f"[数据] 已加载 {len(history)} 期历史数据")
    print(f"[范围] {history[-1]['period']} ~ {history[0]['period']}")
    
    # 初始化分析引擎
    analyzer = HotNumberDeepAnalyzer(history)
    
    # 生成完整报告
    report = analyzer.generate_full_report()
    
    # 打印报告摘要
    print("\n" + "=" * 60)
    print("  分析完成！报告摘要:")
    print("=" * 60)
    
    # 提取关键洞察
    lines = report.split("\n")
    for line in lines:
        if line.startswith("> **核心洞察") or line.startswith("**核心热码") or \
           line.startswith("**衰退预警") or line.startswith("**冷码觉醒") or \
           line.startswith("**最聚集") or line.startswith("**最优窗口"):
            print(f"  {line}")


if __name__ == '__main__':
    main()
