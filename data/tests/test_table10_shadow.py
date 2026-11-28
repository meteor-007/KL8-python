# -*- coding: utf-8 -*-
import os
import unittest

from fastapi.testclient import TestClient

from backend.core.module_gate import decree_status_of, is_module_active
from backend.modules.table10_shadow.service import get_period_detail, get_shadow_summary
from backend.utils.paths import data_path


class TestTable10Shadow(unittest.TestCase):
    def test_module_gate_observation_only(self):
        self.assertEqual(decree_status_of("table10_shadow"), "observation")
        self.assertTrue(is_module_active("table10_shadow"))
        self.assertNotEqual(decree_status_of("table10_shadow"), "votable")

    def test_shadow_summary_and_period_detail(self):
        summary = get_shadow_summary()
        self.assertEqual(summary["status"], "success")
        self.assertEqual(summary["module_status"], "observation")
        self.assertGreaterEqual(summary["metrics"]["total_periods"], 10)
        self.assertIsNotNone(summary["latest"])

        detail_318 = get_period_detail(318)
        self.assertEqual(detail_318["status"], "success")
        self.assertFalse(detail_318["is_drawn"])
        self.assertTrue(len(detail_318["matrix"]) > 0)

        detail_317 = get_period_detail(317)
        self.assertEqual(detail_317["status"], "success")

    def test_api_endpoints_and_frontend_build(self):
        from backend.api.api_server import app

        client = TestClient(app)
        resp = client.get("/api/table10-shadow/summary")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["module_status"], "observation")

        resp_p = client.get("/api/table10-shadow/period/318")
        self.assertEqual(resp_p.status_code, 200)
        self.assertEqual(resp_p.json()["period"], 318)

        resp_404 = client.get("/api/table10-shadow/period/999999")
        self.assertEqual(resp_404.status_code, 404)

        index_path = data_path("frontend", "static", "index.html")
        self.assertTrue(os.path.exists(index_path))
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("table10_shadow_cockpit", html)


if __name__ == "__main__":
    unittest.main()
