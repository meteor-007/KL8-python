# -*- coding: utf-8 -*-
"""§1 位次（顺序统计量）的真实分布。

对 k=1..12：实测均值/标准差/min-max/常用区间、经验 CDF 关键点，
并与精确超几何顺序统计量理论分布、与"均匀随机一个号"(均值 40.5) 对比。
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)

from common import load_index, save_json, save_text  # noqa: E402
import struct_lib as L  # noqa: E402
import numpy as np  # noqa: E402

KS = list(range(1, 13))
UNIF_MEAN = 40.5
# 1..80 均匀分布的标准差
UNIF_SD = math.sqrt((80 ** 2 - 1) / 12)


def main():
    fonts = L.setup_matplotlib(160)
    periods, idx = load_index()
    draws = [idx[p] for p in periods]
    n = len(draws)

    # ── 1.1 每个位次的实测统计量 ──
    rows = []
    for k in KS:
        vals = [d[k - 1] for d in draws]
        arr = np.array(vals, dtype=float)
        mu_th, sd_th = L.order_stat_moments(k)
        c10 = L.order_stat_cdf(k, 10)
        c20 = L.order_stat_cdf(k, 20)
        c30 = L.order_stat_cdf(k, 30)
        c40 = L.order_stat_cdf(k, 40)
        c50 = L.order_stat_cdf(k, 50)
        # 中心 80% 实测区间
        lo80, hi80 = float(np.percentile(arr, 10)), float(np.percentile(arr, 90))
        # 与理论分布的卡方
        pmf = L.order_stat_pmf(k)
        counts, exps = [], []
        for x in range(1, 81):
            counts.append(vals.count(x))
            exps.append(pmf[x - 1] * n)
        gof = L.chi2_gof(counts, exps, min_exp=5.0)
        # 与理论均值的 z 检验（已知理论 sd）
        zt = L.z_test_mean(vals, mu_th, sd_th)
        # 与"均匀一个号"的对比：效应量
        d = (arr.mean() - UNIF_MEAN) / UNIF_SD
        rows.append({
            "k": k,
            "n": n,
            "mean": round(float(arr.mean()), 4),
            "sd": round(float(arr.std(ddof=0)), 4),
            "sd_sample": round(float(arr.std(ddof=1)), 4),
            "min": int(arr.min()),
            "max": int(arr.max()),
            "median": float(np.median(arr)),
            "p10_p90": [lo80, hi80],
            "mode": int(np.bincount(np.array(vals), minlength=81)[1:].argmax() + 1),
            "theory_mean": round(mu_th, 4),
            "theory_sd": round(sd_th, 4),
            "ecdf_le10": round(sum(1 for v in vals if v <= 10) / n, 4),
            "ecdf_le20": round(sum(1 for v in vals if v <= 20) / n, 4),
            "ecdf_le30": round(sum(1 for v in vals if v <= 30) / n, 4),
            "ecdf_le40": round(sum(1 for v in vals if v <= 40) / n, 4),
            "ecdf_le50": round(sum(1 for v in vals if v <= 50) / n, 4),
            "theory_ecdf_le10": round(c10, 4),
            "theory_ecdf_le20": round(c20, 4),
            "theory_ecdf_le30": round(c30, 4),
            "theory_ecdf_le40": round(c40, 4),
            "theory_ecdf_le50": round(c50, 4),
            "band_1_10": round(sum(1 for v in vals if 1 <= v <= 10) / n, 4),
            "band_11_20": round(sum(1 for v in vals if 11 <= v <= 20) / n, 4),
            "band_21_30": round(sum(1 for v in vals if 21 <= v <= 30) / n, 4),
            "band_31_40": round(sum(1 for v in vals if 31 <= v <= 40) / n, 4),
            "band_41_50": round(sum(1 for v in vals if 41 <= v <= 50) / n, 4),
            "band_51_60": round(sum(1 for v in vals if 51 <= v <= 60) / n, 4),
            "band_61_70": round(sum(1 for v in vals if 61 <= v <= 70) / n, 4),
            "band_71_80": round(sum(1 for v in vals if 71 <= v <= 80) / n, 4),
            "offset_vs_uniform_mean": round(float(arr.mean()) - UNIF_MEAN, 4),
            "cohen_d_vs_uniform": round(float(d), 4),
            "z_vs_theory_mean": round(zt["z"], 4),
            "p_vs_theory_mean": round(zt["p"], 6),
            "chi2_vs_theory": round(gof["chi2"], 4),
            "dof": gof["dof"],
            "p_vs_theory": round(gof["p"], 6),
        })

    # ── 1.2 1位 的"小号偏好"有多强：与"任意位次"对比 ──
    # 全部 20 个号的均值应 ≈ 40.5（无偏），而 1位 均值远小于 40.5
    all_mean = sum(sum(d) for d in draws) / (n * 20)
    k1 = rows[0]
    pref = {
        "all20_numbers_mean": round(all_mean, 4),
        "k1_mean": k1["mean"],
        "k1_share_le04": round(sum(1 for d in draws if d[0] <= 4) / n, 4),
        "k1_share_le10": k1["ecdf_le10"],
        "k1_max_ever": k1["max"],
        "k1_theory_mean": k1["theory_mean"],
        "k1_expected_share_le04": round(L.order_stat_cdf(1, 4), 4),
        "k2_mean": rows[1]["mean"],
        "k3_mean": rows[2]["mean"],
        "note": "1位 = 当期最小号；最小号天然落在小号区，与任何'紫球/橙球对应'无关。",
    }

    # ── 1.3 全部 20 个位次的均值（验证"位次均值是等差"） ──
    all20 = []
    for k in range(1, 21):
        vals = [d[k - 1] for d in draws]
        mu_th, _ = L.order_stat_moments(k)
        all20.append({"k": k, "mean": round(sum(vals) / n, 4),
                      "theory_mean": round(mu_th, 4),
                      "diff": round(sum(vals) / n - mu_th, 4)})
    # 位次均值的线性度: 理论为 k*(N+1)/(m+1) = 3.8571k
    slope_num = sum(k * r["mean"] for k, r in zip(range(1, 21), all20))
    slope_den = sum(k * k for k in range(1, 21))
    slope = slope_num / slope_den
    resid = max(abs(r["mean"] - slope * r["k"]) for r, k in zip(all20, range(1, 21)))

    out = {
        "meta": {"periods": n, "first": periods[0], "last": periods[-1],
                 "fonts": fonts, "unif_mean": UNIF_MEAN, "unif_sd": round(UNIF_SD, 4)},
        "positions": rows,
        "positions_1_20_mean": all20,
        "fitted_slope_k": round(slope, 4),
        "theory_slope": round(81 / 21, 4),
        "max_abs_resid_from_linear": round(resid, 4),
        "k1_bias": pref,
    }
    save_json("struct_positions.json", out)

    # ══════════════════ 图1：箱线图 k=1..12 ══════════════════
    fig, ax = L.plt.subplots(figsize=(11, 5.6))
    data = [np.array([d[k - 1] for d in draws]) for k in KS]
    bp = ax.boxplot(data, positions=KS, widths=0.62, patch_artist=True,
                    showfliers=True, flierprops=dict(marker=".", ms=2.5,
                                                     markerfacecolor="#888", alpha=0.35,
                                                     markeredgecolor="none"),
                    medianprops=dict(color="#c0392b", lw=1.6))
    for patch in bp["boxes"]:
        patch.set_facecolor("#8ecae6")
        patch.set_alpha(0.75)
        patch.set_edgecolor("#1d3557")
    th_means = [L.order_stat_moments(k)[0] for k in KS]
    ax.plot(KS, th_means, "o--", color="#e76f51", ms=6, lw=1.4,
            label="精确理论均值 k·81/21")
    obs_means = [r["mean"] for r in rows]
    ax.plot(KS, obs_means, "s-", color="#023047", ms=5, lw=1.2, label="实测均值")
    ax.axhline(UNIF_MEAN, color="#6a4c93", ls=":", lw=1.6,
               label=f"均匀单号均值 {UNIF_MEAN}")
    ax.set_xlabel("位次 k（升序第 k 个号）")
    ax.set_ylabel("号码")
    ax.set_title("图1  1..12 位的号码分布（2101 期实测箱线）\n"
                 "位次越靠前越系统偏小：这是顺序统计量的必然，不是规律", fontsize=11)
    ax.set_xticks(KS)
    ax.set_ylim(0, 81)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    p1 = L.save_fig(fig, "struct_fig1_position_boxplot.png")

    # ══════════════════ 图2：1/2/3 位直方图 + 理论密度 ══════════════════
    fig, axes = L.plt.subplots(3, 1, figsize=(11, 9.2), sharex=True)
    for ax, k in zip(axes, (1, 2, 3)):
        vals = [d[k - 1] for d in draws]
        bins = np.arange(0.5, 81.5, 1.0)
        cnt, _ = np.histogram(vals, bins=bins)
        ax.bar(np.arange(1, 81), cnt / n, width=0.92, color="#219ebc",
               alpha=0.75, label=f"{k}位实测频率")
        th = np.array(L.order_stat_pmf(k))
        ax.plot(np.arange(1, 81), th, color="#e63946", lw=1.8,
                label=f"{k}位理论 P(X({k})=x)（超几何精确）")
        mu_th, sd_th = L.order_stat_moments(k)
        ax.axvline(np.mean(vals), color="#023047", ls="--", lw=1.0)
        ax.axvline(mu_th, color="#fb8500", ls=":", lw=1.4)
        ax.set_ylabel("概率 / 频率")
        ax.set_title(f"{k}位：实测均值 {np.mean(vals):.2f} vs 理论 {mu_th:.2f}"
                     f"（理论 sd {sd_th:.2f}）", fontsize=10)
        ax.legend(fontsize=8.5, loc="upper right")
    axes[-1].set_xlabel("号码")
    axes[-1].set_xlim(0.5, 80.5)
    fig.suptitle("图2  1位/2位/3位 的分布：实测直方图与精确理论密度几乎重合", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    p2 = L.save_fig(fig, "struct_fig2_hist_k123.png")

    # 控制台摘要
    print(f"[1] 期数={n}  字体={fonts[0]}")
    print(f"{'k':>3} {'实测均值':>9} {'理论均值':>9} {'实测sd':>8} {'理论sd':>8} "
          f"{'P(<=10)':>9} {'理论':>7} {'p_gof':>8}")
    for r in rows:
        print(f"{r['k']:>3} {r['mean']:>9.3f} {r['theory_mean']:>9.3f} "
              f"{r['sd']:>8.3f} {r['theory_sd']:>8.3f} {r['ecdf_le10']:>9.4f} "
              f"{r['theory_ecdf_le10']:>7.4f} {r['p_vs_theory']:>8.4f}")
    print(f"1位 均值={k1['mean']:.2f} (理论 {k1['theory_mean']:.2f}), "
          f"P(1位<=4)={pref['k1_share_le04']:.4f} (理论 {pref['k1_expected_share_le04']:.4f}), "
          f"历史最大 1位={k1['max']}, Cohen d vs 40.5 = {k1['cohen_d_vs_uniform']:.2f}")
    print(f"20 位次均值 线性拟合斜率={slope:.4f} (理论 81/21={81/21:.4f}), "
          f"最大偏离={resid:.3f}")
    print("figs:", os.path.basename(p1), os.path.basename(p2))


if __name__ == "__main__":
    main()
