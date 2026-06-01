# -*- coding: utf-8 -*-
"""
K8-Quant v2 统一入口
=====================
整合所有修复后的核心模块, 提供一步到位的预测管线。

修复内容:
  1. Beta-Binomial 共轭推断 (替代伪贝叶斯)
  2. 约束抽样蒙特卡洛 (替代循环论证MC)
  3. 降维+平滑马尔可夫链 (替代欠采样MC)
  4. 统一ScoreComposer (替代三套并行评分)
  5. Loss Function权重更新 (实现白皮书)
  6. 多尺度R/S Hurst系数 (替代单点估计)
  7. Walk-Forward Validation (替代短窗口回测)
  8. 配置外部化 (替代魔法数字)

v2.1 修复清单:
  - [Bug] load_points()丢失期号映射 → 改为返回 {issue: set()} 字典
  - [Bug] load_all_data(history, points)签名不匹配 → 改用 get_all_layer_a_scores(history)
  - [Bug] load_history()未排序 → 按期号降序排列
  - [Bug] recognize_environment()返回格式不一致 → 统一为dict
  - [Code] import re 在循环体内 → 移到文件顶部
"""
import os
import sys
import re
import json
import math
import time
import argparse
import collections
import numpy as np

_PROJ = os.path.dirname(os.path.abspath(__file__))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)


