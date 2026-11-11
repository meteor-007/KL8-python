# -*- coding: utf-8 -*-
"""步骤1：基准率基准线 —— 理论（精确枚举） + 实测（卡方）。

核心论证
--------
官方每期从 1..80 中不放回抽 20 个号。任取该 20 号中的 3 个不同号，
其集合分布 **恰好** 等同于从 1..80 中均匀取 3 个不同号
（因为 20 子集是均匀的，其任意 3 子集在 C(80,3) 上均匀）。
所以"随机三球和值"的精确零分布可以 **完全枚举** C(80,3)=82160 个三元组得到，
不需要任何近似 —— 本步骤给出这个精确零分布，并与实测数据做卡方检验。

由此得到两个"天花板"：
  p_A = P(三球和值 %3 == 紫球 %3) 在独立且边际均匀时 ≈ 1/3
  p_B = P(三球和值尾数大小 == 紫球尾数大小) ≈ 1/2
任何"对应规律"的命中率都必须与这两个数比较，而不是与 0 比较。
"""
from __future__ import annotations

import itertools

import numpy as np

import audit_lib as L
from common import chi2_uniform

rs = np.random.RandomState(L.SEED)


# ─────────────────── 1. 精确理论零分布（枚举 C(80,3)） ───────────────────
def exact_nulls():
    balls = np.arange(1, 81, dtype=np.int32)
    # 单号
    r_purple = np.bincount(balls % 3, minlength=3) / 80.0            # 012 路
    tail_purple = balls % 10
    size_purple = np.bincount((tail_purple >= 5).astype(int), minlength=2) / 80.0

    # 全部 C(80,3) 三元组（分块枚举，避免大内存）
    cnt_r = np.zeros(3, dtype=np.int64)
    cnt_s = np.zeros(2, dtype=np.int64)
    tri = np.array(list(itertools.combinations(range(80), 3)), dtype=np.int32) + 1  # (82160,3)
    s = tri.sum(axis=1)
    cnt_r += np.bincount(s % 3, minlength=3)
    cnt_s += np.bincount((s % 10 >= 5).astype(int), minlength=2)
    n_tri = tri.shape[0]
    assert n_tri == 82160, n_tri

    r_triple = cnt_r / n_tri
    size_triple = cnt_s / n_tri

    # 独立 + 各自边际 -> 规则命中率（精确零假设下的"天花板"）
    p_A = float((r_purple * r_triple).sum())
    p_B = float((size_purple * size_triple).sum())
    # 若强行假设两者都是均匀 1/3 / 1/2：
    p_A_unif = 1.0 / 3.0
    p_B_unif = 0.5
    # 均匀 null 下的卡方理论值（用于说明 1/3、1/2 的误差量级）
    chi2_A_unif = float((((r_triple - 1 / 3) ** 2) / (1 / 3)).sum() * n_tri)
    chi2_B_unif = float((((size_triple - 0.5) ** 2) / 0.5).sum() * n_tri)
    return {
        "single_road012_probs": r_purple.tolist(),
        "single_tailsize_probs": size_purple.tolist(),
        "triple_sum_road012_probs": r_triple.tolist(),
        "triple_sum_tailsize_probs": size_triple.tolist(),
        "n_triples_enumerated": int(n_tri),
        "triple_sum_min": int(s.min()), "triple_sum_max": int(s.max()),
        "p_A_exact": p_A, "p_B_exact": p_B,
        "p_A_uniform_1_3": p_A_unif, "p_B_uniform_1_2": p_B_unif,
        "deviation_A_from_1_3": p_A - p_A_unif,
        "deviation_B_from_1_2": p_B - p_B_unif,
        "chi2_if_assuming_uniform_A": chi2_A_unif,
        "chi2_if_assuming_uniform_B": chi2_B_unif,
    }


# ─────────────────── 2. 实测：边际分布卡方 ───────────────────
def empirical_cells(num, n_sample_per_period, seed_shift=0):
    """每期 iid 抽 n_sample_per_period 个"3 球组"（位置无放回），返回 (T, ns, 3) 索引。

    用位置无放回抽样：C(20,3) 上均匀 => 号码三元组在 C(80,3) 上均匀（精确）。
    """
    rng = np.random.RandomState(L.SEED + 1000 + seed_shift)
    T = num.shape[0]
    idx = np.empty((T, n_sample_per_period, 3), dtype=np.int64)
    for t in range(T):
        rows = []
        for _ in range(n_sample_per_period):
            rows.append(rng.choice(20, 3, replace=False))
        idx[t] = np.array(rows)
    return idx


