# -*- coding: utf-8 -*-
"""
thirty_ball_engine.py — 快乐8 30 码黄金大底实战生产引擎
========================================================

【架构原则 (2026-10-12 数据诚信整改)】:
1. 产线 30 码成员 = 被回测的那个策略函数逐字调用 (从 thirty_ball_benchmark.STRATEGY_REGISTRY
   取函数对象, 单一事实源), 杜绝"研报宣称冠军算法、实际跑的是另一套手调打分器"的张冠李戴;
2. 全部历史窗口按 `period < target_period` 截断, 对任意目标期重放均无未来函数穿透;
3. lanes_vote (19 路模块票池) 与 daily_points (当日点位) 只影响 30 码内部的展示排序
   (哪个号进 Top 梯队), 绝不改变成员集合 —— 历史上无逐期票池数据, 任何"票数加权的成员"
   都是无法回测的黑箱;
4. 证据数字动态读取 benchmark JSON 产物, 缺产物时如实标注, 绝不写死回测成绩;
5. 按期落盘 storage/outputs/thirty_ball/thirty_ball_{period}.json, 供复盘账本对账。

@author Antigravity Quant Team & Old-School Quant Trader
@since 2026-10-12
"""

from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.dirname(_CURR_DIR)
_BACKEND_DIR = os.path.dirname(_MODULES_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils.paths import get_outputs_dir
from backend.modules.spear_shield_portfolio.thirty_ball_benchmark import (
    STRATEGY_REGISTRY,
    DEFAULT_STRATEGY_ID,
    load_history_records,
)

TOTAL_BALLS = 80
PORTFOLIO_SIZE = 30
ZONE_NAMES = ["一区[01-10]", "二区[11-20]", "三区[21-30]", "四区[31-40]",
              "五区[41-50]", "六区[51-60]", "七区[61-70]", "八区[71-80]"]


@dataclass
class ThirtyBallResult:
    target_period: int
    picks: List[int]
    top10_core: List[int]
    mid10_assault: List[int]
    tail10_hedge: List[int]
    zone_counts: Dict[str, int]
    odd_even: Tuple[int, int]  # (奇数, 偶数)
    source_stats: Dict[str, Any]
    quick_copy_text: str


class ThirtyBallEngine:
    """30 码黄金大底实战生产引擎 (成员=被回测算法, 梯队仅展示排序)。"""

    def __init__(self, data_root: Optional[str] = None):
        self.data_root = data_root or _PROJ_DIR
        # 测试可注入假的 benchmark 产物路径
        self._benchmark_artifact_path: Optional[str] = None

    # ── benchmark 证据产物 ──
    def _benchmark_artifact(self) -> Optional[Dict[str, Any]]:
        path = self._benchmark_artifact_path or os.path.join(
            get_outputs_dir(), "reports", "thirty_ball_benchmark_report.json"
        )
        try:
            with open(path, "r", encoding="utf-8") as f:
                art = json.load(f)
        except Exception:
            return None
        return art if isinstance(art, dict) and art.get("recommended") else None

    def _resolve_strategy(self, strategy_id: Optional[str]) -> Tuple[str, str, Any, str]:
        """返回 (strategy_id, 显示名, 函数, 来源)。显式指定 > 产物 recommended > 默认。"""
        if strategy_id:
            if strategy_id not in STRATEGY_REGISTRY:
                raise ValueError(f"未知策略 id: {strategy_id}")
            name, fn = STRATEGY_REGISTRY[strategy_id]
            return strategy_id, name, fn, "explicit"
        art = self._benchmark_artifact()
        if art and art["recommended"] in STRATEGY_REGISTRY:
            sid = art["recommended"]
            name, fn = STRATEGY_REGISTRY[sid]
            return sid, name, fn, "artifact"
        name, fn = STRATEGY_REGISTRY[DEFAULT_STRATEGY_ID]
        return DEFAULT_STRATEGY_ID, name, fn, "default_fallback"

    def _evidence_note(self, art: Optional[Dict[str, Any]], sid: str, sname: str) -> str:
        """按回测产物生成中性证据说明; 无产物时如实声明, 绝不引用写死成绩。"""
        if art:
            rec = next((s for s in art.get("strategies", []) if s.get("id") == sid), None)
            if rec:
                base = art.get("baseline", {})
                sig = rec.get("significant")
                verdict = (
                    "通过 BH-FDR 0.05 门槛（仍需样本外持续跟踪）"
                    if sig
                    else "未通过 BH-FDR 0.05 门槛，与随机基线差异不能排除随机波动，仅作覆盖型参考、不作加注依据"
                )
                return (
                    f"回测基准期{art.get('base_period')}，n={rec.get('n_periods')}期OOF，"
                    f"≥11码 {rec.get('ge11_count')}/{rec.get('n_periods')}（{rec.get('ge11_rate')}%，"
                    f"随机基线{base.get('p_ge11', 0) * 100:.1f}%），"
                    f"Wilson95[{rec.get('wilson_lo', 0) * 100:.1f}%, {rec.get('wilson_hi', 0) * 100:.1f}%]，"
                    f"BH-q={rec.get('bh_q')} —— {verdict}。"
                )
            return (
                f"回测产物缺少「{sname}」的明细数据，回测证据不可用；"
                f"随机期望命中≈7.50码/期，本大底为覆盖型工具，不构成概率优势证据。"
            )
        name, _fn = STRATEGY_REGISTRY[DEFAULT_STRATEGY_ID]
        return (
            f"无有效回测产物（benchmark 未运行或产物损坏），成员默认采用「{name}」；"
            f"随机期望命中≈7.50码/期，本大底为覆盖型工具，不构成概率优势证据。"
        )

    def generate(
        self,
        target_period: int,
        lanes_vote: Optional[Dict[int, int]] = None,
        daily_points: Optional[List[int]] = None,
        history: Optional[List[Any]] = None,
        strategy_id: Optional[str] = None,
    ) -> ThirtyBallResult:
        """
        生成指定目标期的 30 码大底。
        :param target_period: 目标推演期号 (期号=被预测期)
        :param lanes_vote: 各模块投票统计 (号码 -> 票数)，仅影响展示排序
        :param daily_points: 当日录入的 20 空间点位，仅影响展示排序
        :param history: 注入的历史开奖列表 (PeriodRecord)，缺省从数据文件加载；测试用
        :param strategy_id: 显式指定成员算法 id (跳过产物推荐)，测试/审计用
        """
        if history is None:
            history = load_history_records(limit=250)

        # 未来函数防线: 只允许看到目标期之前的数据
        pre = [r for r in history if r.period < target_period]
        if not pre:
            raise ValueError(f"目标期 {target_period} 之前无可用历史开奖记录")

        sid, sname, strat_fn, strategy_source = self._resolve_strategy(strategy_id)
        art = self._benchmark_artifact()

        # 成员 = 被回测的同一个函数对象, 逐字调用
        picks: List[int] = sorted(strat_fn(pre, len(pre)))

        # ── 梯队: 仅展示排序 (票数降序 > 在点位中 > 号码升序), 不改成员 ──
        def _disp_key(b: int) -> Tuple[int, int, int]:
            v = lanes_vote.get(b, 0) if lanes_vote else 0
            in_pts = 1 if (daily_points and b in daily_points) else 0
            return (-v, -in_pts, b)

        display_order = sorted(picks, key=_disp_key)
        top10_core = sorted(display_order[:10])
        mid10_assault = sorted(display_order[10:20])
        tail10_hedge = sorted(display_order[20:30])

        z_stats: Dict[str, int] = {
            ZONE_NAMES[z]: sum(1 for b in picks if (b - 1) // 10 == z)
            for z in range(8)
        }
        odd_c = sum(1 for b in picks if b % 2 == 1)
        even_c = PORTFOLIO_SIZE - odd_c

        base_period = pre[-1].period
        evidence_note = self._evidence_note(art, sid, sname)
        source_stats = {
            "has_lanes_vote": bool(lanes_vote),
            "has_daily_points": bool(daily_points),
            "total_voted_count": len(lanes_vote) if lanes_vote else 0,
            "strategy_id": sid,
            "strategy_name": sname,
            "strategy_source": strategy_source,
            "base_period": base_period,
            "benchmark_base_period": art.get("base_period") if art else None,
        }

        copy_text = self._render_copy_text(
            target_period, sname, top10_core, mid10_assault, tail10_hedge,
            picks, z_stats, odd_c, even_c, evidence_note,
        )

        result = ThirtyBallResult(
            target_period=target_period,
            picks=picks,
            top10_core=top10_core,
            mid10_assault=mid10_assault,
            tail10_hedge=tail10_hedge,
            zone_counts=z_stats,
            odd_even=(odd_c, even_c),
            source_stats=source_stats,
            quick_copy_text=copy_text,
        )
        self._persist(result, evidence_note)
        return result

    def _render_copy_text(
        self, target_period: int, sname: str,
        top10: List[int], mid10: List[int], tail10: List[int],
        picks: List[int], z_stats: Dict[str, int],
        odd_c: int, even_c: int, evidence_note: str,
    ) -> str:
        art = self._benchmark_artifact()
        p11 = None
        if art and isinstance(art.get("baseline"), dict):
            p11 = art["baseline"].get("p_ge11")
        if p11 is None:
            from backend.modules.kl8_lab.numerics import hypergeom_sf
            p11 = hypergeom_sf(11, PORTFOLIO_SIZE, TOTAL_BALLS, 20)

        fmt = lambda nums: " ".join(f"{n:02d}" for n in nums)
        return (
            f"🎯【快乐8 第 {target_period} 期 30码黄金实战大底 (成员算法: {sname})】\n"
            f"👑 核心梯队 (Top 10, 展示排序) : {fmt(top10)}\n"
            f"⚡ 中坚梯队 (Mid 10, 展示排序) : {fmt(mid10)}\n"
            f"🛡️ 尾部梯队 (Tail 10, 展示排序): {fmt(tail10)}\n"
            f"──────────────────────────────────────────────────────\n"
            f"💎 30码大底全集 (升序排)  : {fmt(picks)}\n"
            f"📊 8区分布: {' | '.join(f'{k[:2]}:{v}码' for k, v in z_stats.items())}\n"
            f"⚖️ 奇偶比: {odd_c}:{even_c}（理论期望 15:15）｜ 期望命中 7.50 ｜ 随机基线 ≥11码 {p11 * 100:.1f}%\n"
            f"ℹ️ 梯队排序仅展示（票数/点位），大底成员由「{sname}」决定；{evidence_note}"
        )

    def _persist(self, result: ThirtyBallResult, evidence_note: str) -> None:
        """按期落盘, 供逐模块复盘账本对账 (仿 follow_rank 产物模式)。"""
        payload = {
            "module_code": "thirty_ball",
            "target_period": result.target_period,
            "base_period": result.source_stats.get("base_period"),
            "strategy_id": result.source_stats.get("strategy_id"),
            "strategy_name": result.source_stats.get("strategy_name"),
            "strategy_source": result.source_stats.get("strategy_source"),
            "picks": result.picks,
            "tiers": {
                "top10_core": result.top10_core,
                "mid10_assault": result.mid10_assault,
                "tail10_hedge": result.tail10_hedge,
            },
            "zone_counts": result.zone_counts,
            "odd_even": {"odd": result.odd_even[0], "even": result.odd_even[1]},
            "source_stats": result.source_stats,
            "evidence_note": evidence_note,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        out_dir = os.path.join(get_outputs_dir(), "thirty_ball")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"thirty_ball_{result.target_period}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


def generate_thirty_ball_portfolio(
    target_period: int,
    lanes_vote: Optional[Dict[int, int]] = None,
    daily_points: Optional[List[int]] = None,
    history: Optional[List[Any]] = None,
    strategy_id: Optional[str] = None,
) -> ThirtyBallResult:
    """快捷调用入口函数。"""
    engine = ThirtyBallEngine()
    return engine.generate(target_period, lanes_vote, daily_points, history, strategy_id)


if __name__ == "__main__":
    _hist = load_history_records(limit=250)
    _target = _hist[-1].period + 1
    _res = generate_thirty_ball_portfolio(_target)
    print(_res.quick_copy_text)
