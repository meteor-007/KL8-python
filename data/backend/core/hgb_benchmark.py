# -*- coding: utf-8 -*-
"""
HistGradientBoosting 基准模型 (C8) — 用 sklearn 替代已退役的 LSTM/RF
=====================================================================
大白话:
  项目里的 LSTM / RandomForest / Transformer 等复杂模型已经退役(见
  module_vote_registry.json), 因为它们在 KL8 这种近随机数据上没有
  可验证 edge。本模块提供一个"诚实的现代基线": sklearn 的
  HistGradientBoostingClassifier —— 表格特征上通常强于手写规则,
  且原生处理非线性, 不需要 GPU。

  但它的定位是【基准/对照】, 不是新的预测神谕:
  - 严格 walk-forward: 训练窗只用过去, 预测下一期, 绝不偷看未来;
  - 输出样本外 lift 与现有前瞻账同口径 (hits/picks / 0.25);
  - 如果它的 lift 也≈1.0, 恰好再次印证"此数据近随机"的结论。

特征 (每个"期×号"一行, 80 号 × D 期):
  omission      — 距上次开出多少期 (0 = 上期开出, D+1 = 从未开出)
  freq_5/10/20  — 近 5/10/20 期出现次数
  freq_50       — 近 50 期出现次数
  freq_all      — 截至上期的全历史出现率
  prev_hit      — 上一期是否开出 (动量代理)

用法:
  python -m backend.core.hgb_benchmark [--folds 4] [--min-train 300]
"""
import argparse
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np

if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_cache_dir, _ensure_project_path
_ensure_project_path()

try:
    from sklearn.ensemble import HistGradientBoostingClassifier
except Exception:  # pragma: no cover
    HistGradientBoostingClassifier = None

from utils.history_loader import load_history

N_NUMBERS = 80
BASELINE = 0.25          # KL8 单号命中基线 (20/80)
TOP_K = 20               # 每期取概率 top20 号作为 picks
FEATURE_NAMES = ['omission', 'freq_5', 'freq_10', 'freq_20',
                 'freq_50', 'freq_all', 'prev_hit']
RESULT_FILE = os.path.join(get_cache_dir(), 'hgb_benchmark_result.json')


def _draws_asc(history: List[Dict]) -> List[Dict]:
    """history 是期号降序, 转成升序 (最老在前) 并缓存语义由调用方保证。"""
    return list(reversed(history))


