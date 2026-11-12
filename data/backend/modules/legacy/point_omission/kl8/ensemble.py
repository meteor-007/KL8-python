# -*- coding: utf-8 -*-
"""融合链路：方法分 → 维度分 → 综合分（§5.1 / §4.14）+ Exp3 在线权重（§6.3）。

**全文档唯一的融合路径**：

    第 1 段（方法层）  score_m[n] ∈ [0,1]        11 个模块各自产出
            │  维度内聚合（§4.14）
    第 2 段（维度层）  H_k[n] ∈ [0,1]             k = 1..7
            │  维度加权（w_k 由 config.scoring.weights 给出，和为 1）
    第 3 段（综合分）  composite[n] = Σ_k w_k · H_k[n] × 100

Exp3 学的是**方法权重 w_m**（第 1 段的维度内权重），不是 w_k。
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .contracts import ModuleResult
from .data_io import Draw
from .numerics import EPS, GEO_EPS, clip01, finite, rank_normalize, safe_div
from .points import NumberStats
from . import observability

NUMBERS = list(range(1, 81))

# 11 个主分方法（Exp3 的臂）
MAIN_METHODS = ["cluster", "cyclic", "heatmap", "markov", "fibonacci",
                "linalg_svd", "complex_fft", "graph_net", "volatility",
                "remainder", "entropy"]

# 元模块（不进主分）
META_METHODS = ["contrarian", "adversarial"]

# 维度构成（§4.14）
DIM_SPEC: dict[str, dict] = {
    "H1": {"weighted": ["fibonacci"], "with_base_stats": True},
    "H2": {"weighted": ["omission"]},
    "H3": {"weighted": ["cluster", "remainder:cluster"]},
    "H4": {"geo": ["cyclic", "complex_fft"],
           "weighted": ["heatmap", "volatility"]},
    "H5": {"weighted": ["linalg_svd", "graph_net"]},
    "H6": {"weighted": ["markov"]},
    "H7": {"weighted": ["entropy", "heatmap:balance", "remainder:balance"]},
}

DIM_NAMES = {"H1": "热度", "H2": "遗漏反弹", "H3": "集群", "H4": "周期/波动",
             "H5": "共现/图", "H6": "马尔可夫", "H7": "熵/均衡"}


# ── 子分数解析 ────────────────────────────────────────────────

def _sub_scores(result: ModuleResult, key: str) -> dict[int, float] | None:
    """取模块的子分数。

    约定：模块可在 metrics["sub_scores"] 里暴露额外打分向量，例如
        metrics["sub_scores"] = {"cluster": {...}, "balance": {...}}
    未提供时回退为该模块的主 scores（保证融合链路永不缺项）。
    """
    subs = result.metrics.get("sub_scores") if result.metrics else None
    if isinstance(subs, dict):
        got = subs.get(key)
        if isinstance(got, dict) and got:
            return {n: clip01(finite(got.get(n, 0.0), 0.0)) for n in NUMBERS}
    return None


def _resolve(token: str, results: dict[str, ModuleResult]) -> dict[int, float] | None:
    """解析 'method' 或 'method:subkey' 记号。"""
    if ":" in token:
        mod, key = token.split(":", 1)
        res = results.get(mod)
        if res is None or not res.sufficient:
            return None
        return _sub_scores(res, key) or res.scores
    res = results.get(token)
    if res is None or not res.sufficient:
        return None
    return res.scores


def _base_stats_scores(base_stats: dict[int, NumberStats] | None) -> dict[int, float] | None:
    """H1 的基础统计子项：z_score 与 hit10 各自 rank 归一等权合成。"""
    if not base_stats:
        return None
    z = [base_stats[n].z_score if n in base_stats else 0.0 for n in NUMBERS]
    h = [float(base_stats[n].hit10 if n in base_stats else 0) for n in NUMBERS]
    zn = rank_normalize(z)
    hn = rank_normalize(h)
    return {n: clip01(0.5 * zn[i] + 0.5 * hn[i]) for i, n in enumerate(NUMBERS)}


# ── 维度聚合 ──────────────────────────────────────────────────

def _weighted_mean(vectors: list[tuple[dict[int, float], float]]
                   ) -> dict[int, float] | None:
    """加权平均，权重归一。"""
    total = sum(w for _, w in vectors if w > 0)
    if not vectors or total <= EPS:
        return None
    out = {}
    for n in NUMBERS:
        acc = 0.0
        for vec, w in vectors:
            if w <= 0:
                continue
            acc += w * clip01(finite(vec.get(n, 0.0), 0.0))
        out[n] = clip01(acc / total)
    return out


def _geo_mean_n(vectors: list[dict[int, float]]) -> dict[int, float]:
    """n 元几何平均：exp(mean(log(v+ε))) − ε。

    任一项为 0 时整体不归零（§4.14 对 v1.0 缺陷的修复）。
    """
    if not vectors:
        return {n: 0.0 for n in NUMBERS}
    out = {}
    k = len(vectors)
    for n in NUMBERS:
        acc = 0.0
        for vec in vectors:
            acc += math.log(clip01(finite(vec.get(n, 0.0), 0.0)) + GEO_EPS)
        out[n] = clip01(math.exp(acc / k) - GEO_EPS)
    return out


def aggregate_dimensions(results: dict[str, ModuleResult],
                         method_weights: dict[str, float],
                         base_stats: dict[int, NumberStats] | None = None
                         ) -> tuple[dict[str, dict[int, float]], list[str]]:
    """按 §4.14 聚合出 H1–H7。返回 (h_values, 未生效的维度列表)。"""
    h_values: dict[str, dict[int, float]] = {}
    skipped: list[str] = []

    for dim, spec in DIM_SPEC.items():
        parts: list[tuple[dict[int, float], float]] = []

        # H4 的两级聚合：先对 cyclic 与 complex_fft 取几何平均，再与其余加权平均
        geo_tokens = spec.get("geo", [])
        if geo_tokens:
            vecs = [v for v in (_resolve(t, results) for t in geo_tokens)
                    if v is not None]
            if vecs:
                parts.append((_geo_mean_n(vecs), 1.0))

        for token in spec.get("weighted", []):
            vec = _resolve(token, results)
            if vec is None:
                continue
            parts.append((vec, method_weights.get(token.split(":")[0], 1.0)))

        if spec.get("with_base_stats"):
            bs = _base_stats_scores(base_stats)
            if bs is not None:
                parts.append((bs, 0.5))     # 基础统计作为低权子项

        agg = _weighted_mean(parts)
        if agg is None:
            skipped.append(dim)
            continue
        h_values[dim] = agg

    return h_values, skipped


# ── Exp3 在线权重（§6.3）──────────────────────────────────────

@dataclass
class Exp3State:
    """Exp3 权重状态。

    臂 = 11 个主分方法；下注 = 该方法 scores 在拓展集合内的 top-5；
    奖励 = (命中数 − 1.25)/1.25；权重下限 0.01；预热 60 期。
    """
    weights: dict[str, float] = field(default_factory=dict)
    cumulative_reward: dict[str, float] = field(default_factory=dict)
    pulls: dict[str, int] = field(default_factory=dict)
    periods: int = 0
    gamma: float = 0.1
    floor: float = 0.01
    warmup: int = 60
    # 实盘路径的待结算期：{"period": P, "method_top5": {m: [...]}}
    # 等 P 开奖后再用它更新权重，保证权重永远由**已开出**的期决定（无前视）。
    pending: dict = field(default_factory=dict)

    @classmethod
    def uniform(cls, methods: list[str], gamma: float, floor: float,
                warmup: int) -> "Exp3State":
        w = 1.0 / max(1, len(methods))
        return cls(
            weights={m: w for m in methods},
            cumulative_reward={m: 0.0 for m in methods},
            pulls={m: 0 for m in methods},
            gamma=gamma, floor=floor, warmup=warmup,
        )

    @property
    def active(self) -> bool:
        """预热期结束前用等权（§6.3 冷启动）。"""
        return self.periods >= self.warmup

    def effective(self, methods: list[str]) -> dict[str, float]:
        if not self.active:
            w = 1.0 / max(1, len(methods))
            return {m: w for m in methods}
        return {m: self.weights.get(m, 1.0 / len(methods)) for m in methods}

    # ── 每期更新 ──────────────────────────────────────────────
    def update(self, method_top5: dict[str, list[int]], actual: set[int]) -> None:
        """用**截止上一期**的开奖结果更新全部臂（§6.3）。"""
        methods = list(method_top5)
        if not methods:
            return
        self.periods += 1

        w = self.effective(methods)
        wsum = sum(w.values()) or 1.0
        probs = {m: max(self.floor, w[m] / wsum) for m in methods}
        psum = sum(probs.values()) or 1.0
        probs = {m: p / psum for m, p in probs.items()}

        for m in methods:
            hits = len(set(method_top5[m]) & actual)
            # 奖励中心在 0：正 = 优于随机，负 = 劣于随机
            reward = (hits - 1.25) / 1.25
            self.cumulative_reward[m] = self.cumulative_reward.get(m, 0.0) + reward
            self.pulls[m] = self.pulls.get(m, 0) + 1
            # 重要性加权估计量：r̂ = reward / p
            est = reward / max(probs[m], EPS)
            # Exp3 指数更新（用 exp 的裁剪防止溢出）
            self.weights[m] = self.weights.get(m, 1.0 / len(methods)) * \
                math.exp(min(30.0, self.gamma * est / len(methods)))

        self._renormalize(methods)

    def _renormalize(self, methods: list[str]) -> None:
        """归一化并施加下限（不置 0，保证该臂可通过探索恢复，§6.3）。"""
        vals = {m: max(self.floor, finite(self.weights.get(m, 0.0), 0.0))
                for m in methods}
        total = sum(vals.values()) or 1.0
        self.weights = {m: v / total for m, v in vals.items()}

    # ── 持久化 ────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {"weights": self.weights, "cumulative_reward": self.cumulative_reward,
                "pulls": self.pulls, "periods": self.periods, "gamma": self.gamma,
                "floor": self.floor, "warmup": self.warmup, "pending": self.pending}

    @classmethod
    def from_dict(cls, d: dict) -> "Exp3State":
        st = cls()
        st.weights = {k: float(v) for k, v in (d.get("weights") or {}).items()}
        st.cumulative_reward = {k: float(v) for k, v in
                                (d.get("cumulative_reward") or {}).items()}
        st.pulls = {k: int(v) for k, v in (d.get("pulls") or {}).items()}
        st.periods = int(d.get("periods") or 0)
        st.gamma = float(d.get("gamma") or 0.1)
        st.floor = float(d.get("floor") or 0.01)
        st.warmup = int(d.get("warmup") or 60)
        st.pending = d.get("pending") or {}
        return st

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                            encoding="utf-8")
        except OSError as exc:
            observability.warn(f"保存在线权重失败: {exc}")

    @classmethod
    def load_or_uniform(cls, path: Path, methods: list[str], gamma: float,
                        floor: float, warmup: int) -> "Exp3State":
        if path.exists():
            try:
                st = cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
                missing = [m for m in methods if m not in st.weights]
                if missing:
                    w = 1.0 / max(1, len(methods))
                    for m in missing:
                        st.weights[m] = w
                    st._renormalize(methods)
                return st
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                observability.warn(f"读取在线权重失败，回退等权: {exc}")
        return cls.uniform(methods, gamma, floor, warmup)


# ── 综合分 ────────────────────────────────────────────────────

@dataclass
class FusionResult:
    method_results: dict[str, ModuleResult]
    h_values: dict[str, dict[int, float]]
    composite: dict[int, float]              # 百分制 0..100
    skipped_dims: list[str] = field(default_factory=list)
    method_weights: dict[str, float] = field(default_factory=dict)
    dim_weights: dict[str, float] = field(default_factory=dict)

    def ranked(self, restrict_to=None) -> list[int]:
        allow = set(restrict_to) if restrict_to else None
        keys = [n for n in NUMBERS if allow is None or n in allow]
        return sorted(keys, key=lambda n: (-self.composite.get(n, 0.0), n))

    def dominant_dim(self, n: int) -> tuple[str, float]:
        """该号得分最高的维度，用于报告解释。"""
        best, best_v = "", -1.0
        for dim, vec in self.h_values.items():
            v = vec.get(n, 0.0)
            if v > best_v:
                best, best_v = dim, v
        return best, best_v


def fuse(results: dict[str, ModuleResult],
         cfg,
         base_stats: dict[int, NumberStats] | None = None,
         method_weights: dict[str, float] | None = None) -> FusionResult:
    """执行唯一的融合链路。"""
    weights = dict(method_weights or {m: 1.0 for m in MAIN_METHODS})
    for m in MAIN_METHODS:
        weights.setdefault(m, 1.0)

    h_values, skipped = aggregate_dimensions(results, weights, base_stats)

    dim_w = {k: float(cfg.scoring.weights.get(k, 0.0) or 0.0)
             for k in ("H1", "H2", "H3", "H4", "H5", "H6", "H7")}
    total_w = sum(dim_w.values())
    if total_w <= EPS:
        dim_w = {k: 1.0 / 7 for k in dim_w}
    else:
        dim_w = {k: v / total_w for k, v in dim_w.items()}
    # 未生效的维度权重按比例分摊到生效维度（避免综合分被系统性压低）
    active = [k for k in dim_w if k in h_values]
    if active:
        lost = sum(dim_w[k] for k in dim_w if k not in h_values)
        if lost > EPS:
            for k in dim_w:
                if k not in h_values:
                    dim_w[k] = 0.0
            add = lost / len(active)
            for k in active:
                dim_w[k] += add

    composite: dict[int, float] = {}
    for n in NUMBERS:
        acc = 0.0
        for dim, vec in h_values.items():
            acc += dim_w.get(dim, 0.0) * vec.get(n, 0.0)
        composite[n] = round(clip01(acc) * 100.0, 4)

    return FusionResult(
        method_results=results,
        h_values=h_values,
        composite=composite,
        skipped_dims=skipped,
        method_weights=weights,
        dim_weights=dim_w,
    )
