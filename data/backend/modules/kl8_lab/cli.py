# -*- coding: utf-8 -*-
"""快乐8 点位+遗漏号分析 · 命令行入口（§3.3 / §11.2）。

已迁入 K8-QUANT 主系统（backend/core/kl8_lab/），两种调用方式等价：

    python -m backend.core.kl8_lab.cli <命令>      # 推荐（在仓库根目录执行）
    python backend/core/kl8_lab/cli.py <命令>      # 脚本直调，自动自举包路径

命令（原《点位+遗漏号分析》项目 CLI 全量保留）：

    run / daily                        # fetch → 校验 → 分析 → 报告（一条命令，§11.2）
    daily --points data/uploads/x.txt  # 覆盖点位文件
    daily --methods cluster,markov      # 只跑部分方法
    analyze / report                   # 只做分析并出报告
    fetch [--seed]                     # 增量抓取开奖（--seed 另存本地种子）
    input-points                       # 交互录入今日点位（§3.3）
    input-points --points "01 02 …" --yes
    points add -i / points add -r "..." / points list
    backfill --from P --to Q           # 别名 catchup
    backtest [--n 60|--all] [--no-report]
    doctor                             # 数据体检（§2.6）

退出码：0 = 成功且有统计显著信号；2 = 成功但走 §9.8 退化分支（**正常结果**）；
        1 = 运行错误。
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

# 支持 `python backend/modules/kl8_lab/cli.py <命令>` 直接运行：无父包上下文时自举包名
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "backend.modules.kl8_lab"

from . import observability, points_input, registry, report, replay, source
from .config import load_config
from .contracts import ModuleResult
from .data_io import PointEntry, format_numbers_line
from .ensemble import MAIN_METHODS, Exp3State, fuse
from .points import compute_base_stats, expand
from .scoring import select_52, select_top5

EXIT_OK, EXIT_ERROR, EXIT_DEGRADED = 0, 1, 2


# ── 在线学习结算（无前视：用**上一期**的开奖更新权重）─────────

def _settle_pending(cfg, dataset, exp3: Exp3State) -> None:
    """若上次运行留下的待结算期已开出，用其开奖更新 Exp3 权重。

    这是实盘路径下"每期重算"的实现：权重只由**已开出**的期决定，
    当前待预测期永远看不到自己的开奖。
    """
    pend = exp3.pending or {}
    if not pend:
        return
    period = int(pend.get("period") or 0)
    method_top5 = {k: list(v) for k, v in (pend.get("method_top5") or {}).items()}
    draw = next((d for d in dataset.draws if d.period == period), None)
    if draw is None:
        observability.info(f"待结算期 {period:07d} 尚未开出，权重保持不变。")
        return
    if not method_top5:
        exp3.pending = {}
        return
    exp3.update(method_top5, set(draw.numbers))
    exp3.pending = {}
    observability.info(f"已用 {period:07d} 开奖结算在线权重"
                       f"（累计 {exp3.periods} 期）。")


def _set_pending(exp3: Exp3State, period: int,
                 method_top5: dict[str, list[int]]) -> None:
    exp3.pending = {"period": int(period),
                    "method_top5": {k: list(v) for k, v in method_top5.items()}}


# ── 分析流水线 ────────────────────────────────────────────────

def _shared_counts(cfg) -> tuple[int, int]:
    """共享档案期数（供 §8.5 对账）。读取失败按 0 计，不阻断主流程。"""
    from .data_io import ParseReport, load_draws, load_points_archive
    rep = ParseReport()
    n_draws = n_points = 0
    try:
        if cfg.shared_history_file.exists():
            n_draws = len(load_draws(str(cfg.shared_history_file), rep))
    except (OSError, UnicodeDecodeError, ValueError):
        n_draws = 0
    try:
        if cfg.shared_points_file.exists():
            n_points = len(load_points_archive(str(cfg.shared_points_file), rep))
    except (OSError, UnicodeDecodeError, ValueError):
        n_points = 0
    return n_draws, n_points


def _analyze_target(cfg, dataset, entry: PointEntry, target,
                    methods: list[str] | None = None) -> report.ReportContext:
    """对目标期执行完整分析，返回渲染上下文。

    `methods` 非空时只跑指定方法子集（§3.3 调试用），且不改动在线学习状态。
    """
    hist = dataset.history_before(target.period)
    if len(hist) < 30:
        raise RuntimeError(f"目标期 {target.period:07d} 之前仅 {len(hist)} 期历史，"
                           f"不足以分析（最少 30 期）。")

    expanded = expand(entry.points)
    base_stats = compute_base_stats(hist, expanded)
    names = list(methods) if methods else list(MAIN_METHODS)
    observability.info(f"历史 {len(hist)} 期 / 点位 {len(entry.points)} 个 / "
                       f"拓展集合 {len(expanded)} 个，开始 {len(names)} 方法分析…")

    results, _ = registry.run_all(hist, expanded, base_stats, cfg,
                                  names, run_meta=True)

    ol = cfg.online_learner
    full_run = methods is None
    exp3 = Exp3State.load_or_uniform(cfg.state_file, MAIN_METHODS,
                                     gamma=float(ol.gamma or 0.1),
                                     floor=float(ol.weight_floor or 0.01),
                                     warmup=int(ol.warmup_periods or 60))
    if full_run:
        _settle_pending(cfg, dataset, exp3)
    weights = exp3.effective(MAIN_METHODS)

    fusion = fuse(results, cfg, base_stats, weights)

    passed, _ = replay._gate(cfg, sorted(expanded), fusion, results, base_stats)
    pool = sorted(set(passed) or expanded)
    selection = select_top5(fusion, pool, cfg)
    picks = select_52(fusion, selection.core, set(expanded), results,
                      results["omission"].scores, results.get("contrarian"), cfg)

    # §8.5 对账：共享档案期数较上次运行减少 → 疑似被外部覆盖
    n_shared_draws, n_shared_points = _shared_counts(cfg)
    reconcile_notes = [m for m in (
        observability.reconcile(cfg.state_dir, "shared_history_periods", n_shared_draws),
        observability.reconcile(cfg.state_dir, "shared_points_periods", n_shared_points),
    ) if m]

    state = observability.staleness(dataset.draws[0].date if dataset.draws else None, cfg)
    ctx = report.ReportContext(
        cfg=cfg, target=target, entry=entry, dataset=dataset,
        health=dataset.health,
        staleness=f"{state[1]} {'✅' if state[0] == 'ok' else '⚠️'}",
        results=results, fusion=fusion, selection=selection, picks=picks,
        base_stats=base_stats, expanded=expanded,
        module_notes=[f"{n}（{r.diagnostics.get('degraded', '数据不足')}）"
                      for n, r in results.items() if not r.sufficient],
        degradation_reasons=[r.diagnostics["degraded"] for r in results.values()
                             if not r.sufficient and r.diagnostics.get("degraded")],
        reconcile_note="；".join(reconcile_notes),
    )

    # 记录待结算状态：本期的方法 top5 供下一期开奖后更新权重。
    # 仅完整分析时写入；`--methods` 子集调试不得污染在线学习状态。
    if full_run:
        method_top5: dict[str, list[int]] = {}
        for m in MAIN_METHODS:
            res = results.get(m)
            if res is not None and res.sufficient:
                method_top5[m] = res.top(5, restrict_to=expanded)
        _set_pending(exp3, target.period, method_top5)
        exp3.save(cfg.state_file)

    observability.write_heartbeat(cfg.state_dir, {
        "command": "analyze", "target_period": target.period,
        "target_date": str(target.date),
        "latest_draw": dataset.draws[0].period if dataset.draws else None,
        "pairable": dataset.health.pairable_count,
        "dirty": dataset.health.dirty,
        "insufficient_modules": [n for n, r in results.items() if not r.sufficient],
        "shared_history_periods": n_shared_draws,
        "shared_points_periods": n_shared_points,
    })
    return ctx


# ── 子命令 ────────────────────────────────────────────────────

def cmd_doctor(cfg, args) -> int:
    ds = source.load_dataset(cfg, allow_fetch=False)
    print("=" * 62)
    print("数据体检（§2.6）")
    print("=" * 62)
    print(ds.health.render())
    lvl, msg = observability.staleness(
        ds.draws[0].date if ds.draws else None, cfg)
    print(f"数据新鲜度        : [{lvl}] {msg}")
    print(f"\n路径解析：\n{cfg.describe_paths()}")
    bad = ds.health.malformed or not ds.pairable()
    return EXIT_ERROR if bad else EXIT_OK


def cmd_fetch(cfg, args) -> int:
    from . import fetcher
    merged = fetcher.fetch_incremental(cfg, dry_run=args.dry_run)
    if not merged:
        observability.error("无可用数据（本地档案与数据源均为空）。")
        return EXIT_ERROR
    if getattr(args, "seed", False):
        from . import source as _src
        draws, _ = _src.load_history_only(cfg, allow_fetch=False)
        seed_path = cfg.seed_dir / "kl8_history_seed.csv"
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        recent = sorted(draws, key=lambda d: d.period, reverse=True)[:500]
        seed_path.write_text("".join(format_numbers_line(d.date, d.period, list(d.numbers)) + "\n"
                                     for d in recent),
                            encoding="utf-8", newline="\r\n")
        observability.info(f"本地种子已生成：{seed_path}（{len(recent)} 期）")
    return EXIT_OK


def cmd_points(cfg, args) -> int:
    if args.action == "list":
        entries = points_input.load_points_any(cfg)
        print(f"点位档案共 {len(entries)} 期"
              f"（共享档案 + 本地副本合并；共享={cfg.shared_points_file}）")
        for p in sorted(entries, reverse=True)[:15]:
            e = entries[p]
            flag = "  ⚠ 脏" if e.dirty else ""
            print(f"  {p:07d}  {e.date}  {len(e.points)} 个点位{flag}")
        return EXIT_OK

    if args.action != "add":
        print("用法：main.py points {add|list}", file=sys.stderr)
        return EXIT_ERROR

    if args.interactive or not args.raw:
        info = points_input.entry_interactive(cfg)
    else:
        info = points_input.entry_from_raw(cfg, args.raw, period=args.period)
    print(f"已录入：{info}")
    return EXIT_OK


def cmd_backfill(cfg, args) -> int:
    """§11.3：只补点位、不补开奖；逐期人工录入，禁止自动生成。"""
    draws, _ = source.load_history_only(cfg, allow_fetch=False)
    by_period = {d.period: d for d in draws}
    if args.start not in by_period:
        observability.error(f"起始期 {args.start:07d} 不在开奖档案中，请先 fetch。")
        return EXIT_ERROR

    cur, date_ = args.start, by_period[args.start].date
    entries = points_input.load_points_any(cfg)
    todo = []
    while cur < args.end:
        nxt = points_input.next_period_after(cur, date_, set(by_period))
        d = by_period.get(nxt)
        if d is None:
            observability.warn(f"{nxt:07d} 无开奖记录，停止推进。")
            break
        cur, date_ = nxt, d.date
        if cur not in entries:
            todo.append((cur, d.date))

    if not todo:
        print("该区间内没有缺失的点位，无需补录。")
        return EXIT_OK

    print(f"需补录 {len(todo)} 期点位（逐期人工录入，系统不会自动生成）：")
    for period, d in todo:
        print(f"\n── {period:07d}  {d} ──")
        try:
            points_input.entry_interactive(cfg)
        except (EOFError, KeyboardInterrupt):
            observability.warn("用户中断，已录入的部分保留。")
            return EXIT_ERROR
    print("\n补录完成，建议重跑 `python main.py doctor` 与 `python main.py backtest`。")
    return EXIT_OK


def cmd_backtest(cfg, args) -> int:
    ds = source.load_dataset(cfg, allow_fetch=False)
    if not ds.pairable():
        observability.error("无可配对期，无法回测。")
        return EXIT_ERROR

    bt = replay.run_backtest(cfg, ds, n=args.n, all_periods=args.all)
    bt.exp3.save(cfg.state_file)

    print("=" * 62)
    skip_note = f"跳过 {bt.skipped}"
    if bt.missing_points:
        skip_note += f"（其中遗漏期 {bt.missing_points}）"
    print(f"滚动外样本回测 · {bt.window_label} · T={bt.T}（{skip_note}）")
    print("=" * 62)
    if bt.system_test:
        print(bt.system_test.render())
    if bt.method_tests:
        print("\n各方法（BH-FDR 校正后）：")
        for m, tr in sorted(bt.method_tests.items(), key=lambda kv: -kv[1].lift):
            print(f"  {m:12s} {tr.render()}")
    if bt.baselines:
        print("\n基线对照：")
        print(bt.baselines.render())
    if bt.degraded:
        print("\n⚠️  全部方法未通过随机基线检验——按 §9.8，推荐与随机选取无统计差异。")

    if not args.no_report:
        out = cfg.out_dir / f"kl8_backtest_{bt.T}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# 快乐8 滚动外样本回测报告（T={bt.T}）", "",
                 f"- 窗口：{bt.window_label}；跳过 {bt.skipped} 期"
                 f"（遗漏期 {bt.missing_points}）；耗时 {bt.elapsed_sec:.1f}s", ""]
        if bt.system_test:
            lines.append(f"- 系统：{bt.system_test.render()}")
        lines.append("")
        if bt.baselines:
            lines += ["## 基线对照", "", bt.baselines.render(), ""]
            lines += [f"> {n}" for n in bt.baselines.notes] + [""]
        if bt.method_tests:
            lines += ["## 各方法", "", "| 方法 | T | 均值 | lift | z | q | 判定 |",
                      "|---|---|---|---|---|---|---|"]
            for m, tr in bt.method_tests.items():
                lines.append(f"| {m} | {tr.T} | {tr.mean_hits:.4f} | {tr.lift:.4f} | "
                             f"{tr.z:+.3f} | {tr.q_value:.4f} | {tr.verdict} |")
            lines.append("")
        lines += ["---", "", f"> **免责声明**：{report.DISCLAIMER}", ""]
        text = "\n".join(lines)
        report.assert_compliant(text)
        out.write_text(text, encoding="utf-8", newline="\r\n")
        print(f"\n报告已写入：{out}")

    return EXIT_DEGRADED if bt.degraded else EXIT_OK


def _resolve_target(cfg, ds, period_override: int | None):
    """确定分析目标期。默认取"最新开奖之后的一期"（§8.3），可用 --period 覆盖。"""
    if period_override is None:
        return points_input.infer_target(cfg, ds.draws, ds.points)

    p = int(period_override)
    entry = ds.points.get(p)
    draw = next((d for d in ds.draws if d.period == p), None)
    if entry is None:
        return None
    d = entry.date or (draw.date if draw else None)
    if d is None:
        raise RuntimeError(f"期号 {p:07d} 既无开奖日期也无点位日期，无法定位。")
    return points_input.TargetInfo(period=p, date=d, already_input=True,
                                   existing_points=entry.points)


def cmd_analyze(cfg, args) -> int:
    cfg.override_files(getattr(args, "points", None), getattr(args, "history", None))
    ds = source.load_dataset(cfg)
    target = _resolve_target(cfg, ds, getattr(args, "period", None))
    if target is None:
        raise RuntimeError(
            f"期号 {args.period:07d} 不在点位档案中。请先用 `points list` 查看可用期号。")
    entry = ds.points.get(target.period)
    if entry is None:
        observability.error(
            f"目标期 {target.period:07d}（{target.date}）尚无点位。\n"
            f"请先录入：python main.py points add -i")
        return EXIT_ERROR

    ctx = _analyze_target(cfg, ds, entry, target,
                          methods=_parse_methods(getattr(args, "methods", None)))

    if args.backtest is not False:
        bt = replay.run_backtest(cfg, ds, n=(args.n or cfg.backtest.default_n))
        ctx.backtest = bt
        ctx.degradation_reasons.extend([])

    print(report.render_stdout(ctx))
    path = report.write_report(ctx, args.out)
    print(f"\n报告已写入：{path}")

    if ctx.degraded:
        return EXIT_DEGRADED
    if ctx.backtest and ctx.backtest.system_test and ctx.backtest.system_test.significant:
        return EXIT_OK
    return EXIT_DEGRADED


def cmd_run(cfg, args) -> int:
    """一条命令：fetch → 分析 → 报告（§11.2，§3.3 别名 `daily`）。"""
    from . import fetcher
    cfg.override_files(getattr(args, "points", None), getattr(args, "history", None))
    if not args.no_fetch:
        fetcher.fetch_incremental(cfg)
    return cmd_analyze(cfg, args)


def _parse_methods(spec: str | None) -> list[str] | None:
    """§3.3：`--methods cluster,markov,entropy` → 方法名列表。"""
    if not spec:
        return None
    names = [s.strip() for s in spec.split(",") if s.strip()]
    unknown = [n for n in names if n not in MAIN_METHODS]
    if unknown:
        raise RuntimeError(f"未知方法 {unknown}；可选：{list(MAIN_METHODS)}")
    return names


def cmd_input_points(cfg, args) -> int:
    """§3.3：`input-points [--points "01 02 …"] [--yes] [--period P]`。"""
    raw = getattr(args, "points_raw", None)
    if raw is None:
        info = points_input.entry_interactive(cfg)
        print(f"已录入：{info}")
        return EXIT_OK if info.get("status") != "error" else EXIT_ERROR

    nums = points_input.parse_points_input(raw)
    ok, msg = points_input.validate_core_points(nums)
    if not ok:
        observability.error(f"点位校验失败：{msg}")
        return EXIT_ERROR
    if not args.yes:
        print(f"将录入 {len(nums)} 个点位：{' '.join(f'{n:02d}' for n in nums)}")
        try:
            ans = input("确认？[y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            return EXIT_OK
        if ans not in ("y", "yes"):
            print("已取消。")
            return EXIT_OK
    info, _target = points_input.entry_from_raw(cfg, raw, period=args.period)
    print(f"已录入：{info}")
    return EXIT_OK if info.get("status") != "error" else EXIT_ERROR


# ── argparse ──────────────────────────────────────────────────

def _add_daily_args(sp: argparse.ArgumentParser) -> None:
    """`run` / `daily` / `analyze` / `report` 共用的参数（§3.3 / §11.2）。"""
    sp.add_argument("--no-fetch", action="store_true")
    sp.add_argument("--period", type=int, default=None,
                    help="指定分析某历史期号（默认自动推断下一期）")
    sp.add_argument("--no-backtest", dest="backtest", action="store_false")
    sp.add_argument("--n", type=int, default=None, help="回测窗口期数")
    sp.add_argument("--out", default=None)
    sp.add_argument("--points", default=None, help="覆盖点位文件路径（§3.3）")
    sp.add_argument("--history", default=None, help="覆盖开奖文件路径（§3.3）")
    sp.add_argument("--methods", default=None,
                    help="只跑部分方法，逗号分隔（§3.3 调试用）")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py", description="快乐8 点位+遗漏号分析（统计观察工具，非预测器）")
    p.add_argument("--config", default=None, help="配置文件路径（默认 ./config.yaml）")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    for _name, _help in (("run", "fetch → 分析 → 报告（§11.2）"),
                         ("daily", "同 run（§3.3 别名）")):
        _add_daily_args(sub.add_parser(_name, help=_help))

    for _name, _help in (("analyze", "只做分析并出报告"),
                         ("report", "同 analyze（§11.2 别名）")):
        _add_daily_args(sub.add_parser(_name, help=_help))

    sp = sub.add_parser("input-points", help="录入今日点位（§3.3）")
    sp.add_argument("--points", dest="points_raw", default=None,
                    help='一行号码文本，如 "04 10 12 …"；省略则交互录入')
    sp.add_argument("--yes", action="store_true", help="跳过确认（非交互）")
    sp.add_argument("--period", type=int, default=None)

    sp = sub.add_parser("doctor", help="数据体检（§2.6）")

    sp = sub.add_parser("fetch", help="增量抓取开奖")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--seed", action="store_true", help="另存最近 500 期为本地种子")

    sp = sub.add_parser("points", help="点位档案")
    sp.add_argument("action", choices=["add", "list"])
    sp.add_argument("-i", "--interactive", action="store_true")
    sp.add_argument("-r", "--raw", default=None, help="一行文本，如 '01 05 12 ...'")
    sp.add_argument("--period", type=int, default=None)

    for _name, _help in (("backfill", "补跑遗漏期点位（§11.3）"),
                         ("catchup", "同 backfill（§3.3 别名）")):
        sp = sub.add_parser(_name, help=_help)
        sp.add_argument("--from", dest="start", type=int, required=True)
        sp.add_argument("--to", dest="end", type=int, required=True)

    sp = sub.add_parser("backtest", help="滚动外样本回测")
    sp.add_argument("--n", type=int, default=None)
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--no-report", action="store_true")

    return p


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认 GBK，中文报告会乱码；统一强制 UTF-8 输出。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
    except Exception as exc:
        print(f"配置加载失败：{exc}", file=sys.stderr)
        return EXIT_ERROR

    cfg.ensure_dirs()
    import logging
    observability.setup(cfg.log_dir,
                        level=logging.DEBUG if args.verbose else logging.INFO)
    observability.rotate(cfg.log_dir)

    if args.cmd in (None, "run", "daily"):
        if args.cmd is None:
            args.no_fetch = False
            args.backtest = True
            args.n = None
            args.out = None
            args.period = None
            args.points = None
            args.history = None
            args.methods = None
        handler = cmd_run
    else:
        handler = {
            "analyze": cmd_analyze, "report": cmd_analyze,
            "doctor": cmd_doctor, "fetch": cmd_fetch,
            "points": cmd_points, "input-points": cmd_input_points,
            "backfill": cmd_backfill, "catchup": cmd_backfill,
            "backtest": cmd_backtest,
        }[args.cmd]

    try:
        return handler(cfg, args)
    except KeyboardInterrupt:
        observability.warn("用户中断。")
        return EXIT_ERROR
    except Exception as exc:
        observability.error(f"运行失败：{exc}")
        if args.verbose:
            traceback.print_exc()
        else:
            print(traceback.format_exc(limit=3), file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
