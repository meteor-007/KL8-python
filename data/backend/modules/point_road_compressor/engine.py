# -*- coding: utf-8 -*-
"""
点位012压缩推演引擎 (PointRoadCompressor Engine v1.0)
================================================================================
【业务背景与量化逻辑】:
本微服务专为快乐8量化操盘研发，遵循老派量化操盘手大白话落地执行协议：
  1. 【点位锚定重心】: 读取当期输入 20 个点位，作为全盘能量的锚点与引力重心；
  2. 【正负2划定半径】: 开奖号码往往不是正好落在点位正中，而是大规模炸裂在点位周围正负 1 或正负 2
     的近邻扩散圈内（近30期实测外围每期高达 11.5 码）。引擎以点位为中心展开 [p-2, p+2] 候选池；
  3. 【012路偏态剪枝过滤】:
     - 模3同余定理：任何点位其正负2窗口必然同时覆盖 0路、1路和 2路；
     - 双层偏态模型：
       * 宏观大盘层：分析近 3~10 期全盘 012 路出号偏态，识别严重超发（熔断冷却）与严重欠出（报复反弹）之路；
       * 微观分区层：8 个十分区（01-10 到 71-80）独立核算 012 路饱和度。若某分区某路持续过热（如七区2路），
         则对该区域该路实施严格的一票否决或大幅扣分剪枝（如精准剔除 65 号）；
  4. 【凝聚压缩交付】:
     将膨胀的候选号码高效压缩至：核心 3 码 (Top3)、精选 5 码 (Top5)、十全防线 (Top10) 与跨路对冲选2搭档。

@author Antigravity Quant Team
@since 2026-10-11
"""
from __future__ import annotations

import os
import sys
import re
import csv
import json
import math
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any, Optional

