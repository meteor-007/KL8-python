# -*- coding: utf-8 -*-
"""
common_ai_review.py - 顶级数学与AI现代高精战区通用 Walk-Forward 样本外滚动对账计算引擎
========================================================================================
【业务背景与架构定位】:
统一为线性代数 (linear_algebra)、动态时间规整 (dtw)、Transformer (transformer)、
矩阵轮廓 (matrix_profile)、拓扑数据分析 (tda) 提供严格无未来函数的近 N 期逐期滚动实战对账计算与极速缓存。

@author K8-Quant AI Quantitative Team
@since 2026-09-11
"""
from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Type, Optional

from backend.utils.paths import get_cache_dir
from backend.utils.history_loader import load_history

logger = logging.getLogger("k8quant.ai_review")


def compute_rolling_ai_review(
    module_name: str,
    engine_class: Type[Any],
    n: int = 30,
    force_refresh: bool = False,
    history_buffer: int = 35,
    cache_tag: Optional[str] = None,
) -> Dict[str, Any]:
    """
    通用近 N 期 Walk-Forward 滚动样本外对账流水与统计指标计算
    @param module_name 模块标识 (e.g. 'linear_algebra', 'dtw_matching', etc.)
    @param engine_class 对应模块的核心推演引擎类
    @param n 滚动回溯期数 (默认 30)
    @param force_refresh 是否强制重新计算
    @param history_buffer 每折训练额外历史缓冲（线性代数用 100，与实盘近窗对齐）
    @param cache_tag 可选缓存后缀（如 p2），用于口径变更隔离旧缓存
    @return Dict 包含统计指标与逐期对账明细列表
    """
    buf = max(5, int(history_buffer or 35))
    history = load_history(limit=n + buf)
    if not history or len(history) < n + 5:
        return {"status": "error", "message": "历史开奖数据不足以进行样本外滚动对账"}

    cache_dir = os.path.join(get_cache_dir(), module_name)
    os.makedirs(cache_dir, exist_ok=True)
    tag = f"_{cache_tag}" if cache_tag else ""
    cache_file = os.path.join(cache_dir, f"review_{n}_buf{buf}{tag}.json")

    latest_item = history[0]
    latest_period = int(latest_item.get("period", latest_item.get("issue", 0)))

    # 1. 检查缓存
    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                if (
                    cached_data.get("latest_period") == latest_period
                    and cached_data.get("n_periods") == n
                    and cached_data.get("history_buffer") == buf
                    and cached_data.get("cache_tag", None) == (cache_tag or None)
                ):
                    return cached_data
        except Exception as e:
            logger.warning("读取 %s 对账缓存失败: %s", module_name, e)

    def _parse_pair_balls(item: Any) -> List[int]:
        if not isinstance(item, dict):
            return []
        if "balls" in item and isinstance(item["balls"], list) and len(item["balls"]) >= 2:
            try:
                return [int(x) for x in item["balls"][:2]]
            except (TypeError, ValueError):
                return []
        pair_str = str(item.get("pair", ""))
        if not pair_str:
            return []
        sep = "+" if "+" in pair_str else ("-" if "-" in pair_str else "+")
        out = []
        for p in pair_str.split(sep):
            p = p.strip()
            if p.isdigit():
                out.append(int(p))
        return out[:2]

    # 2. 逐期 Walk-Forward 滚动推演
    try:
        records: List[Dict[str, Any]] = []
        total_top3_hits = 0
        total_gold_hits = 0
        total_gold_pair_hits = 0
        total_pair1_double = 0
        total_pair2_double = 0
        total_any_pair_double = 0
        total_both_pairs_double = 0
        total_pair1_hit1plus = 0
        total_pair2_hit1plus = 0

        for i in range(n):
            target_idx = i
            target_item = history[target_idx]
            target_period = int(target_item.get("period", target_item.get("issue", 0)))
            actual_draw = target_item.get("numbers", [])
            actual_set = set(actual_draw)

            # 使用截至 target_idx + 1 的历史切片（严禁未来数据穿越）
            sub_hist = history[target_idx + 1 :]
            engine = engine_class(history_data=sub_hist)
            pred = engine.run_prediction()

            # 主口径：最优 3 码（兼容旧 top5_gold / top5_assault）
            top3 = list(pred.get("top3_gold") or pred.get("top5_gold") or pred.get("top5_assault") or [])[:3]
            gold = top3[0] if top3 else 0

            gold_pairs_raw = pred.get("gold_pairs", []) or []
            pair1 = _parse_pair_balls(gold_pairs_raw[0]) if len(gold_pairs_raw) >= 1 else []
            pair2 = _parse_pair_balls(gold_pairs_raw[1]) if len(gold_pairs_raw) >= 2 else []
            if len(pair1) < 2 and len(top3) >= 2:
                pair1 = top3[:2]
            # 兼容旧字段：首组作为 gold_pair
            gold_pair = pair1

            hit_top3 = len(actual_set.intersection(top3))
            hit_gold = 1 if gold in actual_set else 0
            hit_gold_pair = len(actual_set.intersection(gold_pair)) if gold_pair else 0

            p1_hits = len(actual_set.intersection(pair1)) if len(pair1) >= 2 else 0
            p2_hits = len(actual_set.intersection(pair2)) if len(pair2) >= 2 else 0
            p1_double = p1_hits == 2
            p2_double = p2_hits == 2
            any_double = p1_double or p2_double
            both_double = p1_double and p2_double

            total_top3_hits += hit_top3
            total_gold_hits += hit_gold
            if hit_gold_pair == 2:
                total_gold_pair_hits += 1
            if p1_double:
                total_pair1_double += 1
            if p2_double:
                total_pair2_double += 1
            if any_double:
                total_any_pair_double += 1
            if both_double:
                total_both_pairs_double += 1
            if p1_hits >= 1:
                total_pair1_hit1plus += 1
            if p2_hits >= 1:
                total_pair2_hit1plus += 1

            hit_top3_nums = sorted(list(actual_set.intersection(top3)))
            hit_gold_pair_nums = sorted(list(actual_set.intersection(gold_pair))) if gold_pair else []

            records.append({
                "period": target_period,
                "draw_date": target_item.get("date", ""),
                "actual_draw": actual_draw,
                "top3": top3,
                "top3_hits": hit_top3,
                "top3_hit_nums": hit_top3_nums,
                # 兼容旧前端字段名（内容同 top3）
                "top5": top3,
                "top5_hits": hit_top3,
                "top5_hit_nums": hit_top3_nums,
                "top12": top3,
                "top12_hits": hit_top3,
                "top12_hit_nums": hit_top3_nums,
                "gold_core": gold,
                "gold_hit": hit_gold == 1,
                "gold_pair": gold_pair,
                "gold_pair_hits": hit_gold_pair,
                "gold_pair_hit_nums": hit_gold_pair_nums,
                "pair1": pair1,
                "pair1_hits": p1_hits,
                "pair1_double": p1_double,
                "pair2": pair2,
                "pair2_hits": p2_hits,
                "pair2_double": p2_double,
                "any_pair_double": any_double,
                "both_pairs_double": both_double,
            })

        # 3. 统计汇总（主口径 Top3；不再输出 Top5/Top12 随机基线 Lift）
        avg_top3_hit = round(total_top3_hits / max(1, n), 2)
        gold_hit_rate = round(total_gold_hits / max(1, n) * 100.0, 1)
        pair_double_rate = round(total_gold_pair_hits / max(1, n) * 100.0, 1)

        pair1_double_rate = round(total_pair1_double / max(1, n) * 100.0, 1)
        pair2_double_rate = round(total_pair2_double / max(1, n) * 100.0, 1)
        any_pair_double_rate = round(total_any_pair_double / max(1, n) * 100.0, 1)
        both_pairs_double_rate = round(total_both_pairs_double / max(1, n) * 100.0, 1)
        pair1_single_rate = round(total_pair1_hit1plus / max(1, n) * 100.0, 1)
        pair2_single_rate = round(total_pair2_hit1plus / max(1, n) * 100.0, 1)

        review_result = {
            "status": "success",
            "module_name": module_name,
            "latest_period": latest_period,
            "n_periods": n,
            "history_buffer": buf,
            "cache_tag": cache_tag,
            "stats": {
                "avg_top3_hit": avg_top3_hit,
                "avg_top5_hit": avg_top3_hit,  # 兼容旧前端
                "avg_top12_hit": avg_top3_hit,  # 兼容旧前端
                "gold_hit_rate": gold_hit_rate,
                "pair_double_rate": pair_double_rate,
                "pair1_double_rate": pair1_double_rate,
                "pair2_double_rate": pair2_double_rate,
                "any_pair_double_rate": any_pair_double_rate,
                "both_pairs_double_rate": both_pairs_double_rate,
                "pair1_single_rate": pair1_single_rate,
                "pair2_single_rate": pair2_single_rate,
                "total_periods": n
            },
            "records": records,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(review_result, f, ensure_ascii=False, indent=2)

        # 同时同步一份到 frontend/static/ 作为极速无缝静态容灾镜像
        try:
            static_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static", f"{module_name}_review_{n}.json")
            with open(static_file, "w", encoding="utf-8") as sf:
                json.dump(review_result, sf, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return review_result

    except Exception as e:
        logger.error("❌ %s 滚动对账异常: %s", module_name, e, exc_info=True)
        return {"status": "error", "message": f"{module_name} 滚动对账异常: {str(e)}"}


def compute_consensus_rolling_review(
    n: int = 30,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    聚合六大核心前沿数学与AI模型（遗传算法、线性代数、DTW、Transformer、矩阵轮廓、TDA）
    近 N 期 Walk-Forward 滚动样本外超级共识对账流水与统计指标
    @param n 滚动回溯期数 (默认 30)
    @param force_refresh 是否强制刷新
    @return Dict 包含统计指标与逐期对账明细列表
    """
    cache_dir = os.path.join(get_cache_dir(), "ai_math_consensus")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"review_{n}.json")

    history = load_history(limit=n + 35)
    latest_period = int(history[0].get("period", history[0].get("issue", 0))) if history else 0

    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                if cached_data.get("latest_period") == latest_period and cached_data.get("n_periods") == n:
                    return cached_data
        except Exception as e:
            logger.warning("读取 AI 超级共识对账缓存失败: %s", e)

    try:
        from backend.modules._retired.linear_algebra.service import get_linear_algebra_review
        from backend.modules._retired.dtw_matching.service import get_dtw_review
        from backend.modules._retired.transformer_attention.service import get_transformer_review
        from backend.modules._retired.matrix_profile.service import get_matrix_profile_review
        from backend.modules._retired.tda_engine.service import get_tda_review
        from backend.api.deps import data_service

        # 1. 批量加载 6 大模型样本外对账流水
        la_res = get_linear_algebra_review(n=n, force_refresh=force_refresh)
        dtw_res = get_dtw_review(n=n, force_refresh=force_refresh)
        tf_res = get_transformer_review(n=n, force_refresh=force_refresh)
        mp_res = get_matrix_profile_review(n=n, force_refresh=force_refresh)
        tda_res = get_tda_review(n=n, force_refresh=force_refresh)
        ga_res = data_service.get_genetic_review(n=n)

        # 转换为按期号映射的字典
        def to_map(res_dict: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
            if not isinstance(res_dict, dict):
                return {}
            return {r.get("period"): r for r in res_dict.get("records", []) if "period" in r}

        la_map = to_map(la_res)
        dtw_map = to_map(dtw_res)
        tf_map = to_map(tf_res)
        mp_map = to_map(mp_res)
        tda_map = to_map(tda_res)
        ga_map = to_map(ga_res)

        records: List[Dict[str, Any]] = []
        total_top3_hits = 0
        total_gold_hits = 0
        total_gold_pair_hits = 0

        # 获取有效的对账期号序列 (按期号降序，即最近的期在最前)
        periods_order = [int(h.get("period", h.get("issue", 0))) for h in history[:n]]

        for period in periods_order:
            hist_item = next((h for h in history if int(h.get("period", h.get("issue", 0))) == period), None)
            if not hist_item:
                continue
            actual_draw = hist_item.get("numbers", [])
            actual_set = set(actual_draw)
            draw_date = hist_item.get("date", "")

            # 初始化 80 球打分表
            balls = [{
                "ball": b_idx,
                "score": 0.0,
                "vote_count": 0,
                "sources": [],
            } for b_idx in range(1, 81)]

            def add_votes(m_rec: Optional[Dict[str, Any]], code: str, weight: float = 1.0):
                if not m_rec:
                    return
                top3_nums = list(m_rec.get("top3") or m_rec.get("top5") or [])[:3]

                for idx, b in enumerate(top3_nums):
                    if 1 <= b <= 80:
                        item = balls[b - 1]
                        item["score"] += (3.0 - idx * 0.5) * weight
                        item["vote_count"] += 1
                        if code not in item["sources"]:
                            item["sources"].append(code)

            add_votes(ga_map.get(period), "GA", 1.05)
            add_votes(la_map.get(period), "SVD", 1.0)
            add_votes(dtw_map.get(period), "DTW", 1.0)
            add_votes(tf_map.get(period), "TRANS", 1.0)
            add_votes(mp_map.get(period), "MP", 1.0)
            add_votes(tda_map.get(period), "TDA", 1.0)

            # 按得分降序、票数降序排序 → 主推最优 3 码
            sorted_balls = sorted(balls, key=lambda x: (x["score"], x["vote_count"]), reverse=True)
            top3 = [x["ball"] for x in sorted_balls[:3]]
            gold = top3[0] if top3 else 0

            # 黄金搭档选2
            gold_pair = top3[:2] if len(top3) >= 2 else [1, 2]

            hit_top3 = len(actual_set.intersection(top3))
            hit_gold = 1 if gold in actual_set else 0
            hit_gold_pair = len(actual_set.intersection(gold_pair))

            total_top3_hits += hit_top3
            total_gold_hits += hit_gold
            if hit_gold_pair == 2:
                total_gold_pair_hits += 1

            top3_details = [{
                "ball": b,
                "score": round(balls[b - 1]["score"], 2),
                "vote_count": balls[b - 1]["vote_count"],
                "sources": balls[b - 1]["sources"],
                "is_hit": b in actual_set
            } for b in top3]

            records.append({
                "period": period,
                "draw_date": draw_date,
                "actual_draw": actual_draw,
                "top3": top3,
                "top3_hits": hit_top3,
                "top3_hit_nums": sorted(list(actual_set.intersection(top3))),
                "top3_details": top3_details,
                "top5": top3,
                "top5_hits": hit_top3,
                "top5_hit_nums": sorted(list(actual_set.intersection(top3))),
                "top5_details": top3_details,
                "top12": top3,
                "top12_hits": hit_top3,
                "top12_hit_nums": sorted(list(actual_set.intersection(top3))),
                "top12_details": top3_details,
                "gold_core": gold,
                "gold_hit": hit_gold == 1,
                "gold_pair": gold_pair,
                "gold_pair_hits": hit_gold_pair,
                "gold_pair_hit_nums": sorted(list(actual_set.intersection(gold_pair))),
            })

        # 统计汇总（主口径 Top3，无随机基线 Lift）
        calc_n = max(1, len(records))
        avg_top3_hit = round(total_top3_hits / calc_n, 2)
        gold_hit_rate = round(total_gold_hits / calc_n * 100.0, 1)
        pair_double_rate = round(total_gold_pair_hits / calc_n * 100.0, 1)

        review_result = {
            "status": "success",
            "module_name": "ai_math_consensus",
            "latest_period": latest_period,
            "n_periods": calc_n,
            "stats": {
                "avg_top3_hit": avg_top3_hit,
                "avg_top5_hit": avg_top3_hit,
                "avg_top12_hit": avg_top3_hit,
                "gold_hit_rate": gold_hit_rate,
                "pair_double_rate": pair_double_rate,
                "total_periods": calc_n
            },
            "records": records,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(review_result, f, ensure_ascii=False, indent=2)

        # 同时同步一份到 frontend/static/ 作为极速无缝静态容灾镜像
        try:
            static_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static", f"ai_consensus_review_{calc_n}.json")
            with open(static_file, "w", encoding="utf-8") as sf:
                json.dump(review_result, sf, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return review_result

    except Exception as e:
        logger.error("❌ 六大AI超级共识滚动对账异常: %s", e, exc_info=True)
        return {"status": "error", "message": f"六大AI超级共识滚动对账异常: {str(e)}"}
