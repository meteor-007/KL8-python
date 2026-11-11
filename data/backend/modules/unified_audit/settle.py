# -*- coding: utf-8 -*-
"""开奖后结算统一对账行。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.modules.unified_audit.ledger import load_by_period, upsert_row
from backend.modules.unified_audit.schema import settle_hits
from backend.utils.history_loader import load_history
from backend.utils.paths import get_project_root


def settle_period(
    period: Optional[int] = None,
    proj_dir: Optional[str] = None,
    actual_numbers: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """结算指定目标期；默认结算「最新已开期」对应的预测行（target=latest）。"""
    root = proj_dir or get_project_root()
    history = load_history()
    if not history:
        return {"status": "error", "message": "无开奖历史"}

    latest = history[0]
    latest_period = int(latest.get("issue") or latest.get("period") or 0)
    settle_target = int(period) if period is not None else latest_period

    row = load_by_period(settle_target, root)
    if not row:
        return {
            "status": "skip",
            "message": f"无目标期 {settle_target} 的预测快照，请先 snapshot",
            "target_period": settle_target,
        }

    if actual_numbers is None:
        # 行的 target_period 对应那一期的实开
        draw_map = {int(h.get("issue") or h.get("period") or 0): h for h in history}
        draw = draw_map.get(settle_target)
        if not draw:
            return {
                "status": "skip",
                "message": f"历史中尚无 {settle_target} 开奖，无法结算",
                "target_period": settle_target,
            }
        actual_numbers = list(draw.get("numbers") or [])

    settled = settle_hits(row, actual_numbers)
    upsert_row(settled, root)
    return {"status": "ok", "target_period": settle_target, "row": settled}
