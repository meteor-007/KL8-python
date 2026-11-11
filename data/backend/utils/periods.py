# -*- coding: utf-8 -*-
"""
期号解析唯一入口 (Single Source of Truth for Period Numbers)
============================================================
背景 (2026-10-21 P2 缺陷整改)：
  全库曾有 **8 处** 各自写死"兜底期号"，形如
      target = int(history[0]['issue']) + 1 if history else 2026234
      latest = history[-1]["period"]        if history else 2026233
      base_period = ... else "2026240"
  问题有两层：
    1. 【编造期号】历史库为空/读取失败时，模块不报错，而是拿一个**平白编出来的期号**
       继续跑完整轮推演并落盘，产物上标着假期号。下游收割器、研报、看板都无从分辨，
       等于用假期号冒充真实推演 —— 属数据诚信红线问题。
    2. 【排序约定二义】`utils.history_loader.load_history()` 返回**降序**(最新在 [0])，
       而 `modules/unified_brain/feature_extractors.load_historical_draws()`
       显式 `sort()` 成**升序**(最新在 [-1])。两处都对，但"同一语义两套约定"使得
       `history[0]` 与 `history[-1]` 在不同文件里都表示"最新一期"。
       一旦有人把某个本地 loader 换成另一个，就会**静默错位一整期**（前视或滞后），
       而这种错误不会抛异常，只会让所有数字悄悄变脏。

本模块把"最新已开期 / 下一目标期"收敛成唯一入口：
  - 调用方不再自己挑 [0] 还是 [-1]，也不会再拿到编造期号；
  - 空库/脏库一律 raise，交由上层按"当期不可推演"如实降级，绝不静默产假数。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "PeriodError",
    "latest_period",
    "next_target_period",
    "target_period_or_none",
]


class PeriodError(RuntimeError):
    """历史开奖为空、或缺少可用期号时抛出。禁止用编造期号代替。"""


def _to_int_period(value: Any) -> Optional[int]:
    """把期号字段安全转成 int；转不动就返回 None（不猜、不补零、不默认）。"""
    if value is None:
        return None
    s = str(value).strip()
    if not s.isdigit():
        return None
    n = int(s)
    # 快乐8 期号为 7 位 YYYYNNN；4 位以下是明显脏数据，不接受
    return n if n >= 1000000 else None


def latest_period(history: Optional[Iterable[Dict[str, Any]]]) -> int:
    """返回**最新已开期号**。

    history 元素支持 `issue` / `period` 两种键名，且**不依赖传入顺序**：
    内部统一取最大值，因此升序 (feature_extractors) 与降序 (history_loader)
    两种约定都会得到同一个答案 —— 这正是收敛掉二义性的关键。

    Raises:
        PeriodError: 历史为空或全部无法解析出合法期号时。**不返回编造期号。**
    """
    if not history:
        raise PeriodError(
            "历史开奖数据为空，无法确定最新已开期号。"
            "请先执行数据同步 (backend.data_acquisition.fetch_kl8_history)，"
            "或按『当期不可推演』如实降级 —— 禁止使用编造期号继续推演。"
        )
    candidates: List[int] = []
    for row in history:
        if not isinstance(row, dict):
            continue
        p = _to_int_period(row.get("issue", row.get("period")))
        if p is not None:
            candidates.append(p)
    if not candidates:
        raise PeriodError("历史开奖中没有任何可解析的合法 7 位期号，拒绝编造期号。")
    return max(candidates)


def next_target_period(history: Optional[Iterable[Dict[str, Any]]]) -> int:
    """返回**下一目标期号** = 最新已开期 + 1。语义见 `latest_period`。"""
    return latest_period(history) + 1


def target_period_or_none(history: Optional[Iterable[Dict[str, Any]]]) -> Optional[int]:
    """非抛错版本：数据不可用时返回 None，供调用方显式走『缺数据降级』分支。

    用在"宁可少出一个产物，也不要假期号"的场景 (研报/看板/收割器)。
    """
    try:
        return next_target_period(history)
    except PeriodError:
        return None
