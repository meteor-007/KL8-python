#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick import test for all key modules"""
import sys
import os

# Add data directory to path - this is the parent of scripts/tmp
data_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, data_dir)
print(f"Added to sys.path: {data_dir}")

modules = [
    "pipeline.auto_generate_daily_report",
    "learning.autonomous_learner",
    "core.feature_optimizer",
    "core.algorithm_optimizer",
    "core.strategy_optimizer",
    "core.score_composer",
    "core.entropy_optimizer",
    "core.loss_weight_updater",
    "core.walk_forward_validator",
    "data_acquisition.fetch_kl8_history",
    "data_acquisition.generate_hot_excel",
    "data_acquisition.process_hot_numbers",
    "data_acquisition.sync_history_to_excel",
    "format.apply_formats",
    "recognition.simplified_env_recognition",
    "audit.v3_trinity_audit",
    "audit.b3_right_quality_checker",
]

results = {}
for mod_name in modules:
    try:
        __import__(mod_name)
        results[mod_name] = "OK"
    except Exception as e:
        results[mod_name] = f"FAIL: {e}"

print("=" * 60)
print("  Module Import Audit Results")
print("=" * 60)
ok_count = 0
fail_count = 0
for mod, status in results.items():
    icon = "OK" if status == "OK" else "FAIL"
    print(f"  {icon} {mod}: {status}")
    if status == "OK":
        ok_count += 1
    else:
        fail_count += 1

print("=" * 60)
print(f"  Total: {ok_count} OK, {fail_count} FAIL")