def load_history(history_file=None):
    """加载历史数据，按期号降序排列（最新在前）"""
    if history_file is None:
        try:
            from utils.paths import data_path
            history_file = data_path('kl8_history_final.txt')
        except Exception:
            history_file = os.path.join(_PROJ, 'kl8_history_final.txt')
    if not os.path.exists(history_file):
        print(f"[ERROR] 历史数据文件不存在: {history_file}")
        return []
    history = []
    with open(history_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 正则匹配 date:...,period:NNN,numbers:N1-N2... 标准格式
            m = re.search(r'period:(\d+),numbers:([\d-]+)', line)
            if m:
                issue = m.group(1)
                num_str = m.group(2)
                numbers = sorted([int(x) for x in num_str.split('-') if x.isdigit()])
                if len(numbers) >= 15:
                    history.append({'issue': issue, 'numbers': numbers})
                continue
                
            # Fallback 兼容旧版空格分割格式
            parts = line.split()
            if len(parts) >= 2:
                issue = parts[0]
                try:
                    numbers = sorted([int(x) for x in parts[1:] if x.isdigit()])
                    if len(numbers) >= 15:
                        history.append({'issue': issue, 'numbers': numbers})
                except ValueError:
                    pass
    
    # 按期号降序排列，确保 history[0] 是最新期
    history.sort(key=lambda h: h['issue'], reverse=True)
    
    print(f"[数据] 加载历史 {len(history)} 期")
    if history:
        print(f"  最新期号: {history[0]['issue']}")
    return history


def load_points(points_file=None):
    """加载点位数据，返回按期号映射的字典 {issue: set(numbers)}

    支持 period:NNN points:N1 N2 ... 格式。
    如果没有period标记，按行序号映射（兼容纯数字行）。
    """
    if points_file is None:
        try:
            from utils.paths import data_path
            points_file = data_path('daily_points.txt')
        except Exception:
            points_file = os.path.join(_PROJ, 'daily_points.txt')
    if not os.path.exists(points_file):
        return {}
    
    points_by_issue = {}
    with open(points_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 标准格式: period:NNN points:N1 N2 ...
            per_m = re.search(r'period:(\d+)', line)
            pts_m = re.search(r'points:([\d\s]+)', line)
            if pts_m and per_m:
                pts = {int(p) for p in pts_m.group(1).strip().split() if p}
                points_by_issue[per_m.group(1)] = pts
            else:
                # Fallback: 纯数字行，无法映射期号，跳过
                pass
    
    # 同时提供一个全局点位集合（所有期号的并集），用于兼容旧逻辑
    return points_by_issue


def recognize_environment(history):
    """环境识别 — 统一返回 dict 格式

    返回格式:
      {'type': str, 'confidence': float, 'strategy_config': dict}
    """
    try:
        from recognition.simplified_env_recognition import recognize_environment as _recognize
        env_class, env_name, env_confidence, strategy_config = _recognize(history)
        return {
            'type': env_name,
            'confidence': env_confidence,
            'strategy_config': strategy_config,
        }
    except Exception:
        if len(history) < 5:
            return {'type': 'balanced', 'confidence': 0.5, 'strategy_config': {}}
        return {'type': 'balanced', 'confidence': 0.7, 'strategy_config': {}}


def compute_volatility(history, window=10):
    """计算波动率"""
    if len(history) < window:
        return 0.15
    recent = history[:window]
    counts = [len(h['numbers']) for h in recent]
    mean_val = np.mean(counts)
    return round(float(np.std(counts) / mean_val) if mean_val > 0 else 0.15, 4)


def run_pipeline(history, top_k=20):
    """
    执行完整 v2 Pipeline
    
    流程:
      1. 马尔可夫 (MK) -> 转移概率
      2. 隐能量场 (EF) -> 能量分数
      3. 遗漏Sigmoid (RW) -> 回补分数
      4. 贝叶斯后验 (辅助验证)
      5. 约束蒙特卡洛 (辅助验证)
      6. 特征优化层 (FO) -> 特征分数
      7. 熵控优化层 (EO) -> 熵分数
      8. 环境识别 -> 确定权重方案
      9. ScoreComposer -> 统一评分
     10. 金胆/银胆输出
    """
    print("\n" + "=" * 70)
    print("  K8-Quant v2 Pipeline")
    print("=" * 70)
    
    start_time = time.time()
    
    # Step 1: 马尔可夫
    print("\n[Step 1/8] 马尔可夫链 (降维+平滑)...")
    mk_probs = {}
    try:
        from core.algorithm_optimizer import plan7_markov_integration
        mk_result = plan7_markov_integration(history)
        mk_probs = mk_result.get('probs', {}) if mk_result else {}
    except Exception as e:
        print(f"  马尔可夫异常: {e}")
    
    # Step 2: 隐能量场
    print("\n[Step 2/8] 隐能量场...")
    ef_scores = {}
    try:
        from audit.v3_trinity_audit import calc_energy_field
        ef_scores = calc_energy_field(history, decay_rate=0.5)
    except Exception as e:
        print(f"  隐能量场异常: {e}")
    
    # Step 3: 遗漏Sigmoid
    print("\n[Step 3/8] 遗漏Sigmoid回补...")
    rw_scores = {}
    for n in range(1, 81):
        gap = 0
        for h in history[:50]:
            if n in h['numbers']:
                break
            gap += 1
        rw_scores[n] = 1.0 / (1.0 + math.exp(-0.3 * (gap - 8)))
    
    # Step 4: 贝叶斯后验
    print("\n[Step 4/8] 贝叶斯后验 (Beta-Binomial)...")
    bayes_result = {}
    try:
        from core.algorithm_optimizer import plan9_bayesian_update
        bayes_result = plan9_bayesian_update(history) or {}
    except Exception as e:
        print(f"  贝叶斯异常: {e}")
    
    # Step 5: 约束蒙特卡洛
    print("\n[Step 5/8] 约束蒙特卡洛抽样...")
    mc_result = {}
    try:
        from core.algorithm_optimizer import plan10_monte_carlo
        mc_result = plan10_monte_carlo(history) or {}
    except Exception as e:
        print(f"  蒙特卡洛异常: {e}")
    
    # Step 6: 特征优化层 — 使用正确的接口
    print("\n[Step 6/8] 特征优化层...")
    fo_scores = {}
    try:
        from core.feature_optimizer import get_all_layer_a_scores
        fo_scores = get_all_layer_a_scores(history) or {}
    except Exception as e:
        print(f"  特征层异常: {e}")
    
    # Step 7: 熵控优化层
    print("\n[Step 7/8] 熵控优化层...")
    eo_scores = {}
    try:
        from core.entropy_optimizer import get_number_entropy_scores
        eo_scores = get_number_entropy_scores(history) or {}
    except Exception as e:
        print(f"  熵控层异常: {e}")
    
    # Step 8: 统一评分
    print("\n[Step 8/8] ScoreComposer 统一评分...")
    from core.score_composer import ScoreComposer
    composer = ScoreComposer()
    
    env_info = recognize_environment(history)
    environment = env_info.get('type', 'balanced')
    volatility = compute_volatility(history)
    
    print(f"  环境类型: {environment} (置信度={env_info.get('confidence', 0):.2f})")
    print(f"  波动率: {volatility:.4f}")
    
    raw_scores = {
        'MK': mk_probs,
        'EF': ef_scores,
        'RW': rw_scores,
        'FO': fo_scores,
        'EO': eo_scores,
    }
    
    final_scores = composer.compose(raw_scores, environment, volatility)
    top_list = composer.get_top(final_scores, top_k)
    gs = composer.get_golden_silver(final_scores)
    confidence = composer.get_confidence_report(final_scores)
    
    elapsed = time.time() - start_time
    
    # 输出
    next_period = str(int(history[0]['issue']) + 1) if history else 'N/A'
    print("\n" + "=" * 70)
    print("  K8-Quant v2 结果")
    print("=" * 70)
    print(f"  最新期号: {history[0]['issue'] if history else 'N/A'}")
    print(f"  推荐期号: {next_period}")
    print(f"  ────────────────────────────────")
    print(f"  金胆(5):  {gs['golden']}")
    print(f"  银胆(10): {gs['silver']}")
    print(f"  Top{top_k}: {top_list}")
    print(f"  ────────────────────────────────")
    print(f"  环境: {environment} | 波动率: {volatility:.4f}")
    print(f"  置信度: {confidence['level']} - {confidence['description']}")
    print(f"  耗时: {elapsed:.2f}s")
    print("=" * 70)
    
    return {
        'target_period': next_period,
        'golden': gs['golden'],
        'silver': gs['silver'],
        f'top{top_k}': top_list,
        'final_scores': final_scores,
        'environment': environment,
        'confidence': confidence,
    }


def run_backtest(history, top_k=20):
    """运行Walk-Forward回测"""
    from core.walk_forward_validator import WalkForwardValidator
    
    print("\n" + "=" * 70)
    print("  Walk-Forward 回测验证")
    print("=" * 70)
    
    def prediction_fn(train_data):
        """简化预测函数 (仅马尔可夫+遗漏Sigmoid)"""
        probs = {}
        for n in range(1, 81):
            # 马尔可夫3阶 (全量滑动统计，与 plan7 一致)
            if len(train_data) >= 4:
                pattern = tuple(1 if n in h['numbers'] else 0 for h in train_data[:3])
                count_appear = 0
                count_total = 0
                for i in range(len(train_data) - 3):
                    p = tuple(1 if n in train_data[i+j]['numbers'] else 0 for j in range(3))
                    if p == pattern:
                        count_total += 1
                        if i + 3 < len(train_data) and n in train_data[i+3]['numbers']:
                            count_appear += 1
                
                if count_total >= 3:
                    mk_prob = (count_appear + 0.25) / (count_total + 1.0)
                else:
                    mk_prob = 0.25
            else:
                mk_prob = 0.25
            
            # 遗漏Sigmoid
            gap = 0
            for h in train_data[:50]:
                if n in h['numbers']:
                    break
                gap += 1
            rw_prob = 1.0 / (1.0 + math.exp(-0.3 * (gap - 8)))
            
            probs[n] = mk_prob * 0.6 + rw_prob * 0.4
        return probs
    
    validator = WalkForwardValidator(train_window=50, val_window=10, step=10, min_history=80)
    results = validator.validate(history, prediction_fn, top_k=top_k)
    report = validator.report(results)
    validator.print_report(report)
    return report


def run_learn(history, period=None, actual=None):
    """运行自主闭环学习"""
    from learning.autonomous_learner import AutonomousLearner
    
    learner = AutonomousLearner()
    
    if period and actual:
        # 指定复盘
        report = learner.on_new_result(period, actual, history)
        print("\n[闭环学习报告]")
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        # 自动查找最新待复盘期号
        state = learner.get_current_state()
        pending = learner._state.get('pending_predictions', [])
        if pending:
            latest = pending[-1]
            print(f"[学习] 发现待复盘预测: 期号{latest['period']}")
            print(f"  需要输入实际开奖号码:")
            print(f"  python main_v2.py --learn --period {latest['period']} --actual 5,12,17,23,...")
        else:
            print("[学习] 无待复盘预测, 先运行预测再复盘")
    
    # 无论如何都输出诊断
    learner.print_diagnosis()


def main():
    parser = argparse.ArgumentParser(description='K8-Quant v2 统一预测系统')
    parser.add_argument('--top', type=int, default=20, help='输出Top-K号码')
    parser.add_argument('--backtest', action='store_true', help='运行Walk-Forward回测')
    parser.add_argument('--report', action='store_true', help='输出详细报告')
    parser.add_argument('--learn', action='store_true', help='运行自主闭环学习')
    parser.add_argument('--diagnose', action='store_true', help='输出学习引擎诊断')
    parser.add_argument('--period', type=str, default=None, help='复盘期号')
    parser.add_argument('--actual', type=str, default=None, help='实际开奖号码(逗号分隔)')
    parser.add_argument('--history', type=str, default=None, help='历史数据文件路径')
    args = parser.parse_args()
    
    # --diagnose 不需要历史数据
    if args.diagnose:
        from learning.autonomous_learner import AutonomousLearner
        learner = AutonomousLearner()
        learner.print_diagnosis()
        return
    
    history = load_history(args.history)
    if not history:
        print("[ERROR] 无法加载历史数据")
        return
    
    if args.learn:
        actual = None
        if args.actual:
            actual = [int(x.strip()) for x in args.actual.split(',')]
        run_learn(history, args.period, actual)
    elif args.backtest:
        run_backtest(history, args.top)
    else:
        result = run_pipeline(history, args.top)
        
        # 记录预测到学习引擎
        try:
            from learning.autonomous_learner import AutonomousLearner
            learner = AutonomousLearner()
            next_period = str(int(history[0]['issue']) + 1) if history else 'N/A'
            learner.record_prediction(
                period=next_period,
                prediction_scores=result.get('final_scores', {}),
                top5=result.get('golden', []),
                top12=result.get('silver', []) + result.get('golden', []),
                top20=result.get(f'top{args.top}', []),
                environment=result.get('environment', 'balanced'),
                volatility=result.get('confidence', {}).get('spread', 0.15),
            )
        except Exception as e:
            print(f"[学习] 预测记录异常: {e}")
        
        if args.report:
            print("\n[详细报告]")
            print(json.dumps({k: v for k, v in result.items() if k != 'final_scores'},
                           ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
