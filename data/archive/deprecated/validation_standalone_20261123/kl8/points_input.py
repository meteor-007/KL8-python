# -*- coding: utf-8 -*-
"""点位录入与原子落盘（§8.3 / §8.4）。

跨年期号推断是这里的核心：**禁止任何形式的裸 `period + 1`**。
参考实现用 `latest_period + 1`，跨年时会得到不存在的期号
（2026 年末期 2026351 加一得 2026352，实际应为 2027001）。
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime, timedelta

from .config import Config
from .data_io import (PointEntry, format_points_line, load_points_archive,
                      parse_points_input, file_hash, validate_core_points,
                      write_text_atomic, write_shared_guarded)
from . import observability

MAX_INDEX_IN_YEAR = 999


@dataclass
class TargetInfo:
    period: int
    date: _date
    already_input: bool
    existing_points: tuple[int, ...] = ()

    @property
    def period_str(self) -> str:
        return f"{self.period:07d}"

    def render(self) -> str:
        note = "（该期点位已存在）" if self.already_input else ""
        return f"目标期号 {self.period_str}   目标日期 {self.date}{note}"


def next_period_after(period: int, next_date: _date,
                      all_periods: set[int] | None = None) -> int:
    """按 §8.3 规则推断下一期号。

    若 next_date 的年份与该期号年份相同 → 同年年内序号 + 1；
    否则 → 新年份第 1 期（20YY001）。

    绝不使用裸 period + 1。
    """
    year = period // 1000
    if next_date.year == year:
        index = period % 1000 + 1
        if index > MAX_INDEX_IN_YEAR:                 # 理论上不会发生
            return (year + 1) * 1000 + 1
        return year * 1000 + index
    return next_date.year * 1000 + 1


def infer_target(cfg: Config, draws, points: dict[int, PointEntry]) -> TargetInfo:
    """基于最新开奖期与点位档案推断今日目标期号与日期。"""
    latest_period = max((d.period for d in draws), default=0)
    latest_date = max((d.date for d in draws), default=None)
    latest_points = max(points.values(), key=lambda e: e.period) if points else None

    if latest_period:
        # 无内置节假日日历：下一"交易日"即最新开奖日 + 1 天（§8.3）。
        # 这不影响期号正确性——休市只让日期与实际开奖日差几天，
        # 期号始终由「同年序号 +1」或「跨年归 1」决定。
        next_date = (latest_date + timedelta(days=1)) if latest_date else _date.today()
        target = next_period_after(latest_period, next_date, {d.period for d in draws})
    elif latest_points is not None:
        next_date = (latest_points.date + timedelta(days=1)) if latest_points.date \
            else _date.today()
        target = next_period_after(latest_points.period, next_date)
    else:
        target = _date.today().year * 1000 + 1
        next_date = _date.today()

    existing = points.get(target)
    return TargetInfo(
        period=target,
        date=next_date,
        already_input=existing is not None,
        existing_points=existing.points if existing else (),
    )


# ── 落盘 ──────────────────────────────────────────────────────

def _points_target(cfg: Config):
    """read_only → 本项目副本；read_write → 共享档案（§8.5）。"""
    return cfg.cache_dir / "points_copy.txt" if cfg.read_only \
        else cfg.shared_points_file


def load_points_any(cfg: Config) -> dict[int, PointEntry]:
    """点位档案：共享文件与本项目副本**合并**（§8.5）。

    只读模式下录入的点位落在 `data/cache/points_copy.txt`，副本必须参与读取，
    否则录入结果会被静默丢弃；副本条目优先（承载本轮新增/修改）。
    """
    merged: dict[int, PointEntry] = {}
    for path in (cfg.shared_points_file, cfg.cache_dir / "points_copy.txt"):
        if path and path.exists():
            try:
                merged.update(load_points_archive(str(path)))
            except (OSError, UnicodeDecodeError) as exc:
                observability.warn(f"读取 {path} 失败: {exc}")
    return merged


def _write_points(cfg: Config, entries: dict[int, PointEntry],
                  expect_hash: str | None = None) -> None:
    """写回点位档案。read_only → 本项目副本；read_write → §8.5 保护写回共享。"""
    target = _points_target(cfg)

    if target.exists() and int(cfg.fetch.backup_before_write or 0):
        backup_dir = cfg.cache_dir / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            shutil.copy2(target, backup_dir / f"{target.stem}_{stamp}.bak")
        except OSError as exc:
            observability.warn(f"备份点位文件失败（继续写入）: {exc}")

    ordered = sorted(entries.values(), key=lambda e: (e.date or _date.min, e.period),
                     reverse=True)
    body = "\n".join(format_points_line(e.date, e.period, list(e.points))
                     for e in ordered) + "\n"

    if cfg.read_only:
        write_text_atomic(str(target), body, newline="\r\n")
    else:
        target, outcome = write_shared_guarded(
            cfg, target, body, expect_hash=expect_hash,
            fallback=cfg.cache_dir / "points_copy.txt")
        if outcome == "aborted":
            return

    back = load_points_archive(str(target))
    if len(back) != len(ordered):
        raise RuntimeError(
            f"写回后复核失败：期望 {len(ordered)} 期，实得 {len(back)} 期")
    observability.info(f"已原子写回 {len(back)} 期点位 → {target}")


def save_points(cfg: Config, period: int, d: _date, points: list[int],
                overwrite: bool = True) -> dict:
    """校验并原子写入点位。"""
    ok, msg = validate_core_points(points)
    if not ok:
        return {"status": "error", "message": msg}

    entries = load_points_any(cfg)

    # §8.5：read_write 写回共享前要比对「读取时」的 hash，检测对方并发修改
    expect_hash = None
    if not cfg.read_only and cfg.shared_points_file.exists():
        try:
            expect_hash = file_hash(cfg.shared_points_file)
        except OSError as exc:
            observability.warn(f"读取共享点位档案 hash 失败: {exc}")

    existed = period in entries
    if existed and not overwrite:
        return {"status": "skipped",
                "message": f"期号 {period:07d} 已存在且未开启覆盖"}

    entries[period] = PointEntry(period=period, date=d, points=tuple(sorted(points)))
    try:
        _write_points(cfg, entries, expect_hash=expect_hash)
    except (OSError, RuntimeError) as exc:
        return {"status": "error", "message": f"写入点位失败: {exc}"}

    return {
        "status": "ok",
        "action": "updated" if existed else "created",
        "period": period,
        "date": d.isoformat(),
        "points": sorted(points),
        "points_str": " ".join(f"{x:02d}" for x in sorted(points)),
        "total_records": len(entries),
    }


def entry_from_raw(cfg: Config, raw: str, period: int | None = None,
                   d: _date | None = None) -> tuple[dict, TargetInfo]:
    """非交互录入：解析纯号码文本 → 校验 → 落盘。"""
    draws, _ = _draws_for_target(cfg)
    info = infer_target(cfg, draws, load_points_any(cfg))
    use_period = period if period is not None else info.period
    use_date = d if d is not None else info.date

    nums = parse_points_input(raw)
    ok, msg = validate_core_points(nums)
    if not ok:
        return {"status": "error", "message": msg}, info
    return save_points(cfg, use_period, use_date, nums), info


def entry_interactive(cfg: Config) -> dict:
    """交互录入：回显推断出的目标期号，请用户粘贴 20 个号码。"""
    draws, _ = _draws_for_target(cfg)
    info = infer_target(cfg, draws, load_points_any(cfg))
    print(f"\n{info.render()}")
    if info.already_input:
        print(f"  已有号码: {' '.join(f'{x:02d}' for x in info.existing_points)}")
    print("请粘贴 20 个点位号码（任意分隔符，直接回车取消）：")

    raw = input("> ").strip()
    if not raw:
        return {"status": "cancelled", "message": "用户取消"}

    nums = parse_points_input(raw)
    ok, msg = validate_core_points(nums)
    if not ok:
        return {"status": "error", "message": msg}

    print(f"  解析结果: {' '.join(f'{x:02d}' for x in nums)}")
    confirm = input(f"确认写入 {info.period_str} ({info.date})? [Y/n] ").strip().lower()
    if confirm and confirm not in ("y", "yes"):
        return {"status": "cancelled", "message": "用户取消"}

    return save_points(cfg, info.period, info.date, nums)


def _draws_for_target(cfg: Config):
    from . import source
    return source.load_history_only(cfg, allow_fetch=False)
