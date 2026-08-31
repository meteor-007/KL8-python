# -*- coding: utf-8 -*-
"""
跟随分析 (重复号追踪与多窗条件跟随) 核心计算引擎 v3.0 (主系统整合版)
====================================================================
大白话执行协议：
1. 重复号追踪 (Top 5 主候选):
   昨天开出的 20 个号码，逐个计算历史自重复率（上期开出 -> 下期连庄再开出）。
   采用贝叶斯平滑 (ALPHA=2.0, BASE_RATE=0.25) 计算超额倍数 Lift。
2. 综合推演 (Top 6 伙伴跟随):
   严格排除上期已开号码。
   单号 Lift (自重复率 30%) + 双号 Lift (当期共现伙伴下期跟随率 70%) 综合加权 × 遗漏欲出度。
3. 条件跟随 (Top 8 多窗软融合):
   提取上期 20 码内部历史共现频次最高的 Top 5 黄金条件对 (A, B)。
   在 4 个时间窗口 (100 / 200 / 300 / 500 期) 中统计 "同时开出 (A, B) -> 下一期跟随号码" 频次。
   计算 >= 3 窗交集，并采用 RRF (Reciprocal Rank Fusion, 1 / (60 + rank)) 软融合跨条件聚合。
4. 双重交集确认 (Resonance Intersection):
   提取重复号 Top 5 与综合推演 Top 6 / 条件跟随 Top 8 的交集号码。
"""
import os
import re
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

NUM_BALLS = 80
BASE_RATE = 20 / 80                    # 0.25 单码理论基准概率
ALPHA = 2.0                            # 贝叶斯平滑先验权重
WINDOWS = [100, 200, 300, 500]         # 多窗口共现历史跨度
N_CONDS = 5                            # 条件对数量
BASELINE_REPEAT_TOP5 = 5 * BASE_RATE   # 1.25 码
BASELINE_INFERENCE_TOP6 = 6 * BASE_RATE # 1.50 码
BASELINE_FOLLOW_TOP8 = 8 * BASE_RATE   # 2.00 码


def load_draws_from_history(history_path: str) -> List[Dict[str, Any]]:
    """
    从指定文件加载开奖历史数据
    返回升序排列列表: [{'period': int, 'date': str, 'nums': set[int], 'num_list': list[int]}]
    """
    if not os.path.exists(history_path):
        return []
    
    draws = []
    with open(history_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line)
            if not m:
                continue
            nums = [int(x) for x in m.group(3).split("-") if x.isdigit()]
            if len(nums) == 20:
                draws.append({
                    "period": int(m.group(2)),
                    "date": m.group(1),
                    "nums": set(nums),
                    "num_list": sorted(nums)
                })
    draws.sort(key=lambda d: d["period"])
    return draws


def bayesian_smooth(hits: int, n: int, base: float = BASE_RATE, alpha: float = ALPHA) -> float:
    """贝叶斯平滑概率估计"""
    return (hits + alpha * base) / (n + alpha) if n else base


def calculate_history_repeat_avg(draws: List[Dict[str, Any]]) -> float:
    """计算全历史相邻两期重复开出号码数量均值 (理论基准期望 20 * 25% = 5.0)"""
    if len(draws) < 2:
        return 5.0
    repeats = [len(draws[i]["nums"] & draws[i + 1]["nums"]) for i in range(len(draws) - 1)]
    return sum(repeats) / len(repeats) if repeats else 5.0


def repeat_analysis(draws: List[Dict[str, Any]], cutoff_idx: Optional[int] = None) -> Dict[str, Any]:
    """
    ① 重复号分析 (连庄追踪):
    基于截止期之前的历史数据（严格无未来函数），对最新一期开出的 20 个号码计算历史自重复率。
    """
    hist = draws[:cutoff_idx] if cutoff_idx is not None else draws
    if len(hist) < 2:
        return {"top5": [], "rates": {}, "hist_avg_repeat": 5.0, "last_repeat": 0, "details": []}
    
    last_nums = hist[-1]["nums"]
    prev_draws = hist[:-1]
    
    # 历史平均连庄数
    repeats = [len(prev_draws[i]["nums"] & prev_draws[i + 1]["nums"]) for i in range(len(prev_draws) - 1)]
    hist_avg = sum(repeats) / len(repeats) if repeats else 5.0
    last_repeat = len(prev_draws[-1]["nums"] & last_nums) if prev_draws else 0
    
    # 统计历史所有相邻期: 号码 n 在期 t 开出 -> 期 t+1 是否连庄再开
    cnt = Counter()
    hit = Counter()
    for i in range(len(prev_draws) - 1):
        cur_set = prev_draws[i]["nums"]
        nxt_set = prev_draws[i + 1]["nums"]
        for n in cur_set:
            cnt[n] += 1
            if n in nxt_set:
                hit[n] += 1
                
    rates = {}
    details = []
    for n in sorted(last_nums):
        c = cnt.get(n, 0)
        h = hit.get(n, 0)
        prob = bayesian_smooth(h, c)
        lift = prob / BASE_RATE
        rates[n] = lift
        details.append({
            "ball": n,
            "display": f"{n:02d}",
            "historical_draws": c,
            "repeat_hits": h,
            "prob": round(prob, 4),
            "lift": round(lift, 3)
        })
        
    details.sort(key=lambda x: -x["lift"])
    top5 = [d["ball"] for d in details[:5]]
    
    return {
        "top5": top5,
        "top5_str": "-".join(f"{x:02d}" for x in top5),
        "rates": rates,
        "hist_avg_repeat": round(hist_avg, 2),
        "last_repeat": last_repeat,
        "details": details
    }


