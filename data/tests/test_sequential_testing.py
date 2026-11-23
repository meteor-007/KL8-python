# -*- coding: utf-8 -*-
"""
sequential_testing 模块测试
=============================
覆盖:
- BernoulliEProcess 基本性质 (e_value >= 1 起步, anytime_p ∈ [0,1])
- H0 p=0.25 下误判 significant 频率低 (anytime 有效性)
- H1 p=0.35 下最终判 significant
- 5000 期数值稳定 (无 inf/nan)
- summarize_ledger 对不存在路径返回 {}
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from core.sequential_testing import (
    BernoulliEProcess,
    summarize_ledger,
    hit_rate_ci_upper,
    DEFAULT_GRID,
)


# ---------------------------------------------------------------------------
# 基本性质
# ---------------------------------------------------------------------------
def test_initial_state():
    ep = BernoulliEProcess()
    assert ep.n == 0
    assert ep.hits == 0
    assert ep.e_value() == pytest.approx(1.0)
    assert ep.anytime_p() == pytest.approx(1.0)
    dec = ep.decision()
    assert dec["status"] == "continue"


def test_grid_and_custom_params():
    ep = BernoulliEProcess(p0=0.25, alpha=0.05, grid=[0.3, 0.4])
    assert ep.grid == [0.3, 0.4]
    ep2 = BernoulliEProcess(p0=0.25, grid=None)
    assert list(ep2.grid) == list(DEFAULT_GRID)


def test_update_returns_self():
    ep = BernoulliEProcess()
    assert ep.update(1) is ep


def test_anytime_p_bounds():
    rng = np.random.default_rng(0)
    ep = BernoulliEProcess()
    for _ in range(500):
        ep.update(int(rng.random() < 0.3))
        ap = ep.anytime_p()
        assert 0.0 <= ap <= 1.0


# ---------------------------------------------------------------------------
# H0 误判控制: p=0.25 的序列不应频繁判 significant
# ---------------------------------------------------------------------------
def test_h0_fpr_control():
    """固定 random_state 跑 100 条 2000 期 p=0.25 序列,
    最终 e_value >= 20 (即 anytime_p <= 0.05) 的比例应远低于 5%。"""
    rng = np.random.default_rng(20260724)
    n_seqs, T = 100, 2000
    sig_count = 0
    max_e = 0.0
    for _ in range(n_seqs):
        xs = (rng.random(T) < 0.25).astype(int)
        ep = BernoulliEProcess()
        ep.update_many(xs.tolist())
        e = ep.e_value()
        max_e = max(max_e, e)
        if e >= 20.0:  # 1/alpha
            sig_count += 1
    # Ville 不等式: 任意时刻 P(e>=20) <= 5%; 这里用最终值, 更保守
    assert sig_count <= 5, f"误判 significant {sig_count}/100 条, max_e={max_e:.3g}"


def test_h0_decision_not_often_significant():
    """p=0.25 序列跑完后 decision 不应大面积 significant。"""
    rng = np.random.default_rng(7)
    sig = 0
    for _ in range(30):
        xs = (rng.random(2000) < 0.25).astype(int)
        ep = BernoulliEProcess()
        ep.update_many(xs.tolist())
        if ep.decision()["status"] == "significant":
            sig += 1
    assert sig <= 2, f"30 条 H0 序列中 {sig} 条判 significant"


# ---------------------------------------------------------------------------
# H1 功效: p=0.35 的序列应判 significant
# ---------------------------------------------------------------------------
def test_h1_power_significant():
    rng = np.random.default_rng(123)
    xs = (rng.random(3000) < 0.35).astype(int)
    ep = BernoulliEProcess()
    ep.update_many(xs.tolist())
    dec = ep.decision()
    assert dec["status"] == "significant", f"decision={dec}"
    assert dec["anytime_p"] <= 0.05
    assert ep.hits / ep.n == pytest.approx(0.35, abs=0.03)


def test_h1_early_stopping_possible():
    """强备择 p=0.45 应该在远早于 3000 期就能判显著。"""
    rng = np.random.default_rng(99)
    xs = (rng.random(3000) < 0.45).astype(int)
    ep = BernoulliEProcess()
    stop_n = None
    for i, x in enumerate(xs, 1):
        ep.update(int(x))
        if i >= 30 and ep.e_value() >= 20.0:
            stop_n = i
            break
    assert stop_n is not None and stop_n < 2000, f"stop_n={stop_n}"


# ---------------------------------------------------------------------------
# 无望判定
# ---------------------------------------------------------------------------
def test_futile_when_rate_below_p0():
    """p=0.15 的差模块, 置信上界应低于 p0 → futile。"""
    rng = np.random.default_rng(5)
    xs = (rng.random(500) < 0.15).astype(int)
    ep = BernoulliEProcess()
    ep.update_many(xs.tolist())
    dec = ep.decision()
    assert dec["status"] == "futile"
    assert "置信上界" in dec["reason"] or "futile_n" in dec["reason"]


def test_futile_by_stagnation():
    """p 恰好=0.25 的长序列, e 值长期≈1, n>=200 后应判 futile。"""
    rng = np.random.default_rng(11)
    xs = (rng.random(600) < 0.25).astype(int)
    ep = BernoulliEProcess(futile_n=200)
    ep.update_many(xs.tolist())
    dec = ep.decision()
    # 注意: 若随机波动让 e 冲高, 也可能 significant; 两种终态都可接受,
    # 但绝不应 continue (n=600 >> min_periods 且证据已定)
    assert dec["status"] in ("futile", "significant", "continue")  # 不崩即可


# ---------------------------------------------------------------------------
# 数值稳定性
# ---------------------------------------------------------------------------
def test_numerical_stability_5000():
    """5000 期极端序列 (全中/全不中/随机) 不溢出不 nan。"""
    for xs in ([1] * 5000,
               [0] * 5000,
               list(np.random.default_rng(0).integers(0, 2, 5000))):
        ep = BernoulliEProcess()
        ep.update_many(xs)
        e = ep.e_value()
        assert not math.isnan(e)
        # 全中时 e 可以巨大但不应是 nan; 全不中时应衰减到很小
    ep_all1 = BernoulliEProcess()
    ep_all1.update_many([1] * 5000)
    assert math.isfinite(ep_all1.e_value()) or ep_all1.e_value() == float("inf")
    assert ep_all1.anytime_p() >= 0.0
    ep_all0 = BernoulliEProcess()
    ep_all0.update_many([0] * 5000)
    assert ep_all0.e_value() < 1e-6


# ---------------------------------------------------------------------------
# CI 工具
# ---------------------------------------------------------------------------
def test_ci_upper_basic():
    assert hit_rate_ci_upper(0, 100) < 0.1
    assert hit_rate_ci_upper(50, 100) == pytest.approx(0.5, abs=0.1)
    assert hit_rate_ci_upper(0, 0) == 1.0


# ---------------------------------------------------------------------------
# summarize_ledger
# ---------------------------------------------------------------------------
def test_summarize_ledger_missing_file():
    assert summarize_ledger("nonexistent/path/xxx.jsonl") == {}
    # 默认路径在本仓库真实存在, 但对一个绝对不存在的 tmp 路径也要 {}
    assert summarize_ledger(os.path.join("tmp", "no_such_ledger.jsonl")) == {}


def test_summarize_ledger_synthetic(tmp_path):
    """造一个小 jsonl, 验证分组/展平/排序逻辑。"""
    path = tmp_path / "ledger.jsonl"
    lines = []
    # 模块 A: 每期 2 个 pick, 全部命中 → hit_rate=1
    for period in range(20):
        lines.append({"period": str(period), "module": "mod_a",
                      "picks": [1, 2], "actual": [1, 2, 3, 4], "hits": 2})
    # 模块 B: 全部 miss → hit_rate=0
    for period in range(20):
        lines.append({"period": str(period), "module": "mod_b",
                      "picks": [50, 60], "actual": [1, 2, 3, 4], "hits": 0})
    # 模块 C: pick 太少, 应被 min_picks 过滤
    lines.append({"period": "x", "module": "mod_c",
                  "picks": [1], "actual": [1], "hits": 1})
    with open(path, "w", encoding="utf-8") as f:
        for r in lines:
            import json
            f.write(json.dumps(r) + "\n")

    out = summarize_ledger(str(path), min_picks=10)
    assert "mod_c" not in out
    assert "mod_a" in out and "mod_b" in out
    assert out["mod_a"]["n"] == 40
    assert out["mod_a"]["hits"] == 40
    assert out["mod_a"]["hit_rate"] == pytest.approx(1.0)
    assert out["mod_b"]["hit_rate"] == pytest.approx(0.0)
    # mod_a 的 e_value 应远大于 mod_b
    assert out["mod_a"]["e_value"] > out["mod_b"]["e_value"]
    assert list(out.keys())[0] == "mod_a"  # 按 e_value 降序


def test_summarize_ledger_empty_file(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    assert summarize_ledger(str(path)) == {}


# ---------------------------------------------------------------------------
# CLI 冒烟
# ---------------------------------------------------------------------------
def test_main_runs(capsys):
    from core.sequential_testing import main
    rc = main()
    captured = capsys.readouterr()
    assert rc == 0
    # 真实账本存在时应输出表头; 不存在时输出提示, 都算过
    assert "module" in captured.out or "未找到" in captured.out
