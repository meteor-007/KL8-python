# -*- coding: utf-8 -*-
"""
自主闭环学习引擎 (Autonomous Learner)
======================================

四大核心能力:
  1. 自主复盘: 开奖后自动对比预测与实际, 逐号码溯源评分路径
  2. 自主学习: 基于复盘结果, 更新贝叶斯先验/马尔可夫转移/Loss权重
  3. 自我调整: 根据环境漂移检测, 动态切换权重方案和策略模式
  4. 自我优化: 用Walk-Forward验证评估权重变更效果, 仅采纳有正收益的变更

闭环流程:
  预测 -> 记录 -> 开奖 -> 复盘 -> 学习 -> 调整 -> 验证 -> 采纳/回滚 -> 下次预测

使用方式:
    from learning.autonomous_learner import AutonomousLearner
    
    learner = AutonomousLearner()
    
    # 每次预测前调用: 获取当前最优权重和参数
    state = learner.get_current_state()
    
    # 每次开奖后调用: 触发闭环学习
    learner.on_new_result(period='2026133', actual_numbers=[5,12,...])
"""
import os
import sys
import json
import math
import time
import copy
import logging
import collections
import datetime
import numpy as np
from typing import Dict, List, Tuple, Optional, Any

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()

# P1-11: Lift 阈值统一收敛到 learning_gate 单一口径 (默认1.0), 不再硬编码 1.1
try:
    from core.learning_gate import DEFAULT_LIFT_THRESHOLD
except Exception:
    DEFAULT_LIFT_THRESHOLD = 1.0


LEARNER_STATE_FILE = os.path.join(_PROJ, 'cache', 'learner_state.json')
LEARNER_LOG_FILE = os.path.join(_PROJ, 'logs', 'learner.log')

