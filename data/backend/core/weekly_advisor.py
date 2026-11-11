# -*- coding: utf-8 -*-
"""
weekly_advisor.py — 周度权重调整建议单 (C4 复盘还账)
=====================================================
大白话:
  系统里有一堆"投票权重"数字在决定谁说话算数。以前这些数字要么是拍脑袋定的,
  要么被每晚自动刷新悄悄改掉, 没人复盘"这周权重变动合理吗"。
  本模块每周日出**一张建议单**: 逐模块告诉你"证据长什么样 / 建议保持还是调整 /
  为什么", 并且**只提建议、绝不自动改参数**。要生效, 得由人跑:

      python -m backend.core.weekly_advisor --apply --who 你的名字

  --apply 只做两件机器不能自己做、必须人类拍板的事:
      (1) 观察仓 → 有票权 (C6 满 200 期且过 BH-FDR, 机器只降不升)
      (2) 退役某个模块 (人类判决, 数据再好也不自动复活)
  写入 backend/config/module_decree_overrides.json, 带 who/when/why/basis 审计痕迹。
  普通投票权重的微调不在此列 —— 那是每晚 100 期天梯榜的自动活儿, 人工去改会被
  第二天覆盖, 提了也是做戏。

产物:
  outputs/reports/weekly_weight_advice_YYYY-Www.json
  outputs/reports/weekly_weight_advice_YYYY-Www.md
"""
from backend.utils.paths import get_outputs_dir
import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in (_BACKEND_DIR, _PROJ_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.module_gate import (
    ModuleGate, load_decree_overrides, save_decree_overrides,
    MIN_PROSPECTIVE_PERIODS, FDR_ALPHA, BASELINE,
)

REPORTS_DIR = os.path.join(get_outputs_dir(), "reports")
ADVICE_LOG = os.path.join(REPORTS_DIR, "weekly_weight_apply_log.jsonl")


def _reports_dir(root: Optional[str] = None) -> str:
    """建议单与审计日志的落脚目录 —— 统一 storage/outputs/reports。"""
    if root:
        return os.path.join(root, "storage", "outputs", "reports")
    return REPORTS_DIR

# 建议动作代码 → 大白话
ACTION_TEXT = {
    "keep_retired":     "保持退役",
    "keep_votable":     "保持有票权",
    "keep_observation": "保持观察仓",
    "promote":          "建议升为有票权 (需人工批准)",
    "demote":           "建议降为观察仓",
    "decide":           "待人工裁决: 补预注册 或 退役",
    "retire":           "建议退役 (需人工批准)",
    "watch":            "样本不足, 继续观察",
}
NEEDS_HUMAN = {"promote", "retire", "decide"}


def _iso_week_tag(now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def should_run_today(now: Optional[datetime] = None) -> bool:
    """nightly 里用它判断今天该不该出建议单 (每周日; weekday(): 周一=0 … 周日=6)。"""
    return (now or datetime.now()).weekday() == 6


def _weekday_cn(d: datetime) -> str:
    return "周" + "一二三四五六日"[d.weekday()]


def _classify(m: Dict[str, Any]) -> Dict[str, Any]:
    """给单个模块下判断: 建议动作 + 理由 (纯读, 不改任何东西)。"""
    st = m.get("status", "observation")
    ev = m.get("evidence") or {}
    n = int(ev.get("n_periods") or 0)
    ls = ev.get("lift_shrunk")
    ci = ev.get("lift_ci_lo")
    lift = ev.get("lift")
    sig = bool(ev.get("significant"))
    insuff = bool(ev.get("insufficient", n < 100))
    prosp = int(m.get("prospective_periods") or 0)
    prereg = m.get("preregistered")
    name = m.get("name") or m.get("id")

    def ev_txt():
        if n <= 0:
            return "无 live 证据 (尚未进 100 期榜)"
        return (f"n={n}期, 实测Lift={lift if lift is not None else '-'}x, "
                f"收缩后Lift={ls if ls is not None else '-'}, "
                f"CI下界={ci if ci is not None else '-'}"
                + ("  ⚠️样本不足100期" if insuff else ""))

    if st == "retired":
        return {"action": "keep_retired", "needs_human": False,
                "reason": (m.get("decree") or {}).get("reason", "人类退役判决")}

    if st == "votable":
        if n <= 0:
            return {"action": "keep_votable", "needs_human": False,
                    "reason": "尚无 live 证据, 暂按审计种子权重执行, 等 100 期榜刷新"}
        if ls is not None and ls < 1.0 and n >= 60:
            return {"action": "demote", "needs_human": False,
                    "reason": f"{ev_txt()} —— 收缩后 Lift 跌破 1.0, nightly 下一晚会自动降观察仓"}
        if ls is not None and ls < 1.0:
            return {"action": "watch", "needs_human": False,
                    "reason": f"{ev_txt()} —— 收缩后 Lift<1.0 但样本太薄(n<60), 不急着降级; "
                              f"连续 4 周如此再建议降观察仓"}
        return {"action": "keep_votable", "needs_human": False, "reason": ev_txt()}

    # observation
    if prereg:
        if prosp < MIN_PROSPECTIVE_PERIODS:
            return {"action": "keep_observation", "needs_human": False,
                    "reason": f"前瞻账 {prosp}/{MIN_PROSPECTIVE_PERIODS} 期, 未满门槛; {ev_txt()}"}
        if sig and (ci or 0) > 1.0:
            return {"action": "promote", "needs_human": True,
                    "reason": (f"前瞻账已满 {prosp} 期, 且过 BH-FDR(q<{FDR_ALPHA}) 与 CI下界>1.0; "
                               f"{ev_txt()} —— 证据达标, 建议批准升为有票权")}
        return {"action": "keep_observation", "needs_human": False,
                "reason": f"前瞻账已满 {prosp} 期, 但未同时满足 BH-FDR(q<{FDR_ALPHA}) 与 CI下界>1.0; {ev_txt()}"}

    return {"action": "decide", "needs_human": True,
            "reason": (f"在跑、在记账, 但既没预注册也没退役 —— 属于'先上车后补票'。"
                       f"建议二选一: 补写预注册(假设+冻结规则, 前瞻账重新起算) 或 正式退役。{ev_txt()}")}


def build_weekly_advice(proj_dir: Optional[str] = None, write: bool = True,
                        now: Optional[datetime] = None) -> Dict[str, Any]:
    """产出本周《权重调整建议单》。write=True 时落盘 json + md。

    纯只读 + 只写报告, 绝不改注册表/参数 —— 要改参数请人工跑 --apply。
    """
    now = now or datetime.now()
    root = proj_dir or _PROJ_DIR
    gate = ModuleGate(root)
    reg = gate.registry()
    modules = reg.get("modules", {})

    rows: List[Dict[str, Any]] = []
    for mid, m in modules.items():
        cls = _classify(m)
        ev = m.get("evidence") or {}
        rows.append({
            "id": mid,
            "name": m.get("name") or mid,
            "cohort": m.get("cohort"),
            "status": m.get("status"),
            "vote_weight": m.get("vote_weight"),
            "prospective_periods": m.get("prospective_periods"),
            "evidence": {k: ev.get(k) for k in
                         ("n_periods", "lift", "lift_shrunk", "lift_ci_lo", "p_value", "bh_q",
                          "significant", "insufficient")},
            "action": cls["action"],
            "action_text": ACTION_TEXT.get(cls["action"], cls["action"]),
            "needs_human": cls["needs_human"],
            "reason": cls["reason"],
            "evidence_source": m.get("evidence_source"),
            "watermark": m.get("watermark"),
        })

    # 投票影响力分布: 权重在用时会被归一化, 所以真正决定话语权的是"占比"
    votable = [r for r in rows if r["status"] == "votable" and (r["vote_weight"] or 0) > 0]
    wsum = sum(r["vote_weight"] for r in votable)
    for r in votable:
        r["influence_share"] = round(r["vote_weight"] / wsum, 4) if wsum else 0.0
    top_influence = sorted(votable, key=lambda r: -r.get("influence_share", 0))[:3]

    need_human = [r for r in rows if r["needs_human"]]
    advice = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "week": _iso_week_tag(now),
        "weekday": _weekday_cn(now),
        "registry_generated_at": reg.get("generated_at"),
        "registry_basis": reg.get("basis"),
        "summary": {
            "n_modules": len(rows),
            "n_votable": sum(1 for r in rows if r["status"] == "votable"),
            "n_observation": sum(1 for r in rows if r["status"] == "observation"),
            "n_retired": sum(1 for r in rows if r["status"] == "retired"),
            "n_needs_human": len(need_human),
            "vote_weight_sum": round(wsum, 4),
            "top_influence": [{"name": r["name"], "share": r.get("influence_share"),
                               "weight": r["vote_weight"]} for r in top_influence],
        },
        "needs_human": [r["id"] for r in need_human],
        "modules": rows,
        "verdict": ("本周无需要人工裁决的事项, 自动口径继续跑"
                    if not need_human else
                    f"本周有 {len(need_human)} 项需人工裁决: "
                    + "、".join(r["name"] for r in need_human)),
        "how_to_apply": "python -m backend.core.weekly_advisor --apply --who <你的名字>",
    }

    if write:
        rdir = _reports_dir(root)
        os.makedirs(rdir, exist_ok=True)
        jf = os.path.join(rdir, f"weekly_weight_advice_{advice['week']}.json")
        with open(jf, "w", encoding="utf-8") as f:
            json.dump(advice, f, ensure_ascii=False, indent=2)
        mf = os.path.join(rdir, f"weekly_weight_advice_{advice['week']}.md")
        with open(mf, "w", encoding="utf-8") as f:
            f.write(render_markdown(advice))
        advice["json_path"] = jf
        advice["md_path"] = mf

    return advice


def render_markdown(a: Dict[str, Any]) -> str:
    s = a["summary"]
    L = []
    L.append(f"# 周度权重调整建议单 · {a['week']}")
    L.append("")
    L.append(f"> 生成时间: {a['generated_at']} ({a['weekday']})　"
             f"| 依据: 注册表快照 {a.get('registry_generated_at')}")
    L.append("> 这份单子**只提建议, 不会自动改任何参数**。"
             "要让建议生效, 由人工运行 `python -m backend.core.weekly_advisor --apply --who 你的名字`。")
    L.append("")
    L.append("## 一、本周结论")
    L.append("")
    L.append(f"- {a['verdict']}")
    L.append(f"- 模块盘子: 有票权 **{s['n_votable']}** 个 / 观察仓 **{s['n_observation']}** 个 / "
             f"已退役 **{s['n_retired']}** 个 (共 {s['n_modules']} 个)")
    L.append(f"- 当前投票权重合计 **{s['vote_weight_sum']}** (用时会被归一化, 真正决定话语权的是下面的占比)")
    L.append("")

    if s["top_influence"]:
        L.append("### 谁在说话: 投票权重占比 Top3")
        L.append("")
        L.append("| 模块 | 票权 | 占比 |")
        L.append("|---|---|---|")
        for t in s["top_influence"]:
            L.append(f"| {t['name']} | {t['weight']} | {t['share']:.1%} |")
        L.append("")

    human = [r for r in a["modules"] if r["needs_human"]]
    L.append("## 二、需要人工裁决的事项")
    L.append("")
    if not human:
        L.append("本周没有需要人工拍板的事项。所有模块的状态与权重都在自动口径内正常运行。")
    else:
        for r in human:
            L.append(f"- **{r['name']}** (`{r['id']}`) — {r['action_text']}")
            L.append(f"  - 理由: {r['reason']}")
    L.append("")

    L.append("## 三、逐模块明细")
    L.append("")
    L.append("| 模块 | 状态 | 票权 | 占比 | 建议 | 依据 |")
    L.append("|---|---|---|---|---|---|")
    for r in sorted(a["modules"], key=lambda x: (x["status"] != "votable", -(x["vote_weight"] or 0))):
        share = f"{r['influence_share']:.1%}" if r.get("influence_share") is not None else "—"
        L.append(f"| {r['name']} | {r['status']} | {r['vote_weight']} | {share} | "
                 f"{r['action_text']} | {r['reason']} |")
    L.append("")

    L.append("## 四、口径说明 (免得看错)")
    L.append("")
    L.append("- **票权** = `max(0, 收缩后Lift - 1.0)`。收缩是防「赢家诅咒」：小样本跑出高 Lift 会被向 1.0 拉回，"
             "公式 `(n*Lift + 30) / (n + 30)`。")
    L.append(f"- **新模块门禁 (C6)**：上线先预注册，前瞻记账满 {MIN_PROSPECTIVE_PERIODS} 期，"
             f"且过 BH-FDR (q<{FDR_ALPHA}) 与 95%CI 下界>1.0，才准升有票权。机器**只降不升**，升级必须人工批准。")
    L.append("- **基线** = 0.25（随机挑号的命中率 = 20/80）。Lift 就是「实测 ÷ 基线」，1.0 表示和瞎猜没差别。")
    L.append("- **样本不足水位**：n<100 期一律带「样本不足」水印，评级不许戴超高信标。")
    L.append("")
    return "\n".join(L)


def apply_advice(proj_dir: Optional[str] = None, who: str = "unknown",
                 advice: Optional[Dict[str, Any]] = None,
                 dry_run: bool = False) -> Dict[str, Any]:
    """人工确认后落地: 把建议单里 needs_human 的事项写进判决覆盖层。

    只落两类:
      promote (观察仓→有票权) 与 retire (→退役)。
    `decide` 类不自动落 —— 它要求人真的写出预注册假设或退役理由, 由人手工编辑文件。
    普通票权微调不落 —— 那是 nightly 天梯榜的自动活儿, 人工改了明天也会被覆盖。
    """
    root = proj_dir or _PROJ_DIR
    a = advice or build_weekly_advice(root, write=False)
    today = datetime.now().strftime("%Y-%m-%d")
    overrides = load_decree_overrides(root)
    applied, skipped = [], []
    basis = f"weekly_weight_advice_{a['week']}.json"

    for r in a["modules"]:
        if not r["needs_human"]:
            continue
        mid, act = r["id"], r["action"]
        if act == "promote":
            overrides[mid] = {
                "status": "votable",
                "date": today,
                "reason": f"C4 周度建议单人工批准升级: {r['reason']}",
                "approved_by": who, "basis": basis,
            }
            applied.append(f"{r['name']}: 观察仓 → 有票权")
        elif act == "retire":
            overrides[mid] = {
                "status": "retired",
                "date": today,
                "reason": f"C4 周度建议单人工批准退役: {r['reason']}",
                "approved_by": who, "basis": basis,
            }
            applied.append(f"{r['name']}: → 退役")
        else:  # decide
            skipped.append(f"{r['name']}: 需人工写出预注册假设或退役理由, 不自动落 (见 {basis})")

    if not dry_run and applied:
        entry = {"applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "who": who, "basis": basis, "changes": applied, "skipped": skipped}
        save_decree_overrides(overrides, root, entry)
        rdir = _reports_dir(root)
        os.makedirs(rdir, exist_ok=True)
        with open(os.path.join(rdir, "weekly_weight_apply_log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        ModuleGate(root).refresh_from_master_ledger()

    return {"status": "dry_run" if dry_run else "applied",
            "who": who, "basis": basis,
            "applied": applied, "skipped": skipped,
            "override_file": os.path.join(root, "backend", "config", "module_decree_overrides.json"),
            "note": "判决覆盖层已更新, 注册表已重算; 审计痕迹写入 weekly_weight_apply_log.jsonl"}


def main():
    ap = argparse.ArgumentParser(description="周度权重调整建议单 (C4)")
    ap.add_argument("--apply", action="store_true", help="人工确认后落地建议 (写判决覆盖层+审计日志)")
    ap.add_argument("--who", default="unknown", help="--apply 时记录操作人")
    ap.add_argument("--dry-run", action="store_true", help="只演练不落盘")
    ap.add_argument("--json", action="store_true", help="打印 JSON 而非人读文本")
    args = ap.parse_args()

    if args.apply:
        res = apply_advice(who=args.who, dry_run=args.dry_run)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    a = build_weekly_advice()
    if args.json:
        print(json.dumps(a, ensure_ascii=False, indent=2))
        return
    print(render_markdown(a))
    print(f"\n已写入: {a.get('json_path')}")
    print(f"        {a.get('md_path')}")


if __name__ == "__main__":
    main()
