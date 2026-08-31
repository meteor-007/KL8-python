# -*- coding: utf-8 -*-
"""
Gemini 选2预测 K8-Quant 快乐8 核心算法引擎 v3.0 (主系统整合版)
================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 算子1 空间张力 (spatial) —— 8大区间(01-10..71-80)真空(0个)重仓填坑 / 过载(≥5个)做空
2. 算子2 尾数熵   (tail)    —— 尾数(0-9)全灭补偿 / 极值(≥5)做空 / 连续2期锁死防接飞刀
3. 算子3 马尔可夫扩散 (diffuse) —— 大热号群热惯性向 ±1、±2 边码渗透溢出
4. 算子4 共现社区 (community) —— 近期共现帮派评分 + 对子号(11-77)异象杀补
5. 算子5 动量 (momentum) —— 上期热号火炉不熄延续性加分

输出矩阵：
- 金胆 Top 1 / 银胆 Top 2 / 铜胆 Top 3
- 核心 4 码主推组 (Core 4)
- 终极 5 码防线组 (Def 5)
- 铁血纪律区 (做空坚决排除)
- 今日物理异象提取 (Anomalies)
"""
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 路径管理：基于 data/ 根目录
ENGINE_DIR = Path(__file__).resolve().parent
DATA_ROOT = ENGINE_DIR.parent
DEFAULT_HISTORY_FILE = DATA_ROOT / "kl8_history_final.txt"
OUTPUT_DIR = ENGINE_DIR / "output"
MEMORY_DIR = ENGINE_DIR / "memory"

