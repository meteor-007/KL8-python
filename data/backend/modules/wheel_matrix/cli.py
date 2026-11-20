# -*- coding: utf-8 -*-
"""
交互式命令行工具 (Interactive CLI for Smart Lottery)
"""
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from .models import PRESET_GAMES
from .data_manager import DataManager
from .trend_engine import TrendEngine
from .scoreboard import ScoreboardEngine
from .wheel_engine import WheelEngine, BUILTIN_WHEELS
from .filter_pipeline import FilterPipeline
from .backtester import Backtester

def main():
    print("=" * 70)
    print("      彩票科学选号与缩水系统 (Gail Howard Smart Luck CLI)")
    print("=" * 70)

    # 1. 选择玩法
    print("\n[1/5] 支持的彩票玩法列表:")
    game_keys = list(PRESET_GAMES.keys())
    for idx, gk in enumerate(game_keys, 1):
        g = PRESET_GAMES[gk]
        print(f"  {idx}. {g.name} (主区 {g.main_pool} 选 {g.main_pick})")
    
    choice = 1 # 默认双色球
    game_key = game_keys[choice - 1]
    spec = PRESET_GAMES[game_key]
    print(f"-> 已选定玩法: {spec.name}")

    # 2. 加载数据
    dm = DataManager()
    draws = dm.generate_synthetic_history(spec, num_draws=100)
    dm.save_draws(spec.game_id, draws)
    print(f"-> 已加载 {len(draws)} 期历史开奖数据 (最新期号: {draws[-1].draw_id})")

    # 3. 趋势与记分板分析
    print("\n[2/5] 执行时序遗漏与形态多因子打分...")
    trend = TrendEngine(spec)
    trend.load_history(draws)
    
    sb = ScoreboardEngine(spec)
    res = sb.evaluate(trend)
    
    print(f"  [★] Tier 1 核心胆码 (Bankers): {res['tier_1_bankers']}")
    print(f"  [●] Tier 2 优选拖码池 (Pool): {res['tier_2_pool']}")
    print(f"  [x] Tier 3 排除冷号: {res['tier_3_excluded'][:6]}...")

    # 4. 旋转矩阵生成
    print("\n[3/5] 匹配 Gail Howard 经典保奖旋转矩阵...")
    template = BUILTIN_WHEELS["W6_12_4_4_6"] if spec.main_pick == 6 else BUILTIN_WHEELS["W5_10_4_4_6"]
    print(f"  已匹配矩阵模板: {template.name} ({template.guarantee})")

    pool = (res["tier_1_bankers"] + res["tier_2_pool"])[:template.pool_size]
    raw_tickets = WheelEngine.generate_wheel(template, pool, res["tier_1_bankers"])
    print(f"  矩阵原始生成注数: {len(raw_tickets)} 注")

    # 5. 多级过滤管道缩水
    print("\n[4/5] 启动平衡过滤流水线 (和值/奇偶/大小/连号/同尾)...")
    pipe = FilterPipeline(spec)
    filter_res = pipe.filter_tickets(raw_tickets)
    
    print(f"  过滤前注数: {filter_res['raw_count']} 注")
    print(f"  过滤后有效实战注数: {filter_res['passed_count']} 注 (压缩率: {filter_res['reduction_rate_pct']}%)")
    print(f"  过滤原因统计: {filter_res['reject_summary']}")

    print("\n[5/5] 输出最终精选投注单:")
    for i, t in enumerate(filter_res["passed_tickets"], 1):
        odds = sum(1 for x in t if x % 2 == 1)
        evens = len(t) - odds
        print(f"  注 {i:02d}: {t}  (和值={sum(t)}, 奇偶={odds}:{evens})")

    # 6. 回测演示
    print("\n[+] 运行无前瞻偏差历史滚动回测 (50 期)...")
    backtester = Backtester(spec, template)
    bt_res = backtester.run_backtest(draws, warmup_period=50)
    print(f"  回测期数: {bt_res['total_tested_draws']} 期, 平均每期投注: {bt_res['avg_tickets_per_draw']} 注")
    print(f"  中奖命中分布: {bt_res['hits_distribution']}")
    print("\n" + "=" * 70)
    print("               全流程自动化执行完成！")
    print("=" * 70)

if __name__ == "__main__":
    main()
