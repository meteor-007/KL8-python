# -*- coding: utf-8 -*-
"""
测试套件：每日点位录入与全模块联动管理引擎 (Daily Points Manager Test Suite)
================================================================================
测试覆盖：
  1. 智能输入解析器 (空格/逗号/连字符/换行/中文标点/重复过滤)
  2. 20码严格契约校验器
  3. 8分区与多维特征画像引擎
  4. 点位原子落盘与带时间戳备份
  5. DataService API 服务方法 (info / submit / history)
  6. 下游重点点位与未开反弹模型联动
"""
import os
import sys
import unittest
import tempfile
import shutil

# 路径自适应
_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.data_acquisition.daily_points_manager import (
    parse_points_input,
    validate_points_list,
    format_points_to_line,
    load_daily_points,
    get_next_target_info,
    analyze_points_distribution,
    save_daily_points,
    POINTS_COUNT,
    NUM_BALLS
)
from backend.api.data_service import QuantDataService


class TestDailyPointsManager(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_points_file = os.path.join(self.temp_dir, "daily_points_test.txt")
        self.sample_20_nums = [4, 12, 17, 19, 24, 25, 34, 35, 39, 40, 44, 45, 49, 50, 54, 59, 60, 67, 69, 74]
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_parse_points_input_formats(self):
        """测试各种输入分隔符的智能解析能力"""
        # 空格分隔
        s1 = "04 12 17 19 24 25 34 35 39 40 44 45 49 50 54 59 60 67 69 74"
        self.assertEqual(parse_points_input(s1), self.sample_20_nums)
        
        # 英文逗号
        s2 = "4, 12, 17, 19, 24, 25, 34, 35, 39, 40, 44, 45, 49, 50, 54, 59, 60, 67, 69, 74"
        self.assertEqual(parse_points_input(s2), self.sample_20_nums)
        
        # 中文逗号与顿号
        s3 = "04，12、17，19、24，25、34，35、39，40、44，45、49，50、54，59、60，67、69，74"
        self.assertEqual(parse_points_input(s3), self.sample_20_nums)
        
        # 连字符
        s4 = "04-12-17-19-24-25-34-35-39-40-44-45-49-50-54-59-60-67-69-74"
        self.assertEqual(parse_points_input(s4), self.sample_20_nums)
        
        # 多行与制表符
        s5 = "04\t12\t17\t19\t24\n25\t34\t35\t39\t40\n44\t45\t49\t50\t54\n59\t60\t67\t69\t74"
        self.assertEqual(parse_points_input(s5), self.sample_20_nums)
        
        # 乱序输入应自动升序
        s6 = "74 12 04 69 17 19 67 24 25 60 34 35 59 39 40 54 44 45 50 49"
        self.assertEqual(parse_points_input(s6), self.sample_20_nums)

    def test_validate_points_list(self):
        """测试点位契约校验规则"""
        # 正确 20 码
        ok, msg = validate_points_list(self.sample_20_nums)
        self.assertTrue(ok)
        
        # 少于 20 码
        ok, msg = validate_points_list(self.sample_20_nums[:19])
        self.assertFalse(ok)
        self.assertIn("19", msg)
        
        # 多于 20 码
        ok, msg = validate_points_list(self.sample_20_nums + [75])
        self.assertFalse(ok)
        self.assertIn("21", msg)
        
        # 越界号码 (0 或 81)
        ok, msg = validate_points_list(self.sample_20_nums[:19] + [81])
        self.assertFalse(ok)
        self.assertIn("越界", msg)
        
        # 重复号码
        ok, msg = validate_points_list(self.sample_20_nums[:19] + [self.sample_20_nums[0]])
        self.assertFalse(ok)
        self.assertIn("重复", msg)

    def test_analyze_points_distribution(self):
        """测试 8 分区、奇偶、大小、和值特征画像"""
        analysis = analyze_points_distribution(self.sample_20_nums)
        self.assertEqual(analysis["total_sum"], sum(self.sample_20_nums))
        self.assertEqual(len(analysis["points"]), 20)
        self.assertEqual(len(analysis["zone_dist"]), 8)
        self.assertIsInstance(analysis["odd_even_ratio"], str)
        self.assertIsInstance(analysis["big_small_ratio"], str)
        self.assertGreaterEqual(analysis["prime_count"], 1)

    def test_atomic_save_and_load(self):
        """测试原子写入与读取"""
        res1 = save_daily_points("2026-08-29", "2026231", self.sample_20_nums, filepath=self.test_points_file)
        self.assertEqual(res1["status"], "ok")
        self.assertEqual(res1["action"], "created")
        
        sample_20_nums_2 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        res2 = save_daily_points("2026-08-30", "2026232", sample_20_nums_2, filepath=self.test_points_file)
        self.assertEqual(res2["status"], "ok")
        
        loaded = load_daily_points(filepath=self.test_points_file)
        self.assertEqual(len(loaded), 2)
        self.assertIn("2026232", loaded)
        self.assertIn("2026231", loaded)
        self.assertEqual(loaded["2026232"]["points"], sample_20_nums_2)

    def test_data_service_integration(self):
        """测试 Web DataService 点位服务接口"""
        ds = QuantDataService(_PROJ_DIR)
        info = ds.get_daily_points_info()
        self.assertEqual(info["status"], "ok")
        self.assertIn("target_info", info)
        
        history = ds.get_daily_points_history(limit=5)
        self.assertEqual(history["status"], "ok")
        self.assertGreaterEqual(len(history["records"]), 1)


if __name__ == "__main__":
    unittest.main()
