# -*- coding: utf-8 -*-
"""
逐模块逐期复盘报告器 (Per-Module Per-Period Review)
================================================================================
大白话: 开奖后, 把"每个模块这一期到底推荐了哪几个号、中了几个"一条条列清楚。

数据来源: 追加式前瞻账 `storage/cache/paper_trading_modules.jsonl`
  (由 `harvester.harvest()` 在开奖前写入, 由 `module_gate.reconcile_module_ledger()` 在开奖后补上 actual/hits)

口径:
  - 单码随机基线 25.0%(快乐8每期开 20/80), Lift = 实际命中率 ÷ 25.0%;
  - 滚动指标复用 `core.wf_hit_engine` (与 module_ledger_report 同口径: lift/CI/p/BH-FDR);
  - 当期没有前瞻账记录的模块 **如实列为"无法复盘"**, 不补算、不编造。

用法:
    python -m backend.modules.daily_review.run_daily review           # 复盘最新已开奖期
    python -m backend.modules.daily_review.run_daily review 2026256   # 指定期号
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
for _p in [_PROJ_DIR, os.path.join(_PROJ_DIR, "backend")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils.paths import get_reports_dir, get_reviews_dir  # noqa: E402
from backend.modules.daily_review.harvester import EXTRACTORS  # noqa: E402

BASELINE = 0.25


def _fmt(nums) -> str:
    return ' '.join('%02d' % n for n in nums) if nums else '—'


def latest_drawn_period() -> str:
    from backend.utils.history_loader import load_history
    hist = load_history()
    if not hist:
        raise RuntimeError("历史开奖为空")
    return str(hist[0]["issue"])


def _load_ledger_rows(period: str) -> List[Dict[str, Any]]:
    from backend.core.module_gate import _load_module_ledger
    return [r for r in _load_module_ledger() if str(r.get("period")) == str(period)]


def review_period(period: Optional[str] = None, verbose: bool = True) -> Dict[str, Any]:
    """对指定已开奖期号生成逐模块命中明细。"""
    from backend.utils.history_loader import load_history

    if not period:
        period = latest_drawn_period()
    period = str(period)

    hist = load_history()
    draw_map = {str(h["issue"]): h for h in hist}
    if period not in draw_map:
        raise RuntimeError("第 %s 期尚未开奖或不在历史库中, 无法复盘" % period)

    draw = draw_map[period]
    actual = sorted(int(x) for x in draw["numbers"])
    actual_set = set(actual)

    rows = _load_ledger_rows(period)
    by_mod: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        picks = [int(x) for x in (r.get("picks") or [])]
        if not picks:
            continue
        hits = sorted(set(picks) & actual_set)
        size = len(picks)
        rate = len(hits) / size if size else 0.0
        by_mod[r["module"]] = {
            "module": r["module"], "picks": picks, "size": size,
            "hits": hits, "hit_count": len(hits), "rate": rate,
            "lift": rate / BASELINE if size else None,
            "recorded_at": r.get("timestamp"),
            "settled": r.get("actual") is not None,
        }

    # 模块中文名 / 舱位 (取自收割清单; 收割清单是模块全集, 用于列出"无留存"者)
    name_of = {s["id"]: s["name"] for s in EXTRACTORS}
    lane_of = {s["id"]: s["lane"] for s in EXTRACTORS}

    reviewed = sorted(by_mod.values(), key=lambda x: (-x["rate"], -x["hit_count"]))
    unreviewed = [{"id": s["id"], "name": s["name"], "lane": s["lane"]}
                  for s in EXTRACTORS if s["id"] not in by_mod]

    # 滚动口径 (与 module_ledger_report 同源)
    rolling: Dict[str, Any] = {}
    try:
        from backend.core.module_gate import module_ledger_report
        rolling = module_ledger_report(min_n=30).get("modules", {}) or {}
    except Exception as e:
        rolling = {"_error": str(e)}

    total_picks = sum(x["size"] for x in reviewed)
    total_hits = sum(x["hit_count"] for x in reviewed)
    pooled_rate = (total_hits / total_picks) if total_picks else None

    result = {
        "status": "ok",
        "period": period,
        "date": draw.get("date"),
        "actual": actual,
        "generated_at": datetime.now().isoformat(),
        "baseline": BASELINE,
        "modules_reviewed": len(reviewed),
        "modules_unreviewed": len(unreviewed),
        "total_picks": total_picks,
        "total_hits": total_hits,
        "pooled_rate": pooled_rate,
        "pooled_lift": (pooled_rate / BASELINE) if pooled_rate is not None else None,
        "reviewed": reviewed,
        "unreviewed": unreviewed,
        "rolling": rolling,
    }

    md = _render_markdown(result, name_of, lane_of)
    out_dir = get_reports_dir()
    os.makedirs(out_dir, exist_ok=True)
    md_file = os.path.join(out_dir, "复盘明细_%s.md" % period)
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md)
    result["report_file"] = md_file

    rv_dir = os.path.join(get_reviews_dir(), "period_review")
    os.makedirs(rv_dir, exist_ok=True)
    json_file = os.path.join(rv_dir, "review_%s.json" % period)
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    result["json_file"] = json_file

    # 联动触发点位重码追踪器自动更新与上色 (复刻图1压舱石指标)
    try:
        from backend.modules.point_repeat_tracker import sync_and_update_tracker
        sync_and_update_tracker(target_period=period)
    except Exception as _track_err:
        pass

    if verbose:
        print('=' * 76)
        print('  🔍 逐模块逐期复盘  第 %s 期 (%s)' % (period, draw.get('date')))
        print('=' * 76)
        print('  开奖: %s' % '-'.join('%02d' % n for n in actual))
        print('  本期有前瞻账的模块: %d 个 (共 %d 票, 命中 %d, 池化命中率 %.1f%%)'
              % (len(reviewed), total_picks, total_hits, (pooled_rate or 0) * 100))
        print('  ── 命中明细 ──')
        for x in reviewed:
            print('  %-24s %-26s %2d/%-2d  %5.1f%%  Lift %.2fx  中: %s'
                  % (x['module'], name_of.get(x['module'], '')[:24], x['hit_count'], x['size'],
                     x['rate'] * 100, x['lift'] or 0, _fmt(x['hits'])))
        if unreviewed:
            print('  ── 无前瞻账、无法复盘 %d 个 ──' % len(unreviewed))
            for u in unreviewed:
                print('     · %-22s %s' % (u['id'], u['name']))
        print('  📄 %s' % md_file)
        print('=' * 76)

    return result


def _render_markdown(res: Dict[str, Any], name_of: Dict[str, str],
                     lane_of: Dict[str, str]) -> str:
    L: List[str] = []
    A = L.append
    period = res["period"]
    A("# 第 %s 期 · 逐模块预测命中明细复盘" % period)
    A("")
    A("**已开奖期**：第 %s 期（%s）　｜　**复盘生成**：%s"
      % (period, res.get("date"), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    A("")
    A("**开奖号码（20码）**：`%s`" % '-'.join('%02d' % n for n in res["actual"]))
    A("")
    A("> 随机基线：单码 25.0%　｜　Lift = 实际命中率 ÷ 25.0%")
    A("> 号码取自追加式前瞻账 `storage/cache/paper_trading_modules.jsonl`（各模块开奖前真实产出，由收割器抽取）")
    A("> 当期没有前瞻账的模块**如实列为「无法复盘」**，不补算、不编造。")
    A("")
    A("---")
    A("")
    A("## 一、总览")
    A("")
    if res["pooled_rate"] is None:
        A("- ⚠️ 本期**没有任何模块的前瞻账记录**，无法复盘。")
    else:
        A("- 有前瞻账的模块：**%d 个**　｜　合计 **%d 票**，命中 **%d 票**"
          % (res["modules_reviewed"], res["total_picks"], res["total_hits"]))
        A("- 池化命中率：**%.1f%%**　｜　池化 Lift：**%.2fx**"
          % (res["pooled_rate"] * 100, res["pooled_lift"] or 0))
        A("- 无前瞻账、无法复盘：**%d 个模块**（见第四节）" % res["modules_unreviewed"])
    A("")
    A("---")
    A("")
    A("## 二、逐模块命中明细（按命中率降序）")
    A("")
    A("| 模块 | 中文名 | 舱位 | 推荐号码 | 命中 | 命中号 | 命中率 | Lift |")
    A("| :--- | :--- | :---: | :--- | :---: | :--- | :---: | :---: |")
    for x in res["reviewed"]:
        mid = x["module"]
        A("| `%s` | %s | %s | `%s` | %d/%d | %s | %.1f%% | %.2fx |"
          % (mid, name_of.get(mid, mid), lane_of.get(mid, '?'), _fmt(x["picks"]),
             x["hit_count"], x["size"], _fmt(x["hits"]), x["rate"] * 100, x["lift"] or 0))
    if not res["reviewed"]:
        A("| — | — | — | — | — | — | — | — |")
    A("")
    A("---")
    A("")
    A("## 三、滚动口径对照（同 `module_ledger_report` 口径）")
    A("")
    A("> 单期命中差异不构成显著性；下表为各模块**已开奖前瞻账**的池化滚动指标（lift / CI下界 / p / BH-q）。")
    A("")
    A("| 模块 | 已对账期数 | 总票数 | 总命中 | 池化命中率 | Lift | CI下界 | p | BH-q | 显著性 | 门禁进度 |")
    A("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    roll = res.get("rolling") or {}
    if "_error" in roll:
        A("| ⚠️ | %s | | | | | | | | | |" % roll["_error"])
    else:
        for mid in sorted(roll.keys()):
            m = roll[mid]
            # 2026-10-21 统计诚信修复 (Bug#7)：改读真正的 BH-FDR 校正位，
            # 不再把单模块未校正的 `significant` 标成「✓FDR显著」。
            sig = ('✓BH-FDR显著' if m.get('bh_significant')
                   else ('样本不足' if m.get('insufficient') else '未过BH-FDR'))
            # 2026-11-09 统计诚信修复：bh_q 为 None 表示该模块已被移出 BH-FDR 校正族
            # （退役/observation），此处曾用 `or 0` 渲染成 0.000 —— 那是"最强显著"的读数，
            # 与同一行的「未过BH-FDR」自相矛盾，且 module_gate 明令不得把不参与校正抹成 0。
            _bhq = m.get("bh_q")
            bh_q_disp = "—（不参与校正）" if _bhq is None else "%.3f" % _bhq
            A("| `%s` | %d | %d | %d | %.1f%% | %.3f | %.3f | %.3f | %s | %s | %s |"
              % (mid, m.get("n_periods", 0), m.get("total_picks", 0), m.get("total_hits", 0),
                 (m.get("pooled_rate") or 0) * 100, m.get("lift") or 0, m.get("lift_ci_lo") or 0,
                 m.get("p_value") or 0, bh_q_disp, sig, m.get("gate_progress", '')))
        if not roll:
            A("| — | | | | | | | | | | |")
    A("")
    A("---")
    A("")
    A("## 四、无法复盘的模块（无前瞻账记录）")
    A("")
    if not res["unreviewed"]:
        A("- ✅ 本期全部已知模块均有前瞻账记录。")
    else:
        A("| 模块 | 中文名 | 舱位 | 原因 |")
        A("| :--- | :--- | :---: | :--- |")
        for u in res["unreviewed"]:
            A("| `%s` | %s | %s | 当期未写入前瞻账：产物缺失、或产物目标期未刷新、或抽不到号码 |"
              % (u["id"], u["name"], u["lane"]))
    A("")
    A("---")
    A("")
    A("## 五、本期结论")
    A("")
    if res["reviewed"]:
        best = res["reviewed"][0]
        worst = sorted(res["reviewed"], key=lambda x: (x["rate"], -x["size"]))[0]
        A("1. **表现最好**：`%s`（%s）命中 %d/%d = %.1f%%，Lift %.2fx。"
          % (best["module"], name_of.get(best["module"], ''), best["hit_count"], best["size"],
             best["rate"] * 100, best["lift"] or 0))
        A("2. **表现最差**：`%s`（%s）命中 %d/%d = %.1f%%，Lift %.2fx。"
          % (worst["module"], name_of.get(worst["module"], ''), worst["hit_count"], worst["size"],
             worst["rate"] * 100, worst["lift"] or 0))
        zero = [x for x in res["reviewed"] if x["hit_count"] == 0]
        if zero:
            A("3. **全灭模块（0 命中）**：%s —— 共 %d 个。"
              % ('、'.join('`%s`' % x["module"] for x in zero), len(zero)))
        A("4. **口径提醒**：以上为**单期**结果，单期命中差异不构成显著性；请结合第三节滚动口径与 p/BH-q 判断，"
          "未过显著性门槛者不可作为下注依据。")
    else:
        A("1. 本期无前瞻账记录，结论为空 —— 需先执行 `harvest` 再复盘。")
    A("")
    A("---")
    A("")
    A("*本报告由 `backend/modules/daily_review/reviewer.py` 自动生成 · 目标期 %s*" % period)
    return '\n'.join(L)


if __name__ == '__main__':
    review_period(verbose=True)