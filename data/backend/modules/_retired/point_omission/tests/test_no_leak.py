# -*- coding: utf-8 -*-
"""§9.4 无前视 —— 分析目标期 T 时，任何进入计算的画期都必须 < T。

做法：用 monkeypatch 包裹**真实链路**里的关键函数，记录"实际传入的历史数据"，
再对记录做断言（不改写任何被测代码）：

  · source.Dataset.history_before  —— 唯一的历史裁剪入口（严格小于）
  · kl8.registry.run_all           —— 11 模块实际收到的 draws
  · compute_base_stats             —— base_stats 实际依据的 draws

附带 §6.3 的 Exp3 在线权重用例（预热等权 / 权重下限不置 0 / 待结算期不自我结算），
它们同属"权重只能由已开出的期决定"这条无前视纪律。

本文件自包含，不联网、不写项目目录（全部落在 tmp_path）。
"""
from __future__ import annotations

import sys
from datetime import date as _date
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as kl8_main                                          # noqa: E402
from kl8 import points_input, registry, replay, source           # noqa: E402
from kl8.config import load_config                               # noqa: E402
from kl8.data_io import (Draw, PointEntry, format_numbers_line,   # noqa: E402
                         format_points_line, sort_draws)
from kl8.ensemble import MAIN_METHODS, Exp3State                 # noqa: E402
from kl8.points import compute_base_stats                        # noqa: E402

CONFIG_YAML = """\
data:
  python_project:
    enabled: true
    dir: "shared"
    points_file: "daily_points.txt"
    history_file: "kl8_history_final.txt"
    mode: "read_only"
  upload_dir: "data/uploads"
  seed_dir: "data/seed"
  cache_dir: "data/cache"
  state_dir: "data/state"
  log_dir: "data/logs"
fetch:
  enabled: false
  sources: ["17500", "cwl"]
report:
  out_dir: "output"
"""

MIN_HISTORY = 30          # main._analyze_target 的最低历史要求


# ── 沙箱档案 ──────────────────────────────────────────────────

def _draw(idx: int, start: int = 2025001) -> Draw:
    nums = tuple(sorted(((idx * 7 + k * 3) % 80) + 1 for k in range(20)))
    return Draw(period=start + idx, date=_date(2025, 1, 1) + timedelta(days=idx),
                numbers=nums)


def _point(idx: int, start: int = 2025001) -> PointEntry:
    pts = tuple(sorted(((idx * 3 + k * 7) % 80) + 1 for k in range(20)))
    return PointEntry(period=start + idx, date=_date(2025, 1, 1) + timedelta(days=idx),
                      points=pts)


def _sandbox(tmp_path: Path, n: int = 150, start: int = 2025001):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(CONFIG_YAML, encoding="utf-8")
    cfg = load_config(path=str(cfg_file), root=tmp_path)
    cfg.shared_dir.mkdir(parents=True, exist_ok=True)

    draws = [_draw(i, start) for i in range(n)]
    pts = [_point(i, start) for i in range(n)]
    cfg.shared_history_file.write_bytes(
        ("\n".join(format_numbers_line(d.date, d.period, list(d.numbers))
                   for d in reversed(draws)) + "\n").encode("utf-8"))
    cfg.shared_points_file.write_bytes(
        ("\n".join(format_points_line(e.date, e.period, list(e.points))
                   for e in reversed(pts)) + "\n").encode("utf-8"))

    ds = source.load_dataset(cfg, allow_fetch=False)
    assert len(ds.draws) == n and len(ds.points) == n
    return cfg, ds


# ── 记录器 ────────────────────────────────────────────────────

class Recorder:
    """按调用顺序记录 (kind, target_period, max_period, n_periods, periods)。"""

    def __init__(self):
        self.events: list[tuple[str, int | None, int, int, tuple[int, ...]]] = []

    def history(self, period: int, hist: list[Draw]) -> None:
        self.events.append(("history", int(period), _maxp(hist), len(hist),
                            tuple(sorted(d.period for d in hist))))

    def consumed(self, kind: str, draws: list[Draw]) -> None:
        self.events.append((kind, None, _maxp(draws), len(draws),
                            tuple(sorted(d.period for d in draws))))

    def of(self, kind: str):
        return [e for e in self.events if e[0] == kind]


