# -*- coding: utf-8 -*-
"""
全模块量化预测标准模版与终极研报生成引擎 (Standard Full Module Report Engine v1.0)
========================================================================================

【业务背景与架构定位】:
本模块作为快乐8智能量化操盘决策终端的核心交付中枢，负责在每日开奖数据更新、点位录入与全模块
推演完成后，全自动无损收割 22 大模块的最新预测成果，严格按照操盘手大白话标准协议，
装配并渲染成结构严谨、细节详尽、涵盖微信分桶与多套可一键复制发群纯文本的终极标准研报。

【核心交付规范】:
1. 涵盖数据源基准、日常舱 12+ 模块独立预测、研究舱 8 大前沿模型、退役舱档案；
2. 顺口溜严格实现【双轨制】：基于 90 条精英口诀规则库 + 基于历史大数据关联带出；
3. 严格装配【三维交集共识定胆系统 (Consensus Straddle)】；
4. 包含 16 期中热全景、微信分桶 80 码闭环原文与多套可直接发群的一键复制纯文本代码块；
5. 自动持久化落盘至 storage/reports/全模块预测明细_{period}.md 与 latest.md。

@author Antigravity Quant Team
@since 2026-09-30
"""
from __future__ import annotations

import os
import sys
import glob
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_CURR_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.utils.paths import get_outputs_dir, get_reports_dir, data_path
from backend.utils.history_loader import load_history
from backend.utils import kl8_probability as prob


def get_latest_draw_and_target() -> Tuple[Dict[str, Any], str, str]:
    """获取最新开奖数据并安全推断目标期号与目标日期"""
    history = load_history()
    if not history:
        raise RuntimeError("开奖历史库为空，无法推算期号！")
    latest = history[0]
    latest_period = str(latest.get("issue", ""))
    # 2026-10-21 P2 整改：期号解析不出时原先回落 "2026001" —— 那是个**编造期号**，
    # 会让整份全模块研报顶着假期号落盘并被下游当真实产物消费。改为显式报错。
    if not latest_period.isdigit():
        raise RuntimeError(
            f"最新开奖记录期号非法 (issue={latest_period!r})，拒绝用编造期号生成研报。"
        )
    target_period = str(int(latest_period) + 1)
    target_date = datetime.now().strftime("%Y-%m-%d")
    return latest, target_period, target_date


