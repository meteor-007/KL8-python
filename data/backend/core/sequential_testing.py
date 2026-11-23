# -*- coding: utf-8 -*-
"""
序贯检验 (Sequential Testing) — e-process / anytime-valid p-value
=====================================================================

背景: 每个预测模块每期给出 picks, 事后与开奖对账得 hits。每个 pick 是一次
伯努利试验, H0: 命中率 p = 0.25 (20/80 基线)。传统做法是攒够 200 期固定样本
再检验, 太死板——有效的模块要白等几个月, 无效的也要先浪费 200 期。

本模块用 e-process (e-value 过程) 做 anytime-valid 序贯检验:

- 每次观测 x ∈ {0,1}, 在备择假设网格 grid 上各自累乘似然比 LR;
- e 值 = 各备择 LR 的算术平均 (mixture martingale), Ville 不等式保证
  在任意时刻停止都不会放大 I 类错误;
- anytime_p ≈ min(1, 1/e_value), 达到 alpha 即可提前判 "显著有效";
- 命中率置信上界掉到 p0 以下, 或跑满足够期数 e 值仍≈1, 则判 "无希望" 提前止损。

数值上全程 log-space 累加, 5000+ 期也不会溢出。
"""
import json
import math
import os
import sys
from typing import Dict, List, Optional, Sequence

import numpy as np

if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, _ensure_project_path, get_cache_dir
_ensure_project_path()

__all__ = ["BernoulliEProcess", "summarize_ledger", "main"]

DEFAULT_GRID = (0.26, 0.28, 0.30, 0.33, 0.36, 0.40, 0.45)
DEFAULT_P0 = 0.25
DEFAULT_ALPHA = 0.05


# ---------------------------------------------------------------------------
# 正态分布工具 (没有 scipy, 自己实现)
# ---------------------------------------------------------------------------
def _norm_cdf(z: float) -> float:
    """标准正态 CDF, 用 math.erf 实现。"""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """标准正态分位数, 二分法反解 _norm_cdf, 精度 ~1e-10。"""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def hit_rate_ci_upper(hits: int, n: int, conf: float = 0.95) -> float:
    """命中率的正态近似单侧置信上界。

    hits=0 或 n=0 时做 Wilson 风格截断: 上界不超过 1, 下界不小于 0。
    """
    if n <= 0:
        return 1.0
    phat = hits / n
    z = _norm_ppf(0.5 + conf / 2.0)  # 双侧 conf → 上界用 1-(1-conf)/2
    se = math.sqrt(max(phat * (1.0 - phat), 1e-12) / n)
    upper = phat + z * se
    # 小样本下正态近似会偏窄, 加一点 Wilson 修正项兜底
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(phat * (1.0 - phat) / n + z * z / (4.0 * n * n))
    wilson_upper = min(1.0, center + half)
    # 取两者较大者: 判 futile 时宁可保守, 不让偏窄的上界误杀模块
    return min(1.0, max(0.0, max(upper, wilson_upper)))


