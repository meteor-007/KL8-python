# -*- coding: utf-8 -*-
"""
CPCV + PBO + DSR — 反"选配置偏差"统计工具箱
============================================
大白话:
  我们有 ~32 个预测模块(策略), 每个模块每期产出 picks, 和实际开奖对账,
  算出 lift(命中率 / 0.25 基线)。但现在的问题是:
  我们试了很多配置、看了很多历史, 最后挑了"看起来最好的"模块。
  就算所有模块都是纯噪声, 挑出来的那个也会"显得"有点厉害 ——
  这就是"选择偏差 / 回测过拟合"。

本模块补两个武器(都是 Marcos López de Prado《Advances in Financial
Machine Learning》里的经典方法, 但没有 scipy, 纯 numpy 手撸):

  1) CPCV + PBO (CSCV): 组合式净化交叉验证 + 回测过拟合概率。
     把时间轴切成 S 组, 枚举所有"一半当样本内(IS)选最优、一半当
     样本外(OOS)看表现"的对称划分。统计: IS 里选出来的冠军, 到 OOS
     还排在前一半的概率有多大? 如果 PBO 高, 说明"选最优"这件事
     本身在过拟合, 别太信 leaderboard 第一名。

  2) DSR (Deflated Sharpe Ratio): 把"最优模块"的 Sharpe, 和
     "如果你试了 N 次无效策略, 纯靠运气期望能摸到的最大 Sharpe"
     做比较。DSR 就是校正了试验次数后的显著性。

数据来源:
  storage/cache/paper_trading_modules.jsonl
  每行 {"period","module","picks","actual","hits"}, 未开奖的行
  actual/hits 为 None, 会被跳过。
  per-period lift = (hits / len(picks)) / 0.25
  注意 picks 里有重复号码时, 命中率分母仍按 len(picks) 算(与
  现有 ledger 口径一致, hits 是 picks 与 actual 的交集计数)。
"""
import itertools
import json
import math
import os
import random
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, _ensure_project_path  # noqa: E402

_ensure_project_path()

BASELINE_HIT_RATE = 0.25  # KL8 随机基线: 20 个号里随便挑, 每个号命中概率 1/20? 实际口径: 每期20个开奖号
# 注: 项目内 lift 口径 = 实际命中率 / 0.25, 与 master_review_ledger 一致。

EULER_GAMMA = 0.5772156649015329  # Euler-Mascheroni 常数


# ---------------------------------------------------------------------------
# 1. 正态分布工具 (无 scipy, 用 math.erf + Acklam 有理逼近)
# ---------------------------------------------------------------------------

def norm_cdf(x: float) -> float:
    """标准正态 CDF: Φ(x) = 0.5 * (1 + erf(x / sqrt(2)))."""
    return 0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """标准正态逆 CDF Φ^{-1}(p): 对 norm_cdf 做二分求逆, 精度 ~1e-7.

    无 scipy 环境下的稳妥实现 (与 sequential_testing._norm_ppf 同思路);
    Acklam 有理逼近更快但此处调用频率低, 二分足够。
    """
    p = float(p)
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# 2. CPCV: 组合式净化交叉验证 (purge 防泄露)
# ---------------------------------------------------------------------------

