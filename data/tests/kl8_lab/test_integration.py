# -*- coding: utf-8 -*-
"""端到端集成：真实档案（只读）+ 统一接口契约 + 共现增量等价（§3.5 / §10.2 / §12.2）。

三条纪律：
  · **只读**：共享档案仅用于读取；报告写到 tmp_path，绝不落进项目 output/。
  · **不联网**：config 里 fetch.enabled=false，且不调用 main.py 的命令行入口
    （避免与真实运行并发写 data/state/）。
  · **不依赖 tests/conftest.py**：本文件自包含。

真实档案缺失（`C:\\D-pan\\Dpanqianyi\\Python-Project\\data` 不存在）时
相关用例 pytest.skip。
"""
from __future__ import annotations

import functools
import math
import random
import sys
import tempfile
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.kl8_lab import cli as kl8_main                # noqa: E402
from backend.core.kl8_lab import registry, report, source                         # noqa: E402
from backend.core.kl8_lab.config import load_config                               # noqa: E402
from backend.core.kl8_lab.contracts import SECTIONS, ModuleResult, NarrativeBlock  # noqa: E402
from backend.core.kl8_lab.cooccurrence import (CooccurrenceBundle,                 # noqa: E402
                              build_cooccurrence, slide_window)
from backend.core.kl8_lab.data_io import Draw                                     # noqa: E402
from backend.core.kl8_lab.ensemble import MAIN_METHODS                            # noqa: E402
from backend.core.kl8_lab.points import compute_base_stats, expand                # noqa: E402
from backend.core.kl8_lab import points_input                                     # noqa: E402

