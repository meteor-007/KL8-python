# -*- coding: utf-8 -*-
"""输出指定期的全模块明细与上一期复盘。

用法：
    python scripts/dump_module_details.py                    # 读 preflight 自动定位
    python scripts/dump_module_details.py --period 2026297 --prev 2026296
    python scripts/dump_module_details.py --out-dir output/20261107

不改动任何预测逻辑，只把 registry 的结果逐模块展开，便于人工核对。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kl8 import registry, replay, source
from kl8.config import load_config
from kl8.ensemble import DIM_NAMES, MAIN_METHODS, Exp3State, fuse
from kl8.points import compute_base_stats, expand
from kl8.scoring import select_52, select_top5

DEFAULT_PREFLIGHT = ROOT / "data/state/preflight.json"


def fmt(nums):
    return " ".join(f"{n:02d}" for n in nums)


def _resolve(preflight: Path, period: int | None, prev: int | None,
             out_dir: str | None):
    pf = {}
    if preflight.exists():
        pf = json.loads(preflight.read_text(encoding="utf-8"))
    target = int(period or pf.get("target", {}).get("period") or 0)
    prev_p = int(prev or pf.get("latest_draw", {}).get("period") or 0)
    if not target:
        raise SystemExit("✗ 无法确定目标期：请传 --period 或先运行 daily_preflight.py")
    if not prev_p:
        prev_p = target - 1
    if out_dir:
        out = Path(out_dir)
    else:
        d = pf.get("target", {}).get("date")
        out = Path("output") / (d.replace("-", "") if d else str(target))
    prev_pub = Path(pf.get("prev_published_dir")
                    or f"output/{pf.get('latest_draw', {}).get('date', '').replace('-', '')}")
    return target, prev_p, out, prev_pub


def module_details(target: int, out_dir: Path) -> str:
    cfg = load_config(None)
    ds = source.load_dataset(cfg, allow_fetch=False)
    entry = ds.points[target]
    hist = ds.history_before(target)
    expanded = expand(entry.points)
    base = compute_base_stats(hist, expanded)
    results, z_rebound = registry.run_all(
        hist, expanded, base, cfg, list(MAIN_METHODS), run_meta=True)
    exp3 = Exp3State.load_or_uniform(
        cfg.state_file, MAIN_METHODS,
        gamma=float(cfg.online_learner.gamma or 0.1),
        floor=float(cfg.online_learner.weight_floor or 0.01),
        warmup=int(cfg.online_learner.warmup_periods or 60))
    fusion = fuse(results, cfg, base, exp3.effective(MAIN_METHODS))
    passed, refuted = replay._gate(cfg, sorted(expanded), fusion, results, base)
    pool = sorted(set(passed) or expanded)
    sel = select_top5(fusion, pool, cfg)
    picks = select_52(fusion, sel.core, set(expanded), results,
                      results["omission"].scores, results.get("contrarian"), cfg)

    L = []
    L.append("=" * 78)
    L.append(f"  {target} 期 全模块明细（历史 {len(hist)} 期 / 拓展集合 {len(expanded)} 个）")
    L.append("=" * 78)
    L.append(f"本期点位（20）：{fmt(entry.points)}")
    L.append(f"拓展集合（{len(expanded)}）：{fmt(sorted(expanded))}")
    L.append("")

    order = ["omission"] + list(MAIN_METHODS) + ["contrarian", "adversarial"]
    for name in order:
        if name == "adversarial":
            L.append("── adversarial ──  状态：门控已执行（推荐层调用）")
            _passed_in_pool = len(set(passed) & expanded)
            L.append(f"   候选池 {len(expanded)} → 通过 {_passed_in_pool}，"
                     f"否决 {len(expanded) - _passed_in_pool}；"
                     f"全 80 码共标记否决 {len(refuted)} 个")
            L.append("")
            continue
        res = results.get(name)
        if res is None:
            L.append(f"── {name} ── 未运行")
            L.append("")
            continue
        L.append(f"── {name} ──  状态：{'正常' if res.sufficient else '降级'}")
        if not res.sufficient:
            L.append(f"   降级原因：{res.diagnostics.get('degraded', '未知')}")
        L.append(f"   全 80 码 Top10：{fmt(res.top(10))}")
        L.append(f"   拓展集合 Top5：{fmt(res.top(5, restrict_to=expanded))}")
        if res.metrics:
            keep = {k: v for k, v in res.metrics.items()
                    if isinstance(v, (int, float, str))}
            if keep:
                L.append("   关键指标：" + "，".join(f"{k}={v}" for k, v in keep.items()))
        if res.diagnostics:
            L.append("   诊断：" + "，".join(
                f"{k}={v}" for k, v in res.diagnostics.items()
                if isinstance(v, (int, float, str))))
        narr = [b.text for b in res.narrative if b.text]
        if narr:
            L.append("   解读：")
            for t in narr[:4]:
                L.append("     " + t.replace("\n", " "))
        L.append("")

    L.append("── 七维融合（H1-H7）──")
    L.append("   号  " + "  ".join(f"{d:>5}" for d in DIM_NAMES) + "   综合")
    for n in sel.core:
        vals = [fusion.h_values.get(d, {}).get(n, 0.0) for d in DIM_NAMES]
        L.append(f"   {n:02d}  " + "  ".join(f"{v:5.2f}" for v in vals)
                 + f"   {fusion.composite.get(n, 0.0):5.1f}")
    if fusion.skipped_dims:
        L.append(f"   未生效维度：{fusion.skipped_dims}")
    L.append("")
    L.append(f"五码核心：{fmt(picks.core)}")
    L.append(f"两码备防：{fmt(picks.defensive)}")
    return "\n".join(L)


BUCKET_PATTERNS = {
    "独胆": r"至尊独胆：【\s*(\d+)\s*】",
    "选2": r"黄金双飞选2：【([^】]+)】",
    "选3": r"必拿铁三角选3：【([^】]+)】",
    "选5": r"五虎上将选5：【([^】]+)】",
    "选7": r"稳健实战选7：【([^】]+)】",
    "选10": r"围底十码选10：【([^】]+)】",
    "绝杀": r"绝杀池：([^\n]+)",
}


def parse_bucket(text: str, pattern: str) -> list[int]:
    m = re.search(pattern, text)
    if not m:
        return []
    return [int(x) for x in re.findall(r"\d+", m.group(1))]


def review_prev(prev: int, prev_pub_dir: Path) -> str:
    cfg = load_config(None)
    ds = source.load_dataset(cfg, allow_fetch=False)
    draw = next((d for d in ds.draws if d.period == prev), None)
    if draw is None:
        return f"未找到 {prev} 期开奖，无法复盘。"
    actual = set(draw.numbers)
    pub = prev_pub_dir / f"kl8_wechat_publish_{prev}.txt"
    if not pub.exists():
        # 兼容手动指定 --prev：按输出目录反查，再按开奖日期兜底
        cands = sorted(Path("output").glob(f"*/kl8_wechat_publish_{prev}.txt"))
        pub = cands[-1] if cands else (
            Path("output") / draw.date.strftime("%Y%m%d")
            / f"kl8_wechat_publish_{prev}.txt")
    text = pub.read_text(encoding="utf-8") if pub.exists() else ""

    L = []
    L.append("=" * 78)
    L.append(f"  {prev} 期 复盘：昨日推荐 vs 实际开奖")
    L.append("=" * 78)
    L.append(f"实际开奖（20）：{fmt(sorted(actual))}")
    L.append("")
    if not text:
        L.append(f"未找到昨日发布原文（{pub}），无法复盘。")
        return "\n".join(L)

    L.append(f"{'桶位':<6}{'推荐号码':<42}{'命中':<6}{'命中号码'}")
    L.append("-" * 78)
    for label, pat in BUCKET_PATTERNS.items():
        nums = parse_bucket(text, pat)
        if not nums:
            continue
        hit = sorted(set(nums) & actual)
        L.append(f"{label:<6}{fmt(nums):<44}{len(hit)}/{len(nums):<4}{fmt(hit)}")

    t1 = [tuple(int(x) for x in g.split("-")) for g in
          re.findall(r"T1核心组\d：([\d\-]+)", text)]
    t2 = [tuple(int(x) for x in g.split("-")) for g in
          re.findall(r"T2对冲组\d：([\d\-]+)", text)]
    L.append("")
    for label, groups in (("T1核心", t1), ("T2对冲", t2)):
        for g in groups:
            hit = sorted(set(g) & actual)
            L.append(f"{label:<6}{'-'.join(f'{n:02d}' for n in g):<16}"
                     f"{len(hit)}/3    {fmt(hit)}")

    kill = parse_bucket(text, BUCKET_PATTERNS["绝杀"])
    if kill:
        bad = sorted(set(kill) & actual)
        L.append("")
        L.append(f"绝杀池：{fmt(kill)}  错杀 {len(bad)}/{len(kill)}：{fmt(bad)}")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", type=int, default=None)
    ap.add_argument("--prev", type=int, default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT))
    args = ap.parse_args(argv)

    target, prev, out_dir, prev_pub = _resolve(
        Path(args.preflight), args.period, args.prev, args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    detail = module_details(target, out_dir)
    review = review_prev(prev, prev_pub)
    (out_dir / f"module_details_{target}.txt").write_text(
        detail, encoding="utf-8", newline="\r\n")
    (out_dir / f"review_{prev}.txt").write_text(
        review, encoding="utf-8", newline="\r\n")
    print(detail)
    print()
    print(review)
    print()
    print(f"已写入 {out_dir}/module_details_{target}.txt")
    print(f"已写入 {out_dir}/review_{prev}.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())