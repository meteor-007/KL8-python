# -*- coding: utf-8 -*-
"""双源增量抓取 + 原子写回（§8.2 / §8.5）。

数据源：
  17500  https://m.17500.cn/tgj/api/kl8/getTbList      字段 qihao/opencode/opentime
  CWL    https://www.cwl.gov.cn/.../findDrawNotice      字段 code/date/kjhyjsx|red

默认 mode=read_only：抓取结果写入本项目 data/cache/ 下的副本，
绝不触碰共享档案（§8.5）。
"""
from __future__ import annotations

import shutil
from datetime import date as _date
from datetime import datetime
from pathlib import Path

from .config import Config
from .data_io import (DRAW_SIZE, NUM_BALLS, Draw, ParseReport, file_hash,
                      load_draws, sort_draws, write_text_atomic,
                      write_shared_guarded, format_numbers_line)
from . import observability

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

URL_17500 = "https://m.17500.cn/tgj/api/kl8/getTbList"
URL_CWL = ("https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/"
           "findDrawNotice?name=kl8&issueCount={n}")


def _clean_numbers(raw: str) -> list[int] | None:
    nums, seen = [], set()
    for tok in str(raw).replace(",", "-").replace(" ", "-").split("-"):
        tok = tok.strip()
        if not tok or not tok.isdigit():
            continue
        v = int(tok)
        if 1 <= v <= NUM_BALLS and v not in seen:
            seen.add(v)
            nums.append(v)
    return sorted(nums) if len(nums) == DRAW_SIZE else None


def _parse_date(raw: str) -> _date | None:
    if not raw:
        return None
    txt = str(raw).split("(")[0].split(" ")[0].strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    return None


def fetch_from_17500(cfg: Config) -> list[Draw]:
    import requests
    out: list[Draw] = []
    try:
        resp = requests.get(URL_17500, headers={"User-Agent": UA},
                            timeout=int(cfg.fetch.timeout_sec or 10))
        if resp.status_code != 200:
            observability.warn(f"[17500] HTTP {resp.status_code}")
            return out
        for item in (resp.json() or {}).get("list") or []:
            issue = item.get("qihao")
            nums = _clean_numbers(item.get("opencode") or "")
            d = _parse_date(item.get("opentime") or "")
            if not issue or not nums or d is None:
                observability.warn(f"[17500] 跳过畸形记录: {str(item)[:80]}")
                continue
            out.append(Draw(period=int(issue), date=d, numbers=tuple(nums)))
    except Exception as exc:
        observability.warn(f"[17500] 抓取失败: {exc}")
    return out


def fetch_from_cwl(cfg: Config) -> list[Draw]:
    import requests
    out: list[Draw] = []
    url = URL_CWL.format(n=int(cfg.fetch.per_source_limit or 150))
    try:
        resp = requests.get(url, headers={"User-Agent": UA, "Referer":
                            "https://www.cwl.gov.cn/ygkj/kjgs/kl8/index.shtml"},
                            timeout=int(cfg.fetch.timeout_sec or 10))
        if resp.status_code != 200:
            observability.warn(f"[CWL] HTTP {resp.status_code}")
            return out
        for item in (resp.json() or {}).get("result") or []:
            issue = item.get("code")
            raw = item.get("kjhyjsx") or item.get("red") or ""
            nums = _clean_numbers(raw)
            d = _parse_date(item.get("date") or "")
            if not issue or not nums or d is None:
                observability.warn(f"[CWL] 跳过畸形记录: {str(item)[:80]}")
                continue
            out.append(Draw(period=int(issue), date=d, numbers=tuple(nums)))
    except Exception as exc:
        observability.warn(f"[CWL] 抓取失败: {exc}")
    return out


def fetch_from_sources(cfg: Config) -> tuple[list[Draw], str]:
    """按配置顺序尝试各源，返回 (抓到的期, 命中源名)。全部失败返回 ([], '')。"""
    for name in (cfg.fetch.sources or ["17500", "cwl"]):
        if name == "17500":
            got = fetch_from_17500(cfg)
        elif name == "cwl":
            got = fetch_from_cwl(cfg)
        else:
            observability.warn(f"未知数据源: {name}")
            continue
        if got:
            return got, name
    return [], ""


# ── 写回 ──────────────────────────────────────────────────────

def _target_path(cfg: Config) -> Path:
    """read_only → 写本项目副本；read_write → 写共享档案（§8.5）。"""
    if cfg.read_only:
        return cfg.cache_dir / "history_copy.txt"
    return cfg.shared_history_file