def cpcv_split_indices(n: int, n_groups: int = 10, k_test: int = 2,
                       purge: int = 0) -> List[Tuple[np.ndarray, np.ndarray]]:
    """组合式 CV 切分.

    把 n 个按时间排序的点切成 n_groups 个连续(contiguous)组,
    枚举所有 C(n_groups, k_test) 种"测试组"组合, 其余组做训练。
    purge>0 时, 从训练集中剔除每个测试块前后各 purge 个点
    (防止相邻信息泄露, 对应 AFML 的 purge-and-embargo 思想)。

    参数:
        n: 时间点总数
        n_groups: 组数 (建议 5~16)
        k_test: 每次留出做测试的组数
        purge: 每个测试块前后剔除的训练点数

    返回:
        list of (train_idx, test_idx), 均为 np.ndarray(int), 按时间升序。
    """
    if n_groups < 2 or k_test < 1 or k_test >= n_groups:
        raise ValueError("需要 n_groups>=2 且 1<=k_test<n_groups")
    if purge < 0:
        raise ValueError("purge 必须 >=0")

    # 1) 按时间顺序把 n 个点切成 n_groups 个连续块
    bounds = np.linspace(0, n, n_groups + 1, dtype=int)  # n_groups+1 个边界
    group_ranges = [(int(bounds[g]), int(bounds[g + 1])) for g in range(n_groups)]

    splits = []
    all_idx = np.arange(n)
    for test_groups in itertools.combinations(range(n_groups), k_test):
        # 测试集 = 选中的组拼起来
        test_idx = np.concatenate([np.arange(group_ranges[g][0], group_ranges[g][1])
                                   for g in test_groups])
        test_mask = np.zeros(n, dtype=bool)
        test_mask[test_idx] = True
        # purge: 每个测试块的前后 purge 个点不许进训练集
        purge_mask = np.zeros(n, dtype=bool)
        for g in test_groups:
            lo, hi = group_ranges[g]  # [lo, hi)
            purge_mask[max(0, lo - purge):lo] = True
            purge_mask[hi:min(n, hi + purge)] = True
        train_mask = ~(test_mask | purge_mask)
        train_idx = all_idx[train_mask]
        # 保持时间顺序
        splits.append((train_idx, np.sort(test_idx)))
    return splits


# ---------------------------------------------------------------------------
# 3. PBO via CSCV (组合对称交叉验证, López de Prado AFML ch.11 / CSCV)
# ---------------------------------------------------------------------------

def pbo_cscv(perf_matrix: np.ndarray, S: int = 16,
             max_splits: int = 5000,
             seed: Optional[int] = None) -> Dict:
    """Probability of Backtest Overfitting (CSCV 法).

    perf_matrix: shape (n_periods, n_configs)。每列一个策略/模块的
        逐期表现(可以是 lift-1 的超额收益, 也可以是命中 0/1 指标,
        调用方负责准备; 本函数只对每半边取列均值做排名)。

    步骤:
      1) 时间轴截成 S 组等长块(不足 S*block 的尾巴丢弃);
      2) 枚举 C(S, S/2) 个"一半 IS / 一半 OOS"对称划分
         (IS 与 OOS 互换是同一个划分, 但对 PBO 无影响, 全枚举也行;
         超过 max_splits 时用固定 seed 随机采样, 并在 note 里注明);
      3) 每个划分: IS 半边选均值最高的列当"冠军", 看它在 OOS 半边
         的排名 ω ∈ (0,1) (ω=1 表示 OOS 也最强);
      4) λ = ln(ω/(1-ω)), PBO = P(λ <= 0), 即冠军在 OOS 跌到
         中位数以下的比例。PBO 越高, 说明"挑最优"越像过拟合。

    返回: {'pbo': float, 'n_splits': int, 'lambda_mean': float, 'note': str}
    """
    M = np.asarray(perf_matrix, dtype=float)
    if M.ndim != 2:
        raise ValueError("perf_matrix 必须是 2 维 (n_periods, n_configs)")
    T, N = M.shape
    if T < S or N < 2:
        raise ValueError(f"需要 n_periods>={S} 且 n_configs>=2, 实际 T={T}, N={N}")
    if S % 2 != 0:
        raise ValueError("S 必须为偶数")

    k = S // 2
    block = T // S
    T_use = block * S
    M = M[:T_use, :]

    # 每个配置在每组上的均值: shape (S, N)
    group_means = M.reshape(S, block, N).mean(axis=1)

    # 枚举/采样划分: 选 k 组做 IS, 其余做 OOS
    all_combos = list(itertools.combinations(range(S), k))
    total = len(all_combos)
    note_parts = []
    rng = random.Random(seed)
    if total > max_splits:
        combos = rng.sample(all_combos, max_splits)
        note_parts.append(f"C({S},{k})={total} 超过 max_splits={max_splits}, "
                          f"随机采样 {max_splits} 个划分(seed={seed})")
    else:
        combos = all_combos
        note_parts.append(f"全枚举 C({S},{k})={total} 个划分")
    # 对称划分 (IS,OOS) 与 (OOS,IS) 等价, 去重可再省一半;
    # 但全枚举下两者 λ 互为相反数, PBO 结果不变, 保留简单起见不去重。

    lambdas = []
    for is_groups in combos:
        oos_groups = tuple(g for g in range(S) if g not in is_groups)
        is_perf = group_means[list(is_groups), :].mean(axis=0)   # (N,)
        oos_perf = group_means[list(oos_groups), :].mean(axis=0)  # (N,)
        best = int(np.argmax(is_perf))
        # OOS 排名: 比 best 差的列数 -> ω = (rank)/(N-1)? 标准做法:
        # ω = (1 + #{列 OOS 表现 <= best 的 OOS 表现}) / (N+1)? 
        # 用 CSCV 原始定义: ω = rank/(N+1) 风格会偏; 这里用
        # ω = (#列 OOS 均值严格小于 best) / (N-1) 映射到 (0,1),
        # 取中位校正: ω = (1 + count_less) / (N + 1) 保证落在 (0,1)。
        count_less = int(np.sum(oos_perf < oos_perf[best]))
        omega = (1.0 + count_less) / (N + 1.0)
        omega = min(max(omega, 1e-12), 1.0 - 1e-12)
        lambdas.append(math.log(omega / (1.0 - omega)))

    lambdas = np.asarray(lambdas)
    pbo = float(np.mean(lambdas <= 0.0))
    return {
        "pbo": pbo,
        "n_splits": len(combos),
        "lambda_mean": float(np.mean(lambdas)),
        "note": "; ".join(note_parts),
    }