def chi2_block(counts, probs):
    exp = np.asarray(probs) * counts.sum()
    chi2, dof, p = chi2_uniform(counts.tolist(), exp.tolist())
    return {"counts": counts.tolist(), "expected": [float(x) for x in exp],
            "chi2": float(chi2), "dof": int(dof), "p_value": float(p)}


def cramers_v(counts, probs):
    n = counts.sum()
    exp = np.asarray(probs) * n
    return float(np.sqrt((((counts - exp) ** 2) / exp).sum() / n))


def main():
    periods, num = L.load_draws()
    T = num.shape[0]
    print(f"[s1] periods={T} {periods[0]}..{periods[-1]}")

    ex = exact_nulls()
    print(f"[s1] 精确天花板 p_A={ex['p_A_exact']:.10f}  p_B={ex['p_B_exact']:.10f}")

    res = {
        "meta": {
            "periods": T, "period_first": periods[0], "period_last": periods[-1],
            "seed": L.SEED,
            "note": "零分布由枚举 C(80,3)=82160 精确得到；因 20 号子集的任意 3 子集在 C(80,3) 上均匀，"
                    "实测三球组与理论完全对应，无近似。",
        },
        "theory_exact": ex,
    }

    # 2a. 紫球单号边际（全部 2101×12 个位置号）
    pur = num[:, :12].ravel()
    res["empirical_single_road012"] = chi2_block(
        np.bincount(pur % 3, minlength=3), ex["single_road012_probs"])
    res["empirical_single_road012"]["n"] = int(pur.size)
    res["empirical_single_road012"]["cramers_v"] = cramers_v(
        np.bincount(pur % 3, minlength=3), ex["single_road012_probs"])
    res["empirical_single_tailsize"] = chi2_block(
        np.bincount((pur % 10 >= 5).astype(int), minlength=2), ex["single_tailsize_probs"])
    res["empirical_single_tailsize"]["n"] = int(pur.size)
    res["empirical_single_tailsize"]["cramers_v"] = cramers_v(
        np.bincount((pur % 10 >= 5).astype(int), minlength=2), ex["single_tailsize_probs"])

    # 2b. 随机三球组：两档样本量（1/期 与 10/期）
    for ns, tag in ((1, "n1_per_period"), (10, "n10_per_period")):
        ci = empirical_cells(num, ns)
        # num[t, ci[t,k]] -> 广播取值
        vals = num[np.arange(T)[:, None, None], ci]        # (T,ns,3)
        s = vals.sum(axis=2).ravel()
        cnt_r = np.bincount(s % 3, minlength=3)
        cnt_s = np.bincount((s % 10 >= 5).astype(int), minlength=2)
        blk_r = chi2_block(cnt_r, ex["triple_sum_road012_probs"])
        blk_s = chi2_block(cnt_s, ex["triple_sum_tailsize_probs"])
        blk_r["n"] = int(s.size); blk_s["n"] = int(s.size)
        blk_r["cramers_v"] = cramers_v(cnt_r, ex["triple_sum_road012_probs"])
        blk_s["cramers_v"] = cramers_v(cnt_s, ex["triple_sum_tailsize_probs"])
        # 同时给"vs 均匀 1/3、1/2"的卡方，直接回答题目
        blk_r["chi2_vs_uniform"] = chi2_uniform(cnt_r.tolist())[:2] + \
            (chi2_uniform(cnt_r.tolist())[2],)
        blk_s["chi2_vs_uniform"] = chi2_uniform(cnt_s.tolist())
        res[f"random_triples_{tag}"] = {"road012": blk_r, "tailsize": blk_s}

    # 2c. 规则空间内全部 220 组合（2101×220，期内相关，仅作大样本边际参考）
    P = num[:, :12]
    s_all = L.triple_sum_matrix(num).ravel()
    cnt_r = np.bincount(s_all % 3, minlength=3)
    cnt_s = np.bincount((s_all % 10 >= 5).astype(int), minlength=2)
    blk_r = chi2_block(cnt_r, ex["triple_sum_road012_probs"])
    blk_s = chi2_block(cnt_s, ex["triple_sum_tailsize_probs"])
    blk_r["n"] = int(s_all.size); blk_s["n"] = int(s_all.size)
    blk_r["cramers_v"] = cramers_v(cnt_r, ex["triple_sum_road012_probs"])
    blk_s["cramers_v"] = cramers_v(cnt_s, ex["triple_sum_tailsize_probs"])
    res["all_220_combos"] = {
        "road012": blk_r, "tailsize": blk_s,
        "warning": "期内 220 个组合彼此强相关（同一期 12 个号），p 值偏乐观，仅作边际参考；"
                   "独立口径请用 random_triples_* 与 uniform_all"}

    # 2d. 直接检验"紫球 vs 三球"是否独立（规则 A/B 的实际命中率）
    #     取跨期(d≠0)独立样本，避免同源相关
    rng = np.random.RandomState(L.SEED + 7)
    pairs = {}
    N_PAIR = 200000
    t_idx = rng.randint(0, T, size=N_PAIR)
    d_choices = rng.choice([d for d in L.OFFSETS if d != 0], size=N_PAIR)
    p_pos = rng.randint(0, 12, size=N_PAIR)
    combos = np.array(L.COMBOS)
    c_idx = rng.randint(0, len(combos), size=N_PAIR)
    t2 = np.clip(t_idx + d_choices, 0, T - 1)
    purple = num[t_idx, p_pos]
    cc = combos[c_idx] - 1
    triple = num[t2[:, None], cc]                      # (N,3)
    s = triple.sum(axis=1)
    hitA = (s % 3) == (purple % 3)
    hitB = ((s % 10) >= 5) == ((purple % 10) >= 5)
    for attr, hit in (("A", hitA), ("B", hitB)):
        k, n = int(hit.sum()), int(hit.size)
        rate = k / n
        p0 = ex["p_A_exact"] if attr == "A" else ex["p_B_exact"]
        se = np.sqrt(rate * (1 - rate) / n)
        z = (rate - p0) / se
        pairs[attr] = {
            "n": n, "hits": k, "rate": rate, "p_theory": p0,
            "z_vs_theory": float(z),
            "p_value_vs_theory": float(2 * (1 - L.normal_cdf(abs(z)))),
            "ci95": [rate - 1.96 * se, rate + 1.96 * se],
            "note": "跨期样本(橙球期=紫球期+d, d≠0)，紫球与橙球来自不同期，相互独立",
        }
    res["rule_hit_rate_empirical_independent"] = pairs

    # 2e. 全模板网格上的平均命中率（真实规则空间的总体实测值）
    ga = L.grid_arrays(num)
    grid = {}
    for attr in L.ATTRS:
        Pv, Sv = ga[attr]["purple"], ga[attr]["triple"]
        k = Pv.shape[1]
        rates = []
        for d in L.OFFSETS:
            t0, t1 = L.valid_range(T, d)
            pv = Pv[t0:t1 + 1]                          # (n,k)
            sv = Sv[t0 + d:t1 + 1 + d]                  # (n,220)
            hit = pv[:, :, None] == sv[:, None, :]       # (n,k,220)
            rates.append(float(hit.mean()))
            del hit
        grid[attr] = {"mean_rate_over_offsets": float(np.mean(rates)),
                      "by_offset": rates, "p_theory": ex["p_A_exact"] if attr == "A" else ex["p_B_exact"]}
    res["grid_mean_hit_rate"] = grid

    # 2f. 结论性判定
    res["headline"] = {
        "p_A_exact": ex["p_A_exact"],
        "p_B_exact": ex["p_B_exact"],
        "p_A_rounded_1_3": 1 / 3,
        "p_B_rounded_1_2": 0.5,
        "grid_mean_rate_A": grid["A"]["mean_rate_over_offsets"],
        "grid_mean_rate_B": grid["B"]["mean_rate_over_offsets"],
        "statement": "规则A 的偶然命中率天花板 = p_A_exact（≈1/3），规则B = p_B_exact（≈1/2）。"
                     "任何'连续命中N次'的说法都必须以这两个数为基线计算概率。",
    }

    path = L.save("audit_baserate.json", res)
    print("[s1] saved:", path)
    print(f"[s1] p_A={ex['p_A_exact']:.6f} p_B={ex['p_B_exact']:.6f}")
    print(f"[s1] grid mean rate A={grid['A']['mean_rate_over_offsets']:.6f} "
          f"B={grid['B']['mean_rate_over_offsets']:.6f}")
    print(f"[s1] independent pair rate A={pairs['A']['rate']:.6f} (p={pairs['A']['p_value_vs_theory']:.3f}) "
          f"B={pairs['B']['rate']:.6f} (p={pairs['B']['p_value_vs_theory']:.3f})")
    for tag in ("n1_per_period", "n10_per_period"):
        b = res[f"random_triples_{tag}"]
        print(f"[s1] {tag} road012 chi2={b['road012']['chi2']:.3f} dof={b['road012']['dof']} "
              f"p={b['road012']['p_value']:.4f} | tailsize chi2={b['tailsize']['chi2']:.3f} "
              f"p={b['tailsize']['p_value']:.4f}")


if __name__ == "__main__":
    main()