def _maxp(draws) -> int:
    return max((d.period for d in draws), default=0)


def _wrappers(rec: Recorder):
    """返回 (history_before, run_all, compute_base_stats) 三个包装函数。"""
    orig_hb = source.Dataset.history_before
    orig_run = registry.run_all
    orig_cbs = compute_base_stats

    def history_before(self, period):
        hist = orig_hb(self, period)
        rec.history(period, hist)
        return hist

    def run_all(draws, expanded_set, base_stats, cfg, names=None, run_meta=True):
        rec.consumed("run_all", draws)
        return orig_run(draws, expanded_set, base_stats, cfg, names, run_meta)

    def base_stats(draws, expanded_set=None):
        rec.consumed("base_stats", draws)
        return orig_cbs(draws, expanded_set)

    return history_before, run_all, base_stats


def _install(monkeypatch, rec: Recorder) -> None:
    hb, run, cbs = _wrappers(rec)
    monkeypatch.setattr(source.Dataset, "history_before", hb)
    monkeypatch.setattr(registry, "run_all", run)
    monkeypatch.setattr(kl8_main, "compute_base_stats", cbs)     # 实盘路径引用
    monkeypatch.setattr(replay, "compute_base_stats", cbs)       # 回测路径引用


def assert_no_lookahead(rec: Recorder) -> int:
    """顺序扫描事件：history 为每个目标期 T 设界，其后消费的数据必须 < T。"""
    checked = 0
    cur_target: int | None = None
    for kind, target, max_period, n_periods, _periods in rec.events:
        if kind == "history":
            if n_periods:
                assert max_period < target, \
                    f"history_before({target}) 返回了 >= T 的期：{max_period}"
                if n_periods >= MIN_HISTORY:
                    cur_target = target
            continue
        assert cur_target is not None, f"{kind} 出现在任何 history 裁剪之前"
        assert max_period < cur_target, \
            f"{kind} 用到了 >= 目标期 {cur_target} 的数据（最大期号 {max_period}）"
        checked += 1
    assert checked > 0, "未捕获到任何被消费的历史数据，测试失效"
    return checked


# ── 实盘路径（main._analyze_target）───────────────────────────

@pytest.fixture(scope="module")
def live(tmp_path_factory):
    """跑一次真实的分析链路并记录全部历史入参（模块级缓存，跑一次即可）。"""
    tmp = tmp_path_factory.mktemp("no_lookahead_live")
    cfg, ds = _sandbox(tmp, n=150)
    pairs = ds.pairable()
    period, draw, entry = pairs[-1]
    target = points_input.TargetInfo(period=period, date=draw.date,
                                     already_input=True,
                                     existing_points=entry.points)

    rec = Recorder()
    hb, run, cbs = _wrappers(rec)
    originals = (source.Dataset.history_before, registry.run_all,
                 kl8_main.compute_base_stats, replay.compute_base_stats)
    source.Dataset.history_before = hb
    registry.run_all = run
    kl8_main.compute_base_stats = cbs
    replay.compute_base_stats = cbs
    try:
        ctx = kl8_main._analyze_target(cfg, ds, entry, target)
    finally:
        (source.Dataset.history_before, registry.run_all,
         kl8_main.compute_base_stats, replay.compute_base_stats) = originals

    return SimpleNamespace(cfg=cfg, ds=ds, ctx=ctx, rec=rec,
                           period=period, draw=draw, entry=entry)


def test_live_analyze_uses_only_periods_before_target(live):
    hist = live.ds.history_before(live.period)
    expected = tuple(sorted(d.period for d in live.ds.draws
                            if d.period < live.period))

    hb = live.rec.of("history")
    assert len(hb) == 1, "分析只应裁剪一次历史"
    kind, target, max_period, n_periods, periods = hb[0]
    assert target == live.period
    assert periods == expected                       # 恰好是 T 之前全部期
    assert live.period not in periods
    assert max_period == max(expected) == live.period - 1
    assert n_periods == len(hist) == 149

    assert_no_lookahead(live.rec)


