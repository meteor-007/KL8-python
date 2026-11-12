# -*- coding: utf-8 -*-
"""
定金选2 快乐8 核心算法引擎 (主系统深度整合版 v5.0)
=============================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 核心玩法：快乐8 "选二定胆配对" = 押 金胆 (单码) + 与它配对的 2 码组合。
2. 随机基线：单码 20/80 = 25.0% | 选2组合 (20/80)*(19/79) = 6.01%。
3. 7 维透明特征打分（2026-09-11 优化升级版：高斯回补甜区 + 冷热互补协同）：
   - 高斯遗漏回补甜区 (sweet_om: 0.35) —— 锁定 7~13 期黄金爆发甜区，惩罚 >=16 期极冷死号
   - 线性遗漏基础 (omission: 0.15)     —— 维持宏观遗漏排位
   - 马尔可夫自转移 (markov: 0.20)     —— 上期开出本期再开出的连号动量
   - Bollinger bias (bollinger: 0.15)  —— 近20期活跃频次偏离度
   - 图论耦合中心度 (graph: 0.10)      —— 近40期共现辅助（保留适度轻量噪音分散）
   - 刚开趋势惩罚 (trend: 0.05)        —— 防过度过热追高
4. 双重金胆法与黄金甜区池：
   - 💎 金胆 (加权Z最高, 严格从 7~13 期黄金爆发甜区中精选)
   - 🥇 动能热胆 (上期开出中近20期活跃度与动量最优号码)
5. 冷热对冲双核配对：
   - 以动能热胆为攻矛，搭配最佳黄金回补甜区温号为守盾。
   - 历史水位一律以系统前瞻账现算为准 (见 backend/utils/ledger_stats.py)，
     本文件不再写入"100 期 11.0% / Lift 1.83x"之类未经复核的数字。
6. 主系统多维交叉风控：
   - 与 Trinity、Hidden Energy、重点点位、未开反弹、16期中热交叉打标（仅标签，不改正序）。
"""
from backend.utils.paths import get_cache_dir, get_outputs_dir
import os
import re
import sys
import math
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set

try:
    from backend.utils.paths import get_project_root
    PROJ_DIR = get_project_root()
except Exception:
    curr = os.path.dirname(os.path.abspath(__file__))
    while curr and os.path.dirname(curr) != curr:
        if os.path.exists(os.path.join(curr, "kl8_history_final.txt")) or os.path.exists(os.path.join(curr, "GEMINI.md")):
            break
        curr = os.path.dirname(curr)
    PROJ_DIR = curr

if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

NUM = 80
WIN = 20
GRAPH_WINDOW = 40
BASE_SINGLE = 20 / 80
BASE_PAIR = (20 / 80) * (19 / 79)

# 默认 7 维特征权重 (独立宪法 2026-09-11: graph/共现归零)
DEFAULT_WEIGHTS = {
    "sweet_om": 0.40,
    "omission": 0.15,
    "markov": 0.20,
    "bollinger": 0.15,
    "graph": 0.0,
    "trend": 0.05,
    "signal": 0.05
}


def norm_z(vals: List[float]) -> List[float]:
    """Z-Score 均值方差归一化"""
    if not vals:
        return []
    mu = sum(vals) / len(vals)
    sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1e-9
    return [(v - mu) / sd for v in vals]


def load_draws_from_file(filepath: Optional[str] = None) -> List[Dict[str, Any]]:
    """从开奖历史文件加载规范化开奖数据"""
    if not filepath or not os.path.exists(filepath):
        candidates = [
            os.path.join(PROJ_DIR, "kl8_history_final.txt"),
            os.path.join(PROJ_DIR, "storage", "raw", "kl8_history_final.txt"),
            os.path.join(PROJ_DIR, "data", "kl8_history_final.txt"),
        ]
        for c in candidates:
            if os.path.exists(c):
                filepath = c
                break

    draws = []
    if not filepath or not os.path.exists(filepath):
        return draws

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line.strip())
            if not m:
                continue
            nums = set(int(x) for x in m.group(3).split("-") if x.isdigit())
            if len(nums) == 20:
                draws.append({
                    "period": int(m.group(2)),
                    "date": m.group(1),
                    "nums": nums,
                    "sorted_nums": sorted(list(nums))
                })
    draws.sort(key=lambda d: d["period"])
    return draws


