# -*- coding: utf-8 -*-
"""研究引擎桥接（vendored kl8_engine → A 的研究对比报告）。

边界：
- 只读 A 的 canonical 历史/点位；
- 调用研究引擎的 run_pipeline(no_sync=True)，输出到 A 的 output/research/<period>/；
- 不写 A 的预注册台账、不改变 A 的生产 Top5。

C 的 loader 内部按期号排序，因此可直接读取 A 的倒序历史文件。
vendored 后该 loader 位于 A 的 research/kl8_engine/，行为不变。
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import timedelta
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kl8.points_input import next_period_after

DISCLAIMER = (
    "本报告为研究引擎输出，仅供观察，不构成投注建议。"
    "快乐8 每期开奖为独立随机事件，历史统计特征不保证在未来重现。"
)

# C 引擎默认参数（dataclass 与 CLI 共用，避免两处漂移）
DEFAULT_EPOCHS = 10          # 研究对比默认训练轮数（C 默认 25，研究路径取较小值）
DEFAULT_SEQ_LEN = 10         # 时序窗口
DEFAULT_DL_WEIGHT = 0.55     # Transformer 分量权重
DEFAULT_BUDGET = 20          # 缩水注数预算
DEFAULT_TOP_K = 10           # 报告展示的分数 TopK


@dataclass
class ResearchConfig:
    engine_root: Path
    output_dir: Path
    history_path: Path
    points_path: Path
    period: int | None = None
    points: Sequence[int] | None = None
    epochs: int = DEFAULT_EPOCHS
    seq_len: int = DEFAULT_SEQ_LEN
    dl_weight: float = DEFAULT_DL_WEIGHT
    budget: int = DEFAULT_BUDGET
    fusion: str = "borda"
    points_mode: str = "compare"
    comparison: bool = True
    engine_output_dir: Path | None = None


def _load_kv(line: str) -> dict[str, str]:
    return dict(kv.split(":", 1) for kv in line.split(",") if ":" in kv)


def _history_lines(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8-sig").splitlines()
            if ln.strip()]


def latest_history_draw(path: Path) -> tuple[int, str]:
    """返回 (最新期号, 日期字符串)；缺失/空档案报错。"""
    best: tuple[int, str] | None = None
    for line in _history_lines(path):
        parts = _load_kv(line)
        try:
            period = int(parts["period"])
        except (KeyError, ValueError):
            continue
        date_str = parts.get("date", "")
        if best is None or period > best[0]:
            best = (period, date_str)
    if best is None:
        raise ValueError(f"{path} 中没有可解析的 period")
    return best


def latest_history_period(path: Path) -> int:
    return latest_history_draw(path)[0]


def default_target_period(path: Path) -> int:
    """按 A 的跨年规则推断下一期，禁止 latest+1。"""
    period, date_str = latest_history_draw(path)
    try:
        day = _date.fromisoformat(date_str)
    except ValueError:
        day = _date.today()
    return next_period_after(period, day + timedelta(days=1))


def points_for_period(path: Path, period: int) -> list[int] | None:
    for line in _history_lines(path):
        parts = _load_kv(line)
        if parts.get("period") == f"{period:07d}" or parts.get("period") == str(period):
            return [int(x) for x in parts.get("points", "").split()]
    return None


def history_for_period(canonical: Path, period: int | None,
                       output_dir: Path) -> Path:
    """period=None 或 period=latest+1 用完整档案；更早的期裁剪到 < period。"""
    latest = latest_history_period(canonical)
    if period is None or period > latest:
        return canonical
    if period == latest + 1:
        return canonical
    kept = []
    for line in _history_lines(canonical):
        try:
            p = int(_load_kv(line)["period"])
        except (KeyError, ValueError):
            continue
        if p < period:
            kept.append(line)
    if not kept:
        raise ValueError(f"没有早于 {period} 的历史，无法裁剪")
    out = output_dir / f"history_upto_{period}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(("\n".join(kept) + "\n").replace("\n", "\r\n").encode("utf-8"))
    return out


def _top_scores(scores: Any, k: int = DEFAULT_TOP_K) -> list[int]:
    if scores is None:
        return []
    vals = [float(x) for x in scores]
    return [i + 1 for i in sorted(range(len(vals)), key=lambda i: -vals[i])[:k]]


def _ensemble_summary(ens: Any) -> dict:
    if ens is None:
        return {}
    return {
        "gold_pool": [int(x) for x in getattr(ens, "gold_pool", ())],
        "main_pool": [int(x) for x in getattr(ens, "main_pool", ())],
        "shrinkage_pool_30": [int(x) for x in getattr(ens, "shrinkage_pool_30", ())],
        "full_order_top10": [int(x) for x in getattr(ens, "full_order", ())[:10]],
        "scores_top10": _top_scores(getattr(ens, "scores", None), DEFAULT_TOP_K),
    }


def _assert_period(requested: int, reported: int) -> None:
    if int(reported) != int(requested):
        raise ValueError(
            f"研究引擎返回期号 {reported} 与请求 {requested} 不一致；"
            f"可能是跨年期号推断差异（C 内部使用 latest+1），已中止以避免错标。")


def summarize_result(result: Any) -> dict:
    sh = getattr(result, "shrinkage", None)
    rv = getattr(result, "review", None)
    out = {
        "period": int(getattr(result, "target_period", 0)),
        "borda": _ensemble_summary(getattr(result, "ensemble", None)),
        "weighted": _ensemble_summary(getattr(result, "comparison_ensemble", None)),
        "fusion_mode": getattr(result, "fusion_mode", ""),
        "comparison_fusion_mode": getattr(result, "comparison_fusion_mode", None),
        "shrinkage": {
            "final_tickets": int(getattr(sh, "final_tickets_count", 0) or 0),
            "total_cost_yuan": int(getattr(sh, "total_cost_yuan", 0) or 0),
            "hit5_guarantee_prob": float(getattr(sh, "hit5_guarantee_prob", 0.0) or 0.0),
            "hit4_or_better_prob": float(getattr(sh, "hit4_or_better_prob", 0.0) or 0.0),
            "hit3_or_better_prob": float(getattr(sh, "hit3_or_better_prob", 0.0) or 0.0),
            "expected_prize_per_draw": float(getattr(sh, "expected_prize_per_draw", 0.0) or 0.0),
            "roi_percentage": float(getattr(sh, "roi_percentage", 0.0) or 0.0),
        } if sh is not None else {},
        "review": {
            "target_period": int(getattr(rv, "target_period", 0) or 0),
            "actual_period": int(getattr(rv, "actual_period", 0) or 0),
            "gold_hits": int(getattr(rv, "gold_hits", 0) or 0),
            "gold_total": int(getattr(rv, "gold_total", 0) or 0),
            "main_hits": int(getattr(rv, "main_hits", 0) or 0),
            "main_total": int(getattr(rv, "main_total", 0) or 0),
            "top20_hits": int(getattr(rv, "top20_hits", 0) or 0),
            "top20_total": int(getattr(rv, "top20_total", 0) or 0),
            "pool30_hits": int(getattr(rv, "pool30_hits", 0) or 0),
            "pool30_total": int(getattr(rv, "pool30_total", 0) or 0),
            "ranking_auc": getattr(rv, "ranking_auc", None),
        } if rv is not None else {},
        "warnings": [str(x) for x in getattr(result, "warnings", ())],
        "elapsed_seconds": float(getattr(result, "elapsed_seconds", 0.0) or 0.0),
    }
    return out


def _ledger_top5(period: int, path: Path | None = None) -> list[int] | None:
    path = Path(path) if path else ROOT / "data" / "state" / "prereg_ledger.jsonl"
    if not path.exists():
        return None
    found: tuple[str, list[int]] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("model") != "main" or int(rec.get("period", 0)) != int(period):
            continue
        core = [int(x) for x in rec.get("core", [])]
        if len(core) != 5:
            continue
        stamp = str(rec.get("locked_at", ""))
        if found is None or stamp > found[0]:
            found = (stamp, core)
    return found[1] if found else None


def _report_top5(period: int, history_path: Path,
                 output_root: Path | None = None) -> list[int] | None:
    date_str = ""
    for line in _history_lines(history_path):
        parts = _load_kv(line)
        if parts.get("period") in (str(period), f"{period:07d}"):
            date_str = parts.get("date", "")
            break
    if not date_str:
        return None
    output_root = Path(output_root) if output_root else ROOT / "output"
    report = output_root / date_str / "daily_report.md"
    if not report.exists():
        return None
    text = report.read_text(encoding="utf-8-sig")
    nl = chr(10)
    m = re.search(r"###\s*6\.1[^" + nl + r"]*" + nl + r"(.*?)(?=" + nl + r"###|" + nl + r"##|\Z)", text, re.S)
    if not m:
        return None
    nums = [int(x) for x in re.findall(r"^\|\s*\*\*(\d{2})\*\*", m.group(1), re.M)]
    return nums[:5] if len(nums) >= 5 else None


def _a_top5(period: int, history_path: Path,
            snapshot_path: Path | None = None,
            ledger_path: Path | None = None,
            output_root: Path | None = None) -> tuple[list[int] | None, str]:
    """按 快照 → 台账 → 日报 的顺序取 A 生产 Top5；都不存在时返回 (None, "none")。"""
    snap = Path(snapshot_path) if snapshot_path else (
        ROOT / "data" / "state" / "last_prediction_main.json")
    if snap.exists():
        try:
            data = json.loads(snap.read_text(encoding="utf-8"))
            if int(data.get("period", 0)) == int(period):
                core = [int(x) for x in data.get("core", [])]
                if len(core) == 5:
                    return core, "snapshot"
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    core = _ledger_top5(period, ledger_path)
    if core:
        return core, "ledger"
    core = _report_top5(period, history_path, output_root)
    if core:
        return core, "daily_report"
    return None, "none"


def render_markdown(summary: dict, cfg: ResearchConfig,
                    a_top5: list[int] | None = None) -> str:
    if a_top5 is None:
        a_top5 = summary.get("a_top5")
    def fmt(nums: Sequence[int]) -> str:
        return " ".join(f"{int(n):02d}" for n in nums)

    b = summary.get("borda", {})
    w = summary.get("weighted", {})
    sh = summary.get("shrinkage", {})
    rv = summary.get("review", {})
    lines = [
        f"# 研究引擎对比 · 第 {summary.get('period')} 期",
        "",
        "> 本报告由 A 内 vendored 的研究引擎（research/kl8_engine）产生，**不进入 A 的生产 Top5、"
        "不写入预注册台账**，仅供观察与对比。",
        "",
        f"- 数据源：`{summary.get('history_used', cfg.history_path)}`",
        f"- 点位源：`{cfg.points_path}`",
        f"- 融合：Borda（正式）/ {summary.get('comparison_fusion_mode') or '未启用'}（对照）",
        f"- 耗时：{summary.get('elapsed_seconds', 0):.1f}s",
        "",
        "## 主选对比",
        "",
        "| 对象 | 号码 |",
        "|---|---|",
        f"| A 生产 Top5 | {fmt(a_top5) if a_top5 else '—（无 A 生产台账/日报）'} |",
        f"| 研究 Borda 金胆池 | {fmt(b.get('gold_pool', []))} |",
        f"| 研究 Borda 主选（{len(b.get('main_pool', []))} 码） | {fmt(b.get('main_pool', []))} |",
        f"| 研究加权主选（{len(w.get('main_pool', [])) if w else 0} 码） | "
        f"{fmt(w.get('main_pool', [])) if w else '—'} |",
        f"| 研究 30 码大底 | {fmt(b.get('shrinkage_pool_30', []))} |",
        "",
    ]
    if sh:
        lines += [
            "## 30 码缩水指标（研究口径）",
            "",
            f"- 最终注数：{sh.get('final_tickets')}",
            f"- 成本：{sh.get('total_cost_yuan')} 元",
            f"- 保 5 / 保 4+ / 保 3+：{float(sh.get('hit5_guarantee_prob', 0)):.2f}% / "
            f"{float(sh.get('hit4_or_better_prob', 0)):.2f}% / "
            f"{float(sh.get('hit3_or_better_prob', 0)):.2f}%",
            f"- 单期期望奖金：{float(sh.get('expected_prize_per_draw', 0)):.2f} 元；"
            f"ROI：{float(sh.get('roi_percentage', 0)):.2f}%",
            "",
        ]
    if rv:
        lines += [
            "## 上一期复盘 / AUC",
            "",
            f"- 期号：{rv.get('actual_period')}（推荐目标 {rv.get('target_period')}）",
            f"- 金胆 {rv.get('gold_hits')}/{rv.get('gold_total')}；"
            f"主选 {rv.get('main_hits')}/{rv.get('main_total')}；"
            f"Top20 {rv.get('top20_hits')}/{rv.get('top20_total')}；"
            f"30 码 {rv.get('pool30_hits')}/{rv.get('pool30_total')}",
            f"- 排序 AUC：{rv.get('ranking_auc')}（0.5=随机）",
            "",
        ]
    if summary.get("warnings"):
        lines += ["## 告警", ""] + [f"- {x}" for x in summary["warnings"]] + [""]
    lines += ["---", "", f"> **免责声明**：{DISCLAIMER}", ""]
    return "\n".join(lines)


def run_research(cfg: ResearchConfig) -> dict:
    engine_pipeline = cfg.engine_root / "kl8_engine" / "pipeline.py"
    if not engine_pipeline.exists():
        raise FileNotFoundError(
            f"找不到研究引擎：{engine_pipeline}（默认 A 的 research/，可用 --engine-root 指定）")
    if str(cfg.engine_root) not in sys.path:
        sys.path.insert(0, str(cfg.engine_root))
    from kl8_engine.pipeline import run_pipeline  # type: ignore

    period = cfg.period if cfg.period is not None else default_target_period(
        cfg.history_path)
    history = history_for_period(cfg.history_path, period, cfg.output_dir)
    points = list(cfg.points) if cfg.points is not None else points_for_period(
        cfg.points_path, period)
    if not points:
        raise ValueError(f"点位档案中找不到 {period} 期点位")

    progress: list[str] = []
    engine_out = cfg.engine_output_dir or (ROOT / "output" / "research" / "engine_state")
    engine_out.mkdir(parents=True, exist_ok=True)
    result = run_pipeline(
        history_path=str(history),
        output_dir=str(engine_out),
        no_sync=True,
        dl_weight=cfg.dl_weight,
        seq_len=cfg.seq_len,
        epochs=cfg.epochs,
        budget_shrinkage=cfg.budget,
        points=points,
        points_mode=cfg.points_mode,
        fusion_mode=cfg.fusion,
        comparison=cfg.comparison,
        progress=progress.append,
    )
    summary = summarize_result(result)
    _assert_period(period, int(summary.get("period", 0)))
    a_top5, a_source = _a_top5(period, cfg.history_path)
    summary["a_top5"] = a_top5
    summary["a_top5_source"] = a_source
    summary["requested_period"] = period
    summary["history_used"] = str(history)
    summary["points"] = points
    summary["progress"] = progress[-10:]
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    (cfg.output_dir / "research_compare.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (cfg.output_dir / "research_compare.md").write_text(
        render_markdown(summary, cfg, a_top5), encoding="utf-8", newline="\r\n")
    return summary
