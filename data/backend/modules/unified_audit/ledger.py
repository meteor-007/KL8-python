# -*- coding: utf-8 -*-
"""统一对账 JSONL 账本。"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from backend.utils.paths import get_project_root, get_reviews_dir

LEDGER_NAME = "unified_daily_audit.jsonl"
LATEST_NAME = "unified_daily_audit_latest.json"


def ledger_path(proj_dir: Optional[str] = None) -> str:
    root = proj_dir or get_project_root()
    return os.path.join(root, "storage", "reviews", LEDGER_NAME)


def latest_path(proj_dir: Optional[str] = None) -> str:
    root = proj_dir or get_project_root()
    return os.path.join(root, "storage", "reviews", LATEST_NAME)


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def load_all(proj_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    path = ledger_path(proj_dir)
    if not os.path.exists(path):
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def load_by_period(target_period: int, proj_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    target = int(target_period)
    hit = None
    for row in load_all(proj_dir):
        if int(row.get("target_period") or 0) == target:
            hit = row
    return hit


def upsert_row(row: Dict[str, Any], proj_dir: Optional[str] = None) -> Dict[str, Any]:
    """按 target_period 覆盖写回整本账（小文件，可全量重写）。"""
    path = ledger_path(proj_dir)
    _ensure_parent(path)
    target = int(row["target_period"])
    rows = [r for r in load_all(proj_dir) if int(r.get("target_period") or 0) != target]
    rows.append(row)
    rows.sort(key=lambda r: int(r.get("target_period") or 0))
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    lp = latest_path(proj_dir)
    with open(lp, "w", encoding="utf-8") as f:
        json.dump(row, f, ensure_ascii=False, indent=2)
    return row


def load_latest(proj_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    path = latest_path(proj_dir)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    rows = load_all(proj_dir)
    return rows[-1] if rows else None


def recent_settled(limit: int = 30, proj_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = [r for r in load_all(proj_dir) if r.get("settled")]
    rows.sort(key=lambda r: int(r.get("target_period") or 0))
    return rows[-limit:]
