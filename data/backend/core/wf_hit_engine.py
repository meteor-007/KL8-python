# -*- coding: utf-8 -*-
"""
统一样本外命中评估引擎 (Walk-Forward Hit Engine)
===================================================
多模块、多规则、多号码在同一批历史数据上反复筛选时, 纯随机也会产生若干
"看上去显著"的假阳性。本引擎提供**诚实、可复现**的单一入口:

- 滚动 Walk-Forward 逐期对账 (训练前段 / 测试后段, 严格无未来函数);
- 每模块/每条规则输出: 池化命中率、Lift、**95% CI 下界**、单侧 p 值、样本量 n;
- 跨模块/跨规则统一做 **BH-FDR 多重检验校正** (复用 core.multiple_testing);
- 归一化指标, 使"扩大池子 (top20/region) 虚高命中数"不再被当成优势;
- 杀号等"负向模块"采用**保留集**口径, 而非"杀号正确率" (随机杀 75% 本就达标)。

度量口径
--------
先验命中率 baseline = 单码随机命中率 (快乐8 = 20/80 = 0.25)。
单期: rate = hits / size ; lift_i = rate_i / baseline
池化: pooled_rate = total_hits / total_picks ; lift = pooled_rate / baseline
95%CI 下界: 对 Pooled_rate 取 Wilson 置信下限后除以 baseline -> lift_ci_lo。
p 值: 单侧检验 H0: pooled_rate <= baseline (正态近似 + 连续性校正)。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from core.multiple_testing import bh_fdr


def _wilson_lo(phat: float, n: int, z: float = 1.96) -> float:
    """Wilson score 区间下界 (对比例 phat, n 次独立试验)。"""
    if n <= 0:
        return 0.0
    z2 = z * z
    denom = 1.0 + z2 / n
    center = phat + z2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))
    return max(0.0, (center - margin) / denom)


def _wilson_hi(phat: float, n: int, z: float = 1.96) -> float:
    """Wilson score 区间上界 (对比例 phat, n 次独立试验)。"""
    if n <= 0:
        return 1.0
    z2 = z * z
    denom = 1.0 + z2 / n
    center = phat + z2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))
    return min(1.0, (center + margin) / denom)


def _one_sided_p(phat: float, p0: float, n: int) -> float:
    """池化命中率显著高于基线 p0 的单侧 p 值 (正态近似)。"""
    if n <= 0:
        return 1.0
    if phat <= p0:
        return 1.0
    sd = math.sqrt(p0 * (1 - p0) / n)
    if sd <= 0:
        return 1.0
    z = (phat - p0) / sd
    # 上尾概率 = 0.5 * erfc(z / sqrt(2))
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def period_hit_metrics(rec: Sequence[int], actual: Sequence[int],
                       is_kill: bool = False) -> Optional[Dict]:
    """单期命中度量。

    - pick 型: hit_count = |rec ∩ actual| (推荐出的号码中了几个)
    - kill 型: hit_count = |rec ∩ (全集\actual)| (杀掉的号码里"杀对"了几个)
    - 负向模块建议传 is_kill=False (保留集), 由上层自行决定口径。
    """
    rec = set(int(x) for x in rec)
    actual = set(int(x) for x in actual)
    size = len(rec)
    if size <= 0 or not actual:
        return None
    if is_kill:
        hit_count = sum(1 for x in rec if x not in actual)
    else:
        hit_count = sum(1 for x in rec if x in actual)
    return {
        "size": size,
        "hit_count": hit_count,
        "rate": hit_count / size if size else 0.0,
    }


def evaluate_series(series: Sequence[Dict], baseline: float = 0.25,
                    min_n: int = 30, alpha: float = 0.05,
                    is_kill: bool = False) -> Dict:
    """对一串 (period, recommended, actual) 记录求池化指标 + CI + p。

    series 元素: {"period": str, "recommended": [int], "actual": [int]}
    或 {"period": str, "recommended": [int]} + actual_map (见 evaluate_module)。
    """
    total_picks = 0
    total_hits = 0
    n_periods = 0
    per_period = []
    for row in series:
        actual = row.get("actual")
        if actual is None:
            continue
        m = period_hit_metrics(row.get("recommended", []), actual, is_kill=is_kill)
        if m is None:
            continue
        total_picks += m["size"]
        total_hits += m["hit_count"]
        n_periods += 1
        per_period.append({**m, "period": row.get("period")})

    if total_picks <= 0:
        return _blank_result(n_periods=n_periods)

    pooled_rate = total_hits / total_picks
    lift = pooled_rate / baseline if baseline else 1.0
    ci_lo = _wilson_lo(pooled_rate, total_picks)
    ci_hi = _wilson_hi(pooled_rate, total_picks)
    lift_ci_lo = ci_lo / baseline if baseline else 0.0
    lift_ci_hi = ci_hi / baseline if baseline else 0.0
    p_value = _one_sided_p(pooled_rate, baseline, total_picks)
    insufficient = total_picks < min_n
    significant = (not insufficient) and (lift_ci_lo > 1.0) and (p_value <= alpha)

    return {
        "n_periods": n_periods,
        "total_picks": total_picks,
        "total_hits": total_hits,
        "pooled_rate": round(pooled_rate, 4),
        "lift": round(lift, 4),
        "lift_ci_lo": round(lift_ci_lo, 4),
        "lift_ci_hi": round(lift_ci_hi, 4),
        "ci_lo": round(ci_lo, 4),
        "ci_hi": round(ci_hi, 4),
        "p_value": round(p_value, 6),
        "precision_gain": round((pooled_rate - baseline) * 100.0, 2),   # 百分点
        "expected_gain": round(lift - 1.0, 4),                          # Lift-1
        "insufficient": insufficient,
        "significant": significant,
        "alpha": alpha,
        "baseline": baseline,
        "is_kill": is_kill,
        "per_period": per_period,
    }


def evaluate_module(rows: Sequence[Dict], actual_map: Dict[str, Sequence[int]],
                    baseline: float = 0.25, min_n: int = 30,
                    alpha: float = 0.05, is_kill: bool = False) -> Dict:
    """将 (rows, actual_map) 归一为 series 后求指标。

    rows 元素: {"period": str, "recommended": [int], ...}
    actual_map: {"period": str -> [actual numbers]}
    """
    series = []
    for row in rows:
        p = str(row.get("period", ""))
        actual = actual_map.get(p)
        if not actual:
            continue
        series.append({"period": p, "recommended": row.get("recommended", []),
                       "actual": actual})
    return evaluate_series(series, baseline=baseline, min_n=min_n,
                           alpha=alpha, is_kill=is_kill)


def evaluate_from_counts(counts_series: Sequence[Dict], baseline: float = 0.25,
                         min_n: int = 30, alpha: float = 0.05,
                         is_kill: bool = False) -> Dict:
    """基于"每期 (size, hit_count)"直接求池化指标。

    用于那些只落盘了命中数/命中率、未落盘具体号码列表的模块 (如三维主系统
    的 review_*.json 只存 top12_hits/rate)。counts_series 元素:
    {"period": str, "size": int, "hit_count": int}
    """
    total_picks = 0
    total_hits = 0
    n_periods = 0
    for row in counts_series:
        size = int(row.get("size", 0) or 0)
        hit_count = int(row.get("hit_count", 0) or 0)
        if size <= 0:
            continue
        total_picks += size
        total_hits += hit_count
        n_periods += 1

    if total_picks <= 0:
        return _blank_result(n_periods=n_periods, is_kill=is_kill)

    pooled_rate = total_hits / total_picks
    lift = pooled_rate / baseline if baseline else 1.0
    ci_lo = _wilson_lo(pooled_rate, total_picks)
    ci_hi = _wilson_hi(pooled_rate, total_picks)
    lift_ci_lo = ci_lo / baseline if baseline else 0.0
    lift_ci_hi = ci_hi / baseline if baseline else 0.0
    p_value = _one_sided_p(pooled_rate, baseline, total_picks)
    insufficient = total_picks < min_n
    significant = (not insufficient) and (lift_ci_lo > 1.0) and (p_value <= alpha)

    return {
        "n_periods": n_periods,
        "total_picks": total_picks,
        "total_hits": total_hits,
        "pooled_rate": round(pooled_rate, 4),
        "lift": round(lift, 4),
        "lift_ci_lo": round(lift_ci_lo, 4),
        "lift_ci_hi": round(lift_ci_hi, 4),
        "ci_lo": round(ci_lo, 4),
        "ci_hi": round(ci_hi, 4),
        "p_value": round(p_value, 6),
        "precision_gain": round((pooled_rate - baseline) * 100.0, 2),
        "expected_gain": round(lift - 1.0, 4),
        "insufficient": insufficient,
        "significant": significant,
        "alpha": alpha,
        "baseline": baseline,
        "is_kill": is_kill,
        "per_period": [],
    }


def fdr_summarize(module_evals: Dict[str, Dict], alpha: float = 0.05) -> Dict:
    """跨模块 BH-FDR: 传入 {module_id -> evaluate_* 结果}, 回填 bh_q 与结论。"""
    ids = list(module_evals.keys())
    if not ids:
        return {"results": {}, "winning": []}
    p_values = [module_evals[i]["p_value"] for i in ids]
    significant_mask, q_values = bh_fdr(p_values, alpha=alpha)
    q_map = {i: round(q, 6) for i, q in zip(ids, q_values)}
    winning = []
    for i, sig in zip(ids, significant_mask):
        ev = module_evals[i]
        ev["bh_q"] = q_map[i]
        ev["bh_significant"] = bool(sig)
        # 判定: 显著 + 无样本不足 + CI下界>1
        ev["winner"] = bool(sig and not ev.get("insufficient") and ev["lift_ci_lo"] > 1.0)
        if ev["winner"]:
            winning.append(i)
    return {"results": module_evals, "winning": winning, "alpha": alpha}


def render_report(module_evals: Dict[str, Dict], winning: List[str]) -> str:
    """生成可读的命中率对账表文本。"""
    lines = []
    lines.append("# 各预测模块 样本外命中率对账表 (Walk-Forward)")
    lines.append("")
    lines.append("> 口径: 池化命中率 = Σ命中 / Σ推荐总数 | Lift = 命中率/基线 | "
                 "基线 = 单码随机命中率 (快乐8 = 25.0%)")
    lines.append("> 判定门槛: 样本 n ≥ 30 且 95%CI下界 > 1.0 且 BH-FDR q < 0.05 才判为优势。")
    lines.append("")
    hdr = f"| 模块 | 期数 | 推荐数 | 命中 | 命中率 | Lift | CI下界 | p值 | BH-q | 判定 |"
    lines.append(hdr)
    lines.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|---|")
    for mid, ev in module_evals.items():
        verdict = "✅ 优势" if mid in winning else (
            "⚠️ 样本不足" if ev.get("insufficient") else "❌ 无优势(贴基线)")
        lines.append(
            f"| {mid} | {ev.get('n_periods')} | {ev.get('total_picks')} | "
            f"{ev.get('total_hits')} | {ev.get('pooled_rate'):.2%} | "
            f"{ev.get('lift'):.2f}x | {ev.get('lift_ci_lo'):.2f}x | "
            f"{ev.get('p_value'):.4g} | {ev.get('bh_q', '-'):.4g} | {verdict} |")
    lines.append("")
    lines.append("## 结论")
    if winning:
        lines.append(f"经多重检验仍具优势的模块: `{', '.join(winning)}` (其余模块贴基线)。")
    else:
        lines.append("经多重检验后无模块显著优于随机基线; 系统应维持 FROZEN 防守并加大样本。")
    return "\n".join(lines)


def _blank_result(n_periods: int = 0, is_kill: bool = False) -> Dict:
    return {
        "n_periods": n_periods, "total_picks": 0, "total_hits": 0,
        "pooled_rate": 0.0, "lift": 1.0, "lift_ci_lo": 0.0, "lift_ci_hi": 1.0,
        "ci_lo": 0.0, "ci_hi": 1.0,
        "p_value": 1.0, "precision_gain": 0.0, "expected_gain": 0.0,
        "insufficient": True, "significant": False, "baseline": 0.25,
        "is_kill": is_kill, "per_period": [],
    }


if __name__ == "__main__":
    # 自测: 构造一个"纯随机"(应贴基线)与一个"显著优势"的样例
    import random
    random.seed(7)

    def null_series(p, size, pool=80, drawn=20):
        """真·随机基线: 从 80 码里随机挑 size 码, 与随机 20 码开奖对比。

        期望命中率 = size * (drawn/pool) / size = 25%, 即 Lift≈1.0。
        """
        rec = random.sample(range(1, pool + 1), size)
        actual = random.sample(range(1, pool + 1), drawn)
        return {"period": p, "recommended": rec, "actual": sorted(actual)}

    def biased_series(p, size, hits, pool=80, drawn=20):
        """显著优势: 先塞 hits 个必中码, 其余随机。"""
        actual = random.sample(range(1, pool + 1), drawn)
        must = random.sample(actual, min(hits, drawn))
        rest = random.sample([n for n in range(1, pool + 1) if n not in must],
                             size - len(must))
        return {"period": p, "recommended": must + rest, "actual": sorted(actual)}

    random_series = [null_series(f"T{i}", 12) for i in range(40)]
    good_series = [biased_series(f"G{i}", 12, 6) for i in range(40)]
    evals = {
        "null(应贴基线)": evaluate_series(random_series, baseline=0.25),
        "biased(应显著)": evaluate_series(good_series, baseline=0.25),
    }
    out = fdr_summarize(evals)
    print(render_report(out["results"], out["winning"]))
