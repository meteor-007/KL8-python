# -*- coding: utf-8 -*-
"""
开奖过程随机性检验 (Draw Randomness Audit)
==========================================
建模之前先回答一个最根本的问题: "开奖本身到底随不随机?"
这是整个系统里唯一可能存在真实 edge 的方向——如果开奖是公平随机的,
后面所有预测模型都只是在拟合噪声。

本模块对历史开奖序列做一组"大白话"的统计体检:

1. uniformity_per_number  每个号出现次数是否符合 Binomial(D, 0.25),
   80 个号合并成一个 GOF 卡方 (df=79), 单号 p 值过 BH-FDR;
2. pair_uniformity        共现对均匀性 (3160 对, 每对期望 D*190/3160 次),
   全量向量化计算 + 抽样报告单对 p 值;
3. runs_test              单个号的 0/1 序列做 Wald-Wolfowitz 游程检验;
4. serial_correlation     单个号相邻两期命中指示的 lag-1 自相关;
5. window_drift           按时间切不重叠窗口, 看"高频号集中度"是否漂移
   (卡方齐性检验 + 线性趋势检验);
6. run_full_report        汇总入口, 返回结构化 dict 并可落盘 JSON。

注意: 没有 scipy, 卡方分布 p 值用自实现的正则化不完全伽马函数
(Numerical Recipes 的 gammp/gammq, series + continued fraction)。
"""
import os
import sys
import json
import math
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# ---- sys.path 引导 (照抄项目惯例) ----
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, get_reports_dir, _ensure_project_path  # noqa: E402
_ensure_project_path()

from utils.history_loader import load_history  # noqa: E402
from core.multiple_testing import bh_fdr  # noqa: E402

# ---- 常量 ----
N_NUMBERS = 80          # 号码池大小
DRAWS_PER_PERIOD = 20   # 每期开出个数
BASE_HIT_P = DRAWS_PER_PERIOD / N_NUMBERS  # 单号基础命中率 = 0.25
N_PAIRS_TOTAL = N_NUMBERS * (N_NUMBERS - 1) // 2  # C(80,2) = 3160
PAIRS_PER_DRAW = DRAWS_PER_PERIOD * (DRAWS_PER_PERIOD - 1) // 2  # C(20,2) = 190
FAMILY_ALPHA = 0.05


# =====================================================================
# 0. 自实现统计分布函数 (没有 scipy, 自己造轮子)
# =====================================================================

def _gammp_series(a: float, x: float) -> float:
    """正则化下不完全伽马 P(a,x), 用级数展开 (x < a+1 时用)。"""
    gln = math.lgamma(a)
    if x <= 0.0:
        return 0.0
    ap = a
    s = 1.0 / a
    delta = s
    for _ in range(200):
        ap += 1.0
        delta *= x / ap
        s += delta
        if abs(delta) < abs(s) * 1e-14:
            break
    return s * math.exp(-x + a * math.log(x) - gln)


def _gammq_cf(a: float, x: float) -> float:
    """正则化上不完全伽马 Q(a,x), 用连分式 (x >= a+1 时用)。"""
    gln = math.lgamma(a)
    b = x + 1.0 - a
    c = 1.0 / 1e-300
    d = 1.0 / b
    h = d
    for i in range(1, 201):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def gammq(a: float, x: float) -> float:
    """正则化上不完全伽马函数 Q(a,x) = Gamma(a,x)/Gamma(a)。"""
    if x < 0.0 or a <= 0.0:
        return float('nan')
    if x == 0.0:
        return 1.0
    if x < a + 1.0:
        return max(0.0, min(1.0, 1.0 - _gammp_series(a, x)))
    return max(0.0, min(1.0, _gammq_cf(a, x)))


def chi_square_sf(x: float, k: int) -> float:
    """卡方分布上尾概率 P(chi2_k >= x)。

    卡方_k 本质上是 Gamma(shape=k/2, scale=2), 所以
    sf = Q(k/2, x/2)。
    """
    if k <= 0:
        return float('nan')
    if x <= 0.0:
        return 1.0
    return gammq(0.5 * k, 0.5 * x)


def _norm_sf(z: float) -> float:
    """标准正态上尾概率, 用 erfc 精确算。"""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


# =====================================================================
# 1. 每号频数均匀性
# =====================================================================

