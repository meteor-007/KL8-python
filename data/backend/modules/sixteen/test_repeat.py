# -*- coding: utf-8 -*-
"""重号深度分析验证脚本"""
import os
import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath("."))
from backend.modules.sixteen.service import SixteenServiceMixin

svc = SixteenServiceMixin()
res = svc.get_sixteen_excel_window(persist=True)
rep = res.get("repeat_analysis") or {}

print("=== 重号深度分析生成成功 ===")
print(f"上期开奖期号: 第 {rep.get('last_period')} 期")
print(f"16窗重号均值: {rep.get('win_avg_repeats')} 个 ｜ 全历史均值: {rep.get('all_avg_repeats')} 个")
print(f"近8期重号走势: {rep.get('win_repeats_trend')}")
print(f"当期预估重号区间: {rep.get('expected_range')}")
print(f"👑 Top 5 黄金重号金选: {rep.get('gold_repeats_str')}")
print(f"🌿 稳健重号候选: {rep.get('steady_repeats_str')}")
print(f"❄️ 建议回避重号: {rep.get('cold_repeats_str')}")
print("-" * 60)
for c in (rep.get("candidates") or []):
    print(f"号码 {c['number_str']} | 连开{c['consecutive_streak']}期 | 16窗{c['freq_16']}次 | 历史连庄率{c['hist_repeat_rate_pct']} | 潜力分{c['repeat_score']} | {c['rank_tag']} | {c['advice']}")
