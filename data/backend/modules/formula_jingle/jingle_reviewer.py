# -*- coding: utf-8 -*-
"""
顺口溜口诀对账复盘与样本外 Lift 审计模块 (Jingle Reviewer)
==========================================================
严格执行「无未来函数对账」：
每一期只用 t-1 期开出的号码去匹配口诀库，然后与 t 期的真实开奖对账。
分为两大分层区间：
1. 规则筛查窗口（≤ 2026210）：存在选择偏差，命中率偏高
2. 真·样本外窗口（> 2026210）：完全未参与规则提取的纯净实战期
"""
from typing import List, Dict, Tuple, Any, Optional
from .jingle_engine import fired_rules, at_least_one_baseline, BASELINE_PAIR, BASELINE_TRIPLE


def review_jingle(
    draws: List[Tuple[int, str, List[int]]],
    rules: List[Dict[str, Any]],
    n: int = 30,
    sel_cut: int = 2026210
) -> Dict[str, Any]:
    """
    近 n 期口诀触发与命中复盘对账。
    """
    if len(draws) < 2:
        return {
            "status": "error",
            "message": "历史期数不足以进行复盘",
            "pairs": [],
            "metrics": {},
        }

    # 取最近 n+1 期数据（用于产生 n 期跨期对账）
    win = draws[-(n + 1):]
    pairs = []

    for t in range(1, len(win)):
        trigger_draw = win[t - 1]
        target_draw = win[t]
        trg_issue, trg_date, trg_nums = trigger_draw
        tgt_issue, tgt_date, tgt_nums = target_draw

        fired = fired_rules(rules, trg_nums)
        if not fired:
            continue

        rec_nums = []
        np_ok = nt_ok = 0
        np_fire = sum(1 for r, *_ in fired if r.get("kind") == "pair_pair")
        nt_fire = sum(1 for r, *_ in fired if r.get("kind") == "triple_single")

        for r, pred, w in fired:
            rec_nums.extend(pred)
            if r.get("kind") == "pair_pair":
                if set(pred) <= set(tgt_nums):
                    np_ok += 1
            else:
                if pred and pred[0] in tgt_nums:
                    nt_ok += 1

        rec_unique = sorted(set(rec_nums))
        hit_set = set(rec_unique) & set(tgt_nums)
        hit_n = len(hit_set)
        at_least_one = (hit_n > 0)
        base_prob = at_least_one_baseline(len(rec_unique))

        pairs.append({
            "trigger_issue": trg_issue,
            "target_issue": tgt_issue,
            "trigger_date": trg_date,
            "target_date": tgt_date,
            "fired_count": len(fired),
            "recommended": rec_unique,
            "hit_numbers": sorted(hit_set),
            "hit_count": hit_n,
            "at_least_one": at_least_one,
            "baseline_prob": round(base_prob, 4),
            "np_ok": np_ok,
            "np_fire": np_fire,
            "nt_ok": nt_ok,
            "nt_fire": nt_fire,
            "is_out_of_sample": (int(trg_issue) > sel_cut),
        })

    if not pairs:
        return {
            "status": "warning",
            "message": f"近 {n} 期内未发现口诀触发记录",
            "pairs": [],
            "metrics": {},
        }

    total_periods = len(pairs)
    total_fired = sum(p["fired_count"] for p in pairs)
    n_at_least_one = sum(1 for p in pairs if p["at_least_one"])
    hit_total = sum(p["hit_count"] for p in pairs)
    rec_total = sum(len(p["recommended"]) for p in pairs)
    np_f_total = sum(p["np_fire"] for p in pairs)
    np_h_total = sum(p["np_ok"] for p in pairs)
    nt_f_total = sum(p["nt_fire"] for p in pairs)
    nt_h_total = sum(p["nt_ok"] for p in pairs)

    avg_baseline = sum(p["baseline_prob"] for p in pairs) / total_periods
    at_rate = n_at_least_one / total_periods
    overall_lift = (at_rate / avg_baseline) if avg_baseline > 0 else 1.0

    # 分层指标计算 (窗口内 vs 真·样本外)
    segments = {}
    for bucket_name, is_oos in [("筛查窗口内(有选择偏差)", False), ("真·样本外(实战验证)", True)]:
        sub = [p for p in pairs if p["is_out_of_sample"] == is_oos]
        if not sub:
            continue
        sub_n = len(sub)
        sub_at = sum(1 for p in sub if p["at_least_one"])
        sub_base = sum(p["baseline_prob"] for p in sub) / sub_n
        sub_at_rate = sub_at / sub_n
        sub_lift = (sub_at_rate / sub_base) if sub_base > 0 else 1.0
        sub_np_h = sum(p["np_ok"] for p in sub)
        sub_np_f = sum(p["np_fire"] for p in sub)
        sub_nt_h = sum(p["nt_ok"] for p in sub)
        sub_nt_f = sum(p["nt_fire"] for p in sub)

        pair_lift = ((sub_np_h / sub_np_f) / BASELINE_PAIR) if sub_np_f > 0 else 0.0
        triple_lift = ((sub_nt_h / sub_nt_f) / BASELINE_TRIPLE) if sub_nt_f > 0 else 0.0

        segments[bucket_name] = {
            "periods": sub_n,
            "fired_rules": sum(p["fired_count"] for p in sub),
            "at_least_one_hits": sub_at,
            "at_least_one_rate": round(sub_at_rate, 4),
            "baseline_rate": round(sub_base, 4),
            "lift": round(sub_lift, 2),
            "pair_hits": sub_np_h,
            "pair_fires": sub_np_f,
            "pair_rate": round(sub_np_h / sub_np_f, 4) if sub_np_f > 0 else 0.0,
            "pair_lift": round(pair_lift, 2),
            "triple_hits": sub_nt_h,
            "triple_fires": sub_nt_f,
            "triple_rate": round(sub_nt_h / sub_nt_f, 4) if sub_nt_f > 0 else 0.0,
            "triple_lift": round(triple_lift, 2),
        }

    metrics = {
        "review_periods": n,
        "valid_trigger_periods": total_periods,
        "total_rules_fired": total_fired,
        "avg_rec_per_period": round(rec_total / total_periods, 2),
        "avg_hit_per_period": round(hit_total / total_periods, 2),
        "at_least_one_hits": n_at_least_one,
        "at_least_one_rate": round(at_rate, 4),
        "baseline_rate": round(avg_baseline, 4),
        "overall_lift": round(overall_lift, 2),
        "pair_stats": {
            "hits": np_h_total,
            "fires": np_f_total,
            "rate": round(np_h_total / np_f_total, 4) if np_f_total > 0 else 0.0,
            "lift": round((np_h_total / np_f_total) / BASELINE_PAIR, 2) if np_f_total > 0 else 0.0,
        },
        "triple_stats": {
            "hits": nt_h_total,
            "fires": nt_f_total,
            "rate": round(nt_h_total / nt_f_total, 4) if nt_f_total > 0 else 0.0,
            "lift": round((nt_h_total / nt_f_total) / BASELINE_TRIPLE, 2) if nt_f_total > 0 else 0.0,
        },
        "segments": segments,
    }

    return {
        "status": "ok",
        "pairs": pairs,
        "metrics": metrics,
    }
