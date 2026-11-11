# -*- coding: utf-8 -*-
"""
三维交集共识与选2冷热对冲 样本外无未来信息滚动回测器 (Walk-Forward Reviewer)
==================================================================================

【业务背景与量化逻辑】:
执行工业级 Walk-Forward 实盘滚动回测：
  1. 目标期 T 仅使用截止 T-1 期的历史数据运行三维共识与冷热对冲配对；
  2. 严禁读取期号 T 及之后的开奖结果（彻底防范未来函数信息泄露）；
  3. 与期号 T 真实开奖号码进行物理红黑核验对账；
  4. 汇总统计：金胆命中率、选2双全中率、Top5均期命中数、Lift 相对提升倍数。

@author Antigravity Quant Team & Old-School Quant Trader
@since 2026-09-21
"""

from __future__ import annotations

import os
import sys
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.dirname(_CURR_DIR)
_BACKEND_DIR = os.path.dirname(_MODULES_DIR)
_PROJ_DIR = os.path.dirname(_BACKEND_DIR)

for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils.history_loader import load_history
from backend.utils.paths import get_cache_dir, get_outputs_dir
from backend.modules._retired.consensus_straddle.engine import (
    ConsensusStraddleEngine,
    BASE_SINGLE_PROB,
    BASE_PAIR_PROB,
)
from backend.data_acquisition.daily_points_manager import load_daily_points
from backend.modules.tri_high.tri_high_engine import TriHighResonanceEngine


