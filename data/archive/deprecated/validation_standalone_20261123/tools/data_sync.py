# -*- coding: utf-8 -*-
"""三项目数据一致性校验（只读）。

规范见 docs/5agent-matrix/20261113-kl8-integration/contract.md §2：
- 历史：date/period/numbers，每期 20 个 1–80 不重复号
- 点位：date/period/points，每期 20 个 1–80 不重复号
- 比较按“期号集合 + 每期号码集合”，不依赖行顺序/换行
- 非法行（字段缺失/日期格式/号码数量/范围/重复）不参与比较，但会计数并提示
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

HISTORY_REQUIRED = ("date", "period", "numbers")
POINTS_REQUIRED = ("date", "period", "points")
DRAW_SIZE = 20
NUM_MIN, NUM_MAX = 1, 80
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_numbers(nums: list[int]) -> bool:
    return (len(nums) == DRAW_SIZE and len(set(nums)) == DRAW_SIZE
            and all(NUM_MIN <= n <= NUM_MAX for n in nums))


def _parse_kv(line: str) -> dict[str, str]:
    return dict(kv.split(":", 1) for kv in line.split(",") if ":" in kv)


def _parse_line(line: str, kind: str) -> tuple[tuple[int, str, frozenset[int]] | None, str | None]:
    """返回 ((period, date, numbers), None) 或 (None, 原因)。"""
    parts = _parse_kv(line)
    required = HISTORY_REQUIRED if kind == "history" else POINTS_REQUIRED
    missing = [k for k in required if k not in parts]
    if missing:
        return None, f"缺少字段 {missing}"
    try:
        period = int(parts["period"])
    except ValueError:
        return None, "period 非整数"
    date_str = parts["date"]
    if not DATE_RE.match(date_str):
        return None, "date 非 YYYY-MM-DD"
    key = "numbers" if kind == "history" else "points"
    try:
        raw = [int(x) for x in (parts[key].split("-") if kind == "history"
                                else parts[key].split()) if x]
    except ValueError:
        return None, f"{key} 含非整数"
    if not _valid_numbers(raw):
        return None, f"{key} 非 20 个/去重/1-80"
    return (period, date_str, frozenset(raw)), None


def load_history(path: str | Path) -> dict[int, tuple[str, frozenset[int]]]:
    return _load(path, "history")


def load_points(path: str | Path) -> dict[int, tuple[str, frozenset[int]]]:
    return _load(path, "points")


def _load(path: str | Path, kind: str) -> dict[int, tuple[str, frozenset[int]]]:
    out: dict[int, tuple[str, frozenset[int]]] = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        parsed, _reason = _parse_line(line, kind)
        if parsed is None:
            continue
        period, date_str, nums = parsed
        out[period] = (date_str, nums)
    return out


def scan_invalid(path: str | Path, kind: str = "history") -> list[dict]:
    """返回格式/数量/范围不合法的行（不参与比较）。"""
    out: list[dict] = []
    p = Path(path)
    if not p.exists():
        return out
    for lineno, line in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parsed, reason = _parse_line(line, kind)
        if parsed is None:
            parts = _parse_kv(line)
            try:
                period = int(parts["period"])
            except (KeyError, ValueError):
                period = None
            out.append({"line": lineno, "period": period, "reason": reason or "非法行"})
    return out


@dataclass
class CompareResult:
    kind: str
    source: str
    target: str
    source_count: int
    target_count: int
    source_latest: int | None
    target_latest: int | None
    missing: list[int]        # 源有、目标无（目标落后）
    extra: list[int]          # 目标有、源无
    mismatched: list[int]     # 同期号码不同
    source_invalid: int = 0   # 源文件非法行数
    target_invalid: int = 0   # 目标文件非法行数

    @property
    def ok(self) -> bool:
        return (not self.missing and not self.extra and not self.mismatched
                and self.source_invalid == 0 and self.target_invalid == 0)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "source": self.source,
            "target": self.target,
            "source_count": self.source_count,
            "target_count": self.target_count,
            "source_latest": self.source_latest,
            "target_latest": self.target_latest,
            "missing": self.missing,
            "extra": self.extra,
            "mismatched": self.mismatched,
            "source_invalid": self.source_invalid,
            "target_invalid": self.target_invalid,
            "ok": self.ok,
        }


def compare(kind: str, source_path: str | Path,
            target_path: str | Path) -> CompareResult:
    loader = load_history if kind == "history" else load_points
    src = loader(source_path)
    tgt = loader(target_path)
    src_periods, tgt_periods = set(src), set(tgt)
    common = src_periods & tgt_periods
    return CompareResult(
        kind=kind,
        source=str(source_path),
        target=str(target_path),
        source_count=len(src),
        target_count=len(tgt),
        source_latest=max(src_periods) if src_periods else None,
        target_latest=max(tgt_periods) if tgt_periods else None,
        missing=sorted(src_periods - tgt_periods),
        extra=sorted(tgt_periods - src_periods),
        mismatched=sorted(p for p in common if src[p][1] != tgt[p][1]),
        source_invalid=len(scan_invalid(source_path, kind)),
        target_invalid=len(scan_invalid(target_path, kind)),
    )


def summarize(path: str | Path, kind: str = "history") -> dict:
    loader = load_history if kind == "history" else load_points
    hist = loader(path)
    invalid = scan_invalid(path, kind)
    return {
        "path": str(path),
        "count": len(hist),
        "latest": max(hist) if hist else None,
        "oldest": min(hist) if hist else None,
        "invalid_count": len(invalid),
        "invalid_samples": invalid[:5],
    }


def render(results: Iterable[CompareResult]) -> str:
    lines = ["| 对象 | 源/目标 | 源期数 | 目标期数 | 源最新 | 目标最新 | 缺失 | 多余 | 不一致 | 非法行(源/目标) | 结论 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(
            f"| {r.kind} | {r.source} → {r.target} | {r.source_count} | {r.target_count} | "
            f"{r.source_latest} | {r.target_latest} | {len(r.missing)} | {len(r.extra)} | "
            f"{len(r.mismatched)} | {r.source_invalid}/{r.target_invalid} | "
            f"{'一致' if r.ok else '有差异'} |")
    return "\n".join(lines)


def apply_sorted(source_path: str | Path, target_path: str | Path,
                 order: str = "descending", kind: str = "history",
                 backup: bool = True) -> bool:
    """按指定期号顺序写出（A/B 倒序、C 正序）；号码升序归一化；写前备份、原子替换。"""
    if order not in ("ascending", "descending", "preserve"):
        raise ValueError(f"未知排序 {order}")
    if order == "preserve":
        return apply_copy(source_path, target_path)
    src, tgt = Path(source_path).resolve(), Path(target_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    if src == tgt:
        raise ValueError("源与目标相同，拒绝覆盖")
    rows: dict[int, str] = {}
    for lineno, line in enumerate(src.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parsed, reason = _parse_line(line, kind)
        if parsed is None:
            raise ValueError(f"源文件第 {lineno} 行非法：{reason}")
        period, date_str, nums = parsed
        key = "numbers" if kind == "history" else "points"
        sep = "-" if kind == "history" else " "
        body = sep.join(f"{n:02d}" for n in sorted(nums))
        rows[period] = f"date:{date_str},period:{period:07d},{key}:{body}"
    ordered = sorted(rows.items(), reverse=(order == "descending"))
    body = "\n".join(line for _p, line in ordered) + "\n"
    tgt.parent.mkdir(parents=True, exist_ok=True)
    backed_up = tgt.exists() and backup
    if backed_up:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(tgt, tgt.with_name(f"{tgt.name}.{stamp}.bak"))
    tmp = tgt.with_name(tgt.name + ".tmp")
    try:
        tmp.write_bytes(body.replace("\n", "\r\n").encode("utf-8"))
        tmp.replace(tgt)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return backed_up


def apply_copy(source_path: str | Path, target_path: str | Path) -> bool:
    """把源文件原子复制到目标；返回目标原本是否存在（是否产生备份）。"""
    src, tgt = Path(source_path).resolve(), Path(target_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    if src == tgt:
        raise ValueError("源与目标相同，拒绝覆盖")
    tgt.parent.mkdir(parents=True, exist_ok=True)
    backed_up = tgt.exists()
    if backed_up:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(tgt, tgt.with_name(f"{tgt.name}.{stamp}.bak"))
    tmp = tgt.with_name(tgt.name + ".tmp")
    try:
        shutil.copy2(src, tmp)
        tmp.replace(tgt)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return backed_up