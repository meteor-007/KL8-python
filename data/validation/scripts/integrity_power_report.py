# -*- coding: utf-8 -*-
"""数据完整性 + 条件功效报告（只读诊断，不改变预注册/模型）。

输出：
    docs/reports/integrity_power_<date>.md
    docs/reports/integrity_power_<date>.json

用法：
    python scripts/integrity_power_report.py
    python scripts/integrity_power_report.py --json-out ... --md-out ...
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from collections import Counter
import sys
from datetime import date
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kl8.numerics import hypergeom_var
from scipy.stats import chi2
from tools.data_sync import load_history, load_points, scan_invalid

DATA_DIR = Path(os.environ.get("KL8_DATA_DIR", str(ROOT.parent / "Python-Project" / "data" / "storage" / "raw")))
A_HISTORY = DATA_DIR / "kl8_history_final.txt"
A_POINTS = ROOT / "data" / "cache" / "points_archive.txt"
ACTIVE = ROOT / "prereg" / "active.json"
LEDGER = ROOT / "data" / "state" / "prereg_ledger.jsonl"
DEFAULT_OUT = ROOT / "docs" / "reports"

Z_ALPHA = 1.6448536269514722       # one-sided 0.05
Z_POWER = 0.8416212335729143       # 80% power
HIT_RATE = 0.25
N_PICK = 5
VAR5 = hypergeom_var(N_PICK)


def period_continuity(periods: set[int], within_range: bool = False) -> dict:
    """按年份检查期号连续性；within_range=True 时只从当年最小期号起算。"""
    out: dict[str, dict] = {}
    for year in sorted({p // 1000 for p in periods}):
        vals = sorted(p for p in periods if p // 1000 == year)
        lower = min(vals) if within_range else year * 1000 + 1
        expected = set(range(lower, max(vals) + 1))
        missing = sorted(expected - set(vals))
        out[str(year)] = {
            "count": len(vals),
            "first": min(vals),
            "last": max(vals),
            "missing_count": len(missing),
            "missing": missing[:20],
        }
    return out


def missing_periods(reference: set[int], actual: set[int]) -> list[int]:
    """actual 覆盖范围内、reference 中存在但 actual 缺失的期号。"""
    if not actual:
        return []
    lo, hi = min(actual), max(actual)
    return sorted(p for p in reference if lo <= p <= hi and p not in actual)


def data_integrity() -> dict:
    hist = load_history(A_HISTORY)
    pts = load_points(A_POINTS)
    hist_invalid = scan_invalid(A_HISTORY, "history")
    pts_invalid = scan_invalid(A_POINTS, "points")
    common = sorted(set(hist) & set(pts))
    points_missing = missing_periods(set(hist), set(pts))
    date_mismatch = [
        {"period": p, "history_date": hist[p][0], "points_date": pts[p][0]}
        for p in common if hist[p][0] != pts[p][0]
    ]
    ordered = sorted(hist)
    date_backtracks = [
        {"period": ordered[i], "previous": ordered[i - 1]}
        for i in range(1, len(ordered))
        if hist[ordered[i]][0] < hist[ordered[i - 1]][0]
    ]
    return {
        "history": {
            "path": str(A_HISTORY),
            "count": len(hist),
            "oldest": min(hist) if hist else None,
            "latest": max(hist) if hist else None,
            "invalid": len(hist_invalid),
            "invalid_samples": hist_invalid[:5],
            "continuity": period_continuity(set(hist)),
            "date_backtracks": date_backtracks[:20],
        },
        "points": {
            "path": str(A_POINTS),
            "count": len(pts),
            "oldest": min(pts) if pts else None,
            "latest": max(pts) if pts else None,
            "invalid": len(pts_invalid),
            "invalid_samples": pts_invalid[:5],
            "continuity": period_continuity(set(pts), within_range=True),
            "missing_vs_history": points_missing,
            "missing_vs_history_count": len(points_missing),
        },
        "overlap": {
            "common_periods": len(common),
            "date_mismatch_count": len(date_mismatch),
            "date_mismatch": date_mismatch,
        },
    }


def load_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def ledger_integrity(hist: dict[int, tuple[str, frozenset[int]]]) -> dict:
    active = json.loads(ACTIVE.read_text(encoding="utf-8")) if ACTIVE.exists() else {}
    rows = load_ledger()
    rid = active.get("registration_id")
    model = active.get("model")
    primary = [r for r in rows if r.get("registration_id") == rid and r.get("model") == model]
    duplicate_keys: list[str] = []
    seen: set[tuple] = set()
    for r in rows:
        key = (r.get("registration_id"), r.get("model"), int(r.get("period", 0)))
        if key in seen:
            duplicate_keys.append(f"{key[0]}/{key[1]}/{key[2]}")
        seen.add(key)

    checks = []
    hits: list[int] = []
    for r in sorted(primary, key=lambda x: int(x.get("period", 0))):
        period = int(r["period"])
        core = [int(x) for x in r.get("core", [])]
        draw = hist.get(period)
        row = {
            "period": period,
            "date": r.get("date"),
            "locked_at": r.get("locked_at"),
            "core_count": len(core),
            "core_unique": len(set(core)),
            "core_valid_range": all(1 <= x <= 80 for x in core),
            "draw_present": draw is not None,
            "hits": None,
        }
        if draw is not None:
            row["hits"] = len(set(core) & draw[1])
            hits.append(row["hits"])
            row["draw_date"] = draw[0]
        checks.append(row)

    same_day = [{"period": c["period"], "lock": c["locked_at"], "draw_date": c.get("draw_date")}
                for c in checks if c.get("draw_date") and str(c["locked_at"]).startswith(c["draw_date"])]
    after_day = [c for c in checks if c.get("draw_date") and
                 str(c["locked_at"])[:10] > c["draw_date"]]

    n_obs = len(hits)
    hits0 = sum(hits)
    expected0 = n_obs * N_PICK * HIT_RATE
    z0 = (hits0 - expected0) / math.sqrt(n_obs * VAR5) if n_obs else 0.0
    return {
        "registration_id": rid,
        "model": model,
        "planned_periods": active.get("planned_periods"),
        "start_period": active.get("start_period"),
        "primary_endpoint": active.get("primary_endpoint"),
        "ledger_rows": len(rows),
        "primary_rows": len(primary),
        "duplicate_keys": duplicate_keys,
        "checks": checks,
        "observed_hits": hits0,
        "observed_n": n_obs,
        "observed_expected": expected0,
        "observed_lift": (hits0 / expected0) if expected0 else None,
        "observed_z_descriptive": z0,
        "same_day_lock": same_day,
        "locked_after_draw_date": after_day,
    }


def power_table(hits_obs: int, n_obs: int, planned: int,
                lifts: list[float] | None = None) -> dict:
    lifts = lifts or [0.0, 0.025, 0.05, 0.075, 0.1083, 0.15, 0.20]
    sd = math.sqrt(VAR5)
    mde = (Z_ALPHA + Z_POWER) * sd / math.sqrt(planned) / (N_PICK * HIT_RATE)
    rows = []
    for lift in lifts:
        mu = N_PICK * HIT_RATE * (1.0 + lift)
        mean_z = (hits_obs + (planned - n_obs) * mu - planned * N_PICK * HIT_RATE) / math.sqrt(planned * VAR5)
        unconditional_z = (planned * mu - planned * N_PICK * HIT_RATE) / math.sqrt(planned * VAR5)
        required_n = (((Z_ALPHA + Z_POWER) * sd) / (N_PICK * HIT_RATE * lift)) ** 2 if lift > 0 else None
        rows.append({
            "lift": lift,
            "power_conditional": NormalDist().cdf(
                (mean_z - Z_ALPHA) / math.sqrt((planned - n_obs) / planned)),
            "power_unconditional": NormalDist().cdf(unconditional_z - Z_ALPHA),
            "required_periods_80pct": required_n,
            "mean_final_z": mean_z,
        })
    return {
        "var5": VAR5,
        "mde_lift_at_planned": mde,
        "planned": planned,
        "observed_n": n_obs,
        "observed_hits": hits_obs,
        "rows": rows,
    }


def bias_power(periods: int, rel_bias: float, balls: int = 80) -> dict:
    p_true = HIT_RATE * (1.0 + rel_bias)
    se = math.sqrt(HIT_RATE * (1 - HIT_RATE) / periods)
    z = abs(p_true - HIT_RATE) / se
    zcrit = NormalDist().inv_cdf(1 - 0.025 / balls)
    power = NormalDist().cdf(z - zcrit) + NormalDist().cdf(-z - zcrit)
    return {"periods": periods, "rel_bias": rel_bias, "z": z,
            "zcrit_bonferroni": zcrit, "power": power}


def frequency_audit(hist: dict[int, tuple[str, frozenset[int]]]) -> dict:
    """80 码频率审计（仅频率，不含顺序/机器归因）。"""
    counts = Counter()
    for _date, nums in hist.values():
        counts.update(nums)
    n = len(hist)
    exp = n * 20.0 / 80.0
    stat = sum((counts[i] - exp) ** 2 / exp for i in range(1, 81)) if exp else 0.0
    p = float(chi2.sf(stat, 79)) if exp else 1.0
    se = math.sqrt(n * HIT_RATE * (1 - HIT_RATE)) if n else 1.0
    z = {i: (counts[i] - exp) / se for i in range(1, 81)}
    zmax = max(z.values(), key=abs) if z else 0.0
    zcrit = NormalDist().inv_cdf(1 - 0.025 / 80)
    top = sorted(((i, counts[i], z[i]) for i in range(1, 81)), key=lambda x: -abs(x[2]))[:8]
    return {"periods": n, "expected": exp, "chi2": stat, "df": 79, "p_value": p,
            "max_abs_z": abs(zmax), "bonferroni_z": zcrit,
            "top": [{"ball": i, "count": c, "z": zz} for i, c, zz in top]}


def physical_bias_feasibility(periods: int) -> dict:
    rows = [bias_power(periods, b) for b in (0.025, 0.05, 0.10, 0.20)]
    return {
        "periods": periods,
        "rows": rows,
        "order_available": False,
        "machine_metadata_available": False,
        "notes": [
            "A 的历史 loader 在 kl8/data_io.py 中返回 sorted(nums)，每期号码顺序被有意丢弃。",
            "原始历史行虽保留一个顺序，但无法确认它是物理开奖顺序还是下载/记录顺序。",
            "历史与台账没有机器编号、球组编号、换球/维护时间；频率偏差无法归因到球重或机器。",
            "仅做 80 码频率审计时，小偏差（2.5%–5%）在 2123 期上功效很低；20% 级偏差才较易发现。",
        ],
    }


def freeze_status() -> dict:
    cmd = [sys.executable, str(ROOT / "scripts" / "prereg.py"), "status"]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    text = (r.stdout or "") + (r.stderr or "")
    return {"exit": r.returncode, "text": text.strip()[-1200:],
            "freeze_ok": "冻结校验    : 通过" in text or "冻结校验   : 通过" in text}


def render(integrity: dict, ledger: dict, power: dict, bias: dict, freq: dict, freeze: dict) -> str:
    h = integrity["history"]
    p = integrity["points"]
    o = integrity["overlap"]
    rows = power["rows"]
    p5 = next(r['power_conditional'] for r in rows if abs(r['lift'] - 0.05) < 1e-9) * 100
    p108 = next(r['power_conditional'] for r in rows if abs(r['lift'] - 0.1083) < 1e-4) * 100
    same_date = o["common_periods"] - o["date_mismatch_count"]
    if o["date_mismatch_count"]:
        date_note = (f"（{same_date}/{o['common_periods']} 期日期一致；"
                     "存在日期差异，需确认提前录入/笔误）")
    else:
        date_note = "（日期全部一致）"
    lift_ratio = ledger.get("observed_lift")
    lift_txt = (f"{lift_ratio:.3f}（= +{(lift_ratio - 1) * 100:.1f}%）"
                if lift_ratio is not None else "—")
    if not h["count"] or not p["count"]:
        status = "FAIL"
    elif h["invalid"] or p["invalid"] or o["date_mismatch_count"] or p["missing_vs_history"]:
        status = "WARN"
    else:
        status = "PASS"
    lines = [
        "# 数据完整性 + 条件功效报告",
        "",
        f"- 生成日期：{date.today().isoformat()}",
        f"- 预注册：`{ledger.get('registration_id')}` / `{ledger.get('primary_endpoint')}`",
        f"- 计划期数：{power['planned']}，已观察：{ledger['observed_n']}，剩余：{power['planned'] - ledger['observed_n']}",
        "",
        "## 结论摘要",
        "",
        f"- 历史：{h['count']} 期（{h['oldest']}–{h['latest']}），非法行 {h['invalid']}；按年连续性见下表。",
        f"- 点位：{p['count']} 期（{p['oldest']}–{p['latest']}），非法行 {p['invalid']}；"
        f"与历史重叠 {o['common_periods']} 期；日期差异 {o['date_mismatch_count']} 期{date_note}；"
        f"范围内缺 {p['missing_vs_history_count']} 期：{p['missing_vs_history'] or '无'}。",
        f"- 台账：活动登记 {ledger['primary_rows']} 条；已结算命中 {ledger['observed_hits']}/{ledger['observed_n'] * 5}"
        f"（描述性 lift ratio={lift_txt}，"
        f"z={ledger['observed_z_descriptive']:+.3f}；**不是正式分析**）。",
        f"- 条件功效：计划 {power['planned']} 期、MDE lift={power['mde_lift_at_planned']*100:.1f}%；"
        f"在 5% lift 下条件功效约 {p5:.1f}%，在 10.83% lift 下约 {p108:.1f}%。",
        f"- 预注册冻结：{'通过' if freeze['freeze_ok'] else '未通过/需复核'}（prereg.py status exit={freeze['exit']}）。",
        f"- 80 码频率审计：χ²={freq['chi2']:.2f}，df=79，p={freq['p_value']:.3f}；"
        f"最大 |z|={freq['max_abs_z']:.2f}（80 球 Bonferroni 阈值 {freq['bonferroni_z']:.2f}），"
        "未发现可报告频率偏差（探索性、非预注册；正式端点仍 final_only；不代表无物理偏差）。",
        "",
        "## 数据完整性",
        "",
        "| 对象 | 期数 | 最早 | 最新 | 非法行 | 日期回退 |",
        "|---|---:|---:|---:|---:|---:|",
        f"| history | {h['count']} | {h['oldest']} | {h['latest']} | {h['invalid']} | {len(h['date_backtracks'])} |",
        f"| points | {p['count']} | {p['oldest']} | {p['latest']} | {p['invalid']} | — |",
        "",
        "### 年度连续性",
        "",
        "| 年份 | 期数 | 首期 | 末期 | 缺失期数 |",
        "|---:|---:|---:|---:|---:|",
    ]
    for year, v in h["continuity"].items():
        lines.append(f"| {year} | {v['count']} | {v['first']} | {v['last']} | {v['missing_count']} |")
    if o["date_mismatch"]:
        lines += ["", "### 日期差异（点位录入日 vs 开奖日，需确认口径）", ""]
        for m in o["date_mismatch"]:
            lines.append(f"- `{m['period']}`：history={m['history_date']}，points={m['points_date']}（早 3 天，需确认）")
    if p["missing_vs_history"]:
        lines += ["", "### 点位缺口（history 范围内有、points 缺）", ""]
        for period in p["missing_vs_history"]:
            lines.append(f"- `{period}`：共享 `daily_points.txt` 有该期，但 `data/cache/points_archive.txt` 缺失；"
                         "该期在冻结前缀内，直接补入会改变 points_prefix_sha256 并使当前预注册失效。")
    if status == "FAIL":
        lines += ["", "> 数据完整性状态：**FAIL**（history/points 为空或不可读）。"]
    elif status == "WARN":
        lines += ["", "> 数据完整性状态：**WARN**（存在点位缺口/日期差异；未阻塞读取，但改动冻结数据前需重新登记）。"]
    else:
        lines += ["", "> 数据完整性状态：**PASS**。"]

    lines += ["", "## 预注册台账", "", "| 期号 | 锁定时间 | 核心数 | 命中 | 开奖日期 |",
              "|---:|---|---:|---:|---|"]
    for c in ledger["checks"]:
        lines.append(f"| {c['period']} | {c['locked_at']} | {c['core_count']} | {c['hits']} | {c.get('draw_date','—')} |")
    if ledger["same_day_lock"]:
        lines += ["", "同日锁定（仅能证明日期，不足以证明开奖前）：" +
                  "、".join(str(x["period"]) for x in ledger["same_day_lock"])]
    if ledger["locked_after_draw_date"]:
        lines += ["", "> **FAIL**：存在锁定日期晚于开奖日期的记录。"]
    lines += ["", "## 条件功效（normal approximation，单侧 α=0.05，80% power）", "",
              "| 假设相对 lift | 条件功效 | 无条件功效 | 80% 功效所需期数（无条件/固定设计） |", "|---:|---:|---:|---:|"]
    for r in rows:
        req = "∞" if r["required_periods_80pct"] is None else f"{r['required_periods_80pct']:.0f}"
        lines.append(f"| {r['lift']*100:.2f}% | {r['power_conditional']*100:.1f}% | "
                     f"{r['power_unconditional']*100:.1f}% | {req} |")
    lines += ["", f"- 300 期 MDE：**+{power['mde_lift_at_planned']*100:.1f}%**（相对 lift）；"
              "若真实 lift 只有 2.5%–5%，300 期功效不足，需延长/重新设计。",
              "- 条件功效使用观察到的前 2 期命中 3 次，并按剩余期数方差缩放；仅作规划参考，不替代 final-only 正式分析。"]
    lines += ["", "## 开奖机器 / 球重 / 顺序偏差：可行性", "",
              "### 80 码频率审计（历史全量）", "",
              f"- χ²={freq['chi2']:.2f}，df=79，p={freq['p_value']:.3f}；"
              f"最大 |z|={freq['max_abs_z']:.2f}，80 球 Bonferroni 阈值 {freq['bonferroni_z']:.2f}。",
              "", "| 号码 | 次数 | z |", "|---:|---:|---:|"]
    for item in freq["top"]:
        lines.append(f"| {item['ball']:02d} | {item['count']} | {item['z']:+.2f} |")
    lines += ["", "### 检测功效（仅频率）", "",
              f"对 {bias['periods']} 期历史、80 个球，做双侧 Bonferroni（α=0.05, m=80）校正后的近似功效：", "",
              "| 相对偏差 | z | 校正阈值 | 功效 |", "|---:|---:|---:|---:|"]
    for r in bias["rows"]:
        lines.append(f"| {r['rel_bias']*100:.1f}% | {r['z']:.2f} | {r['zcrit_bonferroni']:.2f} | {r['power']*100:.1f}% |")
    lines += ["", "限制："]
    for n in bias["notes"]:
        lines.append(f"- {n}")
    lines += ["", "若要做物理偏差审计，先补：①官方逐期开奖顺序；②机器/球组编号与换球维护记录；"
              "③预注册假设与多重校正；④独立样本复现。否则只能做低功效的频率筛查，不能把偏差归因到球重或机器。",
              "", "## 建议", "",
              "1. 当前数据完整性 PASS；若未来再发现点位缺口/日期差异，冻结前缀内不要直接补数据，必要时先作废并重新登记。",
              "2. 当前 2/300 期，不因描述性 lift 做模型调整；按 final-only 继续锁定。",
              "3. 若关心 5% 级效应，300 期不够；先设计更长期限或配对方差缩减，再新开预注册。",
              "4. 物理偏差审计作为独立研究线，先拿顺序/机器元数据；不要直接接入生产 Top5。",
              ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    today = date.today().isoformat()
    ap.add_argument("--json-out", default=str(DEFAULT_OUT / f"integrity_power_{today}.json"))
    ap.add_argument("--md-out", default=str(DEFAULT_OUT / f"integrity_power_{today}.md"))
    args = ap.parse_args(argv)
    integrity = data_integrity()
    hist = load_history(A_HISTORY)
    ledger = ledger_integrity(hist)
    power = power_table(ledger["observed_hits"], ledger["observed_n"],
                        int(ledger.get("planned_periods") or 300))
    bias = physical_bias_feasibility(len(hist))
    freq = frequency_audit(hist)
    freeze = freeze_status()
    payload = {"integrity": integrity, "ledger": ledger, "power": power,
               "physical_bias": bias, "frequency_audit": freq, "freeze": freeze}
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md = render(integrity, ledger, power, bias, freq, freeze)
    Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.md_out).write_text(md, encoding="utf-8")
    print(f"报告：{args.md_out}")
    print(f"JSON：{args.json_out}")
    if not integrity['history']['count'] or not integrity['points']['count']:
        status = "FAIL"
    elif integrity['history']['invalid'] or integrity['points']['invalid'] or integrity['overlap']['date_mismatch_count'] or integrity['points']['missing_vs_history']:
        status = "WARN"
    else:
        status = "PASS"
    print(f"数据完整性：{status}")
    print(f"频率审计：chi2={freq['chi2']:.2f} p={freq['p_value']:.3f} max|z|={freq['max_abs_z']:.2f}")
    print(f"条件功效（5% lift）：{next(r['power_conditional'] for r in power['rows'] if abs(r['lift']-0.05)<1e-9)*100:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())