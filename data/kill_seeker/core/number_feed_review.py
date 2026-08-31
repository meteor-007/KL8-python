"""
KillSeeker — 反哺四类号码逐号复盘明细

基于 kill_logs.jsonl 的 cross_feed 字段 + 开奖结果，
为危险/需复核/共振/独立 每一号码生成可复盘明细。
缺数据时明确标注「无」。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


CATEGORY_META = {
    "danger": {
        "emoji": "🔴",
        "label": "危险信号",
        "why": "前序做多推荐 ∩ 高置信杀号 → 做多池与杀号冲突",
        "good": "未开出=杀对/剔除准确",
        "bad": "开出=误杀/剔除失败",
    },
    "review": {
        "emoji": "🟡",
        "label": "需复核",
        "why": "前序做多推荐 ∩ 中置信杀号 → 谨慎降权 0.5x",
        "good": "未开出=中置信杀对",
        "bad": "开出=中置信漏杀",
    },
    "resonate": {
        "emoji": "🟢",
        "label": "共振确认",
        "why": "前序做多推荐 ∩ 保留号 → 多系统一致，优先选入",
        "good": "开出=共振命中",
        "bad": "未开出=共振未中",
    },
    "independent": {
        "emoji": "⚪",
        "label": "独立杀号",
        "why": "高置信杀号 − 前序做多推荐 → 做多未推，杀号风险较低",
        "good": "未开出=独立杀对",
        "bad": "开出=独立漏杀",
    },
}


def _tier_of(num: int, pred: dict) -> str:
    if num in (pred.get("high_conf_kills") or []):
        return "高置信"
    if num in (pred.get("mid_conf_kills") or []):
        return "中置信"
    if num in (pred.get("low_conf_kills") or []):
        return "观察区"
    if num in (pred.get("safe_numbers") or []):
        return "保留号"
    return "无"


def _tag_of(num: int, cf: dict) -> Optional[str]:
    if num in (cf.get("danger") or []):
        return "danger"
    if num in (cf.get("review") or []):
        return "review"
    if num in (cf.get("resonate") or []):
        return "resonate"
    if num in (cf.get("independent_kills") or []):
        return "independent"
    return None


def _src_list(num: int, cf: dict, category: str) -> List[str]:
    key_map = {
        "danger": "danger_sources",
        "review": "review_sources",
        "resonate": "resonate_sources",
    }
    key = key_map.get(category)
    if not key:
        return []
    src_map = cf.get(key) or {}
    raw = src_map.get(str(num)) or src_map.get(num) or []
    if isinstance(raw, str):
        return [raw]
    return list(raw)


def _upstream_hit(num: int, cf: dict) -> List[str]:
    """本期前序源中出现该号的系统名。"""
    hits = []
    sources = cf.get("sources") or {}
    for name, nums in sources.items():
        if num in (nums or []):
            hits.append(name)
    return hits


def _outcome_label(category: str, opened: bool) -> str:
    meta = CATEGORY_META[category]
    if category == "resonate":
        return f"命中✅({meta['good']})" if opened else f"未中❌({meta['bad']})"
    # kill-side categories: not opened = good
    return f"杀对✅({meta['good']})" if not opened else f"漏杀❌({meta['bad']})"


def _kill_streaks(
    num: int,
    reviewed_preds: List[dict],
    opened: Dict[str, Set[int]],
) -> Tuple[int, int]:
    """连续高置信杀对 streak、连续(高|中)漏杀 streak（从最近往前）。"""
    kill_ok = 0
    for pred in reviewed_preds:
        highs = set(pred.get("high_conf_kills") or [])
        actual = opened[pred["period"]]
        if num in highs and num not in actual:
            kill_ok += 1
        else:
            break
    leak = 0
    for pred in reviewed_preds:
        kills = set(pred.get("high_conf_kills") or []) | set(pred.get("mid_conf_kills") or [])
        actual = opened[pred["period"]]
        if num in kills and num in actual:
            leak += 1
        else:
            break
    return kill_ok, leak


@dataclass
class NumberReview:
    num: int
    category: str
    tier: str
    sources: List[str] = field(default_factory=list)
    why: str = ""
    upstream_now: List[str] = field(default_factory=list)
    boost: bool = False
    leak_down: bool = False
    kill_ok_streak: int = 0
    leak_streak: int = 0
    # 近窗在同分类语境下的表现
    same_cat_rows: List[dict] = field(default_factory=list)
    same_cat_good: int = 0
    same_cat_total: int = 0
    # 近窗无论分类，作为杀号/保留的表现
    any_tag_rows: List[dict] = field(default_factory=list)
    # 近窗开奖：该号是否开出（与档位无关）
    draw_appearances: int = 0
    draw_window: int = 0
    # 前序源推荐期次中该号实际开出率
    upstream_rec_periods: int = 0
    upstream_rec_hit: int = 0


def build_number_reviews(
    current: dict,
    preds: List[dict],
    opened: Dict[str, Set[int]],
    window: int = 10,
) -> Dict[str, List[NumberReview]]:
    """为当期四类号码构建逐号复盘。"""
    cf = current.get("cross_feed") or {}
    period = current.get("period", "")
    groups = {
        "danger": list(cf.get("danger") or []),
        "review": list(cf.get("review") or []),
        "resonate": list(cf.get("resonate") or []),
        "independent": list(cf.get("independent_kills") or []),
    }
    boost_set = set(cf.get("stable_kill_boost") or [])
    leak_set = set(cf.get("leak_downgrade") or [])

    # 最近已开奖且含 cross_feed 的期（不含当期未开奖）
    reviewed: List[dict] = []
    for pred in reversed(preds):
        p = pred.get("period", "")
        if p == period or p not in opened or not pred.get("cross_feed"):
            continue
        reviewed.append(pred)
        if len(reviewed) >= window:
            break

    # 近窗开奖（含无 cross_feed 的期，用于出号频率）
    recent_draws: List[Tuple[str, Set[int]]] = []
    seen = set()
    for pred in reversed(preds):
        p = pred.get("period", "")
        if p == period or p in seen or p not in opened:
            continue
        seen.add(p)
        recent_draws.append((p, opened[p]))
        if len(recent_draws) >= window:
            break

    out: Dict[str, List[NumberReview]] = {k: [] for k in groups}
    for cat, nums in groups.items():
        meta = CATEGORY_META[cat]
        for num in nums:
            nr = NumberReview(
                num=num,
                category=cat,
                tier=_tier_of(num, current),
                sources=_src_list(num, cf, cat),
                why=meta["why"],
                upstream_now=_upstream_hit(num, cf),
                boost=num in boost_set,
                leak_down=num in leak_set,
            )
            nr.kill_ok_streak, nr.leak_streak = _kill_streaks(num, reviewed, opened)

            # 同分类历史
            for pred in reviewed:
                pcf = pred.get("cross_feed") or {}
                tag = _tag_of(num, pcf)
                if tag != cat:
                    continue
                actual = opened[pred["period"]]
                opened_flag = num in actual
                good = (opened_flag if cat == "resonate" else not opened_flag)
                row = {
                    "period": pred["period"],
                    "tag": cat,
                    "tier": _tier_of(num, pred),
                    "opened": opened_flag,
                    "outcome": _outcome_label(cat, opened_flag),
                    "sources": _src_list(num, pcf, cat),
                    "upstream": _upstream_hit(num, pcf),
                    "coverage": pcf.get("kill_coverage"),
                }
                nr.same_cat_rows.append(row)
                nr.same_cat_total += 1
                if good:
                    nr.same_cat_good += 1

            # 任意反哺标签历史（近窗）
            for pred in reviewed:
                pcf = pred.get("cross_feed") or {}
                tag = _tag_of(num, pcf)
                if not tag:
                    continue
                actual = opened[pred["period"]]
                opened_flag = num in actual
                nr.any_tag_rows.append({
                    "period": pred["period"],
                    "tag": tag,
                    "tier": _tier_of(num, pred),
                    "opened": opened_flag,
                    "outcome": _outcome_label(tag, opened_flag),
                    "sources": _src_list(num, pcf, tag) if tag != "independent" else [],
                    "upstream": _upstream_hit(num, pcf),
                })

            # 近窗出号
            nr.draw_window = len(recent_draws)
            nr.draw_appearances = sum(1 for _, a in recent_draws if num in a)

            # 前序源推荐 vs 开出（近窗：该期 sources 含此号）
            for pred in reviewed:
                pcf = pred.get("cross_feed") or {}
                ups = _upstream_hit(num, pcf)
                if not ups:
                    continue
                nr.upstream_rec_periods += 1
                if num in opened[pred["period"]]:
                    nr.upstream_rec_hit += 1

            out[cat].append(nr)
    return out


def _fmt_rate(good: int, total: int) -> str:
    if total <= 0:
        return "无"
    return f"{good}/{total}={good / total:.0%}"


def _fmt_srcs(srcs: List[str]) -> str:
    return ",".join(srcs) if srcs else "无"


def render_cross_feed_review_md(
    period: str,
    current: dict,
    reviews: Dict[str, List[NumberReview]],
    latest_draw: str,
    total_periods: int,
    window: int = 10,
) -> str:
    cf = current.get("cross_feed") or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    L: List[str] = []
    L.append(f"# KillSeeker 反哺四类逐号复盘 — {period}期")
    L.append("")
    L.append(f"- 生成时间: {now}")
    L.append(f"- 锚定开奖: `{latest_draw}` · 历史 `{total_periods}` 期 · 近窗复盘 **{window}** 期")
    L.append(f"- 综合把握: **{float(current.get('kill_confidence') or 0):.1%}**")
    L.append("")
    L.append("> 语义：危险/需复核/独立以「未开出=杀对」计；共振以「开出=命中」计。缺样本写「无」。")
    L.append("")

    # 总览矩阵
    L.append("## 〇 本期交叉矩阵总览")
    L.append("")
    for cat in ("danger", "review", "resonate", "independent"):
        meta = CATEGORY_META[cat]
        nums = reviews.get(cat) or []
        if not nums:
            L.append(f"- {meta['emoji']} {meta['label']}: (无)")
            continue
        parts = []
        for nr in nums:
            tag = _fmt_srcs(nr.sources) if nr.sources else ("—" if cat == "independent" else "无")
            if cat == "independent":
                parts.append(f"{nr.num:02d}")
            else:
                parts.append(f"{nr.num:02d}[{tag}]")
        L.append(f"- {meta['emoji']} {meta['label']}: {', '.join(parts)}")

    cov = float(cf.get("kill_coverage") or 0)
    flag = "严重分歧" if cov > 0.5 else ("方向一致" if cov < 0.2 else "中性")
    L.append(f"- 击杀率: {cov:.0%} → {flag}")
    if cf.get("advice"):
        L.append(f"- 覆盖建议: {cf['advice']}")
    prev = cf.get("prev_review") or {}
    win = cf.get("window_review") or {}
    if prev:
        idx = prev.get("index")
        idx_s = f"{idx:.2f}" if isinstance(idx, (int, float)) else "N/A"
        L.append(f"- 上期反哺回验: {prev.get('status', '无')} | 指数={idx_s}")
        if prev.get("danger_miss_rate") is not None:
            L.append(f"  - 危险未中率: {prev['danger_miss_rate']:.0%}")
        if prev.get("resonate_hit_rate") is not None:
            L.append(f"  - 共振命中率: {prev['resonate_hit_rate']:.0%}")
        if prev.get("advice"):
            L.append(f"  - {prev['advice']}")
    if win and win.get("n"):
        widx = win.get("index")
        widx_s = f"{widx:.2f}" if isinstance(widx, (int, float)) else "N/A"
        L.append(
            f"- 近{win.get('n')}期区分力: {win.get('status', '无')} | 指数={widx_s}"
        )
        if win.get("avg_danger_miss_rate") is not None:
            L.append(f"  - 危险未中均: {win['avg_danger_miss_rate']:.0%}")
        if win.get("avg_resonate_hit_rate") is not None:
            L.append(f"  - 共振命中均: {win['avg_resonate_hit_rate']:.0%}")
    boost = cf.get("stable_kill_boost") or []
    leak = cf.get("leak_downgrade") or []
    L.append(f"- ⬆ 连续杀对升档: {', '.join(f'{n:02d}' for n in boost) if boost else '无'}")
    L.append(f"- ⬇ 漏杀降档: {', '.join(f'{n:02d}' for n in leak) if leak else '无'}")
    L.append("")

    # 核心汇总表
    L.append("## ① 四类号码核心汇总表")
    L.append("")
    L.append(
        "| 分类 | 号码 | 档位 | 来源 | 同分类近窗表现 | 近窗出号 | "
        "前序推荐命中 | 升档/降档 | 连续杀对/漏杀 |"
    )
    L.append(
        "|------|------|------|------|----------------|----------|"
        "--------------|-----------|----------------|"
    )
    for cat in ("danger", "review", "resonate", "independent"):
        meta = CATEGORY_META[cat]
        for nr in reviews.get(cat) or []:
            boost_s = "⬆升档" if nr.boost else ("⬇降档" if nr.leak_down else "—")
            streak_s = f"杀对{nr.kill_ok_streak}/漏杀{nr.leak_streak}"
            draw_s = (
                f"{nr.draw_appearances}/{nr.draw_window}"
                if nr.draw_window
                else "无"
            )
            up_s = _fmt_rate(nr.upstream_rec_hit, nr.upstream_rec_periods)
            L.append(
                f"| {meta['emoji']}{meta['label']} | {nr.num:02d} | {nr.tier} | "
                f"{_fmt_srcs(nr.sources) if cat != 'independent' else '—'} | "
                f"{_fmt_rate(nr.same_cat_good, nr.same_cat_total)} | {draw_s} | "
                f"{up_s} | {boost_s} | {streak_s} |"
            )
    L.append("")

    # 逐号明细
    L.append("## ② 逐号详细复盘")
    L.append("")
    for cat in ("danger", "review", "resonate", "independent"):
        meta = CATEGORY_META[cat]
        nums = reviews.get(cat) or []
        L.append(f"### {meta['emoji']} {meta['label']}")
        L.append("")
        L.append(f"> 分类定义: {meta['why']}")
        L.append("")
        if not nums:
            L.append("(无)")
            L.append("")
            continue
        for nr in nums:
            L.append(f"#### 号码 `{nr.num:02d}`")
            L.append("")
            L.append(f"| 字段 | 内容 |")
            L.append(f"|------|------|")
            L.append(f"| 所属档位 | **{nr.tier}** |")
            L.append(f"| 来源标签 | {_fmt_srcs(nr.sources) if cat != 'independent' else '无（独立杀号）'} |")
            L.append(f"| 为何进该类 | {nr.why} |")
            L.append(f"| 本期前序对照 | {_fmt_srcs(nr.upstream_now)} |")
            L.append(
                f"| 升档/降档标记 | "
                f"{'⬆连续≥3期高置信杀对升档' if nr.boost else ('⬇连续≥2期漏杀降观察' if nr.leak_down else '无')} |"
            )
            L.append(f"| 连续高置信杀对 streak | {nr.kill_ok_streak} 期 |")
            L.append(f"| 连续漏杀 streak | {nr.leak_streak} 期 |")
            L.append(
                f"| 同分类近窗表现 | {_fmt_rate(nr.same_cat_good, nr.same_cat_total)} "
                f"（{meta['good']}） |"
            )
            L.append(
                f"| 近{nr.draw_window}期实际出号 | "
                f"{nr.draw_appearances}/{nr.draw_window if nr.draw_window else '无'} |"
            )
            L.append(
                f"| 近窗被前序推荐时开出 | "
                f"{_fmt_rate(nr.upstream_rec_hit, nr.upstream_rec_periods)} |"
            )
            L.append("")

            L.append("**同分类历史明细（近窗出现过该类标签的期次）**")
            L.append("")
            if not nr.same_cat_rows:
                L.append("无")
                L.append("")
            else:
                L.append("| 期号 | 档位 | 来源 | 前序含号 | 开出 | 结果 | 当击杀率 |")
                L.append("|------|------|------|----------|------|------|----------|")
                for row in nr.same_cat_rows:
                    cov_v = row.get("coverage")
                    cov_s = f"{cov_v:.0%}" if isinstance(cov_v, (int, float)) else "无"
                    L.append(
                        f"| {row['period']} | {row['tier']} | {_fmt_srcs(row.get('sources') or [])} | "
                        f"{_fmt_srcs(row.get('upstream') or [])} | "
                        f"{'是' if row['opened'] else '否'} | {row['outcome']} | {cov_s} |"
                    )
                L.append("")

            L.append("**近窗任意反哺标签轨迹**")
            L.append("")
            if not nr.any_tag_rows:
                L.append("无")
                L.append("")
            else:
                L.append("| 期号 | 标签 | 档位 | 来源 | 开出 | 结果 |")
                L.append("|------|------|------|------|------|------|")
                for row in nr.any_tag_rows:
                    tag_meta = CATEGORY_META.get(row["tag"], {})
                    tag_label = f"{tag_meta.get('emoji', '')}{tag_meta.get('label', row['tag'])}"
                    L.append(
                        f"| {row['period']} | {tag_label} | {row['tier']} | "
                        f"{_fmt_srcs(row.get('sources') or [])} | "
                        f"{'是' if row['opened'] else '否'} | {row['outcome']} |"
                    )
                L.append("")

    L.append("---")
    L.append("终极宪章: 除了上帝，我们只信数据；杀得越狠，赢面越大。")
    L.append("")
    return "\n".join(L)


def render_today_result_md(
    period: str,
    current: dict,
    reviews: Dict[str, List[NumberReview]],
    latest_draw: str,
    total_periods: int,
    hit_rate_table: Optional[List[dict]] = None,
    window: int = 10,
) -> str:
    """今日总结果：杀号推荐 + 反哺逐号复盘摘要 + 指向明细。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    eng = current.get("engine_contributions") or {}
    cf = current.get("cross_feed") or {}
    L: List[str] = []
    L.append(f"# KillSeeker 今日完整数据结果 — {period}期")
    L.append("")
    L.append(f"- 生成时间: {now}")
    L.append(f"- 最新开奖: `{latest_draw}` · 历史 `{total_periods}` 期")
    L.append(f"- 预测期号: **{period}** · 综合把握 **{float(current.get('kill_confidence') or 0):.1%}**")
    L.append("")

    if hit_rate_table:
        L.append("## A. 近窗命中率")
        L.append("")
        L.append("| 期号 | 高置信 | 中置信 | 全部杀号 | 保留号 |")
        L.append("|------|--------|--------|----------|--------|")
        th = th_t = tm = tm_t = ta = ta_t = ts = ts_t = 0
        for r in hit_rate_table:
            hr = r["high_hit"] / r["high_total"] if r["high_total"] else 0
            mr = r["mid_hit"] / r["mid_total"] if r["mid_total"] else 0
            ar = r["all_hit"] / r["all_total"] if r["all_total"] else 0
            sr = r["safe_hit"] / r["safe_total"] if r["safe_total"] else 0
            L.append(
                f"| {r['period']} | {r['high_hit']}/{r['high_total']} ({hr:.0%}) | "
                f"{r['mid_hit']}/{r['mid_total']} ({mr:.0%}) | "
                f"{r['all_hit']}/{r['all_total']} ({ar:.0%}) | "
                f"{r['safe_hit']}/{r['safe_total']} ({sr:.0%}) |"
            )
            th += r["high_hit"]; th_t += r["high_total"]
            tm += r["mid_hit"]; tm_t += r["mid_total"]
            ta += r["all_hit"]; ta_t += r["all_total"]
            ts += r["safe_hit"]; ts_t += r["safe_total"]
        if th_t:
            L.append("")
            L.append(
                f"**均值**: 高 {th/th_t:.1%} · 中 {tm/tm_t:.1%} · "
                f"全部 {ta/ta_t:.1%} · 保留 {ts/ts_t:.1%} · "
                f"相对基线75% {(ta/ta_t/0.75-1)*100:+.1f}%"
            )
        L.append("")

    L.append(f"## B. {period}期杀号推荐")
    L.append("")
    L.append(
        f"- 引擎贡献: 相似 {eng.get('similarity', 0):.0%} / 密集 {eng.get('density', 0):.0%} / "
        f"形态 {eng.get('pattern', 0):.0%} / 曲线 {eng.get('curve', 0):.0%}"
    )
    highs = current.get("high_conf_kills") or []
    mids = current.get("mid_conf_kills") or []
    lows = current.get("low_conf_kills") or []
    safes = current.get("safe_numbers") or []
    L.append(f"- 🔴 高置信: {', '.join(f'{n:02d}' for n in highs)}")
    L.append(f"- 🟡 中置信: {', '.join(f'{n:02d}' for n in mids)}")
    L.append(f"- 🟠 观察区: {', '.join(f'{n:02d}' for n in lows)}")
    L.append(f"- 🟢 保留号: {', '.join(f'{n:02d}' for n in safes)}")
    all_k = current.get("all_kills") or (highs + mids + lows)
    L.append(f"- 排除 {len(all_k)}/80 → 剩余可选 {80 - len(all_k)}")
    L.append("")

    L.append("## C. 反哺交叉矩阵 + 逐号复盘摘要")
    L.append("")
    L.append(
        "| 分类 | 号码 | 档位 | 来源/为何 | 同分类近窗 | 升/降档 | 连续杀对 | 行动 |"
    )
    L.append("|------|------|------|-----------|------------|---------|----------|------|")
    action_map = {
        "danger": "仅供参考/视反哺闭环",
        "review": "降权0.5x",
        "resonate": "优先选入",
        "independent": "缩水划去",
    }
    # soft danger from prev_review
    soft = False
    prev = cf.get("prev_review") or {}
    st = str(prev.get("status") or "")
    if any(k in st for k in ("无效", "失真", "微弱", "共振失效", "样本不足")):
        soft = True
    for cat in ("danger", "review", "resonate", "independent"):
        meta = CATEGORY_META[cat]
        act = action_map[cat]
        if cat == "danger":
            act = "仅供参考不强制剔除" if soft else "建议从做多池剔除"
        for nr in reviews.get(cat) or []:
            why_short = _fmt_srcs(nr.sources) if nr.sources else (
                "高置信−做多" if cat == "independent" else "无"
            )
            boost_s = "⬆" if nr.boost else ("⬇" if nr.leak_down else "—")
            L.append(
                f"| {meta['emoji']}{meta['label']} | {nr.num:02d} | {nr.tier} | {why_short} | "
                f"{_fmt_rate(nr.same_cat_good, nr.same_cat_total)} | {boost_s} | "
                f"{nr.kill_ok_streak} | {act} |"
            )
    L.append("")

    L.append("### 区分力 / 击杀率")
    L.append("")
    cov = float(cf.get("kill_coverage") or 0)
    L.append(f"- 本期击杀率: **{cov:.0%}**")
    if cf.get("advice"):
        L.append(f"- {cf['advice']}")
    if prev:
        idx = prev.get("index")
        idx_s = f"{idx:.2f}" if isinstance(idx, (int, float)) else "N/A"
        L.append(f"- 上期回验: {prev.get('status')} · 指数 {idx_s}")
    win = cf.get("window_review") or {}
    if win and win.get("n"):
        widx = win.get("index")
        widx_s = f"{widx:.2f}" if isinstance(widx, (int, float)) else "N/A"
        L.append(f"- 近窗区分力: {win.get('status')} · 指数 {widx_s}")
    L.append("")
    L.append(
        f"> 完整逐号明细见: `logs/control_panel_{period}_cross_feed_review.md`"
    )
    L.append("")

    L.append("## D. 行动清单")
    L.append("")
    L.append("1. 高置信杀号 → 从大盘直接划去")
    if soft:
        L.append("2. 🔴危险信号 → **仅供参考，不强制剔除**")
    else:
        L.append("2. 🔴危险信号 → 从做多推荐中剔除")
    L.append("3. 🟡需复核 → 降权 0.5x")
    L.append("4. 🟢共振确认 → 提高选入优先级")
    L.append("5. ⚪独立杀号 → 随高置信一并缩水")
    L.append("6. 杀号仅缩水，不做主战做多")
    L.append("")
    L.append("---")
    L.append("终极宪章: 除了上帝，我们只信数据；杀得越狠，赢面越大。")
    L.append("")
    return "\n".join(L)


def write_number_feed_reports(
    output_dir: Path,
    current: dict,
    preds: List[dict],
    opened: Dict[str, Set[int]],
    latest_draw: str,
    total_periods: int,
    hit_rate_table: Optional[List[dict]] = None,
    window: int = 10,
) -> Tuple[Path, Path]:
    period = current.get("period", "")
    reviews = build_number_reviews(current, preds, opened, window=window)
    review_md = render_cross_feed_review_md(
        period, current, reviews, latest_draw, total_periods, window=window
    )
    today_md = render_today_result_md(
        period, current, reviews, latest_draw, total_periods,
        hit_rate_table=hit_rate_table, window=window,
    )
    review_path = output_dir / f"control_panel_{period}_cross_feed_review.md"
    today_path = output_dir / f"today_result_{period}.md"
    review_path.write_text(review_md, encoding="utf-8")
    today_path.write_text(today_md, encoding="utf-8")
    return review_path, today_path
