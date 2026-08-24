"""
KillSeeker STEP 2.5 — 杀号反哺交叉校验（轻量落地版）

读取前序做多系统推荐，与本期杀号做交叉矩阵。
不做复杂参数自学习闭环（易过拟合、难维护）；仅输出可执行建议。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# 反哺区分力统计窗口期数：从近5期→近10期→近15期，继续平滑共振样本过少导致的指数异常波动
CROSS_FEED_WINDOW_N = 15

WORKSPACE = Path(__file__).resolve().parents[2]

LSTM_PRED_DIR = WORKSPACE / "双层LSTM" / "outputs" / "predictions"
DJX2_LOG = WORKSPACE / "定金选2-分析" / "logs" / "prediction_logs.txt"
DIWEI_LOG = WORKSPACE / "重点点位分析" / "logs" / "prediction_logs.txt"
TONGJI_LOG = WORKSPACE / "archive" / "统计次数-复盘" / "logs" / "prediction_logs.txt"
DATA_AGG_LOG_DIR = WORKSPACE / "数据汇总复盘" / "logs"


@dataclass
class SourceRec:
    name: str
    numbers: List[int]
    note: str = ""


@dataclass
class CrossFeedResult:
    period: str
    sources: List[SourceRec] = field(default_factory=list)
    union_long: List[int] = field(default_factory=list)
    danger: List[int] = field(default_factory=list)
    review: List[int] = field(default_factory=list)
    resonate: List[int] = field(default_factory=list)
    independent_kills: List[int] = field(default_factory=list)
    danger_sources: Dict[int, List[str]] = field(default_factory=dict)
    resonate_sources: Dict[int, List[str]] = field(default_factory=dict)
    review_sources: Dict[int, List[str]] = field(default_factory=dict)
    kill_coverage: float = 0.0
    chaos_flag: bool = False
    stable_kill_boost: List[int] = field(default_factory=list)
    leak_downgrade: List[int] = field(default_factory=list)
    advice: str = ""


def _parse_nums(text: str) -> List[int]:
    # 期号(如 2026208)/日期(如 20260806)等 ≥4 位长数字串先剔除，
    # 否则 re.findall(r"\d{1,2}") 会把它们切成 20/26/20/8 之类的伪号码混入候选。
    # 合法号码范围 1-80，不会出现在 ≥4 位连续数字串中（号码间必有分隔符）。
    text = re.sub(r"\d{4,}", " ", text)
    nums = []
    for tok in re.findall(r"\d{1,2}", text):
        n = int(tok)
        if 1 <= n <= 80 and n not in nums:
            nums.append(n)
    return nums


def _dedupe(nums: List[int]) -> List[int]:
    seen = set()
    out = []
    for n in nums:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _load_lstm(period: str) -> Optional[SourceRec]:
    path = LSTM_PRED_DIR / f"prediction_{period}.txt"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    nums: List[int] = []
    m = re.search(r"Top10:\s*([0-9\-]+)", text)
    if m:
        nums.extend(_parse_nums(m.group(1)))
    for label in ("金胆", "银胆", "铜胆"):
        m2 = re.search(rf"{label}:\s*(\d+)", text)
        if m2:
            n = int(m2.group(1))
            if n not in nums:
                nums.insert(0, n)
    if not nums:
        return None
    return SourceRec("双层LSTM", nums[:12], note="Top10+金银铜胆")


def _section_for_period(text: str, period: str) -> str:
    # 期号(如 2026208)可能作为子串出现在日期/序号等长数字中，
    # 直接 rfind 会定位到无关位置。改为按"完整数字词元"匹配
    # （左右都不是数字，排除 20262085 / 202620805 这类长数字串），
    # 并保留旧实现的"取最后一次出现"语义。
    pat = re.compile(rf"(?<!\d){re.escape(period)}(?!\d)")
    matches = list(pat.finditer(text))
    idx = matches[-1].start() if matches else -1
    if idx < 0:
        return ""
    start = max(0, idx - 80)
    end = min(len(text), idx + 2500)
    return text[start:end]


def _load_djx2(period: str) -> Optional[SourceRec]:
    if not DJX2_LOG.exists():
        return None
    text = DJX2_LOG.read_text(encoding="utf-8", errors="replace")
    chunk = _section_for_period(text, period)
    if not chunk:
        return None
    nums: List[int] = []
    for pat in [
        r"动态金胆:\s*(\d+)",
        r"热号金胆:\s*(\d+)",
        r"Top\s*\d+\s*推荐组合\s*:\s*\[([^\]]+)\]",
    ]:
        for m in re.finditer(pat, chunk):
            nums.extend(_parse_nums(m.group(1)))
    uniq = _dedupe(nums)
    if not uniq:
        return None
    return SourceRec("定金选2", uniq[:15], note="金胆+Top组合搭档")


def _load_diwei(period: str) -> Optional[SourceRec]:
    if not DIWEI_LOG.exists():
        return None
    text = DIWEI_LOG.read_text(encoding="utf-8", errors="replace")
    chunk = _section_for_period(text, period)
    if not chunk:
        return None
    nums: List[int] = []
    m = re.search(r"精选十码:\s*\[([^\]]+)\]", chunk)
    if m:
        nums.extend(_parse_nums(m.group(1)))
    for m in re.finditer(r"最佳号码:\[([^\]]+)\]", chunk):
        # 原正则 \[(\d+)\] 只能取单个数字，且遇到 [63,64] 这类多值直接不匹配；
        # 改为整段提取再拆分，可兼容多值（拆分后统一去重，保持旧行为无重复）
        nums.extend(_parse_nums(m.group(1)))
    uniq = _dedupe(nums)
    if not uniq:
        return None
    return SourceRec("重点点位", uniq[:12], note="精选十码/最佳号码")


def _load_tongji(period: str) -> Optional[SourceRec]:
    """统计次数：必须命中目标期号块；禁止回退上期（会污染危险信号）。"""
    if not TONGJI_LOG.exists():
        return None
    text = TONGJI_LOG.read_text(encoding="utf-8", errors="replace")
    # 优先：含目标期号的段落（目标期号: 2026xxx / 2026xxx | 日期）
    chunk = _section_for_period(text, period)
    if not chunk:
        return None
    m = re.search(
        r"金胆:\s*(\d+)\s*\|\s*银胆:\s*(\d+)\s*\|\s*铜胆:\s*(\d+)",
        chunk,
    )
    if not m:
        return None
    nums = [int(m.group(1)), int(m.group(2)), int(m.group(3))]
    for nm in re.finditer(r"号码\s+(\d+)\s+评分", chunk):
        n = int(nm.group(1))
        if n not in nums:
            nums.append(n)
    if len(nums) < 3:
        return None
    return SourceRec("统计次数", nums[:10], note="金胆银胆铜胆+Top评分")


def _load_data_agg(period: str) -> Optional[SourceRec]:
    """读取数据汇总复盘：核心定胆 + 分区主推（原 HE5/Trinity 后继形态）。"""
    if not DATA_AGG_LOG_DIR.exists():
        return None
    candidates = sorted(
        DATA_AGG_LOG_DIR.glob("分区深度聚合推荐_*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        candidates = sorted(
            DATA_AGG_LOG_DIR.glob("*.txt"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    for path in candidates[:5]:
        text = path.read_text(encoding="utf-8", errors="replace")
        if period not in text:
            continue
        # 截取「今日目标期」后的推荐总汇（窗口需覆盖分区表+定胆摘要）
        m_target = re.search(rf"今日目标期\s*{period}([\s\S]{{0,4000}})", text)
        chunk = m_target.group(0) if m_target else _section_for_period(text, period)
        if not chunk:
            continue
        # 只取到下一个「📅 期号」复盘块之前，避免混入历史
        cut = re.search(r"📅\s*期号", chunk)
        if cut and cut.start() > 40:
            chunk = chunk[: cut.start()]
        nums: List[int] = []
        for pat in [
            r"核心定胆主推[^:：]*[:：]\s*([0-9\s]+)",
            r"分区主推号码[^:：]*[:：]\s*([0-9\s]+)",
            r"核心胆码[^:：]*[:：]\s*([0-9\s]+)",
        ]:
            for m in re.finditer(pat, chunk):
                nums.extend(_parse_nums(m.group(1)))
        uniq = _dedupe(nums)
        if uniq:
            return SourceRec("数据汇总", uniq[:20], note="核心定胆+分区主推")
    return None


def collect_upstream(period: str) -> List[SourceRec]:
    sources = []
    for loader in (_load_data_agg, _load_lstm, _load_djx2, _load_diwei, _load_tongji):
        try:
            rec = loader(period)
            if rec and rec.numbers:
                sources.append(rec)
        except (OSError, ValueError, re.error):
            continue
    return sources


def _source_map(sources: List[SourceRec]) -> Dict[int, List[str]]:
    mapping: Dict[int, List[str]] = {}
    for src in sources:
        for n in src.numbers:
            mapping.setdefault(n, []).append(src.name)
    return mapping


def analyze_stability(
    preds: List[dict],
    opened: Dict[str, Set[int]],
    current_high: List[int],
    current_mid: List[int],
) -> Tuple[List[int], List[int]]:
    reviewed = []
    for pred in reversed(preds):
        p = pred.get("period", "")
        if p in opened:
            reviewed.append(pred)
        if len(reviewed) >= 5:
            break
    if len(reviewed) < 2:
        return [], []

    boost: List[int] = []
    for num in range(1, 81):
        streak = 0
        for pred in reviewed:
            highs = set(pred.get("high_conf_kills", []))
            actual = opened[pred["period"]]
            if num in highs and num not in actual:
                streak += 1
            else:
                break
        if streak >= 3 and num in current_high:
            boost.append(num)

    downgrade: List[int] = []
    for num in range(1, 81):
        streak = 0
        for pred in reviewed:
            kills = set(pred.get("high_conf_kills", []) + pred.get("mid_conf_kills", []))
            actual = opened[pred["period"]]
            if num in kills and num in actual:
                streak += 1
            else:
                break
        if streak >= 2 and (num in current_high or num in current_mid):
            downgrade.append(num)

    return sorted(boost), sorted(downgrade)


def run_cross_feed(
    period: str,
    high_kills: List[int],
    mid_kills: List[int],
    safe_numbers: List[int],
    preds_history: Optional[List[dict]] = None,
    opened: Optional[Dict[str, Set[int]]] = None,
) -> CrossFeedResult:
    sources = collect_upstream(period)
    src_map = _source_map(sources)
    union_long = sorted(src_map.keys())
    high_set, mid_set, safe_set = set(high_kills), set(mid_kills), set(safe_numbers)
    long_set = set(union_long)

    danger = sorted(long_set & high_set)
    review = sorted(long_set & mid_set)
    resonate = sorted(long_set & safe_set)
    independent = sorted(high_set - long_set)

    logger.info(
        "[交叉矩阵] 期=%s | 前序做多并集=%s | 高置信杀=%s 中置信杀=%s 保留=%s",
        period, sorted(union_long), sorted(high_set), sorted(mid_set), sorted(safe_set),
    )
    logger.info(
        "[交叉矩阵] 危险(做多∩高杀)=%s | 复核(做多∩中杀)=%s | 共振(做多∩保留)=%s | 独立杀号=%s",
        danger, review, resonate, independent,
    )

    top_limited: List[int] = []
    for src in sources:
        for n in src.numbers[:10]:
            if n not in top_limited:
                top_limited.append(n)
    top_pool = set(top_limited[:15]) if top_limited else set()
    coverage = len(high_set & top_pool) / len(top_pool) if top_pool else 0.0
    logger.info(
        "[交叉矩阵] 击杀率=%.0f%% (高置信杀∩前序Top15=%s / Top15=%s)",
        coverage * 100, sorted(high_set & top_pool), sorted(top_pool),
    )

    chaos = coverage > 0.50
    boost, leak = [], []
    if preds_history and opened:
        boost, leak = analyze_stability(preds_history, opened, high_kills, mid_kills)
        logger.info("[交叉矩阵] 稳定性回溯: 升档=%s 降档=%s", boost, leak)

    if not union_long:
        advice = "未读到前序做多推荐，反哺仅做稳定性回溯"
    elif chaos:
        advice = "击杀率>50%：多系统信号严重分歧，建议观望或缩小注额"
    elif coverage < 0.20:
        advice = "击杀率<20%：杀号与做多方向较一致，信号可靠度较高"
    else:
        advice = "击杀率中等：按红/黄/绿分层处理即可"

    return CrossFeedResult(
        period=period,
        sources=sources,
        union_long=union_long,
        danger=danger,
        review=review,
        resonate=resonate,
        independent_kills=independent,
        danger_sources={n: src_map.get(n, []) for n in danger},
        resonate_sources={n: src_map.get(n, []) for n in resonate},
        review_sources={n: src_map.get(n, []) for n in review},
        kill_coverage=coverage,
        chaos_flag=chaos,
        stable_kill_boost=boost,
        leak_downgrade=leak,
        advice=advice,
    )


def _classify_discrimination(index: Optional[float]) -> Tuple[str, str]:
    """按脚本阈值划分区分力：>1.5有效 / 1.0-1.5微弱 / <1.0无效。"""
    if index is None:
        return "样本不足", "样本不足，反哺仅供参考"
    if index > 1.5:
        return "有效 ✅", "反哺有效 → 维持当前杀号反哺逻辑，危险信号建议剔除做多池"
    if index >= 1.0:
        return "微弱 ⚠️", "反哺微弱 → 危险信号降级为仅供参考，不强制剔除"
    return "无效 ❌", "反哺无效 → 危险信号仅供参考，不强制剔除做多推荐"


def review_previous_cross_feed(prev_entry: dict, actual: Set[int]) -> dict:
    """回验上期反哺标签区分力。"""
    cf = prev_entry.get("cross_feed") or {}
    if not cf:
        logger.info("[反哺回验] 上期无 cross_feed 字段，跳过区分力计算")
        return {"status": "无上期反哺记录", "index": None}

    danger = set(cf.get("danger", []))
    resonate = set(cf.get("resonate", []))
    review = set(cf.get("review", []))

    danger_miss_rate = (len(danger - actual) / len(danger)) if danger else None
    resonate_hit_rate = (len(resonate & actual) / len(resonate)) if resonate else None
    review_hit_rate = (len(review & actual) / len(review)) if review else None

    logger.info(
        "[反哺回验] 上期=%s | 危险=%s 共振=%s 复核=%s | 实际开出=%s",
        prev_entry.get("period"),
        sorted(danger), sorted(resonate), sorted(review), sorted(actual),
    )
    logger.info(
        "[反哺回验] 危险未中=%s (剔除对=%s, 误杀=%s) | 共振命中=%s (命中=%s, 未中=%s) | 复核命中=%s",
        "N/A" if danger_miss_rate is None else f"{danger_miss_rate:.0%}",
        sorted(danger - actual) if danger else [],
        sorted(danger & actual) if danger else [],
        "N/A" if resonate_hit_rate is None else f"{resonate_hit_rate:.0%}",
        sorted(resonate & actual) if resonate else [],
        sorted(resonate - actual) if resonate else [],
        "N/A" if review_hit_rate is None else f"{review_hit_rate:.0%}",
    )

    # 脚本定义：区分力指数 = 危险未中率 / 共振命中率（>1.5有效 / 1.0-1.5微弱 / <1.0无效）
    # 注意：共振命中率=0 时不可做除法（旧实现用 1e-6 会炸出 500000 假指数）
    index = None
    status = "样本不足"
    advice = "样本不足，反哺仅供参考"
    if danger_miss_rate is not None and resonate_hit_rate is not None:
        if resonate_hit_rate <= 0:
            # 共振全灭：区分力分母失效，改用危险未中率单独判定
            index = None
            logger.info(
                "[反哺回验] 共振命中率=0 触发分支: 无法做除法(危险未中=%s) → 按危险未中率单独判定",
                f"{danger_miss_rate:.0%}",
            )
            if danger_miss_rate >= 0.70:
                status = "共振失效·危险尚可 ⚠️"
                advice = "共振确认全灭，危险剔除尚可；危险信号降级为仅供参考，不强制剔除"
            else:
                status = "区分力失真 ❌"
                advice = "共振全灭且危险未中率偏低 → 反哺标签失真，危险信号仅供参考"
        else:
            index = danger_miss_rate / resonate_hit_rate
            logger.info(
                "[反哺回验] 区分力指数 = 危险未中(%.2f) / 共振命中(%.2f) = %.3f",
                danger_miss_rate, resonate_hit_rate, index,
            )
            status, advice = _classify_discrimination(index)
    elif danger_miss_rate is not None:
        logger.info("[反哺回验] 共振样本为空，仅按危险未中率观察 (%.0f%%)", danger_miss_rate * 100)
        status = "仅危险样本"
        advice = "共振样本为空，仅按危险未中率观察"

    logger.info(
        "[反哺回验] 结论: 状态=%s 指数=%s 建议=%s",
        status, "N/A" if index is None else round(index, 3), advice,
    )

    return {
        "danger_miss_rate": danger_miss_rate,
        "resonate_hit_rate": resonate_hit_rate,
        "review_hit_rate": review_hit_rate,
        "index": index,
        "status": status,
        "advice": advice,
        "prev_coverage": cf.get("kill_coverage"),
        "danger_correct": sorted(danger - actual),
        "danger_wrong": sorted(danger & actual),
        "resonate_hit": sorted(resonate & actual),
        "resonate_miss": sorted(resonate - actual),
    }


def review_cross_feed_window(
    preds: List[dict],
    opened: Dict[str, Set[int]],
    n: int = CROSS_FEED_WINDOW_N,
) -> dict:
    """近N期杀号反哺区分力汇总（脚本 STEP2.5 复盘要求）。"""
    rows = []
    for pred in reversed(preds):
        period = pred.get("period", "")
        if period not in opened or not pred.get("cross_feed"):
            continue
        row = review_previous_cross_feed(pred, opened[period])
        row["period"] = period
        rows.append(row)
        if len(rows) >= n:
            break

    if not rows:
        logger.info("[近窗回测] 近%d期无有效反哺复盘样本，跳过", n)
        return {"n": 0, "periods": [], "index": None, "status": "无反哺复盘样本", "advice": "样本不足"}

    d_rates = [r["danger_miss_rate"] for r in rows if r.get("danger_miss_rate") is not None]
    r_rates = [r["resonate_hit_rate"] for r in rows if r.get("resonate_hit_rate") is not None]
    avg_dmr = sum(d_rates) / len(d_rates) if d_rates else None
    avg_rhr = sum(r_rates) / len(r_rates) if r_rates else None

    logger.info(
        "[近窗回测] 覆盖期=%s | 逐期: %s",
        [r["period"] for r in rows],
        [(r["period"], r.get("danger_miss_rate"), r.get("resonate_hit_rate")) for r in rows],
    )

    # 指数只对「共振命中率>0」的期次逐期计算再平均，避免 0 分母被均值稀释后抬出伪高指数
    per_period_indices: List[float] = []
    zero_resonate = 0
    for r in rows:
        dmr = r.get("danger_miss_rate")
        rhr = r.get("resonate_hit_rate")
        if dmr is None or rhr is None:
            continue
        if rhr <= 0:
            zero_resonate += 1
            logger.info("[近窗回测] 期%s 共振命中=0 → 计为共振全灭(安全跳过除法)", r["period"])
            continue
        per_period_indices.append(dmr / rhr)
        logger.info("[近窗回测] 期%s 单期指数=%.3f (危险未中%.2f/共振命中%.2f)", r["period"], dmr / rhr, dmr, rhr)

    index = None
    paired = sum(
        1
        for r in rows
        if r.get("danger_miss_rate") is not None and r.get("resonate_hit_rate") is not None
    )
    logger.info(
        "[近窗回测] 已配对=%d | 共振全灭期=%d | 可算单期指数=%d | 均值危险未中=%s 共振命中=%s",
        paired, zero_resonate, len(per_period_indices),
        "N/A" if avg_dmr is None else round(avg_dmr, 3),
        "N/A" if avg_rhr is None else round(avg_rhr, 3),
    )
    if paired == 0:
        status, advice = "样本不足", "近窗危险/共振样本不足"
    elif zero_resonate >= max(1, (paired + 1) // 2):
        # 半数及以上期次共振全灭 → 近窗区分力不可信（勿用稀释均值冒充有效）
        status = "近窗共振失效 ⚠️"
        advice = "近窗半数以上共振全灭 → 反哺区分力不可信，危险信号降级为仅供参考"
        if per_period_indices:
            index = sum(per_period_indices) / len(per_period_indices)
            logger.info("[近窗回测] 共振全灭过半但仍保留 %.0f 期有效指数，均值=%.3f", len(per_period_indices), index)
        else:
            logger.info("[近窗回测] 共振全灭过半且无有效单期指数 → 指数=NaN")
    elif per_period_indices:
        index = sum(per_period_indices) / len(per_period_indices)
        logger.info("[近窗回测] 近窗指数 = 均值(%.0f 期单期指数) = %.3f", len(per_period_indices), index)
        status, advice = _classify_discrimination(index)
    elif avg_rhr is not None and avg_rhr <= 0:
        status = "近窗共振失效 ⚠️"
        advice = "近窗共振命中率≈0 → 反哺区分力不可信，危险信号降级为仅供参考"
    else:
        status, advice = "样本不足", "近窗危险/共振样本不足"

    logger.info("[近窗回测] 结论: 状态=%s 指数=%s 建议=%s", status, "N/A" if index is None else round(index, 3), advice)

    return {
        "n": len(rows),
        "periods": [r["period"] for r in rows],
        "rows": rows,
        "avg_danger_miss_rate": avg_dmr,
        "avg_resonate_hit_rate": avg_rhr,
        "index": index,
        "status": status,
        "advice": advice,
    }


def to_log_dict(result: CrossFeedResult) -> dict:
    return {
        "danger": result.danger,
        "review": result.review,
        "resonate": result.resonate,
        "independent_kills": result.independent_kills,
        "danger_sources": {str(k): v for k, v in result.danger_sources.items()},
        "review_sources": {str(k): v for k, v in result.review_sources.items()},
        "resonate_sources": {str(k): v for k, v in result.resonate_sources.items()},
        "kill_coverage": round(result.kill_coverage, 4),
        "chaos_flag": result.chaos_flag,
        "stable_kill_boost": result.stable_kill_boost,
        "leak_downgrade": result.leak_downgrade,
        "sources": {s.name: s.numbers for s in result.sources},
        "advice": result.advice,
    }