def _backup_file(cfg: Config, target: Path) -> None:
    """写回前备份目标文件（§8.2）。备份失败仅告警，不阻断写入。"""
    if not target.exists() or not int(cfg.fetch.backup_before_write or 0):
        return
    backup_dir = cfg.cache_dir / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        shutil.copy2(target, backup_dir / f"{target.stem}_{stamp}.bak")
    except OSError as exc:
        observability.warn(f"备份失败（继续写入）: {exc}")


def write_history(cfg: Config, draws: list[Draw],
                  expect_hash: str | None = None) -> Path:
    """原子写回开奖历史。写前备份，写后复核（§8.2 / §8.5）。

    read_only → 只写本项目副本；read_write → 经 §8.5 保护写回共享档案
    （hash 比对 / 退避重试 / 降级写副本）。
    """
    ordered = sort_draws(draws)
    body = "\n".join(format_numbers_line(d.date, d.period, list(d.numbers))
                     for d in ordered) + "\n"

    if cfg.read_only:
        target = _target_path(cfg)
        _backup_file(cfg, target)
        write_text_atomic(str(target), body, newline="\r\n")
    else:
        target = cfg.shared_history_file
        _backup_file(cfg, target)
        target, outcome = write_shared_guarded(
            cfg, target, body, expect_hash=expect_hash,
            fallback=cfg.cache_dir / "history_copy.txt")
        if outcome == "aborted":                      # 对方已改，本轮不写
            return target

    # 写入后复核：能被重新解析且期数一致
    rep = ParseReport()
    back = load_draws(str(target), rep)
    if len(back) != len(ordered) or rep.malformed:
        raise RuntimeError(
            f"写回后复核失败：期望 {len(ordered)} 期，实得 {len(back)} 期，"
            f"畸形 {rep.malformed} 行")
    observability.info(f"已原子写回 {len(back)} 期 → {target}")
    return target


def fetch_incremental(cfg: Config, base: list[Draw] | None = None,
                      dry_run: bool = False) -> list[Draw] | None:
    """增量抓取。

    返回**合并后的完整历史**（抓取失败且本地有数据时返回本地数据）。
    完全无数据时返回 None。`dry_run=True` 时只抓取与合并、不写回磁盘（§8.2）。
    """
    if base is None:
        base = _local_history(cfg)

    # §8.5：read_write 写回共享前要比对「读取时」的 hash
    expect_hash = None
    if not cfg.read_only and cfg.shared_history_file.exists():
        try:
            expect_hash = file_hash(cfg.shared_history_file)
        except OSError as exc:
            observability.warn(f"读取共享档案 hash 失败: {exc}")

    existing = {d.period for d in base}
    got, src = fetch_from_sources(cfg)
    fresh = [d for d in got if d.period not in existing]

    if not got:
        observability.warn("所有数据源均不可用")
        return base or None

    merged = sort_draws(list(base) + fresh)
    observability.info(
        f"源 {src}: 取得 {len(got)} 期，其中新增 {len(fresh)} 期；"
        f"合并后共 {len(merged)} 期")

    if fresh and dry_run:
        observability.info(f"dry-run：检出 {len(fresh)} 期新数据，跳过写回。")
    elif fresh:
        try:
            write_history(cfg, merged, expect_hash=expect_hash)
        except (OSError, RuntimeError) as exc:
            observability.warn(f"写回失败，仅在内存中使用: {exc}")
    return merged


def _local_history(cfg: Config) -> list[Draw]:
    """本地已有历史：共享档案与本项目副本**合并**（§8.5）。

    只读模式下的抓取写回落在 `data/cache/history_copy.txt`，副本必须参与读取，
    否则抓到的增量会被静默丢弃；副本条目优先。
    """
    merged: dict[int, Draw] = {}
    for path in (cfg.shared_history_file, cfg.cache_dir / "history_copy.txt"):
        if path and path.exists():
            try:
                for d in load_draws(str(path)):
                    merged[d.period] = d
            except (OSError, UnicodeDecodeError) as exc:
                observability.warn(f"读取 {path} 失败: {exc}")
    return sort_draws(list(merged.values())) if merged else []


def get_latest_issue_and_date(cfg: Config) -> tuple[int, _date | None]:
    draws = _local_history(cfg)
    if not draws:
        return 0, None
    newest = sort_draws(draws)[0]
    return newest.period, newest.date
