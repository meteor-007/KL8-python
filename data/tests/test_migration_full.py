# -*- coding: utf-8 -*-
"""
Post-migration verification: directory layout, path hub, modules, web API payloads.
"""
import os
import sys
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ_DIR)
sys.path.insert(0, os.path.join(PROJ_DIR, "backend"))

from fastapi.testclient import TestClient

from backend.utils.paths import (
    data_path,
    find_module_script,
    get_cache_dir,
    get_frontend_dir,
    get_modules_dir,
    get_outputs_dir,
    get_project_root,
    get_raw_dir,
    get_reports_dir,
    get_storage_dir,
    _ensure_project_path,
)
_ensure_project_path()


class TestMigrationLayout(unittest.TestCase):
    def test_storage_layout(self):
        root = get_project_root()
        self.assertEqual(os.path.normpath(root), os.path.normpath(PROJ_DIR))
        for name in ("cache", "outputs", "reports", "reviews", "raw", "stats"):
            self.assertTrue(os.path.isdir(os.path.join(get_storage_dir(), name)), name)
        # root should NOT still hold live data dirs (ignore empty accidental recreations)
        for name in ("cache", "outputs", "reports", "reviews"):
            p = os.path.join(root, name)
            if os.path.isdir(p):
                nonempty = any(os.scandir(p))
                self.assertFalse(nonempty, f"root still has nonempty {name}")

    def test_core_data_files(self):
        for name in (
            "kl8_history_final.txt",
            "daily_points.txt",
            "auc_stats.json",
            "daily_run_state.json",
            "跟随+点位+开奖数据.xlsx",
        ):
            p = data_path(name)
            self.assertTrue(os.path.exists(p), f"{name} -> {p}")

    def test_modules_present(self):
        mods = get_modules_dir()
        for name in (
            "gold_pick2",
            "sixteen",
            "formula_jingle",
            "point_suppression",
            "datasource",
            "point_omission",
            "unified_brain",
            "aggregation",
            "tri_high",
        ):
            # 物理位置有两条合法路径：在册模块放 modules/<name>，
            # 历史遗留但仍在跑的放 modules/legacy/<name>。
            # 「是否退役」由 module_gate.MODULE_SEED 判决，不由目录位置决定。
            base = os.path.join(mods, name)
            if not os.path.isdir(base):
                base = os.path.join(mods, "legacy", name)
            self.assertTrue(os.path.isdir(base), name)
            self.assertTrue(
                os.path.isfile(os.path.join(base, "routes.py"))
                or name in ("trinity",),
                f"{name} routes",
            )

    def test_find_module_scripts(self):
        root = get_project_root()
        scripts = (
            "run_pick2_daily.py",
            "run_sixteen_daily.py",
            "run_unified_brain_daily.py",
            "run_nightly_daily.py",
            "run_evolution_daily.py",
            "run_full_pipeline.py",
            "run_error_correction_daily.py",
            "run_random_forest_daily.py",
            "run_dtw_daily.py",
            "run_tda_daily.py",
            "run_matrix_profile_daily.py",
            "run_transformer_daily.py",
            "run_linear_algebra_daily.py",
            "run_genetic_daily.py",
            "run_omission_daily.py",
            "run_unified_audit_daily.py",
            "run_jingle_daily.py",
            "run_suppression_daily.py",
            "run_aggregation_daily.py",
            "run_datasource_daily.py",
            "run_tri_high_daily.py",
        )
        for script in scripts:
            p = find_module_script(script)
            self.assertTrue(os.path.isfile(p), f"{script} -> {p}")
            norm = os.path.normpath(p)
            self.assertTrue(
                ("backend" + os.sep + "modules") in norm
                or ("backend" + os.sep + "pipeline") in norm,
                f"{script} should resolve under backend/modules or backend/pipeline, got {p}",
            )
            self.assertNotEqual(
                os.path.normpath(os.path.dirname(p)),
                os.path.normpath(root),
                f"{script} must not resolve to project root shim: {p}",
            )

    def test_frontend_pages_and_build(self):
        static = os.path.join(get_frontend_dir(), "static")
        self.assertTrue(os.path.isfile(os.path.join(static, "js", "k8_pages.js")))
        self.assertTrue(os.path.isfile(os.path.join(static, "js", "pages", "gold_pick2.js")))
        self.assertTrue(os.path.isfile(os.path.join(static, "js", "app.js")))
        self.assertTrue(os.path.isdir(os.path.join(static, "modules", "hub_core", "unified_brain")))
        from scripts.build_web import build_index_html
        self.assertTrue(build_index_html())
        index = open(os.path.join(static, "index.html"), encoding="utf-8").read()
        self.assertIn("k8_pages.js", index)
        self.assertIn("pages/gold_pick2.js", index)
        self.assertIn("hub_core/unified_brain", index)

    def test_packages_importable(self):
        from backend.core.gold_pick2 import calculate_gold_pick2_features
        from backend.modules.legacy.unified_brain.unified_brain import UnifiedDecisionBrain
        self.assertTrue(callable(calculate_gold_pick2_features))
        self.assertTrue(UnifiedDecisionBrain is not None)


class TestMigrationWebAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.api.api_server import app
        cls.client = TestClient(app)
        r = cls.client.post("/login", data={"passcode": "k8quant@2026"}, follow_redirects=False)
        assert r.status_code in (200, 302, 303), r.status_code

    def _json_ok(self, path, min_keys=None):
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200, f"{path} -> {r.status_code} {r.text[:200]}")
        data = r.json()
        self.assertIsInstance(data, (dict, list))
        if min_keys and isinstance(data, dict):
            for k in min_keys:
                self.assertIn(k, data, f"{path} missing {k}")
        return data

    def test_static_assets(self):
        for path in (
            "/static/js/app.js",
            "/static/js/k8_pages.js",
            "/static/js/pages/gold_pick2.js",
            "/static/js/pages/unified_brain.js",
            "/static/css/cyber_theme.css",
        ):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertGreater(len(r.content), 50, path)

    def test_home_after_login(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        # assembled index should be large
        self.assertGreater(len(r.text), 10000)

    def test_core_apis(self):
        self._json_ok("/api/system/status", ["status"])
        self._json_ok("/api/quant/latest-prediction")
        self._json_ok("/api/quant/matrix-80", ["matrix"])
        self._json_ok("/api/quant/unified-brain")
        self._json_ok("/api/modules/registry")

    def test_engine_apis(self):
        endpoints = [
            "/api/gold-pick2/summary",
            "/api/sixteen/summary",
            "/api/jingle/summary",
            "/api/suppression/summary",
            "/api/datasource/summary",
            "/api/point-omission/summary",
            "/api/aggregation/cockpit",
            "/api/tri-high/summary",
        ]
        soft_fail = []
        for path in endpoints:
            r = self.client.get(path)
            if r.status_code != 200:
                soft_fail.append((path, r.status_code, r.text[:160]))
                continue
            data = r.json()
            self.assertIsInstance(data, (dict, list), path)
        # Allow at most a few soft fails (empty module data), but none should 500
        hard = [x for x in soft_fail if x[1] >= 500]
        self.assertEqual(hard, [], f"server errors: {hard}")
        # 401/404 would mean routing broken after split
        broken = [x for x in soft_fail if x[1] in (401, 404)]
        self.assertEqual(broken, [], f"auth/routing broken: {broken}")

    def test_review_and_ops_apis(self):
        for path in (
            "/api/reviews/master-summary",
            "/api/reviews/ledger?limit=5",
            "/api/reports/list",
            "/api/health/freshness",
            "/api/scheduler/status",
            "/api/daily-points/info",
            "/api/config/params",
        ):
            r = self.client.get(path)
            self.assertIn(r.status_code, (200, 204), f"{path} -> {r.status_code}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