def _normalize(vals: List[float]) -> List[float]:
    """Z-score 标准化"""
    if not vals:
        return []
    mu = sum(vals) / len(vals)
    sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1e-9
    return [(v - mu) / sd for v in vals]


def inference_top6(draws: List[Dict[str, Any]], cutoff_idx: Optional[int] = None) -> Dict[str, Any]:
    """
    ② 综合推演 (搭档跟随):
    排除最新一期已开出的 20 个号码，根据单号自重复 Lift (30%) + 双号伙伴跟随 Lift (70%) × 遗漏欲出度。
    """
    hist = draws[:cutoff_idx] if cutoff_idx is not None else draws
    recent = hist[-300:] if len(hist) >= 300 else hist
    if len(recent) < 30:
        return {"top6": [], "top6_str": "", "scores": {}, "details": []}
    
    last_nums = recent[-1]["nums"]
    cnt = Counter()
    self_nxt = Counter()
    occ = Counter()          # (n, m) 当期共现
    nxt_pair = Counter()     # (n, m) 当期共现且下期 m 开出
    
    for i in range(len(recent) - 1):
        cur_set = recent[i]["nums"]
        nxt_set = recent[i + 1]["nums"]
        for n in cur_set:
            cnt[n] += 1
            if n in nxt_set:
                self_nxt[n] += 1
            for m in cur_set:
                if m == n:
                    continue
                occ[(n, m)] += 1
                if m in nxt_set:
                    nxt_pair[(n, m)] += 1
                    
    single_lift = {}
    for n in range(1, NUM_BALLS + 1):
        p = bayesian_smooth(self_nxt.get(n, 0), cnt.get(n, 0))
        single_lift[n] = p / BASE_RATE
        
    double_lift = {}
    for n in range(1, NUM_BALLS + 1):
        tot_w, tot_c = 0.0, 0
        for m in range(1, NUM_BALLS + 1):
            c = occ.get((n, m), 0)
            if c > 0:
                p = bayesian_smooth(nxt_pair.get((n, m), 0), c)
                tot_w += p * c
                tot_c += c
        double_lift[n] = (tot_w / tot_c / BASE_RATE) if tot_c else 1.0
        
    # 计算当前各号码遗漏值
    gap = {}
    for n in range(1, NUM_BALLS + 1):
        g = len(recent)
        for i in range(len(recent) - 1, -1, -1):
            if n in recent[i]["nums"]:
                g = len(recent) - 1 - i
                break
        gap[n] = g
    avg_gap = sum(gap.values()) / NUM_BALLS if gap else 4.0
    
    sl_norm = _normalize([single_lift[n] for n in range(1, NUM_BALLS + 1)])
    dl_norm = _normalize([double_lift[n] for n in range(1, NUM_BALLS + 1)])
    
    scores = {}
    details = []
    for idx, n in enumerate(range(1, NUM_BALLS + 1)):
        if n in last_nums:
            scores[n] = -9999.0
            continue
        desire = max(0.7, min(1.5, gap[n] / avg_gap if avg_gap > 0 else 1.0))
        sc = (0.30 * sl_norm[idx] + 0.70 * dl_norm[idx]) * (0.82 + 0.18 * desire)
        scores[n] = sc
        details.append({
            "ball": n,
            "display": f"{n:02d}",
            "single_lift": round(single_lift[n], 3),
            "double_lift": round(double_lift[n], 3),
            "gap": gap[n],
            "desire": round(desire, 3),
            "score": round(sc, 4)
        })
        
    details.sort(key=lambda x: -x["score"])
    top6 = [d["ball"] for d in details[:6]]
    
    return {
        "top6": top6,
        "top6_str": "-".join(f"{x:02d}" for x in top6),
        "scores": scores,
        "details": details[:15]
    }


