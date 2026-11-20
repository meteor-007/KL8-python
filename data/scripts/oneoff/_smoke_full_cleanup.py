# -*- coding: utf-8 -*-
"""Full cleanup smoke checks."""
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

def t_storage():
    from backend.utils.paths import get_cache_dir, get_outputs_dir, get_reports_dir, get_storage_dir
    assert os.path.isdir(get_storage_dir())
    assert get_cache_dir().replace("\\", "/").endswith("/storage/cache")
    assert os.path.isdir(get_cache_dir())
    assert os.path.isdir(get_outputs_dir())
    assert os.path.isdir(get_reports_dir())
    for name in ("cache", "outputs", "reports", "gemini_pick2", "models"):
        assert not os.path.isdir(os.path.join(ROOT, name)) or name == "storage", name

def t_no_root_runs():
    thin = [f for f in os.listdir(ROOT) if f.startswith("run_") and f.endswith("_daily.py")]
    assert not thin, f"root daily shims still present: {thin}"
    assert not os.path.isfile(os.path.join(ROOT, "run_full_pipeline.py"))

def t_scripts():
    from backend.utils.paths import find_module_script
    for s in ["run_pick2_daily.py", "run_sixteen_daily.py", "run_nightly_daily.py", "run_evolution_daily.py"]:
        p = find_module_script(s)
        assert os.path.isfile(p), p

def t_pkgs():
    from backend.utils.paths import _ensure_project_path
    _ensure_project_path()
    import gemini_pick2
    from models.lstm import LSTMService
    from backend.core.gold_pick2 import calculate_gold_pick2_features
    assert LSTMService and calculate_gold_pick2_features and gemini_pick2

def t_api():
    from backend.api.api_server import app
    assert len(app.routes) >= 10

def t_service():
    from backend.api.data_service import QuantDataService
    s = QuantDataService()
    for m in ("get_gold_pick2_summary", "get_sixteen_summary", "get_unified_brain", "get_dashboard_summary"):
        assert hasattr(s, m), m

def t_build():
    from scripts.build_web import build_index_html
    assert build_index_html() is True
    idx = os.path.join(ROOT, "frontend", "static", "index.html")
    text = open(idx, encoding="utf-8").read()
    assert "k8_pages.js" in text
    assert "pages/gold_pick2.js" in text
    assert "js/app.js" in text

for label, fn in [
    ("storage layout", t_storage),
    ("no root run shims", t_no_root_runs),
    ("find_module_script", t_scripts),
    ("packages via modules path", t_pkgs),
    ("api_server routes", t_api),
    ("data_service mixins", t_service),
    ("build_web pages", t_build),
]:
    check(label, fn)

print("---")
if errors:
    print(f"{len(errors)} failure(s)")
    sys.exit(1)
print("all full-cleanup smoke checks passed")
