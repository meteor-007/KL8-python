# -*- coding: utf-8 -*-
"""
顺口溜口诀跨系统交叉风控与提纯验证器 (Jingle Cross Validator)
============================================================
将顺口溜推荐码与全系统的其他核心模块进行交叉碰撞：
1. 🔴 危险信号号码（撞车风险）：口诀推荐码 ∩ KillSeeker 高置信杀号名单
2. 🟢 强共振确认码（多维共振）：口诀推荐码 ∩ 定金选2最佳搭档 / LSTM 深度时序 Top 榜
3. ⚪ 纯净口诀码：无冲突且具有独立统计优势的口诀推荐码
"""
import os
import json
import re
from typing import List, Dict, Set, Any, Optional

from utils.paths import get_project_root

_PROJ = get_project_root()


def load_kill_seeker_numbers() -> Set[int]:
    """尝试加载 KillSeeker 高置信度杀号列表"""
    candidates = [
        os.path.join(_PROJ, "KillSeeker", "logs", "kill_report.txt"),
        os.path.join(_PROJ, "outputs", "kill_report.txt"),
        os.path.join(_PROJ, "cache", "kill_numbers.json"),
    ]
    kill_set = set()
    for p in candidates:
        if os.path.exists(p):
            try:
                if p.endswith(".json"):
                    with open(p, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        nums = d.get("kill_numbers", [])
                        kill_set.update(int(x) for x in nums)
                else:
                    with open(p, "r", encoding="utf-8") as f:
                        text = f.read()
                        matches = re.findall(r"(?:高置信杀号|杀号清单|kill):\s*([0-9\s,\-]+)", text)
                        for m in matches:
                            nums = [int(x) for x in re.split(r"[\s,\-]+", m) if x.isdigit()]
                            kill_set.update(nums)
            except Exception:
                pass
    return kill_set


def load_pair_selector_numbers() -> Set[int]:
    """加载定金选2最佳搭档号码"""
    pair_cache = os.path.join(_PROJ, "cache", "pair_selection_result.json")
    pair_set = set()
    if os.path.exists(pair_cache):
        try:
            with open(pair_cache, "r", encoding="utf-8") as f:
                d = json.load(f)
                p2 = d.get("optimal_pick2", [])
                pair_set.update(int(x) for x in p2)
                p_cand = d.get("top_candidates", [])
                for pair in p_cand[:3]:
                    if isinstance(pair, list):
                        pair_set.update(int(x) for x in pair)
        except Exception:
            pass
    return pair_set


def load_lstm_numbers(target_issue: Optional[str] = None) -> Set[int]:
    """加载 LSTM 深度学习时序推荐 Top 号码"""
    lstm_set = set()
    pred_dir = os.path.join(_PROJ, "outputs", "predictions")
    if os.path.exists(pred_dir):
        files = sorted([f for f in os.listdir(pred_dir) if f.startswith("prediction_")], reverse=True)
        if files:
            target_file = files[0]
            if target_issue:
                match_files = [f for f in files if target_issue in f]
                if match_files:
                    target_file = match_files[0]
            try:
                with open(os.path.join(pred_dir, target_file), "r", encoding="utf-8") as f:
                    for line in f:
                        if "Top 12" in line or "Top 5" in line or "LSTM" in line:
                            nums = [int(x) for x in re.findall(r"\b\d{2}\b", line)]
                            lstm_set.update(nums)
            except Exception:
                pass
    return lstm_set


def cross_validate_jingle(
    recommended_numbers: List[int],
    target_issue: Optional[str] = None,
    custom_kill_set: Optional[Set[int]] = None,
) -> Dict[str, Any]:
    """
    对顺口溜推荐码进行全方位交叉风控审计与打标。
    """
    rec_set = set(recommended_numbers)
    kill_set = custom_kill_set if custom_kill_set is not None else load_kill_seeker_numbers()
    pair_set = load_pair_selector_numbers()
    lstm_set = load_lstm_numbers(target_issue)

    clash_numbers = sorted(rec_set & kill_set)
    resonance_pair = sorted(rec_set & pair_set)
    resonance_lstm = sorted(rec_set & lstm_set)
    all_resonance = sorted(set(resonance_pair) | set(resonance_lstm))
    pure_numbers = sorted(rec_set - set(clash_numbers) - set(all_resonance))

    detailed_tags = []
    for num in recommended_numbers:
        tags = []
        is_clash = (num in clash_numbers)
        is_res = (num in all_resonance)

        if is_clash:
            tags.append({"type": "danger", "label": "🔴 杀号冲突", "desc": "被KillSeeker列为高置信冷杀号"})
        if num in resonance_pair:
            tags.append({"type": "success", "label": "🟢 选2金胆", "desc": "与定金选2黄金搭档高度重合"})
        if num in resonance_lstm:
            tags.append({"type": "success", "label": "🟢 LSTM共振", "desc": "与双层LSTM时序网络Top码重合"})
        if not tags:
            tags.append({"type": "neutral", "label": "⚪ 独立口诀", "desc": "纯统计顺口溜驱动号码"})

        detailed_tags.append({
            "number": num,
            "is_danger": is_clash,
            "is_resonance": is_res,
            "tags": tags,
        })

    return {
        "recommended": recommended_numbers,
        "clash_numbers": clash_numbers,
        "resonance_pair": resonance_pair,
        "resonance_lstm": resonance_lstm,
        "all_resonance": all_resonance,
        "pure_numbers": pure_numbers,
        "detailed_tags": detailed_tags,
        "summary": {
            "total": len(recommended_numbers),
            "clash_count": len(clash_numbers),
            "resonance_count": len(all_resonance),
            "pure_count": len(pure_numbers),
        }
    }
