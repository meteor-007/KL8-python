# -*- coding: utf-8 -*-
"""预注册研究框架 (Preregistered Research Harness)

存在的理由
==========
这个项目里已经反复出现同一种自欺：在 100 期数据上网格搜索出一个"提升"，
把它当成结论写进报告，然后在样本外发现它只是噪声。

问题不在算法，在于**流程** —— 先看数据、再挑指标、再定样本量、最后决定信不信。
这条路径上任何结果都能被解释成成功。

本模块把顺序倒过来：
  1. **先** 写死假设、主指标、目标样本量、判死标准；
  2. 冻结成带 SHA256 的预注册记录，改一个字都会被发现；
  3. **然后** 才开始收观察数据；
  4. 到期按预先写好的规则判定，不允许中途改规则。

判定只有四种：collecting / confirmed / rejected / inconclusive。
在达到目标样本量之前，除了预设的无效性检查点，**不做任何结论**。

存储
====
  预注册（不可变）：backend/config/research/<exp_id>.json
  观察账本（只追加）：storage/cache/research/<exp_id>.jsonl
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from math import comb
from typing import Any, Dict, List, Optional, Tuple

from backend.utils.paths import get_cache_dir, get_project_root

_PROJ_DIR = get_project_root()
PREREG_DIR = os.path.join(_PROJ_DIR, "backend", "config", "research")
LEDGER_DIR = os.path.join(get_cache_dir(), "research")

BASELINE_RATE = 0.25          # 快乐8 单码命中的理论基线
DEFAULT_ALPHA = 0.05

# 允许的 verdict
VERDICT_COLLECTING = "collecting"
VERDICT_CONFIRMED = "confirmed"
VERDICT_REJECTED = "rejected"
VERDICT_INCONCLUSIVE = "inconclusive"


class ExperimentFrozenError(RuntimeError):
    """预注册已冻结，不允许修改。要改就开一个新实验（新的 exp_id）。"""


def _paths(exp_id: str) -> Tuple[str, str]:
    safe = "".join(c for c in str(exp_id) if c.isalnum() or c in "-_")
    if not safe or safe != str(exp_id):
        raise ValueError(f"exp_id 只能包含字母数字与 -_：{exp_id!r}")
    return (os.path.join(PREREG_DIR, f"{safe}.json"),
            os.path.join(LEDGER_DIR, f"{safe}.jsonl"))


def _canonical(spec: Dict[str, Any]) -> str:
    """规范化序列化：用于计算哈希，键序与空白必须稳定。"""
    return json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(spec: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(spec).encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────
# 预注册
# ──────────────────────────────────────────────────────────────

REQUIRED_FIELDS = ("exp_id", "title", "hypothesis", "primary_metric",
                   "target_periods", "kill_rule")


def create_experiment(spec: Dict[str, Any]) -> Dict[str, Any]:
    """创建并冻结一份预注册。

    spec 必填字段：
      exp_id          实验标识（字母数字与 -_）
      title           一句话标题
      hypothesis      可证伪的假设，例如「sixteen_hot 的 top3 命中率 > 25%」
      primary_metric  唯一主指标，例如 "top3_hit_rate"
      target_periods  目标样本量（期数），收满才判定
      kill_rule       判死规则，见 evaluate() 支持的形式

    可选：
      baseline        基线命中率，默认 0.25
      alpha           显著性水平，默认 0.05
      checkpoints     预设无效性检查点（期数列表）；只允许「提前判死」，不允许提前判成功
      notes           备注
      start_period    从哪一期开始收数据（不含该期之前的所有数据）

    重复创建同一 exp_id 会抛 ExperimentFrozenError —— 冻结就是冻结。
    """
    missing = [f for f in REQUIRED_FIELDS if not spec.get(f)]
    if missing:
        raise ValueError(f"预注册缺少必填字段: {missing}")

    exp_id = str(spec["exp_id"])
    prereg_path, ledger_path = _paths(exp_id)
    if os.path.exists(prereg_path):
        raise ExperimentFrozenError(
            f"实验 {exp_id} 已冻结，不能修改。要换假设请用新的 exp_id。")

    frozen = {
        "exp_id": exp_id,
        "title": str(spec["title"]),
        "hypothesis": str(spec["hypothesis"]),
        "primary_metric": str(spec["primary_metric"]),
        "target_periods": int(spec["target_periods"]),
        "kill_rule": spec["kill_rule"],
        "baseline": float(spec.get("baseline", BASELINE_RATE)),
        "alpha": float(spec.get("alpha", DEFAULT_ALPHA)),
        "checkpoints": list(spec.get("checkpoints") or []),
        "notes": str(spec.get("notes", "")),
        "start_period": str(spec["start_period"]) if spec.get("start_period") else None,
        # 跟踪的前瞻账模块 id；填了才能自动同步观察数据
        "module_id": str(spec["module_id"]) if spec.get("module_id") else None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "schema_version": 1,
    }
    frozen["sha256"] = _hash({k: v for k, v in frozen.items() if k != "sha256"})

    os.makedirs(PREREG_DIR, exist_ok=True)
    with open(prereg_path, "w", encoding="utf-8") as f:
        json.dump(frozen, f, ensure_ascii=False, indent=2)
    os.makedirs(LEDGER_DIR, exist_ok=True)
    open(ledger_path, "a", encoding="utf-8").close()
    return frozen


def load_experiment(exp_id: str) -> Dict[str, Any]:
    prereg_path, _ = _paths(exp_id)
    with open(prereg_path, encoding="utf-8") as f:
        spec = json.load(f)
    recorded = spec.pop("sha256", None)
    actual = _hash(spec)
    if recorded != actual:
        raise ExperimentFrozenError(
            f"实验 {exp_id} 的预注册文件被改动过（哈希不符）。"
            f"预注册一旦写下就不能改 —— 请用新的 exp_id 重新立项。")
    spec["sha256"] = recorded
    return spec


def verify(exp_id: str) -> bool:
    """校验预注册未被篡改。"""
    try:
        load_experiment(exp_id)
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────
# 观察账本（只追加）
# ──────────────────────────────────────────────────────────────

def append_observation(exp_id: str, period: str, picks: List[int],
                       actual: List[int], note: str = "") -> Dict[str, Any]:
    """记录一期的样本外观察。

    picks 必须是**开奖前**产生的推荐；actual 是实际开奖。
    同一期重复写入会被拒绝（避免事后补录或覆盖）。
    """
    load_experiment(exp_id)                     # 顺带做哈希校验
    _, ledger_path = _paths(exp_id)

    existing = {row["period"] for row in read_observations(exp_id)}
    period = str(period)
    if period in existing:
        raise ValueError(f"实验 {exp_id} 已有第 {period} 期记录，不允许覆盖（只追加）")

    picks = [int(x) for x in picks]
    actual = [int(x) for x in actual]
    hits = len(set(picks) & set(actual))
    row = {
        "period": period,
        "picks": picks,
        "actual": actual,
        "picks_n": len(picks),
        "hits": hits,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "note": note,
    }
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read_observations(exp_id: str) -> List[Dict[str, Any]]:
    _, ledger_path = _paths(exp_id)
    rows = []
    if not os.path.exists(ledger_path):
        return rows
    with open(ledger_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    rows.sort(key=lambda r: r["period"])
    return rows


# ──────────────────────────────────────────────────────────────
# 统计与判定
# ──────────────────────────────────────────────────────────────

def _binom_upper_tail(k: int, n: int, p: float) -> float:
    """P(X >= k)，X ~ Binomial(n, p)。单侧检验用。"""
    if n <= 0:
        return 1.0
    return min(1.0, sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def evaluate(exp_id: str) -> Dict[str, Any]:
    """按预注册规则判定。

    判定顺序（顺序本身就是规则的一部分）：
      1. 收满 target_periods 之前，只有在预设 checkpoint 且满足 kill_rule 时才判 rejected；
         其余一律 collecting —— **绝不允许提前判成功**。
      2. 收满后：p <= alpha 判 confirmed，否则 inconclusive。

    kill_rule 支持的写法（在预注册时写死）：
      {"type": "rate_below_baseline"}   观察到命中率 <= baseline
      {"type": "rate_below", "value": 0.22}
    """
    spec = load_experiment(exp_id)
    rows = read_observations(exp_id)

    n_periods = len(rows)
    votes = sum(r["picks_n"] for r in rows)
    hits = sum(r["hits"] for r in rows)
    rate = (hits / votes) if votes else 0.0
    baseline = spec["baseline"]
    p_value = _binom_upper_tail(hits, votes, baseline) if votes else 1.0
    target = spec["target_periods"]

    out = {
        "exp_id": exp_id,
        "title": spec["title"],
        "primary_metric": spec["primary_metric"],
        "n_periods": n_periods,
        "target_periods": target,
        "progress": round(n_periods / target, 4) if target else 0.0,
        "votes": votes,
        "hits": hits,
        "observed_rate": round(rate, 4),
        "baseline": baseline,
        "lift": round(rate / baseline, 4) if baseline else None,
        "p_value": round(p_value, 4),
        "alpha": spec["alpha"],
    }

    if n_periods >= target:
        out["verdict"] = VERDICT_CONFIRMED if p_value <= spec["alpha"] else VERDICT_INCONCLUSIVE
        out["reason"] = (
            f"已达目标 {target} 期：命中率 {rate * 100:.2f}% vs 基线 {baseline * 100:.1f}%，"
            f"p={p_value:.4f} {'≤' if p_value <= spec['alpha'] else '>'} α={spec['alpha']}")
        return out

    if n_periods in (spec.get("checkpoints") or []) and _kill_triggered(spec["kill_rule"], rate, baseline):
        out["verdict"] = VERDICT_REJECTED
        out["reason"] = (
            f"预设检查点 {n_periods} 期触发判死规则：命中率 {rate * 100:.2f}% "
            f"（基线 {baseline * 100:.1f}%），实验终止")
        return out

    out["verdict"] = VERDICT_COLLECTING
    out["reason"] = f"未达目标（{n_periods}/{target} 期），按规则不做任何结论"
    return out


def _kill_triggered(rule: Any, rate: float, baseline: float) -> bool:
    if not isinstance(rule, dict):
        return False
    kind = rule.get("type")
    if kind == "rate_below_baseline":
        return rate <= baseline
    if kind == "rate_below":
        try:
            return rate < float(rule.get("value"))
        except (TypeError, ValueError):
            return False
    return False


def list_experiments() -> List[Dict[str, Any]]:
    """列出全部实验及其当前状态。"""
    if not os.path.isdir(PREREG_DIR):
        return []
    out = []
    for name in sorted(os.listdir(PREREG_DIR)):
        if not name.endswith(".json"):
            continue
        exp_id = name[:-5]
        try:
            out.append(evaluate(exp_id))
        except Exception as e:                                   # noqa: BLE001
            out.append({"exp_id": exp_id, "verdict": "error", "reason": f"{type(e).__name__}: {e}"})
    return out


# ──────────────────────────────────────────────────────────────
# 从前瞻账同步观察数据
# ──────────────────────────────────────────────────────────────

def sync_from_forward_ledger(exp_id: str, module_id: str,
                             ledger_path: Optional[str] = None) -> Dict[str, Any]:
    """把某模块已结算的前瞻账记录同步进实验账本。

    为什么用前瞻账：那份账里的 picks 是**开奖前**写下的，actual 是开奖后补的，
    天然满足「先预测后开奖」。绝不接受事后补算的号码。

    只同步 period >= start_period 的记录；start_period 之前的样本已被用于调参，
    再拿进来就是拿训练集当测试集。
    """
    spec = load_experiment(exp_id)
    if not ledger_path:
        ledger_path = os.path.join(get_cache_dir(), "paper_trading_modules.jsonl")
    if not os.path.exists(ledger_path):
        return {"exp_id": exp_id, "added": 0, "reason": f"前瞻账不存在: {ledger_path}"}

    have = {r["period"] for r in read_observations(exp_id)}
    start = spec.get("start_period")
    added, skipped_before_start = 0, 0

    with open(ledger_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("module") != module_id:
                continue
            if row.get("actual") is None or not row.get("picks"):
                continue
            period = str(row.get("period", "")).strip()
            if not period:
                continue
            if start and period < str(start):
                skipped_before_start += 1
                continue
            if period in have:
                continue
            append_observation(exp_id, period, row["picks"], row["actual"],
                               note="synced from forward ledger")
            have.add(period)
            added += 1

    return {"exp_id": exp_id, "module_id": module_id, "added": added,
            "skipped_before_start": skipped_before_start,
            "total_periods": len(have)}


def sync_all_from_forward_ledger(ledger_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """把所有填了 module_id 的实验各自同步一次。供流水线每日调用。

    只同步、不判定、不修改预注册 —— 判定只在 evaluate() 里按预注册规则做。
    """
    out = []
    if not os.path.isdir(PREREG_DIR):
        return out
    for name in sorted(os.listdir(PREREG_DIR)):
        if not name.endswith(".json"):
            continue
        exp_id = name[:-5]
        try:
            spec = load_experiment(exp_id)
            mid = spec.get("module_id")
            if not mid:
                continue
            out.append(sync_from_forward_ledger(exp_id, mid, ledger_path))
        except Exception as e:                                   # noqa: BLE001
            out.append({"exp_id": exp_id, "added": 0,
                        "reason": f"{type(e).__name__}: {e}"})
    return out


# ──────────────────────────────────────────────────────────────
# 命令行
# ──────────────────────────────────────────────────────────────

def _main(argv: List[str]) -> int:
    import sys as _sys
    cmd = argv[0] if argv else "list"

    if cmd == "list":
        rows = list_experiments()
        if not rows:
            print("尚无实验。用 create_experiment() 立项。")
            return 0
        for r in rows:
            print(f"[{r['verdict']}] {r['exp_id']}  {r.get('title', '')}")
            if r.get("n_periods") is not None:
                print(f"    {r['n_periods']}/{r['target_periods']} 期"
                      f" | 命中率 {r['observed_rate'] * 100:.2f}%"
                      f" | Lift {r['lift']} | p={r['p_value']}")
            print(f"    {r.get('reason', '')}")
        return 0

    if cmd == "status" and len(argv) >= 2:
        print(json.dumps(evaluate(argv[1]), ensure_ascii=False, indent=2))
        return 0

    if cmd == "sync" and len(argv) >= 3:
        print(json.dumps(sync_from_forward_ledger(argv[1], argv[2]),
                         ensure_ascii=False, indent=2))
        return 0

    print("用法: python -m backend.utils.research_harness "
          "[list | status <exp_id> | sync <exp_id> <module_id>]")
    return 1


if __name__ == "__main__":
    import sys as _sys
    raise SystemExit(_main(_sys.argv[1:]))