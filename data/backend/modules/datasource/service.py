# -*- coding: utf-8 -*-
"""DatasourceServiceMixin: methods extracted from QuantDataService"""
from __future__ import annotations

import os
import sys
import re
import json
import glob
import math
import logging
import collections
from datetime import datetime
from typing import Dict, List, Any, Optional

from backend.utils.paths import (
    get_cache_dir, get_outputs_dir, get_reports_dir, get_reviews_dir,
    get_project_root, data_path, get_storage_dir, _ensure_project_path,
)

logger = logging.getLogger("k8quant.service")


class DatasourceServiceMixin:
    def _enrich_datasource_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """统一补齐 gold_pair list / next_likely / 证据水印。"""
        if not isinstance(data, dict):
            return {}
        out = dict(data)
        gp = out.get("gold_pair")
        if isinstance(gp, tuple):
            out["gold_pair"] = list(gp)
        elif gp is None:
            out["gold_pair"] = []
        if "latest_excel_issue" in out and "anchor_period" not in out:
            out["anchor_period"] = out.get("latest_excel_issue")
        if "latest_period" not in out:
            out["latest_period"] = out.get("latest_excel_issue") or out.get("anchor_period")
        lift = out.get("hot_lift")
        n_eval = out.get("review_periods") or out.get("total_evaluated")
        if lift is not None:
            span = f"近{n_eval}期" if n_eval else "样本外"
            out["evidence_note"] = (
                f"结构推荐（非显著超额）；{span}热码 Lift={lift}"
                f"（基线1.0≈随机），仅作形态参考。"
            )
        elif not out.get("evidence_note"):
            out["evidence_note"] = (
                "结构推荐（非显著超额）；样本外热码 Lift 接近随机基线，仅作形态参考。"
            )
        if not out.get("next_likely_numbers") and out.get("top_hot_numbers"):
            # 兼容旧 json/txt：用 Top5 做最小可用排名
            out["next_likely_numbers"] = [
                {
                    "ball": int(n),
                    "score": float(5 - i),
                    "sources": ["爆发Top5"],
                    "kill_flags": [],
                    "in_consensus": int(n) in set(out.get("consensus_numbers") or []),
                    "in_gold_pair": int(n) in set(out.get("gold_pair") or []),
                    "in_top_hot": True,
                }
                for i, n in enumerate(out.get("top_hot_numbers") or [])
            ]
        top_hot = out.get("top_hot_numbers") or []
        out["top3_gold"] = [int(x) for x in top_hot[:3]]
        out.pop("top_cold_numbers", None)
        out.pop("non_d2_kills", None)
        return out

    def get_datasource_summary(self) -> Dict[str, Any]:
        """获取数据源1×2最新深层关联预测（优先 JSON，完整字段含 next_likely_numbers）。"""
        out_dir = os.path.join(get_outputs_dir(), "deep_association")
        json_files = sorted(glob.glob(os.path.join(out_dir, "深层关联预测_*.json")))
        if json_files:
            try:
                with open(json_files[-1], "r", encoding="utf-8") as f:
                    payload = json.load(f)
                return {"status": "ok", "data": self._enrich_datasource_payload(payload)}
            except Exception as e:
                logger.warning("读取深层关联 JSON 失败: %s", e)

        try:
            from backend.modules.datasource.datasource_predictor import predict_datasource_deep
            res = predict_datasource_deep()
            if res:
                return {"status": "ok", "data": self._enrich_datasource_payload(res)}
        except Exception as e:
            logger.warning("现场推演 predict_datasource_deep 失败: %s", e)

        # 兼容旧 txt
        da_pattern = os.path.join(out_dir, "深层关联预测_*.txt")
        da_files = sorted(glob.glob(da_pattern))
        if da_files:
            try:
                with open(da_files[-1], "r", encoding="utf-8") as f:
                    da_txt = f.read()
                period_m = re.search(r"目标期\s*(\d+)", da_txt)
                hot_m = re.search(r"\[精选爆发(?:最优3码| Top 5)\]:\s*([0-9, ]+)", da_txt)
                cons_m = re.search(r"\[跨规则共识金胆\]:\s*([0-9, ]+)", da_txt)
                pair_m = re.search(r"\[黄金连体婴选2\]:\s*\[(\d{2})-(\d{2})\]", da_txt)

                hot_picks = [int(x) for x in re.findall(r"\d{2}", hot_m.group(1))][:3] if hot_m else []
                cons_picks = [int(x) for x in re.findall(r"\d{2}", cons_m.group(1))] if (cons_m and "无" not in cons_m.group(1)) else []
                pair_picks = [int(pair_m.group(1)), int(pair_m.group(2))] if pair_m else []
                payload = {
                    "target_period": int(period_m.group(1)) if period_m else None,
                    "top_hot_numbers": hot_picks,
                    "top3_gold": hot_picks,
                    "consensus_numbers": cons_picks,
                    "gold_pair": pair_picks,
                }
                return {"status": "ok", "data": self._enrich_datasource_payload(payload)}
            except Exception:
                pass

        return {"status": "error", "message": "尚未生成数据源1×2深层关联预测"}

    def get_datasource_review(self, n: int = 30) -> Dict[str, Any]:
        """获取近 N 期数据源1×2 样本外 Walk-Forward 对账流水与命中指标"""
        try:
            from core.datasource_predictor import walk_forward_review_datasource
            res = walk_forward_review_datasource(n_review=n)
            return {"status": "ok", "data": res}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_datasource_history_list(self) -> List[Dict[str, Any]]:
        """获取数据源1×2深层关联历史预测清单"""
        out_dir = os.path.join(get_outputs_dir(), "deep_association")
        if not os.path.exists(out_dir):
            return []
        results = []
        for f in os.listdir(out_dir):
            if f.startswith("深层关联预测_") and f.endswith(".txt"):
                period_match = re.search(r"深层关联预测_(\d+)", f)
                period = period_match.group(1) if period_match else "N/A"
                fpath = os.path.join(out_dir, f)
                results.append({
                    "filename": f,
                    "period": period,
                    "title": f"第 {period} 期 数据源1×2深层关联预测单",
                    "mtime": datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S"),
                    "size_bytes": os.path.getsize(fpath)
                })
        results.sort(key=lambda x: int(x["period"]) if x["period"].isdigit() else 0, reverse=True)
        return results

    def get_datasource_matrix_by_period(self, period: Optional[str] = None) -> Dict[str, Any]:
        """获取指定期号(或最新期)《跟随+点位+开奖数据.xlsx》数据源1与数据源2高保真原始阵列数据"""
        try:
            from core.excel_deep_mining_v2 import load_excel_full
            from utils.history_loader import load_history
            
            records = load_excel_full()
            if not records:
                return {"status": "error", "message": "未能读取到Excel跟随号码统计表数据"}
            
            # 收集全部期号
            issue_set = set(r['issue'] for r in records)
            available_periods = sorted(list(issue_set), key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
            
            target_period = str(period).strip() if period else (available_periods[0] if available_periods else "")
            if target_period not in issue_set:
                target_period = available_periods[0] if available_periods else ""
            
            # 加载实际开奖历史
            history = load_history()
            draw_map = {h['issue']: h for h in history}
            target_draw = draw_map.get(target_period, {})
            actual_numbers = sorted(list(target_draw.get('numbers', [])))
            draw_date = target_draw.get('date', '')
            
            # 过滤当期记录
            cur_records = [r for r in records if r['issue'] == target_period]
            
            def build_source_data(dtype_val: int):
                # 4 个 Block, 每个 Block 4行 x 4列 left, 4行 x 4列 right
                blocks = []
                unique_nums = set()
                stars = set()
                points = set()
                wins = set()
                
                for b_idx in range(4):
                    left_grid = [[None for _ in range(4)] for _ in range(4)]
                    right_grid = [[None for _ in range(4)] for _ in range(4)]
                    
                    b_records = [r for r in cur_records if r['dtype'] == dtype_val and r['block'] == b_idx]
                    for r in b_records:
                        num = r['num']
                        unique_nums.add(num)
                        if r['is_star']: stars.add(num)
                        if r['is_point']: points.add(num)
                        if r['is_win'] or (actual_numbers and num in actual_numbers):
                            wins.add(num)
                            is_win_val = True
                        else:
                            is_win_val = r['is_win']
                            
                        cell_data = {
                            "num": num,
                            "num_str": f"{num:02d}",
                            "is_star": r['is_star'],
                            "is_point": r['is_point'],
                            "is_win": is_win_val,
                            "side": r['side'],
                            "row": r['row'],
                            "col": r['col']
                        }
                        if r['side'] == 'left' and 0 <= r['row'] < 4 and 0 <= r['col'] < 4:
                            left_grid[r['row']][r['col']] = cell_data
                        elif r['side'] == 'right' and 0 <= r['row'] < 4 and 0 <= r['col'] < 4:
                            right_grid[r['row']][r['col']] = cell_data
                            
                    blocks.append({
                        "block_idx": b_idx,
                        "block_name": f"Block {b_idx} (第{b_idx+1}板块)",
                        "left_grid": left_grid,
                        "right_grid": right_grid
                    })
                
                # 统计
                unique_list = sorted(list(unique_nums))
                hit_nums = [n for n in unique_list if n in actual_numbers] if actual_numbers else list(wins)
                hit_rate = round(len(hit_nums) / len(unique_list), 4) if unique_list else 0.0
                
                return {
                    "blocks": blocks,
                    "stats": {
                        "total_count": len(unique_list),
                        "unique_numbers": unique_list,
                        "hit_count": len(hit_nums),
                        "hit_numbers": hit_nums,
                        "hit_rate": hit_rate,
                        "star_count": len(stars),
                        "star_numbers": sorted(list(stars)),
                        "point_count": len(points),
                        "point_numbers": sorted(list(points))
                    }
                }
            
            data1 = build_source_data(1)
            data2 = build_source_data(2)
            
            # 跨源交叉统计
            d1_set = set(data1["stats"]["unique_numbers"])
            d2_set = set(data2["stats"]["unique_numbers"])
            intersection = sorted(list(d1_set & d2_set))
            intersection_hits = [n for n in intersection if n in actual_numbers]
            non_d2 = sorted(list(set(range(1, 81)) - d2_set))
            
            return {
                "status": "ok",
                "period": target_period,
                "available_periods": available_periods,
                "actual_numbers": actual_numbers,
                "draw_date": draw_date,
                "is_drawn": bool(actual_numbers),
                "data1": data1,
                "data2": data2,
                "cross_stats": {
                    "intersection": intersection,
                    "intersection_hits": intersection_hits,
                    "intersection_hit_rate": round(len(intersection_hits) / len(intersection), 4) if intersection else 0.0,
                    "non_d2": non_d2,
                }
            }
        except Exception as e:
            return {"status": "error", "message": f"加载数据源矩阵失败: {str(e)}"}

