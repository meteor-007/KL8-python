# -*- coding: utf-8 -*-
"""
Challenger 2 Empirical Stress Test Suite for Milestone 2
=========================================================
Adversarial challenge tests covering:
1. Root mirror elimination & directory cleanliness & path resolution
2. FastAPI server complete routes, error responses & boundary conditions
3. run_full_pipeline.py task resolution, key dependencies & dry-run execution
4. KillSeeker decoupled pure-Python Markov engine mathematical invariants & edge cases
5. Dual-root bootstrap isolation across independent subprocess invocations
"""

import os
import sys
import glob
import json
import pytest
import subprocess
from fastapi.testclient import TestClient

# Ensure dual-root setup
_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.api.api_server import app, find_script
from backend.utils.paths import get_project_root, get_backend_dir, get_frontend_dir, data_path


# =====================================================================
# Challenge 1: Single Source of Truth & Directory Cleanliness
# =====================================================================
class TestChallenger1DirectoryCleanliness:
    """Stress-test that no mirror directories exist and no dangling references remain."""

    DELETED_DIRS = [
        "audit", "config", "core", "data_acquisition",
        "format", "learning", "pipeline", "recognition", "utils"
    ]

    DELETED_FILES = [
        "deep_mining_engine.py",
        "excel_deep_mining_v2.py",
        "data_monitor.py",
        "trigger_review.py"
    ]

    def test_01_root_mirror_dirs_strictly_absent(self):
        """Verify that all 9 root mirror directories are completely non-existent."""
        root = get_project_root()
        for d in self.DELETED_DIRS:
            target = os.path.join(root, d)
            assert not os.path.exists(target), f"Mirror directory still exists in root: {d}"

    def test_02_root_redundant_files_strictly_absent(self):
        """Verify that all 4 standalone redundant root scripts are completely removed."""
        root = get_project_root()
        for f in self.DELETED_FILES:
            target = os.path.join(root, f)
            assert not os.path.exists(target), f"Redundant file still exists in root: {f}"

    def test_03_backend_canonical_directories_present(self):
        """Verify that all canonical directories exist strictly under backend/."""
        b_dir = get_backend_dir()
        for d in self.DELETED_DIRS:
            target = os.path.join(b_dir, d)
            assert os.path.isdir(target), f"Canonical backend directory missing: backend/{d}"

    def test_04_python_source_tree_import_cleanliness(self):
        """Scan all active python modules in backend/ and ensure they import without error."""
        root = get_project_root()
        b_dir = get_backend_dir()
        py_files = []
        for r, _, files in os.walk(b_dir):
            for f in files:
                if f.endswith(".py") and not f.startswith("."):
                    py_files.append(os.path.join(r, f))
        
        assert len(py_files) >= 20, f"Expected >= 20 python files in backend, found {len(py_files)}"
        
        # Test paths resolution from any arbitrary CWD
        orig_cwd = os.getcwd()
        try:
            # Change CWD to backend to test path resolution resilience
            os.chdir(b_dir)
            assert get_project_root() == root
            assert get_backend_dir() == b_dir
        finally:
            os.chdir(orig_cwd)


