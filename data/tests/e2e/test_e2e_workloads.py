# -*- coding: utf-8 -*-
"""
test_e2e_workloads.py — Tier 4: 全流程端到端业务工作流测试 (Production Workloads & End-to-End Pipelines)
=======================================================================================================
【测试目标 (大白话)】：
  以真实黑盒方式调用 CLI 生产脚本（主脑独立解算、自进化独立迭代、夜间全自动流水线）、
  校验物理资产落地（JSON/MD 决策单据与账本）、并通过 FastAPI TestClient 检验 Web 驾驶舱端到端契约。
"""
from backend.utils.paths import get_outputs_dir
import os
import sys
import glob
import json
import unittest
import subprocess
from fastapi.testclient import TestClient

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)
BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.api.api_server import app


class TestTier4ProductionWorkloads(unittest.TestCase):
    """CLI 生产脚本黑盒执行与物理 I/O 资产落盘检验 (大白话：真刀真枪跑脚本，看文件是否成功生成)"""

    def _run_script(self, script_rel_path: str, args: list = None, timeout: int = 120) -> subprocess.CompletedProcess:
        """执行脚本辅助函数"""
        from backend.utils.paths import find_module_script
        try:
            script_full_path = find_module_script(script_rel_path)
            if not os.path.exists(script_full_path):
                script_full_path = os.path.join(PROJ_DIR, script_rel_path)
        except Exception:
            script_full_path = os.path.join(PROJ_DIR, script_rel_path)
        cmd = [sys.executable, script_full_path] + (args or [])
        res = subprocess.run(
            cmd,
            cwd=PROJ_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )
        return res

    def test_01_run_unified_brain_daily_workload(self):
        """E2E-01: 统一决策主脑 CLI 独立执行脚本 (run_unified_brain_daily.py) 生产负载与资产检验"""
        res = self._run_script("run_unified_brain_daily.py")
        self.assertEqual(res.returncode, 0, f"run_unified_brain_daily 执行失败: {res.stderr}\n{res.stdout}")
        self.assertIn("快乐8 全栈统一决策主脑", res.stdout)
        self.assertIn("尖刀核心金胆", res.stdout)
        self.assertIn("黄金搭档", res.stdout)
        self.assertIn("最优 3 码", res.stdout)

        # 物理检查 JSON 与 Markdown 资产落盘
        json_files = glob.glob(os.path.join(PROJ_DIR, "backend", "outputs", "unified_brain", "unified_decision_*.json")) + \
                     glob.glob(os.path.join(get_outputs_dir(), "unified_brain", "unified_decision_*.json"))
        md_files = glob.glob(os.path.join(PROJ_DIR, "backend", "outputs", "unified_brain", "unified_decision_report_*.md")) + \
                   glob.glob(os.path.join(get_outputs_dir(), "unified_brain", "unified_decision_report_*.md"))

        self.assertGreater(len(json_files), 0, "必须成功生成 unified_decision_*.json")
        self.assertGreater(len(md_files), 0, "必须成功生成 unified_decision_report_*.md")

        latest_json = sorted(json_files)[-1]
        with open(latest_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("target_period", data)
        self.assertIn("gold_single", data)
        self.assertIn("gold_pair", data)
        self.assertIn("top3_gold", data)
        self.assertIn("top5", data)
        self.assertIn("top12_balanced", data)
        self.assertEqual(len(data["top3_gold"]), 3)
        self.assertEqual(len(data["top5"]), 5)
        self.assertEqual(len(data["top12_balanced"]), 12)
        self.assertIn("probabilities", data)

    def test_02_run_evolution_daily_workload(self):
        """E2E-02: 自进化反向校准 CLI 执行脚本 (run_evolution_daily.py) 生产负载与账本检验"""
        res = self._run_script("run_evolution_daily.py", ["5"], timeout=120)
        self.assertEqual(res.returncode, 0, f"run_evolution_daily 执行失败: {res.stderr}\n{res.stdout}")
        self.assertIn("统一主脑物理参数反向校准完成", res.stdout)
        self.assertIn("Focal Loss 残差损失", res.stdout)

        # 物理检查自进化总账本
        ledger_file = os.path.join(PROJ_DIR, "storage", "evolution", "unified_evolution_ledger.json")
        self.assertTrue(os.path.exists(ledger_file), f"进化总账本不存在: {ledger_file}")

        with open(ledger_file, "r", encoding="utf-8") as f:
            ledger = json.load(f)
        self.assertIsInstance(ledger, list)
        self.assertGreater(len(ledger), 0, "进化总账本记录必须非空")
        latest_entry = ledger[-1]
        self.assertIn("generation", latest_entry)
        self.assertIn("focal_loss", latest_entry)
        self.assertIn("sigma", latest_entry)
        self.assertIn("lambda_decay", latest_entry)


class TestTier4WebAPIAndCockpitContracts(unittest.TestCase):
    """FastAPI Web 路由与前端驾驶舱数据契约端到端检验 (大白话：大屏取数据，字段全不全，图表能不能画出来)"""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_api_unified_brain_end_to_end(self):
        """E2E-03: /api/quant/unified-brain 端到端黑盒请求与数据契约校验"""
        response = self.client.get("/api/quant/unified-brain")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "ok")
        payload = body.get("data", {})

        # 必须满足前端驾驶舱四级卡片与热力图渲染所需的所有契约字段
        self.assertIn("gold_single", payload)
        self.assertIn("gold_pair", payload)
        self.assertIn("top3_gold", payload)
        self.assertIn("top5", payload)
        self.assertIn("top12_balanced", payload)
        self.assertEqual(len(payload.get("top3_gold") or []), 3)
        self.assertEqual(len(payload["top5"]), 5)
        self.assertEqual(len(payload["top12_balanced"]), 12)
        self.assertIn("killed_numbers", payload)
        self.assertIn("probabilities", payload)

        probs = payload["probabilities"]
        self.assertEqual(len(probs), 80, "热力图需要 80 个号码的完整概率分布")
        prob_vals = [float(x) for x in probs.values()]
        self.assertAlmostEqual(sum(prob_vals), 1.0, places=3)

    def test_02_api_evolution_status_end_to_end(self):
        """E2E-04: /api/evolution/status 端到端自进化状态查询契约校验"""
        response = self.client.get("/api/evolution/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "ok")

    def test_03_api_system_status_and_health(self):
        """E2E-05: /api/system/status 系统运行状态与健康度契约校验"""
        response = self.client.get("/api/system/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "ONLINE")
        self.assertIn("system_name", body)
        self.assertIn("target_period", body)


if __name__ == "__main__":
    unittest.main()