def conditional_follow(draws: List[Dict[str, Any]], cutoff_idx: Optional[int] = None,
                       windows: List[int] = WINDOWS, n_conds: int = N_CONDS) -> Dict[str, Any]:
    """
    ③ 条件跟随 (多窗交集与 RRF 软融合):
    提取上期开出的 20 个号码中历史共现最强的 Top 5 黄金条件对 (A, B)。
    在 100/200/300/500 四个历史窗口中回溯 "开出 (A, B) -> 下一期跟随开出哪些号码"。
    """
    hist = draws[:cutoff_idx] if cutoff_idx is not None else draws
    if len(hist) < 50:
        return {"top8": [], "top8_str": "", "cross_scores": {}, "cond_info": []}
    
    last_nums = sorted(list(hist[-1]["nums"]))
    recent500 = hist[-500:] if len(hist) >= 500 else hist
    
    # 统计历史共现频次挑出 Top 5 黄金条件对
    pair_occ = Counter()
    for s in recent500:
        sl = s["num_list"]
        for i in range(len(sl)):
            for j in range(i + 1, len(sl)):
                pair_occ[(sl[i], sl[j])] += 1
                
    cond_candidates = []
    for i in range(len(last_nums)):
        for j in range(i + 1, len(last_nums)):
            p_key = (last_nums[i], last_nums[j])
            cond_candidates.append((last_nums[i], last_nums[j], pair_occ.get(p_key, 0)))
            
    cond_candidates.sort(key=lambda c: -c[2])
    selected_conds = cond_candidates[:n_conds]
    
    cross_rrf = defaultdict(float)
    cond_info = []
    
    for a, b, occ_count in selected_conds:
        followers_by_w = []
        for w in windows:
            win_draws = recent500[-w:] if len(recent500) >= w else recent500
            fc = Counter()
            for k in range(len(win_draws) - 1):
                cur_nums = win_draws[k]["nums"]
                if a in cur_nums and b in cur_nums:
                    for x in win_draws[k + 1]["nums"]:
                        fc[x] += 1
            top8_for_w = [x for x, _ in fc.most_common(8)]
            followers_by_w.append({"window": w, "top8": top8_for_w, "top8_str": "-".join(f"{x:02d}" for x in top8_for_w)})
            
            # RRF (Reciprocal Rank Fusion) 软融合计分
            for rank, x in enumerate(top8_for_w, 1):
                cross_rrf[x] += 1.0 / (60 + rank)
                
        # 计算 >= 3 窗口交集
        all_followers = [set(fw["top8"]) for fw in followers_by_w]
        union_all = set().union(*all_followers) if all_followers else set()
        inter3 = [x for x in union_all if sum(1 for fw in followers_by_w if x in fw["top8"]) >= 3]
        inter3.sort(key=lambda x: -cross_rrf[x])
        
        cond_info.append({
            "pair": [a, b],
            "pair_str": f"{a:02d}+{b:02d}",
            "historical_occ": occ_count,
            "windows_detail": followers_by_w,
            "inter3": inter3,
            "inter3_str": "-".join(f"{x:02d}" for x in inter3) if inter3 else "无"
        })
        
    top8_sorted = sorted(cross_rrf.keys(), key=lambda n: -cross_rrf[n])[:8]
    
    return {
        "top8": top8_sorted,
        "top8_str": "-".join(f"{x:02d}" for x in top8_sorted),
        "cross_scores": {k: round(v, 4) for k, v in cross_rrf.items()},
        "cond_info": cond_info
    }


def daily_follow_picks(draws: List[Dict[str, Any]], cutoff_idx: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    统一提炼当日跟随分析综合决策包
    """
    hist = draws[:cutoff_idx] if cutoff_idx is not None else draws
    if len(hist) < 30:
        return None
    
    rep = repeat_analysis(hist)
    inf = inference_top6(hist)
    cf = conditional_follow(hist)
    
    # 黄金共振双重交集确认号 (重复号 Top 5 与 综合推演/条件跟随的交集)
    inter_set = set(rep["top5"]) & (set(inf["top6"]) | set(cf["top8"]))
    inter_nums = sorted(list(inter_set))
    
    latest_draw = hist[-1]
    target_period = latest_draw["period"] + 1
    
    return {
        "latest_period": latest_draw["period"],
        "latest_date": latest_draw["date"],
        "target_period": target_period,
        "repeat": rep,
        "inference": inf,
        "conditional": cf,
        "resonance_intersection": inter_nums,
        "resonance_str": "-".join(f"{x:02d}" for x in inter_nums) if inter_nums else "无",
        "timestamp": datetime.now().isoformat()
    }
