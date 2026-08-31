# -*- coding: utf-8 -*-
"""
未开点位高压反弹与空间关联追踪引擎 (Point Suppression Engine v2.0 - 主系统整合版)
================================================================================
专攻：点位推荐后机器未开（落空点位/高压弹簧）在下一期的深度反弹与空间关联分析。

四大核心量化模型：
  1. 【弹簧压制模型】(Spring Hazard): 统计连续推荐未开期数 K 的条件回补概率，锚定黄金回补窗口。
  2. 【能量外溢模型】(Spatial Spillover): 统计落空后，±1(邻居)、±2(次邻居)、同尾数、对称点的能量漂移。
  3. 【影子替身模型】(Surrogate Network): 建立条件失败伴生矩阵 P(Y开出 | X落空)，提取黄金替身对子。
  4. 【AI海选反弹团】(AI Ranking Ensemble): 6维特征综合打分，优胜劣汰挑选 Top 1~3 反弹金胆。
"""
import os
import re
import sys
import math
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Set, Optional

NUM = 80
SINGLE_BASE = 20.0 / 80.0                                    # 0.2500 (25.0%)
REGION_BASE = 1.0 - math.comb(77, 20) / math.comb(80, 20)   # ≈0.5835 (58.35%)
PAIR_BASE = (20 * 19) / (80 * 79)                            # ≈0.0601 (6.01%)


def load_draws_from_file(history_path: str) -> List[Dict[str, Any]]:
    """加载开奖历史数据"""
    draws = []
    if not os.path.exists(history_path):
        return draws
    with open(history_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line.strip())
            if not m:
                continue
            nums = set(int(x) for x in m.group(3).split("-") if x.isdigit())
            if len(nums) == 20:
                draws.append({"period": int(m.group(2)), "date": m.group(1), "nums": nums})
    draws.sort(key=lambda d: d["period"])
    return draws


def region_of(n: int) -> Set[int]:
    """三号区: n-1, n, n+1 环绕 (1~80)"""
    return {(n - 2) % NUM + 1, n, n % NUM + 1}


def spillover_regions(n: int) -> Dict[str, Set[int]]:
    """各级外溢区域"""
    r1 = {(n - 2) % NUM + 1, n % NUM + 1}                         # ±1 邻居 (不含自身)
    r2 = {(n - 3) % NUM + 1, (n + 1) % NUM + 1}                 # ±2 次邻居
    same_tail = {x for x in range(1, NUM + 1) if x % 10 == n % 10 and x != n}  # 同尾号
    sym = {81 - n} if 1 <= 81 - n <= 80 and 81 - n != n else set()             # 对称点
    return {"r1": r1, "r2": r2, "tail": same_tail, "sym": sym}


def point_signals(hist: List[Dict[str, Any]], n: int) -> Tuple[Set[str], int]:
    """
    计算单个点位激活的 7 路信号与号码全局遗漏
    7 路信号：
      R  重码      T-1开出 且 T-2/T-3 未开出
      G1 隔1期     T-2开出, T-1未开出
      G2 隔2期     T-3开出, T-2/T-1未开出
      G3 隔3期     T-4开出, T-3/T-2/T-1未开出
      L  遗留延续  T-1与T-2该点位邻域连续有号(热点延续)
      O  遗漏回补  距上次开出 3~6 期
      D  连号扩散  上期 ±1 邻号开出(能量外溢)
    """
    if len(hist) < 4:
        return set(), 0
    last = hist[-1]["nums"]
    prev = hist[-2]["nums"]
    p2 = hist[-3]["nums"]
    p3 = hist[-4]["nums"]
    on = set()
    
    # 真实遗漏
    gap = len(hist)
    for i in range(len(hist) - 1, -1, -1):
        if n in hist[i]["nums"]:
            gap = len(hist) - 1 - i
            break
            
    if 3 <= gap <= 6:
        on.add("O")  # 遗漏回补
    if n in last and n not in prev and n not in p2:
        on.add("R")  # 重码新鲜连庄
    if n in prev and n not in last:
        on.add("G1") # 隔1期
    if n in p2 and n not in prev and n not in last:
        on.add("G2") # 隔2期
    if n in p3 and n not in p2 and n not in prev and n not in last:
        on.add("G3") # 隔3期
    
    rg = region_of(n)
    if (rg & last) and (rg & prev):
        on.add("L")  # 遗留延续
        
    if any(m in last for m in ((n - 2) % NUM + 1, n % NUM + 1)):
        on.add("D")  # 连号扩散
        
    return on, gap


