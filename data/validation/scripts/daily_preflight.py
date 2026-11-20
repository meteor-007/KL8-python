# -*- coding: utf-8 -*-
"""每日前置检查：自动推断目标期、校验并归档点位、按内容识别图表角色。

用法：
    python scripts/daily_preflight.py --points "07 08 13 ..."
    python scripts/daily_preflight.py --points-file today_points.txt
    python scripts/daily_preflight.py --dry-run            # 只看推断结果，不写档案

输出：
    - 控制台摘要
    - data/state/preflight.json（供后续生成器读取）

退出码：0 正常；2 有警告（可选数据缺失）；1 致命错误。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import xlrd

from kl8.config import load_config
from kl8.data_io import load_draws, parse_points_input, validate_core_points
from kl8.points_input import next_period_after

POINTS_ARCHIVE = Path(os.environ.get(
    "KL8_POINTS_ARCHIVE", str(ROOT / "data/cache/points_archive.txt")))
POINTS_COPY = POINTS_ARCHIVE.with_name("points_copy.txt")
PREFLIGHT_JSON = ROOT / "data/state/preflight.json"
FILE_DIR = ROOT / "file"

ROLE_DW = "点位图"
ROLE_FX = "高概率图表"
ROLE_ZD = "找胆图"


def fmt(nums) -> str:
    return " ".join(f"{n:02d}" for n in nums)


def _sheet_names(path: Path) -> list[str]:
    wb = xlrd.open_workbook(str(path), on_demand=True, formatting_info=False)
    try:
        return wb.sheet_names()
    finally:
        wb.release_resources()


def _find_sheet(wb, *names):
    for target in names:
        for sh in wb.sheets():
            if sh.name.strip() == target:
                return sh
    return None


def classify_charts(target_period: int, latest_period: int) -> dict:
    """按 sheet 内容识别 file/ 下每个 xls 的角色，并按「期号匹配 > 修改时间」选最新。"""
    roles: dict[str, list[dict]] = {ROLE_DW: [], ROLE_FX: [], ROLE_ZD: []}
    for path in sorted(FILE_DIR.glob("*.xls")):
        if path.name.startswith("~$"):
            continue
        try:
            names = _sheet_names(path)
        except Exception as exc:
            print(f"  ⚠ 无法读取 {path.name}: {exc}")
            continue
        info = {"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "name": path.name,
                "mtime": path.stat().st_mtime,
                "sheets": len(names)}
        if "快乐8点位图（思静分享）" in names:
            roles[ROLE_DW].append(info)
        if any("伴侣组合" in n or "任意两码组合" in n for n in names):
            roles[ROLE_FX].append(info)
        if "快乐8游戏找胆图（初级版）" in names:
            roles[ROLE_ZD].append(info)

    picked: dict[str, dict | None] = {}
    for role, items in roles.items():
        if not items:
            picked[role] = None
            continue

        def score(x: dict) -> tuple[int, float]:
            s = 0
            if str(target_period) in x["name"]:
                s += 100
            elif str(latest_period) in x["name"]:
                s += 50
            return s, x["mtime"]

        picked[role] = max(items, key=score)
    return picked


def inspect_fx(path: Path) -> dict:
    out = {"has_pairs": False, "has_matrix": False, "pairs_rows": 0, "matrix_rows": 0}
    wb = xlrd.open_workbook(str(path), on_demand=True, formatting_info=False)
    try:
        sh = _find_sheet(wb, "图表14任意两码组合", "任意两码组合")
        if sh is not None:
            out["pairs_rows"] = sh.nrows
            out["has_pairs"] = sh.nrows > 1
        sh = _find_sheet(wb, "图表16伴侣组合", "伴侣组合")
        if sh is not None:
            out["matrix_rows"] = sh.nrows
            out["has_matrix"] = sh.nrows > 1
    finally:
        wb.release_resources()
    return out


def inspect_zd(path: Path) -> dict:
    out = {"coverage_end": 0, "kill1_end": 0, "kill2_end": 0}
    wb = xlrd.open_workbook(str(path), on_demand=True, formatting_info=False)
    try:
        for sheet_name, key in (("快乐8游戏杀号（1）", "kill1_end"),
                                ("快乐8游戏杀号（2）", "kill2_end")):
            sh = _find_sheet(wb, sheet_name)
            if sh is None:
                continue
            periods = []
            for r in range(1, min(sh.nrows, 800)):
                v = sh.cell_value(r, 0)
                s = str(v).replace(".0", "")
                if s.isdigit():
                    p = int(float(v))
                    periods.append(p + 2026000 if p < 1000 else p)
            if periods:
                out[key] = max(periods)
        sh = _find_sheet(wb, "快乐8游戏找胆图（初级版）")
        if sh is not None:
            periods = []
            for r in range(1, min(sh.nrows, 800)):
                v = sh.cell_value(r, 0)
                s = str(v).replace(".0", "")
                if s.isdigit():
                    p = int(float(v))
                    periods.append(p + 2026000 if p < 1000 else p)
            if periods:
                out["coverage_end"] = max(periods)
        out["coverage_end"] = max(out["coverage_end"],
                                  out["kill1_end"], out["kill2_end"])
    finally:
        wb.release_resources()
    return out


def load_archive() -> dict[int, list[int]]:
    pts: dict[int, list[int]] = {}
    if not POINTS_ARCHIVE.exists():
        return pts
    for line in POINTS_ARCHIVE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = dict(kv.split(":", 1) for kv in line.split(",") if ":" in kv)
        if "period" in parts and "points" in parts:
            pts[int(parts["period"])] = [int(x) for x in parts["points"].split()]
    return pts


def save_archive(pts: dict[int, list[int]], dates: dict[int, str]) -> None:
    lines = [f"date:{dates.get(p, '')},period:{p:07d},points:{fmt(v)}"
             for p, v in sorted(pts.items(), reverse=True)]
    POINTS_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    POINTS_ARCHIVE.write_bytes(("\n".join(lines) + "\n").replace("\n", "\r\n").encode("utf-8"))
    POINTS_COPY.write_bytes(POINTS_ARCHIVE.read_bytes())


def read_dates() -> dict[int, str]:
    """从档案原始行里保留每期日期。"""
    out: dict[int, str] = {}
    if not POINTS_ARCHIVE.exists():
        return out
    for line in POINTS_ARCHIVE.read_text(encoding="utf-8").splitlines():
        parts = dict(kv.split(":", 1) for kv in line.split(",") if ":" in kv)
        if "period" in parts and "date" in parts:
            out[int(parts["period"])] = parts["date"]
    return out


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", default=None, help='一行 20 个点位，如 "01 02 ..."')
    ap.add_argument("--points-file", default=None, help="从文件读取点位")
    ap.add_argument("--dry-run", action="store_true", help="只检查，不写档案")
    ap.add_argument("--force", action="store_true", help="目标期已存在且号码不同时强制覆盖")
    args = ap.parse_args(argv)

    cfg = load_config(None)
    draws = load_draws(str(cfg.shared_history_file))
    if not draws:
        print("✗ 开奖档案为空，无法推断目标期", file=sys.stderr)
        return 1
    latest = max(draws, key=lambda d: d.period)

    # 目标期与日期
    guess_date = latest.date + timedelta(days=1)
    target_period = next_period_after(latest.period, guess_date,
                                      {d.period for d in draws})

    print("=" * 66)
    print("每日前置检查")
    print("=" * 66)
    print(f"最新开奖      : {latest.period:07d}  {latest.date}")
    print(f"推断目标期    : {target_period:07d}  {guess_date}")

    # 点位
    raw = args.points
    if raw is None and args.points_file:
        raw = Path(args.points_file).read_text(encoding="utf-8-sig")
    points: list[int] = []
    points_status = "未提供"
    if raw:
        points = parse_points_input(raw)
        ok, msg = validate_core_points(points)
        if not ok:
            print(f"✗ 点位校验失败：{msg}", file=sys.stderr)
            return 1
        points_status = f"{len(points)} 个，校验通过"
        print(f"今日点位      : {fmt(points)}")
    else:
        print("今日点位      : 未提供（仅推断目标期，不写档案）")

    # 图表识别
    charts = classify_charts(target_period, latest.period)
    warnings: list[str] = []
    result_charts: dict[str, dict] = {}
    for role, info in charts.items():
        if info is None:
            warnings.append(f"未找到{role}（按 sheet 内容识别）")
            result_charts[role] = {}
            print(f"{role:<10}: ✗ 未找到")
            continue
        entry = {"path": info["path"], "name": info["name"], "sheets": info["sheets"]}
        if role == ROLE_FX:
            entry.update(inspect_fx(ROOT / info["path"]))
            if not entry["has_pairs"]:
                warnings.append("高概率图表缺少《任意两码组合》数据，配对增益按 0 计")
        if role == ROLE_ZD:
            entry.update(inspect_zd(ROOT / info["path"]))
            if entry["coverage_end"] < latest.period:
                warnings.append(
                    f"找胆图数据只到 {entry['coverage_end']}，落后于最新开奖 {latest.period}")
        result_charts[role] = entry
        extra = ""
        if role == ROLE_FX:
            extra = f" 两码组合={entry['pairs_rows']}行 矩阵={entry['matrix_rows']}行"
        if role == ROLE_ZD:
            extra = f" 覆盖至={entry['coverage_end']}"
        print(f"{role:<10}: {info['name']}{extra}")

    # 归档点位
    appended = False
    if points and not args.dry_run:
        archive = load_archive()
        dates = read_dates()
        old = archive.get(target_period)
        if old is not None:
            if old == points:
                points_status += "；档案已存在相同记录，未改动"
            elif args.force:
                points_status += "；已按 --force 覆盖"
                archive[target_period] = points
                dates[target_period] = guess_date.isoformat()
                appended = True
            else:
                print(f"✗ 目标期 {target_period:07d} 已有点位且与本次不同；"
                      f"如确认覆盖请加 --force", file=sys.stderr)
                return 1
        else:
            archive[target_period] = points
            dates[target_period] = guess_date.isoformat()
            appended = True
            points_status += "；已追加到档案"
        if appended:
            save_archive(archive, dates)

    # 回测只能覆盖「找胆图已覆盖」且「开奖已开出」的期
    zd_end = result_charts.get(ROLE_ZD, {}).get("coverage_end") or latest.period
    backtest_end = min(zd_end, latest.period)

    payload = {
        "latest_draw": {"period": latest.period, "date": latest.date.isoformat()},
        "target": {"period": target_period, "date": guess_date.isoformat()},
        "points": {"list": points, "status": points_status},
        "charts": result_charts,
        "backtest_end_period": backtest_end,
        "prev_published_dir": f"output/{latest.date.strftime('%Y%m%d')}",
        "prev_draw_numbers": list(latest.numbers),
        "warnings": warnings,
    }
    PREFLIGHT_JSON.parent.mkdir(parents=True, exist_ok=True)
    PREFLIGHT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    print()
    print(f"回测截止期    : {backtest_end}")
    print(f"昨日发布目录  : {payload['prev_published_dir']}")
    if warnings:
        print("\n警告：")
        for w in warnings:
            print("  ⚠ " + w)
    print(f"\n检查结果已写入 {PREFLIGHT_JSON}")

    if not result_charts.get(ROLE_DW) or not result_charts.get(ROLE_FX):
        return 1
    return 2 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())