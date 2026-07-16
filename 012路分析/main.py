"""
012路分析 — KL8 分路统计规则引擎（增强 ML）
用法:
    python main.py              # 完整：分析+预测+分层号码 → 写 txt
    python main.py --analyze    # 仅深度分析
    python main.py --predict    # 仅分路比+分层号码 → 写 txt
    python main.py --review     # 复盘上期预测
    python main.py --backtest N # N 期回测
    python main.py --no-ml      # 关闭 ML
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.model_config import ModelConfig
from config.paths import OUTPUT_DIR, PRED_DIR, PRED_LOG, REPORT_JSON, REPORT_TXT
from core.association import analyze_association
from core.data_loader import DataLoader, KL8Draw
from core.distribution import analyze_distribution
from core.number_scorer import NumberScorer
from core.predictor import RoadPredictor
from core.road_mapper import fmt_ratio
from core.transition import TransitionModel

WIDTH = 70


def print_section(title: str) -> None:
    print(f"\n{'─' * WIDTH}")
    print(f"  {title}")
    print(f"{'─' * WIDTH}")


def fmt_nums(nums: Sequence[int], per_line: int = 10) -> str:
    lines = []
    for i in range(0, len(nums), per_line):
        chunk = nums[i : i + per_line]
        lines.append(" ".join(f"{n:02d}" for n in chunk))
    return "\n".join(lines)


def next_period(period: str) -> str:
    """下一期期号（开奖历史期内连续递增）。"""
    return str(int(period) + 1)


def build_cfg(args: argparse.Namespace) -> ModelConfig:
    cfg = ModelConfig()
    if args.no_ml:
        cfg.use_ml = False
    if args.window:
        cfg.window_short = args.window
    return cfg


def run_analyze(draws: List[KL8Draw], cfg: ModelConfig) -> dict:
    dist = analyze_distribution(
        draws,
        window=cfg.window_short,
        window_long=cfg.window_long,
        expected=cfg.expected_road,
        top_n=cfg.top_patterns,
    )
    trans = TransitionModel(draws)
    assoc = analyze_association(draws, expected=cfg.expected_road)
    dominant = trans.dominant_transition_table()

    print_section("分路分布")
    print(f"  全量均值: {tuple(round(x, 2) for x in dist['mean_all'])}")
    print(f"  近{cfg.window_short}期: {tuple(round(x, 2) for x in dist['mean_short'])}")
    print(f"  近{cfg.window_long}期: {tuple(round(x, 2) for x in dist['mean_long'])}")
    print(f"  期望约: {cfg.expected_road} (约 7:7:6)")
    print(f"  热冷偏离(近窗-期望): {tuple(round(x, 2) for x in dist['hot_cold']['dev'])}")
    print("  Top 形态:")
    for ratio, cnt, freq in dist["top_patterns"][:8]:
        print(f"    {ratio}  ×{cnt}  ({freq:.1%})")

    print_section("转移 / 主导路")
    last = draws[-1].road
    nxt = trans.next_distribution(last)
    top = sorted(nxt.items(), key=lambda x: -x[1])[:5]
    print(f"  本期 {fmt_ratio(last)} → 下期 Top:")
    for state, p in top:
        print(f"    {fmt_ratio(state)}  {p:.1%}")
    print("  主导路粗转移:")
    for frm, row in sorted(dominant.items()):
        parts = " ".join(f"{k}:{v:.0%}" for k, v in sorted(row.items()))
        print(f"    主导{frm} → {parts}")

    print_section("Streak / 关联")
    for r, info in assoc["streaks"].items():
        direction = {1: "偏高", -1: "偏低", 0: "持平"}.get(info["current_dir"], "?")
        print(
            f"  {r}路: 当前{direction}×{info['current_len']}  "
            f"历史最长高/低={info['max_high']}/{info['max_low']}"
        )
    if assoc.get("sum_cross"):
        print("  主导路×和值档:")
        for k, buckets in assoc["sum_cross"].items():
            print(f"    {k}: {buckets}")

    return {"distribution": dist, "dominant": dominant, "association": assoc}


def run_predict(draws: List[KL8Draw], cfg: ModelConfig) -> dict:
    pred = RoadPredictor(draws, cfg).predict()
    scores = NumberScorer(draws, cfg).score(
        pred["best"], ml_proba=pred.get("number_proba")
    )

    print_section("下期分路比预测")
    print(f"  最佳: {fmt_ratio(pred['best'])}  置信度={pred['confidence']:.2f}")
    print(f"  ML启用: {pred['ml_used']}")
    print("  Top3:")
    for i, s in enumerate(pred["top3"], 1):
        print(f"    {i}. {fmt_ratio(s)}")

    print_section("分层推荐")
    for name, key in (
        ("高置信推荐", "rec_high"),
        ("中置信推荐", "rec_mid"),
        ("低置信推荐", "rec_low"),
    ):
        print(f"  {name} ({len(scores[key])}):")
        print("    " + fmt_nums(scores[key]).replace("\n", "\n    "))

    print_section("分层杀号")
    for name, key in (("高置信杀号", "kill_high"), ("中置信杀号", "kill_mid")):
        print(f"  {name} ({len(scores[key])}):")
        print("    " + fmt_nums(scores[key]).replace("\n", "\n    "))

    return {"prediction": pred, "scores": scores}


def build_prediction_txt(
    *,
    based_on: KL8Draw,
    target_period: str,
    pred_block: dict,
    analysis: Optional[dict] = None,
) -> str:
    """生成可读的每日预测 txt 全文。"""
    pred = pred_block["prediction"]
    scores = pred_block["scores"]
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("012路分析 — 每日预测报告")
    lines.append("=" * 70)
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"数据依据期: {based_on.period}  开奖日={based_on.date}  分路={fmt_ratio(based_on.road)}")
    lines.append(f"预测目标期: {target_period}")
    lines.append("数据源: data/kl8_history_final.txt（开奖历史）")
    lines.append("说明: daily_points.txt 为点位数据，本系统不参与开奖预测。")
    lines.append("")
    lines.append("-" * 70)
    lines.append("一、下期分路比预测 (0路:1路:2路)")
    lines.append("-" * 70)
    lines.append(f"最佳预测: {fmt_ratio(pred['best'])}")
    lines.append(f"置信度:   {pred['confidence']:.2f}")
    lines.append(f"ML启用:   {pred['ml_used']}")
    lines.append("Top3候选:")
    for i, s in enumerate(pred["top3"], 1):
        lines.append(f"  {i}. {fmt_ratio(s)}")
    lines.append("")
    lines.append("-" * 70)
    lines.append("二、分层推荐号码")
    lines.append("-" * 70)
    for title, key in (
        ("高置信推荐", "rec_high"),
        ("中置信推荐", "rec_mid"),
        ("低置信推荐", "rec_low"),
    ):
        nums = scores[key]
        lines.append(f"[{title}] 共{len(nums)}个")
        lines.append(fmt_nums(nums))
        lines.append("")
    lines.append("-" * 70)
    lines.append("三、分层杀号")
    lines.append("-" * 70)
    for title, key in (("高置信杀号", "kill_high"), ("中置信杀号", "kill_mid")):
        nums = scores[key]
        lines.append(f"[{title}] 共{len(nums)}个")
        lines.append(fmt_nums(nums))
        lines.append("")
    if analysis and "distribution" in analysis:
        dist = analysis["distribution"]
        lines.append("-" * 70)
        lines.append("四、近期分路摘要")
        lines.append("-" * 70)
        lines.append(f"全量均值: {tuple(round(x, 2) for x in dist['mean_all'])}")
        lines.append(f"近窗均值: {tuple(round(x, 2) for x in dist['mean_short'])}")
        lines.append(f"热冷偏离: {tuple(round(x, 2) for x in dist['hot_cold']['dev'])}")
        lines.append("Top形态:")
        for ratio, cnt, freq in dist["top_patterns"][:5]:
            lines.append(f"  {ratio}  ×{cnt} ({freq:.1%})")
        lines.append("")
    lines.append("=" * 70)
    lines.append("免责声明: 快乐8近随机，本报告仅供统计分析参考，不构成投注建议。")
    lines.append("=" * 70)
    lines.append("")
    return "\n".join(lines)


def append_pred_log(
    based_on_period: str,
    target_period: str,
    payload: dict,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "based_on_period": based_on_period,
        "target_period": target_period,
        "best": list(payload["prediction"]["best"]),
        "top3": [list(x) for x in payload["prediction"]["top3"]],
        "confidence": payload["prediction"]["confidence"],
        "ml_used": payload["prediction"]["ml_used"],
        "rec_high": payload["scores"]["rec_high"],
        "rec_mid": payload["scores"]["rec_mid"],
        "rec_low": payload["scores"]["rec_low"],
        "kill_high": payload["scores"]["kill_high"],
        "kill_mid": payload["scores"]["kill_mid"],
    }
    with open(PRED_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_prediction_files(
    txt_body: str,
    data: dict,
    target_period: str,
) -> Path:
    """写入 latest_report.txt + predictions/prediction_{期号}.txt + json。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PRED_DIR.mkdir(parents=True, exist_ok=True)

    period_txt = PRED_DIR / f"prediction_{target_period}.txt"
    period_txt.write_text(txt_body, encoding="utf-8")
    REPORT_TXT.write_text(txt_body, encoding="utf-8")

    def _default(o: Any):
        if isinstance(o, tuple):
            return list(o)
        raise TypeError(type(o))

    REPORT_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=_default),
        encoding="utf-8",
    )
    return period_txt


