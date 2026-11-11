# -*- coding: utf-8 -*-
"""
顺口溜口诀跨系统交叉风控与提纯验证器 (Jingle Cross Validator)
============================================================
将顺口溜推荐码与全系统的其他核心模块进行交叉碰撞（仅打标签，不改正序）：
1. 🔴 危险信号号码：口诀推荐码 ∩ 外部杀号池（KillSeeker 已下架，恒为空）
2. 🟢 强共振确认码：口诀推荐码 ∩ 定金选2 / 16期中热最优3码
3. ⚪ 纯净口诀码：无冲突且具有独立统计优势的口诀推荐码

独立宪法 2026-09-11：已移除已退役 LSTM 共振标签。
"""
from backend.utils.paths import get_cache_dir, get_outputs_dir, get_reports_dir
import os
import json
import re
from typing import List, Dict, Set, Any, Optional

from utils.paths import get_project_root

_PROJ = get_project_root()


def load_kill_seeker_numbers() -> Set[int]:
    """KillSeeker 已下架：恒返回空集（保留函数签名兼容旧调用）。"""
    return set()


def load_pair_selector_numbers() -> Set[int]:
    """加载定金选2金胆/搭档号码"""
    pair_set = set()
    candidates = [
        os.path.join(get_outputs_dir(), "gold_pick2", "gold_pick2_latest.json"),
        os.path.join(get_cache_dir(), "pair_selection_result.json"),
    ]
    for pair_cache in candidates:
        if not os.path.exists(pair_cache):
            continue
        try:
            with open(pair_cache, "r", encoding="utf-8") as f:
                d = json.load(f)
            for k in ("golden", "hot"):
                if d.get(k):
                    pair_set.add(int(d[k]))
            for key in ("top5_golden", "top5_hot", "top5_pairs"):
                for item in d.get(key) or []:
                    if isinstance(item, dict):
                        for n in item.get("pair") or []:
                            pair_set.add(int(n))
                        if item.get("partner"):
                            pair_set.add(int(item["partner"]))
                    elif isinstance(item, list):
                        pair_set.update(int(x) for x in item)
            for n in d.get("optimal_pick2") or []:
                pair_set.add(int(n))
        except Exception:
            pass
    return pair_set


def load_sixteen_numbers() -> Set[int]:
    """加载 16期中热最优3码 / 金银胆（主看引擎）"""
    out: Set[int] = set()
    cache = os.path.join(get_cache_dir(), "sixteen_period", "latest_summary.json")
    if os.path.exists(cache):
        try:
            with open(cache, "r", encoding="utf-8") as f:
                d = json.load(f)
            for k in ("gold_dan", "silver_dan", "bronze_dan"):
                if d.get(k):
                    out.add(int(d[k]))
            for n in d.get("medium_top5") or []:
                out.add(int(n))
        except Exception:
            pass
    # report fallback
    if not out:
        for folder in (get_reports_dir(), os.path.join(get_outputs_dir(), "reports")):
            if not os.path.isdir(folder):
                continue
            files = sorted(
                [f for f in os.listdir(folder) if f.startswith("sixteen_analysis_report_")],
                reverse=True,
            )
            for fname in files[:1]:
                try:
                    txt = open(os.path.join(folder, fname), encoding="utf-8", errors="ignore").read()
                    m = re.search(r"中热精选 5 码防线.*?`([0-9 ]+)`", txt)
                    if m:
                        out.update(int(x) for x in m.group(1).split() if x.isdigit())
                except Exception:
                    pass
    return out


def load_lstm_numbers(target_issue: Optional[str] = None) -> Set[int]:
    """已退役：恒返回空集（保留函数签名兼容旧调用）。"""
    return set()


def cross_validate_jingle(
    recommended_numbers: List[int],
    target_issue: Optional[str] = None,
    custom_kill_set: Optional[Set[int]] = None,
) -> Dict[str, Any]:
    """交叉风控：只产出标签，不修改推荐排序。"""
    rec_set = set(int(x) for x in recommended_numbers)
    kill_set = custom_kill_set if custom_kill_set is not None else load_kill_seeker_numbers()
    pair_set = load_pair_selector_numbers()
    sixteen_set = load_sixteen_numbers()

    clash_numbers = sorted(rec_set & kill_set)
    resonance_pair = sorted(rec_set & pair_set)
    resonance_sixteen = sorted(rec_set & sixteen_set)
    all_resonance = sorted(set(resonance_pair) | set(resonance_sixteen))
    pure_numbers = sorted(rec_set - set(clash_numbers) - set(all_resonance))

    detailed_tags = []
    for num in recommended_numbers:
        tags = []
        is_clash = num in clash_numbers
        is_res = num in all_resonance

        if is_clash:
            tags.append({"type": "danger", "label": "🔴 杀号冲突", "desc": "与外部杀号池重叠（仅参考，不改正序）"})
        if num in resonance_pair:
            tags.append({"type": "success", "label": "🟢 选2重叠", "desc": "与定金选2金胆/搭档重叠（并列对照）"})
        if num in resonance_sixteen:
            tags.append({"type": "success", "label": "🟢 16期中热", "desc": "与建议主看引擎最优3码/金胆重叠"})
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
        "resonance_sixteen": resonance_sixteen,
        "resonance_lstm": [],  # 兼容旧字段
        "all_resonance": all_resonance,
        "pure_numbers": pure_numbers,
        "detailed_tags": detailed_tags,
        "summary": {
            "total": len(recommended_numbers),
            "clash_count": len(clash_numbers),
            "resonance_count": len(all_resonance),
            "pure_count": len(pure_numbers),
        },
    }