SANDBOX_CONFIG = """\
data:
  python_project:
    enabled: true
    dir: "__SHARED__"
    # 数据文件在共享目录的 storage/raw/ 下（见 backend/modules/kl8_lab/config.yaml）。
    # 原先写成共享根目录下的裸文件名，是迁移前的旧布局 —— 结果这两个端到端用例
    # 一直读不到档案，静默 skip，等于从没验证过真实档案链路。
    points_file: "storage/raw/daily_points.txt"
    history_file: "storage/raw/kl8_history_final.txt"
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

# report.py 的章节标题（render_markdown 的固定输出）
REPORT_SECTIONS = (
    "## 〇、输入概览",
    "## 一、N 维评分仪表盘",
    "## 二、本期最值得关注的 Top 5",
    "## 三、宏观趋势",
    "## 四、风险预警与应对",
    "## 五、《趋势简报》决策树",
    "## 六、终极推荐清单",
    "## 附录 A",
)

MODULE_KEYS = set(MAIN_METHODS) | {"omission", "contrarian"}

# §2.1 规格示例点位
CANONICAL_POINTS = (4, 10, 12, 14, 16, 20, 22, 27, 30, 38, 39, 40,
                    54, 59, 62, 65, 70, 74, 75, 80)


# ── 沙箱 / 真实档案配置 ───────────────────────────────────────

def _config_at(root: Path, shared: str):
    cfg_file = root / "config.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(SANDBOX_CONFIG.replace("__SHARED__", shared),
                        encoding="utf-8")
    return load_config(path=str(cfg_file), root=root)


def _project_config():
    return load_config()                       # 项目根 config.yaml（真源）


def _real_archive():
    cfg = _project_config()
    return cfg.shared_dir, cfg.shared_points_file, cfg.shared_history_file


def _synthetic_draws(n: int, seed: int = 2024) -> list[Draw]:
    rng = random.Random(seed)
    d0 = _date(2025, 1, 1)
    draws = [Draw(period=2025001 + i, date=d0 + timedelta(days=i),
                  numbers=tuple(sorted(rng.sample(range(1, 81), 20))))
             for i in range(n)]
    return sorted(draws, key=lambda d: (d.date, d.period), reverse=True)


def _tmp_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="kl8_integration_"))


@functools.lru_cache(maxsize=4)
def _run_modules(tiny: bool = False):
    """在合成档案（T=150）上跑一次真实 registry.run_all，结果缓存复用。"""
    draws = _synthetic_draws(150)
    cfg = _config_at(_tmp_root(), "shared")
    expanded = expand([1, 2, 3]) if tiny else expand(CANONICAL_POINTS)
    base_stats = compute_base_stats(draws, expanded)
    results, _z = registry.run_all(draws, expanded, base_stats, cfg,
                                   list(MAIN_METHODS), run_meta=True)
    return results, expanded, base_stats, cfg, draws


# ── 真实档案端到端（只读）────────────────────────────────────

def test_real_archive_loads_and_pairs():
    shared_dir, points_file, history_file = _real_archive()
    if not (points_file.exists() and history_file.exists()):
        pytest.skip(f"共享数据目录不可用：{shared_dir}")

    cfg = _config_at(_tmp_root(), shared_dir.as_posix())
    assert cfg.read_only is True

    ds = source.load_dataset(cfg, allow_fetch=False)
    if not ds.pairable():
        pytest.skip("共享档案中无可严格配对的期")

    assert ds.health.pairable_count >= 30
    period = max(p for p, _d, _e in ds.pairable())
    hist = ds.history_before(period)
    assert hist and max(d.period for d in hist) < period
    assert ds.health.draws_source == "① 共享目录"


def test_real_archive_end_to_end_report(tmp_path):
    shared_dir, points_file, history_file = _real_archive()
    if not (points_file.exists() and history_file.exists()):
        pytest.skip(f"共享数据目录不可用：{shared_dir}")

    cfg = _config_at(tmp_path, shared_dir.as_posix())
    ds = source.load_dataset(cfg, allow_fetch=False)
    pairs = [row for row in ds.pairable()
             if len(ds.history_before(row[0])) >= 30]
    if not pairs:
        pytest.skip("共享档案中没有历史 ≥ 30 期的可配对期")

    period, draw, entry = pairs[-1]
    target = points_input.TargetInfo(period=period, date=draw.date,
                                     already_input=True,
                                     existing_points=entry.points)

    # 走真实分析链路；state/日志/report 全部落在 tmp_path（不碰项目 data/ 与 output/）
    ctx = kl8_main._analyze_target(cfg, ds, entry, target)
    assert ctx.expanded == expand(entry.points)
    assert ctx.health.pairable_count == ds.health.pairable_count

    md = report.render_markdown(ctx)
    report.assert_compliant(md)                        # 合规红线（§11.5）
    for heading in REPORT_SECTIONS:
        assert heading in md, f"报告缺少章节：{heading}"
    assert f"{period:07d}" in md
    assert "免责声明" in md
    assert len(ctx.selection.core) == 5                # §5.3 五码核心

    out_dir = tmp_path / "reports"
    path = report.write_report(ctx, out_dir)
    assert path.is_file()
    assert path.parent.parent == out_dir               # output/<date>/daily_report.md
    assert path.stat().st_size > 2000
    assert "不构成任何投注建议" in path.read_text(encoding="utf-8")

    # 报告只写在 tmp_path 内
    assert str(tmp_path) in str(path)
    assert path.read_text(encoding="utf-8") == md


# ── §3.5 统一接口契约 ────────────────────────────────────────

def test_module_result_contract():
    results, expanded, base_stats, cfg, draws = _run_modules()

    assert set(results) == MODULE_KEYS
    assert len(expanded) >= 20 and len(base_stats) == 80

    for name in sorted(MODULE_KEYS):
        res = results[name]
        assert isinstance(res, ModuleResult), f"{name} 未返回 ModuleResult"
        assert res.name == name

        # scores：全 1–80 号、[0,1] 有限数
        assert isinstance(res.scores, dict)
        assert len(res.scores) == 80
        assert set(res.scores) == set(range(1, 81))
        for n, v in res.scores.items():
            assert isinstance(v, float), f"{name}[{n}] 非 float"
            assert math.isfinite(v) and 0.0 <= v <= 1.0, f"{name}[{n}]={v}"
        assert isinstance(res.sufficient, bool)
        assert isinstance(res.metrics, dict) and isinstance(res.diagnostics, dict)

        # narrative：结构化片段且 section 合法
        assert isinstance(res.narrative, list)
        for blk in res.narrative:
            assert isinstance(blk, NarrativeBlock)
            assert blk.section in SECTIONS
            assert blk.text.strip()
        assert res.narrative, f"{name} 未投递任何 narrative"

        if res.sufficient:
            top5 = res.top(5)
            assert len(top5) == 5 and len(set(top5)) == 5
            assert all(1 <= n <= 80 for n in top5)
            assert top5 == sorted(top5, key=lambda n: (-res.scores[n], n))
            assert len(res.top(5, restrict_to=expanded)) == 5

        # masked_scores：只在融合阶段遮罩，不改变原 scores
        masked = res.masked_scores({1, 2, 3})
        assert set(masked) == set(range(1, 81))
        assert all(masked[n] == 0.0 for n in range(4, 81))
        assert all(masked[n] == res.scores[n] for n in (1, 2, 3))
        assert len(res.scores) == 80                        # 原分未被就地修改

    # 11 个主分方法在 T=150 合成档案上必须全部可用
    for name in MAIN_METHODS:
        assert results[name].sufficient, f"{name} 数据充足却降级"


def test_module_result_contract_section_3_5():
    """§3.5 统一接口契约的显式校验。

    字段为 `name` / `scores`（覆盖全 1–80 号）/ `metrics` / `narrative` /
    `diagnostics` / `sufficient`。

    注：§10.2 必测清单里写的 `avg_scores` / `top5` / `version` 是 v1.0 的旧命名；
    v2.0 权威契约在 §3.5，落点为 `kl8/contracts.py` 的 `ModuleResult`（以代码为准）。
    """
    results, _expanded, _bs, _cfg, _draws = _run_modules()
    assert results, "未产出任何模块结果"
    for name, res in results.items():
        assert isinstance(res.name, str) and res.name, f"{name} 缺 name"
        assert len(res.scores) == 80, f"{name} scores 未覆盖全 80 号"
        assert set(res.scores) == set(range(1, 81))
        assert isinstance(res.metrics, dict)
        assert isinstance(res.diagnostics, dict)
        assert isinstance(res.sufficient, bool)
        assert isinstance(res.narrative, list)
        assert len(res.top(5)) == 5


def test_module_ignores_expanded_restriction():
    """模块必须对全 80 号打分：用极小的 expanded 集合反证"未被集合限制"。"""
    results, expanded, _bs, _cfg, _draws = _run_modules(tiny=True)

    assert len(expanded) <= 8                              # 极小集合（1,2,3 的三元组邻域）
    outside_total = 0
    for name in MAIN_METHODS:
        res = results[name]
        assert res.sufficient, f"{name} 在 T=150 合成档案上降级"
        outside = [n for n in range(1, 81)
                   if n not in expanded and res.scores[n] > 0.0]
        assert outside, (f"{name} 的分数在 expanded({sorted(expanded)}) 之外全为 0，"
                         f"疑似把打分范围限制在输入点位邻域内（§3.5 要求对全 80 号打分）")
        outside_total += len(outside)

    assert outside_total > 11 * 10                         # 非"恰好一个号"的偶然通过


# ── §12.2 增量等价 ───────────────────────────────────────────

def _assert_bundles_equal(a: CooccurrenceBundle, b: CooccurrenceBundle) -> None:
    assert a.T == b.T
    assert np.allclose(a.C, b.C, atol=1e-9)
    assert np.allclose(a.count, b.count, atol=1e-9)
    assert np.allclose(a.J, b.J, atol=1e-9)
    assert np.allclose(a.PMI, b.PMI, atol=1e-9)


def test_incremental_equivalence():
    """增量 add / remove（slide_window）== 全量重算，容差 1e-9。"""
    draws = _synthetic_draws(60, seed=7)
    full = build_cooccurrence(draws)

    # ① 分批增量推进（Bundle.add）== 一次性全量
    part = CooccurrenceBundle()
    for d in draws[:17]:
        part.add(d)
    for d in draws[17:]:
        part.add(d)
    _assert_bundles_equal(part, full)
    assert full.T == 60

    # ② 滑动窗口（先 remove 再 add）== 重新全量构建同一窗口
    window = build_cooccurrence(draws[:30])
    slide_window(window, drop=draws[0], add=draws[30])
    rebuilt = build_cooccurrence(draws[1:31])
    assert window.T == rebuilt.T == 30
    _assert_bundles_equal(window, rebuilt)

    # ③ 增量完全回退（remove 掉窗口内全部实存期）== 归零
    for d in draws[1:31]:                                  # window 实存 draws[1..30]
        window.remove(d)
    assert window.T == 0
    assert np.allclose(window.C, np.zeros((81, 81)), atol=1e-9)
    assert np.allclose(window.count, np.zeros(81), atol=1e-9)
    _assert_bundles_equal(window, CooccurrenceBundle())


def test_incremental_add_only_stepwise_matches_full():
    """逐期 add 的累计量 == 全量重算（含惰性缓存的 J/PMI）。"""
    draws = _synthetic_draws(45, seed=11)
    step = CooccurrenceBundle()
    for d in draws:
        step.add(d)
    _assert_bundles_equal(step, build_cooccurrence(draws))


def test_incremental_equivalence_build_with_bundle():
    """build_cooccurrence(draws, bundle=existing) 真正增量累加（§12.2，已修复）。"""
    draws = _synthetic_draws(60, seed=7)
    part = build_cooccurrence(draws[:17])
    assert part.T == 17
    inc = build_cooccurrence(draws[17:], bundle=part)
    assert inc is part
    assert inc.T == 60
    _assert_bundles_equal(inc, build_cooccurrence(draws))


def test_cooccurrence_rwr_is_bounded_and_seeded():
    """图扩散输出契约：长度 81、下标 0 为 0、非负、质量不超过 1、种子必为正。"""
    draws = _synthetic_draws(40, seed=3)
    bundle = build_cooccurrence(draws)
    seeds = {1, 2, 3, 4, 5}
    r = bundle.rwr(seeds, alpha=0.15, iters=30)

    assert r.shape == (81,)
    assert r[0] == 0.0 and np.all(r >= 0.0)
    assert np.all(np.isfinite(r))
    assert 0.0 < r.sum() <= 1.0 + 1e-9
    for n in seeds:
        assert r[n] > 0.0                                   # 种子恒有重启质量
    assert bundle.rwr(set(), alpha=0.15, iters=5).sum() == 0.0
