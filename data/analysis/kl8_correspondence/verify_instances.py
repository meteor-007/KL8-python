# -*- coding: utf-8 -*-
"""V5 —— 截图实例的反向求解 + 对 2026280 的样本外裁决。

图上能读到的两条"实物规则"
--------------------------
图5（和值尾数大小）：
    橙球 = 11,6,15 的说法在文字里；连线显示 橙球 = 26276 的 2位(06)、
    26278 的 3位(08)、26278 的 4位(15)；紫球 = 26279 的 2位(08)。
    => 模板 F5: 紫 = (t, 2位)；橙 = (t-3, 2位), (t-1, 3位), (t-1, 4位)
       核对: 6+8+15 = 29, 尾 9 -> 大 ; 紫球 08 尾 8 -> 大 ; 成立

图1/图2（和值 012 路）：
    文字明确给出"橙球 11,6,15, 和 32, 012路 = 2"。
    连线显示 11 = 26277 的 3位、06 = 26278 的 2位、15 = 26278 的 4位。
    => 橙 = (t-2, 3位), (t-1, 2位), (t-1, 4位)，其中 t = 26279
       需要紫球 012路 = 2。反解：哪一个(期, 位)的紫球满足且已连中 9 期？
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

periods, idx = load_index()
draws = [idx[p] for p in periods]
P = {p: i for i, p in enumerate(periods)}
N = len(draws)
TARGET = 2026280


def bits_template(attr, ppos, rows, opos):
    """通用模板求值：紫球在 (t, ppos)，橙球在 (t+rows[i], opos[i])。"""
    b = [None] * N
    detail = [None] * N
    for t in range(N):
        tri = []
        ok = True
        for r, o in zip(rows, opos):
            if t + r < 0 or t + r >= N:
                ok = False
                break
            tri.append(draws[t + r][o - 1])
        if not ok:
            continue
        pu = draws[t][ppos - 1]
        if len(set(tri)) != 3:
            b[t] = None
            continue
        if attr == "r012":
            b[t] = road012_of_sum(tri) == road012(pu)
            detail[t] = {"purple": pu, "triple": tri, "sum": sum(tri),
                         "sum_r012": sum(tri) % 3, "purple_r012": pu % 3}
        else:
            b[t] = tail_size(tail_of_sum(tri)) == tail_size(pu % 10)
            detail[t] = {"purple": pu, "triple": tri, "sum": sum(tri),
                         "sum_tail": sum(tri) % 10,
                         "sum_size": tail_size(sum(tri) % 10),
                         "purple_tail": pu % 10, "purple_size": tail_size(pu % 10)}
    return b, detail


def study(name, attr, ppos, rows, opos):
    b, detail = bits_template(attr, ppos, rows, opos)
    valid = [x for x in b if x is not None]
    rate = sum(valid) / len(valid)
    t_tgt = P[TARGET]
    # 该模板截至目标期之前的连中长度
    s = 0
    j = t_tgt - 1
    while j >= 0 and b[j]:
        s += 1
        j -= 1
    # 目标期的真值与预测
    tri = [draws[t_tgt + r][o - 1] for r, o in zip(rows, opos)]
    pred_purple_pos = draws[t_tgt][ppos - 1]
    if attr == "r012":
        pred = road012_of_sum(tri)
        actual = road012(pred_purple_pos)
        hit = pred == actual
    else:
        pred = tail_size(tail_of_sum(tri))
        actual = tail_size(pred_purple_pos % 10)
        hit = pred == actual
    # 全历史最长连击
    mr = max_run(valid)
    return {
        "name": name, "attr": attr, "template": {"purple_pos": ppos,
                                                 "rows": list(rows), "opos": list(opos)},
        "n": len(valid), "hits": sum(valid), "rate": round(rate, 5),
        "base_rate": 1 / 3 if attr == "r012" else 0.5,
        "deviation": round(rate - (1 / 3 if attr == "r012" else 0.5), 5),
        "max_run_all_history": mr,
        "streak_until_2026279": s,
        "target_period": TARGET,
        "target_orange_triple": tri,
        "target_orange_sum": sum(tri),
        "predicted_value": pred,
        "actual_purple_ball": pred_purple_pos,
        "actual_value": actual,
        "prediction_hit": bool(hit),
        "detail_at_target": detail[t_tgt],
    }


if __name__ == "__main__":
    out = {"verified_instances": [], "back_solve_012": [], "target": TARGET}

    # ── 1. 图5 规则：逐项核验 + 样本外裁决 ──
    f5 = study("图5-和值尾数大小", "tailsize", 2, (-3, -1, -1), (2, 3, 4))
    out["verified_instances"].append(f5)
    print("【图5 规则】")
    print("  文本宣称: 6+8+15=29, 尾9 -> 大 ; 紫球 08 尾8 -> 大")
    print(f"  实测: triple={f5['target_orange_triple']} sum={f5['target_orange_sum']} "
          f"-> {f5['detail_at_target']}")
    print(f"  全历史 {f5['n']} 期命中率 = {f5['rate']} (基准 {f5['base_rate']}), "
          f"最长连击 {f5['max_run_all_history']}, 截至26279连中 {f5['streak_until_2026279']}")
    print(f"  对 2026280 的预测: 橙球 {f5['target_orange_triple']} 和={f5['target_orange_sum']} "
          f"-> 预测紫球尾数大小={f5['predicted_value']}; 实际2位={f5['actual_purple_ball']} "
          f"-> {f5['actual_value']}  ==> {'命中' if f5['prediction_hit'] else '失败'}")

    # 同一规则但紫球取 1 位（图上 26280 的紫圈画在 1 位）
    f5b = study("图5规则-紫球改1位", "tailsize", 1, (-3, -1, -1), (2, 3, 4))
    out["verified_instances"].append(f5b)
    print(f"  若紫球改画在 1 位: 预测={f5b['predicted_value']} 实际1位={f5b['actual_purple_ball']} "
          f"({f5b['actual_value']}) ==> {'命中' if f5b['prediction_hit'] else '失败'}")

    # ── 2. 图1/2：反解哪个紫球满足"橙=11,6,15 -> 012路2"且已连中9期 ──
    print("\n【图1/图2 规则反解】")
    rows = (-2, -1, -1)
    opos = (3, 2, 4)
    t = P[2026279]
    tri = [draws[t + r][o - 1] for r, o in zip(rows, opos)]
    print(f"  橙球 = {tri}, 和 = {sum(tri)}, 012路 = {sum(tri) % 3}  "
          f"(文本声称 11+6+15=32 -> 2, {'一致' if tri == [11, 6, 15] and sum(tri) % 3 == 2 else '不一致'})")
    cands = []
    for ppos in range(1, 21):
        b, _ = bits_template("r012", ppos, rows, opos)
        s = 0
        j = t - 1
        while j >= 0 and b[j]:
            s += 1
            j -= 1
        valid = [x for x in b if x is not None]
        cands.append({"purple_pos": ppos,
                      "purple_at_26279": draws[t][ppos - 1],
                      "purple_r012": draws[t][ppos - 1] % 3,
                      "matches_now": draws[t][ppos - 1] % 3 == sum(tri) % 3,
                      "streak_until_26278": s,
                      "history_rate": round(sum(valid) / len(valid), 4)})
    out["back_solve_012"] = cands
    for c in sorted(cands, key=lambda x: -x["streak_until_26278"])[:6]:
        print(f"    紫球位次={c['purple_pos']:>2} 26279号={c['purple_at_26279']:02d} "
              f"012路={c['purple_r012']} 当期成立={c['matches_now']} "
              f"已连中={c['streak_until_26278']} 历史命中率={c['history_rate']}")

    # ── 3. 用该橙球定义做样本外裁决（紫球=2位，与图5同形） ──
    print("\n【图1/2 规则的样本外裁决】")
    for ppos in (1, 2):
        r = study(f"图1/2规则-紫{ppos}位", "r012", ppos, rows, opos)
        out["verified_instances"].append(r)
        print(f"  紫球{ppos}位: 全历史命中率={r['rate']} (基准0.3333) 最长连击={r['max_run_all_history']} "
              f"截至26279连中={r['streak_until_2026279']}")
        print(f"    对2026280预测橙球{r['target_orange_triple']}和={r['target_orange_sum']}"
              f"->012路={r['predicted_value']}; 实际{ppos}位={r['actual_purple_ball']:02d}"
              f"->012路={r['actual_value']} ==> {'命中' if r['prediction_hit'] else '失败'}")

    save_json("v5_instances.json", out)
    print("\nsaved v5_instances.json")
