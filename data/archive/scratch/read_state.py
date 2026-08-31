import json
f = open('cache/self_learning_state.json', 'r', encoding='utf-8')
d = json.load(f)
h = d['history'][-1]
keys = ['target_issue', 'environment', 'top5', 'top12', 'gauss_top5', 'cluster_top5', 
        'fourier_top5', 'fusion_top5', 'he5', 'golden_core', 'pure_pool_high']
for k in keys:
    print(f"{k} = {h.get(k, 'N/A')}")
