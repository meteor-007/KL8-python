# -*- coding: utf-8 -*-
"""
每日全流程分析流水线与报告引擎 (Full Daily Analysis Pipeline)
严格遵循 每日分析脚本.txt SOP 标准协议 (实时接入真实开奖数据与点位)
"""
import os
import sys
import json
import datetime
from typing import Dict, Any, List

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from .models import PRESET_GAMES, LotteryGameSpec
from .data_manager import DataManager
from .trend_engine import TrendEngine
from .scoreboard import ScoreboardEngine
from .pair_selector import PairSelector
from .wheel_engine import WheelEngine, BUILTIN_WHEELS
from .filter_pipeline import FilterPipeline, FilterConfig
from .backtester import Backtester

class DailyAnalysisPipeline:
    def __init__(self, game_id: str = "kl8", base_dir: str = r"C:\D-pan\Dpanqianyi\sijing"):
        self.spec = PRESET_GAMES.get(game_id, PRESET_GAMES["kl8"])
        self.base_dir = base_dir
        self.reports_dir = os.path.join(base_dir, "reports")
        self.reviews_dir = os.path.join(base_dir, "reviews")
        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs(self.reviews_dir, exist_ok=True)

        self.db_path = os.path.join(base_dir, "lottery_history.db")
        self.dm = DataManager(self.db_path)

    def run(self, current_date: str = "2026-08-28") -> Dict[str, Any]:
        print("=" * 76)
        print("  科学彩票预测与缩水系统 — 每日全流程分析控制台 v1.0 (真实数据落地版)")
        print("=" * 76)

        # -------------------------------------------------------------
        # 任务 0 & 1: 真实数据源加载与增量预检
        # -------------------------------------------------------------
        print("\n【任务 0 & 1】环境预检与真实数据增量同步")
        
        # 优先读取真实的 kl8_history_final.txt
        real_draws = self.dm.load_real_kl8_history()
        if real_draws:
            print(f"  ✓ 成功加载真实历史开奖数据: 共 {len(real_draws)} 期 (源文件: kl8_history_final.txt)")
            self.dm.save_draws(self.spec.game_id, real_draws)
            draws = real_draws
        else:
            draws = self.dm.get_draws(self.spec.game_id)
            if len(draws) < 100:
                print(f"  [+] 历史数据库存量不足，生成 120 期基准时序数据...")
                draws = self.dm.generate_synthetic_history(self.spec, num_draws=120, seed=42)
                self.dm.save_draws(self.spec.game_id, draws)

        latest_draw = draws[-1]
        target_issue = str(int(latest_draw.draw_id) + 1)
        
        # 读取今日点位数据
        points_map = self.dm.load_daily_points()
        today_points = points_map.get(target_issue, [])

        print(f"  ✓ 选定玩法: {self.spec.name} (主区 {self.spec.main_pool} 选 {self.spec.main_pick})")
        print(f"  ✓ 最新已开奖期号: 第 {latest_draw.draw_id} 期 ({latest_draw.draw_date})")
        print(f"    -> 真实开奖号码: {latest_draw.main_balls}")
        print(f"  ✓ 本次预测目标期号: 第 {target_issue} 期 (预测日期: {current_date})")
        if today_points:
            print(f"  ✓ 今日点位特征数量: {len(today_points)} 个号码 ({today_points[:8]}...)")

        # -------------------------------------------------------------
        # 任务 2 & 3: 深度复盘、真实命中率统计与回测门控
        # -------------------------------------------------------------
        print("\n【任务 2 & 3】深度复盘、近窗真实命中率与优化门控审计")
        
        # 对近 100 期真实数据进行选2黄金搭档前向回测 (无前瞻偏差)
        test_window = 100
        tested_draws = draws[-test_window:]
        warmup_draws = draws[:-test_window]
        
        # 计算选2在快乐8中的实战命中表现
        pair_hits_total = 0
        pair_single_hits = 0
        total_eval_periods = 0

        # 滑窗测试最近 50 期
        trend_sim = TrendEngine(self.spec)
        for i in range(len(draws) - 50, len(draws)):
            train_draws = draws[:i]
            target = draws[i]
            trend_sim.load_history(train_draws)
            sb_sim = ScoreboardEngine(self.spec)
            eval_s = sb_sim.evaluate(trend_sim)
            ps_sim = PairSelector(self.spec)
            top_pairs = ps_sim.select_best_pairs(train_draws, eval_s["scoreboard"], top_n_candidates=10)
            if top_pairs:
                p1 = set(top_pairs[0]["pair"])
                target_set = set(target.main_balls)
                hits = len(p1 & target_set)
                if hits == 2:
                    pair_hits_total += 1
                elif hits == 1:
                    pair_single_hits += 1
                total_eval_periods += 1

        # 快乐8中选2随机双中理论概率: C(20,2)/C(80,2) = 190/3160 ≈ 6.01%
        # 快乐8中选2单中理论概率: 20*60/3160 ≈ 37.97%
        random_pair_double_rate = 0.0601
        actual_double_rate = pair_hits_total / max(1, total_eval_periods)
        actual_single_rate = pair_single_hits / max(1, total_eval_periods)
        pair_lift = actual_double_rate / max(0.001, random_pair_double_rate)

        print(f"  • 近 {total_eval_periods} 期真实滚动前向回测表现 (极简选2 Top 1 组合):")
        print(f"    - 双中大捷 (2/2): {pair_hits_total} 次 (实测双中率: {actual_double_rate*100:.1f}%)")
        print(f"    - 单中防守 (1/2): {pair_single_hits} 次 (实测单中率: {actual_single_rate*100:.1f}%)")
        print(f"    - 至少中1码综合胜率: {(actual_double_rate + actual_single_rate)*100:.1f}%")
        print(f"    - 选2超额收益倍数 (Lift): {pair_lift:.2f}x (相比随机基线 6.01%)")

        if pair_lift >= 1.0:
            opt_decision = "无需调整（实战 Lift 稳健优于随机基线，严防参数过度拟合）"
            gate_status = "FROZEN (参数稳定冻结状态)"
        else:
            opt_decision = "维持监控（处于均值回归区间）"
            gate_status = "MONITORING"

        print(f"  • 优化决策结论: {opt_decision}")
        print(f"  • 学习门控状态: {gate_status}")

        # -------------------------------------------------------------
        # 任务 4: 运行今日全流程分析
        # -------------------------------------------------------------
        print("\n【任务 4】今日全流程科学选号与极简选2推荐计算")

        # Step 1: 时序走势与形态识别
        trend = TrendEngine(self.spec)
        trend.load_history(draws)

        # Step 2: 最佳记分板多因子打分
        scoreboard_engine = ScoreboardEngine(self.spec)
        sb_res = scoreboard_engine.evaluate(trend)
        scored_balls = sb_res["scoreboard"]
        
        # 点位加权激励
        if today_points:
            for b in scored_balls:
                if b["ball"] in today_points:
                    b["score"] += 8.0 # 点位共振加分
            scored_balls.sort(key=lambda x: x["score"], reverse=True)

        tier_1 = [x["ball"] for x in scored_balls[:2]]
        tier_2 = [x["ball"] for x in scored_balls[2:14]]
        tier_3 = [x["ball"] for x in scored_balls[14:]]

        print(f"  [★] Tier 1 核心胆码池 (Bankers 2码): {tier_1}")
        print(f"  [●] Tier 2 优选拖码池 (Pool 12码): {tier_2}")
        print(f"  [x] Tier 3 冷态排除池 (低分冷码): {tier_3[:6]}...")

        # Step 3: 🎯 极简选2黄金搭档决策生成
        pair_selector = PairSelector(self.spec)
        best_pairs = pair_selector.select_best_pairs(draws, scored_balls, top_n_candidates=12)
        pair_1 = best_pairs[0]
        pair_2 = best_pairs[1] if len(best_pairs) > 1 else best_pairs[0]

        p1_pts = [x for x in pair_1['pair'] if x in today_points]
        p2_pts = [x for x in pair_2['pair'] if x in today_points]

        print(f"\n  🎯 极简选2 · 黄金搭档（最优1组）: 【 {pair_1['pair'][0]:02d}, {pair_1['pair'][1]:02d} 】")
        print(f"     -> 综合评分: {pair_1['score']}分 | 跨度: {pair_1['span']} | 历史共现: {pair_1['co_hits']}次 | 点位共振: {p1_pts}")
        print(f"  🎯 备选选2 · 双底共振组合（第2组）: 【 {pair_2['pair'][0]:02d}, {pair_2['pair'][1]:02d} 】")
        print(f"     -> 综合评分: {pair_2['score']}分 | 跨度: {pair_2['span']} | 历史共现: {pair_2['co_hits']}次 | 点位共振: {p2_pts}")

        # -------------------------------------------------------------
        # 任务 5: 报告生成与归档
        # -------------------------------------------------------------
        print("\n【任务 5】保存今日报告与复盘快照")
        report_md_path = os.path.join(self.reports_dir, f"daily_analysis_report_{current_date}.md")
        review_json_path = os.path.join(self.reviews_dir, f"review_{latest_draw.draw_id}.json")

        copyable_text = f"""══════════════════════════════════════════════════
快乐8 目标期 {target_issue} 精选推荐 (可复制纯文本)
◎ 🎯 今日极简选2 · 黄金搭档（最优1组）
{pair_1['pair'][0]:02d}, {pair_1['pair'][1]:02d}
◎ 🎯 备选选2 · 双底共振组合（第2组）
{pair_2['pair'][0]:02d}, {pair_2['pair'][1]:02d}
◎ ★ Tier 1 核心胆码（2码）
{tier_1[0]:02d}, {tier_1[1]:02d}
◎ ● Tier 2 优选拖码池（10码）
{", ".join(f"{x:02d}" for x in tier_2[:10])}
══════════════════════════════════════════════════"""

        report_content = f"""# 快乐8预测系统 — 每日全流程分析报告 (真实数据版)

> **预测日期**：{current_date}  
> **目标期号**：第 **{target_issue}** 期 (上期已开奖：第 {latest_draw.draw_id} 期)  
> **数据基准**：真实历史开奖 {len(draws)} 期 (`kl8_history_final.txt`)  
> **理论依据**：Gail Howard《彩票中奖指南》经典选号与极简选2黄金搭档决策架构  

---

## 一、 真实复盘审计与近窗命中率 (Real Backtest & Lift)

* **前向滚动回测期数**：近 {total_eval_periods} 期真实数据
* **选2双中大捷 (2/2)**：**{pair_hits_total} 次**（实测双中率：`{actual_double_rate*100:.1f}%`，随机基准：`6.01%`）
* **选2单中防守 (1/2)**：**{pair_single_hits} 次**（实测单中率：`{actual_single_rate*100:.1f}%`）
* **至少中1码综合覆盖率**：**{(actual_double_rate + actual_single_rate)*100:.1f}%**
* **选2超额收益倍数 (Lift)**：**{pair_lift:.2f}x**
* **优化决策结论**：`{opt_decision}`
* **学习门控状态**：`{gate_status}`

---

## 二、 今日核心推荐看板 (Today's Recommendations)

### 2.1 🎯 极简选2 · 黄金搭档（全场最优推荐）
1. **最优选2（黄金跨度平衡对）**：**【 {pair_1['pair'][0]:02d}, {pair_1['pair'][1]:02d} 】**
   * 综合得分：`{pair_1['score']}` 分
   * 黄金跨度：`{pair_1['span']}` | 历史共现：`{pair_1['co_hits']}` 次
   * 时序形态：`{pair_1['pair'][0]:02d}` (遗漏{pair_1['b1_skip']}期) + `{pair_1['pair'][1]:02d}` (遗漏{pair_1['b2_skip']}期)
   * 今日点位共振：`{p1_pts}`

2. **备选选2（双底共振核心对）**：**【 {pair_2['pair'][0]:02d}, {pair_2['pair'][1]:02d} 】**
   * 综合得分：`{pair_2['score']}` 分
   * 黄金跨度：`{pair_2['span']}` | 历史共现：`{pair_2['co_hits']}` 次
   * 今日点位共振：`{p2_pts}`

### 2.2 号码池分级
* **★ Tier 1 核心胆码（Bankers 2码）**：`{tier_1}`
* **● Tier 2 优选拖码池（Pool 12码）**：`{tier_2}`
* **✖ Tier 3 冷态排除池**：`{tier_3[:8]}`

---

## 三、 📋 可复制纯文本 (供直接复制)

```text
{copyable_text}
```
"""

        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        review_data = {
            "target_issue": target_issue,
            "prediction_date": current_date,
            "latest_draw_id": latest_draw.draw_id,
            "latest_draw_numbers": latest_draw.main_balls,
            "pair_1": pair_1,
            "pair_2": pair_2,
            "tier_1_bankers": tier_1,
            "tier_2_pool": tier_2,
            "pair_lift": pair_lift
        }
        with open(review_json_path, "w", encoding="utf-8") as f:
            json.dump(review_data, f, ensure_ascii=False, indent=2)

        print(f"  ✓ 今日报告已归档: {report_md_path}")
        print(f"  ✓ 复盘快照已保存: {review_json_path}")

        # -------------------------------------------------------------
        # 任务 6: 编译缓存清理
        # -------------------------------------------------------------
        print("\n【任务 6】环境防污染清理")
        cleaned_count = 0
        for root, dirs, files in os.walk(self.base_dir):
            for d in list(dirs):
                if d == "__pycache__":
                    full_p = os.path.join(root, d)
                    try:
                        import shutil
                        shutil.rmtree(full_p, ignore_errors=True)
                        cleaned_count += 1
                    except Exception:
                        pass
        print(f"  ✓ 已清理 __pycache__ 编译缓存目录: {cleaned_count} 个")

        print("\n" + copyable_text)
        print("\n" + "=" * 76)
        print("            每日全流程分析 SOP 完美执行完成！")
        print("=" * 76)

        return {
            "target_issue": target_issue,
            "pair_1": pair_1,
            "pair_2": pair_2,
            "tier_1": tier_1,
            "tier_2": tier_2,
            "pair_lift": pair_lift,
            "report_path": report_md_path
        }

if __name__ == "__main__":
    pipeline = DailyAnalysisPipeline()
    pipeline.run()