# ---------------------------------------------------------------------------
# Bernoulli e-process
# ---------------------------------------------------------------------------
class BernoulliEProcess:
    """针对 H0: p=p0 的伯努利 e-process (e-value 过程)。

    参数
    ----
    p0 : float
        零假设命中率 (默认 0.25)。
    alpha : float
        显著性水平 (默认 0.05), e_value >= 1/alpha 即判显著。
    grid : Sequence[float] | None
        备择假设 p1 网格; None 用 DEFAULT_GRID。
    futile_n : int
        跑满该期数且 e_value 仍 <1 时判无望 (默认 200)。
    min_periods : int
        判定前的最少试验次数 (默认 30)。

    用法
    ----
    >>> ep = BernoulliEProcess()
    >>> for x in [1, 0, 1, 1]:
    ...     ep.update(x)
    >>> ep.e_value(), ep.anytime_p(), ep.decision()
    """

    def __init__(self, p0: float = DEFAULT_P0, alpha: float = DEFAULT_ALPHA,
                 grid: Optional[Sequence[float]] = None,
                 futile_n: int = 200, min_periods: int = 30):
        self.p0 = float(p0)
        self.alpha = float(alpha)
        self.futile_n = int(futile_n)
        self.min_periods = int(min_periods)
        g = list(grid) if grid is not None else list(DEFAULT_GRID)
        # 过滤掉和 p0 相同或越界的备择, 避免 LR 恒为 1 白占坑
        self.grid = [float(p) for p in g
                     if 0.0 < float(p) < 1.0 and abs(float(p) - self.p0) > 1e-12]
        if not self.grid:
            self.grid = [min(0.99, self.p0 + 0.05), max(0.01, self.p0 - 0.05)]
        k = len(self.grid)
        # 每个备择的累积 log 似然比; e = mean(exp(log_lr))
        self._log_lrs = np.zeros(k, dtype=np.float64)
        self.n = 0
        self.hits = 0

    # -- 单步更新 ---------------------------------------------------------
    def update(self, x: int) -> "BernoulliEProcess":
        """喂入一个观测 x∈{0,1}。返回 self 便于链式调用。"""
        x = 1 if int(x) else 0
        self.n += 1
        self.hits += x
        p0 = self.p0
        for i, p1 in enumerate(self.grid):
            if x:
                llr = math.log(p1 / p0)
            else:
                llr = math.log((1.0 - p1) / (1.0 - p0))
            self._log_lrs[i] += llr
        return self

    def update_many(self, xs: Sequence[int]) -> "BernoulliEProcess":
        """批量喂入序列。"""
        for x in xs:
            self.update(x)
        return self

    # -- 当前统计量 -------------------------------------------------------
    def e_value(self) -> float:
        """当前 e 值 = 各备择似然比的算术平均 (logsumexp 稳定计算)。"""
        if self.n == 0:
            return 1.0
        m = float(np.max(self._log_lrs))
        # log( mean(exp(l_i)) ) = m + log(sum(exp(l_i - m))) - log(k)
        log_e = m + math.log(float(np.sum(np.exp(self._log_lrs - m)))) - math.log(len(self.grid))
        # 上限截断: e 值理论上可任意大, 但超过 1e300 没有意义
        if log_e > 700:
            return float("inf")
        return math.exp(log_e)

    def anytime_p(self) -> float:
        """anytime-valid p ≈ min(1, 1/e_value) (Ville 不等式)。"""
        e = self.e_value()
        if e <= 0.0 or math.isinf(e):
            return 0.0 if math.isinf(e) else 1.0
        return min(1.0, 1.0 / e)

    def mle_hit_rate(self) -> float:
        """当前样本命中率。"""
        return self.hits / self.n if self.n else 0.0

    # -- 序贯判定 ---------------------------------------------------------
    def decision(self, min_periods: Optional[int] = None) -> Dict:
        """返回当前序贯判定。

        status:
          - 'significant': e_value >= 1/alpha 且 n >= min_periods → 显著有效
          - 'futile'     : n >= min_periods 且 命中率95%置信上界 < p0,
                           或 n >= futile_n 且 e_value < 1 → 无希望
          - 'continue'   : 继续观察
        """
        mp = self.min_periods if min_periods is None else int(min_periods)
        e = self.e_value()
        ap = self.anytime_p()
        result = {
            "status": "continue",
            "n": self.n,
            "hits": self.hits,
            "hit_rate": self.mle_hit_rate(),
            "e_value": e,
            "anytime_p": ap,
            "alpha": self.alpha,
            "threshold": 1.0 / self.alpha,
            "reason": "样本不足或证据未达阈值, 继续观察",
        }
        if self.n < mp:
            result["reason"] = f"样本量 n={self.n} < min_periods={mp}"
            return result

        # 1) 显著有效
        if e >= 1.0 / self.alpha:
            result["status"] = "significant"
            result["reason"] = f"e_value={e:.3g} >= 1/alpha={1.0/self.alpha:.3g}"
            return result

        # 2) 无希望 — 两条路:
        #    a) 命中率的 95% 置信上界已经低于 p0, 再攒也翻不了身
        ci_upper = hit_rate_ci_upper(self.hits, self.n, conf=0.95)
        result["ci_upper_95"] = ci_upper
        if ci_upper < self.p0:
            result["status"] = "futile"
            result["reason"] = (f"命中率95%置信上界 {ci_upper:.4f} < p0={self.p0}"
                                f" (n={self.n}, hits={self.hits})")
            return result

        #    b) 跑满 futile_n 期 e 值仍≈1, 备择下基本不涨, 认命
        if self.n >= self.futile_n and e < 1.0:
            result["status"] = "futile"
            result["reason"] = (f"n={self.n} >= futile_n={self.futile_n} "
                                f"且 e_value={e:.3g} < 1, 证据停滞")
            return result

        result["reason"] = "证据介于两可之间, 继续观察"
        return result