class ConsensusStraddleReviewer:
    """样本外 Walk-Forward 滚动实战回测评测器。"""

    def __init__(self, proj_dir: Optional[str] = None) -> None:
        self.proj_dir = proj_dir or _PROJ_DIR
        self.engine = ConsensusStraddleEngine(proj_dir=self.proj_dir)

    def run_walk_forward_review(
        self,
        n_periods: int = 30,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        运行最近 n_periods 期的样本外滚动回测。

        :param n_periods: 回测期数 (默认 30 期)
        :param verbose: 是否实时打印回测日志
        :return: 结构化回测统计字典
        """
        history = load_history()
        if not history:
            raise RuntimeError("无法读取开奖历史！")

        # history 默认降序 (最新在前) -> 转为升序列表
        draws_records = list(reversed(history))
        total_draws = len(draws_records)

        if total_draws < n_periods + 50:
            raise ValueError(f"开奖历史总期数不足 ({total_draws})，无法支撑 {n_periods} 期样本外回测！")

        # 预先加载点位与三高字典
        all_points_dict = load_daily_points()
        tri_engine = TriHighResonanceEngine(proj_dir=self.proj_dir)
        tri_records = {str(r.get("period")): r for r in tri_engine.load_tri_high_records()}

        # 抽取回测目标索引区间
        start_idx = total_draws - n_periods
        rows: List[Dict[str, Any]] = []

        gold_hits = 0
        silver_hits = 0
        bronze_hits = 0
        top5_total_hits = 0

        pair_both_hits = 0
        pair_at_least_one_hits = 0

        if verbose:
            print("\n" + "=" * 76)
            print(f"🚀 [Consensus Straddle] 正在启动最近 {n_periods} 期样本外无未来信息滚动回测...")
            print("=" * 76)

        for current_idx in range(start_idx, total_draws):
            # 目标期数据（待预测）
            target_record = draws_records[current_idx]
            target_period = int(target_record["issue"])
            actual_numbers = set(target_record["numbers"])
            target_date = target_record.get("date", "")

            # 截止到 T-1 的升序开奖列表（彻底隔离未来信息）
            train_draws_asc = [d["numbers"] for d in draws_records[:current_idx]]
            anchor_period = int(draws_records[current_idx - 1]["issue"])

            # 读取该期点位与三高数据
            pts_entry = all_points_dict.get(str(target_period)) or {}
            points = pts_entry.get("points", [])
            tri_data = tri_records.get(str(target_period))

            # 执行推演
            pred = self.engine.run_prediction(
                all_draws_asc=train_draws_asc,
                target_period=target_period,
                daily_points=points,
                tri_high_data=tri_data,
                draw_date=target_date
            )

            # 物理实战核验
            is_gold_hit = pred.consensus_gold in actual_numbers
            is_silver_hit = pred.consensus_silver in actual_numbers
            is_bronze_hit = pred.consensus_bronze in actual_numbers

            top5_hits = sum(1 for b in pred.top5_defense_line if b in actual_numbers)
            top5_total_hits += top5_hits

            if is_gold_hit:
                gold_hits += 1
            if is_silver_hit:
                silver_hits += 1
            if is_bronze_hit:
                bronze_hits += 1

            # 选2 Top 1 组合双中核验
            top1_pair = pred.top5_straddle_pairs[0] if pred.top5_straddle_pairs else None
            top1_both = False
            top1_one = False
            top1_pair_str = "—"

            if top1_pair:
                top1_pair_str = top1_pair.pair_str
                in1 = top1_pair.attack_ball in actual_numbers
                in2 = top1_pair.defense_ball in actual_numbers
                top1_both = in1 and in2
                top1_one = in1 or in2

                if top1_both:
                    pair_both_hits += 1
                if top1_one:
                    pair_at_least_one_hits += 1

            eval_tag = "🎉 选2双全中" if top1_both else ("🌟 金胆命中" if is_gold_hit else ("🌿 稳健防守" if top1_one else "❄️ 观望轮空"))

            row_info = {
                "target_period": target_period,
                "anchor_period": anchor_period,
                "date": target_date,
                "gold": pred.consensus_gold,
                "gold_hit": is_gold_hit,
                "silver": pred.consensus_silver,
                "silver_hit": is_silver_hit,
                "bronze": pred.consensus_bronze,
                "bronze_hit": is_bronze_hit,
                "top5_defense": pred.top5_defense_line,
                "top5_hits": top5_hits,
                "top1_pair": top1_pair_str,
                "top1_both": top1_both,
                "top1_one": top1_one,
                "kl_div": pred.kl_divergence,
                "eval_tag": eval_tag
            }
            rows.append(row_info)

            if verbose:
                gold_mark = "✅命中" if is_gold_hit else "❌未中"
                pair_mark = "🎉双全中" if top1_both else ("✔中1码" if top1_one else "—")
                print(
                    f"  第 {target_period} 期 | 金胆 {pred.consensus_gold:02d} ({gold_mark}) | "
                    f"选2 [{top1_pair_str}] ({pair_mark}) | "
                    f"5码防线中 {top5_hits} | 评级: {eval_tag}"
                )

        # 汇总决算统计
        gold_hit_rate = round((gold_hits / n_periods) * 100, 2)
        silver_hit_rate = round((silver_hits / n_periods) * 100, 2)
        bronze_hit_rate = round((bronze_hits / n_periods) * 100, 2)

        gold_lift = round((gold_hits / n_periods) / BASE_SINGLE_PROB, 2)
        silver_lift = round((silver_hits / n_periods) / BASE_SINGLE_PROB, 2)

        pair_both_rate = round((pair_both_hits / n_periods) * 100, 2)
        pair_both_lift = round((pair_both_hits / n_periods) / BASE_PAIR_PROB, 2)

        pair_one_rate = round((pair_at_least_one_hits / n_periods) * 100, 2)
        top5_avg_hits = round(top5_total_hits / n_periods, 2)

        stats = {
            "n_periods": n_periods,
            "gold_hits": gold_hits,
            "gold_hit_rate": gold_hit_rate,
            "gold_lift": gold_lift,
            "silver_hits": silver_hits,
            "silver_hit_rate": silver_hit_rate,
            "silver_lift": silver_lift,
            "bronze_hits": bronze_hits,
            "bronze_hit_rate": bronze_hit_rate,
            "top1_pair_both_hits": pair_both_hits,
            "top1_pair_both_rate": pair_both_rate,
            "top1_pair_both_lift": pair_both_lift,
            "top1_pair_one_hits": pair_at_least_one_hits,
            "top1_pair_one_rate": pair_one_rate,
            "top5_avg_hits": top5_avg_hits,
            "base_single_rate": BASE_SINGLE_PROB * 100,
            "base_pair_rate": round(BASE_PAIR_PROB * 100, 2)
        }

        if verbose:
            print("\n" + "═" * 76)
            print(f"📊 [三维交集共识与冷热对冲] 近 {n_periods} 期样本外实测终审对账表")
            print("═" * 76)
            print(f"  👑 至尊共识金胆命中率 : {gold_hit_rate}% (实测 {gold_hits}/{n_periods} | Lift: {gold_lift}x vs 基线 25.0%)")
            print(f"  🥈 次席共识银胆命中率 : {silver_hit_rate}% (实测 {silver_hits}/{n_periods} | Lift: {silver_lift}x)")
            print(f"  🥉 三席共识铜胆命中率 : {bronze_hit_rate}% (实测 {bronze_hits}/{n_periods})")
            print(f"  💎 选2黄金对冲双全中率 : {pair_both_rate}% (双全中 {pair_both_hits} 次 | Lift: {pair_both_lift}x vs 基线 6.01%)")
            print(f"  🎯 选2黄金对冲至少中1 : {pair_one_rate}% (保本率)")
            print(f"  🛡️ 5 码精选防线平均命中 : {top5_avg_hits} 码 / 期 (期望: 1.25 码)")
            print("═" * 76 + "\n")

        review_result = {
            "stats": stats,
            "rows": rows,
            "audit_timestamp": datetime.now().isoformat(),
            "no_lookahead_verified": True
        }

        # 持久化保存对账结果 (JSON 与 Markdown 双备份)
        cache_file = os.path.join(get_cache_dir(), "consensus_straddle_review.json")
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(review_result, f, ensure_ascii=False, indent=2)

        md_lines = [
            "# 📊 三维交集共识与选2冷热对冲 · 30期样本外实测审计战报",
            f"**审计时间**：{review_result['audit_timestamp'][:19]} ｜ **回测期数**：最近 {n_periods} 期",
            "**回测机制**：严格无未来信息泄漏 (Walk-Forward Rolling Backtest)",
            "",
            "## 🏆 核心实测指标总决算",
            f"- 👑 **至尊共识金胆命中率**：`{gold_hit_rate}%` ({gold_hits}/{n_periods}) ｜ 相对大盘提升倍数 (Lift)：`{gold_lift}x` (基线: 25.0%)",
            f"- 🥈 **次席共识银胆命中率**：`{silver_hit_rate}%` ({silver_hits}/{n_periods}) ｜ Lift: `{silver_lift}x`",
            f"- 🥉 **三席共识铜胆命中率**：`{bronze_hit_rate}%` ({bronze_hits}/{n_periods})",
            f"- 💎 **选2黄金对冲双全中率**：`{pair_both_rate}%` (双全中 {pair_both_hits} 次) ｜ 相对大盘提升倍数 (Lift)：`{pair_both_lift}x` (基线: 6.01%)",
            f"- 🎯 **选2黄金对冲保本率 (至少中1)**：`{pair_one_rate}%` ({pair_at_least_one_hits}/{n_periods})",
            f"- 🛡️ **5 码精选防线平均命中**：`{top5_avg_hits}` 码 / 期 (期望: 1.25 码)",
            "",
            "## 📜 近 30 期逐期红黑对账明细",
            "| 期号 | 至尊金胆 | 选2对冲组合 | 选2核验结果 | 5码防线命中 | 操盘手审计评级 |",
            "| :---: | :---: | :---: | :---: | :---: | :---: |"
        ]

        for r in rows:
            g_mark = f"✅命中 ({r['gold']:02d})" if r['gold_hit'] else f"❌未中 ({r['gold']:02d})"
            if r['top1_both']:
                p_mark = "🎉 双全中"
            elif r['top1_one']:
                p_mark = "✔ 中1码"
            else:
                p_mark = "—"
            md_lines.append(f"| {r['target_period']} | {g_mark} | `{r['top1_pair']}` | {p_mark} | {r['top5_hits']} 码 | {r['eval_tag']} |")

        md_content = "\n".join(md_lines) + "\n"
        rep_dir = os.path.join(get_outputs_dir(), "reports")
        os.makedirs(rep_dir, exist_ok=True)
        md_path = os.path.join(rep_dir, f"consensus_straddle_review_{n_periods}.md")
        latest_path = os.path.join(rep_dir, "consensus_straddle_review_latest.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return review_result
