# -*- coding: utf-8 -*-
"""Smoke check after menu-aligned directory reorg."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

errors = []

def check(label, fn):
    try:
        fn()
        print(f"OK  {label}")
    except Exception as e:
        errors.append((label, e))
        print(f"FAIL {label}: {type(e).__name__}: {e}")

def t_build():
    from scripts.build_web import build_index_html
    assert build_index_html() is True

def t_gold_pick2():
    from backend.core import gold_pick2
    from backend.modules.gold_pick2 import load_draws_from_file
    assert hasattr(gold_pick2, "calculate_gold_pick2_features")
    assert callable(load_draws_from_file)

def t_sixteen():
    from backend.core.sixteen_period import sixteen_engine
    from backend.modules import sixteen
    assert sixteen_engine is not None

def t_unified():
    from backend.modules.unified_brain import unified_brain
    from backend.core.unified_brain.unified_brain import UnifiedDecisionBrain
    assert UnifiedDecisionBrain is not None

def t_kill():
    from kill_seeker.core.data_loader import DataLoader
    assert DataLoader is not None

def t_trinity():
    from backend.core.energy_field import calc_energy_field
    from backend.modules.trinity.energy_field import calc_energy_field as c2
    assert calc_energy_field is c2 or callable(calc_energy_field)

def t_retired_lstm():
    from models.lstm import LSTMService
    assert LSTMService is not None

def t_api_import():
    from backend.api.api_server import app
    assert app is not None

for label, fn in [
    ("build_web", t_build),
    ("gold_pick2 compat", t_gold_pick2),
    ("sixteen compat", t_sixteen),
    ("unified_brain", t_unified),
    ("kill_seeker", t_kill),
    ("trinity energy_field", t_trinity),
    ("retired models.lstm", t_retired_lstm),
    ("api_server import", t_api_import),
]:
    check(label, fn)

print("---")
if errors:
    print(f"{len(errors)} failure(s)")
    sys.exit(1)
print("all smoke checks passed")
