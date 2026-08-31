# -*- coding: utf-8 -*-
"""
未开点位反弹追踪 跨系统多维交叉风控器 (Suppression Cross Validator)
================================================================================
将反弹打分出的 Top 候选号码与主系统其它核心模块进行交叉印证：
  1. 主系统三维融合预测 (EF 能量场 / RW 遗漏回补 / FO 周期谐波)
  2. 选2黄金搭档 (Optimal Pair / Co-occurrence)
  3. 空间重点点位 Top 5 / Core 5
  4. 跟随分析 (重复号 + 条件跟随)
  5. 顺口溜 90 条精英口诀
生成大白话共振标签 (如: 🔥四维共振金胆、⚡能量外溢加持、🌟黄金替身对子等)
"""
import os
import re
import json
from typing import Dict, List, Any, Set


def cross_validate_suppression_picks(proj_dir: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    针对未开反弹候选号码，检索各子系统的最新预测结果并生成共振标签
    """
    main_top5: Set[int] = set()
    main_top12: Set[int] = set()
    pair_nums: Set[int] = set()
    spatial_core5: Set[int] = set()
    follow_nums: Set[int] = set()
    jingle_nums: Set[int] = set()
    
    # 1. 尝试从 cache/self_learning_state.json 或 reports 读取主系统 Top 预测
    try:
        mem_file = os.path.join(proj_dir, "cache", "self_learning_state.json")
        if os.path.exists(mem_file):
            with open(mem_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            hist = state.get("history", [])
            if hist:
                latest_rec = hist[0]
                main_top5 = set(latest_rec.get("top5", []))
                main_top12 = set(latest_rec.get("top12", []))
                pair_nums = set(latest_rec.get("optimal_pick2", []))
    except Exception:
        pass
        
    # 2. 尝试从 outputs/spatial_points 读取重点点位
    try:
        pts_json = os.path.join(proj_dir, "outputs", "spatial_points", "spatial_points_latest.json")
        if os.path.exists(pts_json):
            with open(pts_json, "r", encoding="utf-8") as f:
                p_data = json.load(f)
            spatial_core5 = set(p_data.get("picks", {}).get("core5", []))
    except Exception:
        pass
        
    # 3. 尝试从 outputs/follow_analysis 读取跟随
    try:
        fol_json = os.path.join(proj_dir, "outputs", "follow_analysis", "follow_latest.json")
        if os.path.exists(fol_json):
            with open(fol_json, "r", encoding="utf-8") as f:
                fol_data = json.load(f)
            follow_nums = set(fol_data.get("picks", {}).get("cf_top8", []))
    except Exception:
        pass

    # 4. 尝试从 outputs/formula_jingle 读取顺口溜
    try:
        j_json = os.path.join(proj_dir, "outputs", "formula_jingle", "jingle_latest.json")
        if os.path.exists(j_json):
            with open(j_json, "r", encoding="utf-8") as f:
                j_data = json.load(f)
            jingle_nums = set(j_data.get("picks", []))
    except Exception:
        pass

    # 5. 尝试从 daily_points.txt 读取最新录入点位
    daily_pts: Set[int] = set()
    try:
        pts_path = os.path.join(proj_dir, "daily_points.txt")
        if os.path.exists(pts_path):
            with open(pts_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m_pts = re.search(r"points:([\d\s]+)", line)
                    if m_pts:
                        daily_pts = {int(x) for x in m_pts.group(1).split() if x.isdigit()}
                        break
    except Exception:
        pass

    cross_items = []
    for cand in candidates:
        num = cand["num"]
        tags = []
        resonance_count = 0
        
        if num in daily_pts:
            tags.append("📌 今日点位金叉")
            resonance_count += 2

        if num in main_top5:
            tags.append("🔥 主系统Top5金胆")
            resonance_count += 2
        elif num in main_top12:
            tags.append("🎯 主系统Top12")
            resonance_count += 1
            
        if num in pair_nums:
            tags.append("👑 选2黄金搭档")
            resonance_count += 2
            
        if num in spatial_core5:
            tags.append("🔮 重点点位Core5")
            resonance_count += 1
            
        if num in follow_nums:
            tags.append("🔗 强条件跟随")
            resonance_count += 1
            
        if num in jingle_nums:
            tags.append("📜 顺口溜精英口诀")
            resonance_count += 1
            
        if cand.get("active_surrs"):
            tags.append(f"🪞 激活替身({','.join(f'{x:02d}' for x in cand['active_surrs'])})")
            
        if not tags:
            tags.append("🛡️ 独立弹簧回补")
            
        cross_items.append({
            "num": num,
            "score": cand["score"],
            "k_suppression": cand["k_suppression"],
            "conf_grade": cand.get("conf_grade", "B"),
            "resonance_count": resonance_count,
            "tags": tags
        })
        
    return {
        "status": "ok",
        "cross_items": cross_items,
        "active_main_top5": sorted(list(main_top5)),
        "active_pair_nums": sorted(list(pair_nums)),
        "active_spatial_core5": sorted(list(spatial_core5))
    }
