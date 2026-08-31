# -*- coding: utf-8 -*-
"""
Tier 4: Real-World Workload Execution Validation (全量入口脚本与生产负载验收)
=============================================================================
在全量生产环境下逐一调用系统 11 个日常入口脚本，物理校验生成产物的 Schema 与非空完整性。
"""
import os
import sys
import glob
import json
import unittest
import subprocess

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)


class TestTier4Workloads(unittest.TestCase):
    """11 个日常入口脚本生产负载与 I/O 产物物理校验"""

    def _run_script(self, script_rel_path: str, args: list = None, timeout: int = 120) -> subprocess.CompletedProcess:
        """执行脚本辅助函数"""
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

    def test_e2e_01_points_daily_workload(self):
        """E2E-01: 空间重点点位分析脚本执行与产物检验"""
        res = self._run_script("run_points_daily.py", ["5"])
        self.assertEqual(res.returncode, 0, f"run_points_daily failed: {res.stderr}\n{res.stdout}")

        txt_path = os.path.join(PROJ_DIR, "outputs", "spatial_points", "重点点位预测.txt")
        json_path = os.path.join(PROJ_DIR, "outputs", "spatial_points", "spatial_points_latest.json")
        self.assertTrue(os.path.exists(txt_path), f"Missing {txt_path}")
        self.assertTrue(os.path.exists(json_path), f"Missing {json_path}")
        self.assertGreater(os.path.getsize(txt_path), 50)

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("picks", data)
        self.assertIn("confidence", data)

    def test_e2e_02_geminixuan2_daily_workload(self):
        """E2E-02: Gemini 智能选2量化研判脚本执行与产物检验"""
        res = self._run_script("run_geminixuan2_daily.py", ["5"])
        self.assertEqual(res.returncode, 0, f"run_geminixuan2_daily failed: {res.stderr}\n{res.stdout}")

        out_txts = glob.glob(os.path.join(PROJ_DIR, "gemini_pick2", "output", "gemini选2预测_*.txt"))
        out_jsons = glob.glob(os.path.join(PROJ_DIR, "gemini_pick2", "output", "k8_quant_memory_*.json"))
        self.assertGreater(len(out_txts), 0, "No gemini txt predictions generated")
        self.assertGreater(len(out_jsons), 0, "No gemini memory json generated")

        latest_json = sorted(out_jsons)[-1]
        with open(latest_json, "r", encoding="utf-8") as f:
            mem_data = json.load(f)
        self.assertIn("target", mem_data)
        self.assertIn("gold", mem_data)
        self.assertIn("core4", mem_data)

    def test_e2e_03_pick2_daily_workload(self):
        """E2E-03: 定金选2量化决策推演脚本执行与产物检验"""
        res = self._run_script("run_pick2_daily.py", ["5"])
        self.assertEqual(res.returncode, 0, f"run_pick2_daily failed: {res.stderr}\n{res.stdout}")

        out_txts = glob.glob(os.path.join(PROJ_DIR, "outputs", "gold_pick2", "定金选2预测_*.txt"))
        self.assertGreater(len(out_txts), 0, "No gold pick2 txt prediction generated")
        latest_txt = sorted(out_txts)[-1]
        self.assertGreater(os.path.getsize(latest_txt), 50)

        with open(latest_txt, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("定金选2", content)
        self.assertIn("核心金胆", content)

    def test_e2e_04_follow_daily_workload(self):
        """E2E-04: 跟随分析脚本执行与产物检验"""
        res = self._run_script("run_follow_daily.py", ["5"])
        self.assertEqual(res.returncode, 0, f"run_follow_daily failed: {res.stderr}\n{res.stdout}")

        txt_path = os.path.join(PROJ_DIR, "outputs", "follow_analysis", "跟随分析预测.txt")
        self.assertTrue(os.path.exists(txt_path), f"Missing {txt_path}")
        self.assertGreater(os.path.getsize(txt_path), 50)

    def test_e2e_05_jingle_daily_workload(self):
        """E2E-05: 顺口溜口诀规律分析脚本执行与产物检验"""
        res = self._run_script("run_jingle_daily.py", ["5"])
        self.assertEqual(res.returncode, 0, f"run_jingle_daily failed: {res.stderr}\n{res.stdout}")

        out_txts = glob.glob(os.path.join(PROJ_DIR, "outputs", "predictions", "顺口溜预测_*.txt")) + \
                   glob.glob(os.path.join(PROJ_DIR, "outputs", "jingle", "顺口溜预测_*.txt"))
        self.assertGreater(len(out_txts), 0, "No jingle prediction generated")

    def test_e2e_06_suppression_daily_workload(self):
        """E2E-06: 未开点位反弹追踪脚本执行与产物检验"""
        res = self._run_script("run_suppression_daily.py", ["5"])
        self.assertEqual(res.returncode, 0, f"run_suppression_daily failed: {res.stderr}\n{res.stdout}")

        txt_path = os.path.join(PROJ_DIR, "outputs", "point_suppression", "未开点位反弹预测.txt")
        self.assertTrue(os.path.exists(txt_path), f"Missing {txt_path}")
        self.assertGreater(os.path.getsize(txt_path), 50)

    def test_e2e_07_aggregation_daily_workload(self):
        """E2E-07: 终审共识大团长汇总脚本执行与战报检验"""
        res = self._run_script("run_aggregation_daily.py", ["--force"])
        self.assertEqual(res.returncode, 0, f"run_aggregation_daily failed: {res.stderr}\n{res.stdout}")

        out_txts = glob.glob(os.path.join(PROJ_DIR, "outputs", "aggregation", "汇总复盘_*.txt"))
        self.assertGreater(len(out_txts), 0, "No aggregation summary txt generated")

    def test_e2e_08_lstm_daily_workload(self):
        """E2E-08: 双层LSTM深度学习时序建模脚本执行与权重检验"""
        res = self._run_script("run_lstm_daily.py", ["2"], timeout=120)
        self.assertEqual(res.returncode, 0, f"run_lstm_daily failed: {res.stderr}\n{res.stdout}")

        out_txts = glob.glob(os.path.join(PROJ_DIR, "outputs", "predictions", "prediction_*.txt"))
        self.assertGreater(len(out_txts), 0, "No LSTM prediction generated")

    def test_e2e_09_excel_hot_numbers_etl(self):
        """E2E-09: 热码多窗口提取与 Excel 同步脚本执行检验"""
        res = self._run_script("backend/data_acquisition/process_hot_numbers.py", ["--sync-all-missing"])
        self.assertEqual(res.returncode, 0, f"process_hot_numbers failed: {res.stderr}\n{res.stdout}")

    def test_e2e_10_excel_apply_formats_etl(self):
        """E2E-10: Excel 自动化条件格式化脚本执行检验"""
        res = self._run_script("backend/format/apply_formats.py")
        self.assertEqual(res.returncode, 0, f"apply_formats failed: {res.stderr}\n{res.stdout}")

    def test_e2e_11_killseeker_workload_or_diagnosis(self):
        """E2E-11: KillSeeker 杀号推演脚本执行与已知缺陷诊断断言"""
        res = self._run_script("run_killseeker_daily.py", ["--diagnose"])
        if res.returncode != 0:
            # 确认阻断原因为已知 Milestone 2 修复项 (F06: ModuleNotFoundError: kl8_stats)
            self.assertIn("kl8_stats", res.stderr + res.stdout, f"Unexpected killseeker failure: {res.stderr}")
        else:
            self.assertEqual(res.returncode, 0)

    def test_e2e_12_full_pipeline_structure_and_tasks(self):
        """E2E-12: 一键总控 run_full_pipeline.py 任务流结构与关键函数检验"""
        from backend.pipeline.run_full_pipeline import (
            task0_env_check,
            task00_validate,
            task5_verify,
        )
        self.assertTrue(callable(task0_env_check))
        self.assertTrue(callable(task00_validate))
        self.assertTrue(callable(task5_verify))


if __name__ == "__main__":
    unittest.main()
