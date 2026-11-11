# -*- coding: utf-8 -*-
"""
综合多期战绩战力榜驱动·选1至选10动态提炼精选服务 (Service Layer)
========================================================================================

【业务背景与架构定位】:
对外提供统一调用入口，自动串联：
1. 从 `storage/outputs/reports/module_ledger_report_latest.json` 读取各模块长期滚动实战账本；
2. 提取近多期（近 30 期前瞻实测）综合命中率、Lift 提升度战力排行；
3. 结合当期各模块预测推荐号码，执行多期战绩赋能计算；
4. 梯队式提炼出【选1至选10】最优号码，并渲染美观 Markdown 章节。

@author czw
@since 2026-11-02
"""
from __future__ import annotations

import os
import sys
import json
from typing import Dict, Any, List, Optional, Tuple

from backend.utils.paths import get_storage_dir, get_outputs_dir
from backend.modules.battle_rank_optimizer.optimizer import BattleRankOptimizer


class BattleRankService:
    """
    综合多期实战战力排行榜驱动提炼服务类
    """

    def __init__(self):
        self.optimizer = BattleRankOptimizer()

    def load_multi_period_ledger(
        self,
        ledger_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        步骤 1: 物理读取官方全模块多期前瞻账本
        """
        if not ledger_path:
            # 默认路径
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            ledger_path = os.path.join(base_dir, "storage", "outputs", "reports", "module_ledger_report_latest.json")

        if not os.path.exists(ledger_path):
            return []

        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            modules = data.get("modules", {})
            records = []
            for k, v in modules.items():
                if v.get("retired", False):
                    continue
                records.append({
                    "key": k,
                    "name": v.get("name", k),
                    "n_periods": v.get("n_periods", 0),
                    "total_picks": v.get("total_picks", 0),
                    "total_hits": v.get("total_hits", 0),
                    "pooled_rate": v.get("pooled_rate", 0.0),
                    "lift": v.get("lift", 0.0),
                    "bh_q": v.get("bh_q"),
                    "bh_significant": bool(v.get("bh_significant")),
                    "lift_ci_lo": v.get("lift_ci_lo"),
                })
            # 按综合 Lift 提升度降序排列
            records.sort(key=lambda x: (x["lift"], x["pooled_rate"]), reverse=True)
            return records
        except Exception:
            return []

    def run_optimization_multi_period(
        self,
        current_module_picks: Dict[str, List[int]],
        multi_period_records: Optional[List[Dict[str, Any]]] = None,
        daily_points: Optional[List[int]] = None,
        tri_high_features: Optional[Dict[str, List[int]]] = None
    ) -> Dict[str, Any]:
        """
        步骤 2: 核心计算流水线 (多期实战综合赋能)
        """
        if not multi_period_records:
            multi_period_records = self.load_multi_period_ledger()

        # 计算多期综合战力权重
        weights = self.optimizer.calculate_module_weights_multi_period(multi_period_records)

        # 当期号码赋能打分
        scored = self.optimizer.score_current_candidates(
            current_module_picks=current_module_picks,
            module_weights=weights,
            daily_points=daily_points,
            tri_high_features=tri_high_features
        )

        # 提炼选1至选10
        picks_hierarchy = self.optimizer.extract_pick1_to_pick10(scored)

        return {
            "ledger_records": multi_period_records,
            "module_weights": weights,
            "scored_candidates": scored,
            "picks_hierarchy": picks_hierarchy
        }

    def execute_auto_pipeline(self, target_period: int) -> str:
        """
        全自动端到端执行流水线：
        1. 自动从当期推演报告中提取所有模块的推荐号码池；
        2. 自动加载点位与三高特征；
        3. 综合多期前瞻实战账本计算各模块胜率与提升度权重；
        4. 贪心提炼【选1至选10】并渲染标准 Markdown 文本。
        """
        # 步骤 1: 加载点位（必须走标准解析器只取"目标期"那一条）
        # 2026-11-06 修复：原实现整文件 split() 取全部数字，daily_points.txt 是
        # 按期号降序的多期台账，一旦超过一行就会把历史点位全部当成当期点位。
        daily_points: List[int] = []
        try:
            from backend.data_acquisition.daily_points_manager import (
                get_latest_points_entry, POINTS_COUNT,
            )
            entry = get_latest_points_entry() or {}
            pts = list(entry.get("points") or [])
            if len(pts) == POINTS_COUNT:
                daily_points = pts
        except Exception:
            daily_points = []

        # 步骤 2: 加载三高特征（文件是按期号归档的 records 台账，必须按目标期取那一条）
        tri_high: Dict[str, List[int]] = {}
        tri_path = os.path.join(get_storage_dir(), "points", "tri_high_points.json")
        if os.path.exists(tri_path):
            try:
                with open(tri_path, "r", encoding="utf-8") as f:
                    raw_tri = json.load(f)
                for _r in (raw_tri.get("records") or []):
                    if str(_r.get("period", "")).strip() == str(target_period):
                        tri_high = {
                            "repeat_high": _r.get("repeat_high") or [],
                            "edge_high": (_r.get("edge_high_left") or []) + (_r.get("edge_high_right") or []),
                            "cold_high": _r.get("cold_high") or [],
                        }
                        break
            except Exception:
                tri_high = {}

        # 步骤 3: 从全模块预测报告中提取各个模块推荐
        current_module_picks: Dict[str, List[int]] = {}
        report_candidates = [
            os.path.join(get_storage_dir(), "reports", f"全模块预测明细_{target_period}.md"),
            os.path.join(get_outputs_dir(), "reports", f"全模块预测明细_{target_period}.md"),
            os.path.join(get_storage_dir(), "reports", "全模块预测明细_latest.md")
        ]
        
        target_rep = None
        for p in report_candidates:
            if os.path.exists(p):
                target_rep = p
                break

        if target_rep and os.path.exists(target_rep):
            import re
            with open(target_rep, "r", encoding="utf-8") as f:
                content = f.read()
            sections = re.split(r"\n###\s+", content)
            for sec in sections[1:]:
                lines = sec.strip().splitlines()
                header = lines[0].strip()
                for line in lines[1:]:
                    if any(k in line for k in ["码：", "Top", "大底", "搭档", "最优 3 码", "金胆", "防线", "主力池", "精选中底"]):
                        m = re.findall(r"`([0-9\s]+)`", line)
                        for raw in m:
                            nums = [int(x) for x in re.findall(r"\b([0-7][0-9]|80)\b", raw)]
                            if nums and len(nums) <= 30:
                                mod_key = f"{header[:12]}_{line[:12].strip()}"
                                current_module_picks[mod_key] = list(dict.fromkeys(nums))

        # 步骤 4: 运行多期战绩赋能优化
        opt_res = self.run_optimization_multi_period(
            current_module_picks=current_module_picks,
            daily_points=daily_points,
            tri_high_features=tri_high
        )

        return self.render_markdown_section_multi_period(str(target_period), opt_res)

    def render_markdown_section_multi_period(
        self,
        target_period: str,
        opt_result: Dict[str, Any]
    ) -> str:
        """
        步骤 3: 渲染美观的 Markdown 章节 (综合多期战绩排行驱动)
        """
        picks_h = opt_result.get("picks_hierarchy", {})
        ranked_details = picks_h.get("all_ranked_details", [])
        ledger_records = opt_result.get("ledger_records", [])

        lines = []
        lines.append(f"## 🏆 七、综合多期实战战绩排行榜驱动 · 【选1至选10】全梯度精选 (battle_rank_optimizer)")
        lines.append("")
        _top3 = ledger_records[:3]
        _examples = "、".join(f"{m['name']} {m['pooled_rate'] * 100:.1f}%" for m in _top3) or "暂无"
        _n_lo = min((m["n_periods"] for m in ledger_records), default=0)
        _n_hi = max((m["n_periods"] for m in ledger_records), default=0)
        lines.append(f"> 📅 **推演目标期**：第 `{target_period}` 期 ｜ **战绩依据**：全模块前瞻账**累计**对账（各模块已对账 {_n_lo}~{_n_hi} 期，并非固定 30 期窗口） ｜ **算法核心**：长期胜率加权与多维贪心寻优")
        lines.append(f"> 操盘手大白话：**“单看昨天一天有运气成分，本模块按各模块历史上真实已对账的战绩加权。当前累计命中率靠前的是：{_examples}。⚠️ 但这些模块**都还没通过 BH-FDR 多重检验校正** —— 统计上属于‘观察级参考’，不是已验证的有效信号，更不等于稳定盈利。”**")
        lines.append("")

        # 模块长期战绩榜展示
        lines.append("### 📊 核心模块多期累计实战战绩排行榜 (Top 10)")
        lines.append("| 排名 | 模块名称 (代码) | 已对账期数 | 总推 / 命中 | 综合命中率 | 提升度 Lift（相对25%基线） | 统计状态 |")
        lines.append("| :---: | :--- | :---: | :---: | :---: | :---: | :--- |")
        for idx, m in enumerate(ledger_records[:10], 1):
            rate_pct = m["pooled_rate"] * 100
            lift_str = f"{m['lift']:.3f}x"
            _bhq = m.get("bh_q")
            if m.get("bh_significant"):
                grade = f"✅ 已过BH-FDR (q={_bhq:.3f})" if isinstance(_bhq, (int, float)) else "✅ 已过BH-FDR"
            elif _bhq is None:
                grade = "⚪ 不参与BH校正（退役/观察）"
            else:
                grade = f"⚠️ 未证显著 (q={_bhq:.3f})"
            lines.append(f"| 第 {idx:2d} 名 | **{m['name']}** (`{m['key']}`) | {m['n_periods']} 期 | {m['total_picks']} / **{m['total_hits']}** | **{rate_pct:.2f}%** | **{lift_str}** | {grade} |")
        lines.append("")

        # 战力 TOP 号码榜单
        lines.append("### 🌟 当期战力总榜 Top 10 (基于长期综合战绩赋能)")
        lines.append("| 综合排名 | 号码 | 战力总分 | 支持模块数 | 核心背书亮点 | 012路属性 |")
        lines.append("| :---: | :---: | :---: | :---: | :--- | :---: |")
        for idx, item in enumerate(ranked_details[:10], 1):
            num = item["number"]
            score = item["score"]
            votes = item["votes"]
            endorsements_str = ", ".join(item["endorsements"][:3])
            road = f"{item['road012']}路"
            point_tag = " [💎点位锚定]" if item["is_point"] else ""
            lines.append(f"| 第 {idx:2d} 名 | **`{num:02d}`** | **{score:.1f}** | {votes} 路 | {endorsements_str}{point_tag} | {road} |")
        lines.append("")

        # 选1至选10 梯队详细输出
        lines.append("### 🎯 选1 至 选10 实战梯队逐项详细展开")
        lines.append("")

        for k in range(1, 11):
            key = f"pick{k}"
            pdata = picks_h.get(key, {})
            if not pdata:
                continue
            tier_name = pdata.get("tier", "")
            nums = pdata.get("numbers", [])
            nums_str = " ".join(f"{x:02d}" for x in nums)
            desc = pdata.get("desc", "")

            lines.append(f"#### 🔹 【{tier_name}】")
            lines.append(f"- **精选阵容 ({len(nums)}码)**：**`{nums_str}`**")
            if k == 1:
                lines.append(f"- **第一金胆**：**`{pdata.get('leader', 0):02d}`**")
            elif k == 2:
                lines.append(f"- **核心双骄搭档**：**`{pdata.get('pair', '')}`**")
            lines.append(f"- **操盘手量化解析**：{desc}")
            lines.append("")

        # 一键可复制文本块
        lines.append("### 📋 选1至选10 操盘速查一键复制文本块")
        lines.append("```text")
        lines.append(f"【快乐8 第 {target_period} 期 综合多期战绩榜驱动·选1至选10实战精选】")
        for k in range(1, 11):
            key = f"pick{k}"
            pdata = picks_h.get(key, {})
            if pdata:
                nums = pdata.get("numbers", [])
                nums_str = " ".join(f"{x:02d}" for x in nums)
                lines.append(f"• 选{k:2d}: {nums_str}")
        lines.append("```")
        lines.append("")

        return "\n".join(lines)
