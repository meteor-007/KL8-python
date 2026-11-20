# -*- coding: utf-8 -*-
"""审计工具：试验登记（research degrees of freedom）。

为什么需要
----------
同一份 335 期档案上试过 11 个方法、7 维权重、门控、护栏、阈值、十余项修复。
即使每个检验单独看 p<0.05，试得越多，"最好那个"越可能是噪声。
本登记表记录**所有试过的试验**，用于：
  1. 家族大小 N → Bonferroni 阈值 α/N；
  2. N 次零试验下"最大 z"的期望 → 与观测最好的 z 对比；
  3. 预注册前的试验数（DSR/PBO 的输入）。

注意：本模块是审计元数据，**不参与预测路径**，因此刻意不放入
`kl8/*.py`（避免改变已冻结的预注册代码哈希）。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

_MAXZ_CACHE: dict[int, float] = {}


def expected_max_z(n_trials: int, n_sim: int = 50000, seed: int = 42) -> float:
    """N 个独立标准正态试验中最大值的期望（蒙特卡洛，按 N 缓存）。"""
    if n_trials <= 1:
        return 0.0
    if n_trials in _MAXZ_CACHE:
        return _MAXZ_CACHE[n_trials]
    rng = np.random.default_rng(seed)
    total = 0.0
    done = 0
    batch = 10000
    while done < n_sim:
        b = min(batch, n_sim - done)
        total += float(rng.standard_normal((b, n_trials)).max(axis=1).sum())
        done += b
    val = total / n_sim
    _MAXZ_CACHE[n_trials] = val
    return val


class TrialRegistry:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def add(self, trial_id: str, family: str, category: str,
            description: str, status: str = "run",
            result: dict[str, Any] | None = None,
            source: str = "manual",
            created_at: str | None = None,
            meta: dict[str, Any] | None = None,
            skip_existing: bool = True) -> dict[str, Any]:
        records = self.load()
        for rec in records:
            if rec.get("trial_id") == trial_id:
                if skip_existing:
                    return rec
                raise ValueError(f"试验 {trial_id} 已存在")
        rec = {
            "trial_id": trial_id,
            "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
            "family": family,
            "category": category,
            "description": description,
            "status": status,
            "result": result or {},
            "source": source,
            "meta": meta or {},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def families(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for rec in self.load():
            out.setdefault(rec.get("family", "unknown"), []).append(rec)
        return out

    def summary(self, alpha: float = 0.05) -> dict[str, Any]:
        records = self.load()
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for rec in records:
            by_category[rec.get("category", "?")] = by_category.get(rec.get("category", "?"), 0) + 1
            by_status[rec.get("status", "?")] = by_status.get(rec.get("status", "?"), 0) + 1

        fam_out: dict[str, Any] = {}
        for family, recs in self.families().items():
            zs = [float(r["result"]["z"]) for r in recs
                  if isinstance(r.get("result"), dict) and r["result"].get("z") is not None]
            qs = [float(r["result"]["q"]) for r in recs
                  if isinstance(r.get("result"), dict) and r["result"].get("q") is not None]
            n = len(recs)
            emz = expected_max_z(n)
            best_z = max(zs) if zs else None
            fam_out[family] = {
                "N": n,
                "bonferroni_alpha": alpha / n if n else None,
                "expected_max_z": round(emz, 3),
                "observed_best_z": None if best_z is None else round(best_z, 3),
                "best_q": None if not qs else round(min(qs), 4),
                "n_significant": sum(1 for r in recs
                                     if isinstance(r.get("result"), dict)
                                     and r["result"].get("significant")),
                "verdict": (
                    "无结果" if best_z is None else
                    "与零分布最大 z 一致（噪声）" if best_z <= emz else
                    "超过零分布最大 z 期望，需独立复现"
                ),
            }

        all_z = [float(r["result"]["z"]) for r in records
                 if isinstance(r.get("result"), dict) and r["result"].get("z") is not None]
        n_total = len(records)
        emz_total = expected_max_z(n_total)
        return {
            "total": n_total,
            "by_category": by_category,
            "by_status": by_status,
            "families": fam_out,
            "overall": {
                "N": n_total,
                "bonferroni_alpha": alpha / n_total if n_total else None,
                "expected_max_z": round(emz_total, 3),
                "observed_best_z": None if not all_z else round(max(all_z), 3),
                "verdict": (
                    "无结果" if not all_z else
                    "与零分布最大 z 一致（噪声）" if max(all_z) <= emz_total else
                    "超过零分布最大 z 期望，需独立复现"
                ),
            },
        }

    def registration_summary(self, registration_path: Path,
                             alpha: float = 0.05) -> dict[str, Any]:
        reg = json.loads(Path(registration_path).read_text(encoding="utf-8"))
        created = reg.get("created_at", "")
        records = self.load()
        before = [r for r in records if r.get("created_at", "") <= created]
        after = [r for r in records if r.get("created_at", "") > created]
        zs = [float(r["result"]["z"]) for r in before
              if isinstance(r.get("result"), dict) and r["result"].get("z") is not None]
        n = len(before)
        return {
            "registration_id": reg.get("registration_id"),
            "registered_at": created,
            "trials_before_registration": n,
            "trials_after_registration": len(after),
            "after_ids": [r.get("trial_id") for r in after],
            "bonferroni_alpha": alpha / n if n else None,
            "expected_max_z": round(expected_max_z(n), 3),
            "observed_best_z_before": None if not zs else round(max(zs), 3),
            "clean": not after,
            "note": "预注册后新增的试验会污染前瞻性；应为 0",
        }

    # ── 一次性写入已知历史试验 ──────────────────────────────
    def seed(self, report_path: Path | None = None) -> dict[str, int]:
        added = 0
        skipped = 0
        stamp = "2026-11-10T00:00:00"   # 早于登记时间，计入登记前自由度

        def _count(**kw):
            nonlocal added, skipped
            before = len(self.load())
            self.add(created_at=stamp, source="retrospective",
                     skip_existing=True, **kw)
            after = len(self.load())
            if after > before:
                added += 1
            else:
                skipped += 1

        # 1) 11 个方法（从日报方法表解析）
        if report_path and Path(report_path).exists():
            import re
            text = Path(report_path).read_text(encoding="utf-8")
            pat = re.compile(
                r"^\| (cluster|cyclic|heatmap|markov|fibonacci|linalg_svd|"
                r"complex_fft|graph_net|volatility|remainder|entropy) "
                r"\| (\d+) \| ([\d.]+) \| ([\d.]+) \| ([+-]?[\d.]+) \| ([\d.]+) \| (.+?) \|$",
                re.MULTILINE)
            for m in pat.finditer(text):
                name, T, mean, lift, z, q, verdict = m.groups()
                _count(trial_id=f"SEED-METHOD-{name}", family="methods-60",
                       category="method", description=f"方法 {name} 的 60 期外样本检验",
                       status="null" if "未达显著" in verdict else "run",
                       result={"T": int(T), "lift": float(lift), "z": float(z),
                               "q": float(q), "significant": "显著" in verdict and "未达" not in verdict})

        # 2) 融合引擎四大规律
        for tid, desc in (
            ("FREQ", "胆组共识频次与开出率"),
            ("KILL", "双重杀号排除率"),
            ("EXPERT", "四大专家胆组胜率"),
            ("TRIPLE", "三元组 3 码全中率"),
        ):
            _count(trial_id=f"SEED-LAW-{tid}", family="fusion-laws",
                   category="fusion-law", description=desc, status="unverified")

        # 3) 已做的 15 项评估/工程修复
        for i in range(1, 16):
            _count(trial_id=f"SEED-FIX-{i:02d}", family="evaluation-fixes",
                   category="fix", description=f"评估/工程修复 #{i}", status="done")

        # 4) 设计选择（同一档案上迭代过的自由度）
        for tid, desc in (
            ("WEIGHTS", "H1-H7 维度权重 0.18/0.18/0.14/..."),
            ("GATE", "对抗门控阈值"),
            ("GUARD", "多样性护栏上限 3"),
            ("EXP3", "Exp3 warmup=60 / gamma=0.1 / floor=0.01"),
            ("TOPN", "top_n=5"),
        ):
            _count(trial_id=f"SEED-DESIGN-{tid}", family="design-choices",
                   category="design", description=desc, status="adopted")

        # 5) 预注册本身
        _count(trial_id="SEED-PREREG-001", family="prereg",
               category="prereg", description="KL8-2026-11-10-001",
               status="planned")
        return {"added": added, "skipped": skipped}