def get_period_picks(hist: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算某期切片下的全量点位信号，返回 Top 点位与强共振点位"""
    info = {}
    for n in range(1, NUM + 1):
        sigs, gap = point_signals(hist, n)
        info[n] = {"sigs": sigs, "res": len(sigs), "gap": gap}
    order = sorted(info, key=lambda n: (-info[n]["res"], -info[n]["gap"]))
    strong = [n for n in info if info[n]["res"] >= 3]
    top10 = order[:10]
    return {"info": info, "order": order, "strong": strong, "top10": top10}


class PointSuppressionAnalyzer:
    """未开点位高压反弹与空间关联分析器"""
    
    def __init__(self, draws: List[Dict[str, Any]]):
        self.draws = draws
        self.m = len(draws)
        
    def analyze_historical_patterns(self, train_len: int = 1500) -> Dict[str, Any]:
        """
        在历史训练集上挖掘：
        1. 弹簧压制期数 K 的回补概率分布
        2. 能量外溢漂移率
        3. 影子替身伴生矩阵
        """
        active_suppression = defaultdict(int)
        
        spring_stats = defaultdict(lambda: {"count": 0, "single_hit": 0, "region_hit": 0})
        spill_stats = {"total_miss": 0, "r1_hit": 0, "r2_hit": 0, "tail_hit": 0, "sym_hit": 0}
        surrogate_counts = defaultdict(lambda: defaultdict(int))
        miss_occurrences = defaultdict(int)
        
        end_idx = min(self.m, train_len)
        for t in range(40, end_idx):
            hist = self.draws[:t]
            act = self.draws[t]["nums"]
            picks = get_period_picks(hist)
            priority_pts = set(picks["top10"]).union(picks["strong"])
            
            for n, k in list(active_suppression.items()):
                if k > 0:
                    spring_stats[k]["count"] += 1
                    if n in act:
                        spring_stats[k]["single_hit"] += 1
                    if region_of(n) & act:
                        spring_stats[k]["region_hit"] += 1
                        
                    sp = spillover_regions(n)
                    spill_stats["total_miss"] += 1
                    if sp["r1"] & act:
                        spill_stats["r1_hit"] += 1
                    if sp["r2"] & act:
                        spill_stats["r2_hit"] += 1
                    if sp["tail"] & act:
                        spill_stats["tail_hit"] += 1
                    if sp["sym"] & act:
                        spill_stats["sym_hit"] += 1
                        
                    miss_occurrences[n] += 1
                    for drawn_n in act:
                        surrogate_counts[n][drawn_n] += 1

            new_suppression = defaultdict(int)
            for n in range(1, NUM + 1):
                if n in priority_pts:
                    if n not in act:
                        new_suppression[n] = active_suppression[n] + 1
                    else:
                        new_suppression[n] = 0
                else:
                    if active_suppression[n] > 0 and n not in act:
                        new_suppression[n] = active_suppression[n]
                    else:
                        new_suppression[n] = 0
            active_suppression = new_suppression

        surrogate_map = {}
        for n in range(1, NUM + 1):
            tot = miss_occurrences[n]
            if tot >= 10:
                ranked = []
                for cand in range(1, NUM + 1):
                    if cand == n:
                        continue
                    cnt = surrogate_counts[n][cand]
                    prob = cnt / tot
                    lift = prob / SINGLE_BASE
                    if lift >= 1.15:
                        ranked.append((cand, prob, lift, cnt))
                ranked.sort(key=lambda x: -x[2])
                surrogate_map[n] = ranked[:3]
            else:
                surrogate_map[n] = []
                
        return {
            "spring_stats": dict(spring_stats),
            "spill_stats": spill_stats,
            "surrogate_map": surrogate_map
        }

    def score_unhit_candidates(self, hist: List[Dict[str, Any]], active_suppression: Dict[int, int], patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        AI海选反弹团 (综合打分器)
        6维打分选拔未开压制号码：
          1. 弹簧张力得分 (根据K期历史回补率)
          2. 7路共振支撑分
          3. 能量外溢与邻居铺路分 (±1/±2/同尾)
          4. 影子替身牵引分 (伴生替身近期活跃)
          5. 全局遗漏回补分 (3~7期黄金遗漏)
        """
        picks = get_period_picks(hist)
        last_draw = hist[-1]["nums"]
        prev_draw = hist[-2]["nums"] if len(hist) >= 2 else set()
        
        candidates_scores = []
        
        for n in range(1, NUM + 1):
            k = active_suppression.get(n, 0)
            if k == 0:
                continue
                
            info = picks["info"][n]
            res = info["res"]
            gap = info["gap"]
            
            spring_k_stat = patterns["spring_stats"].get(k, {"count": 1, "region_hit": 0, "single_hit": 0})
            reg_rate = spring_k_stat["region_hit"] / spring_k_stat["count"] if spring_k_stat["count"] > 10 else REGION_BASE
            spring_score = (reg_rate / REGION_BASE) * 25.0
            
            resonance_score = min(res, 5) * 6.0
            
            sp = spillover_regions(n)
            spill_heat = 0
            if sp["r1"] & last_draw:
                spill_heat += 12.0
            if sp["tail"] & last_draw:
                spill_heat += 8.0
            if sp["r2"] & last_draw:
                spill_heat += 4.0
                
            surr_list = patterns["surrogate_map"].get(n, [])
            surr_score = 0
            active_surrs = []
            for surr_n, prob, lift, cnt in surr_list:
                if surr_n in last_draw or surr_n in prev_draw:
                    surr_score += 10.0 * (lift - 1.0)
                    active_surrs.append(surr_n)
                    
            gap_score = 0
            if 3 <= gap <= 7:
                gap_score = 15.0
            elif gap > 12:
                gap_score = 5.0
                
            total_score = spring_score + resonance_score + spill_heat + surr_score + gap_score
            
            if total_score >= 68.0 and k in [2, 3] and (spill_heat >= 12.0 or surr_score >= 5.0):
                confidence_level = "🟢 S级 (特级反弹共振)"
                conf_grade = "S"
            elif total_score >= 52.0:
                confidence_level = "🟡 A级 (稳健回补)"
                conf_grade = "A"
            else:
                confidence_level = "⚪ B级 (普通观察)"
                conf_grade = "B"
                
            candidates_scores.append({
                "num": n,
                "k_suppression": k,
                "score": round(total_score, 1),
                "res": res,
                "gap": gap,
                "confidence": confidence_level,
                "conf_grade": conf_grade,
                "active_surrs": active_surrs,
                "surr_list": [{"surrogate_num": s[0], "prob": round(s[1], 3), "lift": round(s[2], 2), "cnt": s[3]} for s in surr_list],
                "sigs": sorted(list(info["sigs"])),
                "region": sorted(list(region_of(n)))
            })
            
        candidates_scores.sort(key=lambda x: -x["score"])
        return candidates_scores


def get_active_suppression_state(draws: List[Dict[str, Any]], cutoff_idx: int) -> Dict[int, int]:
    """回溯计算截至指定切片期 active_suppression 字典"""
    active_suppression = defaultdict(int)
    start_warm = max(0, cutoff_idx - 100)
    for t in range(start_warm, cutoff_idx):
        hist = draws[:t]
        act = draws[t]["nums"]
        picks = get_period_picks(hist)
        priority_pts = set(picks["top10"]).union(picks["strong"])
        new_supp = defaultdict(int)
        for n in range(1, NUM + 1):
            if n in priority_pts:
                new_supp[n] = (active_suppression[n] + 1) if n not in act else 0
            else:
                new_supp[n] = active_suppression[n] if (active_suppression[n] > 0 and n not in act) else 0
        active_suppression = new_supp
    return dict(active_suppression)
