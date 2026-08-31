# -*- coding: utf-8 -*-
"""
Automated Integration Tests for K8-Quant Web System
验证后端 API 契约、数据解析、热力图计算与前端静态资源可用性
"""
import os
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi.testclient import TestClient
from backend.api.api_server import app
from backend.api.data_service import QuantDataService

class TestK8QuantWebSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.service = QuantDataService(PROJ_DIR)

    def test_01_system_status(self):
        """测试系统状态接口"""
        response = self.client.get("/api/system/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ONLINE")
        self.assertIn("latest_draw_period", data)
        self.assertIn("target_period", data)
        print(f"[PASS] 01_system_status: Latest {data['latest_draw_period']}, Target {data['target_period']}")

    def test_02_latest_prediction(self):
        """测试最新量化预测数据接口"""
        response = self.client.get("/api/quant/latest-prediction")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("top5_gold", data)
        self.assertIn("top12_pool", data)
        self.assertIn("golden_pair", data)
        self.assertIn("weights", data)
        self.assertEqual(len(data["golden_pair"]), 2)
        print(f"[PASS] 02_latest_prediction: Top5 {data['top5_gold']}, GoldenPair {data['golden_pair']}")

    def test_03_matrix_80_stats(self):
        """测试 80 码全景态势数据接口"""
        response = self.client.get("/api/quant/matrix-80")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_count"], 80)
        self.assertEqual(len(data["matrix"]), 80)
        self.assertEqual(len(data["tail_stats"]), 10)
        self.assertEqual(len(data["zone_stats"]), 4)
        first_cell = data["matrix"][0]
        self.assertEqual(first_cell["number"], 1)
        self.assertIn("energy", first_cell)
        self.assertIn("omission", first_cell)
        print(f"[PASS] 03_matrix_80_stats: 80-Cells Total {len(data['matrix'])}, Tails {len(data['tail_stats'])}")

    def test_04_number_detail(self):
        """测试单个号码穿透分析"""
        response = self.client.get("/api/quant/number/45")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["number"], 45)
        self.assertIn("appearances_30", data)
        self.assertIn("top_buddies", data)
        print(f"[PASS] 04_number_detail: Ball 45 hits {data['total_hits_30']}/30, TopBuddies len {len(data['top_buddies'])}")

    def test_05_history_trends(self):
        """测试 30 期命中率走势曲线数据"""
        response = self.client.get("/api/quant/history-trends?limit=25")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("periods", data)
        self.assertIn("top5_hits", data)
        self.assertIn("top12_hits", data)
        self.assertTrue(len(data["periods"]) > 0)
        print(f"[PASS] 05_history_trends: Loaded {len(data['periods'])} periods, AvgTop5 {data['avg_top5_hit']}")

    def test_06_reports_endpoints(self):
        """测试研判报告列表与详情接口"""
        res_list = self.client.get("/api/reports/list")
        self.assertEqual(res_list.status_code, 200)
        reports = res_list.json()
        self.assertTrue(len(reports) > 0)
        
        # 获取第一篇报告详情
        first_rep = reports[0]
        res_detail = self.client.get(f"/api/reports/detail/{first_rep['raw_date']}")
        self.assertEqual(res_detail.status_code, 200)
        detail_data = res_detail.json()
        self.assertIn("content", detail_data)
        self.assertTrue(len(detail_data["content"]) > 100)
        print(f"[PASS] 06_reports_endpoints: {len(reports)} reports, Latest {first_rep['filename']}")

    def test_07_param_config_update(self):
        """测试模型参数调优接口"""
        payload = {"EF": 0.45, "RW": 0.25, "FO": 0.30}
        res = self.client.post("/api/config/params", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        print("[PASS] 07_param_config_update: Updated and saved successfully")

    def test_08_static_web_index(self):
        """测试前端主页静态文件返回"""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"K8-QUANT", res.content)
        print("[PASS] 08_static_web_index: HTML index page served")

    def test_09_lottery_trends(self):
        """测试开奖号码走势图接口 (默认100期、升序验证、80码矩阵与汇总统计)"""
        # 1. 默认100期请求
        res = self.client.get("/api/quant/lottery-trends")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("draws", data)
        self.assertIn("ball_stats", data)
        self.assertIn("summary", data)
        self.assertEqual(len(data["draws"]), 100)
        self.assertEqual(len(data["ball_stats"]), 80)
        
        # 2. 严格按开奖日期升序排列验证 (旧 -> 新)
        draws = data["draws"]
        for i in range(len(draws) - 1):
            p1 = int(draws[i]["period"])
            p2 = int(draws[i + 1]["period"])
            self.assertLess(p1, p2, f"期号未按升序排列: {p1} >= {p2}")
            d1 = draws[i]["date"]
            d2 = draws[i + 1]["date"]
            self.assertLessEqual(d1, d2, f"日期未按升序排列: {d1} > {d2}")
            
        # 3. 每期 80 码遗漏数组长度与数值验证
        first_draw = draws[0]
        self.assertEqual(len(first_draw["omissions"]), 80)
        self.assertEqual(len(first_draw["numbers"]), 20)
        for num in first_draw["numbers"]:
            self.assertEqual(first_draw["omissions"][num - 1], 0)
            
        # 4. 自定义期数 (例如 30 期, 200 期)
        res_30 = self.client.get("/api/quant/lottery-trends?limit=30")
        self.assertEqual(res_30.status_code, 200)
        self.assertEqual(len(res_30.json()["draws"]), 30)
        
        summary_range = f"{data['summary']['start_period']}->{data['summary']['end_period']}"
        print(f"[PASS] 09_lottery_trends: 100 periods loaded in ascending order ({summary_range}), 80-ball stats validated")

    def test_10_follow_endpoints(self):
        """测试跟随分析 (重复号追踪与多窗条件跟随) 相关 API 接口"""
        # 1. /api/follow/summary
        res_sum = self.client.get("/api/follow/summary")
        self.assertEqual(res_sum.status_code, 200)
        data_sum = res_sum.json()
        self.assertEqual(data_sum["status"], "ok")
        self.assertIn("target_period", data_sum)
        self.assertIn("rep_lift", data_sum)
        self.assertIn("picks", data_sum)
        self.assertEqual(len(data_sum["picks"]["repeat"]["top5"]), 5)
        self.assertEqual(len(data_sum["picks"]["inference"]["top6"]), 6)
        self.assertEqual(len(data_sum["picks"]["conditional"]["top8"]), 8)

        # 2. /api/follow/review
        res_rev = self.client.get("/api/follow/review?n=20")
        self.assertEqual(res_rev.status_code, 200)
        data_rev = res_rev.json()
        self.assertEqual(data_rev["status"], "ok")
        self.assertEqual(len(data_rev["rows"]), 20)
        self.assertIn("rep_lift", data_rev)
        self.assertIn("confidence", data_rev)

        # 3. /api/follow/conditions
        res_cond = self.client.get("/api/follow/conditions")
        self.assertEqual(res_cond.status_code, 200)
        data_cond = res_cond.json()
        self.assertEqual(data_cond["status"], "ok")
        self.assertIn("cond_info", data_cond)
        self.assertEqual(len(data_cond["cond_info"]), 5)
        print("[PASS] 10_follow_endpoints: summary, review, and conditions APIs validated")

    def test_11_sixteen_endpoints(self):
        """测试 16 期中热号频次动态推演与组合决策相关 API 接口"""
        # 1. /api/sixteen/summary
        res_sum = self.client.get("/api/sixteen/summary")
        self.assertEqual(res_sum.status_code, 200)
        data_sum = res_sum.json()
        self.assertIn("target_period", data_sum)
        self.assertIn("gold_dan", data_sum)
        self.assertIn("medium_top5", data_sum)
        self.assertEqual(len(data_sum["medium_top5"]), 5)
        self.assertIn("top5_pairs", data_sum)
        self.assertEqual(len(data_sum["top5_pairs"]), 5)
        self.assertIn("distribution_counts", data_sum)
        self.assertIn("matrix_80", data_sum)
        self.assertEqual(len(data_sum["matrix_80"]), 80)

        # 2. /api/sixteen/review
        res_rev = self.client.get("/api/sixteen/review?n=15")
        self.assertEqual(res_rev.status_code, 200)
        data_rev = res_rev.json()
        self.assertIn("stats", data_rev)
        self.assertEqual(data_rev["stats"]["n_periods"], 15)
        self.assertIn("rows", data_rev)
        self.assertEqual(len(data_rev["rows"]), 15)

        # 3. /api/sixteen/history
        res_hist = self.client.get("/api/sixteen/history")
        self.assertEqual(res_hist.status_code, 200)
        data_hist = res_hist.json()
        self.assertIsInstance(data_hist, list)
        self.assertGreater(len(data_hist), 0)

        # 4. /api/sixteen/history-detail/{filename}
        detail_name = data_hist[0]["filename"]
        res_detail = self.client.get(f"/api/sixteen/history-detail/{detail_name}")
        self.assertEqual(res_detail.status_code, 200)
        data_detail = res_detail.json()
        self.assertIn("content", data_detail)
        self.assertGreater(len(data_detail["content"]), 0)
        print("[PASS] 11_sixteen_endpoints: summary, review, history, and detail APIs validated")

    def test_12_pipeline_run_follow(self):
        """测试 follow pipeline 运行接口"""
        res_run = self.client.post("/api/pipeline/run-follow")
        self.assertEqual(res_run.status_code, 200)
        data_run = res_run.json()
        self.assertIn("task_id", data_run)
        self.assertEqual(data_run["status"], "QUEUED")
        print(f"[PASS] 12_pipeline_run_follow: task created {data_run['task_id']}")

    def test_13_pipeline_run_sixteen(self):
        """测试 sixteen pipeline 运行接口"""
        res_run = self.client.post("/api/pipeline/run-sixteen")
        self.assertEqual(res_run.status_code, 200)
        data_run = res_run.json()
        self.assertIn("task_id", data_run)
        self.assertEqual(data_run["status"], "QUEUED")
        print(f"[PASS] 13_pipeline_run_sixteen: task created {data_run['task_id']}")

if __name__ == "__main__":
    unittest.main()


