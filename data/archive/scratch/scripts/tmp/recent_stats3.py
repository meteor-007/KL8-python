"""近10期累计统计 - 去重版"""
import json, os
from math import sqrt, erf
import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()

# 加载历史
history = []
with open(os.path.join(_PROJ, 'kl8_history_final.txt'), 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or not line.startswith('date:'):
            continue
        parts = line.split(',')
        period = parts[1].split(':')[1]
        nums = [int(x) for x in parts[2].split(':')[1].split('-')]
        history.append({'issue': period, 'numbers': nums})

# 加载预测历史
with open(os.path.join(_PROJ, 'cache', 'self_learning_state.json'), 'r', encoding='utf-8') as f:
    state = json.load(f)

pred_history = state.get('history', [])
hist_map = {h['issue']: set(h['numbers']) for h in history}

# 去重: 每个target_issue只保留第一条
seen = set()
unique_results = []
for rec in pred_history:
    target = str(rec.get('target_issue', ''))
    if target in seen:
        continue
    seen.add(target)
    
    actual = hist_map.get(target, None)
    if actual is None:
        continue
    
    t5 = rec.get('top5', [])
    t12 = rec.get('top12', [])
    he5 = rec.get('b3_final5', [])
    pp = rec.get('pure_pool_top', [])
    fu5 = rec.get('high_order_fusion_top5', [])
    g5 = rec.get('high_order_gauss_top5', [])
    cl5 = rec.get('high_order_cluster_top5', [])
    f5 = rec.get('high_order_fourier_top5', [])
    
    unique_results.append({
        'period': target,
        't5_hit': len(set(t5) & actual), 't5_lift': len(set(t5) & actual)/5/0.25,
        't12_hit': len(set(t12) & actual), 't12_lift': len(set(t12) & actual)/12/0.25,
        'he5_hit': len(set(he5) & actual), 'he5_lift': len(set(he5) & actual)/max(len(he5),1)/0.25 if he5 else 0,
        'pp_hit': len(set(pp) & actual),
        'fu5_hit': len(set(fu5) & actual), 'fu5_lift': len(set(fu5) & actual)/5/0.25 if fu5 else 0,
        'g5_hit': len(set(g5) & actual),
        'cl5_hit': len(set(cl5) & actual),
        'f5_hit': len(set(f5) & actual),
    })

print('=' * 70)
print('  data目录V4.0 2026163期 实盘复盘统计 (去重版)')
print('=' * 70)

print(f'\n  有效复盘期数: {len(unique_results)}期')
print(f'\n  {"期号":>8s}  {"Top5":>6s}  {"Lift":>6s}  {"Top12":>6s}  {"Lift":>6s}  {"HE5":>4s}  {"整合5":>4s}  {"高斯5":>4s}  {"聚类5":>4s}  {"傅里叶5":>4s}')
print('  ' + '-' * 75)
for r in unique_results[:10]:
    print(f'  {r["period"]:>8s}  {r["t5_hit"]}/5  {r["t5_lift"]:5.2f}x  {r["t12_hit"]}/12 {r["t12_lift"]:5.2f}x  {r["he5_hit"]}/5  {r["fu5_hit"]}/5  {r["g5_hit"]}/5  {r["cl5_hit"]}/5  {r["f5_hit"]}/5')

# 累计统计
n = min(len(unique_results), 10)
recent = unique_results[:n]
t5_rate = sum(r['t5_hit'] for r in recent) / (n * 5) * 100
t12_rate = sum(r['t12_hit'] for r in recent) / (n * 12) * 100
t5_lift = sum(r['t5_lift'] for r in recent) / n
t12_lift = sum(r['t12_lift'] for r in recent) / n
he5_rate = sum(r['he5_hit'] for r in recent) / (n * 5) * 100
fu5_rate = sum(r['fu5_hit'] for r in recent) / (n * 5) * 100
g5_rate = sum(r['g5_hit'] for r in recent) / (n * 5) * 100

print(f'\n  近{n}期累计统计:')
print(f'  ┌──────────────────────────────────────────────┐')
print(f'  │ 三维融合 Top5:  {t5_rate:5.1f}%  Lift={t5_lift:.2f}x  {"✅" if t5_lift > 1.0 else "❌"}    │')
print(f'  │ 三维融合 Top12: {t12_rate:5.1f}%  Lift={t12_lift:.2f}x  {"✅" if t12_lift > 1.0 else "❌"}    │')
print(f'  │ Hidden Energy 5:{he5_rate:5.1f}%  Lift={sum(r["he5_lift"] for r in recent)/n:.2f}x  {"✅" if sum(r["he5_lift"] for r in recent)/n > 1.0 else "❌"}    │')
print(f'  │ 极致整合5码:   {fu5_rate:5.1f}%  Lift={sum(r["fu5_lift"] for r in recent)/n:.2f}x  {"✅" if sum(r["fu5_lift"] for r in recent)/n > 1.0 else "❌"}    │')
print(f'  │ 高斯核5码:     {g5_rate:5.1f}%                          │')
print(f'  └──────────────────────────────────────────────┘')

# 显著性检验
total_trials = n * 12
total_hits = sum(r['t12_hit'] for r in recent)
p_hat = total_hits / total_trials if total_trials > 0 else 0
p0 = 0.25
z = (p_hat - p0) / sqrt(p0 * (1-p0) / total_trials) if total_trials > 0 else 0
p_value = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))

print(f'\n  统计检验 (Top12 vs 25%基线):')
print(f'  观测命中率: {p_hat*100:.1f}% (基线25%)')
print(f'  z统计量: {z:.3f}')
print(f'  p值: {p_value:.4f} {"✅显著(p<0.05)" if p_value < 0.05 else "❌不显著"}')

# 19期累计(如果有)
if len(unique_results) >= 10:
    n_all = len(unique_results)
    t12_rate_all = sum(r['t12_hit'] for r in unique_results) / (n_all * 12) * 100
    t12_lift_all = sum(r['t12_lift'] for r in unique_results) / n_all
    t5_rate_all = sum(r['t5_hit'] for r in unique_results) / (n_all * 5) * 100
    t5_lift_all = sum(r['t5_lift'] for r in unique_results) / n_all
    print(f'\n  全{n_all}期累计统计:')
    print(f'  三维融合 Top5: {t5_rate_all:.1f}% Lift={t5_lift_all:.2f}x')
    print(f'  三维融合 Top12: {t12_rate_all:.1f}% Lift={t12_lift_all:.2f}x')
