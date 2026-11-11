# -*- coding: utf-8 -*-
"""
一胆拖三盾 · 选2组合拳服务层 (Spear-Shield Portfolio Service)
============================================================
承接 Web 驾驶舱的三类读取:
  1. 当期票面 (攻矛/守盾/组合拳/风控) —— 引擎实测 0.33s, 按需即算 + 进程内按期号缓存;
  2. 样本外滚动复盘 —— 读 reviewer 每晚落盘的 storage/cache/spear_shield_review.json;
  3. 历史研报索引 —— 扫 outputs/reports/spear_shield_report_*.md。

数据诚信约束 (与全库口径一致):
  - 票面与 Markdown 战报、前瞻账收割同源 (同一个 engine.run_prediction)，不再造第二套算法;
  - 复盘 rows 只回账本真实存在的期, 缺期不补数。

@since 2026-10-22
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.utils.paths import get_cache_dir, get_outputs_dir, get_project_root
from backend.utils.history_loader import load_history
from backend.data_acquisition.daily_points_manager import load_daily_points
from backend.modules.tri_high.tri_high_engine import TriHighResonanceEngine
from backend.modules.spear_shield_portfolio.engine import SpearShieldPortfolioEngine

logger = logging.getLogger("k8quant.spear_shield.service")

REVIEW_CACHE_FILE = os.path.join(get_cache_dir(), "spear_shield_review.json")

# 进程内缓存: target_period -> payload (引擎 0.33s/期, 同一天多次开页不必重算)
_latest_cache: Dict[str, Dict[str, Any]] = {}


def _pair_to_dict(p) -> Dict[str, Any]:
    if p is None:
        return None
    return {
        "spear": p.spear,
        "shield": p.shield,
        "pair_str": p.pair_str,
        "span": p.span,
        "shield_omission": p.shield_omission,
        "shield_rebound_score": round(float(p.shield_rebound_score), 2),
        "is_spear_in_points": bool(p.is_spear_in_points),
        "is_shield_in_points": bool(p.is_shield_in_points),
        "rationale": p.rationale,
    }


def run_spear_shield_prediction(force: bool = False) -> Dict[str, Any]:
    """按需运行一胆拖三盾当期推演并返回结构化票面。"""
    history = load_history()
    if not history:
        raise ValueError("无法读取历史开奖数据")
    latest_period = int(history[0]["issue"])
    target_period = latest_period + 1

    if not force and str(target_period) in _latest_cache:
        return _latest_cache[str(target_period)]

    draws_asc = [d["numbers"] for d in reversed(history)]
    pts_entry = (load_daily_points() or {}).get(str(target_period)) or {}
    points = pts_entry.get("points", [])
    tri_records = {str(r.get("period")): r
                   for r in TriHighResonanceEngine().load_tri_high_records()}
    tri_data = tri_records.get(str(target_period))

    engine = SpearShieldPortfolioEngine()
    result = engine.run_prediction(
        all_draws_asc=draws_asc,
        target_period=target_period,
        daily_points=points,
        tri_high_data=tri_data,
        draw_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    payload = {
        "target_period": result.target_period,
        "anchor_period": result.anchor_period,
        "draw_date": result.draw_date,
        "primary_spear": result.primary_spear,
        "secondary_spear": result.secondary_spear,
        "shields": list(result.shields),
        "defense_line_4": list(result.defense_line_4),
        "pairs": [_pair_to_dict(p) for p in result.pairs],
        "backup_pair": _pair_to_dict(result.backup_pair),
        "kl_divergence": round(float(result.kl_divergence), 2),
        "risk_level": result.risk_level,
        "points_used": bool(points),
        "tri_high_used": bool(tri_data),
        "report_markdown": result.report_markdown,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _latest_cache[str(target_period)] = payload
    return payload


def get_spear_shield_review(n: Optional[int] = None) -> Dict[str, Any]:
    """读取 reviewer 落盘的样本外复盘 (默认用账本现成期数, 不现算重回测)。

    n 大于账本已有行数时只回已有行数并如实说明, 避免页面加载触发 10s+ 全量回测。
    需要更多期请点驾驶舱「重跑30期回测」按钮 (显式操作)。
    """
    data: Dict[str, Any] = {}
    if os.path.exists(REVIEW_CACHE_FILE):
        try:
            with open(REVIEW_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning("读取 spear_shield 复盘缓存失败: %s", e)

    rows = data.get("rows") or []
    stats = data.get("stats") or {}
    available = len(rows)

    if n is not None and n < available:
        rows = rows[-n:]

    return {
        "cached": bool(rows),
        "rows": rows,
        "stats": stats,
        "available_periods": available,
        "requested_periods": n,
        "audit_timestamp": data.get("audit_timestamp"),
        "no_lookahead_verified": bool(data.get("no_lookahead_verified", False)),
        "note": ("复盘数据来自每晚流水线落盘的 Walk-Forward 账本 (严格无未来信息); "
                 "如需更多期数请显式点击「重跑回测」。"),
    }


def rerun_spear_shield_review(n_periods: int = 30) -> Dict[str, Any]:
    """显式重跑样本外回测 (慢操作, 仅供按钮触发)。"""
    from backend.modules.spear_shield_portfolio.reviewer import SpearShieldPortfolioReviewer
    reviewer = SpearShieldPortfolioReviewer()
    reviewer.run_walk_forward_review(n_periods=n_periods, verbose=False)
    return get_spear_shield_review(n=n_periods)


def get_spear_shield_history() -> List[Dict[str, Any]]:
    """历史研报 md 文件索引 (期号降序)。"""
    reports_dir = os.path.join(get_outputs_dir(), "reports")
    out: List[Dict[str, Any]] = []
    for path in glob.glob(os.path.join(reports_dir, "spear_shield_report_*.md")):
        fname = os.path.basename(path)
        m = re.search(r"spear_shield_report_(\d+)\.md", fname)
        if not m:
            continue
        try:
            st = os.stat(path)
            out.append({
                "filename": fname,
                "period": m.group(1),
                "size_bytes": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
        except Exception:
            continue
    out.sort(key=lambda x: int(x["period"]), reverse=True)
    return out[:60]
