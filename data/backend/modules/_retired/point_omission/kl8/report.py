# -*- coding: utf-8 -*-
"""Markdown 日报与 stdout 摘要（§7）。

**合规红线（§11.5）**：报告内不得出现任何投注相关表述。渲染完成后会调用
`assert_compliant()` 做一次全文扫描，命中违禁词直接抛错——宁可不出报告，
也不输出越界内容。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path

from .contracts import ModuleResult
from .data_io import PointEntry
from .ensemble import DIM_NAMES, FusionResult, MAIN_METHODS
from .numerics import safe_div
from .points import NumberStats
from .scoring import Pick52, Selection, zone_label, zone_of
from .stats_tests import render_power_table

DISCLAIMER = (
    "本报告由统计模型自动生成，**不构成任何投注建议**。快乐8 每期开奖为独立随机事件，"
    "历史统计特征不保证在未来重现。全部结论均附带显著性检验结果，"
    "未达显著的方法已在文中标注；请将本报告视为数据观察工具而非预测工具。"
)

# 违禁词：投注与资金管理相关表述（§11.5）
FORBIDDEN = (
    "单式", "复式", "胆拖", "合买", "倍投", "追号", "加倍", "翻倍",
    "止损", "止盈", "守号", "投注", "下注", "购买", "买彩票", "中奖",
    "必中", "稳赚", "包号", "杀号",
    "保证收益", "稳赢", "回本",
)


# 允许出现的否定式表述：这些短语本身含违禁词，但语义是否定建议，
# 属于合规要求必须写出的内容。扫描前先整体剥离，避免误杀。
SAFE_NEGATIONS = (
    "不构成任何投注建议", "不构成投注建议",
    "不构成任何博彩建议", "不构成博彩建议",
    "不构成购买建议", "非投注建议",
)


def assert_compliant(text: str) -> None:
    """全文扫描违禁词。命中即抛错，阻止报告落盘。

    免责声明与风险提示必须写出"不构成投注建议"一类的否定式表述，
    因此在扫描前先把 `SAFE_NEGATIONS` 中的否定短语整体剥离，
    剩下的正文里只要还出现任何违禁词就判定越界。
    """
    body = text
    for phrase in SAFE_NEGATIONS:
        body = body.replace(phrase, "")
    hits = sorted({w for w in FORBIDDEN if w in body})
    if hits:
        raise ValueError(f"报告含违规表述，已阻止输出：{hits}")


# ── 上下文 ────────────────────────────────────────────────────

@dataclass
class ReportContext:
    cfg: object
    target: object                       # points_input.TargetInfo
    entry: PointEntry
    dataset: object                      # source.Dataset
    health: object                       # source.HealthReport
    staleness: str = ""
    results: dict[str, ModuleResult] = field(default_factory=dict)
    fusion: FusionResult | None = None
    selection: Selection | None = None
    picks: Pick52 | None = None
    base_stats: dict[int, NumberStats] = field(default_factory=dict)
    expanded: set[int] = field(default_factory=set)
    backtest: object | None = None       # replay.BacktestResult
    degradation_reasons: list[str] = field(default_factory=list)
    module_notes: list[str] = field(default_factory=list)
    reconcile_note: str = ""            # §8.5 共享档案对账告警
    generated_at: _date | None = None

    @property
    def degraded(self) -> bool:
        return bool(self.backtest and getattr(self.backtest, "degraded", False))


# ── 一句话结论（stdout 与 md 共用，§7.0）──────────────────────

def _fmt_nums(nums, width: int = 2) -> str:
    return " ".join(f"{n:0{width}d}" for n in nums)


def _strength(v: float) -> str:
    """按集中式阈值把 [0,1] 映射为强/中/弱（§3.4）。"""
    if v >= 0.70:
        return "强"
    if v >= 0.40:
        return "中"
    return "弱"


def _dominant_direction(ctx: ReportContext, n: int) -> str:
    """给一个号挑出最强的两三个维度，用于生成"来自哪个方向"的描述。"""
    if ctx.fusion is None:
        return ""
    vals = sorted(((dim, vec.get(n, 0.0)) for dim, vec in ctx.fusion.h_values.items()),
                  key=lambda kv: -kv[1])[:2]
    return "、".join(f"{DIM_NAMES.get(d, d)}" for d, v in vals if v > 0.35)


def conclusion_line(ctx: ReportContext) -> str:
    """一句话结论。降级时强制切换为警示口径（§9.8）。"""
    core = (ctx.selection.core if ctx.selection else [])
    if ctx.degraded:
        return ("⚠️ **本期一句话结论**：全部方法未通过随机基线检验，"
                "以下推荐与随机选取**无统计差异**，仅供观察。")

    if not core:
        return "**本期一句话结论**：候选池不足，本期无法给出核心号码。"

    dirs = [_dominant_direction(ctx, n) for n in core]
    dirs = [d for d in dirs if d]
    lead = dirs[0] if dirs else "综合分"

    top1 = max(core, key=lambda n: (ctx.fusion.composite.get(n, 0.0) if ctx.fusion else 0))
    strong = [n for n in core
              if ctx.fusion and ctx.fusion.composite.get(n, 0.0) >= 70.0]

    parts = [f"Top5 中最高分为 {top1:02d}（{dirs[0] if dirs else '综合'}方向）"]
    if strong:
        parts.append(f"其中 {len(strong)} 个号综合分 ≥ 70")
    if ctx.backtest and ctx.backtest.T:
        st = ctx.backtest.system_test
        if st:
            parts.append(f"近 {st.T} 期回测 lift={st.lift:.3f}（{st.verdict}）")
    parts.append(f"数据新鲜度{'正常' if '✅' in ctx.staleness else '需注意'}"
                 f"（{ctx.staleness.split('（')[-1].rstrip('）') if ctx.staleness else '—'}）")
    return "**本期一句话结论**：" + "；".join(parts) + "。"


# ── 各章节 ────────────────────────────────────────────────────

def _narrative(ctx: ReportContext, section: str) -> list[str]:
    """收集全部模块投递到该章节的 narrative（按 order 排序）。"""
    out: list[tuple[int, str, str]] = []
    for name, res in ctx.results.items():
        for blk in (res.narrative or []):
            if blk.section == section:
                out.append((blk.order, name, blk.text))
    out.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in out]


def _sec_overview(ctx: ReportContext) -> list[str]:
    h = ctx.health
    L = ["## 〇、输入概览", ""]
    L.append(f"- 目标期号：**{ctx.target.period_str}**（{ctx.target.date}）")
    L.append(f"- 核心点位（{len(ctx.entry.points)}）：`{_fmt_nums(ctx.entry.points)}`")
    extra = sorted(ctx.expanded - set(ctx.entry.points))
    L.append(f"- 拓展集合（{len(ctx.expanded)}）：点位原号 {len(ctx.entry.points)} 个，"
             f"循环三元组新增 {len(extra)} 个")
    if extra:
        L.append(f"  - 新增号：`{_fmt_nums(extra)}`")
    L.append(f"- **数据体检**：点位 {h.points_count} 期 / 开奖 {h.draws_count} 期 / "
             f"**有效配对 {h.pairable_count} 期** / 畸形 {h.malformed} 条")
    if h.dirty:
        L.append(f"  - 语义脏记录：{_fmt_nums(h.dirty, 7)}（点位与开奖日期不一致，已剔除配对）")
    if h.points_only:
        L.append(f"  - 点位有、开奖无：{_fmt_nums(h.points_only, 7)}")
    if h.duplicate_dates:
        L.append(f"  - 同日期多期：{h.duplicate_dates}")
    if h.inversions:
        L.append(f"  - 日期倒挂：{_fmt_nums(h.inversions, 7)}")
    if ctx.staleness:
        L.append(f"- **数据新鲜度**：{ctx.staleness}")
    L.append(f"- 数据来源：点位 `{h.points_source}` / 开奖 `{h.draws_source}`")
    if ctx.reconcile_note:
        L.append(f"- ⚠️ **对账告警**：{ctx.reconcile_note}")
    if ctx.module_notes:
        L.append("- **本次运行未启用的模块**：")
        L.extend(f"  - {m}" for m in ctx.module_notes)
    L.append("")

    # 基础统计表（仅拓展集合）
    L.append("<details><summary>基础统计表（拓展集合内各号）</summary>")
    L.append("")
    L.append("| 号 | 近10期命中 | 近3期命中 | 当前连失 | 全档频次 | 期望命中 | z |")
    L.append("|---|---|---|---|---|---|---|")
    for n in sorted(ctx.expanded):
        bs = ctx.base_stats.get(n)
        if bs is None:
            continue
        L.append(f"| {n:02d} | {bs.hit10} | {bs.hit3} | {bs.miss} | "
                 f"{bs.freq_full} | {bs.exp_hit:.1f} | {bs.z_score:+.2f} |")
    L.append("")
    L.append("</details>")
    L.append("")
    L.extend(_narrative(ctx, "overview"))
    return L


def _sec_dashboard(ctx: ReportContext) -> list[str]:
    L = ["## 一、N 维评分仪表盘", ""]
    if ctx.fusion is None:
        L.append("_融合层未执行，仪表盘不可用。_")
        return L

    L.append("### 1.1 Top 5 维度分解")
    L.append("")
    dims = list(DIM_NAMES)
    L.append("| 号 | " + " | ".join(f"{d} {DIM_NAMES[d]}" for d in dims) +
             " | 综合分 | 主导维度 |")
    L.append("|---" * (len(dims) + 3) + "|")
    for n in (ctx.selection.core if ctx.selection else []):
        cells = []
        for d in dims:
            v = ctx.fusion.h_values.get(d, {}).get(n, 0.0)
            cells.append(f"{v:.2f} {_strength(v)}")
        comp = ctx.fusion.composite.get(n, 0.0)
        dom, _ = ctx.fusion.dominant_dim(n)
        L.append(f"| **{n:02d}** | " + " | ".join(cells) +
                 f" | **{comp:.1f}** | {DIM_NAMES.get(dom, dom)} |")
    L.append("")

    L.append("### 1.2 方法权重")
    L.append("")
    st = getattr(ctx.backtest, "exp3", None) if ctx.backtest else None
    L.append("| 方法 | 当前权重 | 累计奖励 | 参与期数 | 状态 |")
    L.append("|---|---|---|---|---|")
    for m in MAIN_METHODS:
        res = ctx.results.get(m)
        if res is None:
            L.append(f"| {m} | — | — | — | 未启用 |")
            continue
        w = (st.weights.get(m, 0.0) if st else 1.0 / len(MAIN_METHODS))
        cr = (st.cumulative_reward.get(m, 0.0) if st else 0.0)
        pulls = (st.pulls.get(m, 0) if st else 0)
        if not res.sufficient:
            status = "已降级"
        elif w <= 0.02:
            status = "近乎停用"
        else:
            status = "正常"
        L.append(f"| {m} | {w:.4f} | {cr:+.3f} | {pulls} | {status} |")
    if st is not None and not st.active:
        L.append("")
        L.append(f"> 在线学习处于冷启动：已完成 {st.periods}/{st.warmup} 期，"
                 f"当前为等权。")
    L.append("")
    if ctx.fusion.skipped_dims:
        L.append(f"> 本维度未生效（输入模块全部缺失）："
                 f"{'、'.join(ctx.fusion.skipped_dims)}，其权重已按比例分摊。")
        L.append("")
    L.extend(_narrative(ctx, "dashboard"))
    return L


def _sec_top5(ctx: ReportContext) -> list[str]:
    L = ["## 二、本期最值得关注的 Top 5", ""]
    if not ctx.selection or not ctx.selection.core:
        L.append("_候选池不足，本期无 Top5。_")
        return L
    if ctx.selection.relaxed:
        L.append("> 多样性约束曾被放宽（详见 §5.3），Top5 中同段号较多。")
        L.append("")

    om = ctx.results.get("omission")
    for n in ctx.selection.core:
        bs = ctx.base_stats.get(n)
        comp = ctx.fusion.composite.get(n, 0.0) if ctx.fusion else 0.0
        L.append(f"### {n:02d} · 综合分 {comp:.1f}")
        L.append("")
        if bs is not None:
            heat = ("偏热" if bs.z_score > 0.5 else
                    "偏冷" if bs.z_score < -0.5 else "正常")
            L.append(f"- **热度**：近 10 期命中 {bs.hit10} 次、近 3 期 {bs.hit3} 次，"
                     f"z = {bs.z_score:+.2f}（{heat}）")
            L.append(f"- **遗漏**：当前连失 {bs.miss} 期，全档出现 {bs.freq_full} 次"
                     f"（期望 {bs.exp_hit:.1f}）")
        if om is not None and om.sufficient and om.metrics:
            tm = dict((int(a), b) for a, b in (om.metrics.get("top_miss") or []))
            if n in tm:
                L.append(f"- **遗漏结构**：位于当前连失最久的号码之列（{tm[n]} 期）")
        if ctx.fusion:
            dom, dv = ctx.fusion.dominant_dim(n)
            others = sorted(((d, v.get(n, 0.0)) for d, v in ctx.fusion.h_values.items()
                             if d != dom), key=lambda kv: -kv[1])[:2]
            detail = "、".join(f"{DIM_NAMES.get(d, d)} {v:.2f}" for d, v in others)
            L.append(f"- **定位**：主导维度 {DIM_NAMES.get(dom, dom)}（{dv:.2f}），"
                     f"次强 {detail}")
        L.append("")
    return L


def _zone_table(ctx: ReportContext) -> list[str]:
    """8 段场域能量表（从 base_stats 现算，不依赖 heatmap 模块是否可用）。"""
    rows = []
    for z in range(8):
        lo = z * 10 + 1
        nums = [n for n in range(lo, lo + 10) if n in ctx.base_stats]
        if not nums:
            continue
        hits10 = sum(ctx.base_stats[n].hit10 for n in nums)
        # 期望：10 个号 × 10 期 × 20/80
        exp10 = len(nums) * 10 * 0.25
        rows.append((zone_label(lo), hits10, exp10,
                     safe_div(hits10, exp10, 0.0)))
    if not rows:
        return []
    L = ["| 场域 | 近10期命中 | 期望 | 比值 r | 倾向 |", "|---|---|---|---|---|"]
    for label, got, exp, r in rows:
        if got == 0 and exp == 0:
            continue
        trend = "偏热" if r > 1.15 else "偏冷" if r < 0.85 else "中性"
        L.append(f"| {label} | {got} | {exp:.1f} | {r:.2f} | {trend} |")
    L.append("")
    return L


def _sec_macro(ctx: ReportContext) -> list[str]:
    L = ["## 三、宏观趋势", ""]
    L.append("### 3.1 场域能量")
    L.append("")
    zt = _zone_table(ctx)
    L.extend(zt if zt else ["_基础统计不可用。_", ""])

    if ctx.fusion:
        L.append("### 3.2 维度覆盖面")
        L.append("")
        L.append("| 维度 | 覆盖号码数（分数 > 0.5） | 最高分号 |")
        L.append("|---|---|---|")
        for d, name in DIM_NAMES.items():
            vec = ctx.fusion.h_values.get(d)
            if not vec:
                L.append(f"| {name} | 未生效 | — |")
                continue
            hi = [n for n, v in vec.items() if v > 0.5]
            best = max(vec, key=lambda n: vec[n]) if vec else None
            L.append(f"| {name} | {len(hi)} | {best:02d} |" if best else
                     f"| {name} | {len(hi)} | — |")
        L.append("")
    L.extend(_narrative(ctx, "macro"))
    return L


def _sec_risk(ctx: ReportContext) -> list[str]:
    L = ["## 四、风险预警与应对", ""]
    if ctx.fusion:
        # 拥挤：多个模块同时给高分
        crowded = []
        for n in sorted(ctx.expanded):
            vals = [r.scores.get(n, 0.0) for r in ctx.results.values()
                    if r.sufficient and r.name in MAIN_METHODS]
            if vals and sum(1 for v in vals if v >= 0.7) / len(vals) > 0.5:
                crowded.append(n)
        L.append(f"- **共识拥挤**：{len(crowded)} 个号被多数模块同时看好"
                 + (f"（`{_fmt_nums(crowded)}`）" if crowded else ""))
        # 追热衰竭
        hot = [n for n in sorted(ctx.expanded)
               if (bs := ctx.base_stats.get(n)) and bs.hit10 >= 4 and bs.miss >= 3]
        L.append(f"- **追热衰竭**：{len(hot)} 个号近 10 期命中 ≥4 次但已连失 ≥3 期"
                 + (f"（`{_fmt_nums(hot)}`）" if hot else ""))
        # 低位忽视
        low = [n for n in sorted(ctx.expanded)
               if (bs := ctx.base_stats.get(n)) and bs.z_score <= -0.5 and bs.hit10 <= 1]
        L.append(f"- **低位忽视**：{len(low)} 个号近期显著偏冷"
                 + (f"（`{_fmt_nums(low)}`）" if low else ""))
        ns = sum(1 for r in ctx.results.values() if not r.sufficient)
        L.append(f"- **数值告警**：本次运行有 {ns} 个方法处于降级状态")
    L.append("")

    if ctx.backtest and ctx.backtest.method_tests:
        L.append("### 4.1 外样本方法有效性（BH-FDR 校正后）")
        L.append("")
        L.append("| 方法 | T | 均值命中 | lift | z | q | 判定 |")
        L.append("|---|---|---|---|---|---|---|")
        for m, tr in ctx.backtest.method_tests.items():
            L.append(f"| {m} | {tr.T} | {tr.mean_hits:.4f} | {tr.lift:.4f} | "
                     f"{tr.z:+.3f} | {tr.q_value:.4f} | {tr.verdict} |")
        L.append("")
        if ctx.degraded:
            L.append("> ⚠️ **全部方法均未通过随机基线检验**。按 §9.8，所有推荐"
                     "视为与随机选取无统计差异。")
            L.append("")
        weak = [m for m, tr in ctx.backtest.method_tests.items()
                if tr.lift < 1.0 or not tr.significant]
        if weak:
            L.append(f"> 未达显著或劣于随机的方法（权重已由 Exp3 自动降低）："
                     f"{'、'.join(weak)}")
            L.append("")

    if ctx.degradation_reasons:
        L.append("### 4.2 降级原因")
        L.append("")
        L.extend(f"- {r}" for r in ctx.degradation_reasons)
        L.append("")

    L.extend(_narrative(ctx, "risk"))
    return L


def _sec_tree(ctx: ReportContext) -> list[str]:
    L = ["## 五、《趋势简报》决策树", ""]
    L.append("| 分支 | 触发条件 | 取数模块 | 本期候选 |")
    L.append("|---|---|---|---|")
    core = list(ctx.selection.core) if ctx.selection else []
    pool = sorted(ctx.expanded - set(core))
    if ctx.fusion:
        top_pool = sorted(pool, key=lambda n: -ctx.fusion.composite.get(n, 0.0))[:5]
    else:
        top_pool = pool[:5]

    hot_zone = []
    for z in range(8):
        lo = z * 10 + 1
        nums = [n for n in range(lo, lo + 10) if n in ctx.base_stats]
        if not nums:
            continue
        r = safe_div(sum(ctx.base_stats[n].hit10 for n in nums),
                     len(nums) * 10 * 0.25, 0.0)
        if r > 1.15:
            hot_zone.append(zone_label(lo))
    L.append(f"| 顺势 | 场域 r > 1.15 且主导周期显著 | heatmap + cyclic | "
             f"{'、'.join(hot_zone) if hot_zone else '无触发'} |")
    ct = ctx.results.get("contrarian")
    ct_c = (list(ct.metrics.get("gate_passed") or [])[:5]
            if ct is not None and ct.sufficient and ct.metrics else [])
    L.append(f"| 对冲 | 拥挤度 > 0.75 或熵低于低分位 | contrarian | "
             f"{_fmt_nums(ct_c) if ct_c else '无触发'} |")
    L.append(f"| 跟随 | 条件概率显著且 A 已入 Top5 | linalg_svd | "
             f"{_fmt_nums(top_pool) if top_pool else '—'} |")
    L.append(f"| 集群三元组 | 三元组成团 z 显著 | cluster + omission | "
             f"{_fmt_nums(sorted(ctx.expanded))[:60]}… |")
    adv = ctx.results.get("adversarial")
    L.append(f"| 对抗与熵校 | 候选多样性熵 < 阈值 | adversarial | "
             f"{'已执行' if adv is not None else '未启用'} |")
    L.append("")
    L.append("> 本节候选清单为**解释性附录**，与第二章 Top5、第六章 5+2 严格对齐，"
             "不产生第三份不一致的清单。")
    L.append("")
    L.extend(_narrative(ctx, "tree"))
    return L


def _reason_for(ctx: ReportContext, n: int) -> str:
    bits = []
    bs = ctx.base_stats.get(n)
    if bs:
        if bs.miss >= 5:
            bits.append(f"连失 {bs.miss} 期")
        if bs.hit10 >= 4:
            bits.append(f"近10期命中 {bs.hit10} 次")
        if abs(bs.z_score) >= 1.0:
            bits.append(f"z={bs.z_score:+.2f}")
    if ctx.fusion:
        dom, dv = ctx.fusion.dominant_dim(n)
        if dv > 0.4:
            bits.append(f"{DIM_NAMES.get(dom, dom)} {dv:.2f}")
        comp = ctx.fusion.composite.get(n, 0.0)
        bits.append(f"综合 {comp:.1f}")
    return "，".join(bits) if bits else "—"


def _sec_final(ctx: ReportContext) -> list[str]:
    L = ["## 六、终极推荐清单", ""]
    if not ctx.picks:
        L.append("_推荐层未执行。_")
        return L
    if ctx.degraded:
        L.append("> ⚠️ **降级状态**：以下清单与随机选取无统计差异，仅供观察。")
        L.append("")

    L.append("### 6.1 五码核心")
    L.append("")
    L.append("| 号 | 场域 | 关注理由 | 对抗门控 |")
    L.append("|---|---|---|---|")
    adv = ctx.results.get("adversarial")
    for n in ctx.picks.core:
        L.append(f"| **{n:02d}** | {zone_label(n)} | {_reason_for(ctx, n)} | "
                 f"{'已通过' if adv is not None else '未启用'} |")
    L.append("")

    L.append("### 6.2 两码备防")
    L.append("")
    if ctx.picks.defensive:
        L.append("| 号 | 场域 | 关注理由 |")
        L.append("|---|---|---|")
        for n in ctx.picks.defensive:
            L.append(f"| **{n:02d}** | {zone_label(n)} | {_reason_for(ctx, n)} |")
    else:
        L.append("_本期无通过门控的备防候选。_")
    L.append("")

    L.append("### 6.3 浓缩")
    L.append("")
    L.append(f"- **五码核心**：`{_fmt_nums(ctx.picks.core)}`")
    if ctx.picks.defensive:
        L.append(f"- **两码备防**：`{_fmt_nums(ctx.picks.defensive)}`")
    for note in (ctx.picks.notes or []):
        L.append(f"- _{note}_")
    L.append("")
    L.extend(_narrative(ctx, "final"))
    return L


def _sec_backtest(ctx: ReportContext) -> list[str]:
    bt = ctx.backtest
    if bt is None or not bt.T:
        return ["## 附录 A、回测", "", "_本次未执行回测。_", ""]
    L = ["## 附录 A、滚动外样本回测", ""]
    skip_parts = []
    warmup_skips = bt.skipped - getattr(bt, "missing_points", 0)
    if warmup_skips:
        skip_parts.append(f"历史不足预热 {warmup_skips} 期")
    if getattr(bt, "missing_points", 0):
        skip_parts.append(f"遗漏期（有开奖无点位）{bt.missing_points} 期")
    L.append(f"- 窗口：{bt.window_label}，有效样本 **T = {bt.T}** 期"
             + (f"，跳过 {bt.skipped} 期（{'；'.join(skip_parts)}）" if skip_parts else ""))
    L.append(f"- 三条纪律：严格小于（只用 period < P 的历史）／每期重算／配置冻结")
    L.append(f"- 耗时：{bt.elapsed_sec:.1f} 秒")
    L.append("")

    L.append("### A.1 系统表现")
    L.append("")
    if bt.system_test:
        st = bt.system_test
        L.append(f"- 平均命中 **{st.mean_hits:.4f}**（随机期望 {st.expected:.4f}），"
                 f"**lift = {st.lift:.4f}**")
        L.append(f"- z = {st.z:+.3f}，p = {st.p_value:.4f}，判定：**{st.verdict}**")
    L.append("")
    if bt.baselines:
        L.append("### A.2 基线对照")
        L.append("")
        L.append(bt.baselines.render())
        L.append("")
        for nt in bt.baselines.notes:
            L.append(f"> {nt}")
        L.append("")

    L.append("### A.3 分组稳定性")
    L.append("")
    L.append("| 分组 | T | 均值命中 | lift | z | 判定 |")
    L.append("|---|---|---|---|---|---|")
    for label, tr in list(bt.year_breakdown().items()):
        L.append(f"| {label} | {tr.T} | {tr.mean_hits:.4f} | {tr.lift:.4f} | "
                 f"{tr.z:+.3f} | {tr.verdict} |")
    L.append("")
    qb = bt.quarter_breakdown()
    if qb:
        L.append("<details><summary>按季度展开</summary>")
        L.append("")
        L.append("| 季度 | T | 均值命中 | lift | z | 判定 |")
        L.append("|---|---|---|---|---|---|")
        for label, tr in qb.items():
            L.append(f"| {label} | {tr.T} | {tr.mean_hits:.4f} | {tr.lift:.4f} | "
                     f"{tr.z:+.3f} | {tr.verdict} |")
        L.append("")
        L.append("</details>")
        L.append("")

    L.append("### A.4 功效分析")
    L.append("")
    L.append("在当前样本量下，系统需要至少达到以下优势才能被检验出来：")
    L.append("")
    L.append(render_power_table((bt.T, 120, 60) if bt.T not in (277, 120, 60)
                                else (277, 120, 60)))
    L.append("")
    L.append(f"> 本窗口 T={bt.T}，最小可检测 lift 约 "
             f"+{(bt.system_test.mde_lift * 100 if bt.system_test else 0):.1f}%。"
             f"低于该幅度的真实优势**无法**被本回测证实。")
    L.append("")
    return L


# ── 组装 ──────────────────────────────────────────────────────

def render_markdown(ctx: ReportContext) -> str:
    L: list[str] = []
    L.append(f"# 快乐8 点位+遗漏号分析 · 日报 {ctx.target.date}"
             f"（第{ctx.target.period_str}期）")
    L.append("")
    if ctx.degraded:
        L.append("> ⚠️ **本报告处于降级状态，推荐结果与随机选取无统计差异。**")
        L.append("")
    L.append("> " + conclusion_line(ctx))
    L.append("")

    L.extend(_sec_overview(ctx))
    L.extend(_sec_dashboard(ctx))
    L.extend(_sec_top5(ctx))
    L.extend(_sec_macro(ctx))
    L.extend(_sec_risk(ctx))
    L.extend(_sec_tree(ctx))
    L.extend(_sec_final(ctx))
    L.extend(_sec_backtest(ctx))

    L.append("---")
    L.append("")
    L.append(f"> **免责声明**：{DISCLAIMER}")
    L.append("")

    text = "\n".join(L)
    assert_compliant(text)
    return text


def render_stdout(ctx: ReportContext) -> str:
    """终端摘要：与 md 的一句话结论共用渲染函数（§7.0）。"""
    L = []
    L.append("=" * 62)
    L.append(f"快乐8 点位+遗漏号分析 · {ctx.target.date} 第{ctx.target.period_str}期")
    L.append("=" * 62)
    L.append(conclusion_line(ctx).replace("**", ""))
    L.append("")
    if ctx.selection and ctx.selection.core:
        L.append("五码核心：" + _fmt_nums(ctx.selection.core))
    if ctx.picks and ctx.picks.defensive:
        L.append("两码备防：" + _fmt_nums(ctx.picks.defensive))
    if ctx.fusion and ctx.selection:
        L.append("")
        L.append("综合分：")
        for n in ctx.selection.core:
            dom, _ = ctx.fusion.dominant_dim(n)
            L.append(f"  {n:02d}  {ctx.fusion.composite.get(n, 0.0):6.2f}   "
                     f"{DIM_NAMES.get(dom, dom)}")
    L.append("")
    if ctx.backtest and ctx.backtest.system_test:
        st = ctx.backtest.system_test
        L.append(f"回测 T={st.T}  均值={st.mean_hits:.4f}  lift={st.lift:.4f}  "
                 f"{st.verdict}")
    L.append("")
    L.append("※ " + DISCLAIMER[:40] + "…")
    text = "\n".join(L)
    assert_compliant(text)
    return text


def write_report(ctx: ReportContext, out_dir: str | Path | None = None) -> Path:
    """按日期落盘到 `<out_dir>/<date>/daily_report.md`（默认 storage/outputs/point_omission）。"""
    root = Path(out_dir) if out_dir is not None else Path(ctx.cfg.out_dir)
    if not root.is_absolute():
        root = (ctx.cfg.root / root).resolve()
    d = root / str(ctx.target.date)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "daily_report.md"
    path.write_text(render_markdown(ctx), encoding="utf-8", newline="\r\n")
    return path
