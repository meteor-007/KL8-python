# -*- coding: utf-8 -*-
"""
样本外 (Out-of-Sample) 纸面交易台账
====================================
把每日预测与开奖对齐, 自开奖后由 AutonomousLearner 自动追加记录,
用于长期验证"是否真有可复现 edge", 而非只看单期。

- 台账: cache/paper_trading.jsonl (只追加, 人不可篡改)
- 汇总: cache/paper_trading_summary.json
"""
import os
import sys
import json
import math
import datetime

if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()

LEDGER_FILE = os.path.join(_PROJ, 'cache', 'paper_trading.jsonl')
SUMMARY_FILE = os.path.join(_PROJ, 'cache', 'paper_trading_summary.json')

BASELINE_HIT_RATE = 20.0 / 80.0   # 随机选 Top20 的期望命中率


def record_result(period, predicted_top_k, actual_numbers,
                  predicted_env=None, top_k=20) -> dict:
    """追加一条样本外记录 (幂等: 同一 period 已存在则不重复)。"""
    os.makedirs(os.path.dirname(LEDGER_FILE), exist_ok=True)
    actual = set(int(x) for x in actual_numbers)
    pred = [int(x) for x in predicted_top_k]
    hits = len(actual & set(pred))
    baseline_expected = BASELINE_HIT_RATE * top_k
    entry = {
        'period': str(period),
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'predicted_top_k': pred,
        'actual_numbers': sorted(actual),
        'top_k': top_k,
        'hits': hits,
        'baseline_expected_hits': round(baseline_expected, 4),
        'lift': round((hits / top_k) / BASELINE_HIT_RATE, 4) if top_k else 1.0,
        'predicted_env': predicted_env,
    }
    # 幂等去重
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    if json.loads(line).get('period') == entry['period']:
                        return entry
                except Exception:
                    continue
    with open(LEDGER_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry


def _load_ledger():
    rows = []
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    return rows


def report_oos(rolling: int = 60) -> dict:
    """计算累计与滚动窗口的样本外命中率/Lift, 写入汇总文件。"""
    rows = _load_ledger()
    n = len(rows)
    if n == 0:
        summary = {
            'n_records': 0,
            'note': '尚无样本外记录, 开奖后运行 --learn 自动累积',
        }
        os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
        with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        return summary

    def _agg(sub):
        total_hits = sum(r['hits'] for r in sub)
        total_trials = sum(r['top_k'] for r in sub)
        hit_rate = total_hits / total_trials if total_trials else 0.0
        lift = hit_rate / BASELINE_HIT_RATE if BASELINE_HIT_RATE else 1.0
        return {'samples': len(sub), 'total_hits': total_hits,
                'total_trials': total_trials, 'hit_rate': round(hit_rate, 4),
                'lift': round(lift, 4)}

    recent = rows[-rolling:]
    summary = {
        'n_records': n,
        'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'rolling_window': rolling,
        'cumulative': _agg(rows),
        'rolling': _agg(recent),
        'baseline_hit_rate': BASELINE_HIT_RATE,
        'note': ('判定: cumulative.lift > 1 且滚动窗口保持 >1 才说明存在可复现 edge; '
                 '否则建议观望不追号'),
    }
    os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def print_report():
    s = report_oos()
    print(f"\n{'='*60}")
    print("  样本外 (OOS) 纸面交易台账")
    print(f"{'='*60}")
    if s.get('n_records', 0) == 0:
        print("  尚无记录, 开奖后运行 --learn 自动累积")
        return
    c = s['cumulative']
    r = s['rolling']
    print(f"  累计记录: {s['n_records']} 期")
    print(f"  累计命中率: {c['hit_rate']:.2%}, Lift={c['lift']:.4f} (样本={c['samples']})")
    print(f"  近{s['rolling_window']}期命中率: {r['hit_rate']:.2%}, Lift={r['lift']:.4f} (样本={r['samples']})")
    if c['samples'] < 20:
        verdict = f"样本量不足({c['samples']}<20), 暂不下结论"
    elif c['lift'] > 1.0 and r['lift'] > 1.0:
        verdict = '存在可复现 edge'
    else:
        verdict = '无稳定 edge, 建议观望'
    print(f"  判定: {verdict}")


if __name__ == '__main__':
    print_report()