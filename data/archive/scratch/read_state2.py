import json
f = open('cache/self_learning_state.json', 'r', encoding='utf-8')
d = json.load(f)
h = d['history']
print(f"Total entries: {len(h)}")
# Find 2026168 entry
for i, entry in enumerate(h):
    ti = entry.get('target_issue', '')
    if ti in ['2026168', '2026167', '2026166']:
        print(f"\nEntry {i}: target_issue={ti}")
        for k in ['target_issue', 'environment', 'top5', 'top12', 'gauss_top5', 'cluster_top5', 
                   'fourier_top5', 'fusion_top5', 'he5', 'golden_core', 'pure_pool_high',
                   'trinity_weights']:
            print(f"  {k} = {entry.get(k, 'N/A')}")
# Also show last 3 entries
print("\n--- Last 3 entries ---")
for entry in h[-3:]:
    print(f"  target_issue={entry.get('target_issue', 'N/A')}, top5={entry.get('top5', 'N/A')}")
