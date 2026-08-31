import json
with open('cache/walk_forward_results.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
print('global_avg_lift:', d.get('global_avg_lift', 'N/A'))
print('folds:', len(d.get('per_fold_summary', [])))
print('stability:', d.get('stability_score', 'N/A'))