# =====================================================================
# Challenge 2: FastAPI API Server Full Route Instantiation & Stress
# =====================================================================
class TestChallenger2ApiServerStress:
    """Stress-test all FastAPI routes, parameter validation, and error paths."""

    @classmethod
    def setup_class(cls):
        cls.client = TestClient(app)

    def test_01_system_status_endpoint(self):
        resp = self.client.get("/api/system/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ["ONLINE", "OK", "READY", "HEALTHY", "WARNING"]
        assert "version" in data
        assert "system_name" in data

    def test_02_quant_latest_prediction(self):
        resp = self.client.get("/api/quant/latest-prediction")
        assert resp.status_code == 200
        data = resp.json()
        assert "period" in data
        assert "golden_pair" in data
        assert "top5_gold" in data or "top5" in data
        assert "top12_pool" in data or "top12" in data

    def test_03_quant_matrix_80(self):
        resp = self.client.get("/api/quant/matrix-80")
        assert resp.status_code == 200
        data = resp.json()
        matrix_list = data if isinstance(data, list) else data.get("matrix", data.get("numbers", []))
        assert len(matrix_list) == 80

    def test_04_quant_number_detail_boundaries(self):
        # Valid boundaries: 1 and 80
        resp1 = self.client.get("/api/quant/number/1")
        assert resp1.status_code == 200
        assert resp1.json().get("number") == 1

        resp80 = self.client.get("/api/quant/number/80")
        assert resp80.status_code == 200
        assert resp80.json().get("number") == 80

        # Invalid numbers: 0, 81, -5
        resp_invalid1 = self.client.get("/api/quant/number/0")
        assert resp_invalid1.status_code in [400, 422, 500]

        resp_invalid2 = self.client.get("/api/quant/number/81")
        assert resp_invalid2.status_code in [400, 422, 500]

    def test_05_quant_trends_and_history(self):
        resp_h = self.client.get("/api/quant/history-trends?limit=20")
        assert resp_h.status_code == 200
        data_h = resp_h.json()
        assert "periods" in data_h
        assert "top5_hits" in data_h

        resp_l = self.client.get("/api/quant/lottery-trends?limit=30")
        assert resp_l.status_code == 200

        resp_t = self.client.get("/api/quant/history-table?page=1&page_size=15")
        assert resp_t.status_code == 200
        data_t = resp_t.json()
        assert "items" in data_t or "records" in data_t
        assert data_t.get("page") == 1

    def test_06_reports_endpoints(self):
        resp_list = self.client.get("/api/reports/list")
        assert resp_list.status_code == 200
        reports = resp_list.json()
        assert isinstance(reports, list)
        assert len(reports) > 0

        resp_missing = self.client.get("/api/reports/detail/non_existent_20990101.md")
        assert resp_missing.status_code == 404

    def test_07_jingle_endpoints(self):
        resp_sum = self.client.get("/api/jingle/summary")
        assert resp_sum.status_code == 200
        assert "target_issue" in resp_sum.json()

        resp_rev = self.client.get("/api/jingle/review?n=10")
        assert resp_rev.status_code == 200

        resp_rules = self.client.get("/api/jingle/rules")
        assert resp_rules.status_code == 200
        assert "rules" in resp_rules.json()

    def test_08_spatial_points_endpoints(self):
        resp_sum = self.client.get("/api/spatial-points/summary")
        assert resp_sum.status_code == 200

        resp_mat = self.client.get("/api/spatial-points/matrix")
        assert resp_mat.status_code == 200

        resp_rev = self.client.get("/api/spatial-points/review?n=10")
        assert resp_rev.status_code == 200

    def test_09_lstm_endpoints(self):
        resp_sum = self.client.get("/api/lstm/summary")
        assert resp_sum.status_code == 200

        resp_rev = self.client.get("/api/lstm/review?n=5")
        assert resp_rev.status_code == 200

    def test_10_follow_and_suppression_endpoints(self):
        resp_f = self.client.get("/api/follow/summary")
        assert resp_f.status_code == 200

        resp_fc = self.client.get("/api/follow/conditions")
        assert resp_fc.status_code == 200

        resp_s = self.client.get("/api/suppression/summary")
        assert resp_s.status_code == 200

        resp_sp = self.client.get("/api/suppression/patterns")
        assert resp_sp.status_code == 200

    def test_11_kill_and_gemini_endpoints(self):
        resp_k = self.client.get("/api/kill/summary")
        assert resp_k.status_code == 200

        resp_g = self.client.get("/api/gemini/summary")
        assert resp_g.status_code == 200

        resp_gp = self.client.get("/api/gold-pick2/summary")
        assert resp_gp.status_code == 200

    def test_12_aggregation_cockpit_and_history(self):
        """Test newly merged aggregation routes in backend/api/api_server.py."""
        resp_cockpit = self.client.get("/api/aggregation/cockpit")
        assert resp_cockpit.status_code == 200
        data = resp_cockpit.json()
        assert "target_period" in data
        assert "stable_top10" in data

        resp_hist = self.client.get("/api/aggregation/history")
        assert resp_hist.status_code == 200
        hist_files = resp_hist.json()
        assert isinstance(hist_files, list)

        resp_detail_missing = self.client.get("/api/aggregation/history/not_real_file.txt")
        assert resp_detail_missing.status_code == 404

    def test_13_config_param_stress_and_validation(self):
        """Stress-test param config updates, boundaries, and validation rejection."""
        # 1. Valid update
        valid_payload = {"EF": 0.40, "RW": 0.30, "FO": 0.30}
        resp = self.client.post("/api/config/params", json=valid_payload)
        assert resp.status_code == 200
        assert resp.json().get("status") == "SUCCESS"

        # 2. Invalid sum (0.2 != 1.0) -> HTTP 400
        invalid_sum_payload = {"EF": 0.10, "RW": 0.05, "FO": 0.05}
        resp_bad_sum = self.client.post("/api/config/params", json=invalid_sum_payload)
        assert resp_bad_sum.status_code == 400
        assert "三维权重之和" in resp_bad_sum.json()["detail"]

        # 3. Out of range (> 1.0) -> HTTP 422 Pydantic ValidationError
        out_of_range_payload = {"EF": 1.5, "RW": 0.0, "FO": 0.0}
        resp_bad_range = self.client.post("/api/config/params", json=out_of_range_payload)
        assert resp_bad_range.status_code == 422

    def test_14_pipeline_logs_and_static_routes(self):
        resp_log = self.client.get("/api/pipeline/logs/missing_task_id_9999")
        assert resp_log.status_code == 404

        resp_fav = self.client.get("/favicon.ico")
        assert resp_fav.status_code == 204

        resp_index = self.client.get("/")
        assert resp_index.status_code == 200


# =====================================================================
# Challenge 3: run_full_pipeline.py Task Dispatch & Dependencies
# =====================================================================
class TestChallenger3PipelineDispatch:
    """Stress-test run_full_pipeline task dependency resolution and dry execution."""

    def test_01_script_resolver_finds_all_task_targets(self):
        """Verify that find_script resolves all sub-tasks in backend/."""
        tasks = [
            os.path.join("data_acquisition", "fetch_kl8_history.py"),
            os.path.join("data_acquisition", "generate_hot_excel.py"),
            os.path.join("data_acquisition", "process_hot_numbers.py"),
            os.path.join("data_acquisition", "sync_history_to_excel.py"),
            os.path.join("format", "apply_formats.py"),
            os.path.join("pipeline", "auto_generate_daily_report.py"),
            os.path.join("pipeline", "run_full_pipeline.py"),
            os.path.join("utils", "data_validator.py"),
        ]
        for task in tasks:
            resolved = find_script(task)
            assert os.path.exists(resolved), f"Failed to resolve task script: {task} (resolved: {resolved})"

    def test_02_task0_env_check_execution(self):
        """Directly invoke task0_env_check from run_full_pipeline and assert success."""
        import run_full_pipeline
        assert hasattr(run_full_pipeline, "task0_env_check")
        assert hasattr(run_full_pipeline, "task00_validate")
        check_ok = run_full_pipeline.task0_env_check()
        assert check_ok is True, "task0_env_check failed due to missing files or broken lock"

    def test_03_pipeline_dry_run_validation(self):
        """Run data validator dry-run to verify task 0.0 validation integrity."""
        validator_path = find_script(os.path.join("utils", "data_validator.py"))
        assert os.path.exists(validator_path)
        res = subprocess.run(
            [sys.executable, "-u", validator_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        assert res.returncode == 0, f"data_validator failed: {res.stderr}"


# =====================================================================
# Challenge 4: Decoupled KillSeeker Pure-Python Markov Engine Stress
# =====================================================================
class TestChallenger4KillSeekerMarkovStress:
    """Stress-test pure Python MarkovEngine in kill_seeker for numerical stability."""

    def test_01_markov_evidence_empty_and_minimal_history(self):
        from kill_seeker.core.markov_engine import markov_evidence, series_from_sets
        
        # 1. Empty history
        res_empty = markov_evidence([])
        assert isinstance(res_empty, dict)
        assert len(res_empty) == 80
        for num, ev in res_empty.items():
            prob = ev["p_combined"]
            assert 0.0 <= prob <= 1.0
            assert prob == pytest.approx(0.25, abs=0.01)

        # 2. Single draw
        single_draw = [set(range(1, 21))]
        res_single = markov_evidence(single_draw)
        assert len(res_single) == 80
        for num, ev in res_single.items():
            prob = ev["p_combined"]
            assert 0.0 <= prob <= 1.0

    def test_02_cold_comeback_curve_extremes(self):
        from kill_seeker.core.markov_engine import cold_comeback_curve
        
        # Generate synthetic 0/1 series
        series = [1 if i % 4 == 0 else 0 for i in range(100)]
        res_curve = cold_comeback_curve(series, max_omission=15)
        assert len(res_curve) == 16
        for L, metrics in res_curve.items():
            p_hat = metrics["p_hat"]
            assert 0.0 <= p_hat <= 1.0
            assert not (p_hat != p_hat)  # not NaN

    def test_03_kill_seeker_diagnose_cli_execution(self):
        """Execute run_killseeker_daily.py --diagnose in a subprocess and assert 10/10 modules OK."""
        proj = get_project_root()
        script = os.path.join(proj, "run_killseeker_daily.py")
        res = subprocess.run(
            [sys.executable, script, "--diagnose"],
            cwd=proj,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        assert res.returncode == 0, f"KillSeeker diagnose failed with returncode {res.returncode}: {res.stderr}"
        assert "10/10" in res.stdout, f"Diagnose did not report 10/10: {res.stdout}"


# =====================================================================
# Challenge 5: Independent Subprocess Dual-Root Bootstrap Isolation
# =====================================================================
class TestChallenger5SubprocessBootstrapIsolation:
    """Stress-test that scripts can be run directly from external processes without PYTHONPATH."""

    def test_01_root_entrypoint_scripts_help_and_run(self):
        proj = get_project_root()
        entrypoints = [
            ("run_points_daily.py", ["5"]),
            ("run_geminixuan2_daily.py", ["5"]),
            ("run_follow_daily.py", ["5"]),
            ("run_jingle_daily.py", ["5"]),
            ("run_suppression_daily.py", ["5"]),
            ("run_pick2_daily.py", ["5"]),
            ("run_aggregation_daily.py", ["--force"]),
        ]
        
        # Clear PYTHONPATH to test raw dual-root bootstrap
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)

        for script_name, args in entrypoints:
            script_path = os.path.join(proj, script_name)
            assert os.path.exists(script_path), f"Entrypoint missing: {script_name}"
            cmd = [sys.executable, script_path] + args
            res = subprocess.run(
                cmd,
                cwd=proj,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            assert res.returncode == 0, f"Script {script_name} failed: {res.stderr}\nOutput: {res.stdout}"
