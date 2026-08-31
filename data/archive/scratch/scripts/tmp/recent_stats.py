import json, os
import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
d = json.load(open(os.path.join(_PROJ, 'cache', 'learner_state.json'), 'r', encoding='utf-8'))
rh = d.get('review_history', [])
print(f'闭环学习引擎: 总复盘{len(rh)}期')
print(f'策略模式: {d.get("strategy_mode", "?")}')
print(f'三维权重: {d.get("pentagon_weights", {})}')
print(f'\n近10期复盘记录:')
for r in rh[-10:]:
    period = r.get('period', '?')
    t5h = r.get('top5_hits', '?')
    t5t = r.get('top5_total', 5)
    t5l = r.get('top5_lift', 0)
    t12h = r.get('top12_hits', '?')
    t12t = r.get('top12_total', 12)
    t12l = r.get('top12_lift', 0)
    print(f'  期{period}: Top5={t5h}/{t5t}(Lift={t5l:.2f}x) Top12={t12h}/{t12t}(Lift={t12l:.2f}x)')

# 近10期统计
if len(rh) >= 5:
    recent = rh[-10:]
    t5_rates = [r.get('top5_hits', 0) / max(r.get('top5_total', 5), 1) for r in recent]
    t12_rates = [r.get('top12_hits', 0) / max(r.get('top12_total', 12), 1) for r in recent]
    t5_avg = sum(t5_rates) / len(t5_rates) * 100
    t12_avg = sum(t12_rates) / len(t12_rates) * 100
    t5_lift_avg = sum(r.get('top5_lift', 0) for r in recent) / len(recent)
    t12_lift_avg = sum(r.get('top12_lift', 0) for r in recent) / len(recent)
    print(f'\n近{len(recent)}期统计:')
    print(f'  Top5平均命中率: {t5_avg:.1f}% (Lift={t5_lift_avg:.2f}x)')
    print(f'  Top12平均命中率: {t12_avg:.1f}% (Lift={t12_lift_avg:.2f}x)')
    baseline = 25.0
    t5_vs = '✅' if t5_avg > baseline else '❌'
    t12_vs = '✅' if t12_avg > baseline else '❌'
    print(f'  vs基线25%: Top5={t5_vs} Top12={t12_vs}')
