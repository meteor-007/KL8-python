#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re, os, glob

reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
data_dir = os.path.join(os.path.dirname(__file__), '..')
files = sorted(
    glob.glob(os.path.join(reports_dir, 'daily_analysis_report_202606*.md'))
    + glob.glob(os.path.join(reports_dir, 'daily_analysis_report_202607*.md'))
)
hist = {}
with open(os.path.join(data_dir, 'kl8_history_final.txt'), encoding='utf-8') as f:
    for line in f:
        m = re.match(r'date:([^,]+),period:(\d+),numbers:(.+)', line.strip())
        if m:
            nums = set(int(x) for x in m.group(3).split('-'))
            hist[m.group(2)] = nums


def parse_list(text, key):
    m = re.search(key + r'[^[]*\[([^\]]+)\]', text)
    if not m:
        return []
    return [int(x.strip()) for x in m.group(1).split(',') if x.strip().isdigit()]


results = []
for fp in files[-10:]:
    with open(fp, encoding='utf-8') as f:
        content = f.read()
    tm = re.search(r'目标期号[^0-9]*(\d{7})', content)
    if not tm:
        continue
    period = tm.group(1)
    if period not in hist:
        continue
    actual = hist[period]
    he5 = parse_list(content, r'最终推荐 \(5 码\)')
    tr5 = parse_list(content, r'极秘 Top 5')
    tr12 = parse_list(content, r'极秘 Top 12')
    ai5 = parse_list(content, r'Top 5 置信度精选')
    ai12 = parse_list(content, r'Top 12 综合拦截')

    def hits(lst):
        return len(set(lst) & actual), len(lst)

    results.append({
        'period': period,
        'HE5': hits(he5), 'Tr5': hits(tr5), 'Tr12': hits(tr12),
        'AI5': hits(ai5), 'AI12': hits(ai12),
    })

print('=' * 70)
print('  最近10期命中率汇总')
print('=' * 70)
print(f"{'期号':<12} {'HE5':>8} {'Tr5':>8} {'Tr12':>8} {'AI5':>8} {'AI12':>8}")
print('-' * 70)
for r in results:
    fmt = lambda h: f'{h[0]}/{h[1]}'
    print(f"{r['period']:<12} {fmt(r['HE5']):>8} {fmt(r['Tr5']):>8} {fmt(r['Tr12']):>8} {fmt(r['AI5']):>8} {fmt(r['AI12']):>8}")

if results:
    print('-' * 70)
    for key, n in [('HE5', 5), ('Tr5', 5), ('Tr12', 12), ('AI5', 5), ('AI12', 12)]:
        avg = sum(r[key][0] for r in results) / len(results)
        baseline = n * 0.25
        lift = avg / baseline if baseline else 0
        print(f'  {key}: 平均命中 {avg:.2f}/{n}  Lift={lift:.2f}x  (随机基线={baseline:.2f})')
