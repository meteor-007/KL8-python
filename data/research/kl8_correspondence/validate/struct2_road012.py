# -*- coding: utf-8 -*-
"""§2 012 路的真实结构。

- 每期 20 个号中 0/1/2 路个数的分布 vs 多元超几何理论（边缘 + 联合卡方）
- 单球 012 路总体比例（1..80 中 0路26 / 1路27 / 2路27）
- 每期和值分布（精确 DP 子集和）与和值 012 路、尾数分布（卡方 p）
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)

from common import load_index, save_json, road012, road012_of_sum, tail_of_sum  # noqa: E402
import struct_lib as L  # noqa: E402
import numpy as np  # noqa: E402

C0, C1, C2 = 26, 27, 27  # 1..80 中 0/1/2 路的号码个数


def main():
    fonts = L.setup_matplotlib(160)
    periods, idx = load_index()
    draws = [idx[p] for p in periods]
    n = len(draws)
    assert C0 + C1 + C2 == 80 and len([x for x in range(1, 81) if x % 3 == 0]) == 26

    # ── 2.1 每期 0/1/2 路个数 ──
    per = []
    for d in draws:
        c = [0, 0, 0]
        for x in d:
            c[x % 3] += 1
        per.append(tuple(c))
    arr = np.array(per)
    hist = {}
    for c0 in range(0, 21):
        row = []
        for c1 in range(0, 21 - c0):
            c2 = 20 - c0 - c1
            p = (L._C(C0, c0) * L._C(C1, c1) * L._C(C2, c2)) / L._C(80, 20)
            row.append(((c0, c1, c2), p))
        hist[c0] = row

    def mv_p(c0, c1, c2):
        return (L._C(C0, c0) * L._C(C1, c1) * L._C(C2, c2)) / L._C(80, 20)

    obs_counter = {}
    for t in per:
        obs_counter[t] = obs_counter.get(t, 0) + 1

    # 联合卡方：把 (c0,c1,c2) 按期望 >= 4 合并
    cells = []
    for c0 in range(0, 21):
        for c1 in range(0, 21 - c0):
            c2 = 20 - c0 - c1
            cells.append([(c0, c1, c2), obs_counter.get((c0, c1, c2), 0), mv_p(c0, c1, c2) * n])
    # 按期望从大到小合并尾部（保持可加性）
    cells.sort(key=lambda r: -r[2])
    merged, acc_o, acc_e, group = [], 0, 0.0, []
    for key, o, e in cells:
        group.append(key)
        acc_o += o
        acc_e += e
        if acc_e >= 4.0:
            merged.append([acc_o, acc_e, group])
            acc_o = acc_e = 0
            group = []
    if group:
        merged[-1][0] += acc_o
        merged[-1][1] += acc_e
    chi2_joint = sum((o - e) ** 2 / e for o, e, _ in merged if e > 0)
    dof_joint = len(merged) - 1
    joint = {"chi2": chi2_joint, "dof": dof_joint, "n_cells": len(merged),
             "p": L.chi2_sf(chi2_joint, dof_joint)}

    marg = {}
    for r in (0, 1, 2):
        obs = [int((arr[:, r] == v).sum()) for v in range(0, 21)]
        th = L.hyper_pmf(80, (C0, C1, C2)[r], 20)
        exp = [th.get(v, 0.0) * n for v in range(0, 21)]
        g = L.chi2_gof(obs, exp, min_exp=5.0)
        marg[str(r)] = {
            "mean_obs": round(float(arr[:, r].mean()), 4),
            "mean_theory": round(20 * (C0, C1, C2)[r] / 80, 4),
            "sd_obs": round(float(arr[:, r].std(ddof=0)), 4),
            "chi2": round(g["chi2"], 4), "dof": g["dof"],
            "p": round(g["p"], 6), "n_cells": g["n_cells"],
            "obs_counts": obs, "exp_counts": [round(e, 3) for e in exp],
        }

    # ── 2.2 单球 012 路总体比例 ──
    flat = [x for d in draws for x in d]
    road_cnt = [0, 0, 0]
    for x in flat:
        road_cnt[x % 3] += 1
    tot = len(flat)
    exp_cnt = [tot * c / 80 for c in (C0, C1, C2)]
    g = L.chi2_gof(road_cnt, exp_cnt, min_exp=5.0)
    ball012 = {
        "total_balls": tot,
        "obs_counts": road_cnt,
        "obs_prop": [round(c / tot, 5) for c in road_cnt],
        "theory_prop": [round(c / 80, 5) for c in (C0, C1, C2)],
        "exp_counts": [round(e, 2) for e in exp_cnt],
        "chi2": round(g["chi2"], 4), "dof": g["dof"], "p": round(g["p"], 6),
    }

    # 每个号的频次均匀性（80 号，df=79）
    cnt80 = [0] * 80
    for x in flat:
        cnt80[x - 1] += 1
    exp80 = tot / 80
    chi2_80 = sum((c - exp80) ** 2 / exp80 for c in cnt80)
    ball_uniform = {
        "chi2": round(chi2_80, 4), "dof": 79, "p": round(L.chi2_sf(chi2_80, 79), 6),
        "min": min(cnt80), "max": max(cnt80), "expected": round(exp80, 2),
        "cv": round(float(np.std(cnt80, ddof=0) / np.mean(cnt80)), 5),
    }

    # ── 2.3 和值分布（精确 DP） ──
    pmf = L.subset_sum_pmf(80, 20)
    tot_subsets = L._C(80, 20)
    sums = [sum(d) for d in draws]
    sarr = np.array(sums, dtype=float)
    mu_th = 20 * 40.5
    sd_th = math.sqrt(20 * 81 * 60 / 12)
    zt = L.z_test_mean(sums, mu_th, sd_th)
    # 分组卡方（宽 50 的分箱，期望>=5）
    lo, hi = 20 * 41 // 2, 810  # 实际范围用实测 min/max 扩展
    smin, smax = min(sums), max(sums)
    width = 50
    b_lo = (min(400, smin) // width) * width
    b_hi = ((max(1220, smax) // width) + 1) * width
    obs_b, exp_b = [], []
    for b in range(b_lo, b_hi, width):
        o = sum(1 for s in sums if b <= s < b + width)
        e = sum(pmf[s] for s in range(max(b, 20), min(b + width, 20 * 80 + 1))) / tot_subsets * n
        obs_b.append(o)
        exp_b.append(e)
    gs = L.chi2_gof(obs_b, exp_b, min_exp=5.0)
    sum_stat = {
        "n": n, "mean": round(float(sarr.mean()), 4), "sd": round(float(sarr.std(ddof=0)), 4),
        "theory_mean": mu_th, "theory_sd": round(sd_th, 4),
        "min": int(sarr.min()), "max": int(sarr.max()),
        "p5_p95": [float(np.percentile(sarr, 5)), float(np.percentile(sarr, 95))],
        "z": round(zt["z"], 4), "p_mean": round(zt["p"], 6),
        "chi2_binned": round(gs["chi2"], 4), "dof": gs["dof"], "p_dist": round(gs["p"], 6),
        "bin_width": width,
    }

    # ── 2.4 和值 012 路 与 尾数 ──
    r012 = [road012_of_sum(d) for d in draws]
    rc = [r012.count(v) for v in range(3)]
    # 理论：由精确 pmf 推
    th_r = [0.0, 0.0, 0.0]
    for s in range(20, 20 * 80 + 1):
        if pmf[s]:
            th_r[s % 3] += pmf[s] / tot_subsets
    g_r = L.chi2_gof(rc, [p * n for p in th_r], min_exp=5.0)
    sum_road = {
        "obs_counts": rc, "obs_prop": [round(c / n, 5) for c in rc],
        "theory_prop": [round(p, 5) for p in th_r],
        "chi2": round(g_r["chi2"], 4), "dof": g_r["dof"], "p": round(g_r["p"], 6),
    }

    tails = [tail_of_sum(d) for d in draws]
    tc = [tails.count(v) for v in range(10)]
    th_t = [0.0] * 10
    for s in range(20, 20 * 80 + 1):
        if pmf[s]:
            th_t[s % 10] += pmf[s] / tot_subsets
    g_t = L.chi2_gof(tc, [p * n for p in th_t], min_exp=5.0)
    # 尾数 vs 理论（df=9）与 vs 完全均匀 1/10（df=9）
    chi2_u = sum((c - n / 10) ** 2 / (n / 10) for c in tc)
    sum_tail = {
        "obs_counts": tc, "obs_prop": [round(c / n, 4) for c in tc],
        "theory_prop": [round(p, 4) for p in th_t],
        "uniform_prop": 0.1,
        "chi2_vs_theory": round(g_t["chi2"], 4), "dof": g_t["dof"],
        "p_vs_theory": round(g_t["p"], 6),
        "chi2_vs_uniform": round(chi2_u, 4),
        "p_vs_uniform": round(L.chi2_sf(chi2_u, 9), 6),
        "max_dev_from_uniform": round(max(abs(c - n / 10) for c in tc) / n, 4),
    }
    # 尾数大小（0-4 小 / 5-9 大）
    small = sum(1 for t in tails if t < 5)
    g_ts = {"small": small, "large": n - small,
            "p": round(2 * (1 - L.normal_cdf(abs((small - n / 2) / math.sqrt(n * 0.25)))), 6),
            "z": round((small - n / 2) / math.sqrt(n * 0.25), 4)}

    out = {
        "meta": {"periods": n, "fonts": fonts, "road_sizes": [C0, C1, C2]},
        "per_draw_counts": {
            "joint_chi2": {k: (round(v, 6) if isinstance(v, float) else v)
                           for k, v in joint.items()},
            "marginals": marg,
            "mean_counts": [round(float(arr[:, r].mean()), 4) for r in range(3)],
        },
        "ball_012": ball012,
        "ball_uniform_80": ball_uniform,
        "sum_stats": sum_stat,
        "sum_road012": sum_road,
        "sum_tail": sum_tail,
        "sum_tail_size": g_ts,
    }
    save_json("struct_road012.json", out)

    # ══════════════ 图3：每期 0/1/2 路个数堆叠面积 ══════════════
    fig, axes = L.plt.subplots(2, 1, figsize=(12, 8.2),
                               gridspec_kw={"height_ratios": [1.15, 1]})
    ax = axes[0]
    x = np.arange(n)
    ax.stackplot(x, arr[:, 0], arr[:, 1], arr[:, 2],
                 labels=["0路个数", "1路个数", "2路个数"],
                 colors=["#8ecae6", "#ffb703", "#fb8500"], alpha=0.9)
    for r, c in ((0, "#023047"), (1, "#000000"), (2, "#6a4c3b")):
        ax.axhline(20 * (C0, C1, C2)[r] / 80, color=c, ls="--", lw=1.1,
                   label=f"{r}路理论期望 {20*(C0,C1,C2)[r]/80:.2f}")
    ax.set_xlim(0, n - 1)
    ax.set_ylim(0, 20)
    ax.set_xlabel("期号序号（2020001 → 2026280，共 2101 期）")
    ax.set_ylabel("每期个数")
    ax.set_title("图3a  每期 0/1/2 路个数（堆叠面积）：围绕 6.5/6.75/6.75 无趋势漂移",
                 fontsize=11)
    ax.legend(fontsize=8, ncol=6, loc="lower center", framealpha=0.92)

    ax2 = axes[1]
    width = 0.27
    for r, col in ((0, "#8ecae6"), (1, "#ffb703"), (2, "#fb8500")):
        th = L.hyper_pmf(80, (C0, C1, C2)[r], 20)
        ks = list(range(0, 21))
        obs_p = [float((arr[:, r] == v).mean()) for v in ks]
        th_p = [th.get(v, 0.0) for v in ks]
        ax2.bar(np.array(ks) + (r - 1) * width, obs_p, width=width, color=col,
                alpha=0.85, label=f"{r}路 实测")
        ax2.plot(ks, th_p, color=("#023047" if r == 0 else ("#6a4c3b" if r == 1 else "#9b2226")),
                 ls="--", lw=1.3, marker=".", ms=7, label=f"{r}路 超几何理论")
    ax2.set_xlabel("某一路在当期 20 个号中的个数")
    ax2.set_ylabel("概率 / 频率")
    ax2.set_title("图3b  0/1/2 路个数的实测分布 vs 超几何理论（80,26/27/27,20）", fontsize=11)
    ax2.legend(fontsize=8, ncol=3)
    ax2.set_xlim(-0.7, 14.7)
    fig.tight_layout()
    p3 = L.save_fig(fig, "struct_fig3_road012_timeseries.png")

    print(f"[2] 期数={n} 字体={fonts[0]}")
    print("每期0/1/2路个数 均值:", [round(float(arr[:, r].mean()), 3) for r in range(3)],
          "理论:", [round(20 * c / 80, 3) for c in (C0, C1, C2)])
    print(" 联合卡方 chi2=%.3f dof=%d p=%.4f" % (chi2_joint, dof_joint, joint["p"]))
    for r in (0, 1, 2):
        m = marg[str(r)]
        print(f" 路{r} 边缘 chi2={m['chi2']:.2f} dof={m['dof']} p={m['p']:.4f} "
              f"均值 {m['mean_obs']:.3f}/{m['mean_theory']:.3f} sd {m['sd_obs']:.3f}")
    print("单球012占比:", [round(c / tot, 4) for c in road_cnt], "理论:",
          [round(c / 80, 4) for c in (C0, C1, C2)],
          "chi2=%.3f p=%.4f" % (g["chi2"], g["p"]))
    print("80号频次均匀性 chi2=%.2f dof=79 p=%.4f min/max=%d/%d (期望%.1f)"
          % (chi2_80, ball_uniform["p"], ball_uniform["min"], ball_uniform["max"], exp80))
    print("和值 mean=%.2f sd=%.2f (理论 %.1f/%.1f) min/max=%d/%d p_mean=%.4f p_dist=%.4f"
          % (sarr.mean(), sarr.std(), mu_th, sd_th, sarr.min(), sarr.max(),
             zt["p"], gs["p"]))
    print("和值012路:", rc, "p=%.4f" % g_r["p"], "| 尾数:", tc, "p_theory=%.4f p_uniform=%.4f"
          % (g_t["p"], sum_tail["p_vs_uniform"]))
    print("尾数大小 小=%d 大=%d z=%.3f p=%.4f" % (g_ts["small"], g_ts["large"],
                                              g_ts["z"], g_ts["p"]))
    print("fig:", os.path.basename(p3))


if __name__ == "__main__":
    main()
