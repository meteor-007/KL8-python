# -*- coding: utf-8 -*-
"""
点位+遗漏 · 逐期命中复盘台账
================================
- 每日推演落盘预测快照 predictions/{period}.json
- 开奖后结算写入 period_hit_ledger.jsonl（按期 upsert）
- 回测 PeriodRecord 可批量灌入近窗（seed / 完整回测后）
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

LEDGER_NAME = "period_hit_ledger.jsonl"
PRED_DIR_NAME = "predictions"
EXPECTED_TOP5 = 5 * 20 / 80  # 1.25


def _storage_root(proj_dir: str) -> str:
    return os.path.join(proj_dir, "storage", "point_omission")


def ledger_path(proj_dir: str) -> str:
    return os.path.join(_storage_root(proj_dir), LEDGER_NAME)


def predictions_dir(proj_dir: str) -> str:
    return os.path.join(_storage_root(proj_dir), PRED_DIR_NAME)


def _fmt_nums(nums: List[int]) -> str:
    return " ".join(f"{int(x):02d}" for x in nums)


def build_ledger_row(
    *,
    period: int,
    date_str: str,
    top5: List[int],
    actual: Set[int],
    defensive: Optional[List[int]] = None,
    points20: Optional[List[int]] = None,
    expanded: Optional[List[int]] = None,
    source: str = "daily_settle",
) -> Dict[str, Any]:
    top5 = [int(x) for x in (top5 or [])][:5]
    defensive = [int(x) for x in (defensive or [])]
    points20 = [int(x) for x in (points20 or [])]
    expanded = [int(x) for x in (expanded or [])]
    act = {int(x) for x in actual}

    hit_balls = sorted(set(top5) & act)
    def_hits = sorted(set(defensive) & act)
    pts_hits = sorted(set(points20) & act) if points20 else []
    exp_hits = sorted(set(expanded) & act) if expanded else []

    hits = len(hit_balls)
    return {
        "period": int(period),
        "date": date_str or "",
        "top5": top5,
        "top5_str": _fmt_nums(top5),
        "hit_balls": hit_balls,
        "hit_balls_str": _fmt_nums(hit_balls) if hit_balls else "—",
        "hits": hits,
        "expected": round(EXPECTED_TOP5, 4),
        "lift_vs_random": round(hits / EXPECTED_TOP5, 3) if EXPECTED_TOP5 else 0.0,
        "defensive": defensive,
        "defensive_str": _fmt_nums(defensive) if defensive else "",
        "defensive_hit_balls": def_hits,
        "defensive_hits": len(def_hits),
        "points20_hits": len(pts_hits) if points20 else None,
        "expanded_hits": len(exp_hits) if expanded else None,
        "source": source,
        "settled_at": datetime.now().isoformat(timespec="seconds"),
    }


def load_ledger(proj_dir: str) -> Dict[int, Dict[str, Any]]:
    path = ledger_path(proj_dir)
    by_period: Dict[int, Dict[str, Any]] = {}
    if not os.path.exists(path):
        return by_period
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    p = int(row.get("period") or 0)
                    if p:
                        by_period[p] = row
                except Exception:
                    continue
    except Exception:
        pass
    return by_period


def write_ledger(proj_dir: str, by_period: Dict[int, Dict[str, Any]]) -> None:
    root = _storage_root(proj_dir)
    os.makedirs(root, exist_ok=True)
    path = ledger_path(proj_dir)
    periods = sorted(by_period.keys())
    with open(path, "w", encoding="utf-8") as f:
        for p in periods:
            f.write(json.dumps(by_period[p], ensure_ascii=False) + "\n")


def upsert_rows(proj_dir: str, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    by_period = load_ledger(proj_dir)
    n = 0
    for row in rows:
        p = int(row.get("period") or 0)
        if not p:
            continue
        by_period[p] = row
        n += 1
    write_ledger(proj_dir, by_period)
    return n


def save_prediction_snapshot(
    proj_dir: str,
    *,
    period: int,
    date_str: str,
    top5: List[int],
    defensive: List[int],
    points20: List[int],
    expanded: List[int],
) -> str:
    d = predictions_dir(proj_dir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{int(period)}.json")
    payload = {
        "period": int(period),
        "date": date_str or "",
        "top5": [int(x) for x in top5][:5],
        "defensive": [int(x) for x in defensive],
        "points20": [int(x) for x in points20],
        "expanded": [int(x) for x in expanded],
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def settle_predictions_against_draws(
    proj_dir: str,
    draws_by_period: Dict[int, Any],
) -> List[Dict[str, Any]]:
    """
    扫描 predictions/*.json，对已开奖期结算写入台账。
    draws_by_period: period -> object with .numbers and optional .date
    """
    d = predictions_dir(proj_dir)
    if not os.path.isdir(d):
        return []
    settled: List[Dict[str, Any]] = []
    for name in os.listdir(d):
        if not name.endswith(".json"):
            continue
        try:
            period = int(name.replace(".json", ""))
        except ValueError:
            continue
        draw = draws_by_period.get(period)
        if draw is None:
            continue
        path = os.path.join(d, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                pred = json.load(f)
        except Exception:
            continue
        numbers = set(getattr(draw, "numbers", None) or draw.get("numbers") or [])
        date_str = ""
        raw_date = getattr(draw, "date", None)
        if raw_date is not None:
            date_str = raw_date.isoformat() if hasattr(raw_date, "isoformat") else str(raw_date)
        date_str = date_str or str(pred.get("date") or "")
        row = build_ledger_row(
            period=period,
            date_str=date_str,
            top5=list(pred.get("top5") or []),
            actual=numbers,
            defensive=list(pred.get("defensive") or []),
            points20=list(pred.get("points20") or []),
            expanded=list(pred.get("expanded") or []),
            source="daily_settle",
        )
        settled.append(row)
    if settled:
        upsert_rows(proj_dir, settled)
    return settled


def records_from_backtest(period_records: List[Any], source: str = "backtest_seed") -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for rec in period_records or []:
        top5 = list(getattr(rec, "top5", None) or [])
        hits = int(getattr(rec, "hits", 0) or 0)
        # PeriodRecord 未存 hit_balls；用 hits 占位，hit_balls 留空（seed 可再补）
        row = {
            "period": int(getattr(rec, "period")),
            "date": str(getattr(rec, "date_str", "") or ""),
            "top5": top5,
            "top5_str": _fmt_nums(top5),
            "hit_balls": [],
            "hit_balls_str": f"（命中 {hits} 码，种子未回溯球号）" if hits else "—",
            "hits": hits,
            "expected": round(EXPECTED_TOP5, 4),
            "lift_vs_random": round(hits / EXPECTED_TOP5, 3) if EXPECTED_TOP5 else 0.0,
            "defensive": [],
            "defensive_str": "",
            "defensive_hit_balls": [],
            "defensive_hits": int(getattr(rec, "defensive_hits", 0) or 0),
            "points20_hits": int(getattr(rec, "points20_hits", 0) or 0),
            "expanded_hits": int(getattr(rec, "expanded_hits", 0) or 0),
            "source": source,
            "settled_at": datetime.now().isoformat(timespec="seconds"),
        }
        rows.append(row)
    return rows


def merge_backtest_records(proj_dir: str, period_records: List[Any], *, keep_last: int = 60) -> int:
    """把回测近 keep_last 期写入台账；若台账已有同日 daily_settle 且含 hit_balls，则保留球号明细。"""
    if not period_records:
        return 0
    slice_recs = list(period_records)[-keep_last:]
    new_rows = records_from_backtest(slice_recs, source="backtest_seed")
    existing = load_ledger(proj_dir)
    for row in new_rows:
        p = row["period"]
        old = existing.get(p)
        if old and old.get("source") == "daily_settle" and old.get("hit_balls"):
            # 保留实盘结算的中奖球明细，仅补齐缺失的池命中字段
            for k in ("points20_hits", "expanded_hits", "defensive_hits"):
                if old.get(k) is None and row.get(k) is not None:
                    old[k] = row[k]
            existing[p] = old
        else:
            existing[p] = row
    write_ledger(proj_dir, existing)
    return len(new_rows)


def enrich_hit_balls_from_draws(proj_dir: str, draws_by_period: Dict[int, Any]) -> int:
    """用开奖号给台账补全 hit_balls（回测种子常只有 hits 计数）。"""
    by_period = load_ledger(proj_dir)
    patched = 0
    for p, row in list(by_period.items()):
        draw = draws_by_period.get(int(p))
        if not draw:
            continue
        top5 = list(row.get("top5") or [])
        if not top5:
            continue
        numbers = set(getattr(draw, "numbers", None) or (draw.get("numbers") if isinstance(draw, dict) else []) or [])
        hit_balls = sorted(set(int(x) for x in top5) & {int(x) for x in numbers})
        row["hit_balls"] = hit_balls
        row["hit_balls_str"] = _fmt_nums(hit_balls) if hit_balls else "—"
        row["hits"] = len(hit_balls)
        row["lift_vs_random"] = round(len(hit_balls) / EXPECTED_TOP5, 3) if EXPECTED_TOP5 else 0.0
        if not row.get("date"):
            raw_date = getattr(draw, "date", None)
            if raw_date is not None:
                row["date"] = raw_date.isoformat() if hasattr(raw_date, "isoformat") else str(raw_date)
        by_period[p] = row
        patched += 1
    if patched:
        write_ledger(proj_dir, by_period)
    return patched


def get_hit_ledger(
    proj_dir: str,
    n: int = 40,
) -> Dict[str, Any]:
    by_period = load_ledger(proj_dir)
    rows = [by_period[p] for p in sorted(by_period.keys(), reverse=True)]
    total = len(rows)
    rows = rows[: max(1, int(n))] if n else rows
    if rows:
        avg_hits = sum(float(r.get("hits") or 0) for r in rows) / len(rows)
    else:
        avg_hits = 0.0
    return {
        "status": "ok",
        "total": total,
        "returned": len(rows),
        "avg_hits": round(avg_hits, 4),
        "expected": round(EXPECTED_TOP5, 4),
        "avg_lift": round(avg_hits / EXPECTED_TOP5, 3) if EXPECTED_TOP5 else 0.0,
        "rows": rows,
    }


def seed_ledger_from_backtest(proj_dir: str, n: int = 40, verbose: bool = True) -> Dict[str, Any]:
    """轻量回测灌入近 n 期逐期台账（首次落地用）。"""
    from pathlib import Path
    from backend.modules._retired.point_omission.kl8.config import load_config
    from backend.modules._retired.point_omission.kl8 import source as source_mod
    from backend.modules._retired.point_omission.kl8 import replay

    cfg_path = Path(proj_dir) / "backend" / "modules" / "point_omission" / "config.yaml"
    if not cfg_path.exists():
        cfg_path = Path(__file__).resolve().parent / "config.yaml"
    cfg = load_config(cfg_path)
    try:
        from backend.utils.paths import data_path
        cfg.override_files(history=str(data_path("kl8_history_final.txt")), points=str(data_path("daily_points.txt")))
    except Exception:
        pass

    ds = source_mod.load_dataset(cfg)
    if not ds.pairable():
        return {"status": "error", "message": "点位与开奖无法配对，无法灌入台账"}
    bt = replay.run_backtest(cfg, ds, n=int(n))
    written = merge_backtest_records(proj_dir, bt.records, keep_last=int(n))

    draws = {d.period: d for d in ds.draws}
    patched = enrich_hit_balls_from_draws(proj_dir, draws)

    if verbose:
        print(f"[hit_ledger] seeded {written} periods, patched hit_balls={patched}")
    return {
        "status": "ok",
        "written": written,
        "patched": patched,
        "T": getattr(bt, "T", 0),
        "ledger_total": len(load_ledger(proj_dir)),
    }
