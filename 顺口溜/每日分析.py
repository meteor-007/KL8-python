# -*- coding: utf-8 -*-
"""
顺口溜 快乐8 每日分析（重建版 2026-08-24）
================================================================
原理（大白话）：找"顺口溜"规律——某期同时开出了某几个号（触发组合），
            大概率下期带出另外某几个号（口诀）。只认能过验证的规律。
规则来源: rules_c/口诀表_stats.json（90条精英口诀，已过 FDR + 样本外验证）
数据来源: 共享 data/kl8_history_final.txt → 刷新本子系统 data/kl8_history.csv
动作: ①刷新数据 → ②近N期复盘(触发/命中/Lift) → ③今日触发口诀 → ④推荐码+落盘
用法: python 每日分析.py [N=30]
"""
import csv, json, os, re, sys
from datetime import datetime
from math import comb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SHARED_FILE = os.path.join(ROOT, "data", "kl8_history_final.txt")
DATA_FILE = os.path.join(BASE, "data", "kl8_history.csv")
RULES_FILE = os.path.join(BASE, "rules_c", "口诀表_stats.json")
OUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUT_DIR, exist_ok=True)

LINE = "═" * 74
THIN = "─" * 74

BASELINE_PAIR = 20 / 80 * 19 / 79      # 两特定号同时开出 = 0.0601
BASELINE_TRIPLE = 20 / 80              # 单号开出 = 0.25


def at_least_one_baseline(k):
    """随机推荐 k 个号"至少一中"的期望概率（不放回超几何精确值）。"""
    if k <= 0:
        return 0.0
    return 1.0 - comb(60, min(k, 60)) / comb(80, k)


def refresh_csv():
    """用共享开奖数据重建本子系统 CSV（本子系统数据独立，但以共享源为准）。"""
    rows = []
    for line in open(SHARED_FILE, encoding="utf-8"):
        m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line.strip())
        if not m:
            continue
        nums = [int(x) for x in m.group(3).split("-") if x.isdigit()]
        if len(nums) != 20:
            continue
        rows.append((int(m.group(2)), m.group(1), nums))
    rows.sort(key=lambda r: r[0])
    with open(DATA_FILE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["issue", "date"] + [f"n{i}" for i in range(1, 21)])
        for issue, date, nums in rows:
            w.writerow([issue, date] + nums)
    return len(rows)


