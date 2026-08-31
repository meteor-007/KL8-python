# -*- coding: utf-8 -*-
"""
顺口溜口诀核心计算与预测引擎 (Jingle Engine)
==============================================
原理（大白话）：找"顺口溜"规律——某期开奖同时开出了特定的几个号码（触发组合），
下期大概率带出另外特定的号码（口诀推荐）。
规则来源：90 条经过 FDR 显著性校正与样本外 (OOF) 双重检验的精英口诀。
"""
import os
import json
import re
from datetime import datetime
from math import comb
from typing import List, Dict, Tuple, Any, Optional

from utils.paths import get_project_root, data_path

_PROJ = get_project_root()

# 理论基线常数
BASELINE_PAIR = 20 / 80 * 19 / 79      # 两个特定号码同时开出的理论概率 ≈ 0.0601 (6.01%)
BASELINE_TRIPLE = 20 / 80              # 单个特定号码开出的理论概率 = 0.2500 (25.0%)


def at_least_one_baseline(k: int) -> float:
    """
    计算推荐 k 个号码时，在开奖 20 个球中「至少命中 1 个」的理论随机期望概率。
    （采用不放回超几何分布精确公式：1 - C(60, k) / C(80, k)）
    """
    if k <= 0:
        return 0.0
    k_bounded = min(k, 60)
    return 1.0 - comb(60, k_bounded) / comb(80, k)


