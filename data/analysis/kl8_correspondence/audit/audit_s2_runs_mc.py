# -*- coding: utf-8 -*-
"""步骤2：游程（连续命中）的随机期望 —— 解析 + 蒙特卡洛。

四件事
------
(1) 单序列：n=2101, p∈{1/3, 1/2}，
    P(存在 >=9 连)、P(存在 >=14 连) 用**精确 DP**（解析递推，非模拟）给出，
    再用 Poisson 近似与 >=20000 次蒙特卡洛交叉验证；
    并给出 max run 的精确分布分位数 (50/90/99%)。
(2) 多模板：一个会扫描 N 个候选模板的界面，"至少有一个模板出现 9 连/14 连"的概率。
    iid 下 1-(1-p_single)^N 是**精确**值（因此称"独立近似"，实为解析真值）；
    再用蒙特卡洛（N=240 / N=5720）交叉验证，并给 log10 补概率以免浮点饱和丢信息。
(3) 尾随游程（界面口径）：最新一期（2026280）当下"仍在延续"的连击长度 >=k 的概率 = p^k。
(4) 模板空间规模与"必然性"定量结论：N 个模板下天然可刷出的连击阈值 K_med / K*。
"""
from __future__ import annotations

import time

import numpy as np

import audit_lib as L

T = 2101
PS = {"A": 1.0 / 3.0, "B": 0.5}
SIMS_SINGLE = 20000          # 单序列 MC 次数（>=20000 要求）
SIMS_SMALL_N = 20000
SIMS_MULTI = {240: 4000, 5720: 1000}   # N 大时概率饱和，减少次数以控时
KS = (9, 14)
NS_TEMPLATE = [240, 5720]


def wilson(k, n, z=1.96):
    if n == 0:
        return [0.0, 1.0]
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return [float(max(0.0, c - h)), float(min(1.0, c + h))]


def p_any_of_n(p_single, N):
    """1-(1-p_single)^N 的数值稳定版本；返回 (p_any, log10_complement, log10_p_any_safe)。"""
    if p_single <= 0:
        return 0.0, 0.0, None
    log_comp = N * np.log1p(-min(p_single, 1 - 1e-16))     # log((1-p)^N)
    p_any = -np.expm1(log_comp)
    return (
        float(min(1.0, p_any)),
        float(log_comp / np.log(10)),
        float(np.log10(max(p_any, 1e-300))),
    )


def analytic_single(n, p, k):
    p_no = L.prob_no_run(n, p, k)
    E = (n - k + 1) * p ** k * (1 - p)           # 期望长度>=k 的游程个数
    return {
        "n": n, "p": p, "k": k,
        "p_no_run_exact": p_no,
        "p_exist_run_exact": 1.0 - p_no,
        "expected_run_count_E": float(E),
        "poisson_approx": float(1.0 - np.exp(-E)),
        "log10_p_exist": float(np.log10(max(1.0 - p_no, 1e-300))),
        "log10_p_no_run": float(np.log10(max(p_no, 1e-300))),
    }


def mc_single(n, p, sims, rng):
    vals = L.mc_maxrun_quantiles(n, p, sims, rng)
    return {
        "sims": sims, "n": n, "p": p,
        "p_exist_ge9": float((vals >= 9).mean()),
        "p_exist_ge14": float((vals >= 14).mean()),
        "p_exist_ge9_ci95": wilson(int((vals >= 9).sum()), sims),
        "p_exist_ge14_ci95": wilson(int((vals >= 14).sum()), sims),
        "maxrun_mean": float(vals.mean()),
        "maxrun_std": float(vals.std(ddof=1)),
        "maxrun_q50": L.pct(vals, 50), "maxrun_q90": L.pct(vals, 90),
        "maxrun_q99": L.pct(vals, 99), "maxrun_q999": L.pct(vals, 99.9),
        "maxrun_min": int(vals.min()), "maxrun_max": int(vals.max()),
    }


def mc_any_over_templates(n_templates, n, p, ks, sims, rng, chunk=572):
    """MC: P(至少一个模板出现 >=k 连)，对 ks 中每个 k。

    每轮独立模拟 n_templates 条长度 n 的 Bernoulli(p) 序列；
    对每轮取全体模板的 max run，再与各 k 比较（一次模拟同时评估多个 k）。
    """
    t0 = time.time()
    hits = {k: 0 for k in ks}
    idx = np.arange(n, dtype=np.int32)
    for _ in range(sims):
        best = 0
        left = n_templates
        while left > 0:
            b = min(chunk, left)
            left -= b
            m = rng.random((b, n)) < p
            lf = np.maximum.accumulate(np.where(m, np.int32(-1), idx), axis=1)
            best = max(best, int((idx[None, :] - lf).max()))
            del m, lf
        for k in ks:
            if best >= k:
                hits[k] += 1
    return ({k: {"mc_p_any": hits[k] / sims, "sims": sims, "hits": hits[k],
                 "ci95": wilson(hits[k], sims),
                 "resolution_note": f"1/{sims} 为最小可分辨非零值" if hits[k] < sims else "饱和(=1)"}
             for k in ks},
            round(time.time() - t0, 3), n_templates)


