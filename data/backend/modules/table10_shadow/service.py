# -*- coding: utf-8 -*-
"""
表10「同数值」影子观察服务 (Shadow Observation Engine)

只读取本地台账 `storage/表10_前三排行_识别台账.xlsx`，并与实时开奖历史自动对账，
严守“只记账不投票”原则：不参与主系统任何打分或投票，仅追踪胜率与转正进度。
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import openpyxl

from backend.utils.paths import data_path


LEDGER_REL_PATH = os.path.join("storage", "表10_前三排行_识别台账.xlsx")
HISTORY_REL_PATH = os.path.join("storage", "raw", "kl8_history_final.txt")
GRADUATION_MIN_CLEAN_PERIODS = 15
GRADUATION_MIN_LIFT = 1.12
BASELINE_PROB = 0.25


def _load_draws_map(history_path: Optional[str] = None) -> Dict[int, Set[int]]:
    """从 kl8_history_final.txt 加载 {期号: 开奖20码集合}。"""
    import re
    path = history_path or data_path(HISTORY_REL_PATH)
    draws: Dict[int, Set[int]] = {}
    if not os.path.exists(path):
        return draws
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r"period:(\d+),numbers:([\d-]+)", line)
            if m:
                issue = int(m.group(1))
                nums = {int(x) for x in m.group(2).split("-") if x.isdigit() and 1 <= int(x) <= 80}
            else:
                parts = line.strip().replace(",", " ").split()
                if len(parts) < 22 or not parts[0].isdigit():
                    continue
                issue = int(parts[0])
                nums = {int(x) for x in parts[2:22] if x.isdigit() and 1 <= int(x) <= 80}
            if len(nums) == 20:
                draws[issue] = nums
    if draws:
        latest_year = max(draws.keys()) // 1000
        for issue in list(draws.keys()):
            if issue // 1000 == latest_year:
                draws[issue % 1000] = draws[issue]
    return draws


def _load_ledger_rows(excel_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """读取 `明细台账_结构化` 工作表的所有记录。"""
    path = excel_path or data_path(LEDGER_REL_PATH)
    if not os.path.exists(path):
        return []
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    if "明细台账_结构化" not in wb.sheetnames:
        wb.close()
        return []
    ws = wb["明细台账_结构化"]
    rows: List[Dict[str, Any]] = []
    header = None
    for idx, row in enumerate(ws.iter_rows(values_only=True)):
        if idx == 0:
            header = list(row)
            continue
        if not row or row[0] is None:
            continue
        try:
            period = int(row[0])
            board_type = str(row[1] or "")
            out_val = int(row[2])
            slot_idx = int(row[3])
            num = int(row[4])
        except (TypeError, ValueError):
            continue
        raw_text = str(row[5] or num)
        has_star = str(row[6] or "") == "是"
        is_red_font = str(row[7] or "") == "是"
        mark_bg = str(row[8] or "否")
        source = str(row[10] or "") if len(row) > 10 else ""
        rows.append({
            "period": period,
            "board_type": board_type,
            "out_val": out_val,
            "slot_idx": slot_idx,
            "num": num,
            "raw_text": raw_text,
            "has_star": has_star,
            "is_red_font": is_red_font,
            "mark_bg": mark_bg,
            "source": source,
        })
    wb.close()
    return rows


def get_shadow_summary(
    excel_path: Optional[str] = None,
    history_path: Optional[str] = None,
) -> Dict[str, Any]:
    """计算表10「同数值」影子观察完整汇总与逐期对账。"""
    rows = _load_ledger_rows(excel_path)
    draws = _load_draws_map(history_path)
    if not rows:
        return {
            "status": "empty",
            "message": "表10识别台账暂无数据",
            "periods": [],
            "latest": None,
            "metrics": {
                "total_periods": 0,
                "clean_periods": 0,
                "clean_rf_total": 0,
                "clean_rf_hits": 0,
                "clean_rf_hit_rate": 0.0,
                "clean_rf_lift": 0.0,
                "clean_blk_total": 0,
                "clean_blk_hits": 0,
                "clean_blk_hit_rate": 0.0,
                "graduation_target_periods": GRADUATION_MIN_CLEAN_PERIODS,
                "graduation_target_lift": GRADUATION_MIN_LIFT,
                "ready_to_graduate": False,
            },
        }

    by_period: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_period[r["period"]].append(r)

    period_summaries: List[Dict[str, Any]] = []
    clean_rf_total = clean_rf_hits = 0
    clean_blk_total = clean_blk_hits = 0
    clean_periods = 0

    for p in sorted(by_period.keys()):
        items = by_period[p]
        draw_set = draws.get(p)
        is_drawn = draw_set is not None and len(draw_set) == 20
        source = items[0]["source"]

        # 是否为“纯净开奖前数据”（未被开奖红底遮盖原本字体颜色）
        has_red_bg_draw = any(it["mark_bg"] == "开奖红底" for it in items)
        is_clean_pre_draw = is_drawn and not has_red_bg_draw

        rf_nums: List[int] = []
        rf_hits: List[int] = []
        blk_nums: List[int] = []
        blk_hits: List[int] = []
        pt_nums: List[int] = []
        max_nums: Set[int] = set()
        min_nums: Set[int] = set()
        all_nums: Set[int] = set()
        overflow_rows: List[Dict[str, Any]] = []

        by_board_out: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)
        for it in items:
            num = it["num"]
            all_nums.add(num)
            if "最大" in it["board_type"]:
                max_nums.add(num)
            elif "最小" in it["board_type"]:
                min_nums.add(num)
            if it["mark_bg"] == "点位":
                pt_nums.append(num)
            if it["is_red_font"]:
                rf_nums.append(num)
                if is_drawn and num in draw_set:
                    rf_hits.append(num)
            elif it["mark_bg"] != "开奖红底":
                blk_nums.append(num)
                if is_drawn and num in draw_set:
                    blk_hits.append(num)
            by_board_out[(it["board_type"], it["out_val"])].append(it)

        for (bt, ov), grp in sorted(by_board_out.items()):
            if len(grp) > 3:
                overflow_rows.append({
                    "board_type": bt,
                    "out_val": ov,
                    "numbers": [g["num"] for g in grp],
                    "count": len(grp),
                })

        cross_overlap = sorted(max_nums & min_nums)
        pt_unique = sorted(set(pt_nums))
        rf_unique = sorted(set(rf_nums))
        double_resonance = sorted((set(rf_unique) | set(cross_overlap)) & set(pt_unique))
        all_hits = sorted(n for n in all_nums if is_drawn and n in draw_set)

        if is_clean_pre_draw and rf_nums:
            clean_periods += 1
            clean_rf_total += len(rf_nums)
            clean_rf_hits += len(rf_hits)
            clean_blk_total += len(blk_nums)
            clean_blk_hits += len(blk_hits)

        rf_rate = round(len(rf_hits) / len(rf_nums), 4) if (is_drawn and rf_nums) else None
        blk_rate = round(len(blk_hits) / len(blk_nums), 4) if (is_drawn and blk_nums) else None
        rf_lift = round(rf_rate / BASELINE_PROB, 2) if rf_rate is not None else None

        period_summaries.append({
            "period": p,
            "source": source,
            "status": "已开奖" if is_drawn else "待开奖",
            "is_clean_pre_draw": is_clean_pre_draw,
            "has_red_bg_mask": has_red_bg_draw,
            "total_items": len(items),
            "unique_count": len(all_nums),
            "rf_count": len(rf_nums),
            "rf_numbers": rf_unique,
            "rf_hits": len(rf_hits) if is_drawn else None,
            "rf_hit_numbers": sorted(set(rf_hits)) if is_drawn else [],
            "rf_hit_rate": rf_rate,
            "rf_lift": rf_lift,
            "blk_count": len(blk_nums),
            "blk_hits": len(blk_hits) if is_drawn else None,
            "blk_hit_rate": blk_rate,
            "cross_overlap": cross_overlap,
            "point_matches": pt_unique,
            "double_resonance": double_resonance,
            "overflow_rows": overflow_rows,
            "all_hits_count": len(all_hits) if is_drawn else None,
            "all_hits": all_hits,
            "draw_numbers": sorted(draw_set) if is_drawn else [],
        })

    clean_rf_rate = round(clean_rf_hits / clean_rf_total, 4) if clean_rf_total else 0.0
    clean_rf_lift = round(clean_rf_rate / BASELINE_PROB, 2) if clean_rf_total else 0.0
    clean_blk_rate = round(clean_blk_hits / clean_blk_total, 4) if clean_blk_total else 0.0
    ready = (
        clean_periods >= GRADUATION_MIN_CLEAN_PERIODS
        and clean_rf_lift >= GRADUATION_MIN_LIFT
    )

    latest = period_summaries[-1] if period_summaries else None
    return {
        "status": "success",
        "module_status": "observation",
        "rule_note": "只记账不投票：在纯净对照期达标前，严禁参与主系统打分或推荐权重。",
        "ledger_path": LEDGER_REL_PATH,
        "latest": latest,
        "periods": list(reversed(period_summaries)),
        "metrics": {
            "total_periods": len(period_summaries),
            "clean_periods": clean_periods,
            "clean_rf_total": clean_rf_total,
            "clean_rf_hits": clean_rf_hits,
            "clean_rf_hit_rate": clean_rf_rate,
            "clean_rf_lift": clean_rf_lift,
            "clean_blk_total": clean_blk_total,
            "clean_blk_hits": clean_blk_hits,
            "clean_blk_hit_rate": clean_blk_rate,
            "graduation_target_periods": GRADUATION_MIN_CLEAN_PERIODS,
            "graduation_target_lift": GRADUATION_MIN_LIFT,
            "ready_to_graduate": ready,
        },
    }


def get_period_detail(
    period: int,
    excel_path: Optional[str] = None,
    history_path: Optional[str] = None,
) -> Dict[str, Any]:
    """获取指定期号的遗漏分层对照矩阵明细。"""
    rows = [r for r in _load_ledger_rows(excel_path) if r["period"] == period]
    if not rows:
        return {"status": "not_found", "period": period, "rows": []}
    draws = _load_draws_map(history_path)
    draw_set = draws.get(period, set())
    is_drawn = len(draw_set) == 20

    out_levels: Dict[int, Dict[str, List[Dict[str, Any]]]] = defaultdict(
        lambda: {"max": [], "min": []}
    )
    for r in rows:
        bucket = "max" if "最大" in r["board_type"] else "min"
        out_levels[r["out_val"]][bucket].append({
            "num": r["num"],
            "raw_text": r["raw_text"],
            "has_star": r["has_star"],
            "is_red_font": r["is_red_font"],
            "mark_bg": r["mark_bg"],
            "is_hit": (r["num"] in draw_set) if is_drawn else None,
        })

    matrix = []
    for ov in sorted(out_levels.keys()):
        matrix.append({
            "out_val": ov,
            "max": out_levels[ov]["max"],
            "min": out_levels[ov]["min"],
        })

    return {
        "status": "success",
        "period": period,
        "is_drawn": is_drawn,
        "draw_numbers": sorted(draw_set) if is_drawn else [],
        "source": rows[0]["source"],
        "matrix": matrix,
    }