def test_base_stats_and_modules_never_see_target_or_later(live):
    """base_stats 与 11 个模块消费的 draws 只能来自 T 之前。"""
    bs_events = live.rec.of("base_stats")
    run_events = live.rec.of("run_all")
    assert bs_events and run_events

    for kind, _t, max_period, n, periods in bs_events + run_events:
        assert max_period < live.period, f"{kind} 泄漏了目标期 {live.period}"
        assert live.period not in periods
        assert all(p < live.period for p in periods)
    # base_stats 与 run_all 必须看到同一份历史（不许各自偷偷扩窗）
    assert bs_events[0][4] == run_events[0][4]


def test_base_stats_is_pure_function_of_history_before_target(live):
    """用 T 之前的历史独立重算 base_stats，应与链路内实际使用的一份完全一致。"""
    hist = live.ds.history_before(live.period)
    expected = compute_base_stats(hist, live.ctx.expanded)
    actual = live.ctx.base_stats

    assert set(actual) == set(expected) == set(range(1, 81))
    for n in range(1, 81):
        a, e = actual[n], expected[n]
        assert (a.T, a.freq_full, a.hit10, a.hit3, a.miss) == \
               (e.T, e.freq_full, e.hit10, e.hit3, e.miss)
        assert a.T == len(hist) == 149

    # T 期本身绝不能进入 base_stats：hit3 只来自 T 之前最近 3 期
    recent3 = hist[:3]
    for n in live.draw.numbers:
        expected_hit3 = sum(1 for d in recent3 if n in d.numbers_set)
        assert actual[n].hit3 == expected_hit3


# ── 回测路径（replay.run_backtest）────────────────────────────

def test_backtest_history_strictly_before_each_target(tmp_path, monkeypatch):
    cfg, ds = _sandbox(tmp_path, n=150)
    rec = Recorder()
    _install(monkeypatch, rec)

    bt = replay.run_backtest(cfg, ds, all_periods=True, warmup=148)
    assert bt.T == 2 and bt.skipped == 148

    assert_no_lookahead(rec)

    # 逐期核对：每期的历史最大期号 = 该期期号 - 1
    targets = [r.period for r in bt.records]
    assert targets == [2025149, 2025150]
    hb = {e[1]: e for e in rec.of("history") if e[3] >= 148}
    for period in targets:
        _kind, _t, max_period, n_periods, periods = hb[period]
        assert max_period == period - 1
        assert n_periods == period - 2025001
        assert period not in periods and all(p < period for p in periods)


def test_backtest_records_match_strict_history_window(tmp_path, monkeypatch):
    cfg, ds = _sandbox(tmp_path, n=80)
    rec = Recorder()
    _install(monkeypatch, rec)

    bt = replay.run_backtest(cfg, ds, all_periods=True, warmup=78)
    assert bt.T == 2
    # 每个回测记录的目标期都必须严格晚于其历史窗口内所有期
    for record in bt.records:
        window = [d for d in ds.draws if d.period < record.period]
        assert window and max(d.period for d in window) < record.period
        assert record.period not in {d.period for d in window}
    assert_no_lookahead(rec)


# ── Exp3：预热等权（§6.3）─────────────────────────────────────

METHODS = list(MAIN_METHODS)


def _top5_map(nums=(1, 2, 3, 4, 5)) -> dict[str, list[int]]:
    return {m: list(nums) for m in METHODS}