def _counts_per_number(history: Sequence[Dict]) -> np.ndarray:
    """统计每个号 (1..80) 在历史中出现的总次数, 返回长度 80 的数组。"""
    counts = np.zeros(N_NUMBERS, dtype=np.int64)
    for h in history:
        for n in h.get('numbers', []):
            n = int(n)
            if 1 <= n <= N_NUMBERS:
                counts[n - 1] += 1
    return counts


def _binary_matrix(history: Sequence[Dict]) -> np.ndarray:
    """D x 80 的 0/1 命中矩阵, 行顺序与 history 一致。"""
    D = len(history)
    M = np.zeros((D, N_NUMBERS), dtype=np.int8)
    for i, h in enumerate(history):
        for n in h.get('numbers', []):
            n = int(n)
            if 1 <= n <= N_NUMBERS:
                M[i, n - 1] = 1
    return M


def uniformity_per_number(history: Sequence[Dict]) -> Dict:
    """检验每个号出现次数是否符合 Binomial(D, 0.25)。

    - 每号: 观测次数 vs 期望 D*0.25, 单号卡方贡献 + df=1 的 p 值;
    - 80 个号合并成一个 GOF 卡方 (df=79);
    - 单号 p 值过 BH-FDR 得 q 值。
    """
    D = len(history)
    if D == 0:
        return {'error': 'empty history', 'n_draws': 0}

    counts = _counts_per_number(history)
    expected = D * BASE_HIT_P
    contrib = (counts - expected) ** 2 / expected
    chi2_stat = float(contrib.sum())
    p_combined = chi_square_sf(chi2_stat, N_NUMBERS - 1)

    # 单号 p 值 (df=1) + BH-FDR
    p_per = [chi_square_sf(float(c), 1) for c in contrib]
    sig_mask, q_per = bh_fdr(p_per, alpha=FAMILY_ALPHA)

    per_number = []
    for n in range(N_NUMBERS):
        per_number.append({
            'number': n + 1,
            'observed': int(counts[n]),
            'expected': round(expected, 4),
            'chi2': round(float(contrib[n]), 4),
            'p_value': p_per[n],
            'q_value': q_per[n],
            'significant': bool(sig_mask[n]),
        })

    return {
        'test': 'uniformity_per_number',
        'n_draws': D,
        'expected_per_number': round(expected, 4),
        'min_count': int(counts.min()),
        'max_count': int(counts.max()),
        'chi2_stat': round(chi2_stat, 4),
        'df': N_NUMBERS - 1,
        'p_value': p_combined,
        'n_significant_bh': int(sum(sig_mask)),
        'per_number': per_number,
    }


# =====================================================================
# 2. 共现对均匀性
# =====================================================================

