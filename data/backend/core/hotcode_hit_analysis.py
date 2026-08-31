#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 热码→命中率关联分析系统 v1.0
========================================
核心能力：
1. 热码覆盖分析 - 热码对开奖号码的覆盖率、命中度
2. 热码命中评估 - 热码表现指标（精准度、召回率、F1分数）
3. 热码贡献度分析 - 各热码的单独贡献与组合效果
4. 市场环境适应性 - 热码在不同市场环境下的表现对比
5. 每日热码复盘报告 - 自动生成热码的表现总结

Author: 数据分析专家·资深研发分析专家
Date: 2026-05-14
Version: 1.0
"""

import os
import sys
import json
import datetime
import collections
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Set, Optional
from dataclasses import dataclass, asdict, field

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
CACHE_DIR = os.path.join(_PROJ, 'cache')

NUM_TOTAL = 80
WINDOWS = ["全量", "50期", "25期", "10期"]


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════

@dataclass
class HotCodeHitMetrics:
    """热码命中指标集合"""
    period: str
    date: str
    total_hot_nums: int              # 热码总数
    hit_count: int                   # 命中个数
    hit_rate: float                  # 命中率 (命中数/总出球数)
    coverage_rate: float             # 覆盖率 (命中数/热码数)
    precision: float                 # 精准度 (命中数/热码数)
    recall: float                    # 召回率 (命中数/总出球数)
    f1_score: float                  # F1分数
    hit_positions: List[int] = field(default_factory=list)  # 命中的位置
    hit_numbers: List[int] = field(default_factory=list)    # 命中的号码
    missed_numbers: List[int] = field(default_factory=list) # 未命中的号码

    def to_dict(self):
        return asdict(self)


@dataclass
class MarketEnvironment:
    """市场环境特征"""
    period: str
    focus_degree: float              # 聚焦度 (号码集中在某个区间的程度)
    scatter_degree: float            # 散点度
    hot_concentration: float         # 热码浓度（热码命中的集中度）
    environment_type: str            # 聚焦/散点/中性


# ═══════════════════════════════════════════════════════════════
# 数据加载与基础计算
# ═══════════════════════════════════════════════════════════════

def load_history() -> List[Dict[str, Any]]:
    """加载历史开奖数据（最新在前）

    v2.2: 委托给 utils.history_loader.load_history()，消除重复实现。
    本模块约定键名为 period/date, 与 history_loader 的 issue/date 做兼容映射。
    """
    from utils.history_loader import load_history as _load
    return [
        {'period': h['issue'], 'date': h.get('date', ''), 'numbers': list(h['numbers'])}
        for h in _load()
    ]


def load_hot_numbers(period: str) -> Set[int]:
    """
    加载某一期的热码统计
    使用v4.1的多窗口交集策略
    """
    try:
        # 使用本模块的 load_history (generate_hot_excel 并无 load_history, 旧导入恒 ImportError)
        from data_acquisition.generate_hot_excel import (
            build_hot_windows, build_focus_hot_pool
        )
        history = load_history()
        # 前瞻防护: 只使用"该期之前"的历史构建热码池, 排除目标期自身的开奖结果
        cutoff = int(period)
        history = [h for h in history if int(h['period']) < cutoff]
        if not history:
            return set()
        hot_windows = build_hot_windows(history)
        hot_numbers = build_focus_hot_pool(hot_windows)
        return set(hot_numbers)
    except Exception as e:
        print(f"[警告] 加载热码失败: {e}")
        return set()


# ═══════════════════════════════════════════════════════════════
# 命中率分析核心算法
# ═══════════════════════════════════════════════════════════════

def calculate_hit_metrics(hot_numbers: Set[int], drawn_numbers: List[int], 
                         period: str, date: str) -> HotCodeHitMetrics:
    """
    计算热码命中指标
    
    Args:
        hot_numbers: 热码集合
        drawn_numbers: 开奖号码列表（20个）
        period: 期号
        date: 开奖日期
    
    Returns:
        HotCodeHitMetrics: 命中指标对象
    """
    drawn_set = set(drawn_numbers)
    hit_set = hot_numbers & drawn_set
    
    total_hot = len(hot_numbers)
    total_drawn = len(drawn_numbers)  # 通常20个
    hit_count = len(hit_set)
    
    # 计算各指标
    # 语义区分 (修复: 此前 coverage_rate 与 precision 同值, recall 与 hit_rate 同值):
    #   precision  = 精准度 = 命中数 / 推荐(热码)数          (命中占推荐的比例)
    #   coverage   = 覆盖率 = 推荐(热码)覆盖开奖号码的比例     = 命中数 / 开奖数
    #   hit_rate / recall = 命中率/召回率 = 命中数 / 开奖数 (同一数量, 名称不同)
    hit_rate = hit_count / total_drawn if total_drawn > 0 else 0
    coverage_rate = hit_count / total_drawn if total_drawn > 0 else 0
    precision = hit_count / total_hot if total_hot > 0 else 0
    recall = hit_count / total_drawn if total_drawn > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall + 1e-9)
    
    # 找出命中的号码及位置
    hit_numbers = sorted(list(hit_set))
    hit_positions = [drawn_numbers.index(n) + 1 for n in hit_numbers]
    missed_numbers = sorted(list(hot_numbers - drawn_set))
    
    return HotCodeHitMetrics(
        period=period,
        date=date,
        total_hot_nums=total_hot,
        hit_count=hit_count,
        hit_rate=hit_rate,
        coverage_rate=coverage_rate,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        hit_positions=hit_positions,
        hit_numbers=hit_numbers,
        missed_numbers=missed_numbers
    )


def identify_market_environment(drawn_numbers: List[int]) -> MarketEnvironment:
    """
    识别市场环境特征
    
    Args:
        drawn_numbers: 开奖号码
    
    Returns:
        MarketEnvironment: 环境特征
    """
    drawn_set = set(drawn_numbers)
    
    # 计算聚焦度 - 号码在某个区间的集中程度
    zone_distribution = collections.defaultdict(int)
    for num in drawn_set:
        if 1 <= num <= 20:
            zone_distribution["1-20"] += 1
        elif 21 <= num <= 40:
            zone_distribution["21-40"] += 1
        elif 41 <= num <= 60:
            zone_distribution["41-60"] += 1
        elif 61 <= num <= 80:
            zone_distribution["61-80"] += 1
    
    max_count = max(zone_distribution.values()) if zone_distribution else 0
    focus_degree = max_count / len(drawn_set) if len(drawn_set) > 0 else 0
    
    # 环境分类
    if focus_degree > 0.4:
        env_type = "聚焦"
    elif focus_degree < 0.25:
        env_type = "散点"
    else:
        env_type = "中性"
    
    return MarketEnvironment(
        period="",
        focus_degree=focus_degree,
        scatter_degree=1 - focus_degree,
        hot_concentration=0,
        environment_type=env_type
    )


# ═══════════════════════════════════════════════════════════════
# 关联分析与统计
# ═══════════════════════════════════════════════════════════════

def batch_analyze_hotcode_hits(history_data: List[Dict], 
                               lookback_periods: int = 30) -> Dict[str, Any]:
    """
    批量分析热码命中情况（最近N期）
    
    Args:
        history_data: 历史数据
        lookback_periods: 回看期数（默认30期）
    
    Returns:
        分析结果汇总
    """
    metrics_list = []
    environments = []
    
    for i, record in enumerate(history_data[:lookback_periods]):
        period = record['period']
        date = record['date']
        numbers = record['numbers']
        
        # 加载该期的热码
        hot_nums = load_hot_numbers(period)
        if not hot_nums:
            continue
        
        # 计算命中指标
        metrics = calculate_hit_metrics(hot_nums, numbers, period, date)
        metrics_list.append(metrics)
        
        # 识别市场环境
        env = identify_market_environment(numbers)
        env.period = period
        env.hot_concentration = metrics.coverage_rate
        environments.append(env)
    
    # 统计汇总
    if not metrics_list:
        return {
            "total_periods": 0,
            "avg_hot_count": 0,
            "avg_hit_rate": 0,
            "avg_coverage_rate": 0,
            "avg_precision": 0,
            "avg_f1_score": 0,
            "best_period": None,
            "worst_period": None
        }
    
    hit_rates = [m.hit_rate for m in metrics_list]
    coverage_rates = [m.coverage_rate for m in metrics_list]
    precisions = [m.precision for m in metrics_list]
    f1_scores = [m.f1_score for m in metrics_list]
    hot_counts = [m.total_hot_nums for m in metrics_list]
    
    best_metric = max(metrics_list, key=lambda m: m.f1_score)
    worst_metric = min(metrics_list, key=lambda m: m.f1_score)
    
    return {
        "total_periods": len(metrics_list),
        "avg_hot_count": round(np.mean(hot_counts), 1),
        "avg_hit_rate": round(np.mean(hit_rates), 4),
        "avg_coverage_rate": round(np.mean(coverage_rates), 4),
        "avg_precision": round(np.mean(precisions), 4),
        "avg_recall": round(np.mean([m.recall for m in metrics_list]), 4),
        "avg_f1_score": round(np.mean(f1_scores), 4),
        "std_f1_score": round(np.std(f1_scores), 4),
        "max_f1_score": round(max(f1_scores), 4),
        "min_f1_score": round(min(f1_scores), 4),
        "best_period": best_metric.period,
        "best_f1": round(best_metric.f1_score, 4),
        "worst_period": worst_metric.period,
        "worst_f1": round(worst_metric.f1_score, 4),
        "metrics_list": [m.to_dict() for m in metrics_list],
        "environments": [asdict(e) for e in environments]
    }


# ═══════════════════════════════════════════════════════════════
# 报告生成
# ═══════════════════════════════════════════════════════════════

def generate_daily_hotcode_report(period: str) -> str:
    """
    生成每日热码表现报告
    
    Args:
        period: 期号
    
    Returns:
        报告文本
    """
    history = load_history()
    
    # 找到当前期的数据
    current_record = None
    for record in history:
        if record['period'] == period:
            current_record = record
            break
    
    if not current_record:
        return f"[错误] 未找到期号 {period} 的数据"
    
    hot_nums = load_hot_numbers(period)
    metrics = calculate_hit_metrics(hot_nums, current_record['numbers'], 
                                    period, current_record['date'])
    env = identify_market_environment(current_record['numbers'])
    
    report = f"""