def load_draws():
    """返回 [(issue:int, date:str, nums:list[int])] 时间升序。"""
    draws = []
    with open(DATA_FILE, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not r.get("n1"):
                continue
            nums = [int(r[f"n{i}"]) for i in range(1, 21)]
            draws.append((int(r["issue"]), r["date"], nums))
    return draws


def load_rules():
    d = json.load(open(RULES_FILE, encoding="utf-8"))
    return list(d["rules"].values()), d.get("meta", {})


def fired_rules(rules, draw_nums):
    """该期触发哪些口诀(trigger ⊆ 该期号码)。返回[(rule, predict, weight)]。"""
    s = set(draw_nums)
    out = []
    for r in rules:
        if all(x in s for x in r["trigger"]):
            out.append((r, r["predict"], r.get("hr_oof") or r.get("hr_train") or 0.0))
    return out


def banner(txt):
    print("\n" + LINE)
    print("  " + txt)
    print(LINE)


def step_review(draws, rules, n, sel_cut):
    """近n期: 用每期上一期触发口诀, 与本期实开对账。sel_cut=规则筛选窗口上限期号。"""
    banner(f"② 近 {n} 期复盘（用上一期触发口诀 → 对照本期实开）")
    pairs = []
    win = draws[-(n + 1):]
    for t in range(1, len(win)):
        trigger_draw = win[t - 1]
        target_draw = win[t]
        trg_issue, trg_date, trg_nums = trigger_draw
        tgt_issue, tgt_date, tgt_nums = target_draw
        fired = fired_rules(rules, trg_nums)
        if not fired:
            continue
        rec = []
        np_ok = nt_ok = 0
        for r, pred, w in fired:
            rec.extend(pred)
            if r["kind"] == "pair_pair":
                if set(pred) <= set(tgt_nums):
                    np_ok += 1
            else:
                if pred[0] in tgt_nums:
                    nt_ok += 1
        rec = sorted(set(rec))
        hit_n = len(set(rec) & set(tgt_nums))
        at_least_one = hit_n > 0
        pairs.append({
            "trg": trg_issue, "tgt": tgt_issue,
            "nfired": len(fired), "rec": rec, "hit_n": hit_n,
            "at_least_one": at_least_one, "np_ok": np_ok, "nt_ok": nt_ok,
            "np_fire": sum(1 for r, *_ in fired if r["kind"] == "pair_pair"),
            "nt_fire": sum(1 for r, *_ in fired if r["kind"] == "triple_single"),
        })
    if not pairs:
        print("  ⚠️ 复盘期内没有口诀被触发。"); return pairs, {}

    print("   触发期     目标期   触发口诀数  推荐码            中N/个  至少一中  双双中/触发  单中/触发")
    print("  " + THIN)
    for p in pairs:
        rec_s = " ".join(f"{x:02d}" for x in p["rec"]) or "—"
        flag = "✅" if p["at_least_one"] else "❌"
        pp = f"{p['np_ok']}/{p['np_fire']}"
        pt = f"{p['nt_ok']}/{p['nt_fire']}"
        print(f"   {p['trg']}  → {p['tgt']}     {p['nfired']:>4}        {rec_s:<24}  {p['hit_n']:>2}    {flag}      {pp:<7} {pt}")
    print("  " + THIN)

    total_fire = sum(p["nfired"] for p in pairs)
    n_at = sum(1 for p in pairs if p["at_least_one"])
    hit_total = sum(p["hit_n"] for p in pairs)
    rec_total = sum(len(p["rec"]) for p in pairs)
    np_f = sum(p["np_fire"] for p in pairs)
    np_h = sum(p["np_ok"] for p in pairs)
    nt_f = sum(p["nt_fire"] for p in pairs)
    nt_h = sum(p["nt_ok"] for p in pairs)
    base_at = sum(at_least_one_baseline(len(p["rec"])) for p in pairs) / len(pairs)

    at_rate = n_at / len(pairs)
    bl_lift = None
    if base_at > 0:
        bl_lift = at_rate / base_at
    cur_area = {
        "n": len(pairs),
        "fired": total_fire,
        "at_rate": at_rate, "baseline_at": base_at, "lift_at": bl_lift,
        "avg_hit": hit_total / len(pairs),
        "np": (np_h, np_f), "nt": (nt_h, nt_f),
        "avg_rec": rec_total / len(pairs),
    }
    print(f"  📊 触发期 {len(pairs)} 期 / 共触发 {total_fire} 条口诀（平均每期推荐 {cur_area['avg_rec']:.1f} 个码）")
    print(f"     「至少一中」命中率 {at_rate*100:.1f}% | 随机基线(推荐量自适应) ≈{base_at*100:.1f}% | Lift={bl_lift:.2f}x" if bl_lift else "     「至少一中」命中率见上（基线=0）")
    print(f"     平均单期命中 {cur_area['avg_hit']:.2f} 码")
    if np_f:
        print(f"     两号齐出规则: 命中 {np_h}/{np_f} = {np_h/np_f*100:.1f}% | 随机 6.0% | Lift={np_h/np_f/BASELINE_PAIR:.2f}x")
    if nt_f:
        print(f"     单号规则:     命中 {nt_h}/{nt_f} = {nt_h/nt_f*100:.1f}% | 随机25.0% | Lift={nt_h/nt_f/BASELINE_TRIPLE:.2f}x")

    # 分层: 规则筛选窗口内(≤2026210)有选择偏差, 之后才是真·样本外
    segments = {}
    for bucket, cond in (("规则筛查窗口(有选择偏差)", lambda p: p["trg"] <= sel_cut),
                         ("真·样本外(筛选之后)", lambda p: p["trg"] > sel_cut)):
        sub = [p for p in pairs if cond(p)]
        if not sub:
            continue
        n_f = sum(p["nfired"] for p in sub)
        n_at = sum(1 for p in sub if p["at_least_one"])
        b_a = sum(at_least_one_baseline(len(p["rec"])) for p in sub) / len(sub)
        np2 = (sum(p["np_ok"] for p in sub), sum(p["np_fire"] for p in sub))
        nt2 = (sum(p["nt_ok"] for p in sub), sum(p["nt_fire"] for p in sub))
        at_r = n_at / len(sub)
        lift_s = at_r / b_a if b_a else float("nan")
        seg = f"  {bucket}: 触发期 {len(sub)} 期/触发 {n_f} 条 | 至少一中 {at_r*100:.1f}% vs基线{b_a*100:.1f}% Lift={lift_s:.2f}x"
        if np2[1]:
            seg += f" | 两号齐出 {np2[0]}/{np2[1]}={np2[0]/np2[1]*100:.1f}% (Lift={np2[0]/np2[1]/BASELINE_PAIR:.2f}x)"
        if nt2[1]:
            seg += f" | 单号 {nt2[0]}/{nt2[1]}"
        print(seg)
        segments[bucket] = {"n": len(sub), "np": np2, "nt": nt2}
    cur_area["segments"] = segments
    return pairs, cur_area


def step_predict(draws, rules, cur=None):
    latest = draws[-1]
    l_issue, l_date, l_nums = latest
    banner(f"③ 今日口诀触发（基于最新期 {l_issue} {l_date} 触发）")
    fired = fired_rules(rules, l_nums)
    if not fired:
        print("  ⚠️ 今日没有口诀被触发；如要买，只能当随机选号看待。")
        return None, []
    fired.sort(key=lambda x: x[2], reverse=True)
    print("   口诀   类型            触发组合      口诀(推荐)      OOF命中率  OOF_Lift  样本外触发/命中")
    print("  " + THIN)
    agg = {}
    for r, pred, w in fired:
        kname = "两号齐出" if r["kind"] == "pair_pair" else "单号带出"
        if r["kind"] == "pair_pair":
            base = BASELINE_PAIR
        else:
            base = BASELINE_TRIPLE
        lift = w / base if base else 0.0
        tr_s = " ".join(f"{x:02d}" for x in r["trigger"])
        pd_s = " ".join(f"{x:02d}" for x in pred)
        print(f"   {tr_s:>12} {kname:>6}   {tr_s:<12} {pd_s:<16}  {w*100:>6.1f}%   {lift:>5.2f}x   {r.get('triggers_oof','-')}/{r.get('hits_oof','-')}")
        for num in pred:
            agg[num] = agg.get(num, 0.0) + w
    rec = sorted(agg.items(), key=lambda kv: -kv[1])
    top_nums = [n for n, _ in rec]
    banner("④ 推荐码（按口诀OOF命中率加权聚合）")
    print("  🎯 推荐码: " + " ".join(f"{n:02d}" for n in top_nums))
    k = len(top_nums)
    base_at = at_least_one_baseline(k)
    print(f"     推荐 {k} 个码，期望「至少一中」≈{base_at*100:.0f}%（随机水平参考线）")
    if cur:
        seg = cur.get("segments", {}).get("真·样本外(筛选之后)")
        if seg and seg["np"][1]:
            h, f = seg["np"]
            lift = (h / f) / BASELINE_PAIR if f else 0.0
            mark = "✅" if lift >= 1.05 else ("⚠️" if lift >= 1.0 else "❌")
            print(f"     ⚠️ 诚实提醒: 口诀的OOF命中率来自筛选窗口(偏高)；真·样本外近{seg['n']}期"
                  f"两号齐出规则实际 {h}/{f}={100*h/f:.1f}% (Lift={lift:.2f}x {mark})，低于随机水平，请谨慎对待")
    target_now = latest_issue_plus_one(draws)
    pfile = os.path.join(OUT_DIR, f"顺口溜预测_{target_now}.txt")
    with open(pfile, "w", encoding="utf-8") as f:
        f.write("顺口溜 快乐8 每日分析（重建版）\n")
        f.write(f"生成: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"基于最新期 {l_issue} ({l_date}) 触发\n目标期: {target_now}\n")
        f.write("=" * 56 + "\n")
        f.write("触发口诀:\n")
        for r, pred, w in fired:
            f.write(f"  触发 {r['trigger']} → 推荐 {pred} | OOF命中 {w*100:.1f}%\n")
        f.write("=" * 56 + "\n")
        f.write("推荐码: " + " ".join(f"{n:02d}" for n in top_nums) + "\n")
        f.write(f"推荐 {k} 码「至少一中」期望 {base_at*100:.1f}% (随机基线)\n")
    print(f"\n  📄 预测落盘: {os.path.relpath(pfile, BASE)}")
    return top_nums, fired


def latest_issue_plus_one(draws):
    issue = str(draws[-1][0])
    year, seq = int(issue[:4]), int(issue[4:])
    return str(year) + str(seq + 1).zfill(3)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    banner(f"顺口溜 快乐8 每日分析  v2  (重建版 2026-08-24)  复盘期数={n}")
    n_csv = refresh_csv()
    draws = load_draws()
    rules, meta = load_rules()
    print(f"  📁 数据: {len(draws)} 期 (最新 {draws[-1][0]} {draws[-1][1]}) | CSV已从共享源刷新")
    print(f"  📜 口诀表: {len(rules)} 条精英规则 | 生成 {meta.get('generated','-')} | 已过FDR+样本外验证")
    print(f"  🎯 目标期: {latest_issue_plus_one(draws)}")
    pairs, cur = step_review(draws, rules, n, int(str(meta.get("val_end_period", "2026210"))))
    top_nums, fired = step_predict(draws, rules, cur)
    banner("完成 ✅")


if __name__ == "__main__":
    main()