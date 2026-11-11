# -*- coding: utf-8 -*-
"""图1/图2 规则（和值012路对应）—— 逐项核验 + 基准率 + 走查回测。

截图中可读事实
--------------
* 规则A：橙球三球 和值的 012 路 (sum % 3)  ==  紫球自身 012 路 (ball % 3)
* 规则B（图5）：橙球三球 和值尾数的大小  ==  紫球自身尾数的大小
* 截图文字自称"该规律已经连续出现 9 次"（图2/图1），另一图称 14 次（图5）
* 截图给出的算术样例：11+6+15=32 → 32 mod 3 = 2
* 紫球（图1/图2，紫=球号本身取模）：26244→01，26248→03，26252→02，26272→11，26276→02
* 紫球（图5）：26269→02，26274→09，26276→02，26279→08

本脚本做三件事
--------------
V1  算术与球位核验：截图里出现的每个数字是否与真实开奖一致，样例算术是否正确。
V2  基准率：对**任何**固定模板，规则A的真实命中率、规则B的真实命中率。
V3  走查回测：把规则当预测器，在 2101 期上滚动预测，与 1/3、1/2 基准比较。
"""
from __future__ import annotations

import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

FIG = os.path.join(HERE, "verify", "figs")
os.makedirs(FIG, exist_ok=True)

periods, idx = load_index()
draws = [idx[p] for p in periods]
P = {p: i for i, p in enumerate(periods)}
N = len(draws)


# ══════════════════════════════ V1 核验 ══════════════════════════════
def v1_verify():
    out = {"purple_checks": [], "arithmetic_checks": [], "grid_checks": []}

    # 1) 紫球核验：截图声称的紫球号 vs 真实开奖该位次的号
    reported = [
        (2026244, 1, 1, "图1"), (2026248, 1, 3, "图1"), (2026252, 1, 2, "图1"),
        (2026272, 1, 11, "图2"), (2026276, 1, 2, "图2"),
        (2026269, 2, 2, "图5"), (2026274, 2, 9, "图5"), (2026276, 1, 2, "图5"),
        (2026279, 2, 8, "图5"),
    ]
    for per, pos, claimed, src in reported:
        real = draws[P[per]][pos - 1]
        out["purple_checks"].append({
            "period": per, "pos": pos, "claimed": claimed, "real": real,
            "ok": real == claimed, "source": src,
        })

    # 2) 截图算术样例核验：11+6+15=32 → 012路=2
    sample = (11, 6, 15)
    out["arithmetic_checks"].append({
        "expr": "11+6+15", "sum": sum(sample), "sum_mod3": sum(sample) % 3,
        "claimed_sum": 32, "claimed_mod3": 2,
        "ok": sum(sample) == 32 and sum(sample) % 3 == 2,
        "note": "算术本身正确",
    })
    # 3) 图例：26246 行 2/3/4 位 = 08/10/16
    out["arithmetic_checks"].append({
        "expr": "08+10+16", "sum": 34, "sum_mod3": 34 % 3,
        "claimed_sum": None, "claimed_mod3": None,
        "ok": True, "note": "该三球组 012 路 = 1",
    })
    # 4) 网格核验：截图中抓取的 12 行 × 12 列是否与真实开奖完全一致
    grid = {
        2026241: [7, 9, 15, 16, 18, 19, 32, 33, 36, 37, 40, 52],
        2026242: [4, 20, 28, 32, 35, 37, 39, 44, 48, 50, 52, 53],
        2026243: [1, 2, 3, 9, 21, 29, 31, 36, 37, 41, 43, 46],
        2026244: [1, 4, 7, 8, 10, 12, 34, 46, 47, 53, 55, 56],
        2026245: [5, 6, 9, 15, 18, 25, 26, 27, 30, 31, 34, 36],
        2026246: [3, 8, 10, 16, 18, 20, 23, 29, 31, 35, 51, 53],
        2026250: [4, 5, 6, 8, 17, 22, 23, 31, 35, 47, 49, 51],
        2026252: [2, 3, 4, 8, 36, 38, 40, 41, 46, 49, 50, 52],
        2026253: [1, 2, 8, 17, 23, 24, 29, 31, 40, 41, 46, 47],
        2026269: [1, 2, 3, 7, 11, 13, 15, 18, 25, 27, 30, 35],
        2026270: [3, 6, 7, 8, 9, 16, 21, 22, 23, 27, 39, 40],
        2026272: [11, 14, 19, 20, 39, 40, 41, 43, 47, 51, 57, 62],
        2026274: [8, 9, 15, 17, 27, 29, 35, 38, 43, 44, 45, 46],
        2026276: [2, 6, 7, 11, 15, 18, 22, 27, 30, 32, 37, 38],
        2026279: [1, 8, 9, 11, 15, 19, 23, 27, 30, 36, 38, 40],
    }
    okc = 0
    for per, row in grid.items():
        real = list(draws[P[per]][:12])
        out["grid_checks"].append({"period": per, "screenshot": row, "real": real,
                                   "ok": row == real})
        okc += row == real
    out["grid_summary"] = {"checked": len(grid), "match": okc}
    return out