def get_default_rules_path() -> str:
    """获取口诀表默认存储路径"""
    candidates = [
        os.path.join(_PROJ, "core", "formula_jingle", "rules", "口诀表_stats.json"),
        os.path.join(_PROJ, "backend", "core", "formula_jingle", "rules", "口诀表_stats.json"),
        os.path.join(_PROJ, "rules_c", "口诀表_stats.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "口诀表_stats.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def load_jingle_rules(rules_path: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    加载 90 条口诀精英规则库。
    返回: (rules_list, meta_info)
    """
    path = rules_path or get_default_rules_path()
    if not os.path.exists(path):
        return [], {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    raw_rules = data.get("rules", {})
    rules_list = []
    if isinstance(raw_rules, dict):
        for rid, r in raw_rules.items():
            item = dict(r)
            item["rule_id"] = str(rid)
            rules_list.append(item)
    elif isinstance(raw_rules, list):
        for idx, r in enumerate(raw_rules):
            item = dict(r)
            item["rule_id"] = str(idx + 1)
            rules_list.append(item)
            
    meta = data.get("meta", {})
    return rules_list, meta


def fired_rules(rules: List[Dict[str, Any]], draw_nums: Any) -> List[Tuple[Dict[str, Any], List[int], float]]:
    """
    检查当期开奖号码是否触发了口诀（触发条件: trigger ⊆ 当期开奖号码）。
    返回: [(rule_dict, predict_nums, oof_weight), ...]
    """
    s = set(draw_nums)
    fired = []
    for r in rules:
        trigger = r.get("trigger", [])
        if trigger and all(x in s for x in trigger):
            pred = r.get("predict", [])
            w = float(r.get("hr_oof") or r.get("hr_train") or 0.0)
            fired.append((r, pred, w))
    return fired


def compute_target_issue(latest_issue: Any) -> str:
    """由当前最新期号推算下一期目标期号"""
    issue_str = str(latest_issue).strip()
    if len(issue_str) >= 7 and issue_str.isdigit():
        year = int(issue_str[:4])
        seq = int(issue_str[4:])
        return f"{year}{seq + 1:03d}"
    try:
        val = int(issue_str)
        return str(val + 1)
    except Exception:
        return f"{issue_str}_next"


def predict_jingle(draws: List[Tuple[int, str, List[int]]], rules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    顺口溜口诀每日预测核心逻辑。
    基于最新开奖号码扫描口诀库，聚合推荐码并计算理论期望。
    """
    if not draws:
        return {
            "status": "error",
            "message": "开奖历史数据为空",
            "fired_count": 0,
            "recommended_numbers": [],
        }

    if rules is None:
        rules, _ = load_jingle_rules()

    latest = draws[-1]
    l_issue, l_date, l_nums = latest
    target_issue = compute_target_issue(l_issue)

    fired = fired_rules(rules, l_nums)
    # 按 OOF 命中率从高到低排序
    fired.sort(key=lambda x: x[2], reverse=True)

    agg_scores: Dict[int, float] = {}
    fired_details = []

    for r, pred, w in fired:
        kind = r.get("kind", "pair_pair")
        is_pair = (kind == "pair_pair")
        base = BASELINE_PAIR if is_pair else BASELINE_TRIPLE
        lift = (w / base) if base > 0 else 0.0
        kind_name = "两号齐出" if is_pair else "单号带出"
        
        detail = {
            "rule_id": r.get("rule_id", ""),
            "kind": kind,
            "kind_name": kind_name,
            "trigger": r.get("trigger", []),
            "predict": pred,
            "oof_hit_rate": round(w, 4),
            "oof_lift": round(lift, 2),
            "triggers_oof": r.get("triggers_oof", 0),
            "hits_oof": r.get("hits_oof", 0),
            "hr_train": round(r.get("hr_train", 0.0), 4),
            "z_oof": round(r.get("z_oof", 0.0), 2),
        }
        fired_details.append(detail)

        for num in pred:
            agg_scores[num] = agg_scores.get(num, 0.0) + w

    rec_sorted = sorted(agg_scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_nums = [n for n, _ in rec_sorted]
    k_count = len(top_nums)
    expected_baseline = at_least_one_baseline(k_count)

    return {
        "status": "ok",
        "latest_issue": str(l_issue),
        "latest_date": l_date,
        "latest_numbers": l_nums,
        "target_issue": str(target_issue),
        "fired_count": len(fired),
        "fired_details": fired_details,
        "recommended_numbers": top_nums,
        "number_weights": {str(k): round(v, 4) for k, v in rec_sorted},
        "k_count": k_count,
        "at_least_one_baseline": round(expected_baseline, 4),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_jingle_prediction(predict_result: Dict[str, Any], custom_dir: Optional[str] = None) -> List[str]:
    """
    将预测结果持久化保存为文本产物。
    """
    target_issue = predict_result.get("target_issue", "unknown")
    l_issue = predict_result.get("latest_issue", "")
    l_date = predict_result.get("latest_date", "")
    top_nums = predict_result.get("recommended_numbers", [])
    fired_details = predict_result.get("fired_details", [])
    k_count = predict_result.get("k_count", 0)
    baseline_pct = predict_result.get("at_least_one_baseline", 0.0) * 100

    out_dirs = [
        custom_dir or os.path.join(_PROJ, "outputs", "predictions"),
        os.path.join(_PROJ, "outputs", "jingle"),
    ]

    content_lines = [
        "════════════════════════════════════════════════════════",
        f"  快乐8 顺口溜口诀预测报告 (目标期: {target_issue})",
        "════════════════════════════════════════════════════════",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"基准期号: {l_issue} ({l_date})",
        f"目标期号: {target_issue}",
        "────────────────────────────────────────────────────────",
        f"◎ 触发口诀推荐码（共 {k_count} 码，按加权得分排序）:",
        "  " + (" ".join(f"{n:02d}" for n in top_nums) if top_nums else "（今日无口诀触发）"),
        f"◎ 理论期望水平: 至少一中期望 ≈ {baseline_pct:.1f}% (超几何自适应基线)",
        "────────────────────────────────────────────────────────",
        f"◎ 触发口诀明细 (共触发 {len(fired_details)} 条精英口诀):",
    ]

    for d in fired_details:
        tr_s = " ".join(f"{x:02d}" for x in d["trigger"])
        pd_s = " ".join(f"{x:02d}" for x in d["predict"])
        content_lines.append(
            f"  - [{d['kind_name']}] 触发 [{tr_s}] → 推荐 [{pd_s}] | OOF命中率: {d['oof_hit_rate']*100:.1f}% (Lift={d['oof_lift']:.2f}x)"
        )

    content_lines.extend([
        "════════════════════════════════════════════════════════",
        "【大白话操盘锦囊】",
        "  口诀是历史规律的统计提炼。两号齐出属于死党粘连，单号带出属于强力引力。",
        "  建议结合今日金胆、选2搭档和KillSeeker杀号进行综合验证，避开高杀风险码！",
        "════════════════════════════════════════════════════════\n"
    ])

    saved_paths = []
    for d in out_dirs:
        try:
            os.makedirs(d, exist_ok=True)
            fpath = os.path.join(d, f"顺口溜预测_{target_issue}.txt")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(content_lines))
            saved_paths.append(fpath)
        except Exception as e:
            pass

    return saved_paths
