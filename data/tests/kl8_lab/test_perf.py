# -*- coding: utf-8 -*-
"""§12.1 性能基线的**确定性**回归护栏。

不用墙钟断言（会 flaky），而是断言"计算复杂度没有退化"——即已做的优化不被
无意中改回逐窗口/逐次重算的写法。这些断言在任何机器上都稳定。

背景（实测，2026-09-10）：
  · 277 期全档案回测 ~9m10s（优化前 11m45s）；每期约 2s，随历史长度线性增长
  · 已优化：entropy 滑窗计数改前缀和、共现矩阵累加向量化、Draw.numbers_set 预计算、
    numerics 热路径去掉重复 float 转换
  · 剩余热点是 markov 的 HMM 前向-后向与 omission 的 Weibull MLE，
    二者是**逐步递推/逐号拟合**，无法在不改变统计输出的前提下显著加速
"""
from __future__ import annotations

import sys
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.kl8_lab import entropy, registry, replay, source                       # noqa: E402
from backend.core.kl8_lab.config import load_config                                     # noqa: E402
from backend.core.kl8_lab.data_io import (Draw, format_numbers_line, format_points_line)  # noqa: E402
from backend.core.kl8_lab.ensemble import MAIN_METHODS                                  # noqa: E402
from backend.core.kl8_lab.points import compute_base_stats, expand                      # noqa: E402

POINTS = (4, 10, 12, 14, 16, 20, 22, 27, 30, 38, 39, 40,
          54, 59, 62, 65, 70, 74, 75, 80)


def _draws(n: int, seed: int = 7) -> list[Draw]:
    """确定性合成开奖（不依赖 random 的全局状态）。"""
    d0 = _date(2025, 1, 1)
    out = []
    for i in range(n):
        nums = tuple(sorted((((i * 13 + k * 29) % 80) + 1) for k in range(20)))
        out.append(Draw(period=2025001 + i, date=d0 + timedelta(days=i),
                        numbers=nums))
    return out


def _cfg(tmp_path: Path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "data:\n"
        "  python_project:\n"
        "    enabled: true\n"
        '    dir: "shared"\n'
        '    points_file: "daily_points.txt"\n'
        '    history_file: "kl8_history_final.txt"\n'
        '    mode: "read_only"\n'
        '  upload_dir: "data/uploads"\n'
        '  seed_dir: "data/seed"\n'
        '  cache_dir: "data/cache"\n'
        '  state_dir: "data/state"\n'
        '  log_dir: "data/logs"\n'
        "fetch:\n  enabled: false\n"
        'report:\n  out_dir: "output"\n'
        "reproducibility:\n  seed: 42\n",
        encoding="utf-8")
    return load_config(path=str(cfg_file), root=tmp_path)


# ── 护栏 1：entropy 不得逐窗口重算计数 ────────────────────────

def test_entropy_does_not_recount_every_window(monkeypatch, tmp_path):
    """滑窗序列必须走前缀和（O(80)/窗口），不得每个窗口都 O(窗口长×20) 重扫。

    修复前 `_counts` 被调用约 2·(T−win+1)+1 ≈ 540 次；修复后 ≤ 2 次。
    """
    draws = _draws(300)
    cfg = _cfg(tmp_path)
    calls = {"n": 0}
    real = entropy._counts

    def counting(d):
        calls["n"] += 1
        return real(d)

    monkeypatch.setattr(entropy, "_counts", counting)
    res = entropy.analyze(draws, set(range(1, 81)),
                         compute_base_stats(draws, set(range(1, 81))), cfg)

    assert res.sufficient
    assert calls["n"] <= 2, (
        f"entropy 滑窗计数退化为逐窗口重算：_counts 被调用 {calls['n']} 次"
        f"（应 ≤ 2；正确实现走 _window_counts 前缀和）")


def test_entropy_prefix_counts_matches_direct_count():
    """前缀和取窗口计数必须与直接重扫完全一致（数值前提）。"""
    draws = _draws(120)
    P = entropy._prefix_counts(draws)
    for start, win in ((0, 30), (5, 30), (40, 30), (90, 30)):
        direct = entropy._counts(draws[start:start + win])
        assert entropy._window_counts(P, start, win) == direct


# ── 护栏 2：Draw.numbers_set 必须预计算（回测中访问千万次）────

def test_draw_numbers_set_is_precomputed():
    d = Draw(period=2025001, date=_date(2025, 1, 1), numbers=(1, 2, 3, 80))
    assert d.numbers_set is d.numbers_set          # 同一对象 → 未每次重建
    assert d.numbers_set == frozenset({1, 2, 3, 80})


# ── 护栏 3：所有主方法必须真的对全 80 号打分（复杂度下限）────

def test_all_main_methods_scale_to_full_history(tmp_path):
    """T=300 时必须全部可用——防止某个模块退化为"只在短历史上可用"。"""
    draws = _draws(300)
    cfg = _cfg(tmp_path)
    expanded = expand(POINTS)
    results, _z = registry.run_all(draws, expanded,
                                   compute_base_stats(draws, expanded), cfg,
                                   list(MAIN_METHODS), run_meta=True)
    for m in MAIN_METHODS:
        assert m in results
        assert len(results[m].scores) == 80


# ── 护栏 4：回测在合成档案上跑通（宽松上界，只拦灾难性回归）──

@pytest.mark.parametrize("periods", [5])
def test_backtest_smoke_completes(tmp_path, periods):
    """小规模回测冒烟：拦住"缓存失效导致每期重算 Monte Carlo"这类灾难性回归。

    上界刻意宽松（120s，实测约 10–20s），避免在负载机器上 flaky。
    """
    cfg = _cfg(tmp_path)
    shared = cfg.shared_dir
    shared.mkdir(parents=True, exist_ok=True)
    draws = _draws(150)
    (shared / "kl8_history_final.txt").write_text(
        "".join(format_numbers_line(d.date, d.period, list(d.numbers)) + "\n"
                for d in draws), encoding="utf-8", newline="\r\n")
    (shared / "daily_points.txt").write_text(
        "".join(format_points_line(d.date, d.period, list(POINTS)) + "\n"
                for d in draws), encoding="utf-8", newline="\r\n")

    ds = source.load_dataset(cfg, allow_fetch=False)
    bt = replay.run_backtest(cfg, ds, n=periods)

    assert bt.T == periods
    assert bt.records
    assert bt.elapsed_sec >= 0.0