# ---------------------------------------------------------------------------
# 前瞻账本汇总
# ---------------------------------------------------------------------------
def _iter_ledger(jsonl_path: str):
    """逐行 yield jsonl 记录, 跳过坏行。"""
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def summarize_ledger(jsonl_path: Optional[str] = None,
                     min_picks: int = 30,
                     p0: float = DEFAULT_P0,
                     alpha: float = DEFAULT_ALPHA) -> Dict[str, Dict]:
    """读取 paper_trading_modules.jsonl, 按 module 汇总序贯检验结果。

    参数
    ----
    jsonl_path : str | None
        jsonl 路径; None 时用 storage/cache/paper_trading_modules.jsonl。
    min_picks : int
        每个 module 至少需要的 pick 数才纳入汇总 (默认 30)。
    p0, alpha : float
        透传给 BernoulliEProcess。

    返回
    ----
    {module_id: {n, hits, hit_rate, e_value, anytime_p, decision, ...}}
    按 e_value 降序; 文件不存在或无有效数据返回 {}。
    """
    if jsonl_path is None:
        jsonl_path = os.path.join(get_cache_dir(), "paper_trading_modules.jsonl")
    if not os.path.exists(jsonl_path):
        return {}

    # module -> list of (pick, actual_set) 展平后的 0/1 序列稍后统一算
    module_trials: Dict[str, List[int]] = {}
    for rec in _iter_ledger(jsonl_path):
        module = rec.get("module")
        picks = rec.get("picks") or []
        actual = rec.get("actual") or []
        if not module or not picks or not actual:
            continue
        actual_set = set(int(a) for a in actual)
        seq = module_trials.setdefault(str(module), [])
        for pk in picks:
            seq.append(1 if int(pk) in actual_set else 0)

    out: Dict[str, Dict] = {}
    for module, seq in module_trials.items():
        n = len(seq)
        if n < min_picks:
            continue
        ep = BernoulliEProcess(p0=p0, alpha=alpha)
        ep.update_many(seq)
        dec = ep.decision()
        out[module] = {
            "n": n,
            "hits": ep.hits,
            "hit_rate": ep.mle_hit_rate(),
            "e_value": ep.e_value(),
            "anytime_p": ep.anytime_p(),
            "decision": dec["status"],
            "decision_reason": dec["reason"],
            "ci_upper_95": dec.get("ci_upper_95"),
        }

    # 按 e_value 降序
    return dict(sorted(out.items(), key=lambda kv: kv[1]["e_value"], reverse=True))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    """命令行入口: 打印各模块 e_value / anytime_p / decision 中文表格。"""
    result = summarize_ledger()
    if not result:
        print("未找到 paper_trading_modules.jsonl 或无满足 min_picks 的模块。")
        return 0

    header = (f"{'module':<28} {'n':>6} {'hits':>6} {'hit_rate':>9} "
              f"{'e_value':>12} {'anytime_p':>10} {'decision':<12} reason")
    print(header)
    print("-" * len(header))
    status_cn = {"significant": "显著有效", "futile": "无希望", "continue": "继续观察"}
    for module, info in result.items():
        ev = info["e_value"]
        ev_s = f"{ev:.4g}" if math.isfinite(ev) else "inf"
        dec_cn = status_cn.get(info["decision"], info["decision"])
        print(f"{module:<28} {info['n']:>6} {info['hits']:>6} "
              f"{info['hit_rate']:>9.4f} {ev_s:>12} "
              f"{info['anytime_p']:>10.4f} {dec_cn:<12} {info['decision_reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