def calculate_gold_pick2_features(
    draws: List[Dict[str, Any]],
    cutoff_idx: Optional[int] = None,
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    用 draws[:cutoff_idx] 预测第 cutoff_idx 期 (无任何未来数据泄露)。
    返回详细打分矩阵、金胆、热号金胆、配对组合、温号池态势。
    """
    if cutoff_idx is None:
        cutoff_idx = len(draws)

    hist = draws[:cutoff_idx]
    nh = len(hist)
    if nh < 30:
        return {}

    w = weights or DEFAULT_WEIGHTS

    flat = [n for s in hist for n in s["nums"]]
    freq_long = Counter(flat)
    recent_idx = range(max(0, nh - WIN), nh)
    freq_recent = Counter(n for i in recent_idx for n in hist[i]["nums"])

    # 1. 马尔可夫自转移率 (上期开出→本期再开出)
    trans, starts = Counter(), Counter()
    for i in range(nh - 1):
        for n in hist[i]["nums"]:
            starts[n] += 1
            if n in hist[i + 1]["nums"]:
                trans[n] += 1
    markov = {n: (trans[n] / starts[n] if starts[n] else 0.0) for n in range(1, NUM + 1)}

    # 2. 遗漏期数 (距上次开出期数)
    last_seen = {}
    for i in range(nh - 1, -1, -1):
        for n in hist[i]["nums"]:
            if n not in last_seen:
                last_seen[n] = i
    gap = {n: (nh - 1 - last_seen[n] if n in last_seen else nh) for n in range(1, NUM + 1)}

    # 3. 图论耦合中心度 (近期 GRAPH_WINDOW 期窗口，避免全史共现锚定)
    gw = min(GRAPH_WINDOW, nh)
    co = Counter()
    for s in hist[-gw:]:
        lst = sorted(list(s["nums"]))
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                co[(lst[i], lst[j])] += 1
    graph = {n: sum(c for (a, b), c in co.items() if a == n or b == n) for n in range(1, NUM + 1)}

    # 4. Z-Score 归一化特征
    gz = norm_z([markov[n] for n in range(1, NUM + 1)])
    nz = norm_z([graph[n] for n in range(1, NUM + 1)])
    oz = norm_z([gap[n] for n in range(1, NUM + 1)])
    bz = norm_z([freq_recent[n] for n in range(1, NUM + 1)])
    lz = norm_z([freq_long[n] for n in range(1, NUM + 1)])
    sz = norm_z([-abs(bz[i] - lz[i]) for i in range(NUM)])

    # 引入高斯钟形遗漏回补甜区 (中心10.0, 方差4.2) 与 >=16期极冷僵尸号惩罚 (x0.6)
    sweet_om = [math.exp(-((gap[n] - 10.0) ** 2) / (2 * 4.2 ** 2)) * (0.6 if gap[n] >= 16 else 1.0) for n in range(1, NUM + 1)]
    soz = norm_z(sweet_om)

    last_draw = hist[-1]["nums"]
    raw_scores = {}
    features_80 = {}
    for i, n in enumerate(range(1, NUM + 1)):
        trend = 1.0 if n in last_draw else 0.0
        # 优化多因子打分: 甜区回补(0.35) + 线性遗漏(0.15) + 马尔可夫连号(0.20) + 近20期频次(0.15) + 图论共现(0.10) - 刚开趋势惩罚(0.05)
        score_val = (
            w.get("sweet_om", 0.35) * soz[i] +
            w.get("omission", 0.15) * oz[i] +
            w.get("markov", 0.20) * gz[i] +
            w.get("bollinger", 0.15) * bz[i] +
            w.get("graph", 0.10) * nz[i] -
            w.get("trend", 0.05) * trend
        )
        raw_scores[n] = score_val
        features_80[n] = {
            "num": n,
            "markov": round(markov[n], 4),
            "graph": graph[n],
            "gap": gap[n],
            "sweet_om": round(sweet_om[i], 4),
            "freq_recent": freq_recent[n],
            "freq_long": freq_long[n],
            "raw_score": round(score_val, 4),
            "in_last_draw": n in last_draw
        }

    # 5. 黄金温号池提取 (2026-09-11 升级为 7~13 期爆发甜区)
    warm = sorted([n for n in range(1, NUM + 1) if 7 <= gap[n] <= 13])
    cand = warm if len(warm) >= 3 else sorted(range(1, NUM + 1), key=lambda n: abs(gap[n] - 10))
    rz = norm_z([raw_scores[n] for n in cand])
    cand_score = {n: rz[i] for i, n in enumerate(cand)}

    # 双重金胆:
    # 💎 核心温号金胆: 7~13期黄金回补甜区中打分第一名
    golden = max(cand, key=lambda n: raw_scores[n])

    # 🥇 动能热胆: 优先在上期开出(gap=0)且近20期活跃(2~5次)的号码中寻找动量最优者
    active_cands = [n for n in last_draw if 2 <= freq_recent[n] <= 5]
    if active_cands:
        hot = max(active_cands, key=lambda n: raw_scores.get(n, 0))
    elif last_draw:
        hot = max(last_draw, key=lambda n: raw_scores.get(n, 0))
    else:
        hot = max(range(1, NUM + 1), key=lambda n: freq_recent[n])

    # 6. 冷热对冲双核配对与多层次搭档生成
    # 6.1 寻找与动能热胆最佳协同的黄金甜区回补温码 (突破 10.53% 盈亏平衡线)
    best_c = None
    best_c_score = -999.0
    for c in cand:
        if c == hot:
            continue
        pt = (min(hot, c), max(hot, c))
        sc = raw_scores[c]
        if sc > best_c_score:
            best_c_score = sc
            best_c = c

    cand_other = [c for c in cand if c != best_c and c != hot]
    cand_other.sort(key=lambda c: raw_scores[c], reverse=True)

    hot_pool = [n for n in last_draw if n != golden and n != hot]
    hot_pool_sorted = sorted(hot_pool, key=lambda h: raw_scores[h], reverse=True)

    # 6.2 构建专属于核心金胆的 Top 5 组合 (契约保障: 每一组均含 golden)
    top5_golden_list = []
    seen_golden = set()
    def add_golden_pair(partner_num, desc):
        if partner_num == golden:
            return False
        pt = (min(golden, partner_num), max(golden, partner_num))
        if pt not in seen_golden:
            seen_golden.add(pt)
            co_cnt = co.get(pt, 0)
            pw = (raw_scores[golden] + raw_scores[partner_num]) / 2.0 + 8.0
            top5_golden_list.append({
                "pair": [pt[0], pt[1]],
                "pair_str": f"{pt[0]:02d}-{pt[1]:02d}",
                "partner": partner_num,
                "co_count": co_cnt,
                "weight": round(pw, 4),
                "is_hot_overlap": bool(partner_num == hot or partner_num in last_draw),
                "desc": desc
            })
            return True
        return False

    # 金胆首选: 与动能热胆对冲共振
    add_golden_pair(hot, "👑 核心金胆 + 动能热胆 (双核共振组合)")
    # 金胆次选: 与上期优质活跃热码搭档
    for h in hot_pool_sorted:
        if add_golden_pair(h, "核心金胆 + 优质活跃热码 (防守共鸣组合)"):
            break
    # 金胆后续: 与甜区回补温码搭档
    for c in cand:
        if add_golden_pair(c, "核心金胆 + 黄金甜区温号 (双温反弹组合)"):
            if len(top5_golden_list) >= 5:
                break
    # 兜底补齐 5 组
    for n in range(1, NUM + 1):
        if len(top5_golden_list) >= 5:
            break
        add_golden_pair(n, "核心金胆 + 全局高频搭档 (稳健组合)")
    top5_golden = top5_golden_list[:5]

    # 6.3 构建专属于动能热胆的 Top 5 组合 (契约保障: 每一组均含 hot)
    top5_hot_list = []
    seen_hot = set()
    def add_hot_pair(partner_num, desc):
        if partner_num == hot:
            return False
        pt = (min(hot, partner_num), max(hot, partner_num))
        if pt not in seen_hot:
            seen_hot.add(pt)
            co_cnt = co.get(pt, 0)
            pw = (raw_scores[hot] + raw_scores[partner_num]) / 2.0 + 8.0
            top5_hot_list.append({
                "pair": [pt[0], pt[1]],
                "pair_str": f"{pt[0]:02d}-{pt[1]:02d}",
                "partner": partner_num,
                "co_count": co_cnt,
                "weight": round(pw, 4),
                "is_hot_overlap": bool(partner_num == golden or partner_num in last_draw),
                "desc": desc
            })
            return True
        return False

    if best_c:
        add_hot_pair(best_c, "🔥 动能热胆 + 黄金回补甜区 (核心主推冷热对冲)")
    for c in cand_other:
        if add_hot_pair(c, "动能热胆 + 次席甜区温号 (进攻对冲组合)"):
            break
    add_hot_pair(golden, "👑 动能热胆 + 核心金胆 (双核共振组合)")
    for c in cand_other:
        if add_hot_pair(c, "动能热胆 + 深度回补温号 (极值对冲组合)"):
            if len(top5_hot_list) >= 5:
                break
    for h in hot_pool_sorted:
        if len(top5_hot_list) >= 5:
            break
        add_hot_pair(h, "双动能热码共振 (全进攻组合)")
    for n in range(1, NUM + 1):
        if len(top5_hot_list) >= 5:
            break
        add_hot_pair(n, "动能热胆 + 全局高频搭档 (进攻组合)")
    top5_hot = top5_hot_list[:5]

    # 6.4 构建多层次综合优选组合 (Top 5 混合互补精选)
    top5_hybrid_list = []
    seen_hybrid = set()
    def add_hybrid_pair(p_item):
        pt = (p_item["pair"][0], p_item["pair"][1])
        if pt not in seen_hybrid:
            seen_hybrid.add(pt)
            top5_hybrid_list.append(p_item)
            return True
        return False

    if top5_hot:
        add_hybrid_pair(top5_hot[0])
    for item in top5_hot[1:]:
        if add_hybrid_pair(item):
            break
    for item in top5_golden:
        if add_hybrid_pair(item):
            if len(top5_hybrid_list) >= 5:
                break
    for item in top5_hot:
        if len(top5_hybrid_list) >= 5:
            break
        add_hybrid_pair(item)
    top5_hybrid = top5_hybrid_list[:5]

    pair_w = {}
    for p in top5_hybrid + top5_golden + top5_hot:
        pt = (p["pair"][0], p["pair"][1])
        pair_w[pt] = p["weight"]

    top3_cand = [golden, hot]
    if top5_hybrid:
        for p in top5_hybrid:
            for b in p["pair"]:
                if b not in top3_cand and len(top3_cand) < 3:
                    top3_cand.append(b)
    while len(top3_cand) < 3:
        for num in cand_score:
            if num not in top3_cand:
                top3_cand.append(num)
                if len(top3_cand) == 3:
                    break

    return {
        "golden": golden,
        "hot": hot,
        "top3_gold": top3_cand[:3],
        "cand_scores": cand_score,
        "raw_scores": raw_scores,
        "features_80": features_80,
        "warm": warm,
        "gap": gap,
        "freq_recent": dict(freq_recent),
        "freq_long": dict(freq_long),
        "co_matrix": {f"{k[0]}-{k[1]}": v for k, v in co.items()},
        "pair_w": {f"{k[0]}-{k[1]}": round(v, 4) for k, v in pair_w.items()},
        "top5_golden": top5_golden,
        "top5_hot": top5_hot,
        "top5_hybrid": top5_hybrid,
        "top5_pairs": top5_hybrid,
        "last_draw": sorted(list(last_draw))
    }


def cross_validate_pick2_picks(proj_dir: str, golden: int, hot: int, top5_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    与主系统多维模型做交叉验证与共振打标
    """
    flags = {
        "golden_in_trinity5": False,
        "golden_in_trinity12": False,
        "golden_in_he5": False,
        "golden_in_spatial_points": False,
        "golden_in_suppression": False,
        "golden_in_sixteen": False,
        "hot_in_trinity": False,
        "pair_resonance_tags": [],
        "safety_audit": "🟢 安全通过 (无高危冲突)"
    }

    # 1. 检查自学习与预测缓存
    cache_file = os.path.join(get_cache_dir(), "self_learning_state.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            t5 = state.get("last_trinity_5", [])
            t12 = state.get("last_trinity_12", [])
            he5 = state.get("last_he_5", [])
            if golden in t5:
                flags["golden_in_trinity5"] = True
            if golden in t12:
                flags["golden_in_trinity12"] = True
            if golden in he5:
                flags["golden_in_he5"] = True
            if hot in t12:
                flags["hot_in_trinity"] = True
        except Exception:
            pass

    # 2. 检查空间重点点位
    pts_file = os.path.join(get_outputs_dir(), "spatial_points", "spatial_points_latest.json")
    if os.path.exists(pts_file):
        try:
            with open(pts_file, "r", encoding="utf-8") as f:
                pdata = json.load(f)
            c5 = pdata.get("picks", {}).get("core_5", [])
            if golden in c5:
                flags["golden_in_spatial_points"] = True
        except Exception:
            pass

    # 3. 检查未开点位反弹（仅标签）
    supp_file = os.path.join(get_outputs_dir(), "point_suppression", "suppression_latest.json")
    if not os.path.exists(supp_file):
        supp_file = os.path.join(get_outputs_dir(), "suppression", "suppression_latest.json")
    if os.path.exists(supp_file):
        try:
            with open(supp_file, "r", encoding="utf-8") as f:
                sdata = json.load(f)
            c3 = sdata.get("picks", {}).get("top3_gold", [])
            if not c3:
                c3 = [c.get("num") for c in (sdata.get("top3_candidates") or []) if isinstance(c, dict)]
            if golden in c3:
                flags["golden_in_suppression"] = True
        except Exception:
            pass

    # 4. 检查 16期中热重叠（替代已退役 LSTM）
    sixteen_cache = os.path.join(get_cache_dir(), "sixteen_period", "latest_summary.json")
    if os.path.exists(sixteen_cache):
        try:
            with open(sixteen_cache, "r", encoding="utf-8") as f:
                s16 = json.load(f)
            top3 = list(s16.get("top3_gold") or s16.get("medium_top5") or s16.get("ops_tip3") or [])[:3]
            if golden in top3 or golden == s16.get("gold_dan"):
                flags["golden_in_sixteen"] = True
        except Exception:
            pass

    return flags
