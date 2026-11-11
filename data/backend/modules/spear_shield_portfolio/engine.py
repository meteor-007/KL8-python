# -*- coding: utf-8 -*-
"""
一胆拖三盾 · 选2组合拳引擎 (Spear-Shield Portfolio Engine)
============================================================

【业务背景与量化逻辑】:
单挑单注选2的理论随机命中率仅 6.01%。本引擎将 16 窗中热「攻矛金胆」
与 3 枚处于 6~14 期黄金回补甜区的「防守盾牌」配对，形成 3 注选2小复式组合拳：
  1. 矛盾跨度严格锁定在 [10, 40] 黄金对冲区间；
  2. 严格排除同尾号与相邻连号，实现空间几何分散；
  3. 历史水位不再写死在文档里 —— 研报改用 ledger_stat_label() 现读前瞻账实算。

@author Antigravity Quant Team & Old-School Quant Trader
@since 2026-09-21
"""

from __future__ import annotations

import os
import sys
import math
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from typing import Any, Dict, List, Optional, Set, Tuple

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.dirname(_CURR_DIR)
_BACKEND_DIR = os.path.dirname(_MODULES_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.modules.sixteen.sixteen_engine import SixteenPeriodEngine, WINDOW_SIZE
from backend.utils.paths import get_outputs_dir
from backend.utils.ledger_stats import ledger_stat_label

TOTAL_BALL_COUNT: int = 80
BASE_SINGLE_PROB: float = 0.25
BASE_PAIR_PROB: float = 0.0601

SWEET_OMISSION_MIN: int = 6
SWEET_OMISSION_MAX: int = 14
MIN_STRADDLE_SPAN: int = 10
MAX_STRADDLE_SPAN: int = 40

LEDGER_FILE = os.path.join(_PROJ_DIR, "storage", "cache", "paper_trading_modules.jsonl")


@dataclass
class PortfolioPair:
    """单个选2组合明细。"""
    spear: int
    shield: int
    pair_str: str
    span: int
    shield_omission: int
    shield_rebound_score: float
    is_spear_in_points: bool = False
    is_shield_in_points: bool = False
    rationale: str = ""


@dataclass
class PortfolioPredictionResult:
    """一胆拖三盾组合拳推演完整视图。"""
    target_period: int
    anchor_period: int
    draw_date: str
    primary_spear: int
    secondary_spear: int
    shields: List[int]
    pairs: List[PortfolioPair]
    backup_pair: Optional[PortfolioPair]
    kl_divergence: float
    risk_level: str
    defense_line_4: List[int]
    report_markdown: str


class SpearShieldPortfolioEngine:
    """一胆拖三盾组合拳量化引擎。"""

    def __init__(self, proj_dir: Optional[str] = None) -> None:
        self.proj_dir = proj_dir or _PROJ_DIR

    def compute_omissions(self, draws_asc: List[List[int]]) -> Dict[int, int]:
        """计算全盘 80 球截止到上一期的当前遗漏值。"""
        omissions: Dict[int, int] = {}
        for ball in range(1, TOTAL_BALL_COUNT + 1):
            om = 0
            for d in reversed(draws_asc):
                if ball in d:
                    break
                om += 1
            omissions[ball] = om
        return omissions

    def compute_rebound_scores(
        self,
        draws_asc: List[List[int]],
        omissions: Dict[int, int]
    ) -> Dict[int, float]:
        """计算马尔可夫转移跟随概率与高斯遗漏回补动能。"""
        scores: Dict[int, float] = {b: 0.0 for b in range(1, TOTAL_BALL_COUNT + 1)}
        if not draws_asc:
            return scores

        latest_draw = set(draws_asc[-1])
        eval_slice = draws_asc[-100:] if len(draws_asc) >= 100 else draws_asc
        trans_counter: Dict[int, Counter] = defaultdict(Counter)

        for idx in range(len(eval_slice) - 1):
            for u in eval_slice[idx]:
                for v in eval_slice[idx + 1]:
                    trans_counter[u][v] += 1

        for u in latest_draw:
            total_trans = sum(trans_counter[u].values()) or 1
            for v, cnt in trans_counter[u].items():
                prob = cnt / total_trans
                scores[v] += prob * 10.0

        for b, om in omissions.items():
            if SWEET_OMISSION_MIN <= om <= SWEET_OMISSION_MAX:
                gauss = math.exp(-0.5 * ((om - 10.0) / 3.0) ** 2)
                scores[b] += 5.0 * gauss
            elif om > 15:
                scores[b] *= 0.65

        return scores

    def compute_kl_divergence(self, draws_asc: List[List[int]]) -> float:
        """计算大盘分布 KL 散度，监控结构异动。"""
        if len(draws_asc) < 11:
            return 0.8
        recent_10 = draws_asc[-11:-1]
        latest_draw = draws_asc[-1]

        def _get_zone_dist(draw_list: List[List[int]]) -> List[float]:
            zone_counts = [0.0] * 8
            total_balls = 0
            for d in draw_list:
                for b in d:
                    z_idx = min(7, (b - 1) // 10)
                    zone_counts[z_idx] += 1.0
                    total_balls += 1
            total_balls = total_balls or 1.0
            return [cnt / total_balls for cnt in zone_counts]

        prior = _get_zone_dist(recent_10)
        curr = _get_zone_dist([latest_draw])
        eps = 1e-4
        d_kl = 0.0
        for p, q in zip(curr, prior):
            p_s = max(p, eps)
            q_s = max(q, eps)
            d_kl += p_s * math.log(p_s / q_s)
        return max(0.5, round(d_kl * 15.0, 2))

    def run_prediction(
        self,
        all_draws_asc: List[List[int]],
        target_period: int,
        daily_points: Optional[List[int]] = None,
        tri_high_data: Optional[Dict[str, List[int]]] = None,
        draw_date: str = ""
    ) -> PortfolioPredictionResult:
        """
        执行一胆拖三盾组合拳推演。
        """
        if not all_draws_asc:
            raise ValueError("开奖历史数据不能为空！")

        anchor_period = target_period - 1
        omissions = self.compute_omissions(all_draws_asc)
        rebound_scores = self.compute_rebound_scores(all_draws_asc, omissions)
        kl_div = self.compute_kl_divergence(all_draws_asc)

        # 1. 运行 16 期引擎提取中热攻矛金胆
        sixteen_draws = []
        for idx, d in enumerate(all_draws_asc):
            sim_period = anchor_period - (len(all_draws_asc) - 1 - idx)
            sixteen_draws.append({
                "period": sim_period,
                "date": draw_date,
                "numbers": sorted(d),
                "nums": sorted(d),
                "sorted_nums": sorted(d)
            })

        sixteen_engine = SixteenPeriodEngine(sixteen_draws)
        sixteen_res = sixteen_engine.analyze_at_index(len(sixteen_draws) - 1)

        primary_spear = sixteen_res["gold_dan"]
        secondary_spear = sixteen_res["silver_dan"]

        points_set: Set[int] = set(daily_points or [])

        # 2. 从黄金遗漏甜区 (6~14期) 精选 3 枚防守盾牌
        sweet_candidates = [
            b for b, om in omissions.items()
            if SWEET_OMISSION_MIN <= om <= SWEET_OMISSION_MAX and b != primary_spear
        ]
        sweet_candidates.sort(key=lambda b: rebound_scores[b], reverse=True)

        selected_shields: List[int] = []
        for sh in sweet_candidates:
            span = abs(primary_spear - sh)
            if not (MIN_STRADDLE_SPAN <= span <= MAX_STRADDLE_SPAN):
                continue
            if primary_spear % 10 == sh % 10:
                continue
            selected_shields.append(sh)
            if len(selected_shields) == 3:
                break

        # 兜底补充不足 3 盾的情况
        if len(selected_shields) < 3:
            cold_sorted = sorted(range(1, TOTAL_BALL_COUNT + 1), key=lambda b: omissions[b], reverse=True)
            for b in cold_sorted:
                if b != primary_spear and b not in selected_shields:
                    span = abs(primary_spear - b)
                    if MIN_STRADDLE_SPAN <= span <= MAX_STRADDLE_SPAN and (primary_spear % 10 != b % 10):
                        selected_shields.append(b)
                        if len(selected_shields) == 3:
                            break

        # 3. 构造 3 组主要选2组合拳 (Pair 1, Pair 2, Pair 3)
        pairs: List[PortfolioPair] = []
        for sh in selected_shields:
            b1, b2 = min(primary_spear, sh), max(primary_spear, sh)
            span = abs(primary_spear - sh)
            pair_str = f"{b1:02d}-{b2:02d}"
            is_spear_pt = primary_spear in points_set
            is_sh_pt = sh in points_set
            rationale = (
                f"攻矛{primary_spear:02d}(16窗中热金胆) × "
                f"守盾{sh:02d}(遗漏{omissions[sh]}期/反弹分{rebound_scores[sh]:.1f}) "
                f"跨度{span}对冲 (非同尾分散)"
            )
            pairs.append(
                PortfolioPair(
                    spear=primary_spear,
                    shield=sh,
                    pair_str=pair_str,
                    span=span,
                    shield_omission=omissions[sh],
                    shield_rebound_score=round(rebound_scores[sh], 2),
                    is_spear_in_points=is_spear_pt,
                    is_shield_in_points=is_sh_pt,
                    rationale=rationale
                )
            )

        # 4. 次席银矛备用选2 (Backup Pair)
        backup_pair: Optional[PortfolioPair] = None
        for sh in selected_shields:
            if sh != secondary_spear:
                span = abs(secondary_spear - sh)
                if MIN_STRADDLE_SPAN <= span <= MAX_STRADDLE_SPAN and (secondary_spear % 10 != sh % 10):
                    b1, b2 = min(secondary_spear, sh), max(secondary_spear, sh)
                    backup_pair = PortfolioPair(
                        spear=secondary_spear,
                        shield=sh,
                        pair_str=f"{b1:02d}-{b2:02d}",
                        span=span,
                        shield_omission=omissions[sh],
                        shield_rebound_score=round(rebound_scores[sh], 2),
                        is_spear_in_points=secondary_spear in points_set,
                        is_shield_in_points=sh in points_set,
                        rationale=f"次席银矛{secondary_spear:02d} × 守盾{sh:02d} 备选对冲"
                    )
                    break

        defense_line_4 = [primary_spear] + selected_shields

        risk_level = "GREEN (平稳顺风)"
        if kl_div >= 4.0:
            risk_level = "RED (物理熔断/紧急刹车)"
        elif kl_div >= 2.8:
            risk_level = "YELLOW (微幅震荡)"

        # 5. 生成专业操盘手 Markdown 战报
        report_md = self._build_report_markdown(
            target_period=target_period,
            anchor_period=anchor_period,
            draw_date=draw_date,
            primary_spear=primary_spear,
            secondary_spear=secondary_spear,
            shields=selected_shields,
            pairs=pairs,
            backup_pair=backup_pair,
            defense_line_4=defense_line_4,
            kl_div=kl_div,
            risk_level=risk_level
        )

        return PortfolioPredictionResult(
            target_period=target_period,
            anchor_period=anchor_period,
            draw_date=draw_date,
            primary_spear=primary_spear,
            secondary_spear=secondary_spear,
            shields=selected_shields,
            pairs=pairs,
            backup_pair=backup_pair,
            kl_divergence=kl_div,
            risk_level=risk_level,
            defense_line_4=defense_line_4,
            report_markdown=report_md
        )

    def _build_report_markdown(
        self,
        target_period: int,
        anchor_period: int,
        draw_date: str,
        primary_spear: int,
        secondary_spear: int,
        shields: List[int],
        pairs: List[PortfolioPair],
        backup_pair: Optional[PortfolioPair],
        defense_line_4: List[int],
        kl_div: float,
        risk_level: str
    ) -> str:
        """构建大白话实战研报。"""
        shields_str = "、".join(f"{s:02d}" for s in shields)
        def_line_str = " ".join(f"{b:02d}" for b in defense_line_4)

        lines = [
            f"# ⚔️ 一胆拖三盾 · 选2组合拳实战量化研报",
            f"**目标期号**：第 {target_period} 期 ｜ **锚定已开**：第 {anchor_period} 期 ｜ **系统版本**：`Spear_Shield_v1.0`",
            "",
            "---",
            "## 🎯 一、战术核心指令：一攻矛 × 三守盾",
            "> **操盘手大白话**：放弃单注死拼！以 16 窗中热金胆为核心长矛，同时搭配 3 枚憋了 7~13 期的黄金回补盾牌，打出 3 组选2组合拳，把大盘包围圈收紧！",
            f"- 👑 **核心攻矛金胆**：`【 {primary_spear:02d} 】`（锚定 16 窗中热首席金胆；历史水位：{ledger_stat_label('sixteen_hot')}）",
            f"- 🛡️ **三枚防守盾牌**：`【 {shields_str} 】`（黄金遗漏甜区 + 马尔可夫强反弹）",
            f"- 🏰 **4 码钢铁防守包围圈**：`{def_line_str}`",
            "",
            "---",
            "## 💎 二、实战 3 注选2组合拳票面明细",
            "| 战术序号 | 组合拳选2 | 跨度 | 守盾遗漏期数 | 盾牌反弹动能 | 操盘手实操策略 |",
            "| :---: | :---: | :---: | :---: | :---: | :--- |"
        ]

        for idx, p in enumerate(pairs, 1):
            lines.append(
                f"| **组合拳 {idx}** | **`{p.pair_str}`** | `{p.span}` | `遗漏 {p.shield_omission} 期` | `{p.shield_rebound_score}` | 🌟 必跟主战组合 · {p.rationale} |"
            )

        if backup_pair:
            lines.append(
                f"| **备选辅助** | **`{backup_pair.pair_str}`** | `{backup_pair.span}` | `遗漏 {backup_pair.shield_omission} 期` | `{backup_pair.shield_rebound_score}` | 🌿 辅防组合 · {backup_pair.rationale} |"
            )

        lines.extend([
            "",
            "---",
            "## 🛑 三、大盘风控与执行纪律",
            f"- **当前 KL 散度**：`{kl_div}` ｜ **大盘风控评级**：`{risk_level}`",
            "- **投入注数推荐**：标准 3 注（6 元成本）。单注选2随机双中率 6.01%，三注保本需整体见号率高于随机；"
            f"本模块历史水位以系统前瞻账为准（当前：{ledger_stat_label('spear_shield')}），未过门禁前请按研究票对待。",
            "",
            "---",
            "## 📋 四、可直接发群的一句话实战票面",
            "```text",
            f"【第 {target_period} 期 一胆拖三盾实战票面】",
            f"👑 核心攻矛：{primary_spear:02d}",
            f"🛡️ 三大守盾：{shields_str}",
            "💎 选2组合拳（共3注，打法必跟）：",
            *[f"   第{i}注：[{p.pair_str}]" for i, p in enumerate(pairs, 1)],
            f"🏰 4码防线包围圈：{def_line_str}",
            f"风控态势：{risk_level}",
            "```"
        ])

        return "\n".join(lines) + "\n"
