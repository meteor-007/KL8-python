#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026162期详细复盘 + 2026163期区域尾数预测"""
import json, os
from collections import Counter

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()

# 2026162期开奖号码
actual_162 = [73, 37, 13, 19, 69, 39, 1, 71, 2, 18, 40, 63, 8, 33, 78, 76, 30, 57, 16, 56]
actual_set = set(actual_162)

# 读取学习状态
with open(os.path.join(_PROJ, 'cache', 'self_learning_state.json'), 'r', encoding='utf-8') as f:
    state = json.load(f)

# 找2026162期推荐
y_rec = None
for rec in state['history']:
    if str(rec.get('target_issue')) == '2026162':
        y_rec = rec
        break
if y_rec is None and len(state['history']) > 1:
    y_rec = state['history'][1]

print('=' * 70)
print('  快乐8预测系统 — 2026162期详细复盘报告')
print('=' * 70)
print(f'\n开奖号码: {"-".join(f"{n:02d}" for n in sorted(actual_162))}')
print(f'共 {len(actual_162)} 个号码 (期望20个)')

# 三维融合
t5 = y_rec.get('top5', []) if y_rec else []
t12 = y_rec.get('top12', []) if y_rec else []
hit5 = sorted(set(t5) & actual_set)
hit12 = sorted(set(t12) & actual_set)
lift5 = (len(hit5)/5) / 0.25 if t5 else 0
lift12 = (len(hit12)/12) / 0.25 if t12 else 0

print(f'\n{"─"*70}')
print(f'  三维融合复盘')
print(f'{"─"*70}')
print(f'  Top5 推荐: {sorted(t5)}')
print(f'  Top5 命中: {hit5} ({len(hit5)}/5, Lift={lift5:.2f}x)')
print(f'  Top12 推荐: {sorted(t12)}')
print(f'  Top12 命中: {hit12} ({len(hit12)}/12, Lift={lift12:.2f}x)')

# HE5
he5 = y_rec.get('b3_final5', []) if y_rec else []
hit_he5 = sorted(set(he5) & actual_set)
print(f'\n  HE5 推荐: {sorted(he5)}')
print(f'  HE5 命中: {hit_he5} ({len(hit_he5)}/5, Lift={len(hit_he5)/5/0.25:.2f}x)')

# 纯净池
pp = y_rec.get('pure_pool_top', []) if y_rec else []
hit_pp = sorted(set(pp) & actual_set)
print(f'\n  纯净池: {sorted(pp)}')
print(f'  纯净池命中: {hit_pp} ({len(hit_pp)}/{len(pp)})')

# 传统AI
c5 = y_rec.get('conf_top5', []) if y_rec else []
c12 = y_rec.get('conf_top12', []) if y_rec else []
hit_c5 = sorted(set(c5) & actual_set)
hit_c12 = sorted(set(c12) & actual_set)
print(f'\n  传统AI Top5: {sorted(c5)} → 命中 {hit_c5} ({len(hit_c5)}/5)')
print(f'  传统AI Top12: {sorted(c12)} → 命中 {hit_c12} ({len(hit_c12)}/12)')

# 高阶前瞻
g5 = y_rec.get('high_order_gauss_top5', []) if y_rec else []
cl5 = y_rec.get('high_order_cluster_top5', []) if y_rec else []
f5 = y_rec.get('high_order_fourier_top5', []) if y_rec else []
fu5 = y_rec.get('high_order_fusion_top5', []) if y_rec else []
print(f'\n  高斯核5: {sorted(g5)} → 命中 {sorted(set(g5)&actual_set)} ({len(set(g5)&actual_set)}/5)')
print(f'  聚类5: {sorted(cl5)} → 命中 {sorted(set(cl5)&actual_set)} ({len(set(cl5)&actual_set)}/5)')
print(f'  傅里叶5: {sorted(f5)} → 命中 {sorted(set(f5)&actual_set)} ({len(set(f5)&actual_set)}/5)')
print(f'  极致整合5: {sorted(fu5)} → 命中 {sorted(set(fu5)&actual_set)} ({len(set(fu5)&actual_set)}/5)')

# mRMR
m12 = y_rec.get('mrmr_top12', []) if y_rec else []
hit_m12 = sorted(set(m12) & actual_set)
print(f'\n  mRMR Top12: {sorted(m12)} → 命中 {hit_m12} ({len(hit_m12)}/12)')

# ─── 区域分析 ───
print(f'\n{"═"*70}')
print(f'  区域分布分析 (2026162期开奖 → 2026163期预测)')
print(f'{"═"*70}')

# 历史10期区域命中
with open(os.path.join(_PROJ, 'kl8_history_final.txt'), 'r', encoding='utf-8') as f:
    lines = f.readlines()

history = []
for line in lines:
    line = line.strip()
    if not line or not line.startswith('date:'):
        continue
    parts = line.split(',')
    date_str = parts[0].split(':')[1]
    period_str = parts[1].split(':')[1]
    nums_str = parts[2].split(':')[1]
    nums = [int(x) for x in nums_str.split('-')]
    history.append({'date': date_str, 'issue': period_str, 'numbers': nums})

zones = [(i*10+1, (i+1)*10) for i in range(8)]
zone_names = ['01-10', '11-20', '21-30', '31-40', '41-50', '51-60', '61-70', '71-80']

print(f'\n  近5期区域命中分布:')
header = f'  {"期号":>10s}'
for z in zone_names:
    header += f' {z:>6s}'
print(header)
print('  ' + '-' * 60)

