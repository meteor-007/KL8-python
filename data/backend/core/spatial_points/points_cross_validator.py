# -*- coding: utf-8 -*-
"""
重点点位分析 (空间点位打分与精排) - 多维交叉风控与共振提纯校验器
================================================================
跨系统数据交叉核验：
1. 🔴 撞车风险核验 (Kill Conflict):
   - 与 KillSeeker 杀号模型交叉：若点位精选号被 KillSeeker 高置信拦截，标记为撞车风险，降低仓位防守。
2. 🟢 黄金共振核验 (Golden Resonance):
   - 与 双层LSTM / 三维融合 (Trinity Top5/HE5) / 顺口溜口诀 (Jingle) 交叉：
     若出现多系统交集共识，标记为黄金多维共振码。
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
                    # 匹配数字
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


def load_trinity_and_lstm_numbers(proj_root: str) -> Dict[str, Set[int]]:
    """从主系统自学习状态与预测产物中提取 LSTM 与 Trinity 推荐号码"""
    res = {
        "trinity_top5": set(),
        "trinity_he5": set(),
        "lstm_picks": set(),
        "jingle_picks": set(),
    }
    
    # 1. 自学习记忆中的 Trinity 推荐
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

    # 2. 顺口溜最新预测
    jingle_file = os.path.join(proj_root, "cache", "jingle_prediction.json")
    if os.path.exists(jingle_file):
        try:
            with open(jingle_file, "r", encoding="utf-8", errors="ignore") as f:
                jdata = json.load(f)
                res["jingle_picks"] = set(jdata.get("k_numbers", []))
        except Exception:
            pass

    # 3. 检查 outputs/predictions 下最新 txt 预测
    pred_dir = os.path.join(proj_root, "outputs", "predictions")
    if os.path.exists(pred_dir):
        txts = sorted([f for f in os.listdir(pred_dir) if f.endswith(".txt")], reverse=True)
        if txts:
            try:
                with open(os.path.join(pred_dir, txts[0]), "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "LSTM" in line or "金胆" in line or "银胆" in line:
                            nums = [int(x) for x in re.findall(r"\b\d{1,2}\b", line) if 1 <= int(x) <= 80]
                            res["lstm_picks"].update(nums)
            except Exception:
                pass

    return res


def cross_validate_spatial_picks(
    proj_root: str,
    picks: Dict[str, Any]
) -> Dict[str, Any]:
    """
    对重点点位精选结果执行多维交叉风控与共振打标
    """
    kill_nums = load_kill_seeker_numbers(proj_root)
    other_sys = load_trinity_and_lstm_numbers(proj_root)

    # 读取 daily_points.txt 最新点位
    daily_pts: Set[int] = set()
    try:
        pts_path = os.path.join(proj_root, "daily_points.txt")
        if os.path.exists(pts_path):
            with open(pts_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m_pts = re.search(r"points:([\d\s]+)", line)
                    if m_pts:
                        daily_pts = {int(x) for x in m_pts.group(1).split() if x.isdigit()}
                        break
    except Exception:
        pass

    ten_set = set(picks.get("ten", []))
    core5_set = set(picks.get("core5", []))
    ext15 = picks.get("ext15", [])

    kill_conflicts = sorted(list(ten_set & kill_nums))
    
    # 共振池
    resonance_source = other_sys["trinity_top5"] | other_sys["trinity_he5"] | other_sys["lstm_picks"] | other_sys["jingle_picks"] | daily_pts
    resonance_numbers = sorted(list(ten_set & resonance_source))

    number_tags = {}
    for num in ext15:
        tags = []
        is_risk = num in kill_nums
        is_resonance = num in resonance_source

        if num in core5_set:
            tags.append({"name": "核心五码", "type": "gold"})
        elif num in ten_set:
            tags.append({"name": "精选十码", "type": "cyan"})
        else:
            tags.append({"name": "扩展防守", "type": "slate"})

        if num in daily_pts:
            tags.append({"name": "📌今日点位金叉", "type": "warning"})

        if is_risk:
            tags.append({"name": "KillSeeker撞车", "type": "danger"})
        if is_resonance:
            # 细化共振来源
            res_details = []
            if num in daily_pts:
                res_details.append("当日点位")
            if num in other_sys["trinity_he5"]:
                res_details.append("HiddenEnergy")
            if num in other_sys["trinity_top5"]:
                res_details.append("Trinity")
            if num in other_sys["lstm_picks"]:
                res_details.append("LSTM")
            if num in other_sys["jingle_picks"]:
                res_details.append("Jingle")
            src_str = "/".join(res_details) if res_details else "多维"
            tags.append({"name": f"✨共振({src_str})", "type": "success"})

        number_tags[num] = {
            "num": num,
            "tags": tags,
            "is_risk": is_risk,
            "is_resonance": is_resonance,
            "action_advice": "减仓观望" if is_risk else ("重点跟进" if is_resonance else "正常配置")
        }

    return {
        "kill_conflicts": kill_conflicts,
        "resonance_numbers": resonance_numbers,
        "number_tags": number_tags,
        "kill_total_count": len(kill_nums),
        "resonance_total_count": len(resonance_numbers),
    }
