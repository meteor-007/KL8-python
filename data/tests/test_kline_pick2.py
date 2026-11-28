# -*- coding: utf-8 -*-
import os
import unittest

from fastapi.testclient import TestClient

from backend.core.module_gate import decree_status_of, is_module_active
from backend.modules.kline_pick2.kline_engine import (
    get_kline_risk_map,
    get_kline_summary,
    get_pair_kline_chart,
)
from backend.utils.paths import data_path


class TestKlinePick2(unittest.TestCase):
    def test_module_gate_registered(self):
        self.assertEqual(decree_status_of("kline_pick2"), "observation")
        self.assertTrue(is_module_active("kline_pick2"))

    def test_engine_summary_and_chart(self):
        summary = get_kline_summary(oos_window=60)
        self.assertEqual(summary["status"], "success")
        self.assertEqual(summary["total_pairs_scanned"], 3160)
        self.assertTrue(len(summary["top_positive"]) > 0)
        self.assertIn("oos_audit", summary)

        pair = summary["top_positive"][0]["pair"]
        chart = get_pair_kline_chart(pair[0], pair[1], num_candles=30)
        self.assertEqual(chart["status"], "success")
        self.assertTrue(len(chart["candles"]) > 0)

        risk_map = get_kline_risk_map([(pair[0], pair[1])])
        key = (min(pair), max(pair))
        self.assertIn(key, risk_map)

    def test_api_endpoints_and_frontend_build(self):
        from backend.api.api_server import app

        client = TestClient(app)
        resp = client.get("/api/kline-pick2/summary?oos_window=60")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "success")

        resp_chart = client.get("/api/kline-pick2/chart/17/35?candles=30")
        self.assertEqual(resp_chart.status_code, 200)
        self.assertEqual(resp_chart.json()["pair"], [17, 35])

        resp_bad = client.get("/api/kline-pick2/chart/10/10")
        self.assertEqual(resp_bad.status_code, 400)

        index_path = data_path("frontend", "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("kline_pick2_cockpit", html)
        self.assertIn("klinePick2ChartDom", html)


if __name__ == "__main__":
    unittest.main()
