# -*- coding: utf-8 -*-
"""
Walk-Forward 验证框架
======================
替代原 deep_hit_rate_optimizer.py 中简单的滑动窗口回测。

Walk-Forward Validation 是时间序列回测的黄金标准:
  - 训练窗口: 用于拟合模型参数
  - 验证窗口: 用于评估预测效果 (严格未来数据, 无泄露)
  - 步进: 每次向前滑动一个期号, 重复训练-验证

这避免了:
  1. 过拟合短窗口 (原15期验证窗口)
  2. 前瞻偏差 (用未来数据调参)
  3. 单次验证不稳健 (一次验证不能代表长期表现)

使用方式:
    from core.walk_forward_validator import WalkForwardValidator
    
    validator = WalkForwardValidator(
        train_window=50,
        val_window=10,
        step=5,
        min_history=100
    )
    
    results = validator.validate(history, prediction_fn)
    report = validator.report(results)
"""
import os
import json
import math
import numpy as np
from typing import Dict, List, Callable, Tuple, Any
from collections import defaultdict

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
WF_RESULTS_FILE = os.path.join(_PROJ, 'cache', 'walk_forward_results.json')


class WalkForwardValidator:
    """
    Walk-Forward 验证器
    
    参数说明:
      train_window: 训练窗口大小 (用多少期历史数据训练模型)
      val_window: 验证窗口大小 (评估多少期的预测效果)
      step: 滑动步长 (每次前进几期)
      min_history: 最少需要的总历史期数
    
    推荐配置:
      - 保守: train=100, val=10, step=5 (需要~150期历史)
      - 中等: train=50, val=10, step=5 (需要~80期历史)
      - 激进: train=30, val=5, step=3 (需要~50期历史)
    """
    
    def __init__(self,
                 train_window: int = 50,
                 val_window: int = 10,
                 step: int = 5,
                 min_history: int = 80):
        self.train_window = train_window
        self.val_window = val_window
        self.step = step
        self.min_history = min_history
    
    def validate(self,
                 history: List[Dict],
                 prediction_fn: Callable,
                 top_k: int = 20) -> List[Dict]:
        """
        执行 Walk-Forward 验证
        
        Args:
            history: 历史数据 [{issue: '2026100', numbers: [1,5,...]}, ...]
                     按时间降序排列 (最新在前)
            prediction_fn: 预测函数, 签名:
                           prediction_fn(train_data) -> Dict[int, float]
                           输入训练数据, 输出各号码的评分
            top_k: 取Top-K进行命中率评估
        
        Returns:
            各Fold的验证结果列表
        """
        if len(history) < self.min_history:
            print(f"[WF] 历史数据不足: {len(history)} < {self.min_history}")
            return []
        
        # 反转为升序 (最老在前)
        data = list(reversed(history))
        n = len(data)
        
        results = []
        fold_id = 0
        
        # 起始位置: 训练窗口之后
        start = self.train_window
        
        while start + self.val_window <= n:
            fold_id += 1

            # 验证集: [start, start + val_window)
            val_data = data[start:start + self.val_window]

            # 每个验证期独立预测: 训练数据为其之前的所有历史,
            # 避免用"未来"信息 (单点预测不复用整段验证窗)
            fold_hits = []
            for j in range(start, start + self.val_window):
                val_record = data[j]
                train_data = list(reversed(data[:j]))  # 转回降序, 兼容原有函数
                try:
                    scores = prediction_fn(train_data)
                except Exception as e:
                    print(f"[WF] Fold {fold_id} 期 {j} 预测异常: {e}")
                    continue
                if not scores:
                    continue

                actual = set(val_record.get('numbers', []))
                top_nums = sorted(scores, key=lambda n: (-scores[n], n))[:top_k]
                hit_count = len(actual & set(top_nums))
                hit_rate = hit_count / top_k if top_k > 0 else 0

                # Lift: 实际命中率 / 期望命中率(20/80=0.25)
                expected_rate = 20 / 80
                lift = hit_rate / expected_rate if expected_rate > 0 else 0

                fold_hits.append({
                    'issue': val_record.get('issue', f'fold{fold_id}'),
                    'hit_count': hit_count,
                    'hit_rate': round(hit_rate, 4),
                    'lift': round(lift, 4),
                    'top_k': top_nums,
                    'actual': sorted(actual),
                })

            if not fold_hits:
                start += self.step
                continue

            # Fold汇总
            avg_hit_rate = np.mean([h['hit_rate'] for h in fold_hits])
            avg_lift = np.mean([h['lift'] for h in fold_hits])
            hit_rates = [h['hit_rate'] for h in fold_hits]

            result = {
                'fold_id': fold_id,
                'train_range': f'[0, {start})',
                'val_range': f'[{start}, {start + self.val_window})',
                'n_train': start,
                'n_val': self.val_window,
                'avg_hit_rate': round(avg_hit_rate, 4),
                'avg_lift': round(avg_lift, 4),
                'std_hit_rate': round(np.std(hit_rates), 4),
                'fold_hits': fold_hits,
            }
            results.append(result)

            start += self.step

        return results
    
    def report(self, results: List[Dict]) -> Dict:
        """
        生成Walk-Forward验证汇总报告
        """
        if not results:
            return {'status': 'NO_DATA', 'message': '无验证结果'}
        
        # 各Fold的平均命中率
        avg_rates = [r['avg_hit_rate'] for r in results]
        avg_lifts = [r['avg_lift'] for r in results]
        std_rates = [r['std_hit_rate'] for r in results]
        
        # 全局统计
        global_avg_rate = np.mean(avg_rates)
        global_avg_lift = np.mean(avg_lifts)
        global_std_rate = np.mean(std_rates)
        
        # 稳定性: 命中率的标准差越小越稳定
        stability = 1.0 - min(1.0, np.std(avg_rates) / max(global_avg_rate, 0.01))
        
        # 趋势: 后半段 vs 前半段
        mid = len(results) // 2
        first_half_avg = np.mean(avg_rates[:mid]) if mid > 0 else avg_rates[0]
        second_half_avg = np.mean(avg_rates[mid:])
        trend = 'IMPROVING' if second_half_avg > first_half_avg * 1.05 else \
                'DECLINING' if second_half_avg < first_half_avg * 0.95 else 'STABLE'
        
        # 期望基线 (随机选择 Top20 的期望命中率 = 20/80 = 0.25)
        baseline = 20.0 / 80.0
        excess = global_avg_rate - baseline

        # ── 多折 CI 下界: 基于各折 Lift / 命中率的均值 ± z·SE ──
        # 门控依据: 用 CI 下界 > 基线(1.0) 判定是否有可复现优势, 而非单点全局均值。
        # 保守校正: 各折训练窗高度重叠(step<train_window), 折间不独立,
        #           有效样本量远小于 n_folds; 故按 eff_n = max(2, n_f/2) 放大 SE,
        #           避免区间偏窄(anti-conservative)导致门控误解锁。
        import math as _math
        lifts = [r['avg_lift'] for r in results]
        rates = [r['avg_hit_rate'] for r in results]
        n_f = len(results)
        eff_n = max(2, n_f // 2) if n_f > 1 else n_f
        z = 1.96  # 95% 置信水平 (n 大, 正态近似足够)
        if n_f > 1:
            mean_lift = float(np.mean(lifts))
            std_lift = float(np.std(lifts, ddof=1))
            se_lift = std_lift / _math.sqrt(eff_n)
            mean_rate = float(np.mean(rates))
            std_rate = float(np.std(rates, ddof=1))
            se_rate = std_rate / _math.sqrt(eff_n)
        else:
            # 单折无法计算多折 CI, 下界必须为 None (门控据此保持冻结)
            mean_lift = float(global_avg_lift)
            mean_rate = float(global_avg_rate)
            se_lift = se_rate = None
        if se_lift is None:
            ci_lift_lo = ci_lift_hi = ci_rate_lo = ci_rate_hi = None
        else:
            ci_lift_lo = round(mean_lift - z * se_lift, 4)
            ci_lift_hi = round(mean_lift + z * se_lift, 4)
            ci_rate_lo = round(mean_rate - z * se_rate, 4)
            ci_rate_hi = round(mean_rate + z * se_rate, 4)

        report = {
            'status': 'OK',
            'n_folds': len(results),
            'train_window': self.train_window,
            'val_window': self.val_window,
            'step': self.step,
            'global_avg_hit_rate': round(global_avg_rate, 4),
            'global_avg_lift': round(global_avg_lift, 4),
            'global_std_hit_rate': round(global_std_rate, 4),
            'ci_lift_lo': ci_lift_lo,
            'ci_lift_hi': ci_lift_hi,
            'ci_rate_lo': ci_rate_lo,
            'ci_rate_hi': ci_rate_hi,
            'ci_z': z,
            'n_folds_used': n_f,
            'stability': round(stability, 4),
            'trend': trend,
            'baseline_rate': baseline,
            'excess_over_baseline': round(excess, 4),
            'first_half_avg': round(first_half_avg, 4),
            'second_half_avg': round(second_half_avg, 4),
            'per_fold_summary': [
                {
                    'fold_id': r['fold_id'],
                    'avg_hit_rate': r['avg_hit_rate'],
                    'avg_lift': r['avg_lift'],
                    'std_hit_rate': r['std_hit_rate'],
                }
                for r in results
            ],
        }
        
        # 保存
        try:
            os.makedirs(os.path.dirname(WF_RESULTS_FILE), exist_ok=True)
            with open(WF_RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        
        return report
    
    @staticmethod
    def print_report(report: Dict):
        """打印验证报告"""
        if report.get('status') != 'OK':
            print(f"[WF] {report.get('message', '无结果')}")
            return
        
        print("\n" + "=" * 70)
        print("  Walk-Forward 验证报告")
        print("=" * 70)
        print(f"  Fold数:       {report['n_folds']}")
        print(f"  训练窗口:     {report['train_window']}期")
        print(f"  验证窗口:     {report['val_window']}期")
        print(f"  滑动步长:     {report['step']}期")
        print(f"  ────────────────────────────────")
        print(f"  全局平均命中率: {report['global_avg_hit_rate']:.2%}")
        print(f"  全局平均Lift:   {report['global_avg_lift']:.4f}")
        print(f"  命中率标准差:   {report['global_std_hit_rate']:.4f}")
        if report.get('ci_lift_lo') is not None:
            print(f"  Lift 95%CI:     [{report['ci_lift_lo']:.4f}, {report['ci_lift_hi']:.4f}] "
                  f"(下界={report['ci_lift_lo']:.4f})")
        else:
            print(f"  Lift 95%CI:     N/A (折数不足, 无法计算多折置信区间)")
        print(f"  稳定性评分:     {report['stability']:.2%}")
        print(f"  趋势:           {report['trend']}")
        print(f"  基线命中率:     {report['baseline_rate']:.2%}")
        print(f"  超额命中率:     {report['excess_over_baseline']:+.4f}")
        print(f"  前半段均值:     {report['first_half_avg']:.2%}")
        print(f"  后半段均值:     {report['second_half_avg']:.2%}")
        print(f"  ────────────────────────────────")
        
        # 各Fold详情
        print(f"\n  {'Fold':>5}  {'命中率':>8}  {'Lift':>8}  {'标准差':>8}")
        print(f"  {'─'*5}  {'─'*8}  {'─'*8}  {'─'*8}")
        for fold in report.get('per_fold_summary', []):
            print(f"  {fold['fold_id']:>5}  {fold['avg_hit_rate']:>8.2%}  "
                  f"{fold['avg_lift']:>8.4f}  {fold['std_hit_rate']:>8.4f}")
        print("=" * 70)


if __name__ == '__main__':
    # 测试: 用简单的频率预测函数
    import random
    
    def dummy_prediction_fn(train_data):
        """简单的频率预测"""
        from collections import Counter
        freq = Counter()
        for h in train_data:
            for n in h.get('numbers', []):
                freq[n] += 1
        return {n: freq.get(n, 0) for n in range(1, 81)}
    
    # 生成模拟历史数据
    mock_history = []
    for i in range(200):
        numbers = random.sample(range(1, 81), 20)
        mock_history.append({'issue': f'2026{i+1:03d}', 'numbers': numbers})
    
    validator = WalkForwardValidator(train_window=50, val_window=10, step=20, min_history=80)
    results = validator.validate(mock_history, dummy_prediction_fn, top_k=20)
    report = validator.report(results)
    validator.print_report(report)


def assert_is_future_consistent(feature_builder, aio_history):
    """校验特征构建函数签名必须接受显式 is_future 参数。

    防止回测恒 False 而线上读取目标期行的 train/serve 偏差。
    """
    if aio_history:
        raise ValueError("aio_history 参数已废弃，请直接传 draw 列表")
    import inspect
    try:
        sig = inspect.signature(feature_builder)
    except (TypeError, ValueError):
        raise ValueError("feature_builder 必须是可内省的函数/方法")
    params = list(sig.parameters)
    if "is_future" not in params:
        raise ValueError(
            "feature_builder 必须接受显式 is_future 参数（回测传 False，线上传 True）"
        )
    return True