def k_thresholds(n, p, N, kmax=30):
    """N 个模板下天然最长连击的量级。"""
    ps = {k: L.prob_exist_run(n, p, k) for k in range(2, kmax + 1)}

    def first_at(target, fn):
        for k in range(2, kmax + 1):
            if fn(k) >= target:
                return k, ps[k]
        return None, None

    k_med, _ = first_at(0.5, lambda k: p_any_of_n(ps[k], N)[0])
    k_90, _ = first_at(0.9, lambda k: p_any_of_n(ps[k], N)[0])
    k_99, _ = first_at(0.99, lambda k: p_any_of_n(ps[k], N)[0])
    k_star, _ = first_at(1.0, lambda k: N * ps[k])
    return {"p_single_by_k": {str(k): float(v) for k, v in ps.items()},
            "K_med": k_med, "K_90": k_90, "K_99": k_99,
            "K_star_expected_count_1": k_star,
            "expected_num_templates_at_K_med": float(N * ps[k_med]) if k_med else None}


def main():
    periods, num = L.load_draws()
    assert num.shape[0] == T
    out = {
        "meta": {
            "periods": T, "seed": L.SEED, "n_sequence": T,
            "note": ("p_single = 长度 2101 iid 伯努利序列中'至少出现一段长度>=k 连击'的概率。"
                     "exact 用 O(n·k) 递推 DP 精确计算（解析）；Poisson 与 MC 仅作交叉验证。"
                     "iid 模板下 1-(1-p_single)^N 为精确值。"),
            "sims_single": SIMS_SINGLE, "sims_multi": SIMS_MULTI,
        }
    }

    # ─────────── (1) 单序列 ───────────
    rng = np.random.RandomState(L.SEED + 11)
    single = {}
    for tag, p in PS.items():
        blk = {"analytic": {f"k{k}": analytic_single(T, p, k) for k in KS},
               "mc": mc_single(T, p, SIMS_SINGLE, rng)}
        cdf = L.maxrun_cdf(T, p, mmax=40)
        blk["maxrun_distribution_exact"] = {
            "cdf_ge": {str(m): float(1.0 - cdf[m]) for m in range(4, 26)},
            "q50": L.maxrun_quantile(cdf, 0.50), "q90": L.maxrun_quantile(cdf, 0.90),
            "q99": L.maxrun_quantile(cdf, 0.99), "q999": L.maxrun_quantile(cdf, 0.999),
            "mean": float(sum(m * (cdf[m] - cdf[m - 1]) for m in range(1, len(cdf)))),
            "note": "P(maxrun<=m)=P(无长度 m+1 的游程)，精确 DP",
        }
        a9, a14, mc = blk["analytic"]["k9"], blk["analytic"]["k14"], blk["mc"]
        blk["cross_check"] = {
            "ge9": {"exact": a9["p_exist_run_exact"], "mc": mc["p_exist_ge9"],
                    "mc_ci95": mc["p_exist_ge9_ci95"],
                    "exact_in_mc_ci": bool(mc["p_exist_ge9_ci95"][0] <= a9["p_exist_run_exact"]
                                           <= mc["p_exist_ge9_ci95"][1]),
                    "poisson": a9["poisson_approx"]},
            "ge14": {"exact": a14["p_exist_run_exact"], "mc": mc["p_exist_ge14"],
                     "mc_ci95": mc["p_exist_ge14_ci95"],
                     "exact_in_mc_ci": bool(mc["p_exist_ge14_ci95"][0] <= a14["p_exist_run_exact"]
                                            <= mc["p_exist_ge14_ci95"][1]),
                     "poisson": a14["poisson_approx"]},
        }
        single[tag] = blk
    out["single_sequence"] = single

    # ─────────── (2) 多模板 ───────────
    multi = {}
    rngm = np.random.RandomState(L.SEED + 22)

    # 2a. MC 实现校验：用 p_single 未饱和的小 k，验证 MC == 独立解析值
    val_ks = (4, 5, 6, 7)
    val = {}
    for N in (1, 3, 10):
        st, secs, _ = mc_any_over_templates(N, T, PS["A"], val_ks, SIMS_SMALL_N, rngm, chunk=N)
        val[str(N)] = {
            "mc": st, "secs": secs,
            "analytic_iid": {str(k): p_any_of_n(L.prob_exist_run(T, PS["A"], k), N)[0]
                             for k in val_ks},
            "abs_diff": {str(k): abs(p_any_of_n(L.prob_exist_run(T, PS["A"], k), N)[0]
                                     - st[k]["mc_p_any"]) for k in val_ks},
        }
    multi["validation_mc_vs_analytic_iid"] = {
        "k_list": list(val_ks), "by_N": val,
        "note": "iid 模板下 1-(1-p_single)^N 是精确值，此处仅校验 MC 代码正确性；"
                "真实模板高度相关（共享位次与期次），故独立近似是上界，真实值需由第3步打乱对照给出。"}

    for N in NS_TEMPLATE:
        blk = {}
        for tag, p in PS.items():
            ap = {str(k): dict(zip(("p_any", "log10_complement", "log10_p_any"),
                                   p_any_of_n(L.prob_exist_run(T, p, k), N))) for k in KS}
            st, secs, _ = mc_any_over_templates(N, T, p, KS, SIMS_MULTI[N], rngm)
            blk[tag] = {
                "independent_analytic": ap, "mc": st, "secs": secs,
                "p_single": {str(k): float(L.prob_exist_run(T, p, k)) for k in KS},
                "expected_templates_with_run": {
                    str(k): float(min(N * L.prob_exist_run(T, p, k), 1e300)) for k in KS},
            }
        blk["K_thresholds"] = {tag: k_thresholds(T, p, N) for tag, p in PS.items()}
        multi[f"N={N}"] = blk

    for N in (L.N_PER_ATTR, L.N_ALL):
        multi[f"N={N}_K_thresholds"] = {tag: k_thresholds(T, p, N) for tag, p in PS.items()}
    out["multi_template"] = multi

    # ─────────── (2c) 尾随游程（界面口径：最新一期仍在延续的连击） ───────────
    trailing = {"note": "界面展示'当前仍在延续'的连击，其零概率 = p^k（只看最新一期往前的最长后缀）。"
                        "N 个模板中至少一个尾随连击 >=k：1-(1-p^k)^N。",
                "by_p": {}}
    for tag, p in PS.items():
        entry = {"p": p, "by_k": {}}
        for k in (5, 6, 7, 8, 9, 10, 12, 14):
            ps = float(p ** k)
            for N in (240, 5720, L.N_PER_ATTR, L.N_ALL):
                pa, logc, _ = p_any_of_n(ps, N)
                entry["by_k"].setdefault(str(k), {})[f"N={N}"] = {
                    "p_single_template": ps, "p_any": pa, "log10_complement": logc}
        trailing["by_p"][tag] = entry
    out["trailing_run_null"] = trailing

    # ─────────── (3) 模板空间 ───────────
    out["template_space"] = {
        "purple_positions": len(L.PURPLE_POS),
        "orange_combos_C12_3": L.N_COMBOS,
        "offsets": len(L.OFFSETS), "offset_range": [min(L.OFFSETS), max(L.OFFSETS)],
        "attributes": len(L.ATTRS),
        "n_templates_per_attr": L.N_PER_ATTR,
        "n_templates_total": L.N_ALL,
        "n_templates_no_offset_both_attrs": len(L.PURPLE_POS) * L.N_COMBOS * len(L.ATTRS),
        "derivation": ("紫球位次 12 × 橙三球位次组合 C(12,3)=220 × 期差 13 × 属性 2 = 68640；"
                       "限同构建(不扫期差) 12×220×2 = 5280；界面若再限橙球位次范围则约数百~数千，"
                       "故取 N=240 与 N=5720 两档作为保守/现实区间。"),
    }

    # ─────────── (4) 结论 ───────────
    sa, sb = out["single_sequence"]["A"], out["single_sequence"]["B"]
    m5720 = multi["N=5720"]
    out["headline"] = {
        "P_single_seq_ge9_p1_3": sa["analytic"]["k9"]["p_exist_run_exact"],
        "P_single_seq_ge14_p1_3": sa["analytic"]["k14"]["p_exist_run_exact"],
        "P_single_seq_ge9_p1_2": sb["analytic"]["k9"]["p_exist_run_exact"],
        "P_single_seq_ge14_p1_2": sb["analytic"]["k14"]["p_exist_run_exact"],
        "expected_maxrun_q50_p1_3": sa["maxrun_distribution_exact"]["q50"],
        "expected_maxrun_q90_p1_3": sa["maxrun_distribution_exact"]["q90"],
        "expected_maxrun_q99_p1_3": sa["maxrun_distribution_exact"]["q99"],
        "expected_maxrun_q50_p1_2": sb["maxrun_distribution_exact"]["q50"],
        "expected_maxrun_q90_p1_2": sb["maxrun_distribution_exact"]["q90"],
        "expected_maxrun_q99_p1_2": sb["maxrun_distribution_exact"]["q99"],
        "P_any_240_ge9_p1_3": multi["N=240"]["A"]["independent_analytic"]["9"]["p_any"],
        "P_any_240_ge14_p1_3": multi["N=240"]["A"]["independent_analytic"]["14"]["p_any"],
        "P_any_5720_ge9_p1_3": m5720["A"]["independent_analytic"]["9"]["p_any"],
        "P_any_5720_ge14_p1_3": m5720["A"]["independent_analytic"]["14"]["p_any"],
        "P_any_5720_ge9_p1_2": m5720["B"]["independent_analytic"]["9"]["p_any"],
        "P_any_5720_ge14_p1_2": m5720["B"]["independent_analytic"]["14"]["p_any"],
        "log10_P_any_5720_ge14_p1_3": m5720["A"]["independent_analytic"]["14"]["log10_p_any"],
        "log10_P_any_240_ge14_p1_3": multi["N=240"]["A"]["independent_analytic"]["14"]["log10_p_any"],
        "expected_num_5720_templates_ge9_p1_3": m5720["A"]["expected_templates_with_run"]["9"],
        "expected_num_5720_templates_ge14_p1_3": m5720["A"]["expected_templates_with_run"]["14"],
        "expected_num_5720_templates_ge14_p1_2": m5720["B"]["expected_templates_with_run"]["14"],
        "K_med_N5720_A": m5720["K_thresholds"]["A"]["K_med"],
        "K_med_N240_A": multi["N=240"]["K_thresholds"]["A"]["K_med"],
        "K_star_N5720_A": m5720["K_thresholds"]["A"]["K_star_expected_count_1"],
        "K_star_N5720_B": m5720["K_thresholds"]["B"]["K_star_expected_count_1"],
        "K_med_N_all34320_A": multi[f"N={L.N_PER_ATTR}_K_thresholds"]["A"]["K_med"],
        "statement": (
            "单模板 9 连在 p=1/3 下只有 %.2f%% 概率（14 连 %.4f%%），看似稀有；"
            "但界面扫描 N=5720 个模板时'至少一个出现 14 连'的概率在 p=1/3 下也是 1-10^(%.0f) 量级，"
            "在 p=1/2 下同样是 1-10^(%.0f) 量级 —— 即必然事件。"
            "因此截图的'连续9次/14次'本身不能作为任何证据。"
        ) % (100 * sa["analytic"]["k9"]["p_exist_run_exact"],
             100 * sa["analytic"]["k14"]["p_exist_run_exact"],
             m5720["A"]["independent_analytic"]["14"]["log10_complement"],
             m5720["B"]["independent_analytic"]["14"]["log10_complement"]),
    }

    path = L.save("audit_runs_mc.json", out)
    print("[s2] saved:", path)
    for tag in PS:
        s = out["single_sequence"][tag]
        a, m = s["analytic"], s["mc"]
        print(f"[s2] {tag} p={PS[tag]:.4f} exactP>=9={a['k9']['p_exist_run_exact']:.6f} "
              f"exactP>=14={a['k14']['p_exist_run_exact']:.6f} | MC9={m['p_exist_ge9']:.4f} "
              f"MC14={m['p_exist_ge14']:.4f} | q50={s['maxrun_distribution_exact']['q50']} "
              f"q99={s['maxrun_distribution_exact']['q99']}")
    for N in NS_TEMPLATE:
        b = out["multi_template"][f"N={N}"]
        print(f"[s2] N={N} A: iidP(any>=9)={b['A']['independent_analytic']['9']['p_any']:.4f} "
              f"iidP(any>=14)={b['A']['independent_analytic']['14']['p_any']:.6g} "
              f"log10comp14={b['A']['independent_analytic']['14']['log10_complement']:.0f} "
              f"MC9={b['A']['mc']['9']['mc_p_any']:.4f} MC14={b['A']['mc']['14']['mc_p_any']:.4f} "
              f"K_med={b['K_thresholds']['A']['K_med']}")
    print("[s2] template space total:", out["template_space"]["n_templates_total"])


if __name__ == "__main__":
    main()