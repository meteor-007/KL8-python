import sys, json

sys.stdout.reconfigure(encoding='utf-8')
with open('storage/outputs/reports/module_ledger_report_latest.json', encoding='utf-8') as f:
    data = json.load(f)

modules = data.get('modules', {})
active_mods = []
for k, v in modules.items():
    if not v.get('retired', False):
        active_mods.append({
            'key': k,
            'name': v.get('name', k),
            'n_periods': v.get('n_periods', 0),
            'total_picks': v.get('total_picks', 0),
            'total_hits': v.get('total_hits', 0),
            'pooled_rate': v.get('pooled_rate', 0.0),
            'lift': v.get('lift', 0.0)
        })

active_mods.sort(key=lambda x: (x['lift'], x['pooled_rate']), reverse=True)

print(f"Active Modules Sorted by Recent Multi-Period Lift ({len(active_mods)}):")
for idx, m in enumerate(active_mods, 1):
    print(f"{idx:2d}. {m['name']} ({m['key']}): {m['n_periods']}期实战 | {m['total_hits']}/{m['total_picks']}码 | 综合命中率 {m['pooled_rate']*100:.2f}% | Lift {m['lift']:.3f}x")
