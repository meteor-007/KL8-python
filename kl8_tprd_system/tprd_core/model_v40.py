#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TPRD v4.0 双时间尺度集成推理主脑 (Dual-Window RF & Zero-Blind-Spot Inference Engine)
融合 60期敏捷树 + 240期稳健树、正交六大子空间配额、空间八段守卫与和值走廊
"""

from typing import Dict, List, Any
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from .constants import (
    SUBSPACES, BASE_QUOTA_30, BASE_QUOTA_25, BASE_QUOTA_20,
    WEIGHT_SHORT_WINDOW, WEIGHT_LONG_WINDOW,
    SUM_CORRIDOR_MIN, SUM_CORRIDOR_MAX,
    REPEAT_LOCK_20, REPEAT_LOCK_25, REPEAT_LOCK_30
)
from .matrices import generate_drawer_pick2, generate_dhm_pro_v40


def apply_spatial_guard_30(pool_30: List[int], all_ranked: List[int], scores: Dict[int, float], protected_set: set) -> List[int]:
    """
    四区(6~9码) + 八段10码区间(每段>=2码) 零盲区守卫
    确保全盘 8 个 10 码小段绝对无盲区，消除大底极端空缺
    """
    pool = list(pool_30)

    # 1. 八段零盲区守卫：每 10 码小段 (1-10, 11-20, ..., 71-80) 保底 >= 2 码
    for seg in range(8):
        lo, hi = seg * 10 + 1, seg * 10 + 10
        seg_balls = [n for n in pool if lo <= n <= hi]
        while len(seg_balls) < 2:
            cands = [n for n in all_ranked if lo <= n <= hi and n not in pool]
            zone_cnts = [sum(1 for m in pool if (m - 1) // 20 == z) for z in range(4)]
            max_z = int(np.argmax(zone_cnts))
            drops = sorted([n for n in pool if (n - 1) // 20 == max_z and n not in protected_set], key=lambda x: scores[x])
            if not cands or not drops:
                break
            pool.remove(drops[0])
            pool.append(cands[0])
            seg_balls.append(cands[0])

    # 2. 四区均衡守卫：每个大区限制在 6~9 码之间
    for z in range(4):
        z_balls = sorted([n for n in pool if (n - 1) // 20 == z], key=lambda x: scores[x])
        while len(z_balls) > 9:
            drops = [n for n in z_balls if n not in protected_set]
            cands = [n for n in all_ranked if n not in pool and sum(1 for m in pool if (m - 1) // 20 == (n - 1) // 20) < 7]
            if not drops or not cands:
                break
            pool.remove(drops[0])
            z_balls.remove(drops[0])
            pool.append(cands[0])

    return sorted(pool)


def infer_period_v40(t: int, X: np.ndarray, B: np.ndarray, road_counts: np.ndarray) -> Dict[str, Any]:
    """
    第 t 期全套决策推演 (严格限制使用历史 [0, t-1])
    """
    w_long = min(240, t)

    # 1. 双时间尺度随机森林集成 (45% W=60 + 55% W=240)
    rf_short = RandomForestClassifier(
        n_estimators=80, max_depth=5, min_samples_leaf=10, max_features='sqrt',
        random_state=42, n_jobs=1
    )
    rf_long = RandomForestClassifier(
        n_estimators=80, max_depth=5, min_samples_leaf=12, max_features='sqrt',
        random_state=7, n_jobs=1
    )

    rf_short.fit(X[t - 60:t].reshape(-1, 15), B[t - 60:t, 1:].reshape(-1))
    rf_long.fit(X[t - w_long:t].reshape(-1, 15), B[t - w_long:t, 1:].reshape(-1))

    p_short = rf_short.predict_proba(X[t])[:, 1]
    p_long = rf_long.predict_proba(X[t])[:, 1]
    p_blend = WEIGHT_SHORT_WINDOW * p_short + WEIGHT_LONG_WINDOW * p_long

    # 2. 横截面 Z-Score 标准化与受限辅助微调 (<= 25% 模型标准差)
    z_ml = (p_blend - p_blend.mean()) / (p_blend.std() + 1e-6)
    aux = 0.15 * (X[t, :, 7] == 2.0).astype(np.float32) + 0.10 * ((X[t, :, 4] >= 4.0) & (B[t - 1, 1:] == 1)).astype(np.float32)
    final_z = z_ml + aux
    p_in = (final_z - final_z.min()) / (final_z.max() - final_z.min() + 1e-6)

    scores = {n: float(final_z[n - 1]) for n in range(1, 81)}
    ranked_all = sorted(range(1, 81), key=lambda x: scores[x], reverse=True)

    # 3. 012路宏观动态赤字配额微调
    q30 = dict(BASE_QUOTA_30)
    q25 = dict(BASE_QUOTA_25)
    q20 = dict(BASE_QUOTA_20)

    r_3draw = np.sum(road_counts[t - 3:t], axis=0)
    r_priority = r_3draw + 1.5 * road_counts[t - 1]
    min_r, max_r = int(np.argmin(r_priority)), int(np.argmax(r_priority))
    if r_priority[max_r] - r_priority[min_r] >= 5.0:
        for q in (q30, q25, q20):
            if q[f'S{max_r}_C'] >= 3:
                q[f'S{min_r}_C'] += 1
                q[f'S{max_r}_C'] -= 1

    # 4. 03 号球动态熔断器 (排名 > 35 或两连重时熔断)
    if ranked_all.index(3) + 1 > 35 or (B[t - 1, 3] == 1 and B[t - 2, 3] == 1):
        for q in (q30, q25, q20):
            q['S0_P'] = 0
            q['S0_C'] += 1

    # 5. 子空间配额入选
    pool_30, pool_25, pool_20 = [], [], []
    for k in SUBSPACES:
        cands = sorted(SUBSPACES[k], key=lambda x: scores[x], reverse=True)
        pool_30.extend(cands[:max(0, int(q30[k]))])
        pool_25.extend(cands[:max(0, int(q25[k]))])
        pool_20.extend(cands[:max(0, int(q20[k]))])

    # 6. 012 三路正交金胆 (Top 3) 与 主力五码 (Top 5)
    p20_sorted = sorted(pool_20, key=lambda x: scores[x], reverse=True)
    top3_orthogonal = [next(n for n in p20_sorted if n % 3 == r) for r in (0, 1, 2)]
    top3_orthogonal = sorted(top3_orthogonal, key=lambda x: scores[x], reverse=True)
    top5_leaders = top3_orthogonal + [n for n in p20_sorted if n not in top3_orthogonal][:2]
    top3_set = set(top3_orthogonal)

    # 7. 热重号守恒锁 (对冲 9重号极端突袭)
    hot_repeats = sorted(
        [n for n in range(1, 81) if B[t - 1, n] == 1],
        key=lambda x: (X[t, x - 1, 4] >= 4.0, scores[x]),
        reverse=True
    )
    for pool, min_rep, prot in [
        (pool_20, REPEAT_LOCK_20, top3_set),
        (pool_25, REPEAT_LOCK_25, set(pool_20)),
        (pool_30, REPEAT_LOCK_30, set(pool_25))
    ]:
        cur = [n for n in pool if B[t - 1, n] == 1]
        if len(cur) < min_rep:
            adds = [n for n in hot_repeats if n not in pool]
            drops = sorted([n for n in pool if B[t - 1, n] == 0 and n not in prot], key=lambda x: scores[x])
            for a, d in zip(adds[:min_rep - len(cur)], drops):
                pool.remove(d)
                pool.append(a)

    # 8. 空间零盲区守卫 (四区 6~9 码 + 八段每段 >= 2 码)
    pool_30 = apply_spatial_guard_30(pool_30, ranked_all, scores, set(pool_25))

    # 9. 稳健和值走廊守卫 [760, 860] (按 AI 评分最低换球，禁止死循环与误踢高分小号)
    sorted_30 = sorted(pool_30, key=lambda x: scores[x], reverse=True)
    for _ in range(10):
        s20 = sum(pool_20)
        rem = [n for n in sorted_30 if n not in pool_20]
        rep = [n for n in pool_20 if n not in top3_set]
        if not rem or not rep:
            break
        if s20 < SUM_CORRIDOR_MIN:
            # 和值偏低，淘汰前半区 AI 分最低的球，置换为大于其 10 码的高分区球
            low_candidates = [n for n in rep if n <= 35] or rep
            low_b = min(low_candidates, key=lambda x: scores[x])
            highs = [n for n in rem if n > low_b + 10]
            if not highs:
                break
            pool_20.remove(low_b)
            pool_20.append(highs[0])
        elif s20 > SUM_CORRIDOR_MAX:
            # 和值偏高，淘汰后半区 AI 分最低的球，置换为小于其 10 码的低分区球
            high_candidates = [n for n in rep if n >= 46] or rep
            high_b = min(high_candidates, key=lambda x: scores[x])
            lows = [n for n in rem if n < high_b - 10]
            if not lows:
                break
            pool_20.remove(high_b)
            pool_20.append(lows[0])
        else:
            break

    # 10. 近 100 期共现 Lift (PMI) + 双端量纲对齐选2亲和力场
    sub_b = B[t - 100:t, 1:]
    co = sub_b.T @ sub_b
    np.fill_diagonal(co, 0)
    freq = np.sum(sub_b, axis=0)
    lift_co = (co + 1.0) / ((np.outer(freq, freq) / 100.0) + 1.0)
    aff = co * np.sqrt(lift_co)
    triu = aff[np.triu_indices(80, k=1)]
    aff_norm = (aff - triu.min()) / (triu.max() - triu.min() + 1e-6)
    P_base = 0.55 * ((p_in[:, None] + p_in[None, :]) / 2.0) + 0.45 * aff_norm

    # 11. 组合矩阵生成
    pick2_details = generate_drawer_pick2(top5_leaders, P_base)
    dhm_bets = generate_dhm_pro_v40(pool_30, pool_20, scores)

    return {
        'scores': scores,
        'ranked_all': ranked_all,
        'top5_leaders': top5_leaders,
        'pool_30': sorted(pool_30),
        'pool_25': sorted(pool_25),
        'pool_20': sorted(pool_20),
        'pick2_details': pick2_details,
        'dhm_bets': dhm_bets,
        'p_in': p_in,
        'P_base': P_base
    }
