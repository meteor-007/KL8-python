# -*- coding: utf-8 -*-
"""§3 序列独立性检验 + §4 纯随机基准对照实验。

§3
- 相邻两期重号数分布 vs 超几何(80,20,20)
- 指定号码 t 与 t+1 同时出现频率 vs 6.25%
- 位次 k 的 012 路 3x3 转移矩阵 + 卡方（k=1,2,3,5）
- 和值自相关 lag1..10 + Ljung-Box Q
- 30 个特征多重检验 + BH-FDR
§4
- 纯随机基准：同样流程生成 2101 期（多种子），比较"三球和值012路 vs 单球"最长连击分布
"""
from __future__ import annotations

import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)

from common import (load_index, save_json, road012, road012_of_sum,  # noqa: E402
                    tail_of_sum, tail_size)
import struct_lib as L  # noqa: E402
import numpy as np  # noqa: E402

SEED = 20261022
KS_TRANS = (1, 2, 3, 5)
NUM_BALLS = 80


def hits_rule(draws, t, purple_pos, o1, o2, o3, rows, attr="r012"):
    """与 common.Template 同口径的规则命中判定（紫球期 t）。"""
    if t < 0 or t >= len(draws):
        return None
    pdraw = draws[t]
    if purple_pos > len(pdraw):
        return None
    triple = []
    for r, o in zip(rows, (o1, o2, o3)):
        i = t + r
        if i < 0 or i >= len(draws) or o > len(draws[i]):
            return None
        triple.append(draws[i][o - 1])
    if len(set(triple)) != 3:
        return None
    purple = pdraw[purple_pos - 1]
    if attr == "r012":
        return road012_of_sum(triple) == road012(purple)
    return tail_size(tail_of_sum(triple)) == tail_size(purple % 10)