def _pair_counts_vectorized(history: Sequence[Dict]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """全量向量化计算 3160 个共现对的出现次数。

    返回 (pair_counts, pair_i, pair_j): pair_i/pair_j 是号码-1 索引 (i<j)。
    每期 20 个号产生 C(20,2)=190 对, 键 = i*80+j。
    """
    D = len(history)
    S = np.zeros((D, DRAWS_PER_PERIOD), dtype=np.int64)
    for r, h in enumerate(history):
        nums = sorted(int(n) for n in h.get('numbers', []) if 1 <= int(n) <= N_NUMBERS)
        if len(nums) < DRAWS_PER_PERIOD:
            nums = (nums + [0] * DRAWS_PER_PERIOD)[:DRAWS_PER_PERIOD]
        S[r] = [n - 1 for n in nums]
    S.sort(axis=1)

    ii, jj = np.triu_indices(DRAWS_PER_PERIOD, 1)  # 每期内 190 个位置对
    U = S[:, ii]   # (D, 190) 较小值
    V = S[:, jj]   # (D, 190) 较大值
    keys = (U * N_NUMBERS + V).ravel()
    flat = np.bincount(keys, minlength=N_NUMBERS * N_NUMBERS)

    pi, pj = np.triu_indices(N_NUMBERS, 1)  # 3160 个合法对
    pair_counts = flat[pi * N_NUMBERS + pj].astype(np.int64)
    return pair_counts, pi, pj


def pair_uniformity(history: Sequence[Dict], max_pairs: Optional[int] = 500,
                    random_state: int = 42) -> Dict:
    """检验共现对是否均匀。

    H0: 每对共现次数 ~ 期望 D*190/3160。对间不独立, 所以合并卡方只是
    近似体检; 另抽样 max_pairs 对做单对 p 值 + BH-FDR。
    """
    D = len(history)
    if D == 0:
        return {'error': 'empty history', 'n_draws': 0}

    pair_counts, pi, pj = _pair_counts_vectorized(history)
    expected = D * PAIRS_PER_DRAW / N_PAIRS_TOTAL
    contrib = (pair_counts - expected) ** 2 / expected
    chi2_stat = float(contrib.sum())
    df = N_PAIRS_TOTAL - 1
    p_combined = chi_square_sf(chi2_stat, df)

    # 抽样报告单对细节 (固定 random_state 保证可复现)
    rng = np.random.default_rng(random_state)
    n_sample = min(max_pairs or N_PAIRS_TOTAL, N_PAIRS_TOTAL)
    sample_idx = rng.choice(N_PAIRS_TOTAL, size=n_sample, replace=False)
    sample_idx.sort()

    p_sample = [chi_square_sf(float(contrib[i]), 1) for i in sample_idx]
    sig_mask, q_sample = bh_fdr(p_sample, alpha=FAMILY_ALPHA)

    pair_details = []
    for k, i in enumerate(sample_idx):
        pair_details.append({
            'pair': [int(pi[i]) + 1, int(pj[i]) + 1],
            'observed': int(pair_counts[i]),
            'expected': round(expected, 4),
            'chi2': round(float(contrib[i]), 4),
            'p_value': p_sample[k],
            'q_value': q_sample[k],
            'significant': bool(sig_mask[k]),
        })

    return {
        'test': 'pair_uniformity',
        'n_draws': D,
        'n_pairs': N_PAIRS_TOTAL,
        'pairs_per_draw': PAIRS_PER_DRAW,
        'expected_per_pair': round(expected, 4),
        'min_pair_count': int(pair_counts.min()),
        'max_pair_count': int(pair_counts.max()),
        'chi2_stat': round(chi2_stat, 4),
        'df': df,
        'p_value': p_combined,
        'n_sampled_pairs': int(n_sample),
        'n_significant_bh_in_sample': int(sum(sig_mask)),
        'sampled_pairs': pair_details,
    }


# =====================================================================
# 3. 单号游程检验 (Wald-Wolfowitz runs test)
# =====================================================================

def _chronological_binary(history: Sequence[Dict], number: int) -> np.ndarray:
    """按时间升序的 0/1 命中序列。history 默认期号降序, 这里反转。"""
    idx = int(number) - 1
    hist = list(reversed(list(history)))  # 升序: 旧 -> 新
    x = np.zeros(len(hist), dtype=np.int8)
    for i, h in enumerate(hist):
        for n in h.get('numbers', []):
            if int(n) - 1 == idx:
                x[i] = 1
                break
    return x


def _pick_typical_number(history: Sequence[Dict]) -> int:
    """挑出现次数最接近期望 D*0.25 的号 (最'普通'的号)。"""
    D = len(history)
    counts = _counts_per_number(history)
    expected = D * BASE_HIT_P
    return int(np.argmin(np.abs(counts - expected))) + 1


def runs_test(history: Sequence[Dict], number: Optional[int] = None) -> Dict:
    """对单个号的 0/1 序列做 Wald-Wolfowitz 游程检验。

    游程太少 -> 聚集 (该号爱连着开/不连着开); 游程太多 -> 交替过度。
    双侧 p 值用正态近似。
    """
    D = len(history)
    if D < 10:
        return {'error': 'too few draws', 'n_draws': D}
    if number is None:
        number = _pick_typical_number(history)

    x = _chronological_binary(history, number)
    n1 = int(x.sum())
    n0 = D - n1
    if n1 == 0 or n0 == 0:
        return {'error': 'degenerate sequence', 'number': int(number), 'n_draws': D}

    # 数游程
    runs = 1 + int(np.sum(x[1:] != x[:-1]))
    n = n1 + n0
    mean_r = 2.0 * n1 * n0 / n + 1.0
    var_r = (2.0 * n1 * n0 * (2.0 * n1 * n0 - n)) / (n * n * (n - 1.0))
    if var_r <= 0:
        return {'error': 'zero variance', 'number': int(number)}
    z = (runs - mean_r) / math.sqrt(var_r)
    p_two_sided = math.erfc(abs(z) / math.sqrt(2.0))

    return {
        'test': 'runs_test',
        'number': int(number),
        'n_draws': D,
        'hits': n1,
        'misses': n0,
        'runs_observed': int(runs),
        'runs_expected': round(mean_r, 4),
        'runs_var': round(var_r, 4),
        'z': round(z, 4),
        'p_value': p_two_sided,
        'interpretation': 'too_few_runs_clustered' if z < -1.96 else (
            'too_many_runs_alternating' if z > 1.96 else 'consistent_with_random'),
    }


# =====================================================================
# 4. 单号 lag-1 序列相关
# =====================================================================

def serial_correlation(history: Sequence[Dict], number: int) -> Dict:
    """该号相邻两期命中指示的 lag-1 自相关及显著性。

    r1 = corr(x_t, x_{t-1}); iid 零假设下 Var(r1) ≈ 1/n,
    z = r1*sqrt(n), 双侧正态近似 p 值 (对二值序列是近似, 仅作体检)。
    """
    D = len(history)
    if D < 10:
        return {'error': 'too few draws', 'n_draws': D}

    x = _chronological_binary(history, number).astype(np.float64)
    x0, x1 = x[:-1], x[1:]
    n = len(x0)
    m0, m1 = x0.mean(), x1.mean()
    v0 = ((x0 - m0) ** 2).sum()
    v1 = ((x1 - m1) ** 2).sum()
    if v0 <= 0 or v1 <= 0:
        return {'error': 'degenerate sequence', 'number': int(number), 'n_draws': D}
    r1 = float(((x0 - m0) * (x1 - m1)).sum() / math.sqrt(v0 * v1))
    z = r1 * math.sqrt(n)
    p_two_sided = math.erfc(abs(z) / math.sqrt(2.0))

    return {
        'test': 'serial_correlation',
        'number': int(number),
        'n_draws': D,
        'lag_pairs': int(n),
        'lag1_autocorr': round(r1, 6),
        'z': round(z, 4),
        'p_value': p_two_sided,
        'note': 'iid近似, Var(r1)≈1/n, 双侧正态近似',
    }


# =====================================================================
# 5. 窗口漂移检验
# =====================================================================

def window_drift(history: Sequence[Dict], window: int = 200) -> Dict:
    """按时间升序切不重叠窗口, 检验"高频号集中度"是否随时间漂移。

    方法:
    - 全局 top20 高频号集合;
    - 每个窗口计算 top20 号占总开出次数的比例 (期望≈0.25);
    - 齐性检验: 各窗口 top20 命中数做卡方齐性检验 (df = 窗口数-1);
    - 趋势检验: 集中度对窗口序号做线性回归, 斜率显著性用正态近似。
    """
    D = len(history)
    if D < 20:
        return {'error': 'too few draws', 'n_draws': D}

    # 窗口数太少时自动缩小窗口, 保证至少 ~4 个窗口
    w = int(window)
    if D // w < 2:
        w = max(10, D // 5)
    hist = list(reversed(list(history)))  # 升序
    n_win = D // w
    if n_win < 2:
        return {'error': 'not enough windows', 'n_draws': D, 'window': w}

    M = _binary_matrix(hist)  # D x 80
    total_counts = M.sum(axis=0)
    top20 = np.argsort(-total_counts)[:DRAWS_PER_PERIOD]  # 全局 top20 索引
    top_mask = np.zeros(N_NUMBERS, dtype=bool)
    top_mask[top20] = True

    # 每窗口: top20 命中数 c_w, 总开出 20*w 个
    windows = []
    shares = []
    for k in range(n_win):
        seg = M[k * w:(k + 1) * w]
        c_w = int(seg[:, top_mask].sum())
        total_picks = w * DRAWS_PER_PERIOD
        share = c_w / total_picks
        windows.append({
            'window_index': k,
            'start_issue': hist[k * w].get('issue'),
            'end_issue': hist[(k + 1) * w - 1].get('issue'),
            'top20_hits': c_w,
            'total_picks': total_picks,
            'top20_share': round(share, 4),
        })
        shares.append(share)

    shares_arr = np.array(shares)
    c = np.array([wd['top20_hits'] for wd in windows], dtype=np.float64)
    totals = np.array([wd['total_picks'] for wd in windows], dtype=np.float64)
    overall_prop = c.sum() / totals.sum()

    # 卡方齐性检验: 每窗口 top20 命中 vs 非 top20 命中, 期望按总体比例
    chi2_homog = 0.0
    for k in range(n_win):
        e_hit = totals[k] * overall_prop
        e_miss = totals[k] * (1.0 - overall_prop)
        o_hit = c[k]
        o_miss = totals[k] - c[k]
        if e_hit > 0:
            chi2_homog += (o_hit - e_hit) ** 2 / e_hit
        if e_miss > 0:
            chi2_homog += (o_miss - e_miss) ** 2 / e_miss
    df_homog = n_win - 1
    p_homog = chi_square_sf(chi2_homog, df_homog)

    # 线性趋势: share ~ window_index
    t = np.arange(n_win, dtype=np.float64)
    tm, sm = t.mean(), shares_arr.mean()
    sxx = ((t - tm) ** 2).sum()
    slope = float(((t - tm) * (shares_arr - sm)).sum() / sxx) if sxx > 0 else 0.0
    resid = shares_arr - (sm + slope * (t - tm))
    dof = max(1, n_win - 2)
    s2 = float((resid ** 2).sum() / dof)
    se_slope = math.sqrt(s2 / sxx) if sxx > 0 else float('nan')
    z_trend = slope / se_slope if se_slope and se_slope > 0 else 0.0
    p_trend = math.erfc(abs(z_trend) / math.sqrt(2.0))

    return {
        'test': 'window_drift',
        'n_draws': D,
        'window': w,
        'n_windows': n_win,
        'overall_top20_share': round(float(overall_prop), 4),
        'windows': windows,
        'homogeneity': {
            'method': 'chi_square_homogeneity(top20_hits vs rest, df=n_windows-1)',
            'chi2_stat': round(chi2_homog, 4),
            'df': df_homog,
            'p_value': p_homog,
        },
        'trend': {
            'method': 'OLS share~window_index, normal approx on slope',
            'slope_per_window': round(slope, 6),
            'z': round(z_trend, 4),
            'p_value': p_trend,
        },
    }


# =====================================================================
# 6. 汇总报告
# =====================================================================

def _family_pvalues(report_parts: Dict) -> Tuple[List[str], List[float]]:
    """收集各检验的代表性 p 值, 统一过 BH-FDR。"""
    names, ps = [], []
    uni = report_parts.get('uniformity_per_number', {})
    if 'p_value' in uni:
        names.append('uniformity_combined_gof')
        ps.append(float(uni['p_value']))
    pair = report_parts.get('pair_uniformity', {})
    if 'p_value' in pair:
        names.append('pair_uniformity_combined_gof')
        ps.append(float(pair['p_value']))
    runs = report_parts.get('runs_test', {})
    if 'p_value' in runs:
        names.append('runs_test')
        ps.append(float(runs['p_value']))
    ser = report_parts.get('serial_correlation', {})
    if 'p_value' in ser:
        names.append('serial_correlation_lag1')
        ps.append(float(ser['p_value']))
    drift = report_parts.get('window_drift', {})
    if 'p_value' in drift.get('homogeneity', {}):
        names.append('window_drift_homogeneity')
        ps.append(float(drift['homogeneity']['p_value']))
    if 'p_value' in drift.get('trend', {}):
        names.append('window_drift_trend')
        ps.append(float(drift['trend']['p_value']))
    return names, ps


def run_full_report(history: Optional[Sequence[Dict]] = None,
                    write: bool = True) -> Dict:
    """跑全部随机性体检, 返回结构化报告 dict。

    verdict:
      - 'anomaly_detected'        家族检验经 BH-FDR 后仍有 q<=0.05 的显著项;
      - 'consistent_with_random'  未发现可复现的非随机证据。
    """
    if history is None:
        history = load_history()
    D = len(history)

    uni = uniformity_per_number(history)
    pair = pair_uniformity(history, max_pairs=500, random_state=42)

    typical_num = _pick_typical_number(history) if D >= 10 else 1
    runs = runs_test(history, number=typical_num)
    ser = serial_correlation(history, number=typical_num)

    # 小样本自动缩窗, 保证窗口数足够
    w = 200 if D >= 800 else max(20, D // 5)
    drift = window_drift(history, window=w)

    parts = {
        'uniformity_per_number': uni,
        'pair_uniformity': pair,
        'runs_test': runs,
        'serial_correlation': ser,
        'window_drift': drift,
    }
    names, ps = _family_pvalues(parts)
    sig, qs = bh_fdr(ps, alpha=FAMILY_ALPHA) if ps else ([], [])
    family = {
        'alpha': FAMILY_ALPHA,
        'names': names,
        'p_values': [round(p, 8) for p in ps],
        'q_values': [round(q, 8) for q in qs],
        'significant': [bool(s) for s in sig],
    }

    verdict = 'anomaly_detected' if any(sig) else 'consistent_with_random'

    report = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'module': 'backend.core.draw_randomness',
        'n_draws': D,
        'n_numbers': N_NUMBERS,
        'base_hit_rate': BASE_HIT_P,
        'tests': parts,
        'family_bh_fdr': family,
        'verdict': verdict,
    }

    if write:
        try:
            out_dir = get_reports_dir()
            out_path = os.path.join(out_dir, 'draw_randomness_report.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            report['report_path'] = out_path
        except Exception as e:  # 落盘失败不影响返回
            report['report_path'] = None
            report['write_error'] = str(e)

    return report


# =====================================================================
# 7. CLI
# =====================================================================

def _fmt_p(p) -> str:
    try:
        p = float(p)
    except (TypeError, ValueError):
        return 'n/a'
    if p < 0.0001:
        return '<0.0001'
    return f'{p:.4f}'


def print_summary(report: Dict) -> None:
    """人类可读的中文摘要。"""
    print('=' * 64)
    print('  开奖随机性体检报告 (draw_randomness)')
    print('=' * 64)
    print(f"  历史期数        : {report.get('n_draws')}")
    print(f"  判定结论        : {report.get('verdict')}")
    print('-' * 64)

    t = report.get('tests', {})
    uni = t.get('uniformity_per_number', {})
    if 'p_value' in uni:
        print(f"  [1] 单号频数均匀性 (GOF 卡方 df={uni.get('df')})")
        print(f"      统计量={uni.get('chi2_stat')}  p={_fmt_p(uni.get('p_value'))}  "
              f"BH显著号数={uni.get('n_significant_bh')}")
        print(f"      计数范围    : {uni.get('min_count')} ~ {uni.get('max_count')} "
              f"(期望 {uni.get('expected_per_number')})")

    pair = t.get('pair_uniformity', {})
    if 'p_value' in pair:
        print(f"  [2] 共现对均匀性 ({pair.get('n_pairs')} 对, 抽样 {pair.get('n_sampled_pairs')})")
        print(f"      统计量={pair.get('chi2_stat')}  p={_fmt_p(pair.get('p_value'))}  "
              f"抽样BH显著对数={pair.get('n_significant_bh_in_sample')}")
        print(f"      对计数范围  : {pair.get('min_pair_count')} ~ {pair.get('max_pair_count')}")

    runs = t.get('runs_test', {})
    if 'p_value' in runs:
        print(f"  [3] 游程检验 (号 {runs.get('number')})")
        print(f"      游程 {runs.get('runs_observed')} vs 期望 {runs.get('runs_expected')}  "
              f"Z={runs.get('z')}  p={_fmt_p(runs.get('p_value'))}  -> {runs.get('interpretation')}")

    ser = t.get('serial_correlation', {})
    if 'p_value' in ser:
        print(f"  [4] lag-1 序列相关 (号 {ser.get('number')})")
        print(f"      r1={ser.get('lag1_autocorr')}  Z={ser.get('z')}  "
              f"p={_fmt_p(ser.get('p_value'))}")

    drift = t.get('window_drift', {})
    if 'n_windows' in drift:
        print(f"  [5] 窗口漂移 (窗口={drift.get('window')}, 窗口数={drift.get('n_windows')})")
        print(f"      齐性检验    : chi2={drift['homogeneity'].get('chi2_stat')} "
              f"p={_fmt_p(drift['homogeneity'].get('p_value'))}")
        print(f"      趋势检验    : 斜率={drift['trend'].get('slope_per_window')} "
              f"p={_fmt_p(drift['trend'].get('p_value'))}")

    fam = report.get('family_bh_fdr', {})
    if fam.get('names'):
        print('-' * 64)
        print('  家族检验 BH-FDR 汇总:')
        for name, p, q, s in zip(fam['names'], fam['p_values'], fam['q_values'], fam['significant']):
            mark = ' *显著*' if s else ''
            print(f"    {name:<32} p={p:<10} q={q:<10}{mark}")

    rp = report.get('report_path')
    if rp:
        print('-' * 64)
        print(f"  报告已落盘: {rp}")
    print('=' * 64)


def main() -> None:
    report = run_full_report(history=None, write=True)
    print_summary(report)


if __name__ == '__main__':
    main()