for _d in [OUTPUT_DIR, MEMORY_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

NUM = 80
WIN = 30                       # 近期滑动窗口
TWINS = {n: n for n in range(11, 78, 11)}   # 对子号 11..77
W = {
    "spatial": 0.28,
    "tail": 0.22,
    "diffuse": 0.24,
    "community": 0.16,
    "momentum": 0.10
}  # 5大算子权重
BASE_SINGLE = 20 / 80          # 0.25 单码理论开出率基线


def norm_z(vals: List[float]) -> List[float]:
    """Z-Score 均值方差归一化"""
    mu = sum(vals) / len(vals)
    sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1e-9
    return [(v - mu) / sd for v in vals]


def load_draws(history_file: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """从历史开奖文件载入数据"""
    hf = Path(history_file) if history_file else DEFAULT_HISTORY_FILE
    draws = []
    if not hf.exists():
        return draws

    with open(hf, "r", encoding="utf-8", errors="ignore") as f:
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


def bin_of(n: int) -> int:
    """计算号码所在10码区间 (1..8)"""
    return (n - 1) // 10 + 1


def tail_of(n: int) -> int:
    """计算号码尾数 (0..9)"""
    return n % 10


def neighbor_spill(last: Set[int], recent_nums: List[Set[int]], n: int) -> Tuple[int, float]:
    """邻域能量溢出计算"""
    spill = 0
    for d in (1, 2):
        for m in (n + d, n - d):
            if 1 <= m <= NUM:
                for s in recent_nums[-2:]:
                    if m in s:
                        spill += 1
    mom = 1.0 if n in last else 0.0
    return spill, mom


def operator_vectors(hist: List[Dict[str, Any]], last: Set[int], recent: List[Dict[str, Any]]) -> Tuple[Dict[str, List[float]], List[Tuple[str, str]], Counter, Counter]:
    """5大算子特征提取"""
    recent_nums = [s["nums"] for s in recent]
    n_recent = len(recent_nums)

    # 1. 空间张力
    bin_last = Counter(bin_of(x) for x in last)
    bin_prev = Counter(bin_of(x) for x in hist[-2]["nums"])
    hist_bin_means = [Counter(bin_of(x) for x in s) for s in recent_nums]
    sp = {}
    for b in range(1, 9):
        mean = sum(hb.get(b, 0) for hb in hist_bin_means) / n_recent
        vac2 = bin_last.get(b, 0) == 0 and bin_prev.get(b, 0) == 0
        for n in range((b - 1) * 10 + 1, b * 10 + 1):
            s = 0.0
            if bin_last.get(b, 0) == 0:
                s += 1.0 + (1.0 if vac2 else 0.0)
            if bin_last.get(b, 0) >= 5:
                s -= 1.5
            s += (mean - bin_last.get(b, 0)) / 5.0
            sp[n] = s
    spatial = norm_z([sp[n] for n in range(1, NUM + 1)])

    # 2. 尾数香农熵
    tail_last = Counter(tail_of(x) for x in last)
    tail_prev = Counter(tail_of(x) for x in hist[-2]["nums"])
    tl = {}
    for t in range(10):
        lock2 = tail_last.get(t, 0) == 0 and tail_prev.get(t, 0) == 0
        for n in range(1, NUM + 1):
            if tail_of(n) != t:
                continue
            s = 0.0
            if tail_last.get(t, 0) == 0:
                s += 0.9 if lock2 else 1.3
            if tail_last.get(t, 0) >= 5:
                s -= 1.5
            if tail_last.get(t, 0) == 0 and tail_prev.get(t, 0) > 0:
                s += 0.4
            tl[n] = s
    tail = norm_z([tl[n] for n in range(1, NUM + 1)])

    # 3. 马尔可夫邻居扩散
    df = {}
    for n in range(1, NUM + 1):
        spill, _ = neighbor_spill(last, recent_nums, n)
        df[n] = spill
    diffuse = norm_z([df[n] for n in range(1, NUM + 1)])

    # 4. 共现社区 + 对子异象
    co = Counter()
    for s in recent_nums:
        lst = sorted(s)
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                co[(lst[i], lst[j])] += 1
    cm = {}
    for n in range(1, NUM + 1):
        s = 0.0
        for m in last:
            s += co.get((min(n, m), max(n, m)), 0)
        cm[n] = s

    drawn_twins = [t for t in TWINS if t in last]
    if len(drawn_twins) >= 4:
        for t in TWINS:
            if t in drawn_twins:
                cm[t] -= 5.0
            else:
                cm[t] += 3.0
    community = norm_z([cm[n] for n in range(1, NUM + 1)])

    # 5. 动量
    mt = {}
    for n in range(1, NUM + 1):
        mt[n] = 1.0 if n in last else 0.0
    momentum = norm_z([mt[n] for n in range(1, NUM + 1)])

    vecs = {
        "spatial": spatial,
        "tail": tail,
        "diffuse": diffuse,
        "community": community,
        "momentum": momentum
    }

    anomalies = []
    for b in range(1, 9):
        c = bin_last.get(b, 0)
        if c == 0:
            anomalies.append(("空间真空", f"{(b-1)*10+1:02d}-{b*10:02d}区 0个 (大裂谷)"))
        elif c >= 5:
            anomalies.append(("空间过载", f"{(b-1)*10+1:02d}-{b*10:02d}区 {c}个 (严重超载)"))
    for t in range(10):
        c = tail_last.get(t, 0)
        if c == 0:
            anomalies.append(("尾数湮灭", f"{t}尾 0个 (全灭补偿)"))
        elif c >= 5:
            anomalies.append(("尾数极值", f"{t}尾 {c}个 (极值做空)"))
    if len(drawn_twins) >= 4:
        anomalies.append(("对子异象", f"对子{len(drawn_twins)}个: {'-'.join('%02d'%t for t in sorted(drawn_twins))}"))

    return vecs, anomalies, bin_last, tail_last


def daily_picks(draws: List[Dict[str, Any]], t: int) -> Optional[Dict[str, Any]]:
    """无未来函数：基于 draws[:t] 预测第 t 期"""
    hist = draws[:t]
    if len(hist) < 40:
        return None
    last = hist[-1]["nums"]
    recent = hist[-WIN:]
    vecs, anomalies, bin_last, tail_last = operator_vectors(hist, last, recent)

    order = list(range(1, NUM + 1))
    score = {}
    for n in order:
        score[n] = sum(W[k] * vecs[k][n - 1] for k in W)

    kill = set()
    for b in range(1, 9):
        if bin_last.get(b, 0) >= 5:
            kill |= set(range((b - 1) * 10 + 1, b * 10 + 1))
    for t_idx in range(10):
        if tail_last.get(t_idx, 0) >= 5:
            kill |= {n for n in range(1, NUM + 1) if tail_of(n) == t_idx}

    def pick_diverse(k: int, forbid=()) -> List[int]:
        picked = []
        for _ in range(k):
            best, bs = None, -1e18
            for n in order:
                if n in picked or n in forbid:
                    continue
                pen = 0.0
                for p in picked:
                    d = min(abs(n - p), NUM - abs(n - p))
                    if d <= 2:
                        pen += 3.0 - d
                    elif d <= 5:
                        pen += 0.8
                    if bin_of(n) == bin_of(p):
                        pen += 0.3
                v = score[n] - pen
                if v > bs:
                    best, bs = n, v
            picked.append(best)
        return picked

    three = pick_diverse(3)
    core4 = pick_diverse(4)
    def5 = pick_diverse(5)

    return {
        "score": score,
        "vecs": vecs,
        "anomalies": anomalies,
        "dans": three,
        "gold": three[0],
        "silver": three[1],
        "bronze": three[2],
        "core4": core4,
        "def5": def5,
        "kill": sorted(kill)
    }


def oof_stats(draws: List[Dict[str, Any]], k: int = 30) -> Dict[str, Any]:
    """Walk-Forward 滚动无泄露实测评估"""
    m = len(draws)
    lo = max(0, m - k)
    op_hit = Counter()
    op_n = Counter()
    gold = silver = bronze = any_dan = 0
    c4_hits = 0
    d5_hits = 0
    n = 0
    for t in range(lo, m):
        p = daily_picks(draws, t)
        if not p:
            continue
        act = draws[t]["nums"]
        g, s, b = p["gold"], p["silver"], p["bronze"]
        if g in act: gold += 1
        if s in act: silver += 1
        if b in act: bronze += 1
        if act & {g, s, b}: any_dan += 1
        c4_hits += len(set(p["core4"]) & act)
        d5_hits += len(set(p["def5"]) & act)
        for op in W:
            vec = p["vecs"][op]
            pick = max(range(1, NUM + 1), key=lambda x: vec[x - 1])
            op_hit[op] += 1 if pick in act else 0
            op_n[op] += 1
        n += 1
    return {
        "n": n,
        "gold": gold,
        "silver": silver,
        "bronze": bronze,
        "any": any_dan,
        "c4": c4_hits,
        "d5": d5_hits,
        "op_hit": dict(op_hit),
        "op_n": dict(op_n)
    }


def get_confidence_badge(g_rate: float, n: int) -> Tuple[str, float, float]:
    """计算置信等级与 Z-Score"""
    p = BASE_SINGLE
    se = (p * (1 - p) / n) ** 0.5 if n > 0 else 1.0
    z = (g_rate - p) / se if se else 0.0
    lift = g_rate / p if p > 0 else 1.0
    if lift >= 1.20 and z >= 1.64:
        return "🟢 高置信 (Level 1)", z, lift
    if lift >= 1.00 and z >= 0.84:
        return "🟡 中置信 (Level 2)", z, lift
    return "🔴 观望 (Level 3)", z, lift


def get_latest_summary(history_file: Optional[Path | str] = None) -> Dict[str, Any]:
    """获取最新一期的 Gemini 选2预测数据"""
    draws = load_draws(history_file)
    if not draws:
        return {"status": "error", "message": "无法加载开奖历史"}

    m = len(draws)
    latest = draws[-1]
    target = latest["period"] + 1

    # 生成预测
    p = daily_picks(draws, m)
    st = oof_stats(draws, WIN)
    g_rate = st["gold"] / max(st["n"], 1)
    conf_text, z_score, lift = get_confidence_badge(g_rate, st["n"])

    # 80 码全景分类
    gold_set = {p["gold"]}
    silver_set = {p["silver"]}
    bronze_set = {p["bronze"]}
    core4_set = set(p["core4"])
    def5_set = set(p["def5"])
    kill_set = set(p["kill"])

    matrix_80 = []
    for num in range(1, 81):
        status = "normal"
        status_text = "普通观察"
        score_val = round(p["score"].get(num, 0.0), 3)

        if num in gold_set:
            status = "gold"
            status_text = "首席金胆"
        elif num in silver_set:
            status = "silver"
            status_text = "次席银胆"
        elif num in bronze_set:
            status = "bronze"
            status_text = "强力铜胆"
        elif num in core4_set:
            status = "core4"
            status_text = "核心4码"
        elif num in def5_set:
            status = "def5"
            status_text = "终极5码"
        elif num in kill_set:
            status = "kill"
            status_text = "铁血做空"

        matrix_80.append({
            "number": num,
            "score": score_val,
            "status": status,
            "status_text": status_text,
            "is_gold": num in gold_set,
            "is_dan": num in (gold_set | silver_set | bronze_set),
            "is_def5": num in def5_set,
            "is_kill": num in kill_set
        })

    # 算子活跃度统计
    operators = []
    for op, weight in W.items():
        op_hit_cnt = st["op_hit"].get(op, 0)
        op_tot = max(st["op_n"].get(op, 1), 1)
        hr = round(op_hit_cnt / op_tot * 100, 1)
        name_map = {
            "spatial": "空间张力 (真空重仓/超载做空)",
            "tail": "尾数信息熵 (全灭补偿/极值杀号)",
            "diffuse": "马尔可夫扩散 (热点边码溢出)",
            "community": "共现社区 (帮派跟随/对子杀补)",
            "momentum": "动量延续 (火炉不熄)"
        }
        operators.append({
            "key": op,
            "name": name_map.get(op, op),
            "weight": weight,
            "hit_rate": hr,
            "hit_count": op_hit_cnt,
            "total_count": op_tot,
            "is_effective": hr >= 25.0
        })

    return {
        "status": "ok",
        "latest_period": latest["period"],
        "latest_date": latest["date"],
        "target_period": target,
        "confidence": conf_text,
        "z_score": round(z_score, 2),
        "lift": round(lift, 2),
        "gold": p["gold"],
        "silver": p["silver"],
        "bronze": p["bronze"],
        "core4": p["core4"],
        "def5": p["def5"],
        "kill_count": len(p["kill"]),
        "kill_numbers": p["kill"],
        "anomalies": [{"kind": a[0], "desc": a[1]} for a in p["anomalies"]],
        "operators": operators,
        "matrix_80": matrix_80
    }


def get_walk_forward_review(history_file: Optional[Path | str] = None, n_review: int = 30) -> Dict[str, Any]:
    """获取近 N 期样本外滚动复盘对账流水"""
    draws = load_draws(history_file)
    if not draws:
        return {"status": "error", "message": "无法加载开奖历史", "rows": []}

    m = len(draws)
    lo = max(0, m - n_review)
    by = {d["period"]: d for d in draws}

    pred = {}
    for t in range(lo, m):
        p = daily_picks(draws, t)
        if p:
            pred[draws[t]["period"]] = p

    periods = [d["period"] for d in draws[lo:m]]
    rows = []
    for per in periods:
        d, pk = by.get(per), pred.get(per)
        if not d or not pk:
            continue
        act_nums = d["nums"]
        dans = pk["dans"]
        core4 = pk["core4"]
        def5 = pk["def5"]

        dans_hit_list = [x for x in dans if x in act_nums]
        core4_hit_list = [x for x in core4 if x in act_nums]
        def5_hit_list = [x for x in def5 if x in act_nums]

        rows.append({
            "period": per,
            "gold": pk["gold"],
            "silver": pk["silver"],
            "bronze": pk["bronze"],
            "dans": dans,
            "dans_hits": len(dans_hit_list),
            "dans_hit_list": dans_hit_list,
            "gold_hit": pk["gold"] in act_nums,
            "core4": core4,
            "core4_hits": len(core4_hit_list),
            "core4_hit_list": core4_hit_list,
            "def5": def5,
            "def5_hits": len(def5_hit_list),
            "def5_hit_list": def5_hit_list,
            "actual_numbers": sorted(list(act_nums))
        })

    n = len(rows)
    avg_dan_hits = round(sum(r["dans_hits"] for r in rows) / max(n, 1), 2)
    avg_core4_hits = round(sum(r["core4_hits"] for r in rows) / max(n, 1), 2)
    avg_def5_hits = round(sum(r["def5_hits"] for r in rows) / max(n, 1), 2)
    gold_hit_count = sum(1 for r in rows if r["gold_hit"])
    gold_hit_rate = round(gold_hit_count / max(n, 1) * 100, 1)

    return {
        "status": "ok",
        "n_periods": n,
        "gold_hit_rate": gold_hit_rate,
        "gold_lift": round(gold_hit_rate / (BASE_SINGLE * 100), 2),
        "avg_dan_hits": avg_dan_hits,
        "dan_lift": round(avg_dan_hits / 0.75, 2),
        "avg_core4_hits": avg_core4_hits,
        "core4_lift": round(avg_core4_hits / 1.0, 2),
        "avg_def5_hits": avg_def5_hits,
        "def5_lift": round(avg_def5_hits / 1.25, 2),
        "rows": rows
    }


def run_daily_pipeline(history_file: Optional[Path | str] = None, n_review: int = 30) -> Dict[str, Any]:
    """完整命令行与日常流程执行，并自动落盘"""
    draws = load_draws(history_file)
    if not draws:
        print("❌ 无法加载开奖数据")
        return {"status": "error"}

    m = len(draws)
    latest = draws[-1]
    target = latest["period"] + 1

    today = daily_picks(draws, m)
    st = oof_stats(draws, n_review)
    lvl, z, lift = get_confidence_badge(st["gold"] / max(st["n"], 1), st["n"])

    # 落盘
    of = OUTPUT_DIR / f"gemini选2预测_{target}.txt"
    jf = OUTPUT_DIR / f"k8_quant_memory_{target}.json"
    snap = {
        "target": target,
        "based_on": latest["period"],
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "confidence": lvl,
        "gold": today["gold"],
        "silver": today["silver"],
        "bronze": today["bronze"],
        "core4": today["core4"],
        "def5": today["def5"],
        "kill": today["kill"],
        "anomalies": today["anomalies"],
        "walk_forward": {
            "n": st["n"],
            "gold_lift": round(st["gold"] / max(st["n"], 1) / BASE_SINGLE, 3)
        }
    }

    with open(of, "w", encoding="utf-8") as f:
        f.write(f"gemini选2-预测 K8-Quant 每日预测 {target} (重建版 {datetime.now():%Y-%m-%d %H:%M})\n")
        f.write(f"置信: {lvl} (z={z:.2f}) | 金胆 {today['gold']:02d} 银胆 {today['silver']:02d} 铜胆 {today['bronze']:02d}\n")
        f.write(f"核心4码: {'-'.join('%02d' % x for x in today['core4'])}\n")
        f.write(f"终极5码: {'-'.join('%02d' % x for x in today['def5'])}\n")
        f.write(f"铁血纪律区(做空): {'-'.join('%02d'%x for x in today['kill']) or '无'}\n")
        f.write(f"异象: {today['anomalies']}\n")

    with open(jf, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)

    print(f"✅ 预测落盘: {of}")
    print(f"✅ 记忆落盘: {jf}")
    return snap


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    run_daily_pipeline(n_review=n)