os.makedirs(os.path.join(_PROJ, 'cache'), exist_ok=True)
os.makedirs(os.path.join(_PROJ, 'logs'), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LEARNER_LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger("AutonomousLearner")


class AutonomousLearner:
    """
    自主闭环学习引擎
    
    维护的学习状态:
      - pentagon_weights: 三维融合权重 (EF/RW/FO) — v4.0: MK/EO已移除
      - markov_params: 马尔可夫参数 (lookback, prior_strength, 1阶/3阶融合比)
      - bayesian_params: 贝叶斯参数 (alpha_0, beta_0, decay_factor)
      - mc_params: 蒙特卡洛参数 (sampling weights)
      - strategy_mode: 当前策略模式 (aggressive/balanced/conservative)
      - environment_state: 环境状态 (type, confidence, volatility)
      - number_biases: 号码级偏差校准 (Platt scaling)
      - loss_history: 各算法Loss历史
      - drift_alerts: 环境漂移告警
    """
    
    def __init__(self):
        self._state = self._load_state()
        self._ensure_defaults()
        # 状态文件过大时自动瘦身 (prediction_scores 等大字段会随复盘累积)
        try:
            if os.path.exists(LEARNER_STATE_FILE) and \
                    os.path.getsize(LEARNER_STATE_FILE) > 300 * 1024:
                self.compact_state()
        except Exception:
            pass
    
    # ──────────────────────────────────────────────
    #  状态管理
    # ──────────────────────────────────────────────
    
    def _load_state(self) -> dict:
        if os.path.exists(LEARNER_STATE_FILE):
            try:
                with open(LEARNER_STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                logger.warning("学习状态文件损坏, 重新初始化")
        return {}
    
    def _save_state(self):
        # 原子写: 先写临时文件再替换, 避免写入中断损坏状态文件
        tmp = LEARNER_STATE_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, LEARNER_STATE_FILE)
    
    def _ensure_defaults(self):
        """确保所有必要字段有默认值"""
        defaults = {
            'pentagon_weights': {'EF': 0.40, 'RW': 0.30, 'FO': 0.30},
            'markov_params': {'lookback': 3, 'prior_strength': 1.0, 'fusion_ratio': 0.6},
            'bayesian_params': {'alpha_0': 5.0, 'beta_0': 15.0, 'decay_factor': 0.7},
            'mc_params': {'zone_w': 0.3, 'tail_w': 0.2, 'omit_w': 0.3, 'uniform_w': 0.2},
            'strategy_mode': 'balanced',
            'environment_state': {'type': 'balanced', 'confidence': 0.5, 'volatility': 0.15},
            'number_biases': {str(n): 0.0 for n in range(1, 81)},
            'number_bias_reviews': 0,
            'platt_a': 1.0,
            'platt_b': 0.0,
            'loss_history': [],
            'review_history': [],
            'drift_alerts': [],
            'adaptation_log': [],
            'pending_predictions': [],
            'last_review_period': None,
            'total_reviews': 0,
            'total_adaptations': 0,
            'successful_adaptations': 0,
            'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': None,
        }
        for key, val in defaults.items():
            if key not in self._state:
                self._state[key] = val
        self._save_state()

    def _number_bias_config(self) -> dict:
        """号码偏差校准配置 (衰减回先验 + 钳位 + 置信门槛)"""
        try:
            from config import get_config
            return get_config().section('number_bias') or {
                'decay': 0.9, 'clamp': 0.5, 'max_step': 0.02, 'min_reviews': 30}
        except Exception:
            return {'decay': 0.9, 'clamp': 0.5, 'max_step': 0.02, 'min_reviews': 30}

    def compact_state(self, retain_full: int = 40, max_bytes: int = 300 * 1024) -> bool:
        """状态瘦身/归档: 控制 learner_state.json 体积。

        - review_history[0] 是最新复盘; 最近 retain_full 条保留完整字段,
          更早的仅保留摘要(丢弃 prediction_scores 等大字段), 幂等不重复写。
        - adaptation_log / drift_alerts / pending_predictions 截断。
        返回是否发生截断。
        """
        changed = False
        reviews = self._state.get('review_history', [])
        if len(reviews) > retain_full:
            full = reviews[:retain_full]
            old = reviews[retain_full:]
            # 幂等: 仅当旧段仍有未压缩记录时才处理
            if any(not r.get('compacted') for r in old):
                compact = []
                for r in old:
                    entry = {
                        'period': r.get('period'),
                        'predicted_env': r.get('predicted_env'),
                        'hit_stats': r.get('hit_stats'),
                        'timestamp': r.get('timestamp'),
                        'compacted': True,
                    }
                    compact.append(entry)
                self._state['review_history'] = full + compact
                changed = True

        for key, cap in (('adaptation_log', 50),
                         ('drift_alerts', 20),
                         ('pending_predictions', 30)):
            lst = self._state.get(key, [])
            if len(lst) > cap:
                self._state[key] = lst[-cap:]
                changed = True

        if changed:
            self._save_state()
        return changed
    
    # ──────────────────────────────────────────────
    #  能力1: 自主复盘
    # ──────────────────────────────────────────────
    
    def record_prediction(self,
                          period: str,
                          prediction_scores: Dict[int, float],
                          top5: List[int],
                          top12: List[int],
                          top20: List[int],
                          algo_raw_scores: Dict[str, Dict[int, float]] = None,
                          environment: str = 'balanced',
                          volatility: float = 0.15):
        """
        在预测时记录完整快照 (用于复盘溯源)
        """
        record = {
            'period': period,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'prediction_scores': {str(n): round(s, 6) for n, s in prediction_scores.items()},
            'top5': top5,
            'top12': top12,
            'top20': top20,
            'environment': environment,
            'volatility': volatility,
            'pentagon_weights': copy.deepcopy(self._state['pentagon_weights']),
            'strategy_mode': self._state['strategy_mode'],
            'actual': None,
            'review': None,
        }
        
        if algo_raw_scores:
            record['algo_raw'] = {name: {str(n): round(s, 6) for n, s in scores.items()}
                                  for name, scores in algo_raw_scores.items()}
        
        pending = self._state.get('pending_predictions', [])
        pending.append(record)
        self._state['pending_predictions'] = pending
        self._save_state()
        if algo_raw_scores:
            try:
                from core.loss_weight_updater import LossBasedWeightUpdater
                updater = LossBasedWeightUpdater()
                loss_predictions = {
                    'energy': algo_raw_scores.get('EF', {}),
                    'bayesian': algo_raw_scores.get('RW', {}),
                    'feature': algo_raw_scores.get('FO', {})
                }
                updater.record_predictions(period, loss_predictions)
            except Exception as le:
                logger.warning(f"[记录] 同步記錄至LossWeightUpdater異常: {le}")
        logger.info(f"[记录] 期号{period}预测已记录, Top5={top5}")
    
    def review(self, period: str, actual_numbers: List[int]) -> dict:
        """
        自主复盘: 对比预测与实际, 逐号码溯源
        """
        actual_set = set(actual_numbers)
        
        pending = self._state.get('pending_predictions', [])
        target_record = None
        for record in pending:
            if record['period'] == period:
                target_record = record
                break
        
        if target_record is None:
            # 幂等：同一期已被复盘并从 pending 移除时，复用 review_history，避免二次触发误报
            for past in self._state.get('review_history', []):
                if str(past.get('period')) == str(period):
                    logger.info(f"[复盘] 期号{period}已复盘过，复用历史结果 (幂等)")
                    return past
            logger.warning(f"[复盘] 未找到期号{period}的预测记录")
            return {'status': 'NO_PREDICTION', 'period': period}
        
        # 命中统计
        top5_hits = len(set(target_record['top5']) & actual_set)
        top12_hits = len(set(target_record['top12']) & actual_set)
        top20_hits = len(set(target_record['top20']) & actual_set)
        
        top5_rate = top5_hits / 5
        top12_rate = top12_hits / 12
        top20_rate = top20_hits / 20
        
        baseline = 20 / 80
        top5_lift = top5_rate / baseline
        top12_lift = top12_rate / baseline
        top20_lift = top20_rate / baseline
        
        # 逐号码溯源
        hit_analysis = []
        miss_analysis = []
        
        pred_scores = target_record.get('prediction_scores', {})
        
        for n in sorted(actual_set):
            score = pred_scores.get(str(n), 0)
            sorted_keys = sorted(pred_scores.keys(), key=lambda x: -pred_scores[x])
            rank = sorted_keys.index(str(n)) + 1 if str(n) in sorted_keys else 81
            if n in target_record['top20']:
                hit_analysis.append({
                    'number': n, 'score': round(score, 4), 'rank': rank,
                    'in_top5': n in target_record['top5'],
                    'in_top12': n in target_record['top12'],
                })
            else:
                miss_analysis.append({
                    'number': n, 'score': round(score, 4), 'rank': rank,
                    'gap_to_top20': rank - 20 if rank <= 30 else '>30',
                })
        
        # 各维度贡献分析
        algo_contribution = {}
        algo_raw = target_record.get('algo_raw', {})
        for algo_name, scores in algo_raw.items():
            hit_scores = [scores.get(str(n), 0) for n in actual_set if str(n) in scores]
            miss_scores = [scores.get(str(n), 0) for n in range(1, 81) if n not in actual_set and str(n) in scores]
            avg_hit = float(np.mean(hit_scores)) if hit_scores else 0
            avg_miss = float(np.mean(miss_scores)) if miss_scores else 0
            discriminability = avg_hit - avg_miss
            algo_contribution[algo_name] = {
                'avg_hit_score': round(avg_hit, 4),
                'avg_miss_score': round(avg_miss, 4),
                'discriminability': round(discriminability, 4),
                'contribution': 'POSITIVE' if discriminability > 0 else 'NEGATIVE',
            }
        
        # 组装复盘报告
        review_report = {
            'period': period,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'actual_numbers': sorted(actual_set),
            'hit_stats': {
                'top5_hits': top5_hits, 'top5_rate': round(top5_rate, 4), 'top5_lift': round(top5_lift, 4),
                'top12_hits': top12_hits, 'top12_rate': round(top12_rate, 4), 'top12_lift': round(top12_lift, 4),
                'top20_hits': top20_hits, 'top20_rate': round(top20_rate, 4), 'top20_lift': round(top20_lift, 4),
            },
            'hit_analysis': hit_analysis,
            'miss_analysis': miss_analysis[:10],
            'algo_contribution': algo_contribution,
            'prediction_scores': pred_scores,
            'predicted_env': target_record.get('environment', 'balanced'),
            'weights_used': target_record.get('pentagon_weights', {}),
        }
        
        # 更新记录
        target_record['actual'] = sorted(actual_set)
        target_record['review'] = review_report
        
        pending.remove(target_record)
        self._state['pending_predictions'] = pending
        
        history = self._state.get('review_history', [])
        history.insert(0, review_report)
        self._state['review_history'] = history[-100:]
        
        self._state['last_review_period'] = period
        self._state['total_reviews'] = self._state.get('total_reviews', 0) + 1
        
        self._save_state()
        self._persist_review_json(review_report)
        
        logger.info(f"[复盘] 期号{period}: Top5={top5_hits}/5(Lift={top5_lift:.2f}), "
                     f"Top12={top12_hits}/12(Lift={top12_lift:.2f}), "
                     f"Top20={top20_hits}/20(Lift={top20_lift:.2f})")
        
        for algo, contrib in sorted(algo_contribution.items(), key=lambda x: -x[1]['discriminability']):
            logger.info(f"  {algo:15s}: 区分度={contrib['discriminability']:+.4f} [{contrib['contribution']}]")
        
        return review_report

    def _persist_review_json(self, review_report: dict) -> None:
        """将复盘结果落盘到 reviews/review_<period>.json（脚本任务5.4要求）。"""
        period = str(review_report.get('period') or '').strip()
        if not period:
            return
        # 安全文件名: 期号仅允许数字, 杜绝路径穿越 (../ 等)
        period = ''.join(ch for ch in period if ch.isdigit())
        if not period:
            return
        reviews_dir = os.path.join(_PROJ, 'reviews')
        os.makedirs(reviews_dir, exist_ok=True)
        out_path = os.path.join(reviews_dir, f'review_{period}.json')
        learning_status = 'ACTIVE'
        gate_info = {'wf_lift': None, 'threshold': DEFAULT_LIFT_THRESHOLD}
        try:
            from core.learning_gate import gate_status, is_learning_enabled
            learning_status = 'ACTIVE' if is_learning_enabled() else 'FROZEN'
            gs = gate_status() or {}
            gate_info = {
                'wf_lift': gs.get('last_wf_lift'),
                'threshold': gs.get('lift_threshold', DEFAULT_LIFT_THRESHOLD),
            }
        except Exception:
            pass
        payload = {
            'period': period,
            'timestamp': review_report.get('timestamp'),
            'actual_numbers': review_report.get('actual_numbers', []),
            'hit_stats': review_report.get('hit_stats', {}),
            'algo_contribution': {
                k: (v.get('contribution') if isinstance(v, dict) else v)
                for k, v in (review_report.get('algo_contribution') or {}).items()
            },
            'weights_used': review_report.get('weights_used') or self._state.get('pentagon_weights', {}),
            'optimization_decision': 'N/A',
            'learning_status': learning_status,
            'gate': gate_info,
        }
        try:
            with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
                f.write('\n')
            logger.info(f"[复盘] 已落盘 {out_path}")
        except Exception as e:
            logger.warning(f"[复盘] 落盘 reviews/ 失败: {e}")
    
    # ──────────────────────────────────────────────
    #  能力2: 自主学习
    # ──────────────────────────────────────────────
    
    def learn(self, review_report: dict, history: list) -> dict:
        """
        基于复盘报告, 自主更新学习参数
        """
        if review_report.get('status') == 'NO_PREDICTION':
            return {'status': 'SKIPPED'}

        try:
            from core.learning_gate import is_learning_enabled, learning_frozen_message
            if not is_learning_enabled():
                logger.info(f"[学习] {learning_frozen_message()}")
                return {'status': 'FROZEN', 'message': learning_frozen_message()}
        except Exception:
            pass
        
        period = review_report['period']
        logger.info(f"[学习] 期号{period}开始自主学习...")
        
        changes = {}
        
        # 学习1: Loss权重更新
        algo_contribution = review_report.get('algo_contribution', {})
        if algo_contribution:
            try:
                from core.loss_weight_updater import LossBasedWeightUpdater
                
                updater = LossBasedWeightUpdater()
                new_weights = updater.update_with_actual(period, review_report['actual_numbers'])
                
                if new_weights:
                    # v4.0: MK/EO已移除, 仅映射EF/RW/FO三维
                    # LossBasedWeightUpdater 键: energy/bayesian/feature
                    weight_map = {
                        'energy': 'EF', 'bayesian': 'RW', 'feature': 'FO',
                        'pentagon': 'EF',
                        'omission_decay': 'RW', 'frequency': 'FO',
                        'tail_compensation': 'RW', 'zone_deficit': 'RW',
                        'momentum': 'FO',
                        'EF': 'EF', 'RW': 'RW', 'FO': 'FO',
                    }
                    updated = False
                    new_pentagon = copy.deepcopy(self._state['pentagon_weights'])
                    baselines = {'EF': 0.40, 'RW': 0.30, 'FO': 0.30}
                    for algo_name, w in new_weights.items():
                        dim = weight_map.get(algo_name)
                        if dim and dim in new_pentagon:
                            old_w = new_pentagon[dim]
                            
                            # 计算目标权重
                            target_w = old_w * 0.8 + w * 0.2
                            
                            # 1. 单步幅度不超过 ±15% (神父防线红线三)
                            max_step = old_w * 0.15
                            target_w = max(old_w - max_step, min(old_w + max_step, target_w))
                            
                            # 2. 累积偏离基线不超过 ±50% (神父防线红线三)
                            base_w = baselines.get(dim, old_w)
                            target_w = max(base_w * 0.50, min(base_w * 1.50, target_w))
                            
                            new_pentagon[dim] = round(target_w, 4)
                            updated = True
                    
                    if updated:
                        total = sum(new_pentagon.values())
                        if total > 0:
                            new_pentagon = {k: round(v / total, 4) for k, v in new_pentagon.items()}
                        changes['pentagon_weights'] = {
                            'old': copy.deepcopy(self._state['pentagon_weights']),
                            'new': new_pentagon,
                        }
                        self._state['pentagon_weights'] = new_pentagon
                
            except Exception as e:
                logger.warning(f"Loss权重学习异常: {e}")
        
        # 学习2: 号码偏差校准 (Platt Scaling) — 衰减回先验 + 置信门槛 + 单期限幅
        self._state['number_bias_reviews'] = self._state.get('number_bias_reviews', 0) + 1
        nb_cfg = self._number_bias_config()
        if self._state['number_bias_reviews'] >= nb_cfg['min_reviews']:
            _decay = float(nb_cfg.get('decay', 0.9))
            _clamp = float(nb_cfg.get('clamp', 0.5))
            _max_step = float(nb_cfg.get('max_step', 0.02))
            actual_set = set(review_report['actual_numbers'])
            pred_scores = review_report.get('prediction_scores', {})
            if pred_scores:
                sorted_keys = sorted(pred_scores.keys(), key=lambda x: -pred_scores[x])
                for n in range(1, 81):
                    n_str = str(n)
                    current_bias = self._state['number_biases'].get(n_str, 0.0)

                    if n in actual_set:
                        rank = sorted_keys.index(n_str) + 1 if n_str in sorted_keys else 81
                        if rank > 20:
                            delta = 0.02
                        else:
                            delta = -0.005
                    else:
                        n_str_rank = sorted_keys.index(n_str) + 1 if n_str in sorted_keys else 81
                        if n_str_rank <= 20:
                            delta = -0.015
                        else:
                            delta = 0.0

                    # 指数滑动(EMA)更新: 旧偏差按 decay 衰减, 单步向 delta 靠拢 (并非严格回归到0)
                    target = current_bias * _decay + delta * (1 - _decay)
                    # 单期限幅: 防止单期噪声把偏差推太远
                    step_capped = max(current_bias - _max_step,
                                      min(current_bias + _max_step, target))
                    new_bias = max(-_clamp, min(_clamp, step_capped))
                    self._state['number_biases'][n_str] = round(new_bias, 4)

                changes['number_biases_updated'] = True
        
        # 学习3: 贝叶斯先验微调
        top5_rate = review_report['hit_stats']['top5_rate']
        if top5_rate > 0.4:
            self._state['bayesian_params']['alpha_0'] = min(10.0,
                self._state['bayesian_params']['alpha_0'] + 0.1)
        elif top5_rate < 0.2:
            self._state['bayesian_params']['alpha_0'] = max(2.0,
                self._state['bayesian_params']['alpha_0'] - 0.1)
        changes['bayesian_params'] = self._state['bayesian_params']
        
        # 学习4: 环境记忆
        env_memory = self._state.get('env_memory', {})
        predicted_env = review_report.get('predicted_env', 'balanced')
        if predicted_env not in env_memory:
            env_memory[predicted_env] = {'reviews': 0, 'avg_top5_lift': 0, 'avg_top12_lift': 0}
        
        mem = env_memory[predicted_env]
        mem['reviews'] += 1
        n = mem['reviews']
        mem['avg_top5_lift'] = round(mem['avg_top5_lift'] * (n-1)/n + review_report['hit_stats']['top5_lift'] / n, 4)
        mem['avg_top12_lift'] = round(mem['avg_top12_lift'] * (n-1)/n + review_report['hit_stats']['top12_lift'] / n, 4)
        self._state['env_memory'] = env_memory
        changes['env_memory_updated'] = True
        
        self._save_state()
        logger.info(f"[学习] 期号{period}学习完成, 变更项: {list(changes.keys())}")
        
        return changes
    
    # ──────────────────────────────────────────────
    #  能力3: 自我调整
    # ──────────────────────────────────────────────
    
    def adapt(self, history: list) -> dict:
        """
        自我调整: 检测环境漂移, 动态切换策略
        """
        try:
            from core.learning_gate import is_learning_enabled, learning_frozen_message
            if not is_learning_enabled():
                logger.info(f"[调整] {learning_frozen_message()}")
                return {'status': 'FROZEN', 'message': learning_frozen_message()}
        except Exception:
            pass

        logger.info("[调整] 开始自我调整检测...")
        
        adjustments = {}
        review_history = self._state.get('review_history', [])
        
        if len(review_history) < 3:
            logger.info("  复盘历史不足3期, 跳过调整")
            return {'status': 'INSUFFICIENT_DATA'}
        
        # 调整1: 连续低命中/高命中 -> 模式切换
        recent_3_top5_rates = [r['hit_stats']['top5_rate'] for r in review_history[:3]]
        
        old_mode = self._state['strategy_mode']
        
        if all(r < 0.2 for r in recent_3_top5_rates):
            new_mode = 'conservative'
            self._state['strategy_mode'] = new_mode
            self._state['pentagon_weights']['RW'] = min(0.40, self._state['pentagon_weights'].get('RW', 0.30) + 0.05)
            self._state['pentagon_weights']['EF'] = max(0.20, self._state['pentagon_weights'].get('EF', 0.40) - 0.05)
            logger.info(f"  [调整] 连续低命中->保守模式, RW+ EF-")
            
        elif all(r > 0.4 for r in recent_3_top5_rates):
            new_mode = 'aggressive'
            self._state['strategy_mode'] = new_mode
            # v4.0: MK已移除, 激进模式加EF
            self._state['pentagon_weights']['EF'] = min(0.50, self._state['pentagon_weights'].get('EF', 0.40) + 0.05)
            self._state['pentagon_weights']['FO'] = min(0.40, self._state['pentagon_weights'].get('FO', 0.30) + 0.05)
            logger.info(f"  [调整] 连续高命中->激进模式, MK+(上限0.35) EF+")
            
        else:
            new_mode = 'balanced'
            self._state['strategy_mode'] = new_mode
        
        if new_mode != old_mode:
            adjustments['strategy_mode'] = {'old': old_mode, 'new': new_mode}
        
        # 调整2: 环境漂移检测
        if len(history) >= 20:
            current_env = self._detect_environment(history)
            old_env = self._state.get('environment_state', {}).get('type', 'balanced')
            
            if current_env['type'] != old_env:
                drift_alert = {
                    'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'old_env': old_env,
                    'new_env': current_env['type'],
                    'confidence': current_env['confidence'],
                }
                alerts = self._state.get('drift_alerts', [])
                alerts.insert(0, drift_alert)
                self._state['drift_alerts'] = alerts[-20:]
                adjustments['environment_drift'] = drift_alert
                logger.info(f"  [漂移] 环境 {old_env}->{current_env['type']} (置信度={current_env['confidence']:.2f})")
            
            self._state['environment_state'] = current_env
        
        # 调整3: 归一化五维权重
        total_w = sum(self._state['pentagon_weights'].values())
        if total_w > 0:
            self._state['pentagon_weights'] = {
                k: round(v / total_w, 4) for k, v in self._state['pentagon_weights'].items()
            }
        
        # 记录调整历史
        if adjustments:
            adaptation_record = {
                'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'adjustments': adjustments,
                'resulting_weights': copy.deepcopy(self._state['pentagon_weights']),
                'strategy_mode': self._state['strategy_mode'],
            }
            adapt_log = self._state.get('adaptation_log', [])
            adapt_log.insert(0, adaptation_record)
            self._state['adaptation_log'] = adapt_log[-50:]
            self._state['total_adaptations'] = self._state.get('total_adaptations', 0) + 1
        
        self._state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self._save_state()
        
        logger.info(f"[调整] 完成, 策略模式={self._state['strategy_mode']}, "
                     f"权重={self._state['pentagon_weights']}")
        
        return adjustments
    
    def _detect_environment(self, history: list) -> dict:
        """环境漂移检测"""
        if len(history) < 10:
            return {'type': 'balanced', 'confidence': 0.5, 'volatility': 0.15}
        
        recent_10 = history[:10]
        freq = collections.Counter()
        for h in recent_10:
            for n in h['numbers']:
                freq[n] += 1
        
        hot_count = sum(1 for n in range(1, 81) if freq.get(n, 0) >= 3)
        hot_ratio = hot_count / 80
        
        cold_count = sum(1 for n in range(1, 81) if freq.get(n, 0) == 0)
        cold_ratio = cold_count / 80
        
        counts_per_period = [len(h['numbers']) for h in recent_10]
        volatility = round(float(np.std(counts_per_period) / max(np.mean(counts_per_period), 1)), 4)
        
        try:
            from config import get_config
            cfg = get_config()
            hot_threshold = cfg.get('environment.hot_ratio_threshold', 0.55)
            cold_threshold = cfg.get('environment.cold_ratio_threshold', 0.35)
        except Exception:
            hot_threshold = 0.55
            cold_threshold = 0.35
        
        if hot_ratio > hot_threshold:
            env_type = 'hot_burst'
            confidence = min(1.0, hot_ratio / hot_threshold)
        elif cold_ratio > cold_threshold:
            env_type = 'cold_rebound'
            confidence = min(1.0, cold_ratio / cold_threshold)
        elif volatility > 0.25:
            env_type = 'chaotic'
            confidence = min(1.0, volatility / 0.25)
        elif volatility < 0.10:
            env_type = 'trend_accel'
            confidence = min(1.0, 0.10 / max(volatility, 0.01))
        else:
            env_type = 'balanced'
            confidence = 0.7
        
        return {'type': env_type, 'confidence': round(confidence, 2), 'volatility': volatility}
    
    # ──────────────────────────────────────────────
    #  能力4: 自我优化
    # ──────────────────────────────────────────────
    
    def optimize(self, history: list) -> dict:
        """
        自我优化: 用Walk-Forward验证评估当前参数效果
        """
        try:
            from core.learning_gate import is_learning_enabled, learning_frozen_message
            if not is_learning_enabled():
                logger.info(f"[优化] {learning_frozen_message()}")
                return {'status': 'FROZEN', 'message': learning_frozen_message()}
        except Exception:
            pass

        logger.info("[优化] 开始Walk-Forward验证...")
        
        if len(history) < 80:
            logger.info("  历史数据不足80期, 跳过优化验证")
            return {'status': 'INSUFFICIENT_DATA'}
        
        try:
            from core.walk_forward_validator import WalkForwardValidator
        except Exception:
            logger.warning("WalkForwardValidator 加载失败")
            return {'status': 'MODULE_UNAVAILABLE'}
        
        current_weights = copy.deepcopy(self._state['pentagon_weights'])
        baseline_weights = copy.deepcopy(
            self._state.get('previous_weights') or current_weights
        )
        
        def prediction_fn(train_data):
            """三维轻量预测: EF(热度) + RW(遗漏Sigmoid) + FO(近窗频率) — 与日报维度对齐"""
            scores = {}
            weights = self._state['pentagon_weights']
            window = train_data[:50] if train_data else []
            short = train_data[:15] if train_data else []

            freq_long = {n: 0 for n in range(1, 81)}
            freq_short = {n: 0 for n in range(1, 81)}
            for h in window:
                for n in h.get('numbers', []):
                    if 1 <= n <= 80:
                        freq_long[n] += 1
            for h in short:
                for n in h.get('numbers', []):
                    if 1 <= n <= 80:
                        freq_short[n] += 1
            max_long = max(freq_long.values()) or 1
            max_short = max(freq_short.values()) or 1

            for n in range(1, 81):
                gap = 0
                for h in window:
                    if n in h.get('numbers', []):
                        break
                    gap += 1
                rw_prob = 1.0 / (1.0 + math.exp(-0.3 * (gap - 8)))
                ef_score = freq_long[n] / max_long
                fo_score = freq_short[n] / max_short
                bias = self._state['number_biases'].get(str(n), 0.0)
                scores[n] = (
                    ef_score * weights.get('EF', 0.4)
                    + rw_prob * weights.get('RW', 0.3)
                    + fo_score * weights.get('FO', 0.3)
                    + bias * 0.05
                )
            return scores
        
        validator = WalkForwardValidator(train_window=50, val_window=10, step=10, min_history=80)
        results = validator.validate(history, prediction_fn, top_k=20)
        report = validator.report(results)
        
        last_wf = self._state.get('last_wf_report')
        if last_wf and last_wf.get('status') == 'OK':
            old_lift = last_wf.get('global_avg_lift', 0)
            new_lift = report.get('global_avg_lift', 0)
            
            improvement = new_lift - old_lift
            
            if improvement > 0.02:
                self._state['successful_adaptations'] = self._state.get('successful_adaptations', 0) + 1
                logger.info(f"  [优化] 参数有效! Lift {old_lift:.4f}->{new_lift:.4f} (+{improvement:.4f})")
                decision = 'ADOPTED'
                self._state['previous_weights'] = copy.deepcopy(current_weights)
                self._state['last_wf_report'] = report
            elif improvement < -0.02:
                logger.info(f"  [优化] 参数退步! Lift {old_lift:.4f}->{new_lift:.4f} ({improvement:.4f}), 回滚")
                self._state['pentagon_weights'] = copy.deepcopy(baseline_weights)
                # 回滚后基线仍是采纳过的权重；勿用被拒权重覆盖 previous / last_wf
                self._state['previous_weights'] = copy.deepcopy(baseline_weights)
                decision = 'ROLLED_BACK'
            else:
                logger.info(f"  [优化] 参数无显著变化, Lift {old_lift:.4f}->{new_lift:.4f}")
                decision = 'KEPT'
                self._state['previous_weights'] = copy.deepcopy(current_weights)
                self._state['last_wf_report'] = report
        else:
            decision = 'FIRST_RUN'
            self._state['previous_weights'] = copy.deepcopy(current_weights)
            self._state['last_wf_report'] = report
        
        self._save_state()
        
        optimization_report = {
            'decision': decision,
            'wf_report': {k: v for k, v in report.items() if k != 'per_fold_summary'},
            'current_weights': self._state['pentagon_weights'],
            'strategy_mode': self._state['strategy_mode'],
        }
        
        logger.info(f"[优化] 完成, 决策={decision}")
        return optimization_report
    
    # ──────────────────────────────────────────────
    #  一键闭环: on_new_result
    # ──────────────────────────────────────────────
    
    def on_new_result(self, period: str, actual_numbers: List[int], history: list = None) -> dict:
        """
        开奖后一键触发完整闭环:
          复盘 -> 学习 -> 调整 -> 优化
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"  自主闭环学习: 期号{period}")
        logger.info(f"{'='*60}")
        
        start_time = time.time()
        
        # Step 1: 自主复盘
        review_report = self.review(period, actual_numbers)

        # 样本外台账: 自动记录预测 vs 开奖 (只追加, 供长期 OOS 验证)
        try:
            # 仅在有实际预测(非 NO_PREDICTION)时记录, 避免无预测写入 0 命中污染台账
            if review_report.get('status') != 'NO_PREDICTION':
                from learning.paper_trading import record_result
                ps = review_report.get('prediction_scores', {})
                topk = [k for k, _ in sorted(ps.items(), key=lambda x: -x[1])][:20] if ps else []
                record_result(period, topk, actual_numbers,
                              predicted_env=review_report.get('predicted_env'))
        except Exception as e:
            logger.warning(f"样本外台账记录失败: {e}")
        
        # Step 2: 自主学习
        learn_changes = self.learn(review_report, history or [])
        
        # Step 3: 自我调整
        adapt_adjustments = {}
        if history:
            adapt_adjustments = self.adapt(history)
        
        # Step 4: 自我优化
        optimize_report = {}
        if history and len(history) >= 80:
            optimize_report = self.optimize(history)
        
        elapsed = time.time() - start_time
        
        loop_report = {
            'period': period,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'review_summary': {
                'top5_hits': review_report.get('hit_stats', {}).get('top5_hits', 0),
                'top5_lift': review_report.get('hit_stats', {}).get('top5_lift', 0),
                'top12_hits': review_report.get('hit_stats', {}).get('top12_hits', 0),
                'top12_lift': review_report.get('hit_stats', {}).get('top12_lift', 0),
            },
            'learning_changes': list(learn_changes.keys()) if isinstance(learn_changes, dict) else [],
            'adjustments': adapt_adjustments,
            'optimization_decision': optimize_report.get('decision', 'N/A'),
            'elapsed_seconds': round(elapsed, 2),
            'current_weights': self._state['pentagon_weights'],
            'strategy_mode': self._state['strategy_mode'],
            'total_reviews': self._state.get('total_reviews', 0),
            'total_adaptations': self._state.get('total_adaptations', 0),
            'successful_adaptations': self._state.get('successful_adaptations', 0),
        }
        
        logger.info(f"[闭环] 期号{period}完成, 耗时{elapsed:.2f}s, "
                     f"策略={self._state['strategy_mode']}")
        
        return loop_report
    
    # ──────────────────────────────────────────────
    #  获取当前状态
    # ──────────────────────────────────────────────
    
    def get_current_state(self) -> dict:
        """获取当前学习状态 (预测前调用)"""
        return {
            'pentagon_weights': self._state['pentagon_weights'],
            'number_biases': {int(k): v for k, v in self._state['number_biases'].items()},
            'strategy_mode': self._state['strategy_mode'],
            'environment_state': self._state['environment_state'],
            'bayesian_params': self._state['bayesian_params'],
            'markov_params': self._state['markov_params'],
            'mc_params': self._state['mc_params'],
            'recent_performance': self._get_recent_performance(),
        }
    
    def _get_recent_performance(self, lookback: int = 10) -> dict:
        """获取近期表现统计"""
        reviews = self._state.get('review_history', [])[:lookback]
        if not reviews:
            return {'avg_top5_lift': 0, 'avg_top12_lift': 0, 'n_periods': 0}
        
        top5_lifts = [r['hit_stats']['top5_lift'] for r in reviews]
        top12_lifts = [r['hit_stats']['top12_lift'] for r in reviews]
        
        return {
            'avg_top5_lift': round(float(np.mean(top5_lifts)), 4),
            'avg_top12_lift': round(float(np.mean(top12_lifts)), 4),
            'n_periods': len(reviews),
            'trend': 'IMPROVING' if len(top5_lifts) >= 3 and np.mean(top5_lifts[:3]) > np.mean(top5_lifts[-3:]) else 'STABLE',
        }
    
    # ──────────────────────────────────────────────
    #  诊断与报告
    # ──────────────────────────────────────────────
    
    def diagnose(self) -> dict:
        """生成学习引擎自诊断报告"""
        reviews = self._state.get('review_history', [])
        drifts = self._state.get('drift_alerts', [])
        
        recent_10 = reviews[:10]
        if recent_10:
            top5_trend = [r['hit_stats']['top5_rate'] for r in recent_10]
            top12_trend = [r['hit_stats']['top12_rate'] for r in recent_10]
        else:
            top5_trend = []
            top12_trend = []
        
        biases = self._state.get('number_biases', {})
        positive_biases = [n for n, b in biases.items() if b > 0.05]
        negative_biases = [n for n, b in biases.items() if b < -0.05]
        
        return {
            'total_reviews': self._state.get('total_reviews', 0),
            'total_adaptations': self._state.get('total_adaptations', 0),
            'successful_adaptations': self._state.get('successful_adaptations', 0),
            'success_rate': round(self._state.get('successful_adaptations', 0) / max(self._state.get('total_adaptations', 1), 1), 4),
            'current_weights': self._state['pentagon_weights'],
            'strategy_mode': self._state['strategy_mode'],
            'environment': self._state.get('environment_state', {}),
            'recent_top5_rates': [round(r, 4) for r in top5_trend],
            'recent_top12_rates': [round(r, 4) for r in top12_trend],
            'positive_bias_numbers': sorted(positive_biases, key=lambda n: -biases[n])[:10],
            'negative_bias_numbers': sorted(negative_biases, key=lambda n: biases[n])[:10],
            'drift_alerts_count': len(drifts),
            'recent_drifts': drifts[:3],
            'pending_predictions': len(self._state.get('pending_predictions', [])),
        }
    
    def print_diagnosis(self):
        """打印诊断报告"""
        diag = self.diagnose()
        print("\n" + "=" * 70)
        print("  自主学习引擎 诊断报告")
        print("=" * 70)
        print(f"  总复盘次数:     {diag['total_reviews']}")
        print(f"  总调整次数:     {diag['total_adaptations']}")
        print(f"  成功调整率:     {diag['success_rate']:.2%}")
        print(f"  当前策略模式:   {diag['strategy_mode']}")
        print(f"  当前环境:       {diag['environment'].get('type', 'N/A')} "
              f"(置信度={diag['environment'].get('confidence', 0):.2f})")
        print(f"  ────────────────────────────────")
        w = diag['current_weights']
        print(f"  三维权重: EF={w.get('EF', 0):.2f} "
              f"RW={w.get('RW', 0):.2f} "
              f"FO={w.get('FO', 0):.2f}")
        print(f"  近期Top5命中率: {diag['recent_top5_rates']}")
        print(f"  近期Top12命中率: {diag['recent_top12_rates']}")
        print(f"  正偏差号码(被低估): {diag['positive_bias_numbers']}")
        print(f"  负偏差号码(被高估): {diag['negative_bias_numbers']}")
        print(f"  环境漂移告警: {diag['drift_alerts_count']}次")
        print(f"  待复盘预测: {diag['pending_predictions']}条")
        print("=" * 70)


def quick_learn(period: str, actual_numbers: List[int], history: list = None) -> dict:
    """一键闭环学习"""
    learner = AutonomousLearner()
    return learner.on_new_result(period, actual_numbers, history)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='自主学习引擎')
    parser.add_argument('--diagnose', action='store_true', help='输出诊断报告')
    parser.add_argument('--review', type=str, help='复盘指定期号 (需--actual)')
    parser.add_argument('--actual', type=str, help='实际开奖号码 (逗号分隔)')
    args = parser.parse_args()
    
    learner = AutonomousLearner()
    
    if args.diagnose:
        learner.print_diagnosis()
    elif args.review and args.actual:
        actual = [int(x.strip()) for x in args.actual.split(',')]
        report = learner.on_new_result(args.review, actual)
        print(json.dumps({k: v for k, v in report.items()}, ensure_ascii=False, indent=2, default=str))
    else:
        learner.print_diagnosis()
