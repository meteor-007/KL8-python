# -*- coding: utf-8 -*-
"""
GeneticServiceMixin: 快乐8 遗传算法业务服务封装与滚动对账
===========================================================
【业务背景与架构定位】:
负责与 FastAPI 路由和 QuantDataService 对接，提供：
1. 遗传算法最新期大屏推演数据 (`get_genetic_summary`)；
2. 历史样本外滚动对账流水与命中天梯统计 (`get_genetic_review`)；
3. 在线即时进化求解接口 (`run_genetic_evolution`)。

@author Antigravity Quantitative Team
@since 2026-09-11
"""

from __future__ import annotations

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from backend.utils.paths import (
    get_cache_dir, get_outputs_dir, get_reports_dir, get_reviews_dir,
    get_project_root, data_path, get_storage_dir, _ensure_project_path,
)

logger = logging.getLogger("k8quant.service")


class GeneticServiceMixin:
    """遗传算法服务 Mixin，混入 QuantDataService"""

    def get_genetic_summary(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取遗传算法最新期推演大屏数据 (优先读取缓存，期号不一致时自愈计算)
        @param force_refresh 是否强制重新进化计算
        @return Dict 大屏推演核心数据字典
        """
        history = self.load_history(limit=1)
        curr_latest_period = int(history[0]["period"]) if history and str(history[0].get("period", "")).isdigit() else None
        
        cache_dir = os.path.join(get_cache_dir(), "genetic_algorithm")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, "latest_summary.json")

        if not force_refresh and os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if curr_latest_period is None or data.get("latest_period") == curr_latest_period:
                        return data
            except Exception as e:
                logger.warning("⚠️ 读取遗传算法缓存失败: %s", e)

        # 触发核心引擎计算
        try:
            from backend.modules._retired.genetic_algorithm.genetic_engine import GeneticAlgorithmEngine
            engine = GeneticAlgorithmEngine()
            summary = engine.generate_prediction()
            
            # 写入缓存
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            return summary
        except Exception as e:
            logger.error("❌ 遗传算法推演计算异常: %s", e, exc_info=True)
            return {"status": "error", "message": f"遗传算法计算异常: {str(e)}"}

    def run_genetic_online(self, pop_size: int = 40, generations: int = 25, eval_periods: int = 15) -> Dict[str, Any]:
        """
        在线手动触发遗传算法高精寻优并刷新缓存
        """
        try:
            from backend.modules._retired.genetic_algorithm.genetic_engine import GeneticAlgorithmEngine
            engine = GeneticAlgorithmEngine()
            evo_res = engine.run_evolution(
                pop_size=max(10, min(100, pop_size)),
                generations=max(10, min(50, generations)),
                eval_periods=max(5, min(30, eval_periods))
            )
            import numpy as np
            best_chrom = np.array(evo_res["best_chromosome"], dtype=np.float64)
            summary = engine.generate_prediction(best_chromosome=best_chrom)
            summary["evolution_meta"] = evo_res

            cache_dir = os.path.join(get_cache_dir(), "genetic_algorithm")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, "latest_summary.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

            return summary
        except Exception as e:
            logger.error("❌ 在线进化触发失败: %s", e, exc_info=True)
            return {"status": "error", "message": str(e)}

    def get_genetic_review(self, n: int = 30) -> Dict[str, Any]:
        """
        获取近 N 期遗传算法 Walk-Forward 样本外滚动对账流水与统计指标
        @param n 滚动回溯期数 (默认 30)
        """
        history = self.load_history(limit=n + 35)
        if not history or len(history) < n + 15:
            return {"status": "error", "message": "历史开奖数据不足以进行样本外回测"}

        cache_dir = os.path.join(get_cache_dir(), "genetic_algorithm")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"review_{n}.json")

        latest_issue = int(history[0]["period"]) if str(history[0].get("period", "")).isdigit() else 0
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("latest_period") == latest_issue and data.get("n_periods") == n:
                        return data
            except Exception:
                pass

        try:
            from backend.modules._retired.genetic_algorithm.genetic_engine import GeneticAlgorithmEngine
            
            records: List[Dict[str, Any]] = []
            total_top3_hits = 0
            total_gold_hits = 0
            total_gold_pair_hits = 0
            # 统一预热基准引擎并求解先验最优染色体
            base_engine = GeneticAlgorithmEngine(history=history[n:])
            evo_base = base_engine.run_evolution(pop_size=30, generations=15, eval_periods=15)
            import numpy as np
            best_chrom = np.array(evo_base["best_chromosome"], dtype=np.float64)

            # 滚动 Walk-Forward 回测
            for i in range(n):
                target_idx = i
                target_item = history[target_idx]
                target_period = int(target_item.get("period", target_item.get("issue", 0)))
                actual_draw = target_item.get("numbers", [])
                actual_set = set(actual_draw)

                # 使用截至 target_idx + 1 的历史切片
                sub_hist = history[target_idx + 1 :]
                period_engine = GeneticAlgorithmEngine(history=sub_hist)
                
                # 传入最优染色体进行纯矩阵特征打分推演
                pred = period_engine.generate_prediction(best_chromosome=best_chrom)
                
                top3 = list(pred.get("top3_gold") or pred.get("top5_assault") or [])[:3]
                gold = pred.get("gold_core", 0) or (top3[0] if top3 else 0)
                gold_pair = pred.get("gold_pair", [])

                hit_top3 = len(actual_set.intersection(top3))
                hit_gold = 1 if gold in actual_set else 0
                hit_gold_pair = len(actual_set.intersection(gold_pair))

                total_top3_hits += hit_top3
                total_gold_hits += hit_gold
                if hit_gold_pair == 2:
                    total_gold_pair_hits += 1

                hit_top3_nums = sorted(list(actual_set.intersection(top3)))
                hit_gold_pair_nums = sorted(list(actual_set.intersection(gold_pair)))

                records.append({
                    "period": target_period,
                    "actual_draw": actual_draw,
                    "top3": top3,
                    "top3_hits": hit_top3,
                    "top3_hit_nums": hit_top3_nums,
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
                    "draw_date": target_item.get("date", "")
                })

            # 统计汇总（主口径 Top3，无随机基线 Lift）
            avg_top3_hit = round(total_top3_hits / max(1, n), 2)
            gold_hit_rate = round(total_gold_hits / max(1, n) * 100.0, 1)
            pair_double_rate = round(total_gold_pair_hits / max(1, n) * 100.0, 1)

            review_result = {
                "status": "success",
                "latest_period": latest_issue,
                "n_periods": n,
                "stats": {
                    "avg_top3_hit": avg_top3_hit,
                    "avg_top5_hit": avg_top3_hit,
                    "avg_top12_hit": avg_top3_hit,
                    "gold_hit_rate": gold_hit_rate,
                    "pair_double_rate": pair_double_rate,
                    "total_periods": n
                },
                "records": records,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(review_result, f, ensure_ascii=False, indent=2)

            return review_result

        except Exception as e:
            logger.error("❌ 遗传算法滚动对账异常: %s", e, exc_info=True)
            return {"status": "error", "message": str(e)}