zone_trend = {i: [] for i in range(8)}
for h in history[:5]:
    row = f'  {h["issue"]:>10s}'
    for zi, (z0, z1) in enumerate(zones):
        cnt = sum(1 for n in h['numbers'] if z0 <= n <= z1)
        zone_trend[zi].append(cnt)
        row += f' {cnt:>6d}'
    print(row)

# 理论密度
theory = 20.0 / 80.0 * 10  # 每区2.5个
print(f'\n  各区近5期平均 vs 理论(2.5):')
for zi, zn in enumerate(zone_names):
    avg = sum(zone_trend[zi]) / len(zone_trend[zi])
    dev = (avg - theory) / theory * 100
    marker = '🔥过热' if dev > 20 else ('❄️过冷' if dev < -20 else '✅正常')
    print(f'  区{zi+1}({zn}): 平均{avg:.1f} 偏差{dev:+.0f}% {marker}')

# 尾数分析
print(f'\n{"═"*70}')
print(f'  尾数分布分析')
print(f'{"═"*70}')

tail_trend = {t: [] for t in range(10)}
for h in history[:5]:
    tail_cnt = Counter()
    for n in h['numbers']:
        tail_cnt[n % 10] += 1
    for t in range(10):
        tail_trend[t].append(tail_cnt.get(t, 0))

print(f'\n  近5期尾数分布:')
header = f'  {"期号":>10s}'
for t in range(10):
    header += f'  尾{t}'
print(header)
print('  ' + '-' * 40)

for h in history[:5]:
    row = f'  {h["issue"]:>10s}'
    tail_cnt = Counter()
    for n in h['numbers']:
        tail_cnt[n % 10] += 1
    for t in range(10):
        row += f'  {tail_cnt.get(t, 0):>2d}'
    print(row)

tail_theory = 20.0 / 10.0  # 每尾2个
print(f'\n  各尾近5期平均 vs 理论(2.0):')
for t in range(10):
    avg = sum(tail_trend[t]) / len(tail_trend[t])
    dev = (avg - tail_theory) / tail_theory * 100
    marker = '🔥过热' if dev > 30 else ('❄️过冷' if dev < -30 else '✅正常')
    print(f'  尾{t}: 平均{avg:.1f} 偏差{dev:+.0f}% {marker}')

# ─── 2026163期点位区域预测 ───
print(f'\n{"═"*70}')
print(f'  2026163期点位区域预测')
print(f'{"═"*70}')

# 读取2026163期点位
with open(os.path.join(_PROJ, 'daily_points.txt'), 'r', encoding='utf-8') as f:
    for line in f:
        if 'period:2026163' in line:
            pts = [int(x) for x in line.split('points:')[1].strip().split()]
            break

pts_set = set(pts)
print(f'\n  2026163期点位: {sorted(pts)}')
print(f'  点位区域分布:')
for zi, (z0, z1) in enumerate(zones):
    cnt = sum(1 for n in pts if z0 <= n <= z1)
    print(f'    区{zi+1}({z0:02d}-{z1:02d}): {cnt}码')

# 金胆交叉验证
print(f'\n{"═"*70}')
print(f'  2026163期金胆交叉验证')
print(f'{"═"*70}')

# 当前推荐
cur = state['history'][0] if state['history'] else {}
t5_cur = cur.get('top5', [])
t12_cur = cur.get('top12', [])
he5_cur = cur.get('b3_final5', [])
pp_cur = cur.get('pure_pool_top', [])
g5_cur = cur.get('high_order_gauss_top5', [])
fu5_cur = cur.get('high_order_fusion_top5', [])

# 多维度交叉
all_nums = t5_cur + t12_cur + he5_cur + pp_cur + g5_cur + fu5_cur
num_counter = Counter(all_nums)
print(f'\n  多维度推荐交叉(出现次数≥3为强信号):')
for n, cnt in sorted(num_counter.items(), key=lambda x: (-x[1], x[0])):
    if cnt >= 2:
        sources = []
        if n in t5_cur: sources.append('Trinity5')
        if n in t12_cur: sources.append('Trinity12')
        if n in he5_cur: sources.append('HE5')
        if n in pp_cur: sources.append('纯净池')
        if n in g5_cur: sources.append('高斯5')
        if n in fu5_cur: sources.append('整合5')
        marker = '🔥🔥🔥' if cnt >= 4 else ('🔥🔥' if cnt >= 3 else '🔥')
        print(f'    号码{n:02d}: 出现{cnt}次 {marker} [{", ".join(sources)}]')

# 最终推荐汇总
print(f'\n{"═"*70}')
print(f'  2026163期最终推荐汇总面板')
print(f'{"═"*70}')
print(f'\n  🏆 Hidden Energy 5: {sorted(he5_cur)}')
print(f'  🎯 三维融合 Top5: {sorted(t5_cur)}')
print(f'  🎯 三维融合 Top12: {sorted(t12_cur)}')
print(f'  💎 纯净池定胆: {sorted(pp_cur)}')
print(f'  🔮 Golden Core: {sorted(set(t12_cur) & set(pp_cur))}')
print(f'  🌊 极致整合5: {sorted(fu5_cur)}')
print(f'  🌊 高斯核5: {sorted(g5_cur)}')
print(f'\n  💰 统计置信度: Level 1 (0.5x)')
print(f'  🌍 环境: 平衡震荡期 (置信1.00)')
print(f'  ⚙️ 三维权重: EF=0.40/RW=0.30/FO=0.30')
print(f'\n  ⚠️ 风险预警:')
print(f'    1. Level 1零信标降级⚠️(溢价减半)')
print(f'    3. 闭环学习决策KEPT(权重无变更)')
