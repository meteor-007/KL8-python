# -*- coding: utf-8 -*-
"""
跟随分析 (重复号追踪与多窗条件跟随) - 多维交叉风控与共振提纯校验器 v3.0
====================================================================
跨系统数据交叉核验：
1. 🔴 杀号冲突预警 (Kill Conflict):
   - 与 KillSeeker / 风险拦截池交叉核验：若跟随号码被高置信拦截，标记为撞车预警。
2. 🟢 黄金多维共振 (Golden Resonance):
   - 与 主系统三维融合 (Top 5 / HE 5)、双层 LSTM 金银铜胆、空间重点点位、顺口溜口诀交叉核验：
     若出现多系统交集共识，标记为高置信多维共振码。
"""
import os
import re
import json
from typing import Dict, List, Any, Set, Optional


def load_kill_seeker_numbers(proj_root: str) -> Set[int]:
    """尝试从 KillSeeker 报告或缓存中提取高置信杀号"""
    kill_nums = set()
    candidates = [
        os.path.join(proj_root, "..", "KillSeeker", "logs", "kill_report.txt"),
        os.path.join(proj_root, "logs", "kill_report.txt"),
        os.path.join(proj_root, "cache", "kill_report.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    found = re.findall(r"(?:高置信杀号|杀号列表|KILL)[\s:：]*([0-9\s,\-]+)", content)
                    for block in found:
                        for item in re.split(r"[\s,\-]+", block):
                            if item.isdigit() and 1 <= int(item) <= 80:
                                kill_nums.add(int(item))
            except Exception:
                pass
            if kill_nums:
                break
    return kill_nums


def load_main_system_recommendations(proj_root: str) -> Dict[str, Set[int]]:
    """从主系统自学习状态与各子系统预测产物中提取共振号码"""
    res = {
        "trinity_top5": set(),
        "trinity_he5": set(),
        "lstm_picks": set(),
        "spatial_picks": set(),
        "jingle_picks": set(),
    }
    
    # 1. 主系统 Trinity Top5 / HE5
    mem_file = os.path.join(proj_root, "cache", "self_learning_state.json")
    if os.path.exists(mem_file):
        try:
            with open(mem_file, "r", encoding="utf-8", errors="ignore") as f:
                state = json.load(f)
                latest_pred = state.get("latest_prediction", {})
                res["trinity_top5"] = set(latest_pred.get("top5", []))
                res["trinity_he5"] = set(latest_pred.get("b3_final5", []))
        except Exception:
            pass

    # 2. 空间重点点位最新预测
    spatial_file = os.path.join(proj_root, "outputs", "spatial_points", "spatial_points_latest.json")
    if os.path.exists(spatial_file):
        try:
            with open(spatial_file, "r", encoding="utf-8", errors="ignore") as f:
                sdata = json.load(f)
                res["spatial_picks"] = set(sdata.get("picks", {}).get("ten", []))
        except Exception:
            pass

    # 3. 顺口溜口诀最新预测
    jingle_file = os.path.join(proj_root, "cache", "jingle_prediction.json")
    if os.path.exists(jingle_file):
        try:
            with open(jingle_file, "r", encoding="utf-8", errors="ignore") as f:
                jdata = json.load(f)
                res["jingle_picks"] = set(jdata.get("recommended_numbers", []))
        except Exception:
            pass

    # 4. 双层 LSTM 预测产物
    pred_dir = os.path.join(proj_root, "outputs", "predictions")
    if os.path.exists(pred_dir):
        try:
            files = sorted([os.path.join(pred_dir, f) for f in os.listdir(pred_dir) if f.startswith("prediction_")], reverse=True)
            if files:
                with open(files[0], "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    tm = re.search(r"Top10:\s*([\d\-]+)", content)
                    if tm:
                        res["lstm_picks"] = set(int(x) for x in tm.group(1).split("-") if x.isdigit())
        except Exception:
            pass

    return res


def cross_validate_follow_picks(proj_root: str, follow_picks: Dict[str, Any]) -> Dict[str, Any]:
    """
    对跟随分析的三路核心号码进行多维交叉风控与共振打标
    """
    kill_set = load_kill_seeker_numbers(proj_root)
    main_picks = load_main_system_recommendations(proj_root)
    
    rep_set = set(follow_picks.get("repeat", {}).get("top5", []))
    inf_set = set(follow_picks.get("inference", {}).get("top6", []))
    cf_set = set(follow_picks.get("conditional", {}).get("top8", []))
    all_follow_nums = sorted(list(rep_set | inf_set | cf_set))
    
    kill_conflicts = sorted(list(set(all_follow_nums) & kill_set))
    
    # 黄金共振号码: 被主系统 >= 2 个模块选中的号码
    resonance_map = {}
    for n in all_follow_nums:
        tags = []
        if n in rep_set: tags.append("🔁 重复号Top5")
        if n in inf_set: tags.append("🧮 综合推演Top6")
        if n in cf_set: tags.append("🔗 条件跟随Top8")
        if n in main_picks["trinity_top5"]: tags.append("🛡️ TrinityTop5")
        if n in main_picks["trinity_he5"]: tags.append("⭐ HiddenEnergy5")
        if n in main_picks["lstm_picks"]: tags.append("🧠 双层LSTM")
        if n in main_picks["spatial_picks"]: tags.append("🔮 空间点位")
        if n in main_picks["jingle_picks"]: tags.append("📜 顺口溜")
        
        is_kill = n in kill_set
        resonance_map[n] = {
            "number": n,
            "display": f"{n:02d}",
            "tags": tags,
            "hit_modules_count": len(tags),
            "is_danger": is_kill,
            "is_resonance": len(tags) >= 2 and not is_kill
        }
        
    resonance_numbers = [n for n, info in resonance_map.items() if info["is_resonance"]]
    
    return {
        "kill_conflicts": kill_conflicts,
        "resonance_numbers": sorted(resonance_numbers),
        "detailed_tags": list(resonance_map.values()),
        "summary": {
            "total_candidates": len(all_follow_nums),
            "resonance_count": len(resonance_numbers),
            "conflict_count": len(kill_conflicts)
        }
    }
