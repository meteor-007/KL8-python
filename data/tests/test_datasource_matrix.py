# -*- coding: utf-8 -*-
"""
测试数据源1与数据源2 原始阵列服务接口 (Test DataSource Matrix Service)
"""
import os
import sys
import unittest

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.api.data_service import QuantDataService


class TestDatasourceMatrix(unittest.TestCase):
    def setUp(self):
        self.ds = QuantDataService(_PROJ_DIR)

    def test_get_datasource_matrix_latest(self):
        """测试获取最新期数据源1与数据源2矩阵"""
        res = self.ds.get_datasource_matrix_by_period()
        self.assertEqual(res.get("status"), "ok")
        self.assertTrue(bool(res.get("period")))
        self.assertTrue(len(res.get("available_periods", [])) > 0)
        
        # 验证 data1
        data1 = res.get("data1", {})
        self.assertEqual(len(data1.get("blocks", [])), 4)
        for blk in data1.get("blocks", []):
            self.assertEqual(len(blk.get("left_grid", [])), 4)
            self.assertEqual(len(blk.get("right_grid", [])), 4)

        # 验证 data2
        data2 = res.get("data2", {})
        self.assertEqual(len(data2.get("blocks", [])), 4)
        for blk in data2.get("blocks", []):
            self.assertEqual(len(blk.get("left_grid", [])), 4)
            self.assertEqual(len(blk.get("right_grid", [])), 4)

        # 验证统计
        cross = res.get("cross_stats", {})
        self.assertIn("intersection", cross)
        self.assertIn("non_d2", cross)
        print(f"✅ 最新期第 {res.get('period')} 期数据源矩阵解析通过: D1覆盖 {data1['stats']['total_count']} 码, D2覆盖 {data2['stats']['total_count']} 码, 交集 {len(cross['intersection'])} 码")

    def test_get_datasource_matrix_specific_period(self):
        """测试指定期号查询"""
        res_latest = self.ds.get_datasource_matrix_by_period()
        available = res_latest.get("available_periods", [])
        if len(available) >= 2:
            target_p = available[1]
            res_target = self.ds.get_datasource_matrix_by_period(period=target_p)
            self.assertEqual(res_target.get("status"), "ok")
            self.assertEqual(res_target.get("period"), target_p)
            print(f"✅ 历史期第 {target_p} 期数据源矩阵解析通过: 命中 {res_target['data1']['stats']['hit_count']} / {res_target['data1']['stats']['total_count']}")


if __name__ == "__main__":
    unittest.main()
