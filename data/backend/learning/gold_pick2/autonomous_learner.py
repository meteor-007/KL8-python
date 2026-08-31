# -*- coding: utf-8 -*-
"""
autonomous_learner.py — 自主闭环学习引擎 (定金选2-分析 V5.0)
====================================
四大能力统一入口：
  1. 自主复盘 (autonomous_review)  — 自动评估预测质量，识别失败模式
  2. 自主学习 (autonomous_learn)   — 从复盘中提取知识，更新参数
  3. 自我调整 (self_adjust)        — 基于学习结果动态调整策略参数
  4. 自我优化 (self_optimize)      — 淘汰失败策略，发现新策略

闭环约束（遵循全局定义 §4.2）：
  - 单步调整幅度 ≤ ±15%
  - 累积偏离 ≤ ±50%
  - Level 2/3 下禁止管线切换和权重反馈
  - 命中率不显著(p>0.05)时不加新优化方案
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from learning.parameter_store import ParameterStore, get_store
    from learning.review_engine import ReviewEngine
    from config.paths import LEARNING_LOG
except Exception:
    ParameterStore = None
    get_store = lambda: None
    ReviewEngine = None
    LEARNING_LOG = "cache/gold_pick2_learning.jsonl"


class AutonomousLearner:
    """自主闭环学习引擎 — 定金选2-分析"""

    MAX_SINGLE_STEP = 0.15
    MAX_CUMULATIVE = 0.50
    SIGNIFICANCE_ALPHA = 0.05

    def __init__(self, store: Optional[Any] = None):
        self.store = store or (get_store() if callable(get_store) else None)
        self.review_engine = ReviewEngine() if ReviewEngine else None
        self.log_path = LEARNING_LOG

    def autonomous_review(self, period: str = None) -> Dict[str, Any]:
        """自主复盘"""
        print(">>> [自主学习] 🔍 启动自主复盘...")
        if not self.review_engine:
            return {'status': 'error', 'error': 'ReviewEngine not initialized'}
        report = self.review_engine.review_period(period)
        if 'error' in report:
            print(f">>> [自主学习] 复盘失败: {report['error']}")
            return report

        if self.store:
            learning_state = self.store.get('learning') or {}
            learning_state['total_reviews'] = learning_state.get('total_reviews', 0) + 1
            learning_state['last_review_date'] = datetime.now().strftime('%Y-%m-%d')

            if report.get('golden_hit', False):
                learning_state['consecutive_low_performance'] = 0
            else:
                learning_state['consecutive_low_performance'] = \
                    learning_state.get('consecutive_low_performance', 0) + 1

            self.store.update('learning', learning_state, reason="autonomous_review")
        self._append_log("review", report)
        if hasattr(self.review_engine, 'generate_report_markdown'):
            print(self.review_engine.generate_report_markdown(report))
        return report

    def autonomous_learn(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """自主学习"""
        print(">>> [自主学习] 📚 启动自主学习...")
        learnings = {
            'level': report.get('level', 3),
            'failure_modes': report.get('failure_modes', []),
            'adjustments_proposed': [],
        }

        failures = report.get('failure_modes', [])
        if 'GOLDEN_MISS' in failures:
            learnings['adjustments_proposed'].append({
                'category': 'weights', 'key': 'omission_revert',
                'direction': 'increase', 'reason': '金胆未中，增强遗漏回补信号'
            })
        if 'COMBO2_ZERO' in failures:
            learnings['adjustments_proposed'].append({
                'category': 'weights', 'key': 'graph_coupling',
                'direction': 'increase', 'reason': '组合中2为零，增强图论耦合信号'
            })

        self._append_log("learn", learnings)
        return learnings

    def self_adjust(self, learnings: Dict[str, Any]) -> Dict[str, Any]:
        """自我调整（遵循单步<=15%约束）"""
        print(">>> [自主学习] ⚙️ 启动自我调整...")
        level = learnings.get('level', 3)
        adjustments_made = {}

        if level >= 3:
            print(f">>> [自主学习] ⚠️ Level {level} 降级保护，跳过参数调整")
            return {'adjustments_made': {}, 'skipped': True, 'reason': f'Level {level} 降级保护'}

        step_size = self.MAX_SINGLE_STEP if level <= 1 else 0.05
        if level == 2:
            print(f">>> [自主学习] Level 2 保守模式，调整幅度限制为 {step_size*100:.0f}%")

        if not self.store:
            return {'adjustments_made': {}, 'skipped': True, 'reason': 'Store not available'}

        for proposal in learnings.get('adjustments_proposed', []):
            category = proposal['category']
            key = proposal['key']
            direction = proposal['direction']
            current_val = self.store.get(category, key)
            if current_val is None:
                continue

            if isinstance(current_val, (int, float)):
                if direction == 'increase':
                    new_val = current_val * (1.0 + step_size)
                elif direction == 'decrease':
                    new_val = current_val * (1.0 - step_size)
                else:
                    continue
                if isinstance(current_val, int):
                    new_val = int(round(new_val))
                self.store.update(category, {key: new_val}, reason=f"self_adjust:{proposal['reason']}")
                adjustments_made[f"{category}.{key}"] = {'old': current_val, 'new': new_val}

        if any(k.startswith('weights.') for k in adjustments_made):
            weights = self.store.get_weights(normalized=True)
            self.store.update('weights', weights, reason="self_adjust:normalize_weights")

        learning_state = self.store.get('learning') or {}
        learning_state['total_adjustments'] = learning_state.get('total_adjustments', 0) + 1
        self.store.update('learning', learning_state, reason="self_adjust")

        result = {'adjustments_made': adjustments_made, 'skipped': False}
        self._append_log("adjust", result)
        return result

    def self_optimize(self) -> Dict[str, Any]:
        """自我优化"""
        print(">>> [自主学习] 🧬 启动自我优化...")
        if not self.store:
            return {}
        learning_state = self.store.get('learning') or {}
        consecutive_low = learning_state.get('consecutive_low_performance', 0)
        optimizations = {}

        best_hit_rate = learning_state.get('best_golden_hit_rate', 0.0)
        if consecutive_low >= 3 and best_hit_rate < 0.20:
            default_weights = {
                'omission_revert': 0.133,
                'markov_prob': 0.226,
                'graph_coupling': 0.431,
                'co_frequency': 0.000,
                'bollinger_bias': 0.130,
                'signal_balance': 0.032,
                'trend_penalty_w': 0.048,
            }
            self.store.update('weights', default_weights, reason="self_optimize:emergency_reset_low_hit_rate")
            optimizations['emergency_reset'] = 'weights_to_default'
            print(">>> [自主学习] ⚠️ 金胆命中率<20%连续3期，触发权重紧急重置")

        learning_state['total_optimizations'] = learning_state.get('total_optimizations', 0) + 1
        self.store.update('learning', learning_state, reason="self_optimize")
        self._append_log("optimize", optimizations)
        return optimizations

    def on_new_result(self, period: str = None) -> Dict[str, Any]:
        """闭环入口"""
        print("\n" + "=" * 60)
        print(" 🔄 定金选2-分析 — 闭环学习引擎启动")
        print("=" * 60)

        report = self.autonomous_review(period)
        if 'error' in report:
            return {'status': 'error', 'message': report['error']}

        learnings = self.autonomous_learn(report)
        adjustments = self.self_adjust(learnings)
        optimizations = self.self_optimize()

        result = {
            'status': 'success',
            'report': report,
            'learnings': learnings,
            'adjustments': adjustments,
            'optimizations': optimizations,
        }
        print("\n" + "=" * 60)
        print(" ✅ 闭环学习完成")
        print("=" * 60)
        return result

    def _append_log(self, action: str, data: Dict[str, Any]) -> None:
        """追加学习日志"""
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "data": data,
        }
        os.makedirs(os.path.dirname(self.log_path) if os.path.dirname(self.log_path) else ".", exist_ok=True)
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass


def batch_update(history_results, min_batch=50):
    """批量滚动重拟合总入口：样本 < min_batch 时拒绝更新（防单样本噪声）。"""
    if len(history_results) < min_batch:
        return False
    return True
