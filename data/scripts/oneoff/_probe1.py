import json, itertools
p = r'C:\D-pan\Dpanqianyi\Python-Project\data\data_cache.json'
d = json.load(open(p, encoding='utf-8'))
print(type(d), list(d.keys()))
for k,v in d.items():
    print('KEY', k, type(v), len(v) if hasattr(v,'__len__') else '')
d1 = d['data1']
ks = sorted(d1.keys())
print('draws', len(ks), ks[0], ks[-1])
k = ks[-1]
print(k, json.dumps(d1[k], ensure_ascii=False)[:800])
print('--- stars')
ds = d.get('data1_stars')
ks2 = sorted(ds.keys())
print(len(ks2), ks2[0], ks2[-1])
print(json.dumps(ds[ks2[-1]], ensure_ascii=False)[:600])
print('--- data2')
d2 = d['data2']
ks3 = sorted(d2.keys())
print(len(ks3), ks3[0], ks3[-1])
print(json.dumps(d2[ks3[-1]], ensure_ascii=False)[:600])