# ---------------------------------------------------------------------------
# 4. DSR: Deflated Sharpe Ratio (Bailey & López de Prado, 2014)
# ---------------------------------------------------------------------------

def deflated_sharpe(sr_obs: float, n_obs: int, sr_trials: Sequence[float],
                    skew: float = 0.0, kurt: float = 3.0) -> Dict:
    """Deflated Sharpe Ratio.

    sr_obs: 观察到的逐期 Sharpe (mean/std, 已是每期口径)
    n_obs:  该 Sharpe 对应的样本期数
    sr_trials: 所有"试过"的策略/配置的 Sharpe 列表 (含本策略自己也行,
               用于估计"N 次无效试验下期望最大 Sharpe"的方差 V)
    skew/kurt: 收益分布的偏度/峰度 (超额峰度, 正态=3)

    步骤:
      PSR(s*) = Φ( (sr_obs - s*) * sqrt(n-1)
                   / sqrt(1 - skew*sr_obs + (kurt-1)/4 * sr_obs^2) )
      E[max SR | H0] ≈ sqrt(V) * ((1-γ) Φ^{-1}(1-1/N) + γ Φ^{-1}(1-1/(N e)))
      DSR = PSR(s* = E[max])

    返回 {'psr','sr0','dsr','n_trials'}
    """
    sr_obs = float(sr_obs)
    n_obs = int(n_obs)
    trials = [float(x) for x in sr_trials if np.isfinite(x)]
    N = len(trials)
    if N == 0:
        raise ValueError("sr_trials 不能为空")

    denom = math.sqrt(max(1e-12,
                          1.0 - skew * sr_obs + (kurt - 1.0) / 4.0 * sr_obs * sr_obs))

    def _psr(s_star: float) -> float:
        z = (sr_obs - s_star) * math.sqrt(max(n_obs - 1, 1)) / denom
        return float(norm_cdf(z))

    # PSR(0): 相对"Sharpe=0"的显著性
    psr = _psr(0.0)

    # H0 下 N 次试验的期望最大 Sharpe (Bailey & LdP 2014, 用 Euler-Mascheroni)
    if N == 1:
        sr0 = 0.0  # 只试了一次, 没有"挑出来"的偏差可校正
    else:
        V = float(np.var(trials, ddof=1))
        if V <= 0.0:
            sr0 = 0.0
        else:
            sr0 = math.sqrt(V) * (
                (1.0 - EULER_GAMMA) * norm_ppf(1.0 - 1.0 / N)
                + EULER_GAMMA * norm_ppf(1.0 - 1.0 / (N * math.e))
            )
    dsr = _psr(sr0)
    return {"psr": psr, "sr0": float(sr0), "dsr": dsr, "n_trials": N}


# ---------------------------------------------------------------------------
# 5. 有效独立试验数估计
# ---------------------------------------------------------------------------

