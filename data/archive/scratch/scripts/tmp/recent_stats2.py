"""近10期累计统计 - 从self_learning_state.json和kl8_history计算"""
import json, os
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
# 建立期号→开奖号码映射
hist_map = {h['issue']: set(h['numbers']) for h in history}

print('=' * 70)
print('  近10期实盘命中率统计 (基于self_learning_state.json)')
print('=' * 70)

results = []
for rec in pred_history[:30]:  # 最多30条记录
    target = str(rec.get('target_issue', ''))
    actual = hist_map.get(target, None)
    if actual is None:
        continue
    
    t5 = rec.get('top5', [])
    t12 = rec.get('top12', [])
    he5 = rec.get('b3_final5', [])
    pp = rec.get('pure_pool_top', [])
    fu5 = rec.get('high_order_fusion_top5', [])
    
    hit5 = len(set(t5) & actual)
    hit12 = len(set(t12) & actual)
    hit_he5 = len(set(he5) & actual)
    hit_pp = len(set(pp) & actual)
    hit_fu5 = len(set(fu5) & actual)
    
    results.append({
        'period': target,
        't5_hit': hit5, 't5_lift': hit5/5/0.25,
        't12_hit': hit12, 't12_lift': hit12/12/0.25,
        'he5_hit': hit_he5, 'he5_lift': hit_he5/5/0.25 if he5 else 0,
        'pp_hit': hit_pp,
        'fu5_hit': hit_fu5, 'fu5_lift': hit_fu5/5/0.25 if fu5 else 0,
    })

# 显示近10期
print(f'\n  {"期号":>8s}  {"Top5":>6s}  {"Lift":>6s}  {"Top12":>6s}  {"Lift":>6s}  {"HE5":>4s}  {"整合5":>4s}')
print('  ' + '-' * 55)
for r in results[:10]:
    print(f'  {r["period"]:>8s}  {r["t5_hit"]}/5  {r["t5_lift"]:5.2f}x  {r["t12_hit"]}/12 {r["t12_lift"]:5.2f}x  {r["he5_hit"]}/5  {r["fu5_hit"]}/5')

# 累计统计
if results:
    n = min(len(results), 10)
    recent = results[:n]
    t5_rate = sum(r['t5_hit'] for r in recent) / (n * 5) * 100
    t12_rate = sum(r['t12_hit'] for r in recent) / (n * 12) * 100
    t5_lift = sum(r['t5_lift'] for r in recent) / n
    t12_lift = sum(r['t12_lift'] for r in recent) / n
    he5_rate = sum(r['he5_hit'] for r in recent) / (n * 5) * 100 if any(r['he5_lift'] > 0 for r in recent) else 0
    fu5_rate = sum(r['fu5_hit'] for r in recent) / (n * 5) * 100 if any(r['fu5_lift'] > 0 for r in recent) else 0
    
    print(f'\n  近{n}期累计统计:')
    print(f'  Top5平均:  {t5_rate:.1f}% (Lift={t5_lift:.2f}x) {"✅" if t5_lift > 1.0 else "❌"}')
    print(f'  Top12平均: {t12_rate:.1f}% (Lift={t12_lift:.2f}x) {"✅" if t12_lift > 1.0 else "❌"}')
    if he5_rate > 0:
        print(f'  HE5平均:   {he5_rate:.1f}%')
    if fu5_rate > 0:
        print(f'  整合5平均: {fu5_rate:.1f}%')
    
    # 显著性检验 (简单二项检验)
    from math import sqrt
    # Top12: n*12次试验, 基线p=0.25, 观测命中率
    total_trials = n * 12
    total_hits = sum(r['t12_hit'] for r in recent)
    p_hat = total_hits / total_trials if total_trials > 0 else 0
    p0 = 0.25
    z = (p_hat - p0) / sqrt(p0 * (1-p0) / total_trials) if total_trials > 0 else 0
    from math import erf
    p_value = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    print(f'\n  统计检验 (Top12 vs 25%基线):')
    print(f'  z={z:.3f}, p={p_value:.4f} {"✅显著" if p_value < 0.05 else "❌不显著"}')