# ══════════════════════════ V2 基准率（含理论） ══════════════════════════
def v2_baseline():
    """任意固定模板的真实命中率三件套：理论值、实测分布、全局均值。"""
    res = {"r012": [], "tailsize": []}
    for attr in ("r012", "tailsize"):
        for p in range(1, 13):
            for c in range(1, 11):
                for d in (-2, 0, 1):
                    bits = []
                    for t in range(N):
                        if t + d < 0 or t + d >= N:
                            continue
                        pu = draws[t][p - 1]
                        tri = (draws[t + d][c - 1], draws[t + d][c], draws[t + d][c + 1])
                        if attr == "r012":
                            bits.append(road012_of_sum(tri) == road012(pu))
                        else:
                            bits.append(tail_size(tail_of_sum(tri)) == tail_size(pu % 10))
                    res[attr].append({"pos": p, "cols": (c, c + 1, c + 2), "offset": d,
                                      "n": len(bits), "hits": sum(bits),
                                      "rate": round(sum(bits) / len(bits), 6)})
    summ = {}
    for attr, base in (("r012", 1 / 3), ("tailsize", 0.5)):
        rates = [r["rate"] for r in res[attr]]
        m = sum(rates) / len(rates)
        sd = (sum((x - m) ** 2 for x in rates) / (len(rates) - 1)) ** 0.5
        # 单一模板命中率的理论标准误
        se = (base * (1 - base) / (N - 2)) ** 0.5
        summ[attr] = {"n_templates": len(rates), "theoretical": base,
                      "measured_mean": round(m, 6), "template_sd": round(sd, 6),
                      "theoretical_se": round(se, 6),
                      "max_rate": round(max(rates), 4), "min_rate": round(min(rates), 4)}
    # 三球和值 012 路 / 尾数大小的理论均匀性（1..80 上精确枚举，再与实测比）
    # 理论：80 球中 0路 26 个(3,6,...,78)、1路 27、2路 27
    cnt = {0: 0, 1: 0, 2: 0}
    for x in range(1, NUM_BALLS + 1):
        cnt[x % 3] += 1
    summ["ball_road_counts"] = cnt
    summ["ball_road_props"] = {k: round(v / NUM_BALLS, 5) for k, v in cnt.items()}
    return res, summ


