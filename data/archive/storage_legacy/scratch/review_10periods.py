#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""10期复盘统计脚本"""
import json
import os

DATA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load history
hist = []
with open(os.path.join(DATA, 'kl8_history_final.txt'), 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = {}
        for p in line.split(','):
            k, v = p.split(':', 1)
            parts[k] = v
        nums = [int(x) for x in parts['numbers'].split('-')]
        hist.append({'period': parts['period'], 'date': parts['date'], 'numbers': set(nums)})

# Load self_learning state
with open(os.path.join(DATA, 'cache', 'self_learning_state.json'), 'r', encoding='utf-8') as f:
    sl = json.load(f)

# Get unique target periods (latest first, dedup by target_issue)
seen = set()
runs = []
for r in sl['history']:
    t = r.get('target_issue')
    if t and t not in seen:
        seen.add(t)
        runs.append(r)

# Build actual results lookup
actual = {h['period']: h['numbers'] for h in hist}

# Review last 10 unique target periods
print('=' * 80)
print('10期复盘统计')
print('=' * 80)

trinity5_hits = []
trinity12_hits = []
ai5_hits = []
ai12_hits = []
he5_hits = []

for r in runs[:10]:
    t = r.get('target_issue')
    act = actual.get(t)
    if not act:
        print(f'  {t}: 无实际开奖数据')
        continue

    t5 = set(r.get('top5', []))
    t12 = set(r.get('top12', []))
    c5 = set(r.get('conf_top5', []))
    c12 = set(r.get('conf_top12', []))
    he5 = set(r.get('he5', []))

    h_t5 = len(t5 & act)
    h_t12 = len(t12 & act)
    h_c5 = len(c5 & act)
    h_c12 = len(c12 & act)
    h_he5 = len(he5 & act)

    trinity5_hits.append(h_t5)
    trinity12_hits.append(h_t12)
    ai5_hits.append(h_c5)
    ai12_hits.append(h_c12)
    he5_hits.append(h_he5)

    lift_t5 = h_t5 / 5 / 0.25
    lift_t12 = h_t12 / 12 / 0.25
    lift_c5 = h_c5 / 5 / 0.25
    lift_c12 = h_c12 / 12 / 0.25
    lift_he5 = h_he5 / 5 / 0.25

    print(f'  {t}: T5={h_t5}/5({lift_t5:.2f}x) T12={h_t12}/12({lift_t12:.2f}x) '
          f'AI5={h_c5}/5({lift_c5:.2f}x) AI12={h_c12}/12({lift_c12:.2f}x) '
          f'HE5={h_he5}/5({lift_he5:.2f}x)')

n = len(trinity5_hits)
if n > 0:
    avg_t5 = sum(trinity5_hits) / n
    avg_t12 = sum(trinity12_hits) / n
    avg_ai5 = sum(ai5_hits) / n
    avg_ai12 = sum(ai12_hits) / n
    avg_he5 = sum(he5_hits) / n

    print(f'\n--- {n}期汇总 ---')
    print(f'  三维融合 Top5:  {avg_t5:.1f}/5 = {avg_t5/5*100:.1f}%  Lift={avg_t5/5/0.25:.2f}x')
    print(f'  三维融合 Top12: {avg_t12:.1f}/12 = {avg_t12/12*100:.1f}%  Lift={avg_t12/12/0.25:.2f}x')
    print(f'  传统AI Top5:    {avg_ai5:.1f}/5 = {avg_ai5/5*100:.1f}%  Lift={avg_ai5/5/0.25:.2f}x')
    print(f'  传统AI Top12:   {avg_ai12:.1f}/12 = {avg_ai12/12*100:.1f}%  Lift={avg_ai12/12/0.25:.2f}x')
    print(f'  HE5:            {avg_he5:.1f}/5 = {avg_he5/5*100:.1f}%  Lift={avg_he5/5/0.25:.2f}x')

# Also do 2026181 detailed review
print('\n' + '=' * 80)
print('2026181期 详细复盘')
print('=' * 80)

act_181 = actual.get('2026181')
if act_181:
    print(f'  实际开奖: {sorted(act_181)}')

    # Get the latest run for 2026181
    for r in runs[:2]:
        if r.get('target_issue') == '2026181':
            t5 = set(r.get('top5', []))
            t12 = set(r.get('top12', []))
            c5 = set(r.get('conf_top5', []))
            c12 = set(r.get('conf_top12', []))
            pp = set(r.get('pure_pool_top', []))

            print(f'  三维融合 Top5:  {sorted(t5)} → 命中 {sorted(t5 & act_181)} → {len(t5 & act_181)}/5 '
                  f'(Lift={len(t5 & act_181)/5/0.25:.2f}x)')
            print(f'  三维融合 Top12: {sorted(t12)} → 命中 {sorted(t12 & act_181)} → {len(t12 & act_181)}/12 '
                  f'(Lift={len(t12 & act_181)/12/0.25:.2f}x)')
            print(f'  传统AI Top5:    {sorted(c5)} → 命中 {sorted(c5 & act_181)} → {len(c5 & act_181)}/5 '
                  f'(Lift={len(c5 & act_181)/5/0.25:.2f}x)')
            print(f'  传统AI Top12:   {sorted(c12)} → 命中 {sorted(c12 & act_181)} → {len(c12 & act_181)}/12 '
                  f'(Lift={len(c12 & act_181)/12/0.25:.2f}x)')
            print(f'  纯净池定胆:     {sorted(pp)} → 命中 {sorted(pp & act_181)} → {len(pp & act_181)}/6 '
                  f'(Lift={len(pp & act_181)/6/0.25:.2f}x)')
            break

# WF backtest summary
print('\n' + '=' * 80)
print('Walk-Forward 回测')
print('=' * 80)
wf_path = os.path.join(DATA, 'cache', 'walk_forward_results.json')
if os.path.exists(wf_path):
    with open(wf_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)
    print(f'  Folds: {wf.get("n_folds")}')
    print(f'  全局平均命中率: {wf.get("global_avg_hit_rate"):.4f} (随机基线=0.25)')
    print(f'  全局平均Lift: {wf.get("global_avg_lift"):.4f}')
    print(f'  标准差: {wf.get("global_std_hit_rate"):.4f}')
    print(f'  稳定性: {wf.get("stability"):.4f}')
    print(f'  趋势: {wf.get("trend")}')

# AUC stats
print('\n' + '=' * 80)
print('AUC 统计')
print('=' * 80)
auc_path = os.path.join(DATA, 'auc_stats.json')
if os.path.exists(auc_path):
    with open(auc_path, 'r', encoding='utf-8') as f:
        auc = json.load(f)
    results = auc.get('results', [])
    sig_bonf = [r for r in results if r.get('significant_bonf')]
    sig_fdr = [r for r in results if r.get('significant_fdr')]
    sig_raw = [r for r in results if r.get('significant_raw')]
    print(f'  Bonferroni显著: {len(sig_bonf)}个 { [r["num"] for r in sig_bonf] }')
    print(f'  FDR显著: {len(sig_fdr)}个 { [r["num"] for r in sig_fdr] }')
    print(f'  Raw p<0.05: {len(sig_raw)}个 { [r["num"] for r in sig_raw] }')

# Learner state
print('\n' + '=' * 80)
print('学习引擎状态')
print('=' * 80)
ls_path = os.path.join(DATA, 'cache', 'learner_state.json')
if os.path.exists(ls_path):
    with open(ls_path, 'r', encoding='utf-8') as f:
        ls = json.load(f)
    print(f'  总复盘次数: {ls.get("total_reviews")}')
    print(f'  总调整次数: {ls.get("total_adaptations")}')
    print(f'  策略模式: {ls.get("strategy_mode")}')
    print(f'  权重: {ls.get("pentagon_weights")}')
