# -*- coding: utf-8 -*-
"""
定金选2 快乐8 核心算法引擎 (主系统深度整合版 v5.0)
=============================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 核心玩法：快乐8 "选二定胆配对" = 押 金胆 (单码) + 与它配对的 2 码组合。
2. 随机基线：单码 20/80 = 25.0% | 选2组合 (20/80)*(19/79) = 6.01%。
3. 7 维透明特征打分：
   - 马尔可夫自转移 (markov: 0.226) —— 看连号自转移率
   - 图论耦合中心度 (graph: 0.431)  —— 近40期共现帮派中心度
   - 遗漏回归 (omission: 0.133)    —— 遗漏4-8期温号池回补
   - Bollinger bias (bollinger: 0.130) —— 近20期频次偏离
   - 趋势惩罚 (trend: 0.048)        —— 上期刚开扣分防追高
   - 信号平衡 (signal: 0.032)       —— 长期与近期偏离稳定性
4. 双重金胆法：
   - 💎 金胆 (加权Z最高, 优先从遗漏4-8期温号池中精选)
   - 🥇 热号金胆 (近20期最热号码, 旁证对齐)
5. 条件共现配对：
   - 以金胆为核，依据条件共现强度与双核得分生成 Top 5 选2组合。
6. 主系统多维交叉风控：
   - 与 Trinity、Hidden Energy、重点点位、未开反弹、KillSeeker杀号、双层LSTM交叉打标。
"""
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

# 默认 7 维特征权重
DEFAULT_WEIGHTS = {
    "markov": 0.226,
    "graph": 0.431,
    "omission": 0.133,
    "bollinger": 0.130,
    "trend": 0.048,
    "signal": 0.032
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

    last_draw = hist[-1]["nums"]
    raw_scores = {}
    features_80 = {}
    for i, n in enumerate(range(1, NUM + 1)):
        trend = 1.0 if n in last_draw else 0.0
        score_val = (
            w.get("markov", 0.226) * gz[i] +
            w.get("graph", 0.431) * nz[i] +
            w.get("omission", 0.133) * oz[i] +
            w.get("bollinger", 0.130) * bz[i] +
            w.get("signal", 0.032) * sz[i] -
            w.get("trend", 0.048) * trend
        )
        raw_scores[n] = score_val
        features_80[n] = {
            "num": n,
            "markov": round(markov[n], 4),
            "graph": graph[n],
            "gap": gap[n],
            "freq_recent": freq_recent[n],
            "freq_long": freq_long[n],
            "raw_score": round(score_val, 4),
            "in_last_draw": n in last_draw
        }

    # 5. 温号池提取 (遗漏 4-8 期)
    warm = sorted([n for n in range(1, NUM + 1) if 4 <= gap[n] <= 8])
    cand = warm if len(warm) >= 3 else sorted(range(1, NUM + 1), key=lambda n: gap[n])
    rz = norm_z([raw_scores[n] for n in cand])
    cand_score = {n: rz[i] for i, n in enumerate(cand)}

    # 双重金胆
    golden = max(cand, key=lambda n: cand_score[n])
    hot = max(last_draw, key=lambda n: freq_recent[n]) if last_draw else max(range(1, NUM + 1), key=lambda n: freq_recent[n])

    # 6. 条件共现强度与双核配对
    pair_w = {}
    for a in range(1, NUM + 1):
        for b in range(a + 1, NUM + 1):
            denom = min(freq_long[a], freq_long[b]) + 1
            cr = co.get((a, b), 0) / denom
            pair_w[(a, b)] = 0.5 * cr + 0.5 * (cand_score.get(a, 0.0) + cand_score.get(b, 0.0)) / 2

    def top_pairs(center: int, k: int = 5) -> List[Dict[str, Any]]:
        pairs = []
        for a in range(1, NUM + 1):
            for b in range(a + 1, NUM + 1):
                if a == center or b == center:
                    partner = b if a == center else a
                    pairs.append({
                        "pair": [a, b],
                        "pair_str": f"{a:02d}-{b:02d}",
                        "partner": partner,
                        "co_count": co.get((a, b), 0),
                        "weight": round(pair_w[(a, b)], 4),
                        "is_hot_overlap": bool(a == hot or b == hot)
                    })
        pairs.sort(key=lambda x: -x["weight"])
        return pairs[:k]

    top5_golden = top_pairs(golden, 5)
    top5_hot = top_pairs(hot, 5)

    return {
        "golden": golden,
        "hot": hot,
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
        "golden_killed_by_killseeker": False,
        "golden_in_lstm": False,
        "hot_in_trinity": False,
        "pair_resonance_tags": [],
        "safety_audit": "🟢 安全通过 (无高危冲突)"
    }

    # 1. 检查自学习与预测缓存
    cache_file = os.path.join(proj_dir, "cache", "self_learning_state.json")
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
    pts_file = os.path.join(proj_dir, "outputs", "spatial_points", "spatial_points_latest.json")
    if os.path.exists(pts_file):
        try:
            with open(pts_file, "r", encoding="utf-8") as f:
                pdata = json.load(f)
            c5 = pdata.get("picks", {}).get("core_5", [])
            if golden in c5:
                flags["golden_in_spatial_points"] = True
        except Exception:
            pass

    # 3. 检查未开点位反弹
    supp_file = os.path.join(proj_dir, "outputs", "suppression", "suppression_latest.json")
    if os.path.exists(supp_file):
        try:
            with open(supp_file, "r", encoding="utf-8") as f:
                sdata = json.load(f)
            c3 = sdata.get("picks", {}).get("top3_gold", [])
            if golden in c3:
                flags["golden_in_suppression"] = True
        except Exception:
            pass

    # 4. 检查 KillSeeker 杀号
    kill_file = os.path.join(proj_dir, "outputs", "killseeker", "kill_decision_latest.json")
    if os.path.exists(kill_file):
        try:
            with open(kill_file, "r", encoding="utf-8") as f:
                kdata = json.load(f)
            kills = kdata.get("kills_core_25", [])
            if golden in kills:
                flags["golden_killed_by_killseeker"] = True
                flags["safety_audit"] = f"⚠️ 警报：金胆 {golden:02d} 落入 KillSeeker 25码杀号区，建议轻仓防御！"
        except Exception:
            pass

    # 5. 检查 LSTM 预测
    lstm_dir = os.path.join(proj_dir, "outputs", "predictions")
    if os.path.exists(lstm_dir):
        txts = sorted([f for f in os.listdir(lstm_dir) if f.startswith("prediction_") and f.endswith(".txt")], reverse=True)
        if txts:
            try:
                with open(os.path.join(lstm_dir, txts[0]), "r", encoding="utf-8") as f:
                    content = f.read()
                nums = [int(x) for x in re.findall(r"\b([0-8]?[0-9])\b", content)]
                if golden in nums[:10]:
                    flags["golden_in_lstm"] = True
            except Exception:
                pass

    return flags