def test_exp3_warmup_outputs_uniform_weights():
    warmup = 3
    st = Exp3State.uniform(METHODS, gamma=0.1, floor=0.01, warmup=warmup)
    uniform = 1.0 / len(METHODS)

    eff = st.effective(METHODS)
    assert set(eff) == set(METHODS)
    assert all(w == pytest.approx(uniform) for w in eff.values())
    assert sum(eff.values()) == pytest.approx(1.0)

    # 预热期内即使内部权重被扰动，输出仍是等权
    st.weights["cluster"] = 0.9
    st.weights["markov"] = 0.001
    assert st.periods == 0 and st.active is False
    assert st.effective(METHODS) == {m: pytest.approx(uniform) for m in METHODS} \
        or all(st.effective(METHODS)[m] == pytest.approx(uniform) for m in METHODS)

    # 走满 warmup 期后进入激活态
    for _ in range(warmup):
        st.update(_top5_map(), {1, 2, 3, 4, 5})
    assert st.periods == warmup
    assert st.active is True

    active_eff = st.effective(METHODS)
    assert sum(active_eff.values()) == pytest.approx(1.0)
    assert active_eff == st.weights                        # 激活后直接用归一权重
    assert active_eff["cluster"] != pytest.approx(uniform)  # 不再是等权


def test_exp3_warmup_boundary_before_activation():
    st = Exp3State.uniform(METHODS, gamma=0.1, floor=0.01, warmup=60)
    st.periods = 59
    assert st.active is False
    assert all(w == pytest.approx(1 / len(METHODS))
               for w in st.effective(METHODS).values())
    st.periods = 60
    assert st.active is True


# ── Exp3：权重下限（§6.3）────────────────────────────────────

def test_exp3_weight_floor_stays_positive_and_normalized():
    floor = 0.01
    st = Exp3State.uniform(METHODS, gamma=0.1, floor=floor, warmup=0)
    loser, winner = "cluster", "markov"
    actual = set(range(1, 21))

    for _ in range(300):
        tops = _top5_map(nums=(21, 22, 23, 24, 25))       # 全部不中（reward = -1）
        tops[loser] = list(actual)[:5]                     # loser 恒定 5 中（reward = 3）
        st.update(tops, actual)

    weights = st.weights
    assert set(weights) == set(METHODS)
    assert all(w > 0.0 for w in weights.values()), "权重下溢到 0，臂不可恢复"
    assert min(weights.values()) > 0.0
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)
    assert weights[loser] > weights[winner]                # 表现好的臂权重更高
    assert st.pulls[loser] == 300 and st.cumulative_reward[loser] > 0

    eff = st.effective(METHODS)
    assert all(w > 0.0 for w in eff.values())
    assert sum(eff.values()) == pytest.approx(1.0, abs=1e-9)


def test_exp3_renormalize_clamps_zero_weight_to_floor():
    st = Exp3State.uniform(METHODS, gamma=0.1, floor=0.02, warmup=0)
    st.weights["markov"] = 0.0                             # 人为置 0
    st._renormalize(METHODS)
    assert st.weights["markov"] > 0.0
    assert sum(st.weights.values()) == pytest.approx(1.0, abs=1e-9)


def test_exp3_update_ignores_empty_bet_map():
    st = Exp3State.uniform(METHODS, gamma=0.1, floor=0.01, warmup=0)
    before = dict(st.weights)
    st.update({}, {1, 2, 3})
    assert st.periods == 0 and st.weights == before


# ── Exp3：待结算期不自我结算（实盘无前视）─────────────────────

def test_settle_pending_waits_until_target_is_drawn(tmp_path):
    cfg, ds = _sandbox(tmp_path, n=150)
    st = Exp3State.uniform(METHODS, gamma=0.1, floor=0.01, warmup=30)
    before = dict(st.weights)

    pending_period = 2025200                                # 档案中尚不存在
    kl8_main._set_pending(st, pending_period, _top5_map())
    kl8_main._settle_pending(cfg, ds, st)

    assert st.periods == 0
    assert st.weights == before, "未开出的期不得影响权重"
    assert st.pending.get("period") == pending_period

    # 该期开出后才结算，并清空待结算状态
    drawn = Draw(period=pending_period, date=_date(2025, 6, 1),
                 numbers=tuple(range(1, 21)))
    ds2 = source.Dataset(draws=sort_draws(list(ds.draws) + [drawn]),
                         points=ds.points, health=ds.health)
    kl8_main._settle_pending(cfg, ds2, st)

    assert st.periods == 1 and st.pending == {}
    assert sum(st.weights.values()) == pytest.approx(1.0, abs=1e-9)
    assert all(w > 0.0 for w in st.weights.values())