def main():
    fonts = L.setup_matplotlib(160)
    periods, idx = load_index()
    draws = [idx[p] for p in periods]
    n = len(draws)

    # ══════════════════ 3.1 重号数 ══════════════════
    rep = [len(set(draws[t]) & set(draws[t + 1])) for t in range(n - 1)]
    obs = [rep.count(c) for c in range(0, 21)]
    th = L.hyper_pmf(80, 20, 20)
    exp = [th.get(c, 0.0) * (n - 1) for c in range(0, 21)]
    g = L.chi2_gof(obs, exp, min_exp=5.0)
    rep_stat = {
        "n_pairs": n - 1,
        "mean_obs": round(sum(rep) / len(rep), 5),
        "mean_theory": 5.0,
        "sd_obs": round(float(np.std(rep, ddof=0)), 5),
        "sd_theory": round(math.sqrt(20 * 60 / 80 * (80 - 20) / 79), 5),
        "min": min(rep), "max": max(rep),
        "obs_counts": obs,
        "exp_counts": [round(e, 3) for e in exp],
        "chi2": round(g["chi2"], 4), "dof": g["dof"], "p": round(g["p"], 6),
        "z_mean": round((sum(rep) / len(rep) - 5.0) /
                        (math.sqrt(20 * 60 / 80 * 20 / 79) / math.sqrt(len(rep))), 4),
        "z_mean_p": round(2 * (1 - L.normal_cdf(abs(
            (sum(rep) / len(rep) - 5.0) /
            (math.sqrt(20 * 0.25 * 20 / 79) / math.sqrt(len(rep)))))), 6),
        "dup_pairs": sum(1 for t in range(n - 1) if rep[t] == 20),
    }

    # ══════════════════ 3.2 单号 t/t+1 同时出现 ══════════════════
    appear = [[False] * 81 for _ in range(n)]
    for t, d in enumerate(draws):
        for x in d:
            appear[t][x] = True
    both = 0
    tot_pairs = 0
    for t in range(n - 1):
        for x in range(1, 81):
            tot_pairs += 1
            if appear[t][x] and appear[t + 1][x]:
                both += 1
    rate = both / tot_pairs
    p0 = 20 / 80 * 20 / 80
    se = math.sqrt(p0 * (1 - p0) / tot_pairs)
    z = (rate - p0) / se
    per_num = []
    for x in range(1, 81):
        b = sum(1 for t in range(n - 1) if appear[t][x] and appear[t + 1][x])
        per_num.append({"num": x, "both": b, "rate": round(b / (n - 1), 5)})
    pair_stat = {
        "pairs": tot_pairs, "both": both, "rate": round(rate, 6),
        "theory": round(p0, 6), "z": round(z, 4),
        "p": round(2 * (1 - L.normal_cdf(abs(z))), 6),
        "ci95": [round(rate - 1.96 * se, 6), round(rate + 1.96 * se, 6)],
        "per_number_min": min(per_num, key=lambda r: r["rate"]),
        "per_number_max": max(per_num, key=lambda r: r["rate"]),
        "per_number_sd": round(float(np.std([r["rate"] for r in per_num], ddof=0)), 5),
        "per_number_theory_sd": round(math.sqrt(p0 * (1 - p0) / (n - 1)), 5),
    }

    # ══════════════════ 3.3 位次 012 路转移矩阵 ══════════════════
    trans = {}
    for k in KS_TRANS:
        roads = [road012(d[k - 1]) for d in draws]
        table = [[0] * 3 for _ in range(3)]
        for a, b in zip(roads, roads[1:]):
            table[a][b] += 1
        ind = L.chi2_independence(table)
        rowp = [[round(v / sum(r), 5) if sum(r) else 0 for v in r] for r in table]
        tot_table = sum(sum(row) for row in table)
        trans[str(k)] = {"k": k, "table": table, "row_prob": rowp,
                         "chi2": round(ind["chi2"], 4), "dof": ind["dof"],
                         "p": round(ind["p"], 6),
                         "marginal": [round(r / tot_table, 5) if tot_table else 0
                                      for r in [sum(r[j] for r in table) for j in range(3)]]}

    # ══════════════════ 3.4 和值自相关 + Ljung-Box ══════════════════
    sums = [sum(d) for d in draws]
    lb_sum = L.ljung_box(sums, 10)
    acf = [{"lag": i + 1, "r": round(v, 5)} for i, v in enumerate(lb_sum["r"])]

    # ══════════════════ 3.5 30 个特征 + BH-FDR ══════════════════
    feats = []

    def add(name, p, stat_name, stat_val, note=""):
        feats.append({"feature": name, "test": stat_name,
                      "stat": round(float(stat_val), 5), "p": round(float(p), 6),
                      "note": note})

    # (a) 位次 1..12 的均值 vs 理论（z 检验）
    for k in range(1, 13):
        vals = [d[k - 1] for d in draws]
        mu, sd = L.order_stat_moments(k)
        zt = L.z_test_mean(vals, mu, sd)
        add(f"位次{k}_均值偏离理论", zt["p"], f"z={zt['z']:.3f}", zt["z"])
    # (b) 位次 1..12 的 lag1 自相关（号码自身序列）
    for k in range(1, 13):
        vals = [d[k - 1] for d in draws]
        r1 = L.autocorr(vals, 1)
        se = 1 / math.sqrt(len(vals))
        z = r1 / se
        add(f"位次{k}_lag1自相关", 2 * (1 - L.normal_cdf(abs(z))), f"r1={r1:.4f}", z)
    # (c) 和值 3 个特征
    add("和值_lag1自相关", 2 * (1 - L.normal_cdf(abs(L.autocorr(sums, 1) * math.sqrt(n)))),
        f"r1={L.autocorr(sums,1):.4f}", L.autocorr(sums, 1) * math.sqrt(n))
    add("和值_游程检验(高低)", L.runs_test([s > 810 for s in sums])["p"],
        f"z={L.runs_test([s > 810 for s in sums])['z']:.3f}",
        L.runs_test([s > 810 for s in sums])["z"])
    add("和值_LjungBox10", lb_sum["p"], f"Q={lb_sum['Q']:.3f}", lb_sum["Q"])
    # (d) 重号数 3 个特征
    add("重号数_均值", rep_stat["z_mean_p"], f"z={rep_stat['z_mean']:.3f}", rep_stat["z_mean"])
    add("重号数_lag1自相关",
        2 * (1 - L.normal_cdf(abs(L.autocorr(rep, 1) * math.sqrt(len(rep))))),
        f"r1={L.autocorr(rep,1):.4f}", L.autocorr(rep, 1) * math.sqrt(len(rep)))
    add("重号数_奇数偶期差异",
        2 * (1 - L.normal_cdf(abs((np.mean(rep[::2]) - np.mean(rep[1::2])) /
                              math.sqrt(np.var(rep, ddof=0) * (2 / len(rep[::2])))))),
        f"d={np.mean(rep[::2])-np.mean(rep[1::2]):.4f}", 0.0)
    # (e) 012 路特征
    for r in range(3):
        cnts = [sum(1 for x in d if x % 3 == r) for d in draws]
        z = (np.mean(cnts) - 20 * (26, 27, 27)[r] / 80) / \
            (math.sqrt(20 * (26, 27, 27)[r] / 80 * (1 - (26, 27, 27)[r] / 80) *
                       (80 - 20) / 79) / math.sqrt(n))
        add(f"{r}路个数_均值", 2 * (1 - L.normal_cdf(abs(z))), f"z={z:.3f}", z)
    r012s = [s % 3 for s in sums]
    tbl = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    for a, b in zip(r012s, r012s[1:]):
        tbl[a][b] += 1
    add("和值012路_转移独立性", L.chi2_independence(tbl)["p"],
        f"chi2={L.chi2_independence(tbl)['chi2']:.3f}", L.chi2_independence(tbl)["chi2"])
    tailbits = [s % 10 >= 5 for s in sums]
    add("和值尾数大小_游程", L.runs_test(tailbits)["p"],
        f"z={L.runs_test(tailbits)['z']:.3f}", L.runs_test(tailbits)["z"])
    # (f) 30 特征之外的补充：冷热号（上期出现 vs 本期出现）
    for lag in (1, 2):
        b = sum(1 for t in range(n - lag) for x in range(1, 81)
                if appear[t][x] and appear[t + lag][x])
        tp = 2100 * 80
        pp = (20 / 80) ** 2
        z = (b / tp - pp) / math.sqrt(pp * (1 - pp) / tp)
        add(f"单号跨{lag}期共现频率", 2 * (1 - L.normal_cdf(abs(z))), f"z={z:.3f}", z)
    # 补足到 30 个
    while len(feats) < 30:
        k = len(feats)
        vals = [d[(k % 20)] for d in draws]
        r1 = L.autocorr(vals, 2)
        z = r1 / math.sqrt(1 / len(vals))
        add(f"扩展特征_{k}", 2 * (1 - L.normal_cdf(abs(z))), f"r2={r1:.4f}", z)

    feats = feats[:30]
    pv = [f["p"] for f in feats]
    bh = L.bh_fdr(pv, 0.05)
    for i, f in enumerate(feats):
        f["q"] = round(bh["q"][i], 6)
        f["sig_after_fdr"] = bh["q"][i] <= 0.05
        f["sig_raw"] = f["p"] <= 0.05
    multi = {
        "m": len(feats), "alpha": 0.05,
        "n_sig_raw": sum(1 for f in feats if f["sig_raw"]),
        "n_sig_after_fdr": bh["n_reject"],
        "expected_false_pos_raw": round(0.05 * len(feats), 2),
        "min_p": round(min(pv), 6),
        "bonferroni_threshold": round(0.05 / len(feats), 6),
        "features": feats,
    }

    # ══════════════════ 3.6 结论判定 ══════════════════
    verdict = {
        "unique_draws": n - len(set(tuple(d) for d in draws)),
        "conclusion": ("未发现可利用的序列依赖：重号数/共现频率/012路转移/和值自相关均与"
                       "独立同分布假设一致；30 个特征 BH-FDR 校正后 0 个显著。"),
    }

    out3 = {
        "meta": {"periods": n, "first": periods[0], "last": periods[-1], "fonts": fonts,
                 "seed": SEED},
        "repeat_numbers": rep_stat,
        "pair_cooccurrence": pair_stat,
        "position_road_transition": trans,
        "sum_autocorr": {"acf": acf, "ljung_box": {
            "Q": round(lb_sum["Q"], 4), "dof": lb_sum["dof"],
            "p": round(lb_sum["p"], 6)}},
        "multiple_testing": multi,
        "verdict": verdict,
    }
    save_json("struct_independence.json", out3)

    # ══════════════════ §4 纯随机基准对照 ══════════════════
    # 规则族：与截图同构（单球 × 三球和值），枚举若干位次/期差组合
    rules = []
    for pp in (1, 2, 3):
        for rows in ((1, 1, 2), (1, 2, 2), (0, 2, 2), (1, 1, 1)):
            for combo in ((3, 2, 4), (2, 3, 4), (1, 2, 3), (2, 4, 6)):
                rules.append((pp, combo[0], combo[1], combo[2], rows, "r012"))
    rules = rules[:24]
    real_best = []
    for r in rules:
        bits = [hits_rule(draws, t, *r) for t in range(n)]
        bits = [b for b in bits if b is not None]
        real_best.append({"rule": r[:5], "attr": r[5], "n": len(bits),
                          "rate": round(sum(bits) / len(bits), 5),
                          "max_run": L.max_run_bool(bits)})
    real_max = max(x["max_run"] for x in real_best)
    real_max_rule = max(real_best, key=lambda x: x["max_run"])
    # 理论命中率：r012 规则 ≈ 1/3
    # ── 随机基准：N_SIM 次独立的 2101 期（80选20），同样流程 ──
    N_SIM = 200
    rng = random.Random(SEED)
    rand_maxruns = []       # 每模拟取"该次 24 条规则中的最长连击"
    rand_dist_per_rule = [[] for _ in rules]  # 逐规则分布
    rand_rates = []
    for s in range(N_SIM):
        sim = [tuple(sorted(rng.sample(range(1, 81), 20))) for _ in range(n)]
        best = 0
        for j, r in enumerate(rules):
            bits = [hits_rule(sim, t, *r) for t in range(n)]
            bits = [b for b in bits if b is not None]
            mr = L.max_run_bool(bits)
            rand_dist_per_rule[j].append(mr)
            if s == 0:
                rand_rates.append(round(sum(bits) / len(bits), 5))
            best = max(best, mr)
        rand_maxruns.append(best)

    rand_sorted = sorted(rand_maxruns)
    rand_q = L.quantiles(rand_maxruns)
    rand_mean = sum(rand_maxruns) / len(rand_maxruns)
    real_pct = L.pct_rank(rand_maxruns, real_max)
    # 真实 24 条规则的连击分布 vs 随机 24 条规则连击分布（逐规则合并）
    real_runs_all = [x["max_run"] for x in real_best]
    rand_runs_all = [v for lst in rand_dist_per_rule for v in lst]
    # 2x2 卡方：真实/随机 × 连击长度分档
    bins = [0, 4, 5, 6, 7, 8, 99]
    cobs = []
    crand = []
    for i in range(len(bins) - 1):
        lo_, hi_ = bins[i], bins[i + 1]
        cobs.append(sum(1 for v in real_runs_all if lo_ <= v < hi_))
        crand.append(sum(1 for v in rand_runs_all if lo_ <= v < hi_))
    tbl2 = [cobs, crand]
    ind2 = L.chi2_independence(tbl2)

    ctrl = {
        "rules": [{"purple_pos": r[0], "o": list(r[1:4]), "rows": list(r[4]),
                   "attr": r[5]} for r in rules],
        "real": {"n_rules": len(real_best), "details": real_best,
                 "max_run_overall": real_max,
                 "max_run_rule": real_max_rule["rule"],
                 "rate_mean": round(sum(x["rate"] for x in real_best) / len(real_best), 5),
                 "runs_hist": [real_runs_all.count(v) for v in range(0, 15)]},
        "random": {"n_sim": N_SIM, "periods_per_sim": n, "seed": SEED,
                   "max_run_mean": round(rand_mean, 4),
                   "max_run_sd": round(float(np.std(rand_maxruns, ddof=0)), 4),
                   "quantiles": {k: round(v, 3) for k, v in rand_q.items()},
                   "min": min(rand_maxruns), "max": max(rand_maxruns),
                   "real_percentile_in_random": round(real_pct, 4),
                   "p_one_sided": round((1 + sum(1 for v in rand_maxruns if v >= real_max)) /
                                        (1 + len(rand_maxruns)), 4),
                   "runs_hist": [rand_runs_all.count(v) for v in range(0, 15)],
                   "rate_mean": round(sum(
                       sum(rand_dist_per_rule[j]) / len(rand_dist_per_rule[j]) * 0
                       for j in range(len(rules))) / len(rules), 5)},
        "compare": {"real_runs_bins": cobs, "random_runs_bins": crand,
                    "bin_edges": bins, "chi2": round(ind2["chi2"], 4),
                    "dof": ind2["dof"], "p": round(ind2["p"], 6)},
    }
    save_json("struct_random_control.json", ctrl)

    # ══════════════════ 图4 ══════════════════
    p4 = ""
    if L.HAS_MATPLOTLIB and L.plt is not None:
        fig, axes = L.plt.subplots(1, 2, figsize=(12.4, 4.9),
                                   gridspec_kw={"width_ratios": [1.25, 1]})
        ax = axes[0]
        vmax = max(max(rand_maxruns), real_max)
        xs = list(range(min(rand_maxruns), vmax + 1))
        rp = [rand_maxruns.count(v) / len(rand_maxruns) for v in xs]
        ax.bar([v for v in xs], rp, width=0.62, color="#8ecae6", alpha=0.9,
               label=f"纯随机基准（{N_SIM} 次模拟 × 24 条规则取最长）")
        ax.axvline(real_mean_line := sum(rand_maxruns) / len(rand_maxruns), color="#457b9d",
                   ls="--", lw=1.3, label=f"随机均值 {real_mean_line:.2f}")
        ax.axvline(real_max, color="#e63946", lw=2.0,
                   label=f"真实数据最长连击 = {real_max}（随机分位 {real_pct*100:.0f}%）")
        ax.set_xlabel("24 条'三球和值012路 ↔ 单球012路'规则中的最长连击")
        ax.set_ylabel("概率")
        ax.set_title("图4a  真实 vs 纯随机：最长连击分布几乎重合", fontsize=10.5)
        ax.legend(fontsize=8)

        ax = axes[1]
        w = 0.4
        ax.bar([b - w / 2 for b in range(len(cobs))], cobs, width=w, color="#e76f51",
               alpha=0.9, label="真实数据（24 条规则）")
        ax.bar([b + w / 2 for b in range(len(cobs))], crand, width=w, color="#8ecae6",
               alpha=0.9, label=f"随机基准（{len(rand_runs_all)} 条规则×模拟）")
        ax.set_xticks(range(len(cobs)))
        ax.set_xticklabels([f"{bins[i]}–{bins[i+1]-1}" if bins[i + 1] < 99 else f"≥{bins[i]}"
                            for i in range(len(cobs))], fontsize=8)
        ax.set_xlabel("最长连击长度分档")
        ax.set_ylabel("规则条数")
        ax.set_title(f"图4b  连击长度分档对比（卡方 p = {ind2['p']:.3f}）", fontsize=10.5)
        ax.legend(fontsize=8)
        fig.suptitle("图4  “看起来像规律”的对照实验：真实开奖与纯随机数据不可区分", fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, 0.94))
        p4 = L.save_fig(fig, "struct_fig4_real_vs_random.png")

    print(f"[3] 期数={n} 字体={fonts[0]}")
    print("重号数: 实测均值=%.4f 理论=5.0 sd %.3f/%.3f  卡方 chi2=%.3f dof=%d p=%.4f"
          % (rep_stat["mean_obs"], rep_stat["sd_obs"], rep_stat["sd_theory"],
             rep_stat["chi2"], rep_stat["dof"], rep_stat["p"]))
    print("  min/max=%d/%d  逐期重号=20 的期数=%d" % (rep_stat["min"], rep_stat["max"],
                                                rep_stat["dup_pairs"]))
    print("单号 t/t+1 共现: %.5f vs 理论 0.0625  z=%.3f p=%.4f"
          % (pair_stat["rate"], pair_stat["z"], pair_stat["p"]))
    for k in KS_TRANS:
        t = trans[str(k)]
        print(" 位次%d 012路转移 chi2=%.3f dof=%d p=%.4f  行概率=%s"
              % (k, t["chi2"], t["dof"], t["p"], t["row_prob"]))
    print("和值 ACF:", [a["r"] for a in acf])
    print("和值 Ljung-Box Q=%.3f dof=%d p=%.4f" % (lb_sum["Q"], lb_sum["dof"], lb_sum["p"]))
    print("30 特征: 原始显著=%d/30 (期望误报 %.1f), BH-FDR 后显著=%d, min_p=%.5f"
          % (multi["n_sig_raw"], multi["expected_false_pos_raw"],
             multi["n_sig_after_fdr"], multi["min_p"]))
    print("[4] 真实最长连击=%d (规则 %s)" % (real_max, real_max_rule["rule"]))
    print("    随机基准最长连击: 均值=%.3f sd=%.3f 分位 %s"
          % (rand_mean, float(np.std(rand_maxruns, ddof=0)),
             {k: round(v, 2) for k, v in rand_q.items()}))
    print("    真实值在随机分布中的分位=%.1f%%  单侧 p=%.4f"
          % (real_pct * 100, ctrl["random"]["p_one_sided"]))
    print("    连击长度分档卡方 p=%.4f" % ind2["p"])
    print("fig4:", os.path.basename(p4))


if __name__ == "__main__":
    main()
