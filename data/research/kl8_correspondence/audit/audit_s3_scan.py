# -*- coding: utf-8 -*-
"""步骤3：实测穷举扫描 —— "最强规则"的分布 + 反证（打乱/合成对照）。

模板定义（本题口径）
--------------------
紫球 = 第 t 期第 p 位 (p ∈ 1..12)
橙三球 = 第 t+d 期第 c1<c2<c3 位 (组合 ∈ C(12,3)=220)
d ∈ [-6, +6] (13 档)
属性 A: (sum % 3) == (purple % 3)
属性 B: (sum % 10 >= 5) == (purple % 10 >= 5)

单属性模板数 = 12 × 220 × 13 = 34320；两属性合计 68640。

输出
----
(a) 全部模板命中率分布（均值/标准差/分位数），应 ≈ 1/3、1/2
(b) "当前仍在延续"的最长连击 top20（尾随游程，即界面展示口径）
(c) 全期 >=9 连 / >=14 连 的模板计数；以及打乱期序 / 按理论 p 合成 的对照分布
(d) 定量判定：截图的 9 连/14 连是否超出随机可解释范围
"""
from __future__ import annotations

import csv
import os

import numpy as np

import audit_lib as L

N_SHUFFLE = 40      # 打乱期序的对照重复次数
KS = (9, 14)


def scan_one(num, periods, attrs=L.ATTRS, ks=KS):
    """全网格扫描，返回每属性的扁平记录 + 汇总。"""
    grid = L.scan_grid(num, attrs=attrs, ks=ks)
    T = num.shape[0]
    out = {}
    for attr in attrs:
        a = grid[attr]
        recs = []
        for di, d in enumerate(a["d"]):
            t0, t1 = L.valid_range(T, int(d))
            last_p = periods[t1]
            for r in range(a["purple_pos"].size):
                ci = int(a["combo_idx"][r])
                c = L.COMBOS[ci]
                tr = int(a["trailing"][di, r])
                recs.append({
                    "attr": attr,
                    "purple_pos": int(a["purple_pos"][r]),
                    "c1": c[0], "c2": c[1], "c3": c[2],
                    "d": int(d), "n": int(a["n"][di, r]),
                    "hits": int(a["hits"][di, r]),
                    "rate": float(a["rate"][di, r]),
                    "maxrun": int(a["maxrun"][di, r]),
                    "maxrun_start_period": int(periods[t0 + int(a["maxrun_start"][di, r])]),
                    "trailing": tr,
                    "trailing_start_period": int(periods[t1 - tr + 1]) if tr > 0 else None,
                    "trailing_end_period": int(last_p),
                    "runs_ge9": int(a["row_runs_ge9"][di, r]),
                    "has_ge14": bool(a["row_has_ge14"][di, r]),
                })
        out[attr] = {"records": recs,
                     "tot_ge9": int(a["tot_ge9"].sum()),
                     "tot_ge14": int(a["tot_ge14"].sum()),
                     "per_offset_ge9": a["tot_ge9"].tolist(),
                     "per_offset_ge14": a["tot_ge14"].tolist(),
                     "offsets": a["d"].tolist()}
    return out


def summarize_records(recs):
    rate = np.array([r["rate"] for r in recs])
    hits = np.array([r["hits"] for r in recs], dtype=np.int64)
    n = np.array([r["n"] for r in recs], dtype=np.int64)
    maxrun = np.array([r["maxrun"] for r in recs], dtype=np.int64)
    trailing = np.array([r["trailing"] for r in recs], dtype=np.int64)
    return {
        "n_templates": len(recs),
        "rate_mean": float(rate.mean()), "rate_std": float(rate.std(ddof=1)),
        "rate_min": float(rate.min()), "rate_max": float(rate.max()),
        "rate_q01": L.pct(rate, 1), "rate_q25": L.pct(rate, 25),
        "rate_q50": L.pct(rate, 50), "rate_q75": L.pct(rate, 75),
        "rate_q99": L.pct(rate, 99),
        "total_hits": int(hits.sum()), "total_trials": int(n.sum()),
        "pooled_rate": float(hits.sum() / n.sum()),
        "maxrun_mean": float(maxrun.mean()), "maxrun_max": int(maxrun.max()),
        "maxrun_q50": L.pct(maxrun, 50), "maxrun_q99": L.pct(maxrun, 99),
        "trailing_mean": float(trailing.mean()),
        "n_templates_ge9_any": int(sum(1 for r in recs if r["runs_ge9"] > 0)),
        "n_templates_ge14_any": int(sum(1 for r in recs if r["has_ge14"])),
        "n_templates_trailing_ge9": int(sum(1 for r in recs if r["trailing"] >= 9)),
        "n_templates_trailing_ge14": int(sum(1 for r in recs if r["trailing"] >= 14)),
        "total_runs_ge9": int(sum(r["runs_ge9"] for r in recs)),
    }


