# -*- coding: utf-8 -*-
"""
K8-Quant 统一入口 — FO 单通道 Baseline
========================================
Daily 默认: FO 主推荐
Weekly: EF/RW/MK/EO/BAYES/MC 通道 Lift 监控 (--weekly-monitor)
自学习: WF Lift > 1.0 (learning_gate 单点阈值) 解锁 (当前冻结)
"""
import os
import sys
import re
import json
import math
import time
import argparse
import collections
import contextlib
import io
import numpy as np

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()

# V1.0 每日幂等校验: 导入失败时静默放行（绝不阻断主流程）
try:
    from daily_run_guard import guard_daily_run, mark_daily_run_done, clean_pycache
except Exception:
    guard_daily_run = lambda *a, **k: False
    mark_daily_run_done = lambda *a, **k: None
    clean_pycache = lambda *a, **k: 0



def load_history(history_file=None):
    """加载历史数据，按期号降序排列（最新在前）

    v2.2: 委托给 utils.history_loader.load_history()，消除重复实现。
    保留 history_file 参数与加载日志输出，行为一致。
    """
    from utils.history_loader import load_history as _load
    history = _load(history_file=history_file)
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


def compute_raw_scores(history, quiet=False, history_only=False, mode='daily'):
    """
    计算信号通道分数。
    mode='daily'  — 仅 FO + RANDOM (daily 默认)
    mode='full'   — 全部通道 (weekly 监控 / --validate-signals)
    返回 (all_scores, primary_channels, control_channels, validation_meta)
    """
    from core.signal_registry import get_active_config
    from core.baseline import compute_fo_scores

    def _run(label, fn):
        if not quiet:
            print(f"\n[{label}]...")
        try:
            return fn() or {}
        except Exception as e:
            if not quiet:
                print(f"  {label} 异常: {e}")
            return {}

    reg_mode = 'weekly' if mode == 'full' else 'daily'
    primary, control, validation_meta = get_active_config(history, mode=reg_mode)

    stdout_ctx = contextlib.redirect_stdout(io.StringIO()) if quiet else contextlib.nullcontext()
    with stdout_ctx:
        fo_scores = _run('FO', lambda: compute_fo_scores(history, history_only=history_only))

        all_scores = {'FO': fo_scores}

        if mode == 'full':
            mk_probs = _run('MK', lambda: (
                __import__('core.algorithm_optimizer', fromlist=['plan7_markov_integration'])
                .plan7_markov_integration(history).get('probs', {})
            ))
            ef_scores = _run('EF', lambda: (
                __import__('core.energy_field', fromlist=['calc_energy_field'])
                .calc_energy_field(history, decay_rate=0.5)
            ))
            rw_scores = _run('RW', lambda: (
                __import__('core.energy_field', fromlist=['calc_omission_sigmoid'])
                .calc_omission_sigmoid(history)
            ))
            bayes_result = _run('BAYES', lambda: (
                __import__('core.algorithm_optimizer', fromlist=['plan9_bayesian_update'])
                .plan9_bayesian_update(history) or {}
            ))
            mc_result = _run('MC', lambda: (
                __import__('core.algorithm_optimizer', fromlist=['plan10_monte_carlo'])
                .plan10_monte_carlo(history) or {}
            ))
            eo_scores = _run('EO', lambda: (
                __import__('core.entropy_optimizer', fromlist=['get_number_entropy_scores'])
                .get_number_entropy_scores([h['numbers'] for h in history]) or {}
            ))
            all_scores.update({
                'MK': mk_probs,
                'EF': ef_scores,
                'RW': rw_scores,
                'EO': eo_scores,
                # 修复: plan9 返回键为 bayes_top20/posteriors/credible_intervals, 无 'probs'
                'BAYES': (bayes_result.get('posteriors')
                          if isinstance(bayes_result, dict) and isinstance(bayes_result.get('posteriors'), dict)
                          else {}),
                # 修复: plan10 返回键为 mc_top20/sim_freq, 无 'probs'
                'MC': (mc_result.get('sim_freq')
                       if isinstance(mc_result, dict) and isinstance(mc_result.get('sim_freq'), dict)
                       else {}),
            })

    if mode == 'full':
        try:
            cache_dir = os.path.join(_PROJ, 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            control_snapshot = {
                ch: {str(n): round(all_scores.get(ch, {}).get(n, 0), 6) for n in range(1, 81)}
                for ch in control
                if ch in all_scores
            }
            with open(os.path.join(cache_dir, 'control_signals.json'), 'w', encoding='utf-8') as f:
                json.dump({
                    'primary': primary,
                    'control': control,
                    'scores': control_snapshot,
                    'validation': {
                        'note': validation_meta.get('note'),
                        'channel_stats': validation_meta.get('channel_stats', []),
                    },
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return all_scores, primary, control, validation_meta


def predict_scores(history, quiet=True):
    """Walk-Forward / 回测入口: FO 单通道 baseline, 返回 {号码: 分数}"""
    from core.baseline import compute_fo_scores
    stdout_ctx = contextlib.redirect_stdout(io.StringIO()) if quiet else contextlib.nullcontext()
    with stdout_ctx:
        return compute_fo_scores(history, history_only=True)


def run_pipeline(history, top_k=20, quiet=False):
    """Daily 极简管线: FO 单通道"""
    from core.baseline import run_daily_baseline

    if not quiet:
        print("\n" + "=" * 70)
        print("  K8-Quant FO Baseline (FO)")
        print("=" * 70)

    start_time = time.time()
    result = run_daily_baseline(history, top_k=top_k)
    elapsed = time.time() - start_time
    result['elapsed_sec'] = round(elapsed, 2)

    gate = result.get('learning_gate', {})

    if not quiet:
        next_period = result.get('target_period', 'N/A')
        print(f"\n[模式] FO 单通道 baseline")
        print(f"  环境: {result.get('environment')} | {result.get('confidence', {}).get('description', '')}")
        print("\n" + "=" * 70)
        print("  主推荐 (FO)")
        print("=" * 70)
        print(f"  推荐期号: {next_period}")
        print(f"  金胆(5):  {result.get('golden', [])}")
        print(f"  银胆(5): {result.get('silver', [])}")
        print(f"  Top{top_k}: {result.get(f'top{top_k}', [])}")
        if gate:
            print(f"\n  自学习: {'已解锁' if gate.get('learning_enabled') else '已冻结'} "
                  f"(WF Lift={gate.get('last_wf_lift', 'N/A')})")
        print(f"  耗时: {elapsed:.2f}s")
        print("=" * 70)

    return result


def run_backtest(history, top_k=20):
    """Walk-Forward 回测 — FO 单通道 baseline (门控依据)"""
    from core.walk_forward_validator import WalkForwardValidator
    from core.learning_gate import record_wf_report, gate_status, WF_RESULTS_FILE, DEFAULT_LIFT_THRESHOLD

    print("\n" + "=" * 70)
    print("  Walk-Forward 回测 (FO Baseline)")
    print("=" * 70)
    print("\n[模式] Daily 固定 FO 单通道 | 其余通道见 --weekly-monitor")

    def prediction_fn(train_data):
        return predict_scores(train_data, quiet=True)

    validator = WalkForwardValidator(train_window=50, val_window=10, step=10, min_history=80)
    results = validator.validate(history, prediction_fn, top_k=top_k)
    report = validator.report(results)
    report['pipeline_mode'] = 'fo_baseline'
    report['primary_channels'] = ['FO']
    try:
        os.makedirs(os.path.dirname(WF_RESULTS_FILE), exist_ok=True)
        with open(WF_RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    record_wf_report(report)
    validator.print_report(report)

    gate = gate_status()
    print(f"\n[自学习门控] {gate.get('message', '')}")
    if not gate.get('learning_enabled'):
        # 阈值统一引用 learning_gate 单点配置, 避免硬编码 1.1 与 1.0 漂移
        print(f"  → param_store / 闭环权重 / Loss更新 均已冻结, 直至 Lift > {gate.get('lift_threshold', DEFAULT_LIFT_THRESHOLD)}")

    return report


def run_weekly_monitor(history, top_k=20):
    """Weekly 全通道 Lift 监控 — 不参与 daily 输出"""
    from core.baseline import run_weekly_monitor as _monitor

    print("\n" + "=" * 70)
    print("  Weekly 通道监控 (EF/RW/MK/EO/BAYES/MC)")
    print("=" * 70)

    report = _monitor(history, top_k=top_k)
    stats = (report.get('channel_validation') or {}).get('channel_stats', [])
    print(f"\n[Daily 主通道] FO (固定 baseline)")
    print(f"[Weekly 监控] {report.get('channel_top20', {}).keys()}")
    for s in stats:
        flag = ' *FDR' if s.get('significant_fdr') else ''
        print(f"  {s['channel']}: Lift={s['lift']:.3f} p={s['p_value']:.4f}{flag}")
    print(f"\n报告已写入 cache/weekly_channel_monitor.json")
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
    parser = argparse.ArgumentParser(description='K8-Quant FO Baseline 预测系统')
    parser.add_argument('--top', type=int, default=20, help='输出Top-K号码')
    parser.add_argument('--backtest', action='store_true', help='Walk-Forward回测 (FO baseline)')
    parser.add_argument('--weekly-monitor', action='store_true', help='Weekly全通道监控 (不参与daily)')
    parser.add_argument('--validate-signals', action='store_true', help='刷新信号通道FDR评估 (weekly)')
    parser.add_argument('--report', action='store_true', help='输出详细报告')
    parser.add_argument('--learn', action='store_true', help='运行自主闭环学习')
    parser.add_argument('--diagnose', action='store_true', help='输出学习引擎诊断')
    parser.add_argument('--oos-report', action='store_true', help='输出样本外纸面交易台账')
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

    if args.oos_report:
        from learning.paper_trading import print_report
        print_report()
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
    elif args.validate_signals:
        compute_raw_scores(history, quiet=False, mode='full')
        from core.signal_registry import validate_channels
        meta = validate_channels(history, force=True)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    elif args.weekly_monitor:
        run_weekly_monitor(history, args.top)
    elif args.backtest:
        run_backtest(history, args.top)
    else:
        # V1.0 每日幂等校验: 仅每日预测 pipeline 触发（其余模式不校验）
        if guard_daily_run("data", interactive=False):
            return
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
                top12=list(result.get(f'top{args.top}', []))[:12],
                top20=result.get(f'top{args.top}', []),
                environment=result.get('environment', 'balanced'),
                volatility=result.get('confidence', {}).get('spread', 0.15),
            )
        except Exception as e:
            print(f"[学习] 预测记录异常: {e}")
        
        # 自动生成每日分析报告 (V18.2 修复)
        try:
            from pipeline.auto_generate_daily_report import DailyReportOrchestrator
            orchestrator = DailyReportOrchestrator()
            orchestrator.generate_report()
        except Exception as e:
            print(f"[报告] 自动生成报告异常: {e}")
        
        if args.report:
            print("\n[详细报告]")
            print(json.dumps({k: v for k, v in result.items() if k != 'final_scores'},
                           ensure_ascii=False, indent=2))

        # V1.0 每日幂等校验: 成功收尾标记 + 环境清理
        mark_daily_run_done("data", period=str(int(history[0]['issue']) + 1) if history else 'N/A')
        clean_pycache(os.path.dirname(os.path.abspath(__file__)))


if __name__ == '__main__':
    main()
