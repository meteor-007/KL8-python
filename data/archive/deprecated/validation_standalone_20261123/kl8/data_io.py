# -*- coding: utf-8 -*-
"""数据解析与写回（§2.1 / §2.2 / §8.4）。

两种文件格式：
  点位  date:2026-06-11,period:2026152,points:04 10 12 ... 80
  开奖  date:2026-06-10,period:2026151,numbers:12-24-44-...-78

解析必须**两段锚定**：先用锚点取出 date / period / payload 三段，
再只对 payload 分词。若对整行分词，`date:2026-06-11` 会被 `-` 切碎
（v1.0 的正则缺陷，见 §8.4）。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date as _date

NUM_BALLS = 80
DRAW_SIZE = 20
POINTS_SIZE = 20

RE_DATE = re.compile(r"date:([0-9]{4}-[0-9]{2}-[0-9]{2})")
RE_PERIOD = re.compile(r"period:([0-9]+)")
RE_PAYLOAD = re.compile(r"(?:points|numbers):(.+)$")
SPLITTER = re.compile(r"[\s,\-、，;；|]+")


@dataclass(frozen=True)
class Draw:
    """一期开奖记录。numbers 已升序去重。"""
    period: int
    date: _date
    numbers: tuple[int, ...]

    def __post_init__(self):
        # 高频只读派生量：回测中 numbers_set 会被访问数百万次，预计算一次。
        object.__setattr__(self, "_numbers_set", frozenset(self.numbers))

    @property
    def numbers_set(self) -> frozenset[int]:
        return self._numbers_set

    @property
    def period_str(self) -> str:
        return f"{self.period:07d}"

    @property
    def year(self) -> int:
        return self.period // 1000

    @property
    def index_in_year(self) -> int:
        return self.period % 1000


@dataclass
class PointEntry:
    """一期点位记录。"""
    period: int
    date: _date | None
    points: tuple[int, ...]
    dirty: bool = False
    reason: str = ""

    @property
    def points_set(self) -> frozenset[int]:
        return frozenset(self.points)

    @property
    def period_str(self) -> str:
        return f"{self.period:07d}"


@dataclass
class ParseReport:
    """解析统计，供 §2.6 数据体检使用。"""
    total_lines: int = 0
    blank_lines: int = 0
    parsed: int = 0
    malformed: int = 0
    malformed_details: list[str] = field(default_factory=list)

    def note_malformed(self, lineno: int, raw: str) -> None:
        self.malformed += 1
        if len(self.malformed_details) < 20:
            self.malformed_details.append(f"第{lineno}行: {raw.strip()[:80]}")


def read_text(path: str) -> str:
    """读文本，保留原始换行符（newline='' 不做任何转换）。

    使用 utf-8-sig 以便在存在 BOM 时静默剥离，无 BOM 时为无操作。
    """
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return f.read()


def detect_newline(text: str) -> str:
    """探测文件实际换行序列，默认 CRLF（实测两个档案均为 CRLF）。"""
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"


def write_text_atomic(path: str, content: str, newline: str = "\r\n") -> None:
    """原子写回，显式控制换行符（§8.2 / §8.4）。

    必须显式写 `\\r\\n`：用 `open(..., 'w')` 的默认 newline 会把内容里的
    `\\r\\n` 转成 `\\r\\r\\n`，用 `newline='\\n'` 又会把 CRLF 悄悄转成 LF。
    两者都会静默改写共享文件。
    """
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    body = content.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


def file_hash(path) -> str:
    """文件内容 SHA-256（UTF-8 文本口径），用于 §8.5 的并发改动检测。"""
    import hashlib
    return hashlib.sha256(read_text(str(path)).encode("utf-8")).hexdigest()


def write_shared_guarded(cfg, target, body: str, expect_hash: str | None = None,
                         fallback=None) -> tuple:
    """共享目录写回保护（§8.5）。

    ① 写前重读目标并比对 `expect_hash`，不一致（说明对方已改）→ **放弃本轮写回**；
    ② 通过则走 §8.2 原子写回；
    ③ `PermissionError` → 退避重试 3 次，仍失败则**降级写本项目副本**并告警。

    返回 `(实际写入路径, 结果标签)`，标签取值 `written` / `aborted` / `fallback`。
    """
    from . import observability

    if expect_hash is not None and target.exists():
        try:
            if file_hash(target) != expect_hash:
                observability.warn(
                    f"共享档案 {target} 已被外部修改，放弃本轮写回（§8.5）。")
                return target, "aborted"
        except OSError as exc:
            observability.warn(f"写回前复核失败，放弃本轮写回（§8.5）: {exc}")
            return target, "aborted"

    import time
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            write_text_atomic(str(target), body, newline="\r\n")
            return target, "written"
        except PermissionError as exc:                # Windows 下对方占用
            last_exc = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    if fallback is not None:
        observability.warn(
            f"共享档案被占用，写回失败（{last_exc}）；"
            f"降级写入本项目副本 {fallback}（§8.5）。")
        write_text_atomic(str(fallback), body, newline="\r\n")
        return fallback, "fallback"
    raise last_exc if last_exc else RuntimeError("写回失败")


# ── 两段锚定解析 ──────────────────────────────────────────────

def parse_line(line: str) -> tuple[_date | None, int | None, list[int]] | None:
    """解析单行。返回 (date, period, numbers) 或 None（格式畸形）。

    锚点提取 date / period / payload 三段，**只对 payload 分词**。
    """
    m_date = RE_DATE.search(line)
    m_period = RE_PERIOD.search(line)
    m_payload = RE_PAYLOAD.search(line)
    if not m_period or not m_payload:
        return None

    payload = m_payload.group(1).strip()
    nums: list[int] = []
    seen: set[int] = set()
    for tok in SPLITTER.split(payload):
        tok = tok.strip()
        if not tok or not tok.isdigit():
            continue
        val = int(tok)
        if 1 <= val <= NUM_BALLS and val not in seen:
            seen.add(val)
            nums.append(val)
    if not nums:
        return None

    d: _date | None = None
    if m_date:
        try:
            y, mo, dd = (int(x) for x in m_date.group(1).split("-"))
            d = _date(y, mo, dd)
        except (ValueError, TypeError):
            d = None

    return d, int(m_period.group(1)), sorted(nums)


def parse_points_input(raw: str) -> list[int]:
    """解析用户输入的点位文本，兼容任意混排分隔符。

    支持：空格 / 中英文逗号 / 顿号 / 分号 / 连字符 / 竖线 / 换行 / 制表符，
    以及 Excel 直接复制粘贴的多行文本。
    """
    if not raw:
        return []
    nums: list[int] = []
    seen: set[int] = set()
    for tok in SPLITTER.split(raw):
        tok = tok.strip()
        if not tok or not tok.isdigit():
            continue
        val = int(tok)
        if 1 <= val <= NUM_BALLS and val not in seen:
            seen.add(val)
            nums.append(val)
    return sorted(nums)


def validate_core_points(nums: list[int]) -> tuple[bool, str]:
    """点位契约校验：恰好 20 个、范围 1–80、无重复。"""
    if not isinstance(nums, (list, tuple)):
        return False, "点位数据必须是数字列表"
    if len(nums) != POINTS_SIZE:
        return False, f"点位数量异常：解析出 {len(nums)} 个号码，必须恰好 {POINTS_SIZE} 个"
    out_of_range = [x for x in nums if not (1 <= x <= NUM_BALLS)]
    if out_of_range:
        return False, f"存在越界号码：{out_of_range}（快乐8范围 01–80）"
    if len(set(nums)) != len(nums):
        return False, "存在重复号码"
    return True, "校验通过"


def format_points_line(d: _date | None, period: int, points: list[int]) -> str:
    pts = " ".join(f"{x:02d}" for x in sorted(points))
    ds = d.isoformat() if d else ""
    return f"date:{ds},period:{period:07d},points:{pts}"


def format_numbers_line(d: _date | None, period: int, numbers: list[int]) -> str:
    nums = "-".join(f"{x:02d}" for x in sorted(numbers))
    ds = d.isoformat() if d else ""
    return f"date:{ds},period:{period:07d},numbers:{nums}"


# ── 加载 ──────────────────────────────────────────────────────

def load_draws(path: str, report: ParseReport | None = None) -> list[Draw]:
    """加载开奖历史。返回**按日期降序（最新在前）**，同日期按期号降序。

    只接受恰好 20 个号码的记录；其余计入畸形行。
    """
    rep = report if report is not None else ParseReport()
    text = read_text(path)
    draws: dict[int, Draw] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            rep.blank_lines += 1
            continue
        rep.total_lines += 1
        parsed = parse_line(line)
        if parsed is None:
            rep.note_malformed(lineno, line)
            continue
        d, period, nums = parsed
        if len(nums) != DRAW_SIZE or d is None:
            rep.note_malformed(lineno, line)
            continue
        # 同期号重复时保留先出现的（最新在前，先出现即更新的记录）
        if period not in draws:
            draws[period] = Draw(period=period, date=d, numbers=tuple(nums))
            rep.parsed += 1
    return sort_draws(draws.values())


def load_points_archive(path: str, report: ParseReport | None = None
                        ) -> dict[int, PointEntry]:
    """加载点位档案。返回 {period: PointEntry}。

    语义校验（期号存在性、日期重复、日期倒挂）由 source.py 的体检环节完成，
    此处只做格式层面的解析。
    """
    rep = report if report is not None else ParseReport()
    text = read_text(path)
    entries: dict[int, PointEntry] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            rep.blank_lines += 1
            continue
        rep.total_lines += 1
        parsed = parse_line(line)
        if parsed is None:
            rep.note_malformed(lineno, line)
            continue
        d, period, nums = parsed
        if len(nums) != POINTS_SIZE:
            rep.note_malformed(lineno, line)
            continue
        if period not in entries:
            entries[period] = PointEntry(period=period, date=d, points=tuple(nums))
            rep.parsed += 1
    return entries


def sort_draws(draws) -> list[Draw]:
    """按 (日期, 期号) 降序 —— 最新在前。以日期为准，不用期号算术（§2.3）。"""
    return sorted(draws, key=lambda d: (d.date, d.period), reverse=True)


def draws_to_text(draws: list[Draw]) -> str:
    return "\n".join(
        format_numbers_line(d.date, d.period, list(d.numbers)) for d in draws
    )


def points_to_text(entries: dict[int, PointEntry]) -> str:
    ordered = sorted(entries.values(), key=lambda e: (e.date or _date.min, e.period),
                     reverse=True)
    return "\n".join(
        format_points_line(e.date, e.period, list(e.points)) for e in ordered
    )