def effective_n_trials(series_dict: Dict[str, np.ndarray],
                       baseline: float = BASELINE_HIT_RATE) -> float:
    """估计"有效独立试验数" —— 32 个模块其实高度相关, 不能当 32 次
    独立试验来算 DSR 的 N。

    输入: {module_id: per-period 超额收益数组 = lift - 1}
    (baseline 参数保留兼容, lift-1 已经是超额, 不再使用;
     若传入的是原始 lift 请自行先减 1。)

    方法(设计效应 design-effect 公式, 与 survey 采样常用口径一致):
      ρ̄ = 所有两两 Pearson 相关系数的均值(取绝对值, 因为负相关
           也意味着"不是独立信息"的另一面; 实际实现见下)
      N_eff = N * (1 - ρ̄) / (1 + (N - 1) * ρ̄)
      其中 ρ̄ 取两两相关的均值, 裁剪到 [0, 0.999] 防止除零/爆炸;
      N_eff 裁剪到 [1, N]。

    返回 float。
    """
    keys = [k for k, v in series_dict.items()
            if v is not None and len(np.asarray(v)) >= 3]
    N = len(keys)
    if N <= 1:
        return float(max(N, 0))

    # 对齐到公共长度(取每列前 min_len 个点的简单截断,
    # 与 evaluate_modules 的 n_obs=min 口径一致)
    min_len = min(len(np.asarray(series_dict[k])) for k in keys)
    cols = [np.asarray(series_dict[k], dtype=float)[:min_len] for k in keys]

    corrs = []
    for i in range(N):
        for j in range(i + 1, N):
            xi, xj = cols[i], cols[j]
            si, sj = xi.std(), xj.std()
            if si <= 0 or sj <= 0:
                continue
            c = float(np.corrcoef(xi, xj)[0, 1])
            if np.isfinite(c):
                corrs.append(abs(c))
    if not corrs:
        return float(N)
    rho_bar = float(np.mean(corrs))
    rho_bar = min(max(rho_bar, 0.0), 0.999)
    n_eff = N * (1.0 - rho_bar) / (1.0 + (N - 1.0) * rho_bar)
    return float(min(max(n_eff, 1.0), float(N)))


# ---------------------------------------------------------------------------
# 6. 便捷入口: evaluate_modules
# ---------------------------------------------------------------------------

def evaluate_modules(series_dict: Dict[str, Sequence[float]],
                     baseline: float = BASELINE_HIT_RATE) -> Dict:
    """对每个模块算逐期 Sharpe 并跑 DSR。

    输入: {module_id: per-period lift 序列} (lift = 命中率/0.25,
          未减基线; 本函数内部转成 lift-1 超额收益再算 Sharpe,
          这样 Sharpe 衡量的是"跑赢随机基线"的稳定性)。

    逐期 Sharpe = mean(超额) / std(超额); std=0 或样本<3 期记 nan 跳过。
    sr_trials = 所有有效模块的 Sharpe 列表; n_obs = 最短序列长度
    (保守口径, 保证每个 Sharpe 都有这么多期支撑)。

    返回: {module_id: {'sharpe','psr','dsr','n'}, ...}
          额外键 '_meta': {'n_trials','effective_n','baseline','note'}
    """
    # 转成超额收益 lift-1
    excess = {}
    for k, v in series_dict.items():
        arr = np.asarray(v, dtype=float)
        arr = arr[np.isfinite(arr)]
        if len(arr) >= 3:
            excess[k] = arr - 1.0

    sharpes = {}
    for k, x in excess.items():
        sd = float(x.std(ddof=1))
        sharpes[k] = float(x.mean() / sd) if sd > 0 else float("nan")

    valid = {k: s for k, s in sharpes.items() if np.isfinite(s)}
    trials = list(valid.values())
    n_obs = min((len(excess[k]) for k in valid), default=0)

    n_eff = effective_n_trials(excess, baseline=baseline)

    out: Dict = {}
    for k in valid:
        res = deflated_sharpe(valid[k], n_obs, trials)
        out[k] = {
            "sharpe": valid[k],
            "psr": res["psr"],
            "dsr": res["dsr"],
            "sr0": res["sr0"],
            "n": int(len(excess[k])),
        }
    # 按 dsr 降序
    sorted_items = sorted(out.items(), key=lambda kv: kv[1]["dsr"], reverse=True)
    result = {k: v for k, v in sorted_items}
    result["_meta"] = {
        "n_trials": len(valid),
        "effective_n": round(n_eff, 3),
        "n_obs": int(n_obs),
        "baseline": baseline,
        "note": ("sharpe/dsr 基于 lift-1 超额收益; sr_trials=全部有效模块 "
                 "Sharpe; effective_n 用两两|相关|均值的设计效应公式估计"),
    }
    return result