def load_daily_points_entry(target_period: str) -> List[int]:
    """读取指定目标期的每日点位 (20码)。

    2026-10-09 整改: 原来"未命中目标期就取第一条", 会在目标期还没录入时悄悄拿上一期
    的点位当今日点位用。现在严格按期号取, 取不到就返回空 (调用方标无数据)。
    """
    pts_file = data_path("daily_points.txt")
    if not os.path.exists(pts_file):
        return []
    try:
        with open(pts_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if f"period:{target_period}" in line:
                    m = re.search(r"points:([\d\s]+)", line)
                    if m:
                        return [int(x) for x in m.group(1).split() if x.isdigit()]
    except Exception:
        pass
    return []


def load_tri_high_entry(target_period: str) -> Dict[str, Any]:
    """读取指定目标期的三高录入数据 (取不到即返回空, 不用其它期的数据顶替)。"""
    path = os.path.join(_PROJ_DIR, "storage", "points", "tri_high_points.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f).get("records", [])
        for r in records:
            if str(r.get("period", "")).strip() == str(target_period).strip():
                return r
    except Exception:
        pass
    return {}


def format_num(n: Any) -> str:
    """安全格式化两位号码字符串"""
    try:
        return f"{int(n):02d}"
    except Exception:
        return str(n)


def format_nums(nums: List[Any], sep: str = " ") -> str:
    """列表号码转字符串"""
    return sep.join(format_num(x) for x in nums)


# ── 数据诚信闸门 (2026-10-09 整改) ──
# 大白话: 以前产物读不到就直接把作者写死的旧号码顶上去, 报告里根本看不出哪些是真算的、
# 哪些是模板抄的。现在一律"读不到就写无数据", 并在文末列出缺口清单, 绝不拿旧数字冒充今日预测。
MISSING = "—（无数据）"


def _num_list(v: Any) -> List[int]:
    """把任意产物里的号码字段规整成合法号码列表 (1~80)。"""
    if v is None:
        return []
    if isinstance(v, (int, float)):
        v = [v]
    if isinstance(v, str):
        v = re.split(r"[^0-9]+", v)
    if not isinstance(v, (list, tuple)):
        return []
    out: List[int] = []
    for x in v:
        if isinstance(x, dict):
            x = x.get("number", x.get("ball"))
        try:
            n = int(x)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 80:
            out.append(n)
    return out


def _product_period(d: Dict[str, Any]) -> str:
    """读取产物自报的目标期号 (兼容 target_period / target_issue)。"""
    for k in ("target_period", "target_issue"):
        v = d.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return ""


def _period_ok(d: Dict[str, Any], target: str) -> bool:
    """产物是否确实是为本次目标期算的 (防拿旧产物冒充当期)。"""
    if not d:
        return False
    p = _product_period(d)
    return bool(p) and p == str(target).strip()


def _covers(nums: List[int], tag: str) -> str:
    """号码列表渲染: 空 → 无数据标记 + 缺口标签。"""
    return format_nums(nums) if nums else f"{MISSING}({tag})"


class EvidenceGap:
    """记录"本应产出却没有当期产物"的模块, 汇总到报告末尾的缺口清单。"""

    def __init__(self) -> None:
        self.items: List[str] = []

    def add(self, module: str, reason: str) -> str:
        if module not in [i.split(":")[0] for i in self.items]:
            self.items.append(f"{module}: {reason}")
        return MISSING

    def render(self) -> str:
        if not self.items:
            return "- ✅ 本次报告全部模块均由**当期真实产物**渲染，无缺口。"
        return "\n".join(f"- ⚠️ **{i}**" for i in self.items)


def _thirty_ball_evidence_line(l_issue: str, gap: EvidenceGap) -> str:
    """30 码大底的量化依据行: 动态读取 benchmark 证据产物 (中性口径)。

    产物缺失 / 损坏 / 基准期落后于最新开奖 → 记入缺口清单并渲染无数据,
    绝不引用写死的回测成绩冒充当日依据。
    """
    missing_line = f"> 🔬 **量化模型依据**：{MISSING}"
    art_path = os.path.join(get_outputs_dir(), "reports", "thirty_ball_benchmark_report.json")
    try:
        with open(art_path, "r", encoding="utf-8") as f:
            art = json.load(f)
    except Exception:
        gap.add("三十码回测依据", "benchmark 产物缺失（未运行 thirty_ball_benchmark.py）")
        return missing_line
    if not isinstance(art, dict) or not art.get("recommended"):
        gap.add("三十码回测依据", "benchmark 产物损坏（无 recommended 字段）")
        return missing_line
    if str(art.get("base_period")) != str(l_issue).strip():
        gap.add(
            "三十码回测依据",
            f"benchmark 基准期 {art.get('base_period')} 落后于最新开奖 {l_issue}，需重跑 thirty_ball_benchmark.py",
        )
        return missing_line
    rec = next(
        (s for s in art.get("strategies", []) if isinstance(s, dict) and s.get("id") == art.get("recommended")),
        None,
    )
    if not rec:
        gap.add("三十码回测依据", "benchmark 产物缺少推荐方案明细")
        return missing_line
    base_p11 = float(art.get("baseline", {}).get("p_ge11") or 0.0)
    verdict = (
        "通过 BH-FDR 0.05 门槛（仍需样本外持续跟踪，不可外推为长期优势）"
        if rec.get("significant")
        else "未通过 BH-FDR 0.05 门槛，与随机基线差异不能排除随机波动，仅作覆盖型参考、不作加注依据"
    )
    return (
        f"> 🔬 **量化模型依据（动态读取回测产物，基准期 {art.get('base_period')}）**：近 {art.get('n_periods')} 期 OOF 盲测，"
        f"成员算法「{rec.get('name')}」≥11 码 {rec.get('ge11_count')}/{rec.get('n_periods')}"
        f"（{rec.get('ge11_rate')}%，随机基线 {base_p11 * 100:.1f}%），"
        f"Wilson95 [{rec.get('wilson_lo', 0) * 100:.1f}%, {rec.get('wilson_hi', 0) * 100:.1f}%]，"
        f"BH-q={rec.get('bh_q')} —— {verdict}。"
    )


class StandardDailyReportEngine:
    """全模块标准研报组装与渲染引擎"""

    def __init__(self, proj_dir: str = _PROJ_DIR):
        self.proj_dir = proj_dir
        # 退役判决的唯一答案来源。报告层不再各自判断「这个模块还要不要展示」，
        # 一律问这里 —— 与流水线、记账闸门共用同一份 MODULE_SEED。
        try:
            from core.module_gate import retired_module_ids
            self.retired = set(retired_module_ids())
        except Exception:
            self.retired = set()

    def is_active(self, module_id: str) -> bool:
        return module_id not in self.retired

    def retired_note(self, module_id: str) -> str:
        """退役模块在报告里的统一标注（活跃模块返回空串）。

        没有这行标注时，退役模块会因为读不到当期产物而被渲染成「产物缺失」，
        读起来像数据故障 —— 实际上是判决结果，两件事必须分开说。
        """
        if self.is_active(module_id):
            return ""
        return ("> ⏹ **本模块已退役**：前瞻账实测未跑赢 25% 随机基线，"
                "不参与决议与 BH-FDR 校正。以下为历史口径说明，**不产出当期号码**。")

    # 报告小节序号 → 注册表模块 id。
    # 不用正则从标题里抠名字：标题格式不统一（"(Trinity Fusion)"、"(road_prime_shrink / TPRD v2.0)"），
    # 抠不准就会静默漏标注 —— 而漏标注的恰恰是读者最容易当真读的那几节。
    _SECTION_MODULE_IDS = {
        "1": "formula_jingle", "2": "consensus_straddle", "3": "sixteen_hot",
        "4": "tri_high", "5": "gold_pick2", "6": "point_suppression",
        "7": "datasource", "8": "trinity_top5", "9": "psychological_game",
        "10": "prime_composite", "11": "multi_resonance", "12": "error_correction",
        "13": "spear_shield", "14": "point_road_compressor",
        "15": "road_prime_shrink", "16": "point_omission",
    }

    def _ledger_stats(self) -> Dict[str, Any]:
        """前瞻账逐模块统计（懒加载一次，避免每节重复读 jsonl 与跑 FDR）。"""
        if getattr(self, "_stats_cache", None) is None:
            try:
                from core.module_gate import module_ledger_report
                rep = module_ledger_report(min_n=30)
                self._stats_cache = rep.get("modules", {}) or {}
            except Exception:
                self._stats_cache = {}
        return self._stats_cache

    def module_stat_line(self, module_id: str) -> str:
        """模块实测对照行：把「理论期望 vs 历史实测」直接摆在号码旁边。

        没有这一行时，「至尊共识第一金胆：40」读起来像一条预测结论；
        有了它，读者一眼能看到该模块的历史命中率、与 25% 随机基线差多少、
        以及是否通过显著性检验。这是本报告最重要的上下文。
        """
        st = self._ledger_stats().get(module_id)
        if not isinstance(st, dict) or not st.get("total_picks"):
            return ""

        picks = st["total_picks"]
        hits = st.get("total_hits") or 0
        rate = st.get("pooled_rate")
        lift = st.get("lift")
        n_periods = st.get("n_periods") or 0

        if st.get("retired"):
            verdict = "已退役，不参与校正"
        elif st.get("bh_significant"):
            verdict = "**已过 BH-FDR**"
        elif st.get("insufficient"):
            verdict = "样本不足，尚无结论"
        else:
            verdict = "**未过 BH-FDR，与随机无统计差异**"

        rate_txt = f"{rate * 100:.1f}%" if isinstance(rate, (int, float)) else "—"
        lift_txt = f"{lift:.2f}x" if isinstance(lift, (int, float)) else "—"
        return (f"> 📊 **实测对照**：理论基线 25.0% ｜ 历史实测 **{rate_txt}**"
                f"（{n_periods} 期 / {picks} 票 / 命中 {hits}）｜ Lift **{lift_txt}** ｜ {verdict}")

    def budget_facts(self) -> str:
        """预算与期望回报区块。

        奖金表未配置时明确说明「本节不计算」，而不是给一个看似合理的数字 ——
        凭空捏一个返奖率推出来的期望回报，比不给更危险。
        """
        try:
            from backend.utils import kl8_budget as budget
        except Exception as e:                                    # noqa: BLE001
            return f"> ⚠️ 预算模块不可用：{e}"

        table = budget.load_payout_table()
        if not budget.is_configured(table):
            return ("## 💰 预算与期望回报\n\n"
                    "> ⚠️ **奖金表未配置，本节不做任何计算。**\n"
                    "> 快乐8 各玩法的奖金按渠道与期次规则变化，把金额写死在代码里等于伪造数据。\n"
                    "> 请按所购渠道的官方规则填写 `backend/config/kl8_payout.json`，并置 `configured: true`。\n"
                    "> 在填好之前，本节不给出任何期望回报数字 —— **缺失信息好过错误信息**。")

        rows = ["## 💰 预算与期望回报（每注）", "",
                "| 玩法 | 单注成本 | 期望回报 | 期望净 | 返奖率 | 至少中一档 |",
                "| :--- | ---: | ---: | ---: | ---: | ---: |"]
        risk = []
        for play in table.get("plays", {}):
            m = budget.play_metrics(play, 1, table)
            if m.get("status") != "ok":
                continue
            rows.append(
                f"| {play} | {m['stake']:.2f} 元 | {m['expected_payout']:.3f} 元 | "
                f"{m['expected_net']:+.3f} 元 | {m['return_rate'] * 100:.1f}% | "
                f"{m['prob_any_prize'] * 100:.2f}% |"
            )
            risk.append(
                f"- **{play}**：全额落空 **{m['prob_total_loss'] * 100:.1f}%** ｜ "
                f"单注回报标准差 **{m['payout_std']:.2f} 元**"
                f"（约 {m['payout_std'] / m['stake']:.1f} 倍注额）"
            )
        rows += ["", "**波动与风险（单注）**："] + risk + [
            "",
            "> 买 N 注时：期望回报与成本同比例增长，标准差只增长 √N 倍。",
            "> 也就是说**买得越多，相对波动越小，但期望亏损比例一点不变**。",
        ]
        src = table.get("source") or "未注明来源"
        ver = table.get("source_version") or "未注明版本"
        rows += ["",
                 f"> 奖金表来源：{src}（{ver}）。",
                 "> 期望回报是**长期平均值**，单期波动极大，不代表任何一期的实际结果。"]
        return "\n".join(rows)

    def gather_all_data(self, target_period: Optional[str] = None) -> Dict[str, Any]:
        """全面归集 22 大模块与全部输入源的真实计算产物"""
        latest_draw, calc_target, target_date = get_latest_draw_and_target()
        target = str(target_period or calc_target)

        bundle: Dict[str, Any] = {
            "target_period": target,
            "target_date": target_date,
            "latest_draw": latest_draw,
            "daily_points": load_daily_points_entry(target),
            "tri_high_raw": load_tri_high_entry(target),
        }

        # 1. 16期中热与微信分桶
        sixteen_json = os.path.join(self.proj_dir, "storage", "cache", "sixteen_period", "excel_window_latest.json")
        if os.path.exists(sixteen_json):
            try:
                with open(sixteen_json, "r", encoding="utf-8") as f:
                    bundle["sixteen"] = json.load(f)
            except Exception:
                bundle["sixteen"] = {}
        else:
            bundle["sixteen"] = {}

        # 2. 顺口溜
        jingle_txt = os.path.join(self.proj_dir, "storage", "outputs", "predictions", f"顺口溜预测_{target}.txt")
        if not self.is_active("formula_jingle"):
            # 已退役：不读产物（否则旧产物会被当成当期结论继续展示）
            bundle["jingle_raw"] = ""
        elif os.path.exists(jingle_txt):
            try:
                with open(jingle_txt, "r", encoding="utf-8") as f:
                    bundle["jingle_raw"] = f.read()
            except Exception:
                bundle["jingle_raw"] = ""
        else:
            bundle["jingle_raw"] = ""

        # 3. 三维交集共识定胆系统
        #    2026-10-09 整改: 原来"当期报告不存在就退到目录里最新那一份", 会把上一期的
        #    共识金胆当成今日金胆发出去。现在只认当期文件, 找不到就留空待标无数据。
        cs_md = os.path.join(self.proj_dir, "storage", "outputs", "reports", f"consensus_straddle_report_{target}.md")
        if not self.is_active("consensus_straddle"):
            # 已退役：不读产物，避免把退役模块的旧号码当成在册模块的当期结论展示
            bundle["consensus_straddle_raw"] = ""
        elif os.path.exists(cs_md):
            try:
                with open(cs_md, "r", encoding="utf-8") as f:
                    bundle["consensus_straddle_raw"] = f.read()
            except Exception:
                bundle["consensus_straddle_raw"] = ""
        else:
            bundle["consensus_straddle_raw"] = ""

        # 4. 定胆选2
        pick2_txt = os.path.join(self.proj_dir, "storage", "outputs", "gold_pick2", f"定金选2预测_{target}.txt")
        if not os.path.exists(pick2_txt):
            pick2_txt = os.path.join(self.proj_dir, "storage", "outputs", "gold_pick2", "定金选2预测_最新.txt")
        if os.path.exists(pick2_txt):
            try:
                with open(pick2_txt, "r", encoding="utf-8") as f:
                    bundle["gold_pick2_raw"] = f.read()
            except Exception:
                bundle["gold_pick2_raw"] = ""
        else:
            bundle["gold_pick2_raw"] = ""

        # 5. 未开点位反弹
        supp_txt = os.path.join(self.proj_dir, "storage", "outputs", "point_suppression", "未开点位反弹预测.txt")
        if os.path.exists(supp_txt):
            try:
                with open(supp_txt, "r", encoding="utf-8") as f:
                    bundle["suppression_raw"] = f.read()
            except Exception:
                bundle["suppression_raw"] = ""
        else:
            bundle["suppression_raw"] = ""

        # 6. 三高深度共振
        tri_json = os.path.join(self.proj_dir, "storage", "points", "tri_high_analysis.json")
        if os.path.exists(tri_json):
            try:
                with open(tri_json, "r", encoding="utf-8") as f:
                    bundle["tri_high_analysis"] = json.load(f)
            except Exception:
                bundle["tri_high_analysis"] = {}
        else:
            bundle["tri_high_analysis"] = {}

        # 7. 统一决策脑
        brain_json = os.path.join(self.proj_dir, "storage", "outputs", "unified_brain", f"unified_decision_{target}.json")
        if os.path.exists(brain_json):
            try:
                with open(brain_json, "r", encoding="utf-8") as f:
                    bundle["brain"] = json.load(f)
            except Exception:
                bundle["brain"] = {}
        else:
            bundle["brain"] = {}

        # 8. 心理博弈论
        psych_json = os.path.join(self.proj_dir, "storage", "stats", "psychological_game_analysis.json")
        if os.path.exists(psych_json):
            try:
                with open(psych_json, "r", encoding="utf-8") as f:
                    bundle["psych"] = json.load(f)
            except Exception:
                bundle["psych"] = {}
        else:
            bundle["psych"] = {}

        # 9. 质合尾数
        prime_json = os.path.join(self.proj_dir, "storage", "stats", "prime_tail_entropy_analysis.json")
        if os.path.exists(prime_json):
            try:
                with open(prime_json, "r", encoding="utf-8") as f:
                    bundle["prime"] = json.load(f)
            except Exception:
                bundle["prime"] = {}
        else:
            bundle["prime"] = {}

        # 10. 多维共振
        multi_json = os.path.join(self.proj_dir, "storage", "stats", "multi_resonance_consensus.json")
        if os.path.exists(multi_json):
            try:
                with open(multi_json, "r", encoding="utf-8") as f:
                    bundle["multi_resonance"] = json.load(f)
            except Exception:
                bundle["multi_resonance"] = {}
        else:
            bundle["multi_resonance"] = {}

        # 11. 研究舱模型集合
        #     (遗传/线性代数/DTW/Transformer/MatrixProfile/TDA/随机森林/残差改错)
        #     2026-10-09 整改: 这些原本在报告里是一张写死的静态表, 每期都印同样 8 行号码。
        #     现在逐个读真实产物, 并核对 target_issue 是否等于目标期。
        for r_id, fname in [
            ("rf", "random_forest_latest.json"),
            ("la", "linear_algebra_latest.json"),
            ("dtw", "dtw_latest.json"),
            ("transformer", "transformer_latest.json"),
            ("mp", "matrix_profile_latest.json"),
            ("tda", "tda_latest.json"),
            ("error_correction", "error_correction_latest.json"),
        ]:
            # 键 → 模块 id：用于向判决层查询「这个模块还在不在册」。
            # 未列出的键（rf/la/dtw…）不是注册表 id，is_active 按活跃处理，
            # 它们是否退役由研究舱那一段的归档说明负责，不在此处处理。
            _RID_MODULE = {"error_correction": "error_correction"}
            if not self.is_active(_RID_MODULE.get(r_id, r_id)):
                bundle[r_id] = {}
                continue
            p = os.path.join(self.proj_dir, "storage", "outputs", fname)
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        bundle[r_id] = json.load(f)
                except Exception:
                    bundle[r_id] = {}
            else:
                bundle[r_id] = {}

        # 12. 遗传算法 (report 落 storage/reports)
        gen_path = os.path.join(self.proj_dir, "storage", "reports", f"genetic_algorithm_report_{target}.md")
        bundle["genetic_raw"] = ""
        if os.path.exists(gen_path):
            try:
                with open(gen_path, "r", encoding="utf-8") as f:
                    bundle["genetic_raw"] = f.read()
            except Exception:
                pass

        # 13. 大报引擎自学习状态 (极简选2 / Trinity / HiddenEnergy5 等只在此按期留档)
        bundle["state_record"] = {}
        state_path = os.path.join(self.proj_dir, "storage", "cache", "self_learning_state.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8", errors="replace") as f:
                    hist = (json.load(f) or {}).get("history") or []
                cands = [r for r in hist if str(r.get("target_issue")) == str(target)]
                cands.sort(key=lambda r: str(r.get("run_time") or ""), reverse=True)
                if cands:
                    bundle["state_record"] = cands[0]
            except Exception:
                pass

        # 13b. 一胆拖三盾 (当期 md)
        spear_md = os.path.join(self.proj_dir, "storage", "outputs", "reports", f"spear_shield_report_{target}.md")
        bundle["spear_raw"] = ""
        if os.path.exists(spear_md):
            try:
                with open(spear_md, "r", encoding="utf-8") as f:
                    bundle["spear_raw"] = f.read()
            except Exception:
                pass

        # 14. 大报引擎工业级日报 (Trinity / HiddenEnergy5 只在这里按期留档)
        bundle["daily_report_text"] = ""
        try:
            cands = sorted(
                glob.glob(os.path.join(get_reports_dir(), "daily_analysis_report_*.md")),
                key=os.path.getmtime, reverse=True,
            )[:8]
            for p in cands:
                head = open(p, encoding="utf-8", errors="replace").read(1500)
                if re.search(r"目标期号[：:]\s*\**\s*%s" % re.escape(target), head):
                    bundle["daily_report_text"] = open(p, encoding="utf-8", errors="replace").read()
                    break
        except Exception:
            pass

        # 14b. 点位012压缩器 (PointRoadCompressor)
        prc_path = os.path.join(self.proj_dir, "storage", "outputs", "point_road_compressor", f"point_road_compressed_{target}.json")
        if not os.path.exists(prc_path):
            prc_path = os.path.join(self.proj_dir, "storage", "outputs", "point_road_compressor", "point_road_compressed_latest.json")
        bundle["point_road_compressor"] = {}
        if os.path.exists(prc_path):
            try:
                with open(prc_path, "r", encoding="utf-8") as f:
                    bundle["point_road_compressor"] = json.load(f)
            except Exception:
                pass

        # 14c. 决策树012路质合缩水器 (RoadPrimeShrink)
        rps_path = os.path.join(self.proj_dir, "storage", "outputs", "road_prime_shrink", f"road_prime_shrink_{target}.json")
        if not os.path.exists(rps_path):
            rps_path = os.path.join(self.proj_dir, "storage", "outputs", "road_prime_shrink", "road_prime_shrink_latest.json")
        bundle["road_prime_shrink"] = {}
        if os.path.exists(rps_path):
            try:
                with open(rps_path, "r", encoding="utf-8") as f:
                    bundle["road_prime_shrink"] = json.load(f)
            except Exception:
                pass

        return bundle

    def render_markdown(self, b: Dict[str, Any]) -> str:
        """根据全量数据包，严格按照标准模版渲染完整 Markdown 报告"""
        target = b["target_period"]
        latest_draw = b["latest_draw"]
        l_issue = str(latest_draw.get("issue", ""))
        l_nums = sorted(list(latest_draw.get("numbers", [])))
        l_nums_str = format_nums(l_nums)

        pts = b["daily_points"]
        pts_str = format_nums(pts)

        tri_raw = b["tri_high_raw"]
        rep_high = tri_raw.get("repeat_high", [])
        edge_l = tri_raw.get("edge_high_left", [])
        edge_r = tri_raw.get("edge_high_right", [])
        cold_h = tri_raw.get("cold_high", [])

        # 1. 微信分桶：优先读 ops 主口径 (sixteen latest_summary / excel_window)
        #    folk_16_window_*.txt 是民间另一套配额口径，不得覆盖 ops 微信桶（否则会串期/串口径）。
        wechat_text = ""
        gap = EvidenceGap()

        # 1a. latest_summary.json → daily_ops_brief.wechat_bucket_lines
        summary_path = os.path.join(self.proj_dir, "storage", "cache", "sixteen_period", "latest_summary.json")
        if os.path.exists(summary_path):
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    sx_sum = json.load(f)
                if str(sx_sum.get("target_period")) == str(target):
                    brief = sx_sum.get("daily_ops_brief") or {}
                    lines = list(brief.get("wechat_bucket_lines") or [])
                    # 去掉「出窗同源…」附行，正文只保留 8+/7/…/0 分桶行
                    bucket_lines = [ln for ln in lines if ln and not str(ln).startswith("出窗同源")]
                    if bucket_lines:
                        wechat_text = "\n".join(bucket_lines).strip()
            except Exception:
                pass

        # 1b. excel_window markdown 代码块
        if not wechat_text:
            sixteen_md_path = os.path.join(self.proj_dir, "storage", "reports", f"sixteen_excel_window_{target}.md")
            if not os.path.exists(sixteen_md_path):
                sixteen_md_path = os.path.join(self.proj_dir, "storage", "outputs", "reports", f"sixteen_excel_window_{target}.md")
            if not os.path.exists(sixteen_md_path):
                sixteen_md_path = os.path.join(self.proj_dir, "storage", "cache", "sixteen_period", "excel_window_latest.md")
            if os.path.exists(sixteen_md_path):
                try:
                    with open(sixteen_md_path, "r", encoding="utf-8", errors="ignore") as f:
                        s_md = f.read()
                    m_wx = re.search(r"```text\s*\n(0个8.*?0个0[^\n]*)\n```", s_md, re.S)
                    if m_wx:
                        wechat_text = m_wx.group(1).strip()
                except Exception:
                    pass

        # 1c. 内存中的 sixteen brief
        if not wechat_text:
            sx = b.get("sixteen") or {}
            brief = sx.get("daily_ops_brief") or {}
            if str(brief.get("target_period") or sx.get("target_period") or "") == str(target):
                lines = list(brief.get("wechat_bucket_lines") or [])
                bucket_lines = [ln for ln in lines if ln and not str(ln).startswith("出窗同源")]
                if bucket_lines:
                    wechat_text = "\n".join(bucket_lines).strip()
                else:
                    brief_wx = brief.get("wechat_text") or ""
                    if brief_wx:
                        wechat_text = brief_wx.strip()

        # 1d. 最后才允许 folk 旁路（并醒目标注口径，避免当成 ops 主桶）
        if not wechat_text:
            folk_txt_path = os.path.join(self.proj_dir, "storage", "stats", f"folk_16_window_{target}.txt")
            if os.path.exists(folk_txt_path):
                try:
                    with open(folk_txt_path, "r", encoding="utf-8") as f:
                        folk_body = f.read().strip()
                    if folk_body:
                        wechat_text = (
                            "【旁路·民间folk口径·非ops主桶】\n" + folk_body
                        )
                        gap.add("微信分桶原文", "ops主桶缺失，已回落 folk_16_window（口径不同，仅旁证）")
                except Exception:
                    pass

        if not wechat_text:
            wechat_text = gap.add("微信分桶原文", f"第 {target} 期分桶产物缺失")

        # 2. 顺口溜动态提取 (取不到就标无数据, 不再回落到模板号码)
        jingle_txt = b.get("jingle_raw", "")
        m_j_nums = re.search(r"触发口诀推荐码[^\n:]*[：:]\s*([0-9\s]+)", jingle_txt)
        j_rec_nums = m_j_nums.group(1).strip() if m_j_nums else _covers([], "顺口溜产物缺失")
        m_j_top3 = re.search(r"最优\s*3\s*码[：:]\s*([0-9\s]+)", jingle_txt)
        j_top3 = m_j_top3.group(1).strip() if m_j_top3 else _covers([], "顺口溜产物缺失")
        m_j_cnt = re.search(r"共触发\s*(\d+)\s*条", jingle_txt)
        j_cnt = m_j_cnt.group(1) if m_j_cnt else _covers([], "顺口溜产物缺失")
        # 理论基线必须读当期产物现算：不同期推荐码数不同，基线随之变化（1码≈25%、3码≈58%）。
        # 此处曾写死「98.4%」，与模块自己算出的值冲突，属模板常数冒充当期统计量。
        m_j_base = re.search(r"至少一中期望\s*[≈~]?\s*([0-9.]+)\s*%", jingle_txt)
        j_base = (m_j_base.group(1) + "%") if m_j_base else "未提供"

        # 点位+遗漏：该模块一直在跑、也一直在入前瞻账，但报告模板里从来没有它的章节，
        # 于是第五节"全部模块当期真实产物、无缺口"的自证是失实的。现补渲染。
        po_top3, po_top5, po_pairs = [], [], []
        po_note = "点位+遗漏产物缺失"
        try:
            _po_file = os.path.join(_PROJ_DIR, "storage", "point_omission", "latest_summary.json")
            if os.path.exists(_po_file):
                with open(_po_file, "r", encoding="utf-8") as _f:
                    _po = json.load(_f)
                if str(_po.get("period", "")).strip() == str(target).strip():
                    po_top3 = [int(x) for x in (_po.get("top3_gold") or [])]
                    po_top5 = [int(x["number"]) if isinstance(x, dict) else int(x)
                               for x in (_po.get("top5_full") or _po.get("top5") or [])]
                    po_pairs = [int(x) for x in (_po.get("five_plus_two") or [])]
                    po_note = ""
                else:
                    po_note = f"产物非当期 (period={_po.get('period')})"
        except Exception as _e:
            po_note = f"读取异常: {_e}"

        j_details = []
        for line in jingle_txt.splitlines():
            line_s = line.strip()
            if line_s.startswith("- [两号齐出]") or line_s.startswith("- [单号带出]"):
                j_details.append(line_s)
        j_detail_str = "\n".join(f"  {d}" for d in j_details[:5]) or f"  {MISSING}(顺口溜产物缺失)"

        # 2b. 顺口溜轨道二: 上期出号的实际跟随带出 (读 follow_rank 当期产物, 不写死)
        follow_lines = []
        follow_top3: List[int] = []
        fr_json = os.path.join(self.proj_dir, "storage", "outputs", "follow_rank", f"follow_rank_{target}.json")
        if os.path.exists(fr_json):
            try:
                with open(fr_json, "r", encoding="utf-8") as f:
                    fr = json.load(f)
                if str(fr.get("target_period")) == str(target):
                    follow_top3 = _num_list(fr.get("top3_gold"))[:3]
                    for item in (fr.get("ranking") or [])[:3]:
                        if not isinstance(item, dict):
                            continue
                        rate = item.get("cond_rate")
                        supp = item.get("supporter_desc") or ""
                        follow_lines.append(
                            f"  - 上期出号带出 `{item.get('num_str', item.get('number'))}`"
                            f"（条件率 {float(rate) * 100:.1f}%，Lift {float(item.get('lift', 0)):.2f}x"
                            + (f"，主要来源：{supp}" if supp else "")
                            + "）"
                        )
                else:
                    gap.add("跟随统计 (follow_rank)", f"产物目标期={fr.get('target_period') or '缺失'}，非 {target}")
            except Exception:
                pass
        else:
            gap.add("跟随统计 (follow_rank)", f"第 {target} 期产物缺失")
        j_follow_str = "\n".join(follow_lines) or f"  {MISSING}(跟随统计当期产物缺失)"

        # 3. 三维交集共识定胆系统动态提取
        cs_raw = b.get("consensus_straddle_raw", "")
        m_cs_g = re.search(r"至尊共识金胆[^\d]*(\d+)", cs_raw)
        cs_gold = m_cs_g.group(1) if m_cs_g else (
            MISSING if not self.is_active("consensus_straddle")
            else gap.add("三维交集共识 (consensus_straddle)", f"第 {target} 期报告缺失"))
        m_cs_s = re.search(r"次席共识银胆[^\d]*(\d+)", cs_raw)
        cs_silver = m_cs_s.group(1) if m_cs_s else MISSING
        m_cs_b = re.search(r"三席共识铜胆[^\d]*(\d+)", cs_raw)
        cs_bronze = m_cs_b.group(1) if m_cs_b else MISSING
        m_cs_def = re.search(r"精选\s*5\s*码钢铁防线[^\d`]*`([0-9\s]+)`", cs_raw)
        cs_defense = m_cs_def.group(1).strip() if m_cs_def else MISSING
        # 选2对冲阵容与大盘风控: 只从当期报告里逐行抽, 抽不到就不列
        # 2026-11-10 修复：原正则假设 "Top 1: 45-72" 这种行内写法，匹配不了当期报告里的
        # Markdown 表格行 `| **Top 1** | **`45-72`** |`，导致明明有 5 组却被渲染成"无数据"。
        _cs_pair_pat = re.compile(r"Top\s*\d+[^\d]{0,15}?(\d{1,2})\s*-\s*(\d{1,2})")
        cs_pairs = []
        for _l in cs_raw.splitlines():
            _m = _cs_pair_pat.search(_l)
            if _m:
                _pair = f"{int(_m.group(1)):02d}-{int(_m.group(2)):02d}"
                if _pair not in cs_pairs:
                    cs_pairs.append(_pair)
        cs_pair_block = "\n".join(f"  · `[{p}]`" for p in cs_pairs[:5]) or f"  {MISSING}(当期共识报告未列选2阵容)"
        if not cs_pairs and self.is_active("consensus_straddle"):
            gap.add("三维交集共识·选2阵容 (consensus_straddle)", f"第 {target} 期报告未匹配到 Top 选2 阵容")
        m_cs_kl = re.search(r"KL\s*散度[^\d]*([0-9.]+)", cs_raw)
        m_cs_grade = re.search(r"风控评级[^\w]*`?([A-Z]+)", cs_raw)
        cs_risk = (
            f"`{m_cs_grade.group(1)}`，KL 散度值 {m_cs_kl.group(1)}"
            if m_cs_grade and m_cs_kl else MISSING
        )

        # 4. 定金选2动态提取
        g_txt = b.get("gold_pick2_raw", "")
        m_g_g = re.search(r"核心金胆[^\d]*(\d+)", g_txt)
        pick2_gold = m_g_g.group(1) if m_g_g else gap.add("定金选2 (gold_pick2)", f"第 {target} 期产物缺失")
        m_g_h = re.search(r"热号金胆[^\d]*(\d+)", g_txt)
        pick2_hot = m_g_h.group(1) if m_g_h else MISSING
        m_g_p1 = re.search(r"Top1:\s*\[([0-9\-]+)\]", g_txt)
        pick2_top1 = m_g_p1.group(1) if m_g_p1 else MISSING
        pick2_alts = re.findall(r"\[(\d{1,2}-\d{1,2})\]", g_txt)
        pick2_alts = [a for a in pick2_alts if a.replace("-", "") != (pick2_top1 or "").replace("-", "")][:4]
        pick2_alt_str = " / ".join(f"`[{a}]`" for a in pick2_alts) or MISSING

        # 5. 未开反弹动态提取
        supp_txt = b.get("suppression_raw", "")
        m_sp_t3 = re.search(r"反弹Top3金胆[：:]\s*([0-9\-]+)", supp_txt)
        supp_top3 = m_sp_t3.group(1).replace("-", " ") if m_sp_t3 else gap.add("未开点位反弹 (point_suppression)", f"第 {target} 期产物缺失")
        m_sp_lead = re.search(r"首重反弹胆[：:]\s*(\d+)", supp_txt)
        supp_lead = m_sp_lead.group(1) if m_sp_lead else MISSING
        # 2026-11-10 修复：产物写的是 "Lift=1.03x"，原正则只认 "Lift 1.03x"，导致有数据也判无数据
        m_sp_lift = re.search(r"Lift\s*[=:：]?\s*([0-9.]+)x", supp_txt)
        supp_lift = f"{m_sp_lift.group(1)}x" if m_sp_lift else gap.add(
            "未开点位反弹·区域Lift (point_suppression)", f"第 {target} 期报告未匹配到区域 Lift")
        m_sp_lvl = re.search(r"置信等级[：:]\s*[^\n]*?(Level\s*\d)", supp_txt)
        supp_level = m_sp_lvl.group(1) if m_sp_lvl else MISSING

        # 6. 三高分析结果提取 (必须当期)
        tri_all = b.get("tri_high_analysis", {})
        tri_rec = tri_all.get("recommendations", {}) if _period_ok(tri_all, target) else {}
        if not tri_rec:
            gap.add("三高×点位 (tri_high)", f"产物目标期={_product_period(tri_all) or '缺失'}，非 {target}")
        tri_gold = tri_rec.get("resonance_gold_single")
        tri_pair = _num_list(tri_rec.get("gold_pair"))
        tri_top3 = _num_list(tri_rec.get("top3_gold"))
        tri_top5 = _num_list(tri_rec.get("top5"))
        tri_top12 = _num_list(tri_rec.get("top12"))

        # 7. 统一决策脑 (需当期)
        brain = b.get("brain", {}) if _period_ok(b.get("brain", {}), target) else {}
        # 兼容契约名(single_gold_dan/gold_pair_pick2)与实盘落盘名(gold_single/gold_pair)
        brain_gold = brain.get("gold_single", brain.get("single_gold_dan"))
        brain_pair = _num_list(brain.get("gold_pair", brain.get("gold_pair_pick2")))
        brain_top3 = _num_list(brain.get("top3_gold"))

        # 8. 心理博弈 (需当期)
        psych = b.get("psych", {}) if _period_ok(b.get("psych", {}), target) else {}
        psych_top3 = _num_list(psych.get("top3_gold"))
        psych_cold = _num_list(psych.get("top_cold_spring"))
        psych_repeat = _num_list(psych.get("top_healthy_repeats"))

        # 9. 质合尾数 (需当期)
        prime = b.get("prime", {}) if _period_ok(b.get("prime", {}), target) else {}
        prime_top3 = _num_list(prime.get("top3_gold"))

        # 10. 多维共振 (需当期)
        multi = b.get("multi_resonance", {}) if _period_ok(b.get("multi_resonance", {}), target) else {}
        multi_top5 = _num_list((multi.get("summary_takeaways") or {}).get("golden_core_5"))

        # 11. 大报引擎子模块 (只认当期留档; 与 harvester 的抽取口径保持一致)
        st = b.get("state_record") or {}
        st_ok = bool(st) and str(st.get("target_issue")) == str(target)
        dr_text = b.get("daily_report_text") or ""

        def _grab(pattern: str, take: Optional[int] = None) -> List[int]:
            m = re.search(pattern, dr_text)
            return _num_list(m.group(1))[:take] if m else []

        optimal_pick2 = _num_list(st.get("optimal_pick2"))[:2] if st_ok else []
        ai_top5 = _num_list(st.get("conf_top5"))[:5] if st_ok else []
        ai_top12 = _num_list(st.get("conf_top12"))[:12] if st_ok else []
        mrmr12 = _num_list(st.get("mrmr_top12"))[:12] if st_ok else []
        deep_blast5 = _num_list(st.get("deep_picks"))[:5] if st_ok else []
        deep_consensus = _num_list(st.get("deep_consensus"))[:4] if st_ok else []
        # 2026-11-10 修复：这两项为空时原来只渲染"无数据"，不进缺口清单，
        # 于是第五节依旧自称"无缺口"。但"为空"有两种情况，必须分开：
        #   a) 深度关联产物缺当期  → 真缺口
        #   b) 产物在、但三条爆发规则本期无交集 → 合法为空，不能算缺口
        def _deep_product_ok() -> bool:
            try:
                _p = os.path.join(get_outputs_dir(), "deep_association", f"深层关联预测_{target}.json")
                if not os.path.exists(_p):
                    return False
                with open(_p, "r", encoding="utf-8") as _f:
                    return str(json.load(_f).get("target_period", "")).strip() == str(target).strip()
            except Exception:
                return False

        _deep_ok = _deep_product_ok()
        deep_consensus_note = "本期三条爆发规则无交集（合法为空）" if _deep_ok else "无当期记录"
        if not deep_blast5 and not _deep_ok and self.is_active("deep_assoc_blast5"):
            gap.add("方案2 精选爆发 (deep_assoc_blast5)", f"第 {target} 期深度关联产物缺失")
        if not deep_consensus and not _deep_ok:
            gap.add("方案2 跨规则共识 (deep_assoc_consensus)", f"第 {target} 期深度关联产物缺失")
        trinity_top5 = _grab(r"极秘 Top 5\**\s*[：:]\s*`\[([\d,\s]+)\]`", 5)
        trinity_top12 = _grab(r"极秘 Top 12\**\s*[：:]\s*`\[([\d,\s]+)\]`", 12)
        he5 = _grab(r"最终推荐\s*\(5\s*码\)\**\s*[：:]\s*`\[([\d,\s]+)\]`", 5)

        # 12. 数据源 1×2 深层关联 (当期 json)
        ds_json = os.path.join(self.proj_dir, "storage", "outputs", "deep_association", f"深层关联预测_{target}.json")
        ds = {}
        if os.path.exists(ds_json):
            try:
                with open(ds_json, "r", encoding="utf-8") as f:
                    ds = json.load(f)
            except Exception:
                ds = {}
        ds = ds if _period_ok(ds, target) else {}
        ds_top3 = _num_list(ds.get("blast_top3") or ds.get("top3_gold") or ds.get("精选爆发最优3码"))
        ds_pair = _num_list(ds.get("best_pair") or ds.get("gold_pair"))

        # 13. 残差改错 (当期)
        ec = b.get("error_correction", {}) if _period_ok(b.get("error_correction", {}), target) else {}
        ec_top5 = _num_list(ec.get("top5_gold"))

        # 13c. 一胆拖三盾当期票面
        sp_raw = b.get("spear_raw", "")
        if not sp_raw:
            gap.add("一胆拖三盾 (spear_shield)", f"第 {target} 期战报缺失")
        m_sp = re.search(r"核心攻矛[^\d]*(\d+)", sp_raw)
        sp_gold = m_sp.group(1) if m_sp else MISSING
        m_sp_sh = re.search(r"三大守盾[^\d]*([\d、\s]+)", sp_raw)
        sp_shields = _num_list(m_sp_sh.group(1)) if m_sp_sh else []
        sp_top3 = _num_list([sp_gold] if sp_gold != MISSING else []) + sp_shields

        # 14. 16 期中热双轨 (当期)
        sx = b.get("sixteen") or {}
        ops = sx.get("daily_ops_brief") or {}
        ops = ops if str(ops.get("target_period")) == str(target) else {}
        if not ops:
            gap.add("16期中热 (sixteen)", f"产物目标期={ops.get('target_period') or '缺失'}，非 {target}")
        ops_tip3 = _num_list(ops.get("tip3"))
        m2 = ops.get("method2") or {}
        ops_m2 = _num_list(m2.get("six"))
        ops_m2_pairs = [p.get("pair_str") for p in (m2.get("pairs") or []) if isinstance(p, dict)][:3]
        rb = ops.get("rebound") or {}
        ops_rb = [rb.get("gold"), rb.get("silver"), rb.get("bronze")]
        ops_rb = [n for n in ops_rb if isinstance(n, int)]
        ops_pairs = [p.get("pair_str") for p in (ops.get("pairs") or []) if isinstance(p, dict)][:3]
        # A辅 = 微信桶频3/4/5 确定性混剪六码
        ops_a_aux = _num_list((ops.get("scoring_contrast") or {}).get("method2_six"))

        # 14b. 16 期维度交叉研究 (出现次数×剩余次数 × 尾数/012路/质合)
        #      结论取自 latest_summary.json 的 dimension_cross（与 GPUs 大屏同源），
        #      仲裁结论取自 dimension_arbitrage_latest.json（7 天缓存，避免每晚重跑 200 期）。
        dim_cross: Dict[str, Any] = {}
        dim_cross_note = ""
        try:
            _sx_path = os.path.join(self.proj_dir, "storage", "cache", "sixteen_period", "latest_summary.json")
            if os.path.exists(_sx_path):
                with open(_sx_path, "r", encoding="utf-8") as _f:
                    _sx_full = json.load(_f)
                _dc = _sx_full.get("dimension_cross") or {}
                if str(_sx_full.get("target_period")) == str(target) and _dc.get("status") == "ok":
                    dim_cross = _dc
                else:
                    dim_cross_note = f"产物目标期={_sx_full.get('target_period') or '缺失'}，非 {target}"
            else:
                dim_cross_note = "latest_summary 缺失"
        except Exception as _e:
            dim_cross_note = f"读取异常: {_e}"

        dc_quadrants: List[str] = []
        for _key, _label in (
            ("hot_short_omission", "高频短漏"),
            ("hot_long_omission", "高频长漏"),
            ("cold_short_omission", "低频短漏"),
            ("cold_long_omission", "低频长漏"),
        ):
            _q = ((dim_cross.get("cross_matrix") or {}).get("quadrants") or {}).get(_key) or {}
            _qn = _num_list(_q.get("nums"))
            dc_quadrants.append(f"{_label} {_covers(_qn, '无')}({_q.get('count', 0)}码)")
        dc_quadrants_str = " ｜ ".join(dc_quadrants) if dc_quadrants else "无交叉矩阵"

        _dp = dim_cross.get("dimension_profile") or {}
        _tail_rows = _dp.get("tail") or []
        _tail_cover = sum(1 for _t in _tail_rows if int(_t.get("count") or 0) > 0)
        _tail_hot = [str(_t["tail"]) for _t in _tail_rows if _t.get("flag") == "聚集"]
        _tail_cold = [str(_t["tail"]) for _t in _tail_rows if _t.get("flag") == "空缺"]
        _roads = _dp.get("road") or []
        _road_str = ":".join(str(int(_r.get("count") or 0)) for _r in _roads) or "无"
        _prime = _dp.get("prime") or {}
        _prime_str = (
            f"质{_prime.get('prime', {}).get('count', 0)}"
            f"/合{_prime.get('composite', {}).get('count', 0)}"
            f"/中{_prime.get('neutral', {}).get('count', 0)}"
        )
        _tail_hot_str = _covers(_tail_hot, "无聚集") if _tail_hot else "无"
        _tail_cold_str = _covers(_tail_cold, "无空缺") if _tail_cold else "无"
        dc_profile_str = (
            f"尾数覆盖 {_tail_cover}/10（聚集 {_tail_hot_str}，空缺 {_tail_cold_str}）"
            f"｜012路 {_road_str}｜{_prime_str}"
            if _tail_rows else "无维度画像"
        )

        _op = dim_cross.get("optimal_picks") or {}
        _op_picks = _num_list(_op.get("picks"))
        _op_feasible = "满足" if _op.get("feasible") else "冲突"
        _cd = _op.get("constraint_detail") or {}
        _op_road = ":".join(str(int((_cd.get("road_counts") or {}).get(str(_r), 0))) for _r in range(3))
        dc_opt_str = (
            f"`{_covers(_op_picks, '无')}`（尾数覆盖 {_cd.get('tail_coverage', 0)}/≥8，"
            f"012路 {_op_road}/6~8，质数 {_cd.get('prime_count', 0)}/4~8，约束{_op_feasible}）"
            if _op_picks else f"无约束选号{dim_cross_note and '（' + dim_cross_note + '）' or ''}"
        )

        arb: Dict[str, Any] = {}
        arb_note = ""
        try:
            from backend.modules.sixteen.dimension_cross import get_dimension_arbitrage
            from backend.modules.sixteen.sixteen_engine import load_draws_from_file
            arb = get_dimension_arbitrage(load_draws_from_file(), n_periods=200, pick_size=20, restarts=25)
            if arb.get("status") != "ok":
                arb_note = str(arb.get("message") or "仲裁失败")
        except Exception as _e:
            arb_note = f"仲裁读取异常: {_e}"

        arb_lines: List[str] = []
        for _key, _label in (
            ("momentum", "纯动量"),
            ("constrained", "动量+维度约束"),
            ("rebound", "遗漏甜区回补"),
        ):
            _tr = (arb.get("tracks") or {}).get(_key) or {}
            if not _tr:
                continue
            _sig = "✅显著" if _tr.get("significant") else "不显著"
            arb_lines.append(
                f"{_label} {_tr.get('hit_rate_pct')}%(lift {_tr.get('lift')}，p={_tr.get('p')}，{_sig})"
            )
        arb_str = " ｜ ".join(arb_lines) if arb_lines else f"无仲裁数据{arb_note and '（' + arb_note + '）' or ''}"
        arb_verdict = arb.get("verdict") or arb_note or "无仲裁结论"
        arb_meta = (
            f"样本 {arb.get('n_periods')} 期 · 口径 {arb.get('pick_size')} 码"
            if arb.get("n_periods") else ""
        )

        # 14c. 点位012压缩器 (当期)
        prc = b.get("point_road_compressor", {}) if _period_ok(b.get("point_road_compressor", {}), target) else {}
        prc_top3 = _num_list(prc.get("top3_gold"))
        prc_top5 = _num_list(prc.get("top5_picks") or prc.get("top5_recommend"))
        prc_pruned = prc.get("pruned_candidates") or prc.get("pruned_list") or []
        prc_pruned_sample = [f"{p.get('number', p.get('ball'))}({p.get('road')}路)" for p in prc_pruned[:6] if isinstance(p, dict)]
        prc_pruned_str = "、".join(prc_pruned_sample) or "无剪枝"
        prc_pairs = [f"[{p[0]:02d}-{p[1]:02d}]" if isinstance(p, (list, tuple)) and len(p) >= 2 else str(p) for p in (prc.get("gold_pairs") or prc.get("road_pairs") or [])][:3]
        prc_pairs_str = " / ".join(prc_pairs) if prc_pairs else MISSING

        # 14d. 决策树 012路 × 质合多梯度智能缩水系统 (当期)
        rps = b.get("road_prime_shrink", {}) if _period_ok(b.get("road_prime_shrink", {}), target) else {}
        rps_top3 = _num_list(rps.get("top3_gold"))
        rps_top5 = _num_list(rps.get("top5_gold"))
        rps_top20 = _num_list(rps.get("top20_core_base"))
        rps_top25 = _num_list(rps.get("top25_mid_base"))
        rps_top30 = _num_list(rps.get("top30_large_base"))
        rps_pairs_raw = rps.get("pick2_pairs") or []
        rps_pairs = [f"[{p['pair'][0]:02d}-{p['pair'][1]:02d}]" for p in rps_pairs_raw if isinstance(p, dict) and "pair" in p][:3]
        rps_pairs_str = " / ".join(rps_pairs) if rps_pairs else MISSING

        # 15. 研究舱逐模型表格 (2026-10-09 整改: 原来是写死的静态表, 每期印同样 8 行号码)
        # 2026-10-22 B6 精简整改: 7 个研究舱模型 (genetic/linear_algebra/dtw/transformer/
        # matrix_profile/tda/random_forest) 已在 module_gate 注册表判 retired —— 它们日常
        # 不产出当期票, 却在报告里每天刷 7 行「无当期产物」缺口噪声, 并虚增 BH-FDR 试验数。
        # 现改为: 退役模型不再逐行进表、不再计入缺口清单, 统一在表下用一行说明其归档状态;
        # 若某期确有当期产物 (手工 --with-research 跑过), 仍照常展示, 只是不算缺口。
        _research_retired_ids = ("genetic", "linear_algebra", "dtw", "transformer",
                                 "matrix_profile", "tda", "random_forest")
        try:
            from core.module_gate import ModuleGate
            _gate_retired = set(ModuleGate().retired_ids())
        except Exception:
            _gate_retired = set()

        _retired_shown: List[str] = []

        def _research_row(b_key: str, label: str, algo: str, hint_key: str = "",
                          gate_id: str = "") -> str:
            d = b.get(b_key) or {}
            is_retired = bool(gate_id) and (gate_id in _gate_retired or gate_id in _research_retired_ids)
            if not _period_ok(d, target):
                if is_retired:
                    # 退役模型: 无当期产物是常态, 不记缺口, 不占表行
                    _retired_shown.append(label)
                    return ""
                reason = f"产物目标期={_product_period(d) or '缺失'}，非 {target}"
                gap.add(label, reason)
                return f"| **{label}** | {algo} | `—（无当期产物）` | — |"
            t3 = _num_list(d.get("top3_gold"))
            pairs = d.get("gold_pairs") or []
            if not pairs and d.get("gold_pair"):
                pairs = [{"pair": "-".join(format_num(x) for x in _num_list(d["gold_pair"]))}]
            pair_str = "—"
            if isinstance(pairs, list) and pairs:
                p0 = pairs[0]
                if isinstance(p0, dict):
                    pair_str = f"`[{p0.get('pair', '—')}]`"
                    if isinstance(p0.get("affinity_score"), (int, float)):
                        pair_str += f" (亲和 {p0['affinity_score']})"
                else:
                    pair_str = f"`[{p0}]`"
            else:
                t5 = _num_list(d.get("top5_gold") or d.get("top5"))
                if len(t5) > 3:
                    pair_str = f"Top5 备选 `{format_nums(t5[3:], sep=' - ')}`"
            hint = ""
            if hint_key and d.get(hint_key):
                hv = d[hint_key]
                hint = f"；{str(hv)[:40]}" if not isinstance(hv, list) else ""
            return f"| **{label}** | {algo} | **`{format_nums(t3, sep=' - ')}`** | {pair_str}{hint} |"

        research_rows = [
            _research_row("brain", "统一决策脑 (unified_brain)", "80维空间物理势能第一峰值"),
            _research_row("rf", "随机森林 (random_forest)", "机器虚拟裁判团投票", gate_id="random_forest"),
            _research_row("la", "线性代数空间投影 (linear_algebra)", "协方差共振与余弦相似度", gate_id="linear_algebra"),
            _research_row("dtw", "DTW 动态时间规整 (dtw_matching)", "曲线弹性形变找历史同款", gate_id="dtw"),
            _research_row("transformer", "Transformer 全局自注意力", "深度神经网络注意力机制", "attention_highlights", gate_id="transformer"),
            _research_row("mp", "Matrix Profile 矩阵轮廓", "毫秒级海量历史切片查重", "top_motifs", gate_id="matrix_profile"),
            _research_row("tda", "TDA 拓扑数据分析 (tda_engine)", "洞察号码云团的高维形状", "attractor_issues", gate_id="tda"),
        ]
        research_rows = [r for r in research_rows if r]

        # 遗传算法只有 markdown 研报, 没有 json; 从当期研报正文抽 (抽不到即标无数据)
        # B6 整改: 已退役 —— 无当期研报属常态, 不再记缺口清单。
        gen_raw = b.get("genetic_raw", "")
        if gen_raw:
            m_gen_p = re.search(r"黄金搭档选2[^\n]*?`([0-9]{1,2}\s+[0-9]{1,2})`", gen_raw)
            m_gen_rank = re.findall(r"第\s*0?[1-3]\s*名\s*\|\s*\*\*(\d+)\*\*", gen_raw)
            gen_t3 = _num_list(m_gen_rank) or _num_list(gen_raw.split("\n")[0:0])
            gen_pair = _num_list(m_gen_p.group(1)) if m_gen_p else []
            if gen_t3 or gen_pair:
                _pair_txt = f"`[{format_nums(gen_pair, sep='-')}]`" if len(gen_pair) >= 2 else "—"
                research_rows.insert(1, f"| **遗传算法 (genetic_algorithm)** | 电脑模拟染色体交叉进化 | **`{format_nums(gen_t3, sep=' - ')}`** | 选2：{_pair_txt} |")
            else:
                _retired_shown.append("遗传算法 (genetic_algorithm)")
        else:
            _retired_shown.append("遗传算法 (genetic_algorithm)")

        if not research_rows:
            research_rows = ["| **—（本期 research 舱无在册现役模型产出）** | — | `—` | — |"]

        research_table = "\n".join(research_rows)
        _retired_note = ""
        if _retired_shown:
            _retired_note = (
                "\n> 🗄️ **已退役归档（不再逐期展示、不计入缺口清单）**："
                + "、".join(_retired_shown)
                + "。判决依据见 `backend/config/module_vote_registry.json` 的 decree 字段："
                  "日常舱默认不跑 (需 `--with-research`)，前瞻账实测全线未跑赢随机基线，"
                  "且在册会虚增跨模块 BH-FDR 试验数、稀释真信号 q 值。"
                  "引擎代码与测试全部保留，撤销判决即可复启。\n"
            )

        # 16. 汇总票池 (2026-10-09 整改: 原汇总与"速发票面"整段写死, 与当日预测无关)
        #     现在按"各模块当期真实推荐中，有多少个模块同时点了这个号"现算, 并如实标出票数。
        lanes: Dict[str, List[int]] = {
            "16期中热 A-主": ops_tip3,
            "16期中热 方法2": ops_m2,
            "三高×点位": tri_top3 or ([tri_gold] if tri_gold else []),
            "三高 Top5": tri_top5,
            "定金选2": _num_list([pick2_gold, pick2_hot]),
            "未开反弹": _num_list(supp_top3),
            "多维共振": multi_top5,
            "残差改错": ec_top5,
            "心理博弈": psych_top3,
            "质合尾数": prime_top3,
            "顺口溜": _num_list(j_rec_nums),
            "共识定胆": _num_list(cs_defense),
            "Trinity": trinity_top5,
            "HiddenEnergy5": he5,
            "数据源1×2": ds_top3,
            "方案2爆发": deep_blast5,
            "跟随统计": follow_top3,
            "一胆拖三盾": sp_top3,
            "点位012压缩": prc_top5,
        }
        lanes = {k: v for k, v in lanes.items() if v}
        vote: Dict[int, int] = {}
        for _lane, nums in lanes.items():
            for n in set(nums):
                vote[n] = vote.get(n, 0) + 1
        ranked_all = sorted(vote.items(), key=lambda kv: (-kv[1], kv[0]))
        consensus_top = [n for n, c in ranked_all if c >= 2]
        if not ranked_all:
            gap.add("全系统汇总票池", "当期无任何模块产出可用推荐")
        n_lane = len(lanes)
        gold_line = (
            " ｜ ".join(f"{format_num(n)} ({c}票)" for n, c in ranked_all[:2])
            if ranked_all else MISSING
        )

        # 16b. 30 码黄金大底 (成员=被回测算法; 票池/点位仅展示排序, 见引擎 2026-10-12 整改)
        tb_res = None
        if str(target).isdigit():
            try:
                from backend.modules.spear_shield_portfolio.thirty_ball_engine import generate_thirty_ball_portfolio
                tb_res = generate_thirty_ball_portfolio(int(target), lanes_vote=vote, daily_points=pts)
            except Exception as _tb_err:
                tb_res = None
                gap.add("三十码大底", f"生成失败: {_tb_err}")
        else:
            gap.add("三十码大底", f"目标期号异常: {target}")
        tb_evidence_line = _thirty_ball_evidence_line(l_issue, gap)

        summary_block = f"""══════════════════════════════════════════════════════════════════════════
               🎯 快乐8 第 {target} 期 全系统汇总 (按模块票数现算, 共 {n_lane} 路有票)
══════════════════════════════════════════════════════════════════════════
【票王 (2票及以上)】   :  {gold_line}
【多模块共识梯队】     :  {_covers(consensus_top[:10], "当期无 2 票以上共识号")}
【最优3码 (票数前3)】  :  {_covers([n for n, _ in ranked_all[:3]], "无")}
【精选5码 (票数前5)】  :  {_covers([n for n, _ in ranked_all[:5]], "无")}
【十全防线 (票数前10)】:  {_covers([n for n, _ in ranked_all[:10]], "无")}
──────────────────────────────────────────────────────────────────────────
【16期中热 A-主 tip3】 :  {_covers(ops_tip3, "无")}
【三高×点位 首选号】     :  {format_num(tri_gold) if tri_gold else MISSING}
【定金选2 搭档】       :  {f'[{pick2_top1}]' if pick2_top1 != MISSING else MISSING}
【选2 票池首选】       :  {_covers(consensus_top[:2], "无 2 票以上共识号")}
──────────────────────────────────────────────────────────────────────────
【30码黄金大底 (冲11+)】:  {_covers(tb_res.picks if tb_res else [], "三十码大底未产出")}
══════════════════════════════════════════════════════════════════════════"""

        quick_block = f"""【第 {target} 期 快乐8 实战速发票面 (全系统汇总现算)】
👑 模块票数前3：{_covers([n for n, _ in ranked_all[:3]], "无")}
💎 选2候选（2票以上共识号两两配对，需自行取舍）：
   - {_covers(consensus_top[:2], "无 2 票以上共识号")}
🛡️ 精选5码：{_covers([n for n, _ in ranked_all[:5]], "无")}
🎯 30码黄金大底 (冲11+特供)：
   {_covers(tb_res.picks if tb_res else [], "三十码大底未产出")}
🛡️ 各模块口径不同、票数≠概率；本期系统统计信标见文末缺口与风险清单，未过显著门槛者不建议加注。"""

        gap_block = gap.render()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 退役标注：活跃模块是空串，模板里直接插值；退役模块则给出明确判决说明，
        # 避免读者把「已退役、不出当期号」误读成「产物缺失的数据故障」。
        note_jingle = self.retired_note("formula_jingle")
        note_straddle = self.retired_note("consensus_straddle")
        note_ec = self.retired_note("error_correction")

        # ── 概率事实区块 ──
        # 纯组合数学，与任何模块的推荐无关，也不依赖历史数据。
        # 放在报告最前面，是因为读者最容易忽略的恰恰是这件事：
        # 下面所有模块的号码，命中分布与随手乱选完全一致。
        def _fmt_prob(p: float) -> str:
            """概率的人类可读写法。

            极小概率（如选10 全中 ≈ 1.1e-7）用两位小数会印成 0.0000%，
            读者看到的不是「很小」而是「没有」——那是错误信息。
            低于 0.01% 时补一个「约 1/N」，让量级可感。
            """
            if p <= 0:
                return "0%"
            pct = p * 100
            if pct >= 1:
                return f"{pct:.2f}%"
            if pct >= 0.01:
                return f"{pct:.3f}%"
            return f"{pct:.6f}%（约 1/{1 / p:,.0f}）"

        _prob_rows = "\n".join(
            f"| 选{k} | {prob.expected_hits(k):.2f} 码 | {_fmt_prob(prob.all_match_prob(k))} |"
            for k in (1, 2, 3, 5, 10)
        )
        prob_facts = f"""## ⚠️ 概率事实（读之前请先看这一段）

快乐8 每期从 80 个号码中开出 20 个，**每个号码被开出的概率恒为 25%，各期相互独立**。
对任意固定的 k 个号码，命中数服从超几何分布，也就是说：

> **选哪 k 个号码，都不会改变下面这张表里的任何一个数字。**

| 玩法 | 期望命中 | 全中概率 |
| :--- | ---: | ---: |
{_prob_rows}

30 码大底：期望命中 **{prob.expected_hits(30):.2f} 码**，命中 ≥11 码的概率 **{prob.prob_at_least(30, 11) * 100:.2f}%**（红利档位）。

**本报告中的模块推荐、命中率、Lift，都是对历史产出的如实记录，不构成「未来会开」的证据。**
全系统前瞻账池化实测约 0.98x，与随机基线无统计差异，且没有任何模块通过 BH-FDR 多重检验。
请把它当作选号参考与历史档案，而不是下注依据。"""

        doc = f"""# 快乐8 全模块独立预测明细 + 全系统汇总标准研报 (目标期 {target})

> 📅 **生成时间**：{now_str} ｜ **开奖基准**：第 `{l_issue}` 期 ｜ **执行引擎**：标准全模块推演引擎 v1.0
> ⚖️ **设计规范**：每个模块独立预测逐条详细展开，全系统汇总提炼核心投资组合，文末附带一键可复制纯文本。

---

{prob_facts}

{self.budget_facts()}

---

## 〇、本次录入的数据源与基准特征档案

- **最新已开基准期**：`{l_issue}` 期
- **官方实际开出 20 码**：
  `{l_nums_str}`
- **💎 每日输入点位（{len(pts)}码）**：
  `{_covers(pts, "第 " + str(target) + " 期点位未录入")}`
- **🔁 快8上期开奖号码·重复高概率（{len(rep_high)}码）**：
  `{_covers(_num_list(rep_high), "第 " + str(target) + " 期三高未录入")}`
- **📐 快8上期开奖号码·边码高概率（{len(edge_l) + len(edge_r)}码，左右双翼）**：
  - **左翼（上期号 - 1）**：`{_covers(_num_list(edge_l), "第 " + str(target) + " 期三高未录入")}`
  - **右翼（上期号 + 1）**：`{_covers(_num_list(edge_r), "第 " + str(target) + " 期三高未录入")}`
- **❄️ 快8下期重点关注指标·冷号高概率（{len(cold_h)}码）**：
  `{_covers(_num_list(cold_h), "第 " + str(target) + " 期三高未录入")}`

---

## 一、daily 日常舱 · 核心预测模块逐项详细输出

### 1. 📜 顺口溜口诀规律与组合带出 (formula_jingle) —— 【双轨全息展开】
{note_jingle}

> **操盘手大白话说明**：顺口溜绝不仅仅是背口诀，本系统采用**双引擎驱动**：
> - **第一轨（基于规则库 Rule-Based）**：90 条经过多重统计检验与样本外检验的固定精英规则；
> - **第二轨（基于历史大数据关联 Data-Driven）**：根据上期 20 码在历史大数据中的实际带出频次、条件共现概率计算的纯数据引力。

#### 🔹 轨道一：基于 90 条精英口诀规则库
- **触发口诀数**：今日触发 `{j_cnt}` 条精英口诀（至少一中理论期望 {j_base}，取自当期顺口溜产物）
- **核心触发口诀明细（前5条）**：
{j_detail_str}
- **规则推荐码（共{len(j_rec_nums.split())}码）**：**`{j_rec_nums}`** ｜ **最优 3 码：`{j_top3}`**

#### 🔹 轨道二：基于历史大数据跟随与引力带出
- **上期出号实际跟随 Top3（读 follow_rank 当期产物，非模板）**：
{j_follow_str}

---

### 2. 🧬 三维交集共识定胆系统与选2冷热对冲 (consensus_straddle)
{note_straddle}

> **操盘手大白话说明**：三个裁判（16窗中热冠军底座、三高点位共振、冷热对冲配对）同时举手才算数！拒绝单兵作战，专打胜率对冲。

- 👑 **共识第一首选号**：**`{cs_gold}`**
- 🥈 **次席共识银胆**：**`{cs_silver}`** ｜ 🥉 **三席共识铜胆**：**`{cs_bronze}`**
- 🛡️ **精选 5 码钢铁防线**：**`{cs_defense}`**
- 💎 **选2冷热对冲阵容（当期报告原样摘录）**：
{cs_pair_block}
- 🛑 **大盘风控评级**：{cs_risk}

---

### 3. 🎯 16 期中热与双轨 4 法推演 (sixteen)

> **操盘手大白话说明**：过去 16 期开出 3~6 次的中热活跃号是出号主阵地。

- **【A-主 · 算法死答案 (ops tip3)】**：最优3码 **`{_covers(ops_tip3, "16期产物缺失")}`** ｜ 回补金银铜：`{_covers(ops_rb, "无")}` ｜ 选2：`{' / '.join(ops_pairs) or MISSING}`
- **【A-辅 · 微信桶频3/4/5 确定性混剪六码】**：**`{_covers(ops_a_aux, "16期产物缺失")}`**
- **【B-主 · 方法2 主核 (辅轨·不替换 A-主)】**：**`{_covers(ops_m2, "16期产物缺失")}`** ｜ 选2：**`{' / '.join(ops_m2_pairs) or MISSING}`**
- **【C · 维度交叉研究 (出现次数×剩余次数 × 尾数/012路/质合)】**
  - **结构象限**：{dc_quadrants_str}
  - **中热池维度画像**：{dc_profile_str}
  - **动量+维度硬约束最优 20 码**：{dc_opt_str}
  - **三轨样本外仲裁**（{arb_meta}）：{arb_str}
  - **仲裁判词**：{arb_verdict}

---

### 4. 🧬 三高特征 × 每日点位 深度共振引擎 (tri_high)

- 👑 **共振突击首选号**：**`{format_num(tri_gold) if tri_gold else MISSING}`**
- 🤝 **黄金选2搭档**：**`{f"{format_num(tri_pair[0])} - {format_num(tri_pair[1])}" if len(tri_pair) >= 2 else MISSING}`**
- 🌟 **最优 3 码**：**`{_covers(tri_top3, "三高产物缺失")}`**
- 🎯 **突击 Top 5**：`{_covers(tri_top5, "三高产物缺失")}`
- 🛡️ **Top 12 梯队**：`{_covers(tri_top12, "三高产物缺失")}`

---

### 5. 💎 定金选2决策推演 (gold_pick2)

- 💎 **核心首选号**：`{pick2_gold}`
- 🥇 **动能热胆**：`{pick2_hot}`
- 👑 **核心选2搭档**：**`[{pick2_top1}]`**
- 备选搭档梯队：{pick2_alt_str}

---

### 6. 🪞 未开点位高压反弹与空间追踪 (point_suppression)

- **置信等级**：`{supp_level}` ｜ **区域 Lift**：`{supp_lift}`
- **首重绝杀反弹胆**：**`{supp_lead}`**
- **反弹 Top 3 首选号**：**`{supp_top3}`**

---

### 7. 🔗 数据源 1 × 2 矩阵深层关联 (datasource)

- **精选爆发最优 3 码**：`{_covers(ds_top3, "数据源当期产物缺失")}`
- **黄金连体婴选2搭档**：`{f'[{ds_pair[0]} - {ds_pair[1]}]' if len(ds_pair) >= 2 else MISSING}`

---

### 8. 🛡️ 三维一体极秘推荐 (Trinity Fusion) 与 Hidden Energy 5

- **极秘 Top 5**：`{_covers(trinity_top5, "大报引擎未产出当期记录")}`
- **极秘 Top 12**：`{_covers(trinity_top12, "大报引擎未产出当期记录")}`
- **首席特供 · Hidden Energy 5**：**`{_covers(he5, "大报引擎未产出当期记录")}`**
- **极简选2 黄金搭档**：`{f'[{optimal_pick2[0]} - {optimal_pick2[1]}]' if len(optimal_pick2) >= 2 else MISSING}`
- **传统AI 对照 Top5 / Top12**：`{_covers(ai_top5, "无当期记录")}` / `{_covers(ai_top12, "无当期记录")}`
- **熵控优化 mRMR Top 12**：`{_covers(mrmr12, "无当期记录")}`
- **方案2 精选爆发 Top5 / 跨规则共识**：`{_covers(deep_blast5, "无当期记录")}` / `{_covers(deep_consensus, deep_consensus_note)}`

---

### 9. 🧠 心理博弈论与逆向均值回归 (psychological_game)

- **Top 3 逆向首选号**：**`{_covers(psych_top3, "心理博弈产物非当期")}`**
- **绝望点报复性回补冷门**：`{_covers(psych_cold, "无")}`
- **单点健康重号**：`{_covers(psych_repeat, "无")}`

---

### 10. 🔢 质合尾数香农熵三大协同推演 (prime_composite)

- **Top 3 首选号**：**`{_covers(prime_top3, "质合产物非当期")}`**（质数反弹前锋）

---

### 11. 🌟 多维共振专家表决 (multi_resonance)

- **共识首选号 Top 5**：**`{_covers(multi_top5, "多维共振产物非当期")}`**

---

### 12. 🧬 残差改错与错题纠偏 (error_correction)
{note_ec}

- **AI 改错裁判纠偏 Top 5**：`{_covers(ec_top5, "残差改错产物非当期")}`

---

### 13. 🎯 一胆拖三盾 · 选2组合拳 (spear_shield)

- **核心攻矛**：**`{sp_gold}`** ｜ **三大守盾**：`{_covers(sp_shields, "守盾未产出")}`

---

### 14. 🧭 点位012偏态压缩器 (point_road_compressor) —— 【点位锚定 + 半径扩张 + 偏态剪枝】

> **操盘手大白话说明**：以今日 20 个点位为绝对重心锚点，向外扩散正负 2 划定热力半径，并根据全盘 012 路饱和偏态与局部拥挤度精准剪枝剔除，打造最高纯度的首选组合。

- 🎯 **最优 3 码**：**`{_covers(prc_top3, "点位压缩器产物缺失")}`**
- 🛡️ **精选 5 码**：`{_covers(prc_top5, "点位压缩器产物缺失")}`
- ✂️ **偏态剪枝过滤（典型防守样本）**：`{prc_pruned_str}`
- 🤝 **012跨路对冲选2搭档**：`{prc_pairs_str}`

---

### 15. 🌲 决策树 012路 × 质合多梯度智能缩水系统 (road_prime_shrink / TPRD v2.0) —— 【AI 海选团 + 规则透视 + 多梯度矩阵】

> **操盘手大白话说明**：利用决策树提取最管用的出号规则，配合 50 棵随机森林（AI 海选团）对 80 码逐一打分，并引入 100 期共现亲和矩阵加权，实现高共现选2搭档与 20/25/30 码三级金字塔式正交缩水！

- 🎯 **突击首选号 Top 3**：**`{_covers(rps_top3, "决策树缩水器产物缺失")}`**
- 🛡️ **主力精选 Top 5**：`{_covers(rps_top5, "决策树缩水器产物缺失")}`
- 🤝 **跨路对冲黄金选 2 搭档**：`{rps_pairs_str}`
- 🔥 **20 码极致实战主力池**：`{format_nums(rps_top20)}`
- 🎯 **25 码梯度精选中底**：`{format_nums(rps_top25)}`
- 🛡️ **30 码黄金守卫大底**：`{format_nums(rps_top30)}`

---

### 16. 🎯 点位 + 遗漏号深度推演 (point_omission)

> **操盘手大白话说明**：以今日 20 个点位为底仓，叠加 7 维特征（热度/遗漏反弹/集群/周期/共现/马尔可夫/熵）打分，挑出点位里最可能开的号。

- 🎯 **Top 3 首选号**：**`{_covers(po_top3, po_note or "无")}`**
- 🛡️ **Top 5 精选**：`{_covers(po_top5, po_note or "无")}`
- 🤝 **5+2 组合**：`{_covers(po_pairs, po_note or "无")}`

---

## 二、research 研究舱 · 各前沿模型独立预测明细

| 模块名称 | 算法核心（大白话） | 核心首选号 Top 3 | 选2搭档 / 特征亮点 |
| :--- | :--- | :---: | :--- |
{research_table}
{_retired_note}
> 说明：上表逐行读取各研究舱模型**当期**产物文件并核对目标期号；产物非当期者一律标注「无当期产物」，不再用模板号码顶替。

---

## 三、📱 微信分桶原文（一键直接复制发群）

```text
{wechat_text}
```

---

## 四、🏆 全系统汇总：核心号码梯队与终审实战总账单

```text
{summary_block}
```

### 🎯 30 码黄金实战大底阵容 (冲 11+ 码特供)

{tb_evidence_line}

```text
{tb_res.quick_copy_text if tb_res else "（三十码大底未产出，见缺口清单）"}
```

---

## 五、🧾 当期产物缺口清单（数据诚信自证）

> 以下模块**本次没有产出当期可用产物**，报告中对应位置一律显示「无数据」，不会用历史或模板号码顶替。补齐后可重跑本报告。

{gap_block}

---

## 附录：操盘速查一键复制文本块 (可直接发群)

```text
{quick_block}
```
"""

        # 在每个模块小节标题下补一行「理论期望 vs 历史实测」。
        # 用后处理而不是逐个改模板：小节有 16 个，模板里逐个插容易漏、也难维护；
        # 标题格式统一为 `### N. 名称 (module_id)`，一处正则即可全覆盖。
        def _inject_stat(m: "re.Match") -> str:
            mid = self._SECTION_MODULE_IDS.get(m.group(2))
            if not mid:
                return m.group(1)
            line = self.module_stat_line(mid)
            return m.group(1) + (line + "\n" if line else "")

        doc = re.sub(
            r"^(###\s+(\d+)\.[^\n]*\n)",
            _inject_stat,
            doc,
            flags=re.M,
        )
        return doc

    def generate_and_save(self, target_period: Optional[str] = None) -> Dict[str, str]:
        """执行生成、渲染并双落盘"""
        data_bundle = self.gather_all_data(target_period)
        target = data_bundle["target_period"]
        md_content = self.render_markdown(data_bundle)

        reports_dir = os.path.join(self.proj_dir, "storage", "reports")
        os.makedirs(reports_dir, exist_ok=True)

        target_file = os.path.join(reports_dir, f"全模块预测明细_{target}.md")
        latest_file = os.path.join(reports_dir, "全模块预测明细_latest.md")

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        with open(latest_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        # 选1~选10 实战梯队：必须排在正文落盘之后 —— 该模块要回读本期报告，
        # 从正文各模块的推荐池里提炼梯队；正文不存在时它拿不到任何候选。
        try:
            from backend.modules.battle_rank_optimizer.service import BattleRankService
            section = BattleRankService().execute_auto_pipeline(int(target))
            if section and section.strip():
                md_content = md_content.rstrip() + "\n\n---\n\n" + section.strip() + "\n"
                for _p in (target_file, latest_file):
                    with open(_p, "w", encoding="utf-8") as f:
                        f.write(md_content)
        except Exception as e:
            print(f"[警告] 选1至选10 梯队生成跳过: {e}")

        # 触发收割器将全量预测数据封存入追加式前瞻账本
        try:
            from backend.modules.daily_review.harvester import harvest
            harvest(str(target))
        except Exception as e:
            print(f"[警告] 收割器执行提示: {e}")

        return {
            "target_file": target_file,
            "latest_file": latest_file,
            "size": str(len(md_content.encode("utf-8"))),
            "target_period": target,
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="快乐8 全模块量化预测标准模版与终极研报生成引擎")
    parser.add_argument("--period", "-p", type=str, default=None, help="目标期号 (默认自动推断下一期)")
    args = parser.parse_args()

    engine = StandardDailyReportEngine()
    res = engine.generate_and_save(args.period)
    print(f"✅ 标准全模块研报已成功生成！")
    print(f"   • 目标期号: {res['target_period']}")
    print(f"   • 文件路径: {res['target_file']} ({res['size']} bytes)")
    print(f"   • 镜像快照: {res['latest_file']}")


if __name__ == "__main__":
    main()
