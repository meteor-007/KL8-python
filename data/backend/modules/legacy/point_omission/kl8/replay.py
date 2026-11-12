# -*- coding: utf-8 -*-
"""滚动外样本回测（§9.2–§9.4）。

三条不可违反的纪律：
  1. **严格小于**  预测第 P 期只允许用 period < P 的历史
  2. **每期重算**  base_stats / 马尔可夫状态 / Exp3 权重都在每个 P 上重新计算
  3. **配置冻结**  回测期间不得依据回测结果调整权重或阈值

实盘与回测共用同一套 registry.run_all 调度，保证代码路径一致。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date as _date

from .contracts import ModuleResult, NumberGateStats
from .data_io import Draw, PointEntry
from .ensemble import MAIN_METHODS, Exp3State, FusionResult, fuse
from .numerics import finite
from .points import compute_base_stats, expand
from .scoring import Pick52, Selection, select_52, select_top5
from .stats_tests import TestResult, all_insignificant, evaluate, evaluate_methods
from .baselines import BaselineReport, build_baselines
from . import observability, registry

DEFAULT_WARMUP = 60


@dataclass
class PeriodRecord:
    period: int
    date_str: str
    top5: list[int]
    hits: int
    core5_hits: int
    defensive_hits: int
    expanded_hits: int
    points20_hits: int
    expanded_size: int
    per_method_hits: dict[str, int] = field(default_factory=dict)
    per_method_top5: dict[str, list[int]] = field(default_factory=dict)
    gate_passed: int = 0


@dataclass
class BacktestResult:
    T: int = 0
    skipped: int = 0
    missing_points: int = 0            # 其中属于"遗漏期"（有开奖无点位，§11.3）
    records: list[PeriodRecord] = field(default_factory=list)
    system_test: TestResult | None = None
    method_tests: dict[str, TestResult] = field(default_factory=dict)
    method_top5_hits: dict[str, list[int]] = field(default_factory=dict)
    baselines: BaselineReport | None = None
    degraded: bool = False
    exp3: Exp3State | None = None
    elapsed_sec: float = 0.0
    window_label: str = ""

    @property
    def top5_hits(self) -> list[int]:
        return [r.hits for r in self.records]

    def quarter_breakdown(self) -> dict[str, TestResult]:
        """按季度分组检验（§9.3）。"""
        buckets: dict[str, list[int]] = {}
        for r in self.records:
            y, m, _ = (int(x) for x in r.date_str.split("-"))
            q = (m - 1) // 3 + 1
            buckets.setdefault(f"{y}Q{q}", []).append(r.hits)
        return {k: evaluate(v, label=k) for k, v in sorted(buckets.items())}

    def year_breakdown(self) -> dict[str, TestResult]:
        buckets: dict[str, list[int]] = {}
        for r in self.records:
            y = r.date_str[:4]
            buckets.setdefault(y, []).append(r.hits)
        return {k: evaluate(v, label=k) for k, v in sorted(buckets.items())}


def _gate(cfg, candidates: list[int], fusion: FusionResult,
          results: dict[str, ModuleResult], base_stats) -> tuple[list[int], dict[int, float]]:
    """应用 §4.13 对抗门控。模块缺失时原样放行并告警。"""
    fn = registry.load_meta("adversarial")
    if fn is None:
        return list(candidates), {}

    stats: dict[int, NumberGateStats] = {}
    for n in candidates:
        bs = base_stats.get(n)
        h_vals = {dim: vec.get(n, 0.0) for dim, vec in fusion.h_values.items()}
        # 拥挤度：全体模块对该号的评分一致偏高时视为共识拥挤
        vals = [r.scores.get(n, 0.0) for r in results.values() if r.sufficient]
        crowding = (sum(1 for v in vals if v >= 0.7) / len(vals)) if vals else 0.0
        stats[n] = NumberGateStats(
            n=n,
            z_score=bs.z_score if bs else 0.0,
            miss=bs.miss if bs else 0,
            hit10=bs.hit10 if bs else 0,
            composite=fusion.composite.get(n, 0.0),
            h_values=h_vals,
            crowding=finite(crowding, 0.0),
            sample_size=bs.T if bs else 0,
        )
    try:
        passed, refute = fn(list(candidates), fusion.composite, stats, cfg)
        return [int(x) for x in passed], {int(k): float(v) for k, v in (refute or {}).items()}
    except Exception as exc:
        observability.warn(f"对抗门控异常，跳过门控: {exc!r}")
        return list(candidates), {}


def run_backtest(cfg,
                 dataset,
                 n: int | None = None,
                 all_periods: bool = False,
                 method_names: list[str] | None = None,
                 warmup: int | None = None,
                 progress_every: int = 25) -> BacktestResult:
    """执行回测。默认只跑最近 `n` 期（config.backtest.default_n）。"""
    t0 = time.time()
    warmup = int(warmup if warmup is not None else
                 (cfg.backtest.warmup_periods or DEFAULT_WARMUP))

    pairs = dataset.pairable()                       # 期号升序
    if not all_periods:
        k = int(n if n is not None else (cfg.backtest.default_n or 60))
        pairs = pairs[-k:] if k > 0 else pairs

    out = BacktestResult(window_label="全档案" if all_periods else f"最近 {len(pairs)} 期")

    # §11.3：有开奖但无点位的"遗漏期"不参与预测，但必须计入跳过期数
    missing = [p for p in dataset.missing_points_periods()
               if len(dataset.history_before(p)) >= warmup]
    if not all_periods and pairs:
        lo = pairs[0][0]
        missing = [p for p in missing if p >= lo]
    out.missing_points = len(missing)
    out.skipped += out.missing_points

    ol = cfg.online_learner
    exp3 = Exp3State.load_or_uniform(
        cfg.state_file, MAIN_METHODS,
        gamma=float(ol.gamma or 0.1),
        floor=float(ol.weight_floor or 0.01),
        warmup=int(ol.warmup_periods or DEFAULT_WARMUP))

    actual_sets: list[set[int]] = []
    expanded_sets: list[set[int]] = []
    expanded_sizes: list[int] = []
    expanded_hits: list[int] = []
    points_hits: list[int] = []
    per_method_hits: dict[str, list[int]] = {m: [] for m in MAIN_METHODS}

    for idx, (P, draw, entry) in enumerate(pairs, 1):
        hist = dataset.history_before(P)             # 严格小于 P
        if len(hist) < warmup:
            out.skipped += 1
            continue

        expanded = expand(entry.points)
        base_stats = compute_base_stats(hist, expanded)
        actual = set(draw.numbers)

        results, z_rebound = registry.run_all(
            hist, expanded, base_stats, cfg, method_names, run_meta=True)

        weights = exp3.effective(MAIN_METHODS)
        fusion = fuse(results, cfg, base_stats, weights)

        # 候选池：拓展集合 ∩ 对抗门控
        passed, _ = _gate(cfg, sorted(expanded), fusion, results, base_stats)
        pool = sorted(set(passed) or expanded)

        sel = select_top5(fusion, pool, cfg)
        picks = select_52(fusion, sel.core, set(expanded), results,
                          results["omission"].scores, results.get("contrarian"), cfg)

        rec = PeriodRecord(
            period=P,
            date_str=draw.date.isoformat(),
            top5=list(sel.core),
            hits=len(set(sel.core) & actual),
            core5_hits=len(set(sel.core) & actual),
            defensive_hits=len(set(picks.defensive) & actual),
            expanded_hits=len(expanded & actual),
            points20_hits=len(set(entry.points) & actual),
            expanded_size=len(expanded),
            gate_passed=len(pool),
        )
        for m in MAIN_METHODS:
            if m in results and results[m].sufficient:
                top = results[m].top(5, restrict_to=expanded)
                rec.per_method_top5[m] = top
                rec.per_method_hits[m] = len(set(top) & actual)
                per_method_hits[m].append(rec.per_method_hits[m])
        out.records.append(rec)

        actual_sets.append(actual)
        expanded_sets.append(expanded)
        expanded_sizes.append(len(expanded))
        expanded_hits.append(len(expanded & actual))
        points_hits.append(len(set(entry.points) & actual))

        # 用**本期**开奖更新权重，供**下一期**使用（无前视）
        exp3.update(rec.per_method_top5, actual)

        if progress_every and idx % progress_every == 0:
            observability.info(f"  回测进度 {idx}/{len(pairs)} 期…")

    out.T = len(out.records)
    out.exp3 = exp3
    out.elapsed_sec = time.time() - t0

    if out.T == 0:
        observability.warn("回测无有效样本（历史均不足 warmup 期）")
        return out

    out.system_test = evaluate(out.top5_hits, label="系统 Top5", alpha=cfg.thresholds.alpha)
    present = {m: s for m, s in per_method_hits.items() if s}
    out.method_top5_hits = present
    out.method_tests = evaluate_methods(
        present, alpha=float(cfg.thresholds.alpha or 0.05),
        method=str(cfg.thresholds.fdr_method or "bh"))

    out.baselines = build_baselines(
        top5_hits=[float(x) for x in out.top5_hits],
        expanded_hits=[float(x) for x in expanded_hits],
        expanded_sizes=expanded_sizes,
        points_hits=[float(x) for x in points_hits],
        actual_draws=actual_sets,
        expanded_sets=expanded_sets,
        n_iters=int(cfg.backtest.random_baseline_iters or 1000),
        seed=int(cfg.backtest.random_seed or cfg.seed),
        alpha=float(cfg.thresholds.alpha or 0.05))

    out.degraded = all_insignificant(out.method_tests)
    return out
