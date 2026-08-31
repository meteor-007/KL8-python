#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""代码审计快速检查脚本"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 70)
print("  代码审计快速检查 — 2026-06-18")
print("=" * 70)

# 1. learner_state.json
try:
    with open('cache/learner_state.json', 'r', encoding='utf-8') as f:
        ls = json.load(f)
    pw = ls.get('pentagon_weights', {})
    print(f"\n[1] learner_state.json:")
    print(f"  Pentagon weights: {pw}")
    print(f"  MK weight: {pw.get('w_mk', 'N/A')} {'⚠️ >0.35' if pw.get('w_mk', 0) > 0.35 else '✅'}")
    print(f"  Total weight sum: {sum(pw.values()):.4f}")
    print(f"  Strategy mode: {ls.get('strategy_mode', 'N/A')}")
    print(f"  Total reviews: {ls.get('total_reviews', 'N/A')}")
    print(f"  Total adaptations: {ls.get('total_adaptations', 'N/A')}")
except Exception as e:
    print(f"[1] Error reading learner_state.json: {e}")

# 2. model_config.json
try:
    with open('model_config.json', 'r', encoding='utf-8') as f:
        mc = json.load(f)
    print(f"\n[2] model_config.json:")
    print(f"  MK weight: {mc.get('w_mk', 'N/A')}")
    print(f"  EF weight: {mc.get('w_ef', 'N/A')}")
    print(f"  RW weight: {mc.get('w_rw', 'N/A')}")
except Exception as e:
    print(f"[2] Error reading model_config.json: {e}")

# 3. scoring_config.yaml
try:
    import yaml
    with open('config/scoring_config.yaml', 'r', encoding='utf-8') as f:
        sc = yaml.safe_load(f)
    print(f"\n[3] scoring_config.yaml:")
    ew = sc.get('environment_weights', {})
    for env, w in ew.items():
        mk = w.get('w_mk', 0)
        print(f"  {env}: MK={mk:.4f} {'⚠️>0.35' if mk > 0.35 else '✅'}")
    b3t = sc.get('b3_right_quality_threshold', 'N/A')
    print(f"  B3 Right quality threshold: {b3t}")
    hot_ratio = sc.get('hot_ratio_threshold', 'N/A')
    print(f"  Hot ratio threshold: {hot_ratio}")
except Exception as e:
    print(f"[3] Error reading scoring_config.yaml: {e}")

# 4. auc_stats.json
try:
    with open('cache/auc_stats.json', 'r', encoding='utf-8') as f:
        auc = json.load(f)
    print(f"\n[4] auc_stats.json:")
    sig_count = auc.get('significant_bonf_count', 0)
    total_count = auc.get('total_numbers', 80)
    print(f"  Significant (Bonferroni) count: {sig_count}/{total_count}")
    print(f"  Level: {auc.get('confidence_level', 'N/A')}")
except Exception as e:
    print(f"[4] Error reading auc_stats.json: {e}")

# 5. Check environment recognition
try:
    import importlib
    mod = importlib.import_module('recognition.simplified_env_recognition')
    cls_name = [n for n in dir(mod) if not n.startswith('_') and 'recognition' in n.lower() or 'env' in n.lower()]
    print(f"\n[5] simplified_env_recognition module classes: {cls_name}")
    # Try different class names
    for cn in cls_name:
        cls = getattr(mod, cn)
        if isinstance(cls, type):
            obj = cls()
            print(f"  {cn}.current_env: {getattr(obj, 'current_env', 'N/A')}")
            print(f"  {cn}.confidence: {getattr(obj, 'confidence', 'N/A')}")
            break
except Exception as e:
    print(f"[5] Error: {e}")

# 7. Check platt parameters
try:
    with open('cache/learner_state.json', 'r', encoding='utf-8') as f:
        ls = json.load(f)
    platt_a = ls.get('platt_a', 'N/A')
    platt_b = ls.get('platt_b', 'N/A')
    print(f"\n[7] Platt calibration: a={platt_a}, b={platt_b}")
    if isinstance(platt_a, (int, float)) and abs(platt_a - 1.0) > 0.1:
        print(f"  ⚠️ platt_a deviates significantly from 1.0")
    else:
        print(f"  ✅ platt_a within normal range")
except Exception as e:
    print(f"[7] Error: {e}")

# 8. Walk-Forward results
try:
    with open('cache/walk_forward_results.json', 'r', encoding='utf-8') as f:
        wf = json.load(f)
    print(f"\n[8] Walk-Forward results:")
    print(f"  Global avg lift: {wf.get('global_avg_lift', 'N/A')}")
    print(f"  Last updated: {wf.get('last_updated', 'N/A')}")
except Exception as e:
    print(f"[8] No WF results or error: {e}")

print("\n" + "=" * 70)
print("  审计检查完成")
print("=" * 70)
