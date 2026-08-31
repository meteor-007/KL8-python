"""
KillSeeker V1.0 — KL8杀号预测系统
核心逻辑: 引擎评分越低 = 越不可能出 = 高置信杀号
目标: 杀号命中率≥75%

⚠️  系统已于 2026-07-01 起从全流程聚合器中分出，作为【独立杀号工具】使用。
原因：杀号功能是定胆系统的互补，不属于聚合范围。
独立用法:
    python main.py              # 完整杀号分析
    python main.py --predict    # 仅杀号预测
    python main.py --review     # 复盘上期杀号
    python main.py --full       # 完整流程(复盘+预测)
    python main.py --full --as-of PERIOD  # 截断历史补跑（预测=PERIOD+1）
    python main.py --backtest N # N期回测
    python main.py --diagnose   # 系统诊断
"""
from __future__ import annotations
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT.parent
PROJ_DIR = DATA_DIR.parent

for p in [str(PROJ_DIR), str(DATA_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# V1.0 每日幂等校验: 仓库根入 path + 导入失败时静默放行（绝不阻断主流程）
try:
    from daily_run_guard import guard_daily_run, mark_daily_run_done, kl8_target_date
except Exception:
    guard_daily_run = lambda *a, **k: False
    mark_daily_run_done = lambda *a, **k: None
    kl8_target_date = lambda: None

from kill_seeker.config.paths import KL8_HISTORY_FILE, KILL_LOGS, KILL_REPORT, OUTPUT_DIR
from kill_seeker.config.model_config import ModelConfig
from kill_seeker.core.data_loader import DataLoader
from kill_seeker.core.similarity_matcher import SimilarityMatcher
from kill_seeker.core.density_detector import DensityDetector
from kill_seeker.core.pattern_recognizer import PatternRecognizer
from kill_seeker.core.curve_analyzer import CurveAnalyzer
from kill_seeker.core.kill_predictor import KillPredictor
from kill_seeker.core.cross_feed import (
    run_cross_feed,
    review_previous_cross_feed,
    review_cross_feed_window,
    CROSS_FEED_WINDOW_N,
    to_log_dict,
)
from kill_seeker.core.number_feed_review import write_number_feed_reports


WIDTH = 70


def fmt_nums(numbers: list[int], per_line: int = 10) -> str:
    """格式化号码列表，每行 per_line 个"""
    lines = []
    for i in range(0, len(numbers), per_line):
        chunk = numbers[i:i + per_line]
        lines.append(", ".join(f"{n:02d}" for n in chunk))
    return "\n".join(lines)


def print_section(title: str) -> None:
    print(f"\n{'─' * WIDTH}")
    print(f"  {title}")
    print(f"{'─' * WIDTH}")


def print_banner(title: str) -> None:
    print(f"\n╔{'═' * (WIDTH - 2)}╗")
    print(f"║  {title:<{WIDTH - 5}}║")
    print(f"╚{'═' * (WIDTH - 2)}╝")


def print_kill_box(title: str, numbers: list[int], emoji: str, note: str = "") -> None:
    note_str = f"  ({note})" if note else ""
    print(f"  ┌{'─' * (WIDTH - 4)}┐")
    print(f"  │ {emoji} {title}{note_str}")
    for line in fmt_nums(numbers, 10).split("\n"):
        print(f"  │   {line}")
    print(f"  └{'─' * (WIDTH - 4)}┘")


def rate_badge(rate: float, target: float = 0.70) -> str:
    if rate >= target:
        return "✅ 达标"
    if rate >= target - 0.05:
        return "⚠️ 接近"
    return "❌ 偏低"


def print_hit_bar(label: str, hit: int, total: int, target: float = 0.70) -> None:
    rate = hit / total if total else 0.0
    bar_len = 20
    filled = min(bar_len, int(rate * bar_len))
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"  {label:<14} {hit:>2}/{total:<2}  {rate:>6.1%}  [{bar}]  {rate_badge(rate, target)}")


def load_all_predictions() -> list[dict]:
    if not KILL_LOGS.exists():
        return []
    preds = []
    with open(KILL_LOGS, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                preds.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return preds


def review_prediction(pred: dict, actual_set: set[int]) -> dict:
    high_kills = set(pred.get("high_conf_kills", []))
    mid_kills = set(pred.get("mid_conf_kills", []))
    low_kills = set(pred.get("low_conf_kills", []))
    all_kills = set(pred.get("all_kills", []))
    safe_nums = set(pred.get("safe_numbers", []))
    return {
        "period": pred.get("period", ""),
        "high_hit": len(high_kills - actual_set),
        "high_total": len(high_kills),
        "mid_hit": len(mid_kills - actual_set),
        "mid_total": len(mid_kills),
        "low_hit": len(low_kills - actual_set),
        "low_total": len(low_kills),
        "all_hit": len(all_kills - actual_set),
        "all_total": len(all_kills),
        "safe_hit": len(safe_nums & actual_set),
        "safe_total": len(safe_nums),
        "high_miss": sorted(high_kills & actual_set),
        "mid_miss": sorted(mid_kills & actual_set),
    }


def run_recent_reviews(data_loader: DataLoader, n: int = 10) -> None:
    """复盘最近N期已开奖预测，汇总命中率趋势"""
    preds = load_all_predictions()
    if not preds:
        return
    opened = {d.period: set(d.numbers) for d in data_loader.history}
    results = []
    seen = set()
    for pred in reversed(preds):
        period = pred.get("period", "")
        if period in seen or period not in opened:
            continue
        seen.add(period)
        results.append(review_prediction(pred, opened[period]))
        if len(results) >= n:
            break
    if not results:
        return

    print_section(f"📈 近{len(results)}期杀号命中率汇总")
    print(f"  {'期号':<10} {'高置信':>8} {'中置信':>8} {'全部':>8} {'保留':>8}  状态")
    print(f"  {'─' * 10} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8}  {'─' * 6}")
    for r in reversed(results):
        hr = r["high_hit"] / r["high_total"] if r["high_total"] else 0
        mr = r["mid_hit"] / r["mid_total"] if r["mid_total"] else 0
        ar = r["all_hit"] / r["all_total"] if r["all_total"] else 0
        sr = r["safe_hit"] / r["safe_total"] if r["safe_total"] else 0
        flag = "✅" if ar >= 0.75 else ("⚠️" if ar >= 0.70 else "❌")
        print(f"  {r['period']:<10} {hr:>7.0%} {mr:>8.0%} {ar:>7.0%} {sr:>7.0%}  {flag}")

    print(f"\n  汇总均值 ({len(results)}期):")
    th = sum(r["high_hit"] for r in results)
    th_t = sum(r["high_total"] for r in results)
    tm = sum(r["mid_hit"] for r in results)
    tm_t = sum(r["mid_total"] for r in results)
    ta = sum(r["all_hit"] for r in results)
    ta_t = sum(r["all_total"] for r in results)
    ts = sum(r["safe_hit"] for r in results)
    ts_t = sum(r["safe_total"] for r in results)
    print_hit_bar("高置信杀号", th, th_t)
    print_hit_bar("中置信杀号", tm, tm_t, 0.65)
    print_hit_bar("全部杀号", ta, ta_t, 0.75)
    print_hit_bar("保留号命中", ts, ts_t, 0.25)
    all_rate = ta / ta_t if ta_t else 0
    print(f"\n  📐 相对瞎蒙基线(75%): {(all_rate / 0.75 - 1) * 100:+.1f}%")
    print_section("🔬 命中率深度优化结论")
    print("  已做消融: 权重重分配 / 纯评分杀号 / decade=4|6|8|10")
    print("  近窗回测: decade约束改动命中率无差异 → 不调参")
    print("  决策: 不自动改引擎权重（防过拟合）；不引入 Hurst/自适应复杂度")
    print("  已精简: DefenseConfig死链路 / 反哺仅人工建议")
    print("  2026-08-06: 形态识别引擎已恢复（pattern 权重 0.15，四引擎归一化）；若后续回测确认无增益可再归零")
    if all_rate < 0.75:
        print("  ⚠️ 近窗低于75%目标 → 实战以高置信杀号缩水为主，观察区降权")
    else:
        print("  ✅ 近窗达标 → 维持当前四引擎(相似+密集+形态+曲线)配置")


def verify_persistence(target_period: str) -> None:
    print_banner("STEP 3 结果持久化与环境清理")
    print_section("💾 结果持久化校验")
    if not KILL_LOGS.exists():
        print("  ❌ kill_logs.jsonl 不存在")
        return
    found = False
    has_cf = False
    with open(KILL_LOGS, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("period") == target_period:
                    found = True
                    has_cf = bool(entry.get("cross_feed"))
                    break
            except json.JSONDecodeError:
                continue
    print(f"  {'✅' if found else '❌'} logs/kill_logs.jsonl 已写入 {target_period} 期记录")
    print(f"  {'✅' if has_cf else '⚠️'} 含 STEP2.5 cross_feed 字段")
    print(f"  {'✅' if KILL_REPORT.exists() else '❌'} logs/kill_report.txt 人类可读报告")
    print("  ℹ️  脚本中的 kill_predictions.json 已统一为 kill_logs.jsonl")


def cleanup_pycache() -> None:
    removed = 0
    for cache_dir in PROJECT_ROOT.rglob("__pycache__"):
        if cache_dir.is_dir():
            for p in cache_dir.iterdir():
                p.unlink(missing_ok=True)
            cache_dir.rmdir()
            removed += 1
    print_section("🧹 环境清理")
    print(f"  ✅ 已清理 {removed} 个 __pycache__ 目录")


def print_header():
    print("=" * WIDTH)
    print("  KillSeeker V1.0 — KL8杀号预测系统")
    print("  核心: 低分=高置信杀号 | 目标: 杀号命中率≥75%")
    print("  角色: 缩水杀号工具 · 不做多主战")
    print("=" * WIDTH)


def check_data_freshness(data_loader: DataLoader) -> dict:
    print("\n📊 数据预检:")
    status = {}
    if KL8_HISTORY_FILE.exists():
        latest = data_loader.latest_period
        total = data_loader.total_periods
        print(f"  ✅ kl8_history: {latest}期, 共{total}期")
        status["kl8_history"] = True
        status["latest_period"] = latest
        status["total_periods"] = total
    else:
        print(f"  ❌ kl8_history: 文件不存在")
        status["kl8_history"] = False
    return status


def _fmt_kill_mark(num: int, actual_set: set) -> str:
    """杀号标记: 正确杀掉(未开出)=[√], 漏杀(开出)=[漏]"""
    if num in actual_set:
        return f"{num:02d}[漏]"
    return f"{num:02d}[√]"


def _fmt_safe_mark(num: int, actual_set: set) -> str:
    """保留号标记: 实际开出=[√]"""
    mark = "[√]" if num in actual_set else ""
    return f"{num:02d}{mark}"


def _fmt_num_list(nums: list[int], formatter, per_line: int = 10) -> str:
    tokens = [formatter(n) for n in nums]
    lines = []
    for i in range(0, len(tokens), per_line):
        lines.append("  ".join(tokens[i:i + per_line]))
    return "\n".join(lines)


def _hit_badge(rate: float, target: float = 0.70) -> str:
    if rate >= target:
        return "✅达标"
    if rate >= target - 0.05:
        return "⚠️接近"
    return "❌偏低"


def generate_detailed_report(data_loader: DataLoader, prediction, target_period: str) -> None:
    """生成每一期详细分析+复盘的完整报告文件"""
    opened = {d.period: set(d.numbers) for d in data_loader.history}
    opened_list = {d.period: d.numbers for d in data_loader.history}

    all_preds = load_all_predictions()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    L = []
    W = 70

    L.append("═" * W)
    L.append("  KillSeeker V1.0 — KL8杀号预测系统 · 详细分析报告")
    L.append(f"  生成时间: {now_str}")
    L.append(f"  数据范围: {data_loader.total_periods}期历史 · 最新开奖: {data_loader.latest_period}")
    L.append(f"  预测期号: {target_period}")
    L.append("═" * W)

    reviewable = []
    for pred in all_preds:
        p = pred.get("period", "")
        if p in opened and p != target_period:
            r = review_prediction(pred, opened[p])
            r["actual"] = sorted(opened_list[p])
            r["pred_data"] = pred
            reviewable.append(r)

    if reviewable:
        L.append("")
        L.append("┌" + "─" * (W - 2) + "┐")
        L.append("│  📊 近期杀号命中率总览 (复盘参考)")
        L.append("└" + "─" * (W - 2) + "┘")
        L.append("")
        L.append(f"  {'期号':<10} {'高置信':>8} {'中置信':>8} {'观察区':>8} {'全部杀号':>8} {'保留号':>8}")
        L.append(f"  {'─'*10} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
        for r in reversed(reviewable):
            hr = r["high_hit"] / r["high_total"] if r["high_total"] else 0
            mr = r["mid_hit"] / r["mid_total"] if r["mid_total"] else 0
            lr = r["low_hit"] / r["low_total"] if r["low_total"] else 0
            ar = r["all_hit"] / r["all_total"] if r["all_total"] else 0
            sr = r["safe_hit"] / r["safe_total"] if r["safe_total"] else 0
            L.append(f"  {r['period']:<10} {hr:>7.0%} {mr:>8.0%} {lr:>8.0%} {ar:>8.0%} {sr:>8.0%}")

        n_res = len(reviewable)
        th = sum(r["high_hit"] for r in reviewable)
        th_t = sum(r["high_total"] for r in reviewable)
        tm = sum(r["mid_hit"] for r in reviewable)
        tm_t = sum(r["mid_total"] for r in reviewable)
        ta = sum(r["all_hit"] for r in reviewable)
        ta_t = sum(r["all_total"] for r in reviewable)
        ts_hit = sum(r["safe_hit"] for r in reviewable)
        ts_t = sum(r["safe_total"] for r in reviewable)
        L.append(f"  {'─'*10} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
        L.append(
            f"  {'均值('+str(n_res)+'期)':<10} "
            f"{th/th_t:>7.0%} {tm/tm_t:>8.0%} {'':>8} {ta/ta_t:>8.0%} {ts_hit/ts_t:>8.0%}"
        )
        L.append("")
        L.append(f"  📈 相对瞎蒙基线(75%)杀号战绩: {(ta/ta_t/0.75 - 1)*100:+.1f}%")

    L.append("")
    L.append("═" * W)
    L.append("┌" + "─" * (W - 2) + "┐")
    L.append(f"│  🎯 {target_period}期 杀号推荐 [最新·待开奖]")
    L.append(f"│  综合把握: {prediction.kill_confidence:.1%}")
    L.append("└" + "─" * (W - 2) + "┘")

    engine_names = {
        "similarity": "相似走势",
        "density": "密集区域",
        "pattern": "形态识别",
        "curve": "曲线分析",
        "markov": "马尔可夫",
    }
    L.append("")
    L.append("  ⚙️  引擎贡献:")
    for engine, contrib in prediction.engine_contributions.items():
        bar = "█" * int(contrib * 30)
        name = engine_names.get(engine, engine)
        L.append(f"     {name:<8} {contrib:>6.1%}  {bar}")

    L.append("")
    L.append("  🔴 高置信杀号 (10个 · 预期命中率最高):")
    for sl in _fmt_num_list(prediction.high_conf_kills, lambda n: f"{n:02d}", 10).split("\n"):
        L.append(f"     {sl}")
    L.append("")
    L.append("  🟡 中置信杀号 (10个 · 次级过滤):")
    for sl in _fmt_num_list(prediction.mid_conf_kills, lambda n: f"{n:02d}", 10).split("\n"):
        L.append(f"     {sl}")
    L.append("")
    L.append("  🟠 观察区杀号 (5个 · 防守观察):")
    for sl in _fmt_num_list(prediction.low_conf_kills, lambda n: f"{n:02d}", 10).split("\n"):
        L.append(f"     {sl}")
    L.append("")
    L.append(f"  🟢 保留号 ({len(prediction.safe_numbers)}个 · 精选对比):")
    for sl in _fmt_num_list(prediction.safe_numbers, lambda n: f"{n:02d}", 10).split("\n"):
        L.append(f"     {sl}")
    L.append("")
    L.append(
        f"  📊 杀号统计: 杀号{len(prediction.all_kills)}个 | "
        f"保留{len(prediction.safe_numbers)}个 | "
        f"排除{len(prediction.all_kills)/80:.0%} | "
        f"剩余可选{80-len(prediction.all_kills)}个"
    )
    L.append("")
    L.append("  --> ⏳ 当期开奖数据未出炉，等待验证。")
    L.append("  标记说明(复盘区): 杀号[√]=正确杀掉  杀号[漏]=漏杀开出  保留[√]=命中开出")

    if reviewable:
        L.append("")
        L.append("═" * W)
        L.append("  📋 逐期杀号详细复盘 (已开奖期次)")
        L.append("═" * W)

        for r in reversed(reviewable):
            pred = r["pred_data"]
            period = r["period"]
            actual_set = opened[period]
            actual_nums = r["actual"]
            ts = str(pred.get("timestamp", "未知"))[:19].replace("T", " ")
            conf = float(pred.get("kill_confidence", 0) or 0)

            L.append("")
            L.append(f"📅 期号 {period}：")
            L.append(f"  生成时间: {ts} | 置信度: {conf:.1%}")

            high_kills = pred.get("high_conf_kills", [])
            L.append(f"  🔴 高置信杀号: {' '.join(_fmt_kill_mark(n, actual_set) for n in high_kills)}")
            mid_kills = pred.get("mid_conf_kills", [])
            L.append(f"  🟡 中置信杀号: {' '.join(_fmt_kill_mark(n, actual_set) for n in mid_kills)}")
            low_kills = pred.get("low_conf_kills", [])
            L.append(f"  🟠 观察区杀号: {' '.join(_fmt_kill_mark(n, actual_set) for n in low_kills)}")
            safe_nums = pred.get("safe_numbers", [])
            mid = max(len(safe_nums) // 2, 1) if safe_nums else 0
            L.append(f"  🟢 保留号:     {' '.join(_fmt_safe_mark(n, actual_set) for n in safe_nums[:mid])}")
            if mid and mid < len(safe_nums):
                L.append(f"               {' '.join(_fmt_safe_mark(n, actual_set) for n in safe_nums[mid:])}")

            hr = r["high_hit"] / r["high_total"] if r["high_total"] else 0
            mr = r["mid_hit"] / r["mid_total"] if r["mid_total"] else 0
            lr = r["low_hit"] / r["low_total"] if r["low_total"] else 0
            ar = r["all_hit"] / r["all_total"] if r["all_total"] else 0
            sr = r["safe_hit"] / r["safe_total"] if r["safe_total"] else 0

            L.append("  ┌── 📈 当期对账 ──")
            L.append(f"  │  🔴 高置信杀号命中: {r['high_hit']}/{r['high_total']} ({hr:.0%}) {_hit_badge(hr)}")
            if r["high_miss"]:
                L.append(f"  │     漏杀(实际开出): {', '.join(f'{n:02d}' for n in r['high_miss'])}")
            L.append(f"  │  🟡 中置信杀号命中: {r['mid_hit']}/{r['mid_total']} ({mr:.0%}) {_hit_badge(mr, 0.65)}")
            if r["mid_miss"]:
                L.append(f"  │     漏杀(实际开出): {', '.join(f'{n:02d}' for n in r['mid_miss'])}")
            L.append(f"  │  🟠 观察区杀号命中: {r['low_hit']}/{r['low_total']} ({lr:.0%}) {_hit_badge(lr, 0.60)}")
            L.append(f"  │  📋 全部杀号命中:   {r['all_hit']}/{r['all_total']} ({ar:.0%}) {_hit_badge(ar, 0.75)}")
            L.append(f"  │  🟢 保留号命中:     {r['safe_hit']}/{r['safe_total']} ({sr:.0%}) {_hit_badge(sr, 0.25)}")
            L.append("  │")
            actual_str = ", ".join(f"{n:02d}" for n in actual_nums)
            L.append(f"  │  实际开奖: {actual_str}")
            L.append("  └" + "─" * 30)

    if reviewable:
        L.append("")
        L.append("═" * W)
        L.append("  📊 总结统计")
        L.append("═" * W)
        n_res = len(reviewable)
        th = sum(r["high_hit"] for r in reviewable)
        th_t = sum(r["high_total"] for r in reviewable)
        ta = sum(r["all_hit"] for r in reviewable)
        ta_t = sum(r["all_total"] for r in reviewable)
        ts_hit = sum(r["safe_hit"] for r in reviewable)
        ts_t = sum(r["safe_total"] for r in reviewable)
        L.append(f"  统计期数: {n_res}期")
        L.append(f"  高置信杀号: {th}/{th_t} = {th/th_t:.1%} {_hit_badge(th/th_t)}")
        L.append(f"  全部杀号:   {ta}/{ta_t} = {ta/ta_t:.1%} {_hit_badge(ta/ta_t, 0.75)}")
        L.append(f"  保留号命中: {ts_hit}/{ts_t} = {ts_hit/ts_t:.1%} {_hit_badge(ts_hit/ts_t, 0.25)}")
        L.append(f"  相对瞎蒙基线(75%)杀号战绩: {(ta/ta_t/0.75 - 1)*100:+.1f}%")
        L.append("")

    L.append("═" * W)
    L.append("  终极宪章: 除了上帝，我们只信数据；杀得越狠，赢面越大。")
    L.append("═" * W)

    with open(KILL_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def save_kill_prediction(prediction, target_period: str, cross_feed: dict | None = None) -> None:
    """持久化杀号预测结果到JSON日志 (kill_logs.jsonl)

    关键：同日重复运行若未带 cross_feed，必须保留已有反哺字段，禁止静默抹掉。
    """
    KILL_LOGS.parent.mkdir(parents=True, exist_ok=True)
    existing_cf = None
    existing_lines = []
    if KILL_LOGS.exists():
        with open(KILL_LOGS, "r", encoding="utf-8") as f:
            existing_lines = [l.strip() for l in f if l.strip()]
        for line in existing_lines:
            try:
                entry = json.loads(line)
                if entry.get("period") == target_period and entry.get("cross_feed"):
                    existing_cf = entry["cross_feed"]
                    break
            except json.JSONDecodeError:
                continue

    log_entry = {
        "period": target_period,
        "timestamp": datetime.now().isoformat(),
        "high_conf_kills": prediction.high_conf_kills,
        "mid_conf_kills": prediction.mid_conf_kills,
        "low_conf_kills": prediction.low_conf_kills,
        "all_kills": prediction.all_kills,
        "safe_numbers": prediction.safe_numbers,
        "kill_confidence": prediction.kill_confidence,
        "engine_contributions": prediction.engine_contributions,
    }
    cf_to_save = cross_feed if cross_feed else existing_cf
    if cf_to_save:
        log_entry["cross_feed"] = cf_to_save

    filtered_lines = []
    for line in existing_lines:
        try:
            entry = json.loads(line)
            if entry.get("period") != target_period:
                filtered_lines.append(line)
        except json.JSONDecodeError:
            filtered_lines.append(line)

    filtered_lines.append(json.dumps(log_entry, ensure_ascii=False))
    with open(KILL_LOGS, "w", encoding="utf-8") as f:
        f.write("\n".join(filtered_lines) + "\n")


def print_cross_feed_report(
    cf,
    review_info: dict | None = None,
    window_info: dict | None = None,
) -> None:
    """美观输出 STEP 2.5 杀号反哺交叉校验报告"""
    print_banner(f"STEP 2.5 杀号反哺提纯 — {cf.period}期")

    if review_info:
        print_section("📎 上期反哺回验")
        print(f"  区分力状态: {review_info.get('status', '无数据')}")
        if review_info.get("index") is not None:
            print(f"  区分力指数: {review_info['index']:.2f}  (阈值: >1.5有效 / 1.0-1.5微弱 / <1.0无效)")
        else:
            print("  区分力指数: N/A  (共振命中率为0或样本不足，禁止伪除法)")
        dmr = review_info.get("danger_miss_rate")
        rhr = review_info.get("resonate_hit_rate")
        rev = review_info.get("review_hit_rate")
        if dmr is not None:
            print(f"  🔴危险信号未中率: {dmr:.0%}  (期望高=剔除准确)")
            if review_info.get("danger_correct"):
                print(f"     正确剔除: {', '.join(f'{n:02d}' for n in review_info['danger_correct'])}")
            if review_info.get("danger_wrong"):
                print(f"     误杀(实际开出): {', '.join(f'{n:02d}' for n in review_info['danger_wrong'])}")
        if rhr is not None:
            print(f"  🟢共振确认命中率: {rhr:.0%}  (期望高=双重确认可靠)")
            if review_info.get("resonate_hit"):
                print(f"     命中: {', '.join(f'{n:02d}' for n in review_info['resonate_hit'])}")
            if review_info.get("resonate_miss"):
                print(f"     未中: {', '.join(f'{n:02d}' for n in review_info['resonate_miss'])}")
        if rev is not None:
            print(f"  🟡需复核命中率: {rev:.0%}  (降权0.5x是否合理参考)")
        if review_info.get("prev_coverage") is not None:
            cov = review_info["prev_coverage"]
            print(f"  上期击杀率: {cov:.0%}", end="")
            if cov > 0.5:
                print("  → 曾判混沌分歧期")
            elif cov < 0.2:
                print("  → 曾判信号一致期")
            else:
                print()
        if review_info.get("advice"):
            print(f"  💡 闭环建议: {review_info['advice']}")

    if window_info and window_info.get("n", 0) > 0:
        print_section(f"📊 近{window_info['n']}期反哺区分力")
        print(f"  覆盖期号: {', '.join(window_info.get('periods', []))}")
        avg_dmr = window_info.get("avg_danger_miss_rate")
        avg_rhr = window_info.get("avg_resonate_hit_rate")
        if avg_dmr is not None:
            print(f"  平均危险未中率: {avg_dmr:.0%}")
        if avg_rhr is not None:
            print(f"  平均共振命中率: {avg_rhr:.0%}")
        if window_info.get("index") is not None:
            print(f"  近窗区分力指数: {window_info['index']:.2f}  → {window_info.get('status')}")
        else:
            print(f"  近窗区分力指数: N/A  → {window_info.get('status')}")
        print(f"  💡 {window_info.get('advice', '')}")
        # 上期回验优先于近窗均值（脚本闭环：失真/微弱当期降级）
        if review_info:
            rst = str(review_info.get("status") or "")
            if any(k in rst for k in ("无效", "失真", "微弱", "共振失效")):
                print("  ⚠️ 本期以【上期回验】为准：危险信号降级为仅供参考（覆盖近窗均值建议）")
        print(f"  {'期号':<10} {'危险未中':>8} {'共振命中':>8} {'复核命中':>8}  状态")
        for row in window_info.get("rows", []):
            d = row.get("danger_miss_rate")
            r = row.get("resonate_hit_rate")
            v = row.get("review_hit_rate")
            ds = f"{d:.0%}" if d is not None else "-"
            rs = f"{r:.0%}" if r is not None else "-"
            vs = f"{v:.0%}" if v is not None else "-"
            print(f"  {row.get('period',''):<10} {ds:>8} {rs:>8} {vs:>8}  {row.get('status','')}")

    print_section("📡 前序做多系统信号")
    expected_srcs = ["数据汇总", "双层LSTM", "定金选2", "重点点位", "统计次数"]
    got = {s.name for s in cf.sources}
    if not cf.sources:
        print("  ⚠️ 未读取到前序系统推荐 (本期前序输出尚未就绪)")
    else:
        for src in cf.sources:
            nums = ", ".join(f"{n:02d}" for n in src.numbers)
            print(f"  ▪ {src.name:<8} ({src.note})")
            print(f"      {nums}")
        missing = [n for n in expected_srcs if n not in got]
        if missing:
            print(f"  ⚠️ 未纳入本期: {', '.join(missing)} (文件未产出或期号未匹配，属正常)")

    print_section("🔀 交叉验证矩阵")
    # 按上期/近窗反哺结论校准危险信号行动（脚本优化闭环）
    soft_danger = False
    if review_info:
        st = str(review_info.get("status") or "")
        soft_danger = any(k in st for k in ("无效", "失真", "微弱", "共振失效", "样本不足"))
    if window_info and not soft_danger:
        wst = str(window_info.get("status") or "")
        if any(k in wst for k in ("无效", "失真", "微弱", "共振失效")):
            soft_danger = True
    danger_action = "仅供参考，不强制剔除" if soft_danger else "强烈建议从做多池剔除"
    print("  ┌──────────────────┬────────────────────────────────────────┐")
    print("  │ 分类             │ 含义 / 行动                            │")
    print("  ├──────────────────┼────────────────────────────────────────┤")
    print(f"  │ 🔴 危险信号号码  │ 做多∩高置信杀 → {danger_action}")
    print("  │ 🟡 需复核号码    │ 做多∩中置信杀 → 降权0.5x             │")
    print("  │ 🟢 共振确认号码  │ 做多∩保留号   → 优先选入             │")
    print("  │ ⚪ 独立杀号      │ 高置信杀-做多 → 杀号风险较低         │")
    print("  └──────────────────┴────────────────────────────────────────┘")
    if soft_danger:
        print("  ⚠️ 反哺闭环校准: 危险信号已降级为仅供参考（防过拟合，不改引擎权重）")

    def _print_tagged(label, nums, src_map):
        if not nums:
            print(f"  {label}: (无)")
            return
        parts = []
        for n in nums:
            srcs = ",".join(src_map.get(n, [])) if src_map else ""
            parts.append(f"{n:02d}[{srcs}]" if srcs else f"{n:02d}")
        print(f"  {label}:")
        for i in range(0, len(parts), 5):
            print(f"     {'  '.join(parts[i:i+5])}")

    _print_tagged("🔴 危险信号", cf.danger, cf.danger_sources)
    _print_tagged("🟡 需复核", cf.review, cf.review_sources)
    _print_tagged("🟢 共振确认", cf.resonate, cf.resonate_sources)
    if cf.independent_kills:
        print(f"  ⚪ 独立杀号: {', '.join(f'{n:02d}' for n in cf.independent_kills)}")

    print_section("📉 杀号覆盖率与混沌度")
    cov = cf.kill_coverage
    bar = "█" * int(cov * 20) + "░" * (20 - int(cov * 20))
    flag = "⚠️ 严重分歧" if cf.chaos_flag else ("✅ 方向一致" if cov < 0.20 else "➖ 中性")
    print(f"  击杀率(高置信∩做多Top): {cov:.0%}  [{bar}]  {flag}")
    print(f"  建议: {cf.advice}")

    print_section("🔁 杀号稳定性回溯 (近5期)")
    if cf.stable_kill_boost:
        print(f"  ⬆ 连续≥3期正确杀号(升档): {', '.join(f'{n:02d}' for n in cf.stable_kill_boost)}")
    else:
        print("  ⬆ 连续≥3期正确杀号(升档): (无)")
    if cf.leak_downgrade:
        print(f"  ⬇ 连续≥2期漏杀(建议降观察区): {', '.join(f'{n:02d}' for n in cf.leak_downgrade)}")
    else:
        print("  ⬇ 连续≥2期漏杀(建议降观察区): (无)")
    print("  ※ 反哺参数自学习已精简为人工建议，不做自动改权重（防过拟合）")


def run_step25_cross_feed(data_loader: DataLoader, prediction, target_period: str) -> dict:
    """执行 STEP 2.5 并返回可持久化的 cross_feed dict"""
    preds = load_all_predictions()
    opened = {d.period: set(d.numbers) for d in data_loader.history}

    # 上期反哺回验 + 近N期区分力（脚本要求，窗口扩至10期平滑共振波动）
    review_info = None
    last = find_reviewable_prediction(data_loader)
    if last and last.get("period") in opened:
        review_info = review_previous_cross_feed(last, opened[last["period"]])
    window_info = review_cross_feed_window(preds, opened, n=CROSS_FEED_WINDOW_N)

    cf = run_cross_feed(
        period=target_period,
        high_kills=prediction.high_conf_kills,
        mid_kills=prediction.mid_conf_kills,
        safe_numbers=prediction.safe_numbers,
        preds_history=preds,
        opened=opened,
    )
    print_cross_feed_report(cf, review_info, window_info)

    cf_dict = to_log_dict(cf)
    # 持久化近窗回验摘要，便于下期对照（不改引擎权重）
    if review_info:
        cf_dict["prev_review"] = {
            "status": review_info.get("status"),
            "index": review_info.get("index"),
            "danger_miss_rate": review_info.get("danger_miss_rate"),
            "resonate_hit_rate": review_info.get("resonate_hit_rate"),
            "advice": review_info.get("advice"),
        }
    if window_info and window_info.get("n", 0) > 0:
        cf_dict["window_review"] = {
            "n": window_info.get("n"),
            "periods": window_info.get("periods"),
            "index": window_info.get("index"),
            "status": window_info.get("status"),
            "avg_danger_miss_rate": window_info.get("avg_danger_miss_rate"),
            "avg_resonate_hit_rate": window_info.get("avg_resonate_hit_rate"),
            "advice": window_info.get("advice"),
        }
    return cf_dict


def find_reviewable_prediction(data_loader: DataLoader) -> dict:
    """找到最近一个已开奖期号的杀号预测"""
    if not KILL_LOGS.exists():
        return {}
    history = data_loader.history
    opened_periods = {draw.period for draw in history}
    with open(KILL_LOGS, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    for line in reversed(lines):
        try:
            pred = json.loads(line)
            if pred.get("period", "") in opened_periods:
                return pred
        except json.JSONDecodeError:
            continue
    return {}


def run_kill_prediction(data_loader: DataLoader, config: ModelConfig, with_cross_feed: bool = False) -> dict:
    """执行杀号预测"""
    print_banner("STEP 2 独立杀号复盘与闭环预测")
    print("\n🔪 执行杀号分析...")

    history = data_loader.history
    if not history:
        print("  ❌ 无历史数据")
        return {}

    target_period = str(int(history[0].period) + 1)
    print(f"  🎯 目标期号: {target_period}")
    print(f"  📅 锚定最新开奖: {history[0].period} ({history[0].date})")

    # 引擎1: 相似走势匹配
    print("  🔄 引擎1: 相似走势匹配...")
    matcher = SimilarityMatcher(config.similarity)
    recent = history[:10]
    sim_result = matcher.find_similar(recent, history)
    print(f"     → 最优窗口={sim_result.optimal_window}, Top3相似期={[p for p, _ in sim_result.top_k_periods[:3]]}")

    # 引擎2: 密集区域检测
    print("  🔥 引擎2: 密集区域检测...")
    detector = DensityDetector(config.density)
    density_result = detector.detect(history[:60])
    print(f"     → 冷寂区={len(density_result.cold_zones)}码")

    # 引擎3: 形态识别 (权重=0 时完全跳过，已证明无增益)
    pattern_w = config.kill.engine_weights.get("pattern", 0.0)
    if pattern_w <= 0:
        print("  📐 引擎3: 形态识别... (权重0·已跳过)")
        pattern_result = None
    else:
        print("  📐 引擎3: 形态识别...")
        recognizer = PatternRecognizer(config.pattern)
        pattern_result = recognizer.recognize(history[0])
        print(f"     → TOP3模板={pattern_result.top3_templates[:2]}, 填充率={pattern_result.fill_ratio:.2f}")

    # 引擎4: 曲线分析
    print("  📈 引擎4: 曲线分析...")
    analyzer = CurveAnalyzer(config.curve)
    curve_result = analyzer.analyze(history)
    print(f"     → 异常点={len(curve_result.anomaly_points)}, FFT主周期={curve_result.dominant_period:.1f}")

    # 引擎5: 马尔可夫链
    print("  🔗 引擎5: 马尔可夫链...")
    markov_w = config.kill.engine_weights.get("markov", 0.0)
    if markov_w <= 0:
        print("     (权重0·已跳过)")
        markov_result = None
    else:
        from kill_seeker.core.markov_engine import MarkovEngine
        markov_engine = MarkovEngine(config.markov)
        markov_result = markov_engine.analyze(history)
        ll_sorted = sorted(markov_result.ll.items(), key=lambda kv: -kv[1])
        hot = [u for u, _ in ll_sorted[:5]]
        cold = [u for u, _ in ll_sorted[-5:]]
        print(f"     → 马尔可夫最热={hot}, 最冷={cold}")
        print("     → 冷号回归假设检验: P(出|遗漏L) 自 L=0..12 平坦=%s"
              % ("%.3f" % markov_result.cold_curve[-1]["p_hat"]))

    # 杀号预测
    print("\n  ⚙️  杀号预测 (低分→高置信杀号)...")
    predictor = KillPredictor(config.kill, config.markov)
    prediction = predictor.predict(
        period=target_period,
        sim_result=sim_result,
        density_result=density_result,
        pattern_result=pattern_result,
        curve_result=curve_result,
        markov_result=markov_result,
        history=history,
    )

    # 输出杀号结果
    print_section(f"🎯 {target_period}期杀号推荐  |  综合把握 {prediction.kill_confidence:.1%}")
    print_kill_box("高置信杀号", prediction.high_conf_kills, "🔴", "10个 · 直接从大盘划去")
    print_kill_box("中置信杀号", prediction.mid_conf_kills, "🟡", "10个 · 次级过滤网")
    print_kill_box("观察区杀号", prediction.low_conf_kills, "🟠", "5个 · 防守观察")
    n_safe = len(prediction.safe_numbers)
    print_kill_box("保留号", prediction.safe_numbers, "🟢", f"{n_safe}个 · 精选对比(非主推)")

    print(f"\n  📊 杀号统计:")
    print(f"     杀号总数: {len(prediction.all_kills)}个  |  保留号: {len(prediction.safe_numbers)}个")
    print(f"     排除比例: {len(prediction.all_kills)}/80 = {len(prediction.all_kills)/80:.0%}  |  剩余可选: {80-len(prediction.all_kills)}个")
    print("     ⚠️ 杀号用于缩水，不作为主战做多参考")

    print_section("⚙️  引擎贡献")
    engine_names = {
        "similarity": "相似走势",
        "density": "密集区域",
        "pattern": "形态识别",
        "curve": "曲线分析",
        "markov": "马尔可夫",
    }
    for engine, contrib in prediction.engine_contributions.items():
        bar = "█" * int(contrib * 30)
        name = engine_names.get(engine, engine)
        print(f"  {name:<8} {contrib:>6.1%}  {bar}")

    cf_dict = None
    if with_cross_feed:
        cf_dict = run_step25_cross_feed(data_loader, prediction, target_period)

    # 持久化
    save_kill_prediction(prediction, target_period, cross_feed=cf_dict)
    generate_detailed_report(data_loader, prediction, target_period)

    return {"prediction": prediction, "period": target_period, "cross_feed": cf_dict}


def run_review(data_loader: DataLoader) -> dict:
    """复盘上期杀号"""
    print_banner("复盘上期杀号战果")
    print_section("🔍 复盘上期杀号")

    last_pred = find_reviewable_prediction(data_loader)
    if not last_pred:
        print("  ⚠️ 无杀号历史记录, 跳过复盘")
        return {}

    pred_period = last_pred.get("period", "")
    history = data_loader.history
    actual_numbers = []
    for draw in history:
        if draw.period == pred_period:
            actual_numbers = draw.numbers
            break

    if not actual_numbers:
        print(f"  ⚠️ 未找到{pred_period}期开奖数据")
        return {}

    actual_set = set(actual_numbers)
    stats = review_prediction(last_pred, actual_set)

    print(f"  复盘期号: {pred_period}")
    print_hit_bar("高置信杀号", stats["high_hit"], stats["high_total"])
    print_hit_bar("中置信杀号", stats["mid_hit"], stats["mid_total"], 0.65)
    print_hit_bar("观察区杀号", stats["low_hit"], stats["low_total"], 0.60)
    print_hit_bar("全部杀号", stats["all_hit"], stats["all_total"], 0.75)
    print_hit_bar("保留号命中", stats["safe_hit"], stats["safe_total"], 0.25)

    if stats["high_miss"]:
        print(f"  ⚠️ 高置信漏杀(实际开出): {', '.join(f'{n:02d}' for n in stats['high_miss'])}")
    if stats["mid_miss"]:
        print(f"  ⚠️ 中置信漏杀(实际开出): {', '.join(f'{n:02d}' for n in stats['mid_miss'])}")

    # 展示杀号明细标记
    print_section(f"📋 {pred_period}期杀号明细 (√=杀对 / 漏=开出)")
    highs = last_pred.get("high_conf_kills", [])
    mids = last_pred.get("mid_conf_kills", [])
    print(f"  🔴 {' '.join(_fmt_kill_mark(n, actual_set) for n in highs)}")
    print(f"  🟡 {' '.join(_fmt_kill_mark(n, actual_set) for n in mids)}")
    print(f"\n  实际开奖: {fmt_nums(sorted(actual_numbers), 10).replace(chr(10), chr(10) + '            ')}")

    return {
        "actual_numbers": actual_numbers,
        "high_kill_hit": stats["high_hit"],
        "mid_kill_hit": stats["mid_hit"],
        "low_kill_hit": stats["low_hit"],
        "all_kill_hit": stats["all_hit"],
        "safe_hit": stats["safe_hit"],
        "last_prediction": last_pred,
    }


def run_diagnose() -> None:
    """系统诊断"""
    print_banner("STEP 1 环境与数据预检")
    print("\n🔧 系统诊断:")
    checks = {
        "kill_seeker.config.paths": True,
        "kill_seeker.config.model_config": True,
        "kill_seeker.core.data_loader": True,
        "kill_seeker.core.similarity_matcher": True,
        "kill_seeker.core.density_detector": True,
        "kill_seeker.core.pattern_recognizer": True,
        "kill_seeker.core.curve_analyzer": True,
        "kill_seeker.core.markov_engine": True,
        "kill_seeker.core.kill_predictor": True,
        "kill_seeker.core.cross_feed": True,
    }
    for module_name in checks:
        try:
            __import__(module_name)
            print(f"  ✅ {module_name}")
        except Exception as e:
            print(f"  ❌ {module_name}: {e}")
            checks[module_name] = False

    # 实际使用依赖：numpy(矩阵运算) + scipy(密度引擎 gaussian_kde)。
    # sklearn/hdbscan 已不再使用（旧诊断残留），移除检查避免误导。
    for dep in ["numpy", "scipy"]:
        try:
            __import__(dep)
            print(f"  ✅ 依赖: {dep}")
        except ImportError:
            print(f"  ❌ 依赖缺失: {dep}")

    # 密集引擎已纯 KDE（scipy.stats.gaussian_kde），无需 sklearn/hdbscan
    print("  ✅ 密集引擎: KDE密度图 (scipy 提供，无需 sklearn/hdbscan)")

    # 数据文件 + 最新期号预检（脚本 STEP1 要求确认最新期）
    if KL8_HISTORY_FILE.exists():
        print(f"  ✅ 开奖数据: {KL8_HISTORY_FILE}")
        try:
            dl = DataLoader()
            dl.load()
            latest = dl.history[0] if dl.history else None
            if latest:
                print(f"  ✅ 最新期号: {latest.period}  ({latest.date})  共{dl.total_periods}期")
                print(f"     下一预测目标: {int(latest.period) + 1}")
                try:
                    latest_date = datetime.strptime(latest.date, "%Y-%m-%d").date()
                except ValueError:
                    latest_date = None
                # 补跑时间旅行时，数据更新下限 = 目标日-1（而非真实昨天）
                _target = kl8_target_date()
                yesterday = ((_target if _target else datetime.now().date()) - timedelta(days=1))
                if latest_date is None or latest_date < yesterday:
                    print(f"  ❌ 数据新鲜度: 最新期 {latest.period} ({latest.date}) 未更新至昨日，需先抓取开奖数据")
                    checks["kl8_history"] = False
            else:
                print("  ❌ 开奖数据为空")
                checks["kl8_history"] = False
        except Exception as e:
            print(f"  ❌ 开奖数据读取失败: {e}")
            checks["kl8_history"] = False
    else:
        print(f"  ❌ 开奖数据缺失: {KL8_HISTORY_FILE}")
        checks["kl8_history"] = False

    all_pass = all(checks.values())
    print(f"\n{'✅ 诊断通过' if all_pass else '❌ 诊断失败'}: {sum(checks.values())}/{len(checks)} 模块正常")
    if not all_pass:
        sys.exit(1)


def run_backtest(data_loader: DataLoader, config: ModelConfig, n_periods: int = 30) -> None:
    """N期回测验证杀号效果"""
    print(f"\n📊 {n_periods}期杀号回测...")

    history = data_loader.history
    if len(history) < n_periods + 60:
        print(f"  ⚠️ 历史数据不足, 需要至少{n_periods+60}期")
        return

    results = []
    for i in range(n_periods):
        # 模拟历史时点
        sim_history = history[i:]
        if len(sim_history) < 60:
            break

        target_period = str(int(sim_history[0].period) + 1)
        # 在全量历史中搜索实际开奖 (sim_history 不包括 target_period)
        actual_set = set()
        for draw in history:
            if draw.period == target_period:
                actual_set = draw.number_set
                break

        if not actual_set:
            continue

        # 执行杀号预测
        try:
            recent = sim_history[:10]
            matcher = SimilarityMatcher(config.similarity)
            sim_result = matcher.find_similar(recent, sim_history)

            detector = DensityDetector(config.density)
            density_result = detector.detect(sim_history[:60])

            pattern_w = config.kill.engine_weights.get("pattern", 0.0)
            if pattern_w <= 0:
                pattern_result = None
            else:
                recognizer = PatternRecognizer(config.pattern)
                pattern_result = recognizer.recognize(sim_history[0])

            analyzer = CurveAnalyzer(config.curve)
            curve_result = analyzer.analyze(sim_history)

            markov_w = config.kill.engine_weights.get("markov", 0.0)
            if markov_w <= 0:
                markov_result = None
            else:
                from kill_seeker.core.markov_engine import MarkovEngine
                markov_result = MarkovEngine(config.markov).analyze(sim_history)

            predictor = KillPredictor(config.kill, config.markov)
            prediction = predictor.predict(
                period=target_period,
                sim_result=sim_result,
                density_result=density_result,
                pattern_result=pattern_result,
                curve_result=curve_result,
                markov_result=markov_result,
                history=sim_history,
            )

            all_kills = set(prediction.all_kills)
            high_kills = set(prediction.high_conf_kills)
            safe_nums = set(prediction.safe_numbers)

            kill_hit = len(all_kills - actual_set)
            high_hit = len(high_kills - actual_set)
            safe_correct = len(safe_nums & actual_set)

            results.append({
                "period": target_period,
                "kill_hit": kill_hit,
                "kill_total": len(all_kills),
                "high_hit": high_hit,
                "high_total": len(high_kills),
                "safe_correct": safe_correct,
                "safe_total": len(safe_nums),
            })
        except Exception as e:
            continue

    if not results:
        print("  ⚠️ 无有效回测结果")
        return

    # 统计
    kill_hits = [r["kill_hit"] for r in results]
    high_hits = [r["high_hit"] for r in results]
    safe_hits = [r["safe_correct"] for r in results]

    kill_rate = sum(kill_hits) / sum(r["kill_total"] for r in results)
    high_rate = sum(high_hits) / sum(r["high_total"] for r in results)
    safe_rate = sum(safe_hits) / sum(r["safe_total"] for r in results)

    print_section(f"📊 {len(results)}期回测结果")
    print_hit_bar("高置信杀号", sum(high_hits), sum(r["high_total"] for r in results))
    print_hit_bar("全部杀号", sum(kill_hits), sum(r["kill_total"] for r in results), 0.75)
    print_hit_bar("保留号命中", sum(safe_hits), sum(r["safe_total"] for r in results), 0.25)
    print(f"\n  📈 相对瞎蒙基线(75%)杀号战绩: {(kill_rate/0.75 - 1)*100:+.1f}%")
    target_ok = kill_rate >= 0.75 and high_rate >= 0.70
    print(f"  {'✅ 回测达标 (全部≥75%, 高置信≥70%)' if target_ok else '⚠️ 回测接近目标，继续观察'}")


def _feed_force_remove(cf: dict) -> bool:
    """脚本闭环：反哺有效才强制剔除危险信号；微弱/无效/失真则仅供参考。"""
    prev = cf.get("prev_review") or {}
    win = cf.get("window_review") or {}
    status = str(prev.get("status") or "")
    # 上期结论优先；若上期失真则看近窗
    if any(k in status for k in ("无效", "失真", "微弱", "共振失效")):
        return False
    if "有效" in status:
        return True
    wstatus = str(win.get("status") or "")
    if any(k in wstatus for k in ("无效", "失真", "微弱", "共振失效")):
        return False
    return "有效" in wstatus


def _fmt_src_map(nums: list, src_map: dict) -> str:
    if not nums:
        return "(无)"
    parts = []
    for n in nums:
        key = str(n)
        srcs = src_map.get(key) or src_map.get(n) or []
        if isinstance(srcs, str):
            srcs = [srcs]
        tag = ",".join(srcs) if srcs else ""
        parts.append(f"{n:02d}[{tag}]" if tag else f"{n:02d}")
    return ", ".join(parts)


def write_control_panel_md(data_loader: DataLoader, result: dict) -> Path | None:
    """将控制面板详细结果写入 logs/control_panel_<期号>.md"""
    prediction = result.get("prediction")
    period = result.get("period", "")
    cf = result.get("cross_feed") or {}
    if not prediction or not period:
        return None

    preds = load_all_predictions()
    opened = {d.period: set(d.numbers) for d in data_loader.history}
    recent = []
    seen = set()
    for pred in reversed(preds):
        p = pred.get("period", "")
        if p in seen or p not in opened or p == period:
            continue
        seen.add(p)
        recent.append(review_prediction(pred, opened[p]))
        if len(recent) >= 10:
            break

    force_rm = _feed_force_remove(cf) if cf else False
    md: list[str] = []
    md.append(f"# KillSeeker 控制面板详细报告 — {period}期")
    md.append("")
    md.append(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"- 生成依据: 最新开奖 `{data_loader.latest_period}` · 历史 `{data_loader.total_periods}` 期")
    md.append(f"- 综合把握: **{prediction.kill_confidence:.1%}**")
    md.append("")

    md.append("## ① 近窗命中率仪表")
    md.append("")
    if recent:
        md.append("| 期号 | 高置信 | 中置信 | 全部杀号 | 保留号 | 状态 |")
        md.append("|------|--------|--------|----------|--------|------|")
        th = th_t = tm = tm_t = ta = ta_t = ts = ts_t = 0
        for r in reversed(recent):
            hr = r["high_hit"] / r["high_total"] if r["high_total"] else 0
            mr = r["mid_hit"] / r["mid_total"] if r["mid_total"] else 0
            ar = r["all_hit"] / r["all_total"] if r["all_total"] else 0
            sr = r["safe_hit"] / r["safe_total"] if r["safe_total"] else 0
            flag = "✅" if ar >= 0.75 else ("⚠️" if ar >= 0.70 else "❌")
            md.append(
                f"| {r['period']} | {r['high_hit']}/{r['high_total']} ({hr:.0%}) | "
                f"{r['mid_hit']}/{r['mid_total']} ({mr:.0%}) | "
                f"{r['all_hit']}/{r['all_total']} ({ar:.0%}) | "
                f"{r['safe_hit']}/{r['safe_total']} ({sr:.0%}) | {flag} |"
            )
            th += r["high_hit"]; th_t += r["high_total"]
            tm += r["mid_hit"]; tm_t += r["mid_total"]
            ta += r["all_hit"]; ta_t += r["all_total"]
            ts += r["safe_hit"]; ts_t += r["safe_total"]
        all_rate = ta / ta_t if ta_t else 0
        md.append("")
        md.append(
            f"**汇总 ({len(recent)}期)**: 高置信 {th}/{th_t}={th/th_t:.1%} · "
            f"中置信 {tm}/{tm_t}={tm/tm_t:.1%} · 全部 {ta}/{ta_t}={ta/ta_t:.1%} · "
            f"保留 {ts}/{ts_t}={ts/ts_t:.1%} · 相对基线75% {(all_rate/0.75-1)*100:+.1f}%"
        )
        if all_rate < 0.75:
            md.append("")
            md.append("> 📌 近窗低于75% → 实战以高置信杀号缩水为主，观察区降权")
    else:
        md.append("(无可复盘样本)")

    md.append("")
    md.append(f"## ② {period}期杀号推荐（准确清单）")
    md.append("")
    eng = prediction.engine_contributions or {}
    md.append(
        f"- 引擎贡献: 相似 {eng.get('similarity', 0):.0%} / 密集 {eng.get('density', 0):.0%} / "
        f"形态 {eng.get('pattern', 0):.0%} / 曲线 {eng.get('curve', 0):.0%}"
    )
    md.append(f"- 综合把握: {prediction.kill_confidence:.1%}")
    md.append(f"- 🔴 高置信(10·直接划去): {', '.join(f'{n:02d}' for n in prediction.high_conf_kills)}")
    md.append(f"- 🟡 中置信(10·次级过滤): {', '.join(f'{n:02d}' for n in prediction.mid_conf_kills)}")
    md.append(f"- 🟠 观察区(5·防守观察): {', '.join(f'{n:02d}' for n in prediction.low_conf_kills)}")
    md.append(
        f"- 🟢 保留号({len(prediction.safe_numbers)}·精选对比): "
        f"{', '.join(f'{n:02d}' for n in prediction.safe_numbers)}"
    )
    md.append(
        f"- 排除 {len(prediction.all_kills)}/80={len(prediction.all_kills)/80:.0%} "
        f"→ 剩余可选 {80 - len(prediction.all_kills)} 个"
    )

    md.append("")
    md.append("## ③ 杀号反哺交叉矩阵（含来源）")
    md.append("")
    if not cf:
        md.append("⚠️ 本期无反哺数据（前序系统未就绪或未写入）")
    else:
        dsrc = cf.get("danger_sources") or {}
        rsrc = cf.get("review_sources") or {}
        zsrc = cf.get("resonate_sources") or {}
        md.append(f"- 🔴 危险信号: {_fmt_src_map(cf.get('danger') or [], dsrc)}")
        md.append(f"- 🟡 需复核: {_fmt_src_map(cf.get('review') or [], rsrc)}")
        md.append(f"- 🟢 共振确认: {_fmt_src_map(cf.get('resonate') or [], zsrc)}")
        indep = cf.get("independent_kills") or []
        md.append(f"- ⚪ 独立杀号: {', '.join(f'{n:02d}' for n in indep) or '(无)'}")
        cov = float(cf.get("kill_coverage") or 0)
        flag = "严重分歧" if cov > 0.5 else ("方向一致" if cov < 0.2 else "中性")
        md.append(f"- 击杀率: {cov:.0%} → {flag}")
        if cf.get("advice"):
            md.append(f"- 覆盖建议: {cf['advice']}")
        prev = cf.get("prev_review") or {}
        win = cf.get("window_review") or {}
        if prev:
            idx = prev.get("index")
            idx_s = f"{idx:.2f}" if isinstance(idx, (int, float)) else "N/A"
            md.append(f"- 上期反哺回验: {prev.get('status')} | 指数={idx_s}")
            if prev.get("advice"):
                md.append(f"  - {prev['advice']}")
            dmr = prev.get("danger_miss_rate")
            rhr = prev.get("resonate_hit_rate")
            if dmr is not None:
                md.append(f"  - 危险未中率: {dmr:.0%}")
            if rhr is not None:
                md.append(f"  - 共振命中率: {rhr:.0%}")
        if win and win.get("n"):
            widx = win.get("index")
            widx_s = f"{widx:.2f}" if isinstance(widx, (int, float)) else "N/A"
            avg_dmr = win.get("avg_danger_miss_rate")
            avg_rhr = win.get("avg_resonate_hit_rate")
            dmr_s = f"{avg_dmr:.0%}" if avg_dmr is not None else "-"
            rhr_s = f"{avg_rhr:.0%}" if avg_rhr is not None else "-"
            md.append(
                f"- 近{win.get('n')}期区分力: {win.get('status')} | 指数={widx_s} "
                f"| 危险未中均={dmr_s} | 共振命中均={rhr_s}"
            )
            if win.get("advice"):
                md.append(f"  - {win['advice']}")
            # 上期回验优先于近窗均值（与控制台 soft_danger 逻辑一致）
            pst = str(prev.get("status") or "")
            if any(k in pst for k in ("无效", "失真", "微弱", "共振失效")):
                md.append(
                    "  - ⚠️ 本期以【上期回验】为准：危险信号降级为仅供参考（覆盖近窗均值建议）"
                )
        if cf.get("leak_downgrade"):
            md.append(f"- ⬇ 漏杀降档建议: {', '.join(f'{n:02d}' for n in cf['leak_downgrade'])}")
        if cf.get("stable_kill_boost"):
            md.append(f"- ⬆ 连续杀对升档: {', '.join(f'{n:02d}' for n in cf['stable_kill_boost'])}")
        srcs = cf.get("sources") or {}
        if srcs:
            md.append("- 前序做多源:")
            for name, nums in srcs.items():
                md.append(f"  - ▪ {name}: {', '.join(f'{n:02d}' for n in nums)}")

    md.append("")
    md.append("## ④ 行动清单（按反哺闭环校准）")
    md.append("")
    md.append("1. 高置信杀号 → 从大盘过滤清单直接划去（缩水主手段）")
    if force_rm:
        md.append("2. 🔴危险信号 → **从所有做多推荐中剔除**（上期/近窗反哺有效）")
    else:
        md.append("2. 🔴危险信号 → **仅供参考，不强制剔除**做多推荐（反哺微弱/无效/失真）")
    md.append("3. 🟡需复核号码 → 降权 0.5x")
    prev_rhr = (cf.get("prev_review") or {}).get("resonate_hit_rate")
    if prev_rhr is not None and prev_rhr <= 0.0:
        md.append("4. 🟢共振确认号码 → 提高选入优先级时谨慎（上期共振确认全灭）")
    elif prev_rhr is not None and prev_rhr < 0.25:
        md.append(
            f"4. 🟢共振确认号码 → 可提高选入优先级（上期共振命中仅 {prev_rhr:.0%}，勿过度加仓）"
        )
    else:
        md.append("4. 🟢共振确认号码 → 提高选入优先级")
    md.append("5. 杀号仅用于缩水，不做主战做多")
    md.append("6. 近窗全部杀号<75%时：观察区降权，勿扩大杀号面")
    md.append("")
    md.append("---")
    md.append("终极宪章: 除了上帝，我们只信数据；杀得越狠，赢面越大。")
    md.append("")

    out_path = OUTPUT_DIR / f"control_panel_{period}.md"
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"\n  💾 控制面板已写入: {out_path}")

    # 反哺四类逐号复盘 + 今日总结果
    try:
        # 复用上面 recent 汇总结构；若为空则按 opened 再算
        hit_rows = list(reversed(recent)) if recent else None
        review_path, today_path = write_number_feed_reports(
            output_dir=OUTPUT_DIR,
            current={
                "period": period,
                "high_conf_kills": prediction.high_conf_kills,
                "mid_conf_kills": prediction.mid_conf_kills,
                "low_conf_kills": prediction.low_conf_kills,
                "all_kills": prediction.all_kills,
                "safe_numbers": prediction.safe_numbers,
                "kill_confidence": prediction.kill_confidence,
                "engine_contributions": prediction.engine_contributions,
                "cross_feed": cf,
            },
            preds=preds,
            opened=opened,
            latest_draw=str(data_loader.latest_period),
            total_periods=int(data_loader.total_periods),
            hit_rate_table=hit_rows,
            window=10,
        )
        print(f"  💾 反哺逐号复盘: {review_path}")
        print(f"  💾 今日总结果: {today_path}")
    except Exception as e:
        print(f"  ⚠️ 逐号复盘报告生成失败: {e}")

    return out_path


def print_control_panel(data_loader: DataLoader, result: dict) -> None:
    """控制面板：各分析维度详细准确结果 + 行动建议"""
    prediction = result.get("prediction")
    period = result.get("period", "")
    cf = result.get("cross_feed") or {}
    if not prediction:
        return

    print_banner(f"控制面板总览 — {period}期")

    preds = load_all_predictions()
    opened = {d.period: set(d.numbers) for d in data_loader.history}
    recent = []
    seen = set()
    for pred in reversed(preds):
        p = pred.get("period", "")
        if p in seen or p not in opened or p == period:
            continue
        seen.add(p)
        recent.append(review_prediction(pred, opened[p]))
        if len(recent) >= 10:
            break

    print_section("① 近窗命中率仪表（逐期 + 汇总）")
    if recent:
        print(f"  {'期号':<10} {'高置信':>8} {'中置信':>8} {'全部':>8} {'保留':>8}  状态")
        print(f"  {'─' * 10} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8}  {'─' * 6}")
        for r in reversed(recent):
            hr = r["high_hit"] / r["high_total"] if r["high_total"] else 0
            mr = r["mid_hit"] / r["mid_total"] if r["mid_total"] else 0
            ar = r["all_hit"] / r["all_total"] if r["all_total"] else 0
            sr = r["safe_hit"] / r["safe_total"] if r["safe_total"] else 0
            flag = "✅" if ar >= 0.75 else ("⚠️" if ar >= 0.70 else "❌")
            print(f"  {r['period']:<10} {hr:>7.0%} {mr:>8.0%} {ar:>7.0%} {sr:>7.0%}  {flag}")
        th = sum(r["high_hit"] for r in recent)
        th_t = sum(r["high_total"] for r in recent)
        tm = sum(r["mid_hit"] for r in recent)
        tm_t = sum(r["mid_total"] for r in recent)
        ta = sum(r["all_hit"] for r in recent)
        ta_t = sum(r["all_total"] for r in recent)
        ts = sum(r["safe_hit"] for r in recent)
        ts_t = sum(r["safe_total"] for r in recent)
        print()
        print_hit_bar("高置信杀号", th, th_t)
        print_hit_bar("中置信杀号", tm, tm_t, 0.65)
        print_hit_bar("全部杀号", ta, ta_t, 0.75)
        print_hit_bar("保留号命中", ts, ts_t, 0.25)
        all_rate = ta / ta_t if ta_t else 0
        print(f"  相对基线75%: {(all_rate / 0.75 - 1) * 100:+.1f}%  |  样本 {len(recent)}期")
        if all_rate < 0.75:
            print("  📌 近窗低于75% → 实战以高置信杀号缩水为主，观察区降权")
    else:
        print("  (无可复盘样本)")

    print_section(f"② {period}期杀号推荐（准确清单）")
    print(f"  综合把握: {prediction.kill_confidence:.1%}")
    eng = prediction.engine_contributions or {}
    eng_names = {"similarity": "相似", "density": "密集", "pattern": "形态", "curve": "曲线"}
    eng_line = " | ".join(
        f"{eng_names.get(k, k)}{v:.0%}" for k, v in eng.items() if v and v > 0
    ) or "—"
    print(f"  引擎贡献: {eng_line}")
    print(f"  🔴 高置信(10·直接划去): {', '.join(f'{n:02d}' for n in prediction.high_conf_kills)}")
    print(f"  🟡 中置信(10·次级过滤): {', '.join(f'{n:02d}' for n in prediction.mid_conf_kills)}")
    print(f"  🟠 观察区(5·防守观察):  {', '.join(f'{n:02d}' for n in prediction.low_conf_kills)}")
    print(
        f"  🟢 保留号({len(prediction.safe_numbers)}·精选对比): "
        f"{', '.join(f'{n:02d}' for n in prediction.safe_numbers)}"
    )
    print(
        f"  排除 {len(prediction.all_kills)}/80={len(prediction.all_kills)/80:.0%} "
        f"→ 剩余可选 {80 - len(prediction.all_kills)} 个"
    )

    print_section("③ 杀号反哺交叉矩阵（含来源）")
    if not cf:
        print("  ⚠️ 本期无反哺数据（前序系统未就绪或未写入）")
        force_rm = False
    else:
        danger = cf.get("danger") or []
        review = cf.get("review") or []
        resonate = cf.get("resonate") or []
        indep = cf.get("independent_kills") or []
        cov = float(cf.get("kill_coverage") or 0)
        dsrc = cf.get("danger_sources") or {}
        rsrc = cf.get("review_sources") or {}
        zsrc = cf.get("resonate_sources") or {}
        print(f"  🔴 危险信号: {_fmt_src_map(danger, dsrc)}")
        print(f"  🟡 需复核:   {_fmt_src_map(review, rsrc)}")
        print(f"  🟢 共振确认: {_fmt_src_map(resonate, zsrc)}")
        print(f"  ⚪ 独立杀号: {', '.join(f'{n:02d}' for n in indep) or '(无)'}")
        flag = "严重分歧" if cov > 0.5 else ("方向一致" if cov < 0.2 else "中性")
        print(f"  击杀率: {cov:.0%} → {flag}")
        if cf.get("advice"):
            print(f"  覆盖建议: {cf['advice']}")
        prev = cf.get("prev_review") or {}
        win = cf.get("window_review") or {}
        if prev:
            idx = prev.get("index")
            idx_s = f"{idx:.2f}" if isinstance(idx, (int, float)) else "N/A"
            print(f"  上期反哺回验: {prev.get('status')} | 指数={idx_s}")
            if prev.get("advice"):
                print(f"    → {prev['advice']}")
        if win and win.get("n"):
            widx = win.get("index")
            widx_s = f"{widx:.2f}" if isinstance(widx, (int, float)) else "N/A"
            avg_dmr = win.get("avg_danger_miss_rate")
            avg_rhr = win.get("avg_resonate_hit_rate")
            dmr_s = f"{avg_dmr:.0%}" if avg_dmr is not None else "-"
            rhr_s = f"{avg_rhr:.0%}" if avg_rhr is not None else "-"
            print(
                f"  近{win.get('n')}期区分力: {win.get('status')} | 指数={widx_s} "
                f"| 危险未中均={dmr_s} | 共振命中均={rhr_s}"
            )
            pst = str(prev.get("status") or "")
            if any(k in pst for k in ("无效", "失真", "微弱", "共振失效")):
                print("  ⚠️ 本期以【上期回验】为准：危险信号降级为仅供参考（覆盖近窗均值建议）")
        if cf.get("leak_downgrade"):
            print(f"  ⬇ 漏杀降档建议: {', '.join(f'{n:02d}' for n in cf['leak_downgrade'])}")
        if cf.get("stable_kill_boost"):
            print(f"  ⬆ 连续杀对升档: {', '.join(f'{n:02d}' for n in cf['stable_kill_boost'])}")
        srcs = cf.get("sources") or {}
        if srcs:
            print("  前序做多源:")
            for name, nums in srcs.items():
                print(f"    ▪ {name}: {', '.join(f'{n:02d}' for n in nums)}")
        force_rm = _feed_force_remove(cf)

    print_section("④ 行动清单（按反哺闭环校准）")
    print("  1. 高置信杀号 → 从大盘过滤清单直接划去（缩水主手段）")
    if force_rm:
        print("  2. 🔴危险信号 → 从所有做多推荐中剔除（上期/近窗反哺有效）")
    else:
        print("  2. 🔴危险信号 → 仅供参考，不强制剔除做多推荐（反哺微弱/无效/失真）")
    print("  3. 🟡需复核号码 → 降权 0.5x")
    prev_rhr = (cf.get("prev_review") or {}).get("resonate_hit_rate") if cf else None
    if prev_rhr is not None and prev_rhr <= 0.0:
        print("  4. 🟢共振确认号码 → 提高选入优先级时谨慎（上期共振确认全灭）")
    elif prev_rhr is not None and prev_rhr < 0.25:
        print(f"  4. 🟢共振确认号码 → 可提高选入优先级（上期共振命中仅 {prev_rhr:.0%}，勿过度加仓）")
    else:
        print("  4. 🟢共振确认号码 → 提高选入优先级")
    print("  5. 杀号仅用于缩水，不做主战做多")
    print("  6. 近窗全部杀号<75%时：观察区降权，勿扩大杀号面")


def main():
    parser = argparse.ArgumentParser(description="KillSeeker V1.0 杀号预测系统")
    parser.add_argument("--predict", action="store_true", help="仅杀号预测")
    parser.add_argument("--review", action="store_true", help="仅复盘")
    parser.add_argument("--full", action="store_true", help="完整流程(复盘+预测)")
    parser.add_argument("--diagnose", action="store_true", help="系统诊断")
    parser.add_argument("--backtest", type=int, nargs="?", const=30, metavar="N",
                        help="N期回测(默认30期)")
    parser.add_argument(
        "--as-of",
        metavar="PERIOD",
        help="按指定开奖期截断历史后跑全流程（预测目标=PERIOD+1，用于断档补跑）",
    )
    args = parser.parse_args()

    # 配置区分力排查日志：INFO 级输出到控制台，便于定位反哺区分力指数波动
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    print_header()

    if args.diagnose:
        run_diagnose()
        return

    config = ModelConfig()

    print("\n📂 加载数据...")
    data_loader = DataLoader()
    data_loader.load()

    if args.as_of:
        as_of = str(args.as_of).strip()
        kept = data_loader.truncate_as_of(as_of)
        print(f"  ⏪ as-of 模式: 历史截断至 ≤{as_of}（保留{kept}期）")
        print(f"     锚定开奖: {data_loader.latest_period} → 预测目标: {int(data_loader.latest_period)+1}")

    check_data_freshness(data_loader)

    # V1.0 每日幂等校验: 回测/断档补跑(as-of)不触发
    if not args.backtest and not args.as_of:
        if guard_daily_run("KillSeeker", interactive=False):
            return

    if args.backtest is not None:
        run_backtest(data_loader, config, args.backtest)
        return

    if args.review:
        run_review(data_loader)
        return

    if args.full:
        print_banner("每日全流程闭环")
        run_review(data_loader)
        run_recent_reviews(data_loader, n=10)
        result = run_kill_prediction(data_loader, config, with_cross_feed=True)
        if result.get("prediction"):
            period = result.get("period") or str(int(data_loader.latest_period) + 1)
            verify_persistence(period)
            print_control_panel(data_loader, result)
            write_control_panel_md(data_loader, result)
        cleanup_pycache()
    elif args.predict:
        run_kill_prediction(data_loader, config, with_cross_feed=True)
    else:
        # 默认 = 完整闭环（含 STEP2.5），避免无参运行覆盖并抹掉 cross_feed
        print_banner("每日全流程闭环 (默认)")
        run_review(data_loader)
        run_recent_reviews(data_loader, n=10)
        result = run_kill_prediction(data_loader, config, with_cross_feed=True)
        if result.get("prediction"):
            period = result.get("period") or str(int(data_loader.latest_period) + 1)
            verify_persistence(period)
            print_control_panel(data_loader, result)
            write_control_panel_md(data_loader, result)
        cleanup_pycache()

    # V1.0 每日幂等校验: 成功收尾标记（仅非回测/as-of 模式）
    if not args.backtest and not args.as_of:
        mark_daily_run_done("KillSeeker", period=str(int(data_loader.latest_period) + 1))

    print("\n✅ KillSeeker V1.0 执行完毕")
    print("   终极宪章: 除了上帝，我们只信数据；杀得越狠，赢面越大。")


if __name__ == "__main__":
    main()
