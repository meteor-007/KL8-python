# -*- coding: utf-8 -*-
"""一次性修正：回填 datasource（数据源1×2）历史前瞻账的退化口径。

背景
----
`backend/modules/datasource/datasource_predictor.py` 的实盘路径曾把「目标期」
（Excel 里已存在但尚未开奖的那一行）当成 T-1 上一期，导致依赖上期开奖的三条规则
（b1_streak / cold_overheat / cold_b2_kill）恒空、rebound 退化成 data1∩点位。
2026-11-10 已在实盘路径修复为「按目标期索引取前一期」，与 Walk-Forward 同口径。

本脚本把该口径修正**回溯**到已经写进前瞻账的历史记录：
  · 用修复后的代码对每一期重算「精选爆发最优 3 码」；
  · 与账本旧值逐期比对，不同则改写 picks；
  · 已开奖的期，按新 picks ∩ 当期开奖重算 hits（保持"已对账"状态，不改变开奖号码）；
  · 全部改动写入 corrections 审计文件，账本先整体备份。

安全约束
--------
· 只动 module == 'datasource' 的记录，其它模块一行不碰。
· 只改 picks / hits，绝不改 period、actual（开奖号码是事实，不可动）。
· 任何一期重算失败 → 跳过并在报告里列明，不猜不补。

用法
----
    python archive/scratch/migration_scripts/backfill_datasource_ledger_20261110.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime

_THIS = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.abspath(os.path.join(_THIS, "..", "..", ".."))
for _p in (_PROJ, os.path.join(_PROJ, "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.modules.datasource.datasource_predictor import predict_datasource_deep  # noqa: E402

LEDGER = os.path.join(_PROJ, "storage", "cache", "paper_trading_modules.jsonl")
CORR_DIR = os.path.join(_PROJ, "storage", "reviews", "corrections")


def main(dry_run: bool = False) -> int:
    with open(LEDGER, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    targets = [r for r in rows if r.get("module") == "datasource"]
    print(f"[账本] 总记录 {len(rows)} 条，datasource {len(targets)} 条")

    changes, skipped = [], []
    for r in targets:
        period = str(r.get("period"))
        old = [int(x) for x in (r.get("picks") or [])]
        try:
            res = predict_datasource_deep(target_period=int(period))
            new = [int(x) for x in (res.get("top3_gold") or [])]
        except Exception as e:                                  # noqa: BLE001
            skipped.append({"period": period, "reason": f"{type(e).__name__}: {e}"})
            continue
        if not new:
            skipped.append({"period": period, "reason": "重算结果为空"})
            continue
        if sorted(new) == sorted(old):
            continue

        actual = r.get("actual")
        new_hits = len(set(new) & set(actual)) if actual else None
        changes.append({
            "period": period,
            "old_picks": old,
            "new_picks": new,
            "old_hits": r.get("hits"),
            "new_hits": new_hits,
            "settled": actual is not None,
        })
        if not dry_run:
            r["picks"] = new
            if actual is not None:
                r["hits"] = new_hits

    print(f"[比对] 需修正 {len(changes)} 条，跳过 {len(skipped)} 条")
    for c in changes[:40]:
        print(f"   {c['period']}: {c['old_picks']} (hits={c['old_hits']}) "
              f"→ {c['new_picks']} (hits={c['new_hits']})")

    if dry_run:
        print("[dry-run] 未写盘")
        return 0

    if not changes:
        print("[完成] 无需修改")
        return 0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = LEDGER + f".bak_{ts}"
    shutil.copy2(LEDGER, backup)

    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, LEDGER)

    os.makedirs(CORR_DIR, exist_ok=True)
    corr_path = os.path.join(CORR_DIR, f"datasource_t1_fix_{ts}.json")
    with open(corr_path, "w", encoding="utf-8") as f:
        json.dump({
            "原因": "datasource 实盘路径曾用目标期当作 T-1，规则退化；2026-11-10 修复后回溯重算",
            "生成时间": datetime.now().isoformat(),
            "账本备份": backup,
            "修正条数": len(changes),
            "跳过": skipped,
            "明细": changes,
        }, f, ensure_ascii=False, indent=2)

    print(f"[完成] 已备份 {backup}")
    print(f"[完成] 修正审计 {corr_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv))