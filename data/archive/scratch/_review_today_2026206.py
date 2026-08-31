# -*- coding: utf-8 -*-
"""复盘 2026206 开奖 + 最近10期命中率趋势"""
import re, json, collections, os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1. 读取开奖历史
history = {}
with open(os.path.join(PROJ, 'kl8_history_final.txt'), 'r', encoding='utf-8') as f:
    for line in f:
        m = re.search(r'period:(\d+),numbers:([\d\-]+)', line.strip())
        if m:
            history[m.group(1)] = set(int(n) for n in m.group(2).split('-'))

# 2. 读取自学习状态
with open(os.path.join(PROJ, 'cache', 'self_learning_state.json'), 'r', encoding='utf-8') as f:
    state = json.load(f)
records = state.get('history', [])

# 去重: 每个target取最新
latest_by_target = {}
for r in records:
    t = r.get('target_issue')
    rt = r.get('run_time', '')
    if t not in latest_by_target or rt > latest_by_target[t][0]:
        latest_by_target[t] = (rt, r)

# 3. 复盘 2026206
TARGET = '2026206'
actual = history.get(TARGET)
print(f"=== 复盘 {TARGET} 实际开奖 ===")
print(f"实际号码: {sorted(actual)}")
if actual:
    rt, r = latest_by_target.get(TARGET, (None, None))
    if r:
        def hits(name, key):
            lst = r.get(key, [])
            h = sorted(set(lst) & actual)
            if lst:
                lift = (len(h)/len(lst)) / (20/80)
            else:
                lift = 0
            print(f"  {name:<28} {hits_str(h, lst)}  Lift={lift:.2f}x")
        def hits_str(h, lst):
            return f"命中{len(h)}/{len(lst)} 号{h} 推荐{lst}"
        for name, key in [
            ("Trinity Top5", 'top5'),
            ("Trinity Top12", 'top12'),
            ("传统AI Top5", 'conf_top5'),
            ("传统AI Top12", 'conf_top12'),
            ("Hidden Energy 5 (HE5)", 'b3_final5'),
            ("mRMR Top12", 'mrmr_top12'),
            ("纯净池高置信", 'pure_pool_top'),
            ("纯净池旧规则", 'pure_pool_old_rule'),
            ("纯净池LR", 'pure_pool_lr'),
            ("纯净池全量", 'pure_pool_all'),
            ("方案2爆发Top5", 'deep_picks'),
            ("方案2跨规则共识", 'deep_consensus'),
        ]:
            hits(name, key)
        # 防守Top3
        kills = r.get('deep_kills', [])
        succ = [k for k in kills if k not in actual]
        err_kill = [k for k in kills if k in actual]
        print(f"  方案2防守Top3          成功{len(succ)}/{len(kills)} 回避正确{succ} 误杀{err_kill}")
        print(f"  kl_msg: {r.get('kl_msg','')}")

# 4. 最近10期趋势 (按target排序取最近10个有开奖的)
targets = sorted([t for t in latest_by_target if t in history])
recent = targets[-10:]
print(f"\n=== 最近10期命中率趋势 (期号 {recent[0]} ~ {recent[-1]}) ===")
print(f"{'期号':<8}{'T5':<6}{'T12':<6}{'HE5':<6}{'纯池top':<8}{'爆发top5':<9}{'T5Lift':<8}")
agg = collections.defaultdict(list)
for t in recent:
    rt, r = latest_by_target[t]
    a = history[t]
    t5 = set(r.get('top5', [])) & a
    t12 = set(r.get('top12', [])) & a
    he5 = set(r.get('b3_final5', [])) & a
    pp = set(r.get('pure_pool_top', [])) & a
    dp = set(r.get('deep_picks', [])) & a
    lift5 = (len(t5)/5)/(20/80)
    agg['t5'].append(len(t5)); agg['t12'].append(len(t12))
    agg['he5'].append(len(he5)); agg['pp'].append(len(pp))
    agg['dp'].append(len(dp)); agg['lift5'].append(lift5)
    print(f"{t:<8}{len(t5):<6}{len(t12):<6}{len(he5):<6}{len(pp):<3}/{len(r.get('pure_pool_top',[])):<5}{len(dp):<3}/{len(r.get('deep_picks',[])):<6}{lift5:<8.2f}")

print(f"\n=== 均值 ===")
for k in ['t5','t12','he5','pp','dp']:
    vals = agg[k]
    print(f"  {k}: 均命中 {sum(vals)/len(vals):.2f}")
print(f"  T5 平均Lift: {sum(agg['lift5'])/len(agg['lift5']):.3f}x (随机基线1.0x)")
print(f"  T5 平均命中率: {sum(agg['t5'])/(5*len(agg['t5']))*100:.1f}% (随机基线25%)")
print(f"  HE5 平均命中率: {sum(agg['he5'])/(5*len(agg['he5']))*100:.1f}% (随机基线25%)")