def _build_xy(draws: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
    """把开奖历史展开成 (期×号) 特征矩阵与 0/1 标签, 全向量化 O(D·80)。

    draws: 升序开奖列表 [{'issue','numbers',...}]
    返回 (X, y): X shape (D*80, 7), y shape (D*80,)
    """
    D = len(draws)
    # M[t, n-1] = 第 t 期号 n 是否开出
    M = np.zeros((D, N_NUMBERS), dtype=np.int8)
    for t, d in enumerate(draws):
        for n in d['numbers']:
            if 1 <= int(n) <= N_NUMBERS:
                M[t, int(n) - 1] = 1

    # C[t] = 前 t 期 (0..t-1) 的累计开出次数, shape (D+1, 80)
    C = np.vstack([np.zeros((1, N_NUMBERS), dtype=np.int64),
                   np.cumsum(M.astype(np.int64), axis=0)])

    # omission: 每号距上次开出的期数。用反向遍历维护 last_seen。
    O = np.zeros((D, N_NUMBERS), dtype=np.float32)
    last = np.full(N_NUMBERS, -1, dtype=np.int64)  # 上次开出位置
    for t in range(D):
        # omission = t - last (last=-1 表示从未开出 -> t+1)
        O[t] = np.where(last >= 0, t - last, t + 1).astype(np.float32)
        hit_cols = np.nonzero(M[t])[0]
        last[hit_cols] = t

    def _win(k: int) -> np.ndarray:
        """近 k 期次数矩阵 shape (D,80): C[t]-C[max(0,t-k)]"""
        lo = np.maximum(0, np.arange(D) - k)
        return (C[np.arange(D)] - C[lo]).astype(np.float32)

    F5, F10, F20, F50 = _win(5), _win(10), _win(20), _win(50)
    # freq_all = 截至上期累计次数 / t (t=0 时分母置 1, 但 t=0 无训练意义)
    denom = np.maximum(np.arange(D), 1)[:, None]
    FALL = (C[np.arange(D)] / denom).astype(np.float32)
    # prev_hit: 上一期是否开出 (t=0 全 0)
    PREV = np.vstack([np.zeros((1, N_NUMBERS), dtype=np.float32),
                      M[:-1].astype(np.float32)]) if D > 1 else \
           np.zeros((D, N_NUMBERS), dtype=np.float32)

    X = np.stack([O, F5, F10, F20, F50, FALL, PREV], axis=-1)  # (D,80,7)
    X = X.reshape(D * N_NUMBERS, len(FEATURE_NAMES))
    y = M.reshape(-1).astype(np.float32)
    return X, y


def walk_forward_eval(history: List[Dict], n_folds: int = 4,
                      min_train_periods: int = 300,
                      seed: int = 42) -> Dict:
    """Walk-forward 评估: 测试段均分在 [min_train, D) 上,
    每段用之前所有数据训练 HGB, 预测段内每一期 top20。

    返回 {'status', 'oos_periods', 'total_picks', 'total_hits',
          'hit_rate', 'lift', 'folds', 'note'}
    """
    if HistGradientBoostingClassifier is None:
        return {'status': 'error', 'message': 'sklearn 不可用'}

    draws = _draws_asc(history)
    D = len(draws)
    if D < min_train_periods + n_folds:
        return {'status': 'error',
                'message': f'历史期数 {D} 不足 (需 > {min_train_periods + n_folds})'}

    X, y = _build_xy(draws)
    test_start = min_train_periods
    fold_bounds = np.linspace(test_start, D, n_folds + 1, dtype=int)

    all_hits = all_picks = 0
    folds = []
    pos_class = 1.0

    for f in range(n_folds):
        s, e = int(fold_bounds[f]), int(fold_bounds[f + 1])
        if e <= s:
            continue
        train_end = s * N_NUMBERS
        Xtr, ytr = X[:train_end], y[:train_end]
        if len(np.unique(ytr)) < 2:
            continue

        clf = HistGradientBoostingClassifier(
            max_iter=100, learning_rate=0.08, max_leaf_nodes=15,
            min_samples_leaf=200, l2_regularization=1.0,
            random_state=seed, early_stopping=False)
        clf.fit(Xtr, ytr)
        classes = list(clf.classes_)
        pos_idx = classes.index(pos_class) if pos_class in classes else -1
        if pos_idx < 0:
            continue

        fold_hits = fold_picks = 0
        for t in range(s, e):
            idx = np.arange(t * N_NUMBERS, (t + 1) * N_NUMBERS)
            proba = clf.predict_proba(X[idx])[:, pos_idx]
            top_local = np.argsort(-proba)[:TOP_K]
            top_nums = set((top_local + 1).tolist())
            actual = set(int(n) for n in draws[t]['numbers'])
            fold_hits += len(top_nums & actual)
            fold_picks += TOP_K
        if fold_picks:
            folds.append({'fold': f + 1,
                          'periods': [str(draws[s].get('issue', s)),
                                      str(draws[e - 1].get('issue', e - 1))],
                          'n_periods': e - s, 'hits': fold_hits,
                          'picks': fold_picks,
                          'lift': round((fold_hits / fold_picks) / BASELINE, 4)})
            all_hits += fold_hits
            all_picks += fold_picks

    if all_picks == 0:
        return {'status': 'error', 'message': '无有效 OOS 样本'}

    hit_rate = all_hits / all_picks
    return {
        'status': 'ok',
        'model': 'HistGradientBoostingClassifier',
        'features': FEATURE_NAMES,
        'oos_periods': sum(f['n_periods'] for f in folds),
        'total_picks': all_picks,
        'total_hits': all_hits,
        'hit_rate': round(hit_rate, 4),
        'lift': round(hit_rate / BASELINE, 4),
        'folds': folds,
        'note': ('lift≈1.0 表示与随机基线无差异; >1.1 且样本>500 期才值得关注。'
                 '本结果仅为基准对照, 不构成投注建议。'),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='HGB 基准模型 walk-forward 评估')
    ap.add_argument('--folds', type=int, default=4)
    ap.add_argument('--min-train', type=int, default=300)
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()

    history = load_history()
    res = walk_forward_eval(history, n_folds=args.folds,
                            min_train_periods=args.min_train, seed=args.seed)
    import datetime
    res['generated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    print('=' * 60)
    print('HGB 基准模型 Walk-Forward 评估')
    print('=' * 60)
    if res.get('status') != 'ok':
        print(f"状态: {res.get('status')} — {res.get('message')}")
        return 1
    print(f"样本外期数: {res['oos_periods']}, picks: {res['total_picks']}")
    print(f"命中: {res['total_hits']}, 命中率: {res['hit_rate']:.2%}, Lift: {res['lift']:.4f}")
    for fd in res['folds']:
        print(f"  fold{fd['fold']} [{fd['periods'][0]}~{fd['periods'][1]}] "
              f"{fd['n_periods']}期 hits={fd['hits']} lift={fd['lift']}")
    print(f"落盘: {RESULT_FILE}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
