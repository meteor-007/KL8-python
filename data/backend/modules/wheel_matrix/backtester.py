# -*- coding: utf-8 -*-
"""
无前瞻偏差策略历史回测引擎 (Walk-Forward Strategy Backtester)
"""
from typing import List, Dict, Any, Optional
from .models import LotteryGameSpec, DrawRecord
from .trend_engine import TrendEngine
from .scoreboard import ScoreboardEngine
from .wheel_engine import WheelEngine, WheelTemplate
from .filter_pipeline import FilterPipeline, FilterConfig

class Backtester:
    def __init__(self, spec: LotteryGameSpec, template: WheelTemplate, filter_config: Optional[FilterConfig] = None):
        self.spec = spec
        self.template = template
        self.filter_pipeline = FilterPipeline(spec, filter_config)

    def run_backtest(self, history: List[DrawRecord], warmup_period: int = 30) -> Dict[str, Any]:
        """
        滚动前向回测: 对第 T 期预测，只能使用 T-1 及之前的历史数据
        """
        if len(history) <= warmup_period:
            raise ValueError(f"历史开奖期数不足! 至少需要 {warmup_period + 1} 期，当前仅有 {len(history)} 期")

        results = []
        total_tickets_generated = 0
        total_tickets_played = 0
        
        # 统计各奖级命中情况 (基于选6/选5的命中球数统计)
        hits_distribution: Dict[int, int] = {i: 0 for i in range(self.spec.main_pick + 1)}

        for t in range(warmup_period, len(history)):
            past_draws = history[:t]
            target_draw = history[t]

            # 1. 拟合趋势引擎
            trend = TrendEngine(self.spec)
            trend.load_history(past_draws)

            # 2. 记分板选号
            scoreboard = ScoreboardEngine(self.spec)
            eval_res = scoreboard.evaluate(trend)
            
            # 取前 template.pool_size 个推荐号码
            candidate_pool = eval_res["combined_candidate_pool"][:self.template.pool_size]
            bankers = eval_res["tier_1_bankers"]

            # 3. 旋转矩阵生成
            raw_tickets = WheelEngine.generate_wheel(self.template, candidate_pool, bankers)
            total_tickets_generated += len(raw_tickets)

            # 4. 过滤管道缩水
            filtered_res = self.filter_pipeline.filter_tickets(raw_tickets)
            final_tickets = filtered_res["passed_tickets"]
            total_tickets_played += len(final_tickets)

            # 5. 开奖核算
            target_set = set(target_draw.main_balls)
            draw_max_hit = 0
            for ticket in final_tickets:
                hit_cnt = len(set(ticket) & target_set)
                hits_distribution[hit_cnt] += 1
                if hit_cnt > draw_max_hit:
                    draw_max_hit = hit_cnt

            results.append({
                "draw_id": target_draw.draw_id,
                "target_balls": target_draw.main_balls,
                "played_tickets_count": len(final_tickets),
                "max_hits": draw_max_hit
            })

        avg_tickets_per_draw = total_tickets_played / len(results)
        return {
            "total_tested_draws": len(results),
            "total_tickets_generated": total_tickets_generated,
            "total_tickets_played": total_tickets_played,
            "avg_tickets_per_draw": round(avg_tickets_per_draw, 2),
            "hits_distribution": hits_distribution,
            "recent_details": results[-5:]
        }