def run_review(loader: DataLoader) -> None:
    print_section("复盘上期预测")
    if not PRED_LOG.exists():
        print("  无预测日志 pred_logs.jsonl，请先运行预测。")
        return
    lines = [ln.strip() for ln in PRED_LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        print("  预测日志为空。")
        return
    last = json.loads(lines[-1])
    based = last["based_on_period"]
    target = last.get("target_period") or next_period(based)
    hist = loader.history
    actual = next((d for d in hist if d.period == target), None)
    if actual is None:
        # 兼容旧日志：取 based 的下一期
        idx = next((i for i, d in enumerate(hist) if d.period == based), None)
        if idx is None or idx + 1 >= len(hist):
            print(f"  目标期 {target} 尚无开奖可复盘（请先更新 kl8_history_final.txt）。")
            return
        actual = hist[idx + 1]
    best = tuple(last["best"])
    top3 = [tuple(x) for x in last["top3"]]
    exact = actual.road == best
    in_top3 = actual.road in top3
    opened = set(actual.numbers)
    kill = set(last["kill_high"] + last["kill_mid"])
    rec = set(last["rec_high"] + last["rec_mid"] + last["rec_low"])
    kill_miss = len(kill - opened) / len(kill) if kill else 0.0
    rec_hit = len(rec & opened)

    print(f"  预测基于期: {based} → 目标期: {target}")
    print(f"  实际期: {actual.period}  分路={fmt_ratio(actual.road)}")
    print(f"  预测最佳: {fmt_ratio(best)}  精确命中={exact}  Top3命中={in_top3}")
    print(f"  杀号未开出率: {kill_miss:.1%}  (杀{len(kill)}个)")
    print(f"  推荐层覆盖开出: {rec_hit}/{len(opened)}  (推荐池{len(rec)})")


def run_backtest(draws: List[KL8Draw], cfg: ModelConfig, n: int) -> None:
    print_section(f"回测近 {n} 期")
    if len(draws) < n + cfg.lookback_k + 5:
        n = max(1, len(draws) - cfg.lookback_k - 5)
        print(f"  可用期数不足，截断为 N={n}")

    exact = top3_hit = 0
    kill_ok = kill_total = 0
    rec_cover = []
    start = len(draws) - n
    for i in range(start, len(draws)):
        train = draws[:i]
        actual = draws[i]
        bt_cfg = ModelConfig(**{**cfg.__dict__})
        pred = RoadPredictor(train, bt_cfg).predict()
        scores = NumberScorer(train, bt_cfg).score(pred["best"])
        if actual.road == pred["best"]:
            exact += 1
        if actual.road in pred["top3"]:
            top3_hit += 1
        kill = set(scores["kill_high"] + scores["kill_mid"])
        opened = set(actual.numbers)
        kill_total += len(kill)
        kill_ok += len(kill - opened)
        rec = set(scores["rec_high"] + scores["rec_mid"] + scores["rec_low"])
        rec_cover.append(len(rec & opened))

    print(f"  分路精确命中: {exact}/{n} = {exact / n:.1%}")
    print(f"  分路 Top3 命中: {top3_hit}/{n} = {top3_hit / n:.1%}")
    print(
        f"  杀号未开出率: {kill_ok}/{kill_total} = "
        f"{(kill_ok / kill_total if kill_total else 0):.1%}"
    )
    print(f"  推荐层覆盖开出均值: {sum(rec_cover) / len(rec_cover):.2f} / 20")
    print("  说明: 快乐8近随机，指标仅供参考，不构成投注建议。")


def main() -> int:
    parser = argparse.ArgumentParser(description="012路分析 CLI")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--predict", action="store_true")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--backtest", type=int, nargs="?", const=30)
    parser.add_argument("--no-ml", action="store_true")
    parser.add_argument("--window", type=int, default=None)
    args = parser.parse_args()

    cfg = build_cfg(args)
    loader = DataLoader()
    try:
        loader.load()
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    draws = loader.history
    if not draws:
        print("❌ 历史为空")
        return 1

    latest = loader.latest
    target = next_period(latest.period)
    print(f"╔{'═' * (WIDTH - 2)}╗")
    print(
        f"║  012路分析  依据期 {latest.period} → 预测期 {target}  "
        f"分路 {fmt_ratio(latest.road):<{WIDTH - 42}}║"
    )
    print(f"╚{'═' * (WIDTH - 2)}╝")
    if loader.skipped:
        print(f"  (跳过异常行 {loader.skipped} 条)")

    do_all = not (args.analyze or args.predict or args.review or args.backtest is not None)

    report_data: Dict[str, Any] = {
        "based_on_period": latest.period,
        "target_period": target,
        "latest_road": latest.road,
    }

    if args.review:
        run_review(loader)
        return 0

    if args.backtest is not None:
        run_backtest(draws, cfg, args.backtest)
        return 0

    analysis = None
    if do_all or args.analyze:
        analysis = run_analyze(draws, cfg)
        report_data["analysis"] = analysis

    if do_all or args.predict:
        pred_block = run_predict(draws, cfg)
        report_data["prediction"] = pred_block["prediction"]
        report_data["scores"] = {
            k: pred_block["scores"][k]
            for k in ("rec_high", "rec_mid", "rec_low", "kill_high", "kill_mid")
        }
        append_pred_log(latest.period, target, pred_block)
        txt_body = build_prediction_txt(
            based_on=latest,
            target_period=target,
            pred_block=pred_block,
            analysis=analysis if do_all else None,
        )
        out_path = write_prediction_files(txt_body, report_data, target)
        print(f"\n  预测TXT已写入: {out_path}")
        print(f"  同步副本:       {REPORT_TXT}")
        print(f"  JSON:           {REPORT_JSON}")
    elif do_all or args.analyze:
        # 仅分析时写简要 txt
        body = (
            f"012路分析（仅分析）\n"
            f"依据期={latest.period} 分路={fmt_ratio(latest.road)}\n"
            f"生成时间={datetime.now().isoformat(timespec='seconds')}\n"
        )
        REPORT_TXT.write_text(body, encoding="utf-8")
        print(f"\n  报告已写入: {REPORT_TXT}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