# ══════════════════════════ V3 走查回测 ══════════════════════════
def v3_walkforward():
    """滚动回测：只用 t 之前的数据选模板，预测 t 期紫球的 012 路。

    策略对比
    --------
    S0 随机猜（基准：按球类比例 26/80,27/80,27/80）
    S1 固定模板（截图式：紫 1位，橙 t-2 期 2/3/4 位）
    S2 "追连击"：在 240 个模板里选当前连击最长者来预测（模拟APP展示逻辑）
    S3 "追热"：选历史命中率最高的模板
    """
    def build(p, c, d, attr):
        bits = [None] * N
        for t in range(N):
            if t + d < 0 or t + d >= N:
                continue
            pu = draws[t][p - 1]
            tri = (draws[t + d][c - 1], draws[t + d][c], draws[t + d][c + 1])
            if attr == "r012":
                bits[t] = road012_of_sum(tri) == road012(pu)
            else:
                bits[t] = tail_size(tail_of_sum(tri)) == tail_size(pu % 10)
        return bits

    # 规则A 的模板集合（紫球位次 1..12，橙三球位次窗口，3 个期差）
    templates = []
    for p in range(1, 13):
        for c in range(1, 11):
            for d in (-2, 0, 1):
                templates.append((p, c, d, build(p, c, d, "r012")))
    # 起点：留 200 期做"训练"，其余逐期预测
    start = 200
    tests = []
    for t in range(start, N):
        tests.append(t)

    def evaluate(chooser):
        hits, n = 0, 0
        streak_len_hist = []
        chosen_streak = []
        for t in tests:
            k = chooser(t)
            if k is None:
                continue
            b = templates[k][3][t]
            if b is None:
                continue
            hits += b
            n += 1
            # 记录被选模板在 t 之前已经连中多久
            s = 0
            j = t - 1
            while j >= 0 and templates[k][3][j]:
                s += 1
                j -= 1
            chosen_streak.append(s)
        rate = hits / n
        se = (rate * (1 - rate) / n) ** 0.5
        z = (rate - 1 / 3) / se
        return {"n": n, "hits": hits, "rate": round(rate, 5),
                "z_vs_1_3": round(z, 3),
                "mean_chosen_streak": round(sum(chosen_streak) / len(chosen_streak), 3),
                "max_chosen_streak": max(chosen_streak)}

    # S1 固定模板：紫1位，橙 t-2 期 2/3/4 位
    fixed_k = next(i for i, tp in enumerate(templates) if tp[:3] == (1, 2, -2))
    s1 = evaluate(lambda t: fixed_k)

    # S2 追连击（平手时取下标最小）
    def s2(t):
        best, bk = -1, None
        for i, (p, c, d, bits) in enumerate(templates):
            s = 0
            j = t - 1
            while j >= 0 and bits[j]:
                s += 1
                j -= 1
            if s > best:
                best, bk = s, i
        return bk

    # S3 追热（历史命中率最高）
    def s3(t):
        best, bk = -1, None
        for i, (p, c, d, bits) in enumerate(templates):
            sub = [x for x in bits[:t] if x is not None]
            if len(sub) < 100:
                continue
            r = sum(sub) / len(sub)
            if r > best:
                best, bk = r, i
        return bk

    s2r = evaluate(s2)
    s3r = evaluate(s3)

    # 随机基准
    import random
    rng = random.Random(20260822)
    base_props = [26 / 80, 27 / 80, 27 / 80]
    rh, rn = 0, 0
    for t in tests:
        pu = draws[t][0]
        guess = rng.choices([0, 1, 2], weights=base_props)[0]
        rh += (guess == road012(pu))
        rn += 1
    s0 = {"n": rn, "hits": rh, "rate": round(rh / rn, 5),
          "z_vs_1_3": round((rh / rn - 1 / 3) / ((1 / 3 * 2 / 3 / rn) ** 0.5), 3)}

    # 全部模板做同样回测，看最优能到多少（这是"挑最好的那个"的上界）
    per_template = []
    for i, (p, c, d, bits) in enumerate(templates):
        sub = [bits[t] for t in tests if bits[t] is not None]
        per_template.append({"pos": p, "cols": c, "offset": d,
                             "rate": round(sum(sub) / len(sub), 5), "n": len(sub)})
    rates = sorted(x["rate"] for x in per_template)
    return {
        "S0_random": s0,
        "S1_fixed_template": s1,
        "S2_chase_streak": s2r,
        "S3_chase_hot": s3r,
        "all_templates": {
            "n": len(per_template),
            "best": per_template[max(range(len(per_template)),
                                     key=lambda i: per_template[i]["rate"])],
            "worst": per_template[min(range(len(per_template)),
                                      key=lambda i: per_template[i]["rate"])],
            "p05": rates[int(0.05 * len(rates))],
            "median": rates[len(rates) // 2],
            "p95": rates[int(0.95 * len(rates))],
        },
        "note": "rate 为命中率；z_vs_1_3 越大越偏离 1/3；|z|<2 即与随机不可区分",
    }


if __name__ == "__main__":
    print("== V1 ==")
    v1 = v1_verify()
    for c in v1["purple_checks"]:
        print(f"  {c['period']} {c['pos']}位 {c['source']} 截图={c['claimed']:02d} "
              f"真实={c['real']:02d} {'OK' if c['ok'] else 'NG'}")
    print("  网格核验:", v1["grid_summary"])

    print("== V2 ==")
    res, summ = v2_baseline()
    for k in ("r012", "tailsize"):
        print(" ", k, summ[k])

    print("== V3 ==")
    v3 = v3_walkforward()
    for k in ("S0_random", "S1_fixed_template", "S2_chase_streak", "S3_chase_hot"):
        print(" ", k, v3[k])
    print("  all_templates:", v3["all_templates"])

    save_json("v1_verify.json", v1)
    save_json("v2_baseline.json", summ)
    save_json("v3_walkforward.json", v3)
    print("saved")
