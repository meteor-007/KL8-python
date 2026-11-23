# -*- coding: utf-8 -*-
"""出图：把核心验证结果可视化（真实数据 vs 纯随机对照）。

产出 analysis/kl8_correspondence/out/figs/*.png
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

# 中文字体
for f in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DengXian"):
    try:
        matplotlib.font_manager.findfont(f, fallback_to_default=False)
        plt.rcParams["font.sans-serif"] = [f]
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

FIGS = os.path.join(HERE, "out", "figs")
os.makedirs(FIGS, exist_ok=True)

OFFSETS = list(range(-6, 3))
POS, WIN = 20, 18


def build_hit_matrix(A, attr):
    N = A.shape[0]
    purple = (A % 3) if attr == "r012" else ((A % 10) >= 5).astype(np.int8)
    mats = []
    for d in OFFSETS:
        idx = np.arange(N) + d
        valid = (idx >= 0) & (idx < N)
        src = A[np.clip(idx, 0, N - 1)]
        for c in range(WIN):
            s = src[:, c] + src[:, c + 1] + src[:, c + 2]
            o = (s % 3) if attr == "r012" else ((s % 10) >= 5)
            mats.append(((o[:, None] == purple) & valid[:, None]).T)
    return np.concatenate(mats, axis=0)


def per_period_stats(H, ks=(9, 14), skip=300):
    """返回 {'ge9': 序列, 'ge14': 序列, 'maxavail': 序列}（按 t 索引，skip 之后）。"""
    n_rules, N = H.shape
    run = np.zeros(n_rules, dtype=np.int16)
    ge = {k: [] for k in ks}
    maxavail = []
    ts = []
    for t in range(N):
        if t >= skip:
            ts.append(t)
            for k in ks:
                ge[k].append(int((run >= k).sum()))
            maxavail.append(int(run.max()) if run.size else 0)
        run = np.where(H[:, t], run + 1, 0)
    return ts, ge, maxavail


if __name__ == "__main__":
    periods, idx = load_index()
    A = np.array([idx[p] for p in periods], dtype=np.int16)
    N = A.shape[0]
    rng = np.random.default_rng(2026)
    A_rand = np.array([np.sort(rng.choice(np.arange(1, 81), 20, replace=False))
                       for _ in range(N)], dtype=np.int16)

    # ── 图1：候选规则命中率分布 vs 理论基准 ──
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for ax, attr, base, title in (
            (axes[0], "r012", 1 / 3, "规则A：和值012路对应（理论基准 1/3）"),
            (axes[1], "tailsize", 0.5, "规则B：和值尾数大小对应（理论基准 1/2）")):
        for A_, lab, color in ((A, "真实开奖", "#d62728"), (A_rand, "纯随机对照", "#1f77b4")):
            H = build_hit_matrix(A_, attr)
            rates = H.sum(axis=1) / N
            ax.hist(rates, bins=45, alpha=0.55, label=lab, color=color, density=True)
        ax.axvline(base, color="k", ls="--", lw=2, label=f"理论基准 {base:.4f}")
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("该规则 2101 期命中率")
        ax.set_ylabel("密度")
        ax.legend(fontsize=9)
    fig.suptitle("3240 条候选“对应规则”的命中率分布：真实数据与随机数据完全重合", fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig1_baserate.png"), dpi=150)
    plt.close(fig)

    # ── 图2/图3：连中统计 ──
    series = {}
    for attr in ("r012", "tailsize"):
        Hr = build_hit_matrix(A, attr)
        Hn = build_hit_matrix(A_rand, attr)
        ts, ge_r, mx_r = per_period_stats(Hr)
        _, ge_n, mx_n = per_period_stats(Hn)
        series[attr] = {
            "ge9_real": ge_r[9], "ge9_rand": ge_n[9],
            "ge14_real": ge_r[14], "ge14_rand": ge_n[14],
            "maxavail_real": mx_r, "maxavail_rand": mx_n,
        }

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for ax, attr, title in ((axes[0], "r012", "规则A（基准 1/3）"),
                            (axes[1], "tailsize", "规则B（基准 1/2）")):
        s = series[attr]
        ax.hist(s["maxavail_real"], bins=range(0, 26), alpha=0.6,
                label="真实开奖", color="#d62728", density=True)
        ax.hist(s["maxavail_rand"], bins=range(0, 26), alpha=0.45,
                label="纯随机对照", color="#1f77b4", density=True)
        ax.axvline(9, color="k", ls=":", lw=2)
        ax.axvline(14, color="k", ls="--", lw=2)
        ax.text(9.1, ax.get_ylim()[1] * 0.85, "9连", fontsize=9)
        ax.text(14.1, ax.get_ylim()[1] * 0.6, "14连", fontsize=9)
        ax.set_title(f"任一时刻“最长可用连中”分布 —— {title}", fontsize=11)
        ax.set_xlabel("当前最长连中次数（可展示给用户的最强规则）")
        ax.set_ylabel("密度")
        ax.legend(fontsize=9)
    fig.suptitle("APP 永远能“找到一个正在连中的规则”：真随机数据同样如此", fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig2_streak_available.png"), dpi=150)
    plt.close(fig)

    # ── 图4：单期内“随便挑三球”的自由度 ──
    import itertools
    dist = {0: [], 1: [], 2: []}
    dts = {"大": [], "小": []}
    for d in A:
        c = {0: 0, 1: 0, 2: 0}
        ct = {"大": 0, "小": 0}
        for tri in itertools.combinations([int(x) for x in d], 3):
            c[sum(tri) % 3] += 1
            ct[tail_size(sum(tri) % 10)] += 1
        for k in c:
            dist[k].append(c[k])
        for k in ct:
            dts[k].append(ct[k])
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.4))
    for k, color in ((0, "#1f77b4"), (1, "#2ca02c"), (2, "#d62728")):
        axes[0].hist(dist[k], bins=60, alpha=0.55, label=f"{k}路", color=color)
    axes[0].set_title("单期内能凑出“和值012路 = 目标”的三球组数", fontsize=11)
    axes[0].set_xlabel("可选三球组数量")
    axes[0].set_ylabel("期数")
    axes[0].legend(fontsize=9)
    axes[1].hist(dts["大"], bins=60, alpha=0.55, label="和值尾数=大 的组数", color="#ff7f0e")
    axes[1].hist(dts["小"], bins=60, alpha=0.55, label="和值尾数=小 的组数", color="#9467bd")
    axes[1].set_title("单期内能凑出“和值尾数大/小”的三球组数", fontsize=11)
    axes[1].set_xlabel("可选三球组数量")
    axes[1].set_ylabel("期数")
    axes[1].legend(fontsize=9)
    fig.suptitle("“对应”必然成立：每期都有约 380 个三球组能凑出任意 012 路目标", fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig3_freedom.png"), dpi=150)
    plt.close(fig)

    # ── 图5：走查回测 ──
    v3 = json_load = None
    import json
    with open(os.path.join(OUT, "v3_walkforward.json"), encoding="utf-8") as f:
        v3 = json.load(f)
    labels = ["随机猜", "固定模板\n(截图形态)", "追最长连击\n(APP展示逻辑)", "追历史最热\n模板"]
    keys = ["S0_random", "S1_fixed_template", "S2_chase_streak", "S3_chase_hot"]
    rates = [v3[k]["rate"] for k in keys]
    ns = [v3[k]["n"] for k in keys]
    errs = [1.96 * (r * (1 - r) / n) ** 0.5 for r, n in zip(rates, ns)]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bars = ax.bar(labels, rates, yerr=errs, capsize=6,
                  color=["#7f7f7f", "#1f77b4", "#d62728", "#2ca02c"])
    ax.axhline(1 / 3, color="k", ls="--", lw=2, label="理论基准 1/3")
    for b, r in zip(bars, rates):
        ax.text(b.get_x() + b.get_width() / 2, r + 0.008, f"{r:.4f}", ha="center", fontsize=10)
    ax.set_ylim(0.28, 0.38)
    ax.set_ylabel("对下一期紫球 012 路的命中率")
    ax.set_title("走查回测（1901 期样本外）：无任何策略显著优于 1/3", fontsize=12)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig4_walkforward.png"), dpi=150)
    plt.close(fig)

    save_json("fig_series.json", {a: {k: v[:400] for k, v in s.items()}
                                  for a, s in series.items()})
    print("figs saved ->", FIGS)
    for f in sorted(os.listdir(FIGS)):
        print("  ", f)