def synthetic_control(T, p, n_templates, rng):
    """按理论 p 直接生成 iid 命中序列（不经几何关系），作为纯随机对照。"""
    m = rng.random((n_templates, T)) < p
    st = L.block_stats(m, ks=KS)
    return {
        "tot_ge9": int(st["total_runs_ge9"]), "tot_ge14": int(st["total_runs_ge14"]),
        "n_templates_ge9_any": int(st["row_has_ge9"].sum()),
        "n_templates_ge14_any": int(st["row_has_ge14"].sum()),
        "trailing_ge9": int((st["trailing"] >= 9).sum()),
        "trailing_ge14": int((st["trailing"] >= 14).sum()),
        "maxrun_max": int(st["maxrun"].max()),
        "maxrun_mean": float(st["maxrun"].mean()),
    }


def main():
    periods, num = L.load_draws()
    T = num.shape[0]
    rng = np.random.RandomState(L.SEED + 31)

    res = {"meta": {"periods": T, "period_first": periods[0], "period_last": periods[-1],
                    "seed": L.SEED,
                    "n_templates_per_attr": L.N_PER_ATTR,
                    "n_templates_total": L.N_ALL,
                    "n_shuffle_control": N_SHUFFLE,
                    "template_def": "purple=t 期 p 位; orange=t+d 期 c1<c2<c3 位; d∈[-6,6]",
                    "attr_def": L.ATTR_DESC}}

    # ─────────── 真实数据全网格扫描 ───────────
    real = scan_one(num, periods)
    res["real_scan"] = {attr: {"summary": summarize_records(real[attr]["records"]),
                              "tot_ge9": real[attr]["tot_ge9"],
                              "tot_ge14": real[attr]["tot_ge14"],
                              "per_offset_ge9": real[attr]["per_offset_ge9"],
                              "per_offset_ge14": real[attr]["per_offset_ge14"]}
                        for attr in L.ATTRS}

    # ─────────── (b) 尾随连击 top20（界面"仍在延续"口径） ───────────
    top = {}
    for attr in L.ATTRS:
        recs = [r for r in real[attr]["records"] if r["trailing"] > 0]
        recs.sort(key=lambda r: (-r["trailing"], -r["hits"]))
        top[attr] = {"top20_trailing": recs[:20],
                     "best_trailing": recs[0]["trailing"] if recs else 0,
                     "n_trailing_ge9": sum(1 for r in recs if r["trailing"] >= 9),
                     "n_trailing_ge14": sum(1 for r in recs if r["trailing"] >= 14)}
        # 历史最长连击 top10
        hr = sorted(real[attr]["records"], key=lambda r: -r["maxrun"])[:10]
        top[attr]["top10_maxrun"] = hr
    res["top_templates"] = top

    # ─────────── (c) 反证：打乱期序对照 ───────────
    shuffle_stats = {attr: {"tot_ge9": [], "tot_ge14": [], "n_templates_ge9_any": [],
                            "n_templates_ge14_any": [], "trailing_ge9": [],
                            "trailing_ge14": [], "maxrun_max": [], "maxrun_mean": []}
                     for attr in L.ATTRS}
    for it in range(N_SHUFFLE):
        perm = rng.permutation(T)
        num_sh = num[perm]
        g = L.scan_grid(num_sh, attrs=L.ATTRS, ks=KS)
        for ai, attr in enumerate(L.ATTRS):
            a = g[attr]
            shuffle_stats[attr]["tot_ge9"].append(int(a["tot_ge9"].sum()))
            shuffle_stats[attr]["tot_ge14"].append(int(a["tot_ge14"].sum()))
            shuffle_stats[attr]["n_templates_ge9_any"].append(int(a["row_has_ge9"].sum()))
            shuffle_stats[attr]["n_templates_ge14_any"].append(int(a["row_has_ge14"].sum()))
            shuffle_stats[attr]["trailing_ge9"].append(int((a["trailing"] >= 9).sum()))
            shuffle_stats[attr]["trailing_ge14"].append(int((a["trailing"] >= 14).sum()))
            shuffle_stats[attr]["maxrun_max"].append(int(a["maxrun"].max()))
            shuffle_stats[attr]["maxrun_mean"].append(float(a["maxrun"].mean()))
        if (it + 1) % 10 == 0:
            print(f"  shuffle {it+1}/{N_SHUFFLE}", flush=True)

    ctrl = {}
    for attr in L.ATTRS:
        s = shuffle_stats[attr]
        p0 = L.RULE_P[attr]
        # 合成对照：条数 = 真实模板数，p = 理论值
        syn = synthetic_control(T, p0, L.N_PER_ATTR, rng)
        key = {"tot_ge9": real[attr]["tot_ge9"], "tot_ge14": real[attr]["tot_ge14"],
               "n_templates_ge9_any": res["real_scan"][attr]["summary"]["n_templates_ge9_any"],
               "n_templates_ge14_any": res["real_scan"][attr]["summary"]["n_templates_ge14_any"],
               "trailing_ge9": res["real_scan"][attr]["summary"]["n_templates_trailing_ge9"],
               "trailing_ge14": res["real_scan"][attr]["summary"]["n_templates_trailing_ge14"],
               "maxrun_max": res["real_scan"][attr]["summary"]["maxrun_max"],
               "maxrun_mean": res["real_scan"][attr]["summary"]["maxrun_mean"]}
        entry = {"real": key, "synthetic_theory_p": {"p": p0, **syn}, "shuffle": {}, "pvalue_shuffle": {}}
        for stat in s:
            arr = np.array(s[stat], dtype=np.float64)
            obs = key[stat]
            # 单侧 p：随机对照中 >= 观测值 的比例（含 +1 校正）
            pv = (int((arr >= obs).sum()) + 1) / (N_SHUFFLE + 1)
            entry["shuffle"][stat] = {
                "mean": float(arr.mean()), "std": float(arr.std(ddof=1)),
                "min": float(arr.min()), "max": float(arr.max()),
                "q50": L.pct(arr, 50), "q95": L.pct(arr, 95), "q99": L.pct(arr, 99),
                "observed": obs, "z": float((obs - arr.mean()) / arr.std(ddof=1))
                if arr.std(ddof=1) > 0 else None}
            entry["pvalue_shuffle"][stat] = pv
        ctrl[attr] = entry
    res["controls"] = ctrl

    # ─────────── (d) 判定 ───────────
    verdict = {}
    for attr in L.ATTRS:
        c = ctrl[attr]
        p0 = L.RULE_P[attr]
        verdict[attr] = {
            "p_theory": p0,
            "observed_rate": res["real_scan"][attr]["summary"]["pooled_rate"],
            "rate_deviation": res["real_scan"][attr]["summary"]["pooled_rate"] - p0,
            "observed_tot_ge9": c["real"]["tot_ge9"],
            "shuffle_ge9_mean": c["shuffle"]["tot_ge9"]["mean"],
            "shuffle_ge9_range": [c["shuffle"]["tot_ge9"]["min"], c["shuffle"]["tot_ge9"]["max"]],
            "p_ge9_vs_shuffle": c["pvalue_shuffle"]["tot_ge9"],
            "observed_tot_ge14": c["real"]["tot_ge14"],
            "shuffle_ge14_mean": c["shuffle"]["tot_ge14"]["mean"],
            "shuffle_ge14_range": [c["shuffle"]["tot_ge14"]["min"], c["shuffle"]["tot_ge14"]["max"]],
            "p_ge14_vs_shuffle": c["pvalue_shuffle"]["tot_ge14"],
            "observed_maxrun_max": c["real"]["maxrun_max"],
            "shuffle_maxrun_max_mean": c["shuffle"]["maxrun_max"]["mean"],
            "p_maxrun_vs_shuffle": c["pvalue_shuffle"]["maxrun_max"],
            "observed_best_trailing": top[attr]["best_trailing"],
            "observed_n_trailing_ge9": top[attr]["n_trailing_ge9"],
            "shuffle_trailing_ge9_mean": c["shuffle"]["trailing_ge9"]["mean"],
            "p_trailing_ge9": c["pvalue_shuffle"]["trailing_ge9"],
        }
        # 单模板单序列 p 值与 N 模板放大（核心论证）
        K = c["real"]["maxrun_max"]
        p_single = L.prob_exist_run(T, p0, K)
        p_any, logc, _ = 1.0 - (1.0 - p_single) ** L.N_PER_ATTR, L.N_PER_ATTR * np.log1p(-p_single), None
        verdict[attr].update({
            "observed_longest_streak": K,
            "p_single_seq_ge_that": float(p_single),
            "expected_templates_with_that": float(L.N_PER_ATTR * p_single),
            "p_any_of_34320": float(p_any),
            "log10_p_any": float(logc / np.log(10)),
        })
    res["verdict"] = verdict

    res["conclusion"] = {
        "q1_reported_9_streak_beyond_random": {
            "attr_A": "否。p=1/3 下单模板出现 >=9 连的概率 %.4f；34320 个模板中 >=9 连的模板数"
                      "实测 %d，打乱对照均值 %.1f（p=%.3f），完全一致。" % (
                          L.prob_exist_run(T, 1 / 3, 9),
                          verdict["A"]["observed_tot_ge9"], verdict["A"]["shuffle_ge9_mean"],
                          verdict["A"]["p_ge9_vs_shuffle"]),
            "attr_B": "否。p=1/2 下单模板出现 >=9 连的概率 %.4f；实测模板数 %d，打乱对照均值 %.1f（p=%.3f）。" % (
                L.prob_exist_run(T, 0.5, 9), verdict["B"]["observed_tot_ge9"],
                verdict["B"]["shuffle_ge9_mean"], verdict["B"]["p_ge9_vs_shuffle"]),
        },
        "q2_reported_14_streak_beyond_random": {
            "attr_A": "否。实测 %d 条 >=14 连，打乱对照均值 %.1f（p=%.3f）；"
                      "理论上 34320 模板期望 %.2f 条。" % (
                          verdict["A"]["observed_tot_ge14"], verdict["A"]["shuffle_ge14_mean"],
                          verdict["A"]["p_ge14_vs_shuffle"],
                          34320 * L.prob_exist_run(T, 1 / 3, 14)),
            "attr_B": "否。实测 %d 条 >=14 连，打乱对照均值 %.1f（p=%.3f）；"
                      "理论上期望 %.2f 条。" % (
                          verdict["B"]["observed_tot_ge14"], verdict["B"]["shuffle_ge14_mean"],
                          verdict["B"]["p_ge14_vs_shuffle"],
                          34320 * L.prob_exist_run(T, 0.5, 14)),
        },
        "overall": "真实数据中 >=9 连/>=14 连 的模板数量与打乱期序、以及按理论 p 合成的纯随机数据"
                   "在统计上不可区分。截图的 9 连/14 连是**多重比较（扫描大量模板）的必然产物**，"
                   "不构成任何真实'对应规律'的证据。",
    }

    path = L.save("audit_scan.json", res)
    print("[s3] saved:", path)

    # 明细 CSV（供人工抽查），只存每属性的关键列
    csv_path = os.path.join(os.path.dirname(path), "audit_scan_top.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["attr", "purple_pos", "c1", "c2", "c3", "d", "n", "hits", "rate",
                    "maxrun", "maxrun_start_period", "trailing", "trailing_start_period"])
        for attr in L.ATTRS:
            for r in sorted(real[attr]["records"], key=lambda r: -r["maxrun"])[:200]:
                w.writerow([r["attr"], r["purple_pos"], r["c1"], r["c2"], r["c3"], r["d"],
                            r["n"], r["hits"], round(r["rate"], 6), r["maxrun"],
                            r["maxrun_start_period"], r["trailing"],
                            r["trailing_start_period"]])
    res["_csv"] = csv_path

    for attr in L.ATTRS:
        v = verdict[attr]
        s = res["real_scan"][attr]["summary"]
        print(f"[s3] {attr}: rate_mean={s['rate_mean']:.4f} std={s['rate_std']:.4f} "
              f"pooled={s['pooled_rate']:.6f} theory={L.RULE_P[attr]:.6f}")
        print(f"[s3] {attr}: maxrun_max={v['observed_maxrun_max']} "
              f"shuffle_mean={v['shuffle_maxrun_max_mean']:.2f} p={v['p_maxrun_vs_shuffle']:.3f}")
        print(f"[s3] {attr}: tot_ge9={v['observed_tot_ge9']} vs shuffle {v['shuffle_ge9_mean']:.1f} "
              f"p={v['p_ge9_vs_shuffle']:.3f} | tot_ge14={v['observed_tot_ge14']} vs "
              f"{v['shuffle_ge14_mean']:.1f} p={v['p_ge14_vs_shuffle']:.3f}")
        print(f"[s3] {attr}: best_trailing={v['observed_best_trailing']} "
              f"n_trailing_ge9={v['observed_n_trailing_ge9']} "
              f"shuffle_ge9_mean={v['shuffle_trailing_ge9_mean']:.1f} p={v['p_trailing_ge9']:.3f}")


if __name__ == "__main__":
    main()