# ---------------------------------------------------------------------------
# 7. 数据加载: 从 paper_trading_modules.jsonl 聚合逐期 lift
# ---------------------------------------------------------------------------

def load_module_lift_series(jsonl_path: Optional[str] = None,
                            project_root: Optional[str] = None) -> Dict[str, np.ndarray]:
    """从 paper_trading_modules.jsonl 读逐期记录, 聚合成
    {module_id: np.array([period1_lift, period2_lift, ...])}。

    每行需含 module/picks/actual/hits; actual 或 hits 为 None
    (未开奖) 的行跳过; picks 为空的行跳过。
    lift = (hits / len(picks)) / 0.25, 与 master_review_ledger 口径一致。
    同一 (period, module) 出现多行时取最后一行(覆盖式更新)。
    返回按期升序排列的 lift 序列。
    """
    root = project_root or get_project_root()
    if jsonl_path is None:
        jsonl_path = os.path.join(root, "storage", "cache",
                                  "paper_trading_modules.jsonl")
    # period -> module -> lift, 用 dict 去重后按期排序
    per_module: Dict[str, Dict[str, float]] = {}
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            module = row.get("module")
            hits = row.get("hits")
            picks = row.get("picks")
            period = str(row.get("period", ""))
            if not module or hits is None or not picks or not period:
                continue
            try:
                rate = float(hits) / float(len(picks))
            except (TypeError, ZeroDivisionError):
                continue
            lift = rate / BASELINE_HIT_RATE
            per_module.setdefault(module, {})[period] = lift

    out = {}
    for module, pdict in per_module.items():
        periods = sorted(pdict.keys())
        out[module] = np.array([pdict[p] for p in periods], dtype=float)
    return out


# ---------------------------------------------------------------------------
# 8. CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """命令行入口: 加载真实数据, 打印 DSR / PBO 中文摘要。"""
    series = load_module_lift_series()
    if not series:
        print("未找到 paper_trading_modules.jsonl 或无有效数据。")
        return

    print("=" * 70)
    print("KL8 模块 DSR 评估 (Deflated Sharpe, 校正多重试验偏差)")
    print("=" * 70)
    print(f"模块数: {len(series)}")
    lens = {k: len(v) for k, v in series.items()}
    print(f"各模块样本期数范围: {min(lens.values())} ~ {max(lens.values())}")

    result = evaluate_modules(series)
    meta = result.pop("_meta")
    print(f"有效模块(>=3期且std>0): {meta['n_trials']}, "
          f"估计有效独立试验数: {meta['effective_n']}, "
          f"n_obs(最短序列): {meta['n_obs']}")
    print("-" * 70)
    print(f"{'module':<28}{'sharpe':>8}{'psr':>8}{'dsr':>8}{'n':>5}")
    for k, v in result.items():
        print(f"{k:<28}{v['sharpe']:>8.3f}{v['psr']:>8.3f}"
              f"{v['dsr']:>8.3f}{v['n']:>5}")
    print("-" * 70)
    print("注: dsr 是校正了 '试了 N 次挑最优' 偏差后的显著性; "
          "dsr<0.95 基本可认为是运气。")

    # PBO: 需要矩阵对齐, 用公共前缀长度
    # 只保留样本够长的模块, 避免被短序列模块把公共长度拖没
    keys = [k for k in result.keys() if len(series[k]) >= 16]
    min_len = min(len(series[k]) for k in keys) if keys else 0
    if min_len >= 16 and len(keys) >= 2:
        mat = np.column_stack([series[k][:min_len] - 1.0 for k in keys])
        S = min(16, min_len // 4 * 4)
        if S >= 8:
            r = pbo_cscv(mat, S=S, max_splits=5000, seed=42)
            print("-" * 70)
            print(f"PBO (CSCV, S={S}, 矩阵 {min_len}期 x {len(keys)}模块, "
                  f"超额=lift-1): {r['pbo']:.3f}  ({r['n_splits']} splits)")
            print(f"  {r['note']}")
            print("  PBO 越接近 1, '选最优模块'越像过拟合; "
                  "<0.2 说明样本内外排名还算稳。")


if __name__ == "__main__":
    main()
