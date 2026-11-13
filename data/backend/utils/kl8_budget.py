# -*- coding: utf-8 -*-
"""快乐8 预算与方差引擎

回答三个问题：
  1. 我这个买法，长期期望亏多少？
  2. 命中 N 个的概率有多大？
  3. 连买多少期、买多少注，波动有多大？

**奖金表不在本模块内置**，来自 backend/config/kl8_payout.json（使用者按所购渠道
官方规则填写）。未配置时本模块拒绝计算 —— 拿一个"约 58% 返奖率"去推具体金额，
就是伪造数据，也正是这个项目一路在防的事。

概率部分（命中分布）来自 kl8_probability，纯组合数学，与奖金无关。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.utils import kl8_probability as prob

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAYOUT_FILE = os.path.join(_PROJ_DIR, "backend", "config", "kl8_payout.json")


def load_payout_table(path: Optional[str] = None) -> Dict[str, Any]:
    """读取奖金表配置；文件不存在或解析失败时返回未配置状态。"""
    target = path or PAYOUT_FILE
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("奖金表根节点必须是对象")
        return data
    except Exception as e:
        return {"configured": False, "plays": {}, "_load_error": f"{type(e).__name__}: {e}"}


def is_configured(table: Optional[Dict[str, Any]] = None) -> bool:
    """奖金表是否已由使用者填写可用。"""
    t = table if table is not None else load_payout_table()
    if not t.get("configured"):
        return False
    plays = t.get("plays") or {}
    if not isinstance(plays, dict) or not plays:
        return False
    for name, spec in plays.items():
        if not isinstance(spec, dict):
            return False
        if not isinstance(spec.get("prizes"), dict) or not spec["prizes"]:
            return False
        if not isinstance(spec.get("stake"), (int, float)) or spec["stake"] <= 0:
            return False
    return True


def play_size(play: str) -> int:
    """从玩法名解析选号个数，如 '选5' -> 5。"""
    m = re.search(r"(\d+)", str(play))
    if not m:
        raise ValueError(f"无法从玩法名解析选号个数: {play!r}")
    return int(m.group(1))


def _normalized_prizes(spec: Dict[str, Any]) -> Dict[int, float]:
    """把 {'5': 1000} 规范成 {5: 1000.0}，并校验取值范围。"""
    out: Dict[int, float] = {}
    for key, amount in (spec.get("prizes") or {}).items():
        try:
            hits = int(str(key).strip())
            value = float(amount)
        except (TypeError, ValueError):
            continue
        if value < 0:
            raise ValueError(f"奖金不能为负: {key} -> {amount}")
        out[hits] = value
    return out


def play_metrics(play: str, tickets: int = 1, table: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """单个玩法的期望、方差与中奖概率。

    Returns 未配置时:
        {'status': 'not_configured', 'message': ...}
    已配置时:
        {'status': 'ok', 'play', 'k', 'tickets', 'stake', 'total_cost',
         'expected_payout', 'expected_net', 'return_rate', 'prob_any_prize',
         'payout_std'}   —— payout_std 为 tickets 注合计的标准差
    """
    t = table if table is not None else load_payout_table()
    if not is_configured(t):
        return {
            "status": "not_configured",
            "message": "奖金表未配置 —— 无法计算期望回报。请在 backend/config/kl8_payout.json 填写并置 configured=true。",
        }

    play = str(play).strip()
    plays = t["plays"]
    if play not in plays:
        return {"status": "unknown_play",
                "message": f"奖金表里没有玩法「{play}」，已配置的有：{', '.join(plays)}"}
    if tickets < 1:
        raise ValueError("tickets 必须 >= 1")

    spec = plays[play]
    k = play_size(play)
    if k > prob.N_DRAWN:
        raise ValueError(f"玩法「{play}」选号数超过每期开出个数 {prob.N_DRAWN}，全中不可能")

    stake = float(spec["stake"])
    prizes = _normalized_prizes(spec)
    pmf = prob.hit_distribution(k)

    e_payout = sum(pmf[h] * prizes.get(h, 0.0) for h in range(k + 1))
    e_payout_sq = sum(pmf[h] * (prizes.get(h, 0.0) ** 2) for h in range(k + 1))
    var = max(0.0, e_payout_sq - e_payout ** 2)
    p_any = sum(pmf[h] for h in prizes if prizes.get(h, 0.0) > 0)
    total_cost = stake * tickets

    return {
        "status": "ok",
        "play": play,
        "k": k,
        "tickets": tickets,
        "stake": stake,
        "total_cost": total_cost,
        "expected_payout": e_payout * tickets,
        "expected_net": e_payout * tickets - total_cost,
        "return_rate": (e_payout * tickets) / total_cost if total_cost else 0.0,
        "prob_any_prize": 1 - (1 - p_any) ** tickets,
        "payout_std": (var ** 0.5) * (tickets ** 0.5),
        "prob_total_loss": (1 - p_any) ** tickets,
    }


def budget_report(rows: List[Tuple[str, int]], table: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """多玩法预算汇总。

    Args:
        rows: [(玩法名, 注数), ...]，例如 [('选5', 3), ('选10', 1)]

    Returns:
        {'status', 'items': [...], 'total_cost', 'expected_payout', 'expected_net',
         'return_rate', 'payout_std'}
    """
    t = table if table is not None else load_payout_table()
    if not is_configured(t):
        return {
            "status": "not_configured",
            "message": "奖金表未配置 —— 无法计算期望回报。请在 backend/config/kl8_payout.json 填写并置 configured=true。",
            "items": [],
        }

    items, skipped = [], []
    for play, tickets in rows:
        m = play_metrics(play, tickets, t)
        (items if m.get("status") == "ok" else skipped).append(m)

    total_cost = sum(m["total_cost"] for m in items)
    total_payout = sum(m["expected_payout"] for m in items)
    # 各玩法相互独立，方差可直接相加
    total_var = sum(m["payout_std"] ** 2 for m in items)
    return {
        "status": "ok" if items else "no_valid_rows",
        "items": items,
        "skipped": skipped,
        "total_cost": total_cost,
        "expected_payout": total_payout,
        "expected_net": total_payout - total_cost,
        "return_rate": (total_payout / total_cost) if total_cost else 0.0,
        "payout_std": total_var ** 0.5,
    }