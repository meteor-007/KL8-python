# -*- coding: utf-8 -*-
"""四级数据源调度 + 数据体检（§2.6 / §8.1）。

优先级：
  ① Python-Project/data 共享目录
  ② 缺失 → fetcher 双源增量抓取（原子写回）
  ③ 失败 → data/uploads 或 data/seed
  ④ 点位仍缺 → points_input 交互录入

默认 mode=read_only：系统只读共享目录，任何写入落在本项目 data/ 下的副本。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date as _date

from .config import Config
from .data_io import (Draw, ParseReport, PointEntry, load_draws,
                      load_points_archive, sort_draws)
from . import observability


# ── 体检 ──────────────────────────────────────────────────────

@dataclass
class HealthReport:
    points_count: int = 0
    draws_count: int = 0
    pairable_count: int = 0
    points_only: list[int] = field(default_factory=list)
    draws_only_count: int = 0
    duplicate_dates: dict[str, int] = field(default_factory=dict)
    inversions: list[int] = field(default_factory=list)
    malformed: int = 0
    dirty: list[int] = field(default_factory=list)
    points_source: str = ""
    draws_source: str = ""

    def render(self) -> str:
        lines = [
            f"点位档案期数      : {self.points_count}   [{self.points_source}]",
            f"开奖档案期数      : {self.draws_count}   [{self.draws_source}]",
            f"可严格配对期数    : {self.pairable_count}          ← 回测样本量以此为准",
            f"点位有而开奖无    : {[f'{p:07d}' for p in self.points_only]}",
            f"日期重复          : {self.duplicate_dates}",
            f"日期倒挂          : {[f'{p:07d}' for p in self.inversions]}",
            f"格式畸形行        : {self.malformed}",
        ]
        return "\n".join(lines)


def _detect_inversions(entries: dict[int, PointEntry]) -> list[int]:
    """检测日期倒挂：文件按日期降序，若某行日期大于前一行日期即为倒挂。"""
    rows = sorted(entries.values(), key=lambda e: e.period, reverse=True)
    inversions: list[int] = []
    prev_date: _date | None = None
    for e in rows:
        if e.date is None:
            continue
        if prev_date is not None and e.date > prev_date:
            inversions.append(e.period)
        prev_date = e.date
    return inversions


def health_check(draws: list[Draw],
                 points: dict[int, PointEntry],
                 parse_rep: ParseReport | None = None,
                 points_source: str = "",
                 draws_source: str = "") -> HealthReport:
    """产出 §2.6 体检报告，并据此决定可用样本。不修改原始文件。"""
    draw_periods = {d.period for d in draws}
    point_periods = set(points)

    pairable = sorted(draw_periods & point_periods)

    date_counter = Counter(e.date.isoformat() for e in points.values() if e.date)
    duplicates = {d: c for d, c in date_counter.items() if c > 1}

    return HealthReport(
        points_count=len(points),
        draws_count=len(draws),
        pairable_count=len(pairable),
        points_only=sorted(point_periods - draw_periods),
        draws_only_count=len(draw_periods - point_periods),
        duplicate_dates=duplicates,
        inversions=_detect_inversions(points),
        malformed=(parse_rep.malformed if parse_rep else 0),
        dirty=sorted(point_periods - draw_periods),
        points_source=points_source,
        draws_source=draws_source,
    )


# ── 数据集 ────────────────────────────────────────────────────

@dataclass
class Dataset:
    draws: list[Draw]                       # 最新在前
    points: dict[int, PointEntry]
    health: HealthReport

    def pairable(self) -> list[tuple[int, Draw, PointEntry]]:
        """可严格配对的 (期号, 开奖, 点位)，按**期号升序**（便于按时序回测）。"""
        draw_by_period = {d.period: d for d in self.draws}
        rows = [(p, draw_by_period[p], e)
                for p, e in self.points.items() if p in draw_by_period]
        return sorted(rows, key=lambda r: r[0])

    def latest_draw(self) -> Draw | None:
        return self.draws[0] if self.draws else None

    def latest_points(self) -> PointEntry | None:
        if not self.points:
            return None
        return max(self.points.values(), key=lambda e: (e.date or _date.min, e.period))

    def history_before(self, period: int) -> list[Draw]:
        """**严格小于**目标期号的历史（无前视，§9.2）。"""
        return [d for d in self.draws if d.period < period]

    def missing_points_periods(self) -> list[int]:
        """**遗漏期**：点位档案起点之后、有开奖却无点位的期号（§11.3）。

        这类期不参与预测，但必须计入「跳过期数」，否则回测会把"漏录入"
        伪装成"这段时期本就没有点位"。
        """
        if not self.points or not self.draws:
            return []
        first = min(self.points)
        return sorted(d.period for d in self.draws
                      if d.period >= first and d.period not in self.points)


# ── 加载与兜底 ────────────────────────────────────────────────

def _try_load(path, loader, label: str, rep: ParseReport):
    if path is None or not path.exists():
        return None
    try:
        return loader(str(path), rep)
    except (OSError, UnicodeDecodeError) as exc:
        observability.warn(f"读取 {label} 失败: {exc}")
        return None


def _merge_draws(base, extra) -> list[Draw] | None:
    """按 period 合并两份开奖档案，`extra`（本项目副本）优先。"""
    if not base and not extra:
        return None
    by_p = {d.period: d for d in (base or [])}
    by_p.update({d.period: d for d in (extra or [])})
    return sort_draws(list(by_p.values()))


def load_shared(cfg: Config) -> tuple[list[Draw] | None, dict[int, PointEntry] | None, ParseReport]:
    """① 共享目录 **+ 本项目副本**（§8.5）。

    只读模式下抓取/录入的增量写在 `data/cache/` 副本上；副本不参与读取就会
    被静默丢弃，因此这里把副本合并进来（副本条目优先）。
    """
    rep = ParseReport()
    draws = _try_load(cfg.shared_history_file, load_draws, "共享开奖文件", rep)
    points = _try_load(cfg.shared_points_file, load_points_archive, "共享点位文件", rep)

    copy_draws = _try_load(cfg.cache_dir / "history_copy.txt", load_draws,
                           "副本开奖文件", rep)
    draws = _merge_draws(draws, copy_draws)

    copy_points = _try_load(cfg.cache_dir / "points_copy.txt",
                            load_points_archive, "副本点位文件", rep)
    if copy_points:
        merged = dict(points or {})
        merged.update(copy_points)
        points = merged
    return draws, points, rep


def _load_dir(directory, points_name: str, history_name: str, rep: ParseReport):
    """③ uploads / seed 目录。"""
    if directory is None or not directory.exists():
        return None, None
    draws = _try_load(directory / history_name, load_draws, f"{directory.name}/开奖", rep)
    points = _try_load(directory / points_name, load_points_archive, f"{directory.name}/点位", rep)
    return draws, points


def load_dataset(cfg: Config, allow_fetch: bool = True) -> Dataset:
    """按 §8.1 四级兜底加载数据，并产出体检报告。"""
    rep = ParseReport()
    draws = points = None
    draws_src = points_src = ""

    # ① 共享目录
    if cfg.data.python_project.enabled:
        draws, points, rep = load_shared(cfg)
        if draws and points:
            draws_src = points_src = "① 共享目录"
        elif draws:
            draws_src = "① 共享目录"
        elif points:
            points_src = "① 共享目录"

    # ② 抓取（仅在共享目录缺开奖时）
    if draws is None and allow_fetch and cfg.fetch.enabled:
        try:
            from . import fetcher
            fetched = fetcher.fetch_incremental(cfg)
            if fetched:
                draws = fetched
                draws_src = "② 联网抓取"
        except Exception as exc:                      # 网络/解析异常一律降级
            observability.warn(f"抓取失败，降级到本地兜底: {exc}")

    # ③ uploads / seed
    if draws is None or points is None:
        up_draws, up_points = _load_dir(
            cfg.upload_dir, cfg.shared_points_file.name,
            cfg.shared_history_file.name, rep)
        seed_draws, seed_points = _load_dir(
            cfg.seed_dir, cfg.shared_points_file.name,
            cfg.shared_history_file.name, rep)
        if draws is None:
            draws = up_draws or seed_draws
            if draws is not None:
                draws_src = "③ uploads" if up_draws else "③ seed"
        if points is None:
            points = up_points or seed_points
            if points is not None:
                points_src = "③ uploads" if up_points else "③ seed"

    draws = sort_draws(draws or [])
    points = points or {}

    health = health_check(draws, points, rep, points_src or "缺失", draws_src or "缺失")
    return Dataset(draws=draws, points=points, health=health)


def load_history_only(cfg: Config, allow_fetch: bool = True) -> tuple[list[Draw], str]:
    """只要开奖历史（供 fetch / doctor 使用）。"""
    rep = ParseReport()
    draws = _try_load(cfg.shared_history_file, load_draws, "共享开奖文件", rep)
    draws = _merge_draws(draws, _try_load(cfg.cache_dir / "history_copy.txt",
                                          load_draws, "副本开奖文件", rep))
    src = "① 共享目录"
    if draws is None and allow_fetch and cfg.fetch.enabled:
        try:
            from . import fetcher
            draws = fetcher.fetch_incremental(cfg)
            src = "② 联网抓取"
        except Exception as exc:
            observability.warn(f"抓取失败: {exc}")
    if draws is None:
        d, _ = _load_dir(cfg.seed_dir, cfg.shared_points_file.name,
                         cfg.shared_history_file.name, rep)
        draws = d
        src = "③ seed"
    return sort_draws(draws or []), src
