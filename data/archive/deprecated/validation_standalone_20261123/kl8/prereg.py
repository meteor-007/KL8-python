# -*- coding: utf-8 -*-
"""预注册与前瞻锁定（对应复盘报告第 6 节“下一步实验设计”）。

设计原则
--------
1. **单一主端点、单次最终分析**：登记时写死主端点与计划期数；到期前不计算
   正式的 p 值（`status` 只显示进度），避免每日窥视导致的假阳性膨胀。
2. **冻结**：登记时冻结代码、配置与截至当期的数据前缀哈希；任一变化即失效。
3. **开奖前锁定**：`lock` 必须在该期开奖入档前执行；已开奖的期拒绝补锁。
4. **只读评估**：评估只读取 append-only 的 `prereg_ledger.jsonl` 与开奖档案，
   不重新选择号码、不改配置。

这不是“提高命中率”的工具；它只保证结论可被证伪、报告不再事后改口径。
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any

from .numerics import EPS, min_detectable_lift
from .stats_tests import TestResult, evaluate

CODE_PATTERNS = (
    "kl8/*.py",
    "main.py",
    "scripts/fusion_engine_template.py",
    "scripts/run_daily.py",
    "scripts/prereg.py",
    "config.yaml",
)
ENDPOINTS = {"top5_lift": 5, "points20_lift": 20}
EXCLUSIONS = [
    "目标期开奖已入档（禁止补锁）",
    "代码/配置/数据前缀哈希与登记不一致",
    "点位缺失或数量不为 20",
]
STOPPING_RULES = [
    "达到计划期数后做唯一一次正式分析",
    "代码、配置或数据前缀变化 → 登记立即失效",
    "计划期数内不因中期结果提前停止或改口径",
]


# ── 基础工具 ──────────────────────────────────────────────────
def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _period_of(line: str) -> int | None:
    parts = dict(kv.split(":", 1) for kv in line.split(",") if ":" in kv)
    try:
        return int(parts["period"])
    except (KeyError, ValueError):
        return None


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8-sig").splitlines()
            if ln.strip()]


def _latest_period(path: Path) -> int:
    periods = [p for p in (_period_of(ln) for ln in _read_lines(path)) if p]
    if not periods:
        raise ValueError(f"{path} 中没有可解析的 period")
    return max(periods)


def _draws_map(path: Path) -> dict[int, set[int]]:
    out: dict[int, set[int]] = {}
    for line in _read_lines(path):
        parts = dict(kv.split(":", 1) for kv in line.split(",") if ":" in kv)
        try:
            period = int(parts["period"])
            nums = parts.get("numbers") or parts.get("points") or ""
            out[period] = {int(x) for x in nums.replace("-", " ").split()}
        except (KeyError, ValueError):
            continue
    return out


def _prefix_hash(path: Path, cutoff: int) -> tuple[str, int]:
    """只哈希 period <= cutoff 的行；新开奖不会改变冻结前缀。"""
    h = hashlib.sha256()
    n = 0
    for line in _read_lines(path):
        p = _period_of(line)
        if p is None or p > cutoff:
            continue
        h.update(line.encode("utf-8"))
        h.update(b"\n")
        n += 1
    return h.hexdigest(), n


def code_hash(root: Path) -> str:
    files: list[Path] = []
    for pattern in CODE_PATTERNS:
        files.extend(sorted(root.glob(pattern)))
    h = hashlib.sha256()
    for path in sorted(set(files), key=lambda p: str(p)):
        if "__pycache__" in path.parts or not path.is_file():
            continue
        h.update(str(path.relative_to(root)).replace("\\", "/").encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes().replace(bytes([13, 10]), bytes([10])))
        h.update(b"\0")
    return h.hexdigest()


def config_hash(cfg) -> str:
    data = cfg.as_dict() if hasattr(cfg, "as_dict") else {}
    return _sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                              default=str).encode("utf-8"))


def _git_head(root: Path) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root),
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _git_is_ancestor(root: Path, commit: str) -> bool:
    try:
        out = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"],
                             cwd=str(root), capture_output=True, text=True, timeout=5)
        return out.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def environment_snapshot(root: Path) -> dict[str, Any]:
    """Python 版本、依赖锁文件与 git 提交，用于冻结“运行环境”。"""
    lock = root / "requirements.lock"
    req = root / "requirements.txt"
    crlf, lf = bytes([13, 10]), bytes([10])
    return {
        "python": platform.python_version(),
        "requirements_lock_sha256": (
            _sha256(lock.read_bytes().replace(crlf, lf)) if lock.exists() else None),
        "requirements_sha256": (
            _sha256(req.read_bytes().replace(crlf, lf)) if req.exists() else None),
        "git_commit": _git_head(root),
    }

def hyper_var(N: int, K: int, n: int) -> float:
    """从 N 个号（其中 K 个开奖号）抽 n 个的命中数方差。"""
    if N <= 1 or n <= 0:
        return 0.0
    p = K / N
    return n * p * (1.0 - p) * ((N - n) / (N - 1))


def _norm_sf(z: float) -> float:
    try:
        from scipy.stats import norm
        return float(norm.sf(z))
    except Exception:
        return 1.0 if z <= 0 else 0.0


# ── 预注册存储 ────────────────────────────────────────────────
class PreregStore:
    def __init__(self, cfg, root: Path | None = None,
                 history_file: Path | None = None,
                 points_file: Path | None = None,
                 code_root: Path | None = None):
        self.cfg = cfg
        self.root = Path(root or Path(__file__).resolve().parents[1])
        self.dir = self.root / "prereg"
        self.state = Path(cfg.state_dir)
        self.active_path = self.dir / "active.json"
        self.ledger = self.state / "prereg_ledger.jsonl"
        self.history = Path(history_file or cfg.shared_history_file)
        self.points = Path(points_file or cfg.shared_points_file)
        self.code_root = Path(code_root or self.root)

    # ── 读写 ──────────────────────────────────────────────────
    def load_active(self) -> dict[str, Any] | None:
        if not self.active_path.exists():
            return None
        return json.loads(self.active_path.read_text(encoding="utf-8"))

    def _save_active(self, reg: dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.active_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(self.active_path)

    def _records(self) -> list[dict[str, Any]]:
        if not self.ledger.exists():
            return []
        out = []
        for line in self.ledger.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def _append(self, rec: dict[str, Any]) -> None:
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ── 登记 ──────────────────────────────────────────────────
    def create(self, registration_id: str, model: str, planned_periods: int,
               start_period: int, hypothesis: str = "",
               alpha: float = 0.05, endpoint: str = "top5_lift",
               min_periods: int = 30) -> dict[str, Any]:
        if endpoint not in ENDPOINTS:
            raise ValueError(f"未知主端点 {endpoint}，可选 {sorted(ENDPOINTS)}")
        if planned_periods < min_periods:
            raise ValueError(f"计划期数至少 {min_periods}")
        latest = _latest_period(self.history)
        if start_period <= latest:
            raise ValueError(
                f"起始期 {start_period} 不晚于最新开奖 {latest}；"
                f"预注册必须从尚未开奖的期开始")
        cutoff = latest
        hist_hash, hist_n = _prefix_hash(self.history, cutoff)
        pts_hash, pts_n = _prefix_hash(self.points, cutoff)
        n_pick = ENDPOINTS[endpoint]
        reg = {
            "registration_id": registration_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "active",
            "hypothesis": hypothesis,
            "model": model,
            "primary_endpoint": endpoint,
            "n_pick": n_pick,
            "alpha": alpha,
            "planned_periods": planned_periods,
            "start_period": start_period,
            "analysis": "final_only",
            "mde_lift_at_plan": round(min_detectable_lift(planned_periods, n_draw=n_pick), 4),
            "baselines": ["same_pool_random", "all80_random"],
            "exclusions": EXCLUSIONS,
            "stopping_rules": STOPPING_RULES,
            "frozen": {
                "code_sha256": code_hash(self.code_root),
                "config_sha256": config_hash(self.cfg),
                "config": self.cfg.as_dict() if hasattr(self.cfg, "as_dict") else {},
                "data_cutoff_period": cutoff,
                "history_prefix_sha256": hist_hash,
                "history_prefix_lines": hist_n,
                "points_prefix_sha256": pts_hash,
                "points_prefix_lines": pts_n,
                "environment": environment_snapshot(self.root),
            },
        }
        self._save_active(reg)
        return reg

    # ── 冻结校验 ──────────────────────────────────────────────
    def check_freeze(self, reg: dict[str, Any]) -> list[str]:
        frozen = reg.get("frozen", {})
        problems: list[str] = []
        if code_hash(self.code_root) != frozen.get("code_sha256"):
            problems.append("代码哈希与登记不一致")
        if config_hash(self.cfg) != frozen.get("config_sha256"):
            problems.append("配置哈希与登记不一致")
        cutoff = int(frozen.get("data_cutoff_period", 0))
        hist_hash, hist_n = _prefix_hash(self.history, cutoff)
        pts_hash, pts_n = _prefix_hash(self.points, cutoff)
        if hist_hash != frozen.get("history_prefix_sha256") or \
                hist_n != frozen.get("history_prefix_lines"):
            problems.append("开奖档案的冻结前缀被改写")
        if pts_hash != frozen.get("points_prefix_sha256") or \
                pts_n != frozen.get("points_prefix_lines"):
            problems.append("点位档案的冻结前缀被改写")

        env_now = environment_snapshot(self.root)
        env_frozen = frozen.get("environment", {})
        for key in ("python", "requirements_lock_sha256", "requirements_sha256"):
            if env_now.get(key) != env_frozen.get(key):
                problems.append(f"环境/版本变化：{key}")
        frozen_commit = env_frozen.get("git_commit")
        now_commit = env_now.get("git_commit")
        if frozen_commit:
            if not now_commit or not _git_is_ancestor(self.root, frozen_commit):
                problems.append("git HEAD 不包含登记提交")
        elif frozen_commit != now_commit:
            problems.append("git 状态与登记不一致")
        return problems

    def invalidate(self, reason: str) -> dict[str, Any]:
        reg = self.load_active()
        if reg is None:
            raise ValueError("没有活动登记")
        reg["status"] = "invalidated"
        reg["invalidated_at"] = datetime.now().isoformat(timespec="seconds")
        reg["invalidated_reason"] = reason
        self._save_active(reg)
        return reg

    # ── 锁定预测 ──────────────────────────────────────────────
    def lock(self, model: str, prediction_path: Path | None = None) -> dict[str, Any]:
        reg = self.load_active()
        if reg is None:
            raise ValueError("没有活动登记；先运行 prereg create")
        if reg.get("status") != "active":
            raise ValueError(f"登记状态为 {reg.get('status')}，不可锁定")
        problems = self.check_freeze(reg)
        if problems:
            self.invalidate("；".join(problems))
            raise ValueError("冻结校验失败，登记已失效：" + "；".join(problems))

        pred_path = Path(prediction_path or
                         (self.state / f"last_prediction_{model}.json"))
        if not pred_path.exists():
            raise FileNotFoundError(f"找不到预测快照 {pred_path}")
        pred = json.loads(pred_path.read_text(encoding="utf-8"))
        period = int(pred["period"])
        if period < int(reg["start_period"]):
            raise ValueError(f"期号 {period} 早于登记起始期 {reg['start_period']}")

        draws = _draws_map(self.history)
        if period in draws:
            raise ValueError(f"期号 {period} 已开奖入档，禁止补锁（防事后选择）")

        core = [int(x) for x in pred.get("core", [])]
        n_pick = int(reg["n_pick"])
        if len(core) != n_pick or len(set(core)) != n_pick or \
                not all(1 <= x <= 80 for x in core):
            raise ValueError(f"预测快照的 core 不是 {n_pick} 个合法且不重复的号码")
        pool = [int(x) for x in pred.get("pool", [])]
        expanded = [int(x) for x in pred.get("expanded", [])]

        for rec in self._records():
            if rec.get("registration_id") != reg["registration_id"]:
                continue
            if rec.get("model") == model and int(rec.get("period", 0)) == period:
                if [int(x) for x in rec.get("core", [])] == core:
                    return {"status": "already_locked", "record": rec}
                raise ValueError(f"{model} 的 {period} 期已有不同锁定记录")

        rec = {
            "registration_id": reg["registration_id"],
            "model": model,
            "period": period,
            "date": pred.get("date") or str(_date.today()),
            "locked_at": datetime.now().isoformat(timespec="seconds"),
            "core": core,
            "defensive": [int(x) for x in pred.get("defensive", [])],
            "pool": pool,
            "expanded": expanded,
            "code_sha256": reg["frozen"]["code_sha256"],
            "config_sha256": reg["frozen"]["config_sha256"],
            "data_cutoff_period": reg["frozen"]["data_cutoff_period"],
        }
        self._append(rec)
        return {"status": "locked", "record": rec}

    # ── 状态（不报告正式 p 值）─────────────────────────────────
    def status(self) -> dict[str, Any]:
        reg = self.load_active()
        if reg is None:
            return {"status": "none"}
        records = [r for r in self._records()
                   if r.get("registration_id") == reg["registration_id"]
                   and r.get("model") == reg["model"]]
        draws = _draws_map(self.history)
        drawn = [r for r in records if int(r["period"]) in draws]
        problems = self.check_freeze(reg)
        return {
            "registration_id": reg["registration_id"],
            "status": reg["status"],
            "model": reg["model"],
            "primary_endpoint": reg["primary_endpoint"],
            "planned_periods": reg["planned_periods"],
            "start_period": reg["start_period"],
            "locked": len(records),
            "drawn": len(drawn),
            "remaining": max(0, int(reg["planned_periods"]) - len(drawn)),
            "mde_lift_at_plan": reg["mde_lift_at_plan"],
            "freeze_ok": not problems,
            "freeze_problems": problems,
            "note": "到期前不计算正式 p 值（final_only）",
        }

    # ── 唯一一次正式分析 ──────────────────────────────────────
    def evaluate(self, exploratory: bool = False) -> dict[str, Any]:
        reg = self.load_active()
        if reg is None:
            raise ValueError("没有活动登记")
        records = [r for r in self._records()
                   if r.get("registration_id") == reg["registration_id"]
                   and r.get("model") == reg["model"]]
        draws = _draws_map(self.history)
        rows = []
        for rec in sorted(records, key=lambda r: int(r["period"])):
            draw = draws.get(int(rec["period"]))
            if draw is None:
                continue
            core = set(int(x) for x in rec.get("core", []))
            pool = set(int(x) for x in rec.get("pool", []))
            hits = len(core & draw)
            pool_hits = len(pool & draw) if pool else 0
            exp_pool = (len(core) * pool_hits / len(pool)) if pool else 0.0
            var_pool = hyper_var(len(pool), pool_hits, len(core)) if pool else 0.0
            rows.append({"period": int(rec["period"]), "hits": hits,
                         "pool_size": len(pool), "pool_hits": pool_hits,
                         "exp_pool": exp_pool, "var_pool": var_pool})

        T = len(rows)
        planned = int(reg["planned_periods"])
        ready = T >= planned
        if not ready and not exploratory:
            return {"ready": False, "T": T, "planned": planned,
                    "remaining": planned - T,
                    "note": "尚未达到计划期数；按预注册不做正式分析"}

        hits = [r["hits"] for r in rows]
        n_pick = int(reg["n_pick"])
        system = evaluate(hits, label=f"{reg['model']} 主端点",
                          alpha=float(reg["alpha"]), n_pick=n_pick,
                          expected=n_pick * 0.25)
        sum_hits = sum(hits)
        sum_exp = sum(r["exp_pool"] for r in rows)
        sum_var = sum(r["var_pool"] for r in rows)
        pool_z = (sum_hits - sum_exp) / math.sqrt(sum_var) if sum_var > EPS else 0.0
        pool_p = _norm_sf(pool_z)
        pool_test = TestResult(
            label="同池随机基线", T=T, mean_hits=sum_hits / T if T else 0.0,
            expected=sum_exp / T if T else 0.0,
            lift=(sum_hits / sum_exp) if sum_exp > EPS else 0.0,
            se=math.sqrt(sum_var) / T if T else 0.0,
            z=pool_z, p_value=pool_p, q_value=pool_p,
            significant=pool_p < float(reg["alpha"]),
            verdict="统计显著优于随机" if pool_p < float(reg["alpha"]) and pool_z > 0
            else "未达显著",
            mde_lift=min_detectable_lift(T, n_draw=n_pick) if T else float("inf"),
            n_pick=n_pick,
        )
        return {
            "ready": ready,
            "exploratory": bool(exploratory and not ready),
            "registration_id": reg["registration_id"],
            "T": T,
            "planned": planned,
            "system": system,
            "same_pool": pool_test,
            "all80_expected": n_pick * 0.25,
            "mde_lift": min_detectable_lift(T, n_draw=n_pick),
            "rows": rows,
        }

    # ── 渲染 ──────────────────────────────────────────────────
    def render_status(self) -> str:
        s = self.status()
        if s.get("status") == "none":
            return "未找到预注册登记。"
        lines = [
            f"登记号      : {s['registration_id']}",
            f"状态        : {s['status']}",
            f"模型/端点   : {s['model']} / {s['primary_endpoint']}",
            f"计划期数    : {s['planned_periods']}（起始 {s['start_period']}）",
            f"已锁定/已开奖/剩余: {s['locked']} / {s['drawn']} / {s['remaining']}",
            f"计划 MDE    : +{s['mde_lift_at_plan'] * 100:.1f}%",
            f"冻结校验    : {'通过' if s['freeze_ok'] else '失败：' + '；'.join(s['freeze_problems'])}",
            f"说明        : {s['note']}",
        ]
        return "\n".join(lines)

    def render_evaluation(self, result: dict[str, Any]) -> str:
        if not result.get("ready") and not result.get("exploratory"):
            return (f"尚未达到计划期数：T={result['T']}/{result['planned']}，"
                    f"剩余 {result['remaining']} 期。按预注册不做正式分析。")
        sys = result["system"]
        pool = result["same_pool"]
        tag = "探索性（非预注册）" if result.get("exploratory") else "正式"
        lines = [
            f"# 预注册{tag}分析 · {result['registration_id']}",
            "",
            f"- T = {result['T']}（计划 {result['planned']}）",
            f"- 主端点：{sys.label}；均值 {sys.mean_hits:.4f}，期望 {sys.expected:.4f}，"
            f"lift {sys.lift:.4f}，z={sys.z:+.3f}，p={sys.p_value:.4f}",
            f"- 95% CI 约 [{sys.mean_hits - 1.96 * sys.se:.3f}, "
            f"{sys.mean_hits + 1.96 * sys.se:.3f}] 命中/期",
            f"- 同期 MDE：+{result['mde_lift'] * 100:.1f}%",
            f"- 同池随机基线：lift {pool.lift:.4f}，z={pool.z:+.3f}，p={pool.p_value:.4f}",
            f"- 全 80 随机基线期望：{result['all80_expected']:.2f} 命中/期",
            "",
            "| 期号 | 命中 | 池内开奖号 | 池大小 | 同池期望 |",
            "|---|---|---|---|---|",
        ]
        for r in result["rows"]:
            lines.append(f"| {r['period']} | {r['hits']} | {r['pool_hits']} | "
                         f"{r['pool_size']} | {r['exp_pool']:.2f} |")
        lines.append("")
        lines.append("> 本分析按预注册口径输出；不构成投注建议。")
        return "\n".join(lines)