# 路径双根引导
_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.dirname(_CURR_DIR)
_BACKEND_DIR = os.path.dirname(_MODULES_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils.paths import (
    data_path,
    get_storage_dir,
    get_outputs_dir,
    get_reports_dir,
    get_stats_dir,
)
from backend.utils.history_loader import load_history

TOTAL_BALL_COUNT = 80
POINTS_COUNT = 20

# 8 分区定义
ZONES = [
    (1, 10, "一区(01-10)"),
    (11, 20, "二区(11-20)"),
    (21, 30, "三区(21-30)"),
    (31, 40, "四区(31-40)"),
    (41, 50, "五区(41-50)"),
    (51, 60, "六区(51-60)"),
    (61, 70, "七区(61-70)"),
    (71, 80, "八区(71-80)"),
]


def get_zone_index(num: int) -> int:
    """获取号码所在的 8 分区索引 (0~7)。"""
    if num < 1:
        return 0
    if num > 80:
        return 7
    return min(7, (num - 1) // 10)


def get_road(num: int) -> int:
    """获取号码的 012 路属性 (0, 1, 2)。"""
    return num % 3


class PointRoadCompressorResult:
    """压缩器推演结果结构体"""

    def __init__(
        self,
        target_period: str,
        target_date: str,
        input_points: List[int],
        top3_gold: List[int],
        top5_picks: List[int],
        top10_defense: List[int],
        gold_pairs: List[Tuple[int, int]],
        pruned_candidates: List[Dict[str, Any]],
        retained_candidates: List[Dict[str, Any]],
        macro_road_skew: Dict[str, Any],
        zone_saturation: Dict[str, Any],
        summary_report: str,
    ):
        self.target_period = target_period
        self.target_date = target_date
        self.input_points = input_points
        self.top3_gold = top3_gold
        self.top5_picks = top5_picks
        self.top10_defense = top10_defense
        self.gold_pairs = gold_pairs
        self.pruned_candidates = pruned_candidates
        self.retained_candidates = retained_candidates
        self.macro_road_skew = macro_road_skew
        self.zone_saturation = zone_saturation
        self.summary_report = summary_report

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "target_period": self.target_period,
            "target_date": self.target_date,
            "input_points_count": len(self.input_points),
            "input_points": self.input_points,
            "top3_gold": self.top3_gold,
            "top5_picks": self.top5_picks,
            "top10_defense": self.top10_defense,
            "gold_pairs": [[p[0], p[1]] for p in self.gold_pairs],
            "pruned_candidates_count": len(self.pruned_candidates),
            "pruned_candidates": self.pruned_candidates,
            "retained_candidates_count": len(self.retained_candidates),
            "retained_candidates": self.retained_candidates,
            "macro_road_skew": self.macro_road_skew,
            "zone_saturation": self.zone_saturation,
            "summary_report": self.summary_report,
            "generated_at": datetime.now().isoformat(),
        }


class PointRoadCompressor:
    """点位012压缩推演微服务"""

    def __init__(self, proj_dir: Optional[str] = None):
        self.proj_dir = proj_dir or _PROJ_DIR
        self.points_file = data_path("daily_points.txt")
        self.history_file = data_path("kl8_history_final.txt")
        self.roads_summary_file = os.path.join(get_stats_dir(), "kl8_012_roads_summary.csv")
        self.tri_high_file = os.path.join(get_storage_dir(), "points", "tri_high_points.json")

    def load_latest_points(self, target_period: Optional[str] = None) -> Tuple[str, str, List[int]]:
        """从 daily_points.txt 读取指定或最新期点位。"""
        if not os.path.exists(self.points_file):
            return "", "", []
        try:
            with open(self.points_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    m_iss = re.search(r"period:(\d+)", line)
                    m_date = re.search(r"date:([0-9\-]+)", line)
                    m_pts = re.search(r"points:([\d\s]+)", line)
                    if m_iss and m_pts:
                        p_str = m_iss.group(1)
                        if target_period is None or p_str == str(target_period):
                            d_str = m_date.group(1) if m_date else ""
                            nums = [int(x) for x in m_pts.group(1).split() if x.isdigit()]
                            if len(nums) == POINTS_COUNT:
                                return p_str, d_str, sorted(nums)
        except Exception:
            pass
        return "", "", []

    def load_tri_high(self, target_period: str) -> Dict[str, List[int]]:
        """读取指定期的三高特征。"""
        if not os.path.exists(self.tri_high_file):
            return {"repeat": [], "edge": [], "cold": []}
        try:
            with open(self.tri_high_file, "r", encoding="utf-8") as f:
                records = json.load(f).get("records", [])
            for r in records:
                if str(r.get("period", "")).strip() == str(target_period).strip():
                    rep = [int(x) for x in r.get("repeat_high", []) if 1 <= int(x) <= 80]
                    edge = [int(x) for x in r.get("edge_high_left", []) + r.get("edge_high_right", []) if 1 <= int(x) <= 80]
                    cold = [int(x) for x in r.get("cold_high", []) if 1 <= int(x) <= 80]
                    return {"repeat": rep, "edge": edge, "cold": cold}
        except Exception:
            pass
        return {"repeat": [], "edge": [], "cold": []}

    def expand_neighborhood(self, points: List[int], max_delta: int = 2) -> Dict[int, Dict[str, Any]]:
        """
        步骤 1 & 2: 以 20 个点位为重心，划定正负 2 邻位引力半径展开。
        返回: {号码: {"min_delta": int, "anchors": List[int], "coverage_count": int}}
        """
        expanded: Dict[int, Dict[str, Any]] = {}
        for p in points:
            if not (1 <= p <= TOTAL_BALL_COUNT):
                continue
            for delta in range(-max_delta, max_delta + 1):
                num = p + delta
                if 1 <= num <= TOTAL_BALL_COUNT:
                    if num not in expanded:
                        expanded[num] = {
                            "number": num,
                            "min_delta": abs(delta),
                            "anchors": [p],
                            "coverage_count": 1,
                            "is_exact_point": (delta == 0),
                        }
                    else:
                        expanded[num]["anchors"].append(p)
                        expanded[num]["coverage_count"] += 1
                        if abs(delta) < expanded[num]["min_delta"]:
                            expanded[num]["min_delta"] = abs(delta)
                        if delta == 0:
                            expanded[num]["is_exact_point"] = True
        return expanded

    def analyze_012_skew(
        self,
        history_draws: List[Dict[str, Any]],
        lookback_macro: int = 5,
        lookback_zone: int = 3,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        步骤 3: 012 路宏观大盘偏态建模与微观分区饱和度测算。
        """
        if not history_draws:
            return {}, {}

        # 1. 宏观大盘分析
        recent_macro = history_draws[:lookback_macro]
        road_counts = {0: 0, 1: 0, 2: 0}
        total_balls_macro = 0

        for draw in recent_macro:
            nums = draw.get("numbers", [])
            for n in nums:
                r = get_road(n)
                road_counts[r] += 1
                total_balls_macro += 1

        # 期望比例: 快乐8中 0路26个 (32.5%), 1路27个 (33.75%), 2路27个 (33.75%)
        exp_ratios = {0: 26.0 / 80.0, 1: 27.0 / 80.0, 2: 27.0 / 80.0}
        macro_skew = {}
        for r in [0, 1, 2]:
            act_count = road_counts[r]
            act_ratio = act_count / max(1, total_balls_macro)
            exp_ratio = exp_ratios[r]
            diff = act_ratio - exp_ratio
            # 状态判定
            if diff > 0.05:
                status = "OVERHEATED"  # 严重过热（冷却熔断防守）
                action = "PENALIZE"
            elif diff < -0.05:
                status = "DEFICIT"     # 严重欠出（超跌报复反弹）
                action = "BOOST"
            else:
                status = "BALANCED"    # 均衡态
                action = "NEUTRAL"
            macro_skew[f"road_{r}"] = {
                "road": r,
                "count": act_count,
                "actual_ratio": round(act_ratio, 4),
                "expected_ratio": round(exp_ratio, 4),
                "diff": round(diff, 4),
                "status": status,
                "action": action,
            }

        # 2. 微观 8 分区饱和度测算
        recent_zone = history_draws[:lookback_zone]
        zone_saturation: Dict[str, Any] = {}

        for z_idx, (z_start, z_end, z_name) in enumerate(ZONES):
            z_road_counts = {0: 0, 1: 0, 2: 0}
            z_total = 0
            for draw in recent_zone:
                nums = draw.get("numbers", [])
                for n in nums:
                    if z_start <= n <= z_end:
                        r = get_road(n)
                        z_road_counts[r] += 1
                        z_total += 1

            zone_saturation[f"zone_{z_idx}"] = {
                "zone_index": z_idx,
                "zone_name": z_name,
                "range": [z_start, z_end],
                "total_in_zone": z_total,
                "road_0_count": z_road_counts[0],
                "road_1_count": z_road_counts[1],
                "road_2_count": z_road_counts[2],
            }

        return macro_skew, zone_saturation

    def score_and_compress(
        self,
        expanded_pool: Dict[int, Dict[str, Any]],
        macro_skew: Dict[str, Any],
        zone_sat: Dict[str, Any],
        tri_high: Dict[str, List[int]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        步骤 4: 综合打分、特征赋能与精准剪枝过滤。
        """
        retained: List[Dict[str, Any]] = []
        pruned: List[Dict[str, Any]] = []

        rep_set = set(tri_high.get("repeat", []))
        edge_set = set(tri_high.get("edge", []))
        cold_set = set(tri_high.get("cold", []))

        for num, item in expanded_pool.items():
            min_delta = item["min_delta"]
            coverage = item["coverage_count"]
            road = get_road(num)
            zone_idx = get_zone_index(num)
            z_info = zone_sat.get(f"zone_{zone_idx}", {})

            # 1. 距离基础分
            if min_delta == 0:
                base_score = 35.0  # 点位本身重心
            elif min_delta == 1:
                base_score = 24.0  # 一级直接近邻
            else:
                base_score = 14.0  # 二级扩展邻域

            # 2. 重叠引力加成
            overlap_bonus = (coverage - 1) * 7.5

            # 3. 宏观 012 路偏态调整
            m_info = macro_skew.get(f"road_{road}", {})
            m_status = m_info.get("status", "BALANCED")
            if m_status == "DEFICIT":
                macro_bonus = 18.0   # 超跌欠出路，反弹加分
            elif m_status == "OVERHEATED":
                macro_bonus = -20.0  # 过热路，扣分压制
            else:
                macro_bonus = 0.0

            # 4. 微观分区 012 路饱和度判定 (关键剪枝触发器！)
            zone_road_count = z_info.get(f"road_{road}_count", 0)
            z_total = z_info.get("total_in_zone", 0)
            is_zone_pruned = False
            zone_prune_reason = ""

            # 若该分区该路在近3期内出号异常集中（占该区出号比例 > 55% 且绝对值 >= 3）
            if z_total >= 3 and (zone_road_count / max(1, z_total) >= 0.55):
                # 触发局部过热剪枝！
                zone_bonus = -25.0
                is_zone_pruned = True
                zone_prune_reason = f"{z_info.get('zone_name', '')}{road}路近3期过度饱和(占{zone_road_count}/{z_total})，触发展开剪枝防守"
            elif zone_road_count == 0 and z_total >= 2:
                # 分区该路极度饥渴欠出，回补加分
                zone_bonus = 15.0
            else:
                zone_bonus = 0.0

            # 5. 三高特征协同加成
            tri_bonus = 0.0
            tags = []
            if num in rep_set:
                tri_bonus += 12.0
                tags.append("重复高连庄")
            if num in edge_set:
                tri_bonus += 10.0
                tags.append("边码邻近")
            if num in cold_set:
                tri_bonus += 8.0
                tags.append("冷高回补")

            final_score = base_score + overlap_bonus + macro_bonus + zone_bonus + tri_bonus

            detail_item = {
                "number": num,
                "road": road,
                "zone_index": zone_idx,
                "zone_name": z_info.get("zone_name", f"第{zone_idx+1}区"),
                "min_delta": min_delta,
                "anchors": item["anchors"],
                "coverage_count": coverage,
                "base_score": base_score,
                "overlap_bonus": overlap_bonus,
                "macro_bonus": macro_bonus,
                "zone_bonus": zone_bonus,
                "tri_bonus": tri_bonus,
                "final_score": round(final_score, 1),
                "tags": tags,
                "prune_reason": zone_prune_reason,
            }

            # 剪枝判定阀：被分区强力过热阻断，或扣分后综合得分跌破 15.0 分
            if is_zone_pruned or final_score < 15.0:
                if not zone_prune_reason:
                    zone_prune_reason = f"012路过热叠加距离衰减，综合得分低于防线阈值({round(final_score, 1)}分)"
                detail_item["prune_reason"] = zone_prune_reason
                pruned.append(detail_item)
            else:
                retained.append(detail_item)

        # 排序
        retained.sort(key=lambda x: x["final_score"], reverse=True)
        pruned.sort(key=lambda x: x["final_score"])
        return retained, pruned

    def form_gold_pairs(self, retained: List[Dict[str, Any]]) -> List[Tuple[int, int]]:
        """
        构建跨路对冲选2搭档（例如 1路+0路 或 2路+0路 最佳风险对冲）。
        """
        if len(retained) < 2:
            return []
        pairs: List[Tuple[int, int]] = []
        top_candidates = retained[:8]
        # 寻找跨 012 路且得分最高的组合
        for i in range(len(top_candidates)):
            for j in range(i + 1, len(top_candidates)):
                a = top_candidates[i]
                b = top_candidates[j]
                if a["road"] != b["road"]:  # 跨路对冲
                    pairs.append((min(a["number"], b["number"]), max(a["number"], b["number"])))
                    if len(pairs) >= 3:
                        return pairs
        # 兜底：若无跨路组合则直接取前2
        if not pairs and len(retained) >= 2:
            pairs.append((min(retained[0]["number"], retained[1]["number"]), max(retained[0]["number"], retained[1]["number"])))
        return pairs

    def render_markdown_report(self, res: PointRoadCompressorResult) -> str:
        """渲染老派量化操盘手大白话研报"""
        top3_str = " ".join(f"{x:02d}" for x in res.top3_gold)
        top5_str = " ".join(f"{x:02d}" for x in res.top5_picks)
        top10_str = " ".join(f"{x:02d}" for x in res.top10_defense)
        pts_str = " ".join(f"{x:02d}" for x in res.input_points)
        pairs_str = " ｜ ".join(f"[{a:02d}-{b:02d}]" for a, b in res.gold_pairs)

        lines = [
            f"# 🧬 点位012压缩推演量化决策研报 (PointRoadCompressor v1.0)",
            f"> 📅 **目标期号**：第 `{res.target_period}` 期 ｜ **分析日期**：`{res.target_date}` ｜ **执行引擎**：点位正负2引力展开 × 012路偏态剪枝",
            f"> ⚖️ **核心操盘原则**：点位是引力中心，出号多在正负2；结合大哥012路偏态风水轮流转，该砍就砍，精准压缩！",
            f"",
            f"---",
            f"",
            f"## 一、 核心操盘手压缩战利品 (黄金决策阵容)",
            f"",
            f"- 👑 **至尊压缩第一金胆**：`【 {res.top3_gold[0]:02d} 】` (综合势能分最高)" if res.top3_gold else "- 👑 至尊金胆：—",
            f"- 🌟 **最优 3 码锋线 (Top 3)**：**`{top3_str}`**",
            f"- 🎯 **精选 5 码突击连 (Top 5)**：**`{top5_str}`**",
            f"- 🛡️ **十全防线大底 (Top 10)**：`{top10_str}`",
            f"- 💎 **跨 012 路对冲黄金选 2 搭档**：`{pairs_str}`",
            f"",
            f"---",
            f"",
            f"## 二、 012 路大盘宏观与微观偏态透视",
            f"",
            f"| 012路别 | 近期出号数 | 实际占比 | 理论期望占比 | 偏态诊断（大白话） | 操盘指令 |",
            f"| :---: | :---: | :---: | :---: | :--- | :--- |",
        ]

        for r in [0, 1, 2]:
            m = res.macro_road_skew.get(f"road_{r}", {})
            st = m.get("status", "BALANCED")
            if st == "DEFICIT":
                diag = "❄️ 严重欠发（超跌蓄力反弹态）"
                act = "🔥 优先重仓加分回补"
            elif st == "OVERHEATED":
                diag = "🔥 严重超发（能量耗尽熔断态）"
                act = "🛑 触发防守扣分剪枝"
            else:
                diag = "⚖️ 相对均衡（温和波动态）"
                act = "⚡ 中性常态跟随"
            lines.append(f"| **{r}路** | {m.get('count', 0)} 码 | {m.get('actual_ratio', 0.0)*100:.1f}% | {m.get('expected_ratio', 0.0)*100:.1f}% | {diag} | {act} |")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 三、 ✂️ 剪枝剔除防空档案 (哪些点位/近邻被一票否决？)",
            f"",
            f"> 大白话说明：这部分号码原本在点位及其正负2辐射圈内，但因为撞上了 012 路局部严重过热或大盘熔断期，被系统严格剪枝剔除，防范诱多陷阱！",
            f"",
        ])

        if res.pruned_candidates:
            lines.append("| 剔除号码 | 012路别 | 所属分区 | 原所属点位锚点 | 剪枝熔断剔除原因 |")
            lines.append("| :---: | :---: | :---: | :---: | :--- |")
            for p in res.pruned_candidates[:8]:
                anchors_s = "、".join(f"{a:02d}" for a in p.get("anchors", []))
                lines.append(f"| **`{p['number']:02d}`** | {p['road']}路 | {p['zone_name']} | 点位 [{anchors_s}] | {p.get('prune_reason', '过热剪枝')} |")
        else:
            lines.append("- ✅ 本期辐射圈内未触发强力剪枝剔除。")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 四、 原始点位档案",
            f"- **当期录入 20 点位**：`{pts_str}`",
            f"- **展开辐射池容量**：共覆盖 `{len(res.retained_candidates) + len(res.pruned_candidates)}` 码，经 012 路剪枝压缩后保留 `{len(res.retained_candidates)}` 码精选池。",
        ])

        return "\n".join(lines)

    def run_prediction(
        self,
        target_period: Optional[str] = None,
        daily_points: Optional[List[int]] = None,
        tri_high_data: Optional[Dict[str, List[int]]] = None,
    ) -> PointRoadCompressorResult:
        """主执行入口：端到端完成点位012压缩推演并落盘。"""
        # 1. 解析目标期与点位
        hist = load_history()
        if not hist:
            raise RuntimeError("历史开奖库为空！")
        latest_hist_period = str(hist[0].get("issue", ""))
        # 2026-10-21 P2 整改：原先解析失败时回落编造期号 "2026001"，整份产物会顶着假期号落盘。
        if not latest_hist_period.isdigit():
            raise RuntimeError(
                f"最新开奖记录期号非法 (issue={latest_hist_period!r})，拒绝用编造期号推演。"
            )
        calc_target = str(int(latest_hist_period) + 1)
        target_p = str(target_period or calc_target)

        # 2026-10-21 P2 前视泄露护栏：外部显式传入**历史期号**做补录时，
        # 下方所有特征 (012路偏态、分区饱和度、共现、遗漏) 原本仍用全量 hist 计算，
        # 而全量 hist 含 target_p 之后（含 target_p 本身）的开奖 —— 等于用未来预测过去。
        # 本模块自己的 run_walk_forward_review 用的是正确切片，此处与之对齐。
        if target_p != calc_target:
            try:
                _tp_int = int(target_p)
            except (TypeError, ValueError):
                raise RuntimeError(f"传入的目标期号非法: {target_p!r}")
            _cut = [h for h in hist if str(h.get("issue", "")).isdigit()
                    and int(h["issue"]) < _tp_int]
            if len(_cut) < 30:
                raise RuntimeError(
                    f"补录第 {target_p} 期所需的前视安全样本不足 (仅 {len(_cut)} 期)，拒绝推演。"
                )
            hist = _cut
        target_d = datetime.now().strftime("%Y-%m-%d")

        # 读取点位
        if daily_points is None or len(daily_points) != POINTS_COUNT:
            p_str, d_str, pts = self.load_latest_points(target_p)
            if not pts:
                # 兼容降级：取点位库最新第一条
                p_str, d_str, pts = self.load_latest_points(None)
            if pts:
                daily_points = pts
                if d_str:
                    target_d = d_str
            else:
                daily_points = []

        # 读取三高
        if tri_high_data is None:
            tri_high_data = self.load_tri_high(target_p)

        # 2. 邻位引力半径展开
        expanded = self.expand_neighborhood(daily_points, max_delta=2)

        # 3. 012 路偏态建模
        macro_skew, zone_sat = self.analyze_012_skew(hist, lookback_macro=5, lookback_zone=3)

        # 4. 打分与剪枝过滤
        retained, pruned = self.score_and_compress(expanded, macro_skew, zone_sat, tri_high_data)

        # 5. 生成梯队与搭档
        top3_gold = [x["number"] for x in retained[:3]]
        top5_picks = [x["number"] for x in retained[:5]]
        top10_defense = [x["number"] for x in retained[:10]]
        gold_pairs = self.form_gold_pairs(retained)

        # 6. 生成研报
        temp_res = PointRoadCompressorResult(
            target_period=target_p,
            target_date=target_d,
            input_points=daily_points,
            top3_gold=top3_gold,
            top5_picks=top5_picks,
            top10_defense=top10_defense,
            gold_pairs=gold_pairs,
            pruned_candidates=pruned,
            retained_candidates=retained,
            macro_road_skew=macro_skew,
            zone_saturation=zone_sat,
            summary_report="",
        )
        report_text = self.render_markdown_report(temp_res)
        temp_res.summary_report = report_text

        # 7. 物理落盘 (JSON + Markdown)
        out_dir = os.path.join(get_outputs_dir(), "point_road_compressor")
        os.makedirs(out_dir, exist_ok=True)
        report_dir = get_reports_dir()
        os.makedirs(report_dir, exist_ok=True)

        json_file_period = os.path.join(out_dir, f"point_road_compressed_{target_p}.json")
        json_file_latest = os.path.join(out_dir, "point_road_compressed_latest.json")
        report_file_period = os.path.join(report_dir, f"point_road_compressor_report_{target_p}.md")
        report_file_latest = os.path.join(report_dir, "point_road_compressor_report_latest.md")

        with open(json_file_period, "w", encoding="utf-8") as f:
            json.dump(temp_res.to_dict(), f, ensure_ascii=False, indent=2)
        with open(json_file_latest, "w", encoding="utf-8") as f:
            json.dump(temp_res.to_dict(), f, ensure_ascii=False, indent=2)

        with open(report_file_period, "w", encoding="utf-8") as f:
            f.write(report_text)
        with open(report_file_latest, "w", encoding="utf-8") as f:
            f.write(report_text)

        return temp_res

    def run_walk_forward_review(self, n_periods: int = 30, verbose: bool = True) -> Dict[str, Any]:
        """
        Walk-Forward 无未来信息滚动样本外对账与回测。
        """
        hist = load_history()
        if len(hist) < n_periods + 10:
            n_periods = max(5, len(hist) - 10)

        # 加载所有历史点位
        points_map: Dict[str, List[int]] = {}
        if os.path.exists(self.points_file):
            with open(self.points_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m_iss = re.search(r"period:(\d+)", line)
                    m_pts = re.search(r"points:([\d\s]+)", line)
                    if m_iss and m_pts:
                        p_str = m_iss.group(1)
                        pts = [int(x) for x in m_pts.group(1).split() if x.isdigit()]
                        if len(pts) == POINTS_COUNT:
                            points_map[p_str] = pts

        top3_hits = []
        top5_hits = []
        prune_correct_counts = []
        total_pruned_counts = []

        tested = 0
        for i in range(n_periods):
            # i=0 对应最新一期已开奖
            target_draw = hist[i]
            target_period = str(target_draw["issue"])
            actual_nums = set(target_draw.get("numbers", []))
            if not actual_nums or target_period not in points_map:
                continue

            past_hist = hist[i + 1:]  # 仅使用历史，严禁未来信息！
            pts = points_map[target_period]
            tri = self.load_tri_high(target_period)

            # 运行压缩
            expanded = self.expand_neighborhood(pts, max_delta=2)
            macro_skew, zone_sat = self.analyze_012_skew(past_hist, lookback_macro=5, lookback_zone=3)
            retained, pruned = self.score_and_compress(expanded, macro_skew, zone_sat, tri)

            top3 = [x["number"] for x in retained[:3]]
            top5 = [x["number"] for x in retained[:5]]
            pruned_nums = [x["number"] for x in pruned]

            h3 = len(set(top3) & actual_nums)
            h5 = len(set(top5) & actual_nums)
            # 剪枝准确率：被剪掉的号码中，实际确实没有开出的比例
            prune_correct = sum(1 for p in pruned_nums if p not in actual_nums)

            top3_hits.append(h3)
            top5_hits.append(h5)
            prune_correct_counts.append(prune_correct)
            total_pruned_counts.append(len(pruned_nums))
            tested += 1

        if tested == 0:
            return {"status": "error", "message": "无足够样本供回测"}

        avg_top3 = sum(top3_hits) / tested
        avg_top5 = sum(top5_hits) / tested
        lift3 = avg_top3 / (3.0 * 20.0 / 80.0)
        lift5 = avg_top5 / (5.0 * 20.0 / 80.0)
        tot_pruned = sum(total_pruned_counts)
        tot_pruned_correct = sum(prune_correct_counts)
        prune_acc = (tot_pruned_correct / tot_pruned) if tot_pruned > 0 else 0.0

        res = {
            "tested_periods": tested,
            "avg_top3_hits": round(avg_top3, 2),
            "lift_top3": round(lift3, 2),
            "avg_top5_hits": round(avg_top5, 2),
            "lift_top5": round(lift5, 2),
            "total_pruned_candidates": tot_pruned,
            "pruning_avoidance_rate": round(prune_acc * 100.0, 1),
        }

        if verbose:
            print(f"\n" + "=" * 76)
            print(f"📊 [PointRoadCompressor] 近 {tested} 期样本外 Walk-Forward 滚动实盘对账")
            print(f"=" * 76)
            print(f"  • 最优 3 码均命中 : {avg_top3:.2f} / 3 码  |  提升度 (Lift) = {lift3:.2f}x (基线 25.0%)")
            print(f"  • 精选 5 码均命中 : {avg_top5:.2f} / 5 码  |  提升度 (Lift) = {lift5:.2f}x (基线 25.0%)")
            print(f"  • 012 偏态剪枝防守率: {prune_acc * 100:.1f}% (被剪枝剔除的号码实际未开出比例，防守基线 75.0%)")
            print(f"=" * 76 + "\n")

        return res


def run_compressor_prediction(target_period: Optional[str] = None) -> PointRoadCompressorResult:
    """全局调用快捷函数"""
    compressor = PointRoadCompressor()
    return compressor.run_prediction(target_period=target_period)
