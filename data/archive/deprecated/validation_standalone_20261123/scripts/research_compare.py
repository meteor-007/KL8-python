# -*- coding: utf-8 -*-
"""研究引擎对比 CLI（默认使用 A 内 vendored 的 research/kl8_engine）。

    python scripts/research_compare.py --period 2026302
    python scripts/research_compare.py --epochs 10 --fusion borda
    python scripts/research_compare.py --points "01 02 ... 80"
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kl8.config import load_config
from kl8.data_io import validate_core_points
from tools.research_bridge import (DEFAULT_BUDGET, DEFAULT_DL_WEIGHT,
                                   DEFAULT_EPOCHS, DEFAULT_SEQ_LEN,
                                   ResearchConfig, default_target_period,
                                   run_research)


def _strict_points(raw: str) -> list[int]:
    """严格解析 --points：不允许被静默丢弃的 token。"""
    tokens = [t for t in re.split(r"[\s,，、;；|\-]+", raw.strip()) if t]
    bad = [t for t in tokens if not t.isdigit()]
    if bad:
        raise ValueError(f"包含非法 token: {bad[:3]}")
    nums = [int(t) for t in tokens]
    ok, msg = validate_core_points(nums)
    if not ok:
        raise ValueError(msg)
    return nums


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine-root",
                    default=str(ROOT / "research"),
                    help="研究引擎根目录（默认 A 内 vendored research/；兼容外部 C 仓库）")
    ap.add_argument("--period", type=int, default=None,
                    help="目标期；默认 A 最新开奖 +1")
    ap.add_argument("--points", default=None,
                    help="一行 20 个点位；默认从点位档案读取")
    ap.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    ap.add_argument("--seq-len", type=int, default=DEFAULT_SEQ_LEN)
    ap.add_argument("--dl-weight", type=float, default=DEFAULT_DL_WEIGHT)
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--fusion", choices=["borda", "weighted"], default="borda")
    ap.add_argument("--points-mode", choices=["compare", "boost"], default="compare")
    ap.add_argument("--no-comparison", dest="comparison", action="store_false")
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--engine-output-dir", default=None,
                    help="研究引擎的稳定输出目录（用于跨期复盘）")
    args = ap.parse_args(argv)

    cfg = load_config(None)
    history = Path(cfg.shared_history_file)
    points_path = Path(cfg.cache_dir) / "points_archive.txt"
    if not points_path.exists():
        points_path = Path(cfg.shared_points_file)
    if not history.exists():
        print(f"✗ 找不到历史档案：{history}", file=sys.stderr)
        return 1

    period = args.period if args.period is not None else default_target_period(history)
    out_dir = Path(args.output_dir) if args.output_dir else (
        ROOT / "output" / "research" / str(period))
    points = None
    if args.points:
        try:
            points = _strict_points(args.points)
        except ValueError as exc:
            print(f"✗ --points 校验失败：{exc}", file=sys.stderr)
            return 1

    rc = ResearchConfig(
        engine_root=Path(args.engine_root),
        output_dir=out_dir,
        history_path=history,
        points_path=points_path,
        period=period,
        points=points,
        epochs=args.epochs,
        seq_len=args.seq_len,
        dl_weight=args.dl_weight,
        budget=args.budget,
        fusion=args.fusion,
        points_mode=args.points_mode,
        comparison=args.comparison,
        engine_output_dir=Path(args.engine_output_dir) if args.engine_output_dir else None,
    )
    try:
        summary = run_research(rc)
    except (OSError, ValueError, ImportError) as exc:
        print(f"✗ 研究引擎执行失败：{exc}", file=sys.stderr)
        return 1

    b = summary.get("borda", {})
    w = summary.get("weighted", {})
    def fmt(xs):
        return " ".join(f"{int(x):02d}" for x in xs)
    print(f"研究对比完成：第 {summary['period']} 期")
    print(f"  研究 Borda 主选 : {fmt(b.get('main_pool', []))}")
    print(f"  研究 Borda 金胆 : {fmt(b.get('gold_pool', []))}")
    print(f"  研究 30 码大底  : {fmt(b.get('shrinkage_pool_30', []))}")
    if w:
        print(f"  研究加权主选   : {fmt(w.get('main_pool', []))}")
    print(f"  报告：{out_dir / 'research_compare.md'}")
    print(f"  JSON：{out_dir / 'research_compare.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())