# -*- coding: utf-8 -*-
"""kl8_lab 服务层：把《点位+遗漏号分析》的分析链路封装成 Web 可用的产物读写接口。

分工（与主系统既有约定一致）：
  · 重计算放在每日脚本 `run_kl8_lab_daily.py` / `service.run_daily()` 里，落盘 JSON + Markdown；
  · Web 只读接口一律走 `load_*` 系列，只读文件、不联网、不触发分析。

数据诚信约定（主系统 A 包整改口径）：
  · 上游缺数据 → 字段留 `null` / 显式标注 `degraded`，绝不填占位号码或中性指标；
  · 未做样本外检验的量（Lift / 显著性）不得输出结论，置 null 并给出 `verdict`；
  · 前端按 `!= null` 判空渲染 `--`。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

from . import observability, points_input, replay, report, source
from .config import load_config
from .ensemble import DIM_NAMES, MAIN_METHODS
from .numerics import safe_div
from .omission import profile_number
from .scoring import zone_label

SUMMARY_FILE = "latest_summary.json"
BACKTEST_FILE = "backtest_summary.json"
REPORTS_SUBDIR = "reports"

DIM_LABELS = {
    "H1": "热度",
    "H2": "遗漏反弹",
    "H3": "集群",
    "H4": "周期/波动",
    "H5": "共现/图",
    "H6": "马尔可夫",
    "H7": "熵/均衡",
}

_MODULE_LABELS = {
    "cluster": "① 连号集群行为",
    "cyclic": "② 周期性共振与波段节奏",
    "heatmap": "③ 数字场域能量分布",
    "markov": "⑤ 马尔可夫转移 + HMM",
    "fibonacci": "⑥ 斐波那契/黄金分割",
    "linalg_svd": "⑦ 共现/协方差/SVD",
    "complex_fft": "⑧ 复变/Hilbert/FFT",
    "graph_net": "⑨ 图网络关系挖掘",
    "volatility": "⑩ 波动率聚类",
    "remainder": "⑪ 余数空间映射",
    "entropy": "⑫ 熵值评估与均衡",
}


# ── 基础 ──────────────────────────────────────────────────────

def get_cfg():
    """加载 kl8_lab 子系统配置（根目录 = backend/core/kl8_lab）。"""
    return load_config()


def _out_dir(cfg=None) -> Path:
    cfg = cfg or get_cfg()
    d = Path(cfg.out_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _num(value: Any) -> Optional[float]:
    """把数值转成 JSON 友好的 float；非有限值一律返回 None（不编造 0）。"""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return round(f, 4)


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


# ── 序列化：分析上下文 → 前端友好 JSON ────────────────────────

def _serialize_health(health) -> dict:
    return {
        "points_count": _int(getattr(health, "points_count", None)),
        "draws_count": _int(getattr(health, "draws_count", None)),
        "pairable_count": _int(getattr(health, "pairable_count", None)),
        "points_only": [f"{p:07d}" for p in (getattr(health, "points_only", None) or [])],
        "draws_only_count": _int(getattr(health, "draws_only_count", None)),
        "duplicate_dates": dict(getattr(health, "duplicate_dates", None) or {}),
        "inversions": [f"{p:07d}" for p in (getattr(health, "inversions", None) or [])],
        "malformed": _int(getattr(health, "malformed", None)),
        "points_source": getattr(health, "points_source", "") or "",
        "draws_source": getattr(health, "draws_source", "") or "",
    }


def _serialize_methods(ctx) -> list[dict]:
    out: list[dict] = []
    weights = (ctx.fusion.method_weights if ctx.fusion else {}) or {}
    for name in MAIN_METHODS:
        res = ctx.results.get(name)
        if res is None:
            continue
        out.append({
            "name": name,
            "label": _MODULE_LABELS.get(name, name),
            "sufficient": bool(res.sufficient),
            "degraded": res.diagnostics.get("degraded"),
            "weight": _num(weights.get(name)),
            "top5": [int(n) for n in res.top(5, restrict_to=ctx.expanded)] if res.sufficient else [],
            "metrics": _jsonable(res.metrics),
        })
    return out


def _jsonable(value: Any, depth: int = 0) -> Any:
    """把 metrics 等可能含 tuple/非有限数的结构转成 JSON 安全结构。"""
    if depth > 5:
        return None
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (int,)):
        return value
    if isinstance(value, float):
        return _num(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v, depth + 1) for v in value]
    return str(value)


def _serialize_dimensions(ctx) -> dict:
    fusion = ctx.fusion
    if fusion is None:
        return {}
    out: dict[str, dict] = {}
    for dim in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        vec = fusion.h_values.get(dim)
        out[dim] = {
            "label": DIM_LABELS.get(dim, DIM_NAMES.get(dim, dim)),
            "weight": _num(fusion.dim_weights.get(dim)) if dim in fusion.dim_weights else None,
            "active": vec is not None,
            "top10": (sorted(vec, key=lambda n: (-vec[n], n))[:10] if vec else []),
        }
    return out


def _serialize_matrix(ctx, draws) -> list[dict]:
    """80 码逐号明细：综合分 + H1–H7 + 基础统计 + 遗漏画像。

    `draws` 必须是**目标期之前**的历史（无前视，§9.2），由调用方传入。
    """
    fusion = ctx.fusion
    rows: list[dict] = []
    stats = ctx.base_stats or {}
    for n in range(1, 81):
        st = stats.get(n)
        prof = None
        try:
            prof = profile_number(draws, n)
        except Exception:                       # 单号画像失败不影响整表
            prof = None
        h = {}
        if fusion is not None:
            for dim in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
                vec = fusion.h_values.get(dim)
                if vec is not None:
                    h[dim] = _num(vec.get(n))
        rows.append({
            "n": n,
            "zone": zone_label(n),
            "in_points": n in (ctx.expanded or set()),
            "composite": _num(fusion.composite.get(n)) if fusion else None,
            "h": h,
            "hit10": _int(st.hit10) if st else None,
            "hit3": _int(st.hit3) if st else None,
            "miss": _int(st.miss) if st else None,
            "z_score": _num(st.z_score) if st else None,
            "freq_full": _int(st.freq_full) if st else None,
            "T": _int(st.T) if st else None,
            "current_miss": _int(prof.current_miss) if prof else None,
            "mean_gap": _num(safe_div(sum(prof.gaps), len(prof.gaps))) if (prof and prof.gaps) else None,
            "hazard": _num(prof.hazard) if prof else None,
            "z_rebound": _num(prof.z_rebound) if prof else None,
            "weibull_fitted": bool(prof.fitted) if prof else None,
        })
    return rows


def _serialize_backtest(bt) -> dict:
    if bt is None:
        return {"available": False}
    payload: dict = {
        "available": True,
        "window_label": getattr(bt, "window_label", "") or "",
        "skipped": _int(getattr(bt, "skipped", None)),
        "missing_points": _int(getattr(bt, "missing_points", None)),
        "elapsed_sec": _num(getattr(bt, "elapsed_sec", None)),
        "degraded": bool(getattr(bt, "degraded", False)),
        "system": _serialize_test(getattr(bt, "system_test", None)),
        "methods": [],
        "baselines": None,
    }
    tests = getattr(bt, "method_tests", None) or {}
    payload["methods"] = [
        {"name": m, "label": _MODULE_LABELS.get(m, m), **_serialize_test(tr)}
        for m, tr in sorted(tests.items(), key=lambda kv: -(kv[1].lift or 0.0))
    ]
    bl = getattr(bt, "baselines", None)
    if bl is not None:
        payload["baselines"] = {
            "null_mean": _num(getattr(bl, "null_mean", None)),
            "null_sd": _num(getattr(bl, "null_sd", None)),
            "system": _serialize_test(getattr(bl, "system", None)),
            "expanded": _serialize_test(getattr(bl, "expanded_lift", None)),
            "points": _serialize_test(getattr(bl, "points_lift", None)),
            "notes": list(getattr(bl, "notes", None) or []),
        }
    return payload


def _serialize_test(tr) -> dict:
    if tr is None:
        return {"available": False}
    return {
        "available": True,
        "label": getattr(tr, "label", "") or "",
        "T": _int(getattr(tr, "T", None)),
        "mean_hits": _num(getattr(tr, "mean_hits", None)),
        "expected": _num(getattr(tr, "expected", None)),
        "lift": _num(getattr(tr, "lift", None)),
        "z": _num(getattr(tr, "z", None)),
        "p_value": _num(getattr(tr, "p_value", None)),
        "q_value": _num(getattr(tr, "q_value", None)),
        "significant": bool(getattr(tr, "significant", False)),
        "verdict": getattr(tr, "verdict", "") or "",
        "mde_lift": _num(getattr(tr, "mde_lift", None)),
    }


def build_summary(ctx, backtest=None, report_path: Optional[Path] = None) -> dict:
    """把 ReportContext 序列化为 Web 模块消费的 summary dict。"""
    target = ctx.target
    history = (ctx.dataset.history_before(target.period)
               if getattr(ctx, "dataset", None) else [])
    latest = ctx.dataset.latest_draw() if getattr(ctx, "dataset", None) else None

    omission = ctx.results.get("omission")
    omission_metrics = _jsonable(omission.metrics) if omission is not None else None

    payload = {
        "available": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target": {
            "period": target.period_str,
            "date": _iso(target.date),
            "period_iso_date": target.date.isoformat() if target.date else None,
            "already_input": bool(target.already_input),
            "points_count": len(ctx.entry.points) if ctx.entry else None,
            "points": [int(n) for n in (ctx.entry.points if ctx.entry else ())],
            "expanded_count": len(ctx.expanded or set()),
        },
        "dataset": {
            "health": _serialize_health(ctx.health),
            "latest_draw_period": latest.period if latest else None,
            "latest_draw_date": latest.date.isoformat() if latest else None,
            "history_periods_for_target": len(ctx.dataset.history_before(target.period)) if getattr(ctx, "dataset", None) else None,
        },
        "staleness": {"verdict": ctx.staleness or None},
        "methods": _serialize_methods(ctx),
        "dimensions": _serialize_dimensions(ctx),
        "top5": {
            "core": [int(n) for n in (ctx.selection.core if ctx.selection else [])],
            "relaxed": bool(ctx.selection.relaxed) if ctx.selection else None,
            "short": bool(ctx.selection.short) if ctx.selection else None,
            "notes": list(ctx.selection.notes) if ctx.selection else [],
        },
        "picks52": {
            "core": [int(n) for n in (ctx.picks.core if ctx.picks else [])],
            "defensive": [int(n) for n in (ctx.picks.defensive if ctx.picks else [])],
            "short_defensive": bool(ctx.picks.short_defensive) if ctx.picks else None,
            "notes": list(ctx.picks.notes) if ctx.picks else [],
        },
        "matrix": _serialize_matrix(ctx, history),
        "omission": {
            "available": omission is not None and bool(omission.sufficient),
            "degraded": (omission.diagnostics.get("degraded") if omission is not None else None),
            "metrics": omission_metrics,
        },
        "degradation": {
            "degraded": bool(ctx.degraded),
            "module_notes": list(ctx.module_notes or []),
            "reasons": list(ctx.degradation_reasons or []),
        },
        "reconcile_note": ctx.reconcile_note or None,
        "disclaimer": report.DISCLAIMER,
        "report_file": report_path.name if report_path else None,
    }
    if backtest is not None:
        payload["backtest"] = _serialize_backtest(backtest)
    return payload


# ── 分析执行（重计算入口） ────────────────────────────────────

def run_daily(period: Optional[int] = None,
              backtest_n: Optional[int] = None,
              allow_fetch: bool = False,
              methods: Optional[list[str]] = None,
              fallback: bool = True) -> dict:
    """执行一次完整分析并落盘。

    与 CLI `analyze` 完全同一条代码路径（复用 `cli._analyze_target`），
    因此在线权重结算、无前视约束、合规扫描行为与命令行一致。

    `fallback=True`：自动推断出的下一期尚未录入点位时，回落到点位档案中最新一期，
    并在返回的 `target.fallback` 里显式标注（今天点位还没录入时页面仍有东西可看，
    但绝不会把"上一期"伪装成"本期"）。
    """
    from . import cli as _cli

    cfg = get_cfg()
    cfg.override_files(None, None)
    ds = source.load_dataset(cfg, allow_fetch=allow_fetch)

    if allow_fetch:
        try:
            from . import fetcher
            fetched = fetcher.fetch_incremental(cfg)
            if fetched:
                ds = source.load_dataset(cfg, allow_fetch=False)
        except Exception as exc:                # 抓取失败不阻断，用本地档案继续
            observability.warn(f"增量抓取失败，改用本地档案：{exc}")

    target = _cli._resolve_target(cfg, ds, period)
    used_fallback = False
    if target is None or ds.points.get(target.period) is None:
        if period is not None:
            raise RuntimeError(f"期号 {period:07d} 不在点位档案中，无法分析。")
        if not fallback:
            missing = target.period if target else None
            raise RuntimeError(
                f"目标期 {missing:07d} 尚无点位记录，请先在「每日点位录入管理」补录该期点位。")
        latest_entry = ds.latest_points()
        if latest_entry is None:
            raise RuntimeError("点位档案为空，无法分析。请先录入点位。")
        target = _cli._resolve_target(cfg, ds, latest_entry.period)
        used_fallback = True

    entry = ds.points.get(target.period)
    if entry is None:
        raise RuntimeError(f"目标期 {target.period:07d}（{target.date}）尚无点位记录。")

    ctx = _cli._analyze_target(cfg, ds, entry, target, methods=methods)

    backtest = None
    if backtest_n:
        backtest = replay.run_backtest(cfg, ds, n=int(backtest_n))
        try:
            backtest.exp3.save(cfg.state_file)
        except Exception as exc:                # 权重落盘失败不影响本次产物
            observability.warn(f"在线权重落盘失败：{exc}")
        ctx.backtest = backtest

    out = _out_dir(cfg)
    report_path = out / REPORTS_SUBDIR / f"kl8_lab_{target.period:07d}_{target.date}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    text = report.render_markdown(ctx)
    report_path.write_text(text, encoding="utf-8", newline="\r\n")
    # 保留原项目的按日期目录布局（output/<date>/daily_report.md），便于与旧产物对账
    try:
        report.write_report(ctx, out)
    except (OSError, ValueError) as exc:
        observability.warn(f"按日期目录落盘失败：{exc}")

    payload = build_summary(ctx, backtest=backtest, report_path=report_path)
    payload["target"]["fallback"] = used_fallback
    _dump(out / SUMMARY_FILE, payload)
    if backtest is not None:
        _dump(out / BACKTEST_FILE, _serialize_backtest(backtest))
    return payload


# ── 只读读取（Web 层） ────────────────────────────────────────

def load_summary() -> dict:
    """最新分析快照。未产出时返回 available=False（前端渲染"尚未产出"）。"""
    cfg = get_cfg()
    data = _load_json(Path(cfg.out_dir) / SUMMARY_FILE)
    if not data:
        return {
            "available": False,
            "message": "尚未产出分析快照。请点击「一键深度分析」或运行 run_kl8_lab_daily.py。",
        }
    if "backtest" not in data:
        bt = _load_json(Path(cfg.out_dir) / BACKTEST_FILE)
        if bt:
            data["backtest"] = bt
    return data


def load_backtest() -> dict:
    cfg = get_cfg()
    out = Path(cfg.out_dir)
    bt = _load_json(out / BACKTEST_FILE)
    if bt:
        return bt
    summary = _load_json(out / SUMMARY_FILE)
    return summary.get("backtest") or {
        "available": False,
        "message": "尚未产出样本外回测结果（触发分析时带上回测期数即可生成）。",
    }


def list_reports(limit: int = 60) -> dict:
    """研报档案列表（按修改时间倒序）。"""
    cfg = get_cfg()
    out = _out_dir(cfg)
    rows = []
    for p in sorted(out.glob(f"{REPORTS_SUBDIR}/*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        rows.append({
            "filename": p.name,
            "size_kb": round(st.st_size / 1024.0, 1),
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        })
    legacy = sorted(out.glob("*/daily_report.md"), key=lambda x: x.stat().st_mtime, reverse=True)
    for p in legacy[:20]:
        rows.append({
            "filename": f"{p.parent.name}/daily_report.md",
            "size_kb": round(p.stat().st_size / 1024.0, 1),
            "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
        })
    return {"available": bool(rows), "count": len(rows), "reports": rows[:limit]}


def read_report(filename: str) -> dict:
    """读取研报正文。filename 只允许 outputs/kl8_lab 下的 .md（防目录穿越）。"""
    cfg = get_cfg()
    out = _out_dir(cfg)
    rel = Path(str(filename).replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts:
        raise FileNotFoundError(filename)
    if rel.suffix.lower() != ".md":
        raise FileNotFoundError(filename)
    path = (out / rel).resolve()
    if not str(path).startswith(str(out.resolve())):
        raise FileNotFoundError(filename)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(filename)
    return {
        "filename": str(filename),
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "content": path.read_text(encoding="utf-8", errors="replace"),
    }


def get_points_overview(limit: int = 40) -> dict:
    """点位档案概览 + 数据体检（只读本地档案，不联网）。"""
    cfg = get_cfg()
    ds = source.load_dataset(cfg, allow_fetch=False)
    entries = sorted(ds.points.values(), key=lambda e: (e.period), reverse=True)[:limit]
    missing = ds.missing_points_periods()
    latest = ds.latest_draw()
    return {
        "available": bool(ds.points),
        "health": _serialize_health(ds.health),
        "points_source": ds.health.points_source,
        "draws_source": ds.health.draws_source,
        "latest_draw": {
            "period": latest.period if latest else None,
            "date": latest.date.isoformat() if latest else None,
        },
        "missing_points_periods": [f"{p:07d}" for p in missing[-30:]],
        "missing_points_count": len(missing),
        "entries": [
            {
                "period": f"{e.period:07d}",
                "date": e.date.isoformat() if e.date else None,
                "count": len(e.points),
                "points": [int(n) for n in e.points],
                "dirty": bool(getattr(e, "dirty", False)),
                "has_draw": any(d.period == e.period for d in ds.draws),
            }
            for e in entries
        ],
    }