╔════════════════════════════════════════════════════════════════╗
║                  热码表现每日复盘报告                          ║
╚════════════════════════════════════════════════════════════════╝

【期号信息】
  期号：{period}
  日期：{metrics.date}
  开奖号码：{', '.join(map(str, current_record['numbers']))}

【热码配置】
  热码总数：{metrics.total_hot_nums}个
  热码号码：{sorted(hot_nums)}

【命中结果】
  命中个数：{metrics.hit_count}个 / {metrics.total_hot_nums}个热码
  命中号码：{metrics.hit_numbers}
  未命中：{metrics.missed_numbers}

【性能指标】
  命中率 (Hit Rate)：{metrics.hit_rate:.1%}
  覆盖率 (Coverage)：{metrics.coverage_rate:.1%}
  精准度 (Precision)：{metrics.precision:.1%}
  召回率 (Recall)：{metrics.recall:.1%}
  F1分数 (F1 Score)：{metrics.f1_score:.4f}

【市场环境】
  环境类型：{env.environment_type}
  聚焦度：{env.focus_degree:.1%}
  散点度：{env.scatter_degree:.1%}

【评价等级】
"""
    
    if metrics.f1_score >= 0.40:
        report += "  ⭐⭐⭐⭐⭐ 极强 (F1 >= 0.40)\n"
    elif metrics.f1_score >= 0.30:
        report += "  ⭐⭐⭐⭐ 强 (0.30 <= F1 < 0.40)\n"
    elif metrics.f1_score >= 0.20:
        report += "  ⭐⭐⭐ 中等 (0.20 <= F1 < 0.30)\n"
    elif metrics.f1_score >= 0.10:
        report += "  ⭐⭐ 弱 (0.10 <= F1 < 0.20)\n"
    else:
        report += "  ⭐ 极弱 (F1 < 0.10)\n"
    
    return report


def export_analysis_to_json(analysis_result: Dict, filename: str = None) -> str:
    """
    导出分析结果为JSON
    
    Args:
        analysis_result: 分析结果字典
        filename: 输出文件名（若为None则生成默认名）
    
    Returns:
        输出文件路径
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    if filename is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hotcode_analysis_{timestamp}.json"
    
    filepath = os.path.join(CACHE_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(analysis_result, f, ensure_ascii=False, indent=2)
    
    return filepath


# ═══════════════════════════════════════════════════════════════
# 主函数 - 完整工作流
# ═══════════════════════════════════════════════════════════════

def main():
    print("\n" + "="*70)
    print("  快乐8 热码→命中率关联分析系统 v1.0")
    print("="*70 + "\n")
    
    # 加载数据
    history = load_history()
    if not history:
        print("[错误] 未能加载历史数据")
        return
    
    print(f"✅ 已加载 {len(history)} 期历史数据\n")
    
    # 执行批量分析
    print("执行热码关联分析（最近30期）...")
    analysis = batch_analyze_hotcode_hits(history, lookback_periods=30)
    
    # 输出统计结果
    print("\n" + "="*70)
    print("【分析结果汇总】")
    print("="*70)
    print(f"分析期数：{analysis['total_periods']}期")
    print(f"平均热码数：{analysis['avg_hot_count']}个")
    print(f"平均命中率：{analysis['avg_hit_rate']:.1%}")
    print(f"平均覆盖率：{analysis['avg_coverage_rate']:.1%}")
    print(f"平均精准度：{analysis['avg_precision']:.1%}")
    print(f"平均F1分数：{analysis['avg_f1_score']:.4f}")
    print(f"F1分数标准差：{analysis['std_f1_score']:.4f}")
    print(f"F1分数范围：{analysis['min_f1_score']:.4f} ~ {analysis['max_f1_score']:.4f}")
    print()
    print(f"最佳表现期：{analysis['best_period']} (F1={analysis['best_f1']:.4f})")
    print(f"最差表现期：{analysis['worst_period']} (F1={analysis['worst_f1']:.4f})")
    print("="*70 + "\n")
    
    # 生成最新期的详细报告
    if history:
        latest_period = history[0]['period']
        print(generate_daily_hotcode_report(latest_period))
    
    # 导出JSON
    json_file = export_analysis_to_json(analysis)
    print(f"\n✅ 分析结果已导出: {json_file}")
    
    return analysis


if __name__ == '__main__':
    main()
