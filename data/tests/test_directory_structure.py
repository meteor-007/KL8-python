# -*- coding: utf-8 -*-
"""
Directory Architecture & Integration Test Suite
验证重构后的 Frontend / Backend 目录体系、功能模块完整性与路径解析
"""
import os
import sys
import unittest
import importlib

DATA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DATA_ROOT not in sys.path:
    sys.path.insert(0, DATA_ROOT)
backend_dir = os.path.join(DATA_ROOT, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.utils.paths import (
    get_project_root,
    get_backend_dir,
    get_frontend_dir,
    get_storage_dir,
    get_config_dir,
    data_path
)


class TestDirectoryArchitecture(unittest.TestCase):
    
    def test_01_paths_resolution(self):
        """验证统一路径中枢解析准确性"""
        root = get_project_root()
        self.assertTrue(os.path.isdir(root))
        self.assertEqual(os.path.normpath(root), os.path.normpath(DATA_ROOT))
        
        b_dir = get_backend_dir()
        self.assertTrue(os.path.isdir(b_dir))
        self.assertEqual(os.path.normpath(b_dir), os.path.normpath(os.path.join(DATA_ROOT, 'backend')))
        
        f_dir = get_frontend_dir()
        self.assertTrue(os.path.isdir(f_dir))
        self.assertEqual(os.path.normpath(f_dir), os.path.normpath(os.path.join(DATA_ROOT, 'frontend')))
        
        s_dir = get_storage_dir()
        self.assertTrue(os.path.isdir(s_dir))
        self.assertIn(os.path.normpath(s_dir), [
            os.path.normpath(os.path.join(DATA_ROOT, 'storage')),
            os.path.normpath(os.path.join(DATA_ROOT, 'archive', 'storage_legacy'))
        ])
        
        # 验证核心数据文件智能寻址
        hist_path = data_path('kl8_history_final.txt')
        self.assertTrue(os.path.exists(hist_path))
        print(f"[PASS] 01_paths_resolution: Root={root}, History={hist_path}")

    def test_02_frontend_assets_integrity(self):
        """验证前端静态资产完整性"""
        f_dir = get_frontend_dir()
        static_dir = os.path.join(f_dir, 'static')
        self.assertTrue(os.path.exists(os.path.join(static_dir, 'index.html')))
        self.assertTrue(os.path.exists(os.path.join(static_dir, 'css', 'cyber_theme.css')))
        self.assertTrue(os.path.exists(os.path.join(static_dir, 'js', 'app.js')))
        self.assertTrue(os.path.isdir(os.path.join(f_dir, 'canvases')))
        print("[PASS] 02_frontend_assets_integrity: HTML/CSS/JS/Canvases verified")

    def test_03_backend_modules_structure(self):
        """验证后端所有功能模块目录与 __init__.py 存在性"""
        b_dir = get_backend_dir()
        expected_modules = [
            'api',
            'core',
            'data_acquisition',
            'pipeline',
            'audit',
            'learning',
            'recognition',
            'format',
            'config',
            'utils'
        ]
        for mod in expected_modules:
            mod_path = os.path.join(b_dir, mod)
            self.assertTrue(os.path.isdir(mod_path), f"Missing backend module directory: {mod}")
            self.assertTrue(os.path.exists(os.path.join(mod_path, '__init__.py')), f"Missing __init__.py in: {mod}")
        print(f"[PASS] 03_backend_modules_structure: {len(expected_modules)} backend packages verified")

    def test_04_backend_imports(self):
        """验证后端核心模块可无缝 import 并正常初始化"""
        modules_to_test = [
            'backend.api.api_server',
            'backend.api.data_service',
            'backend.core.energy_field',
            'backend.core.feature_optimizer',
            'backend.core.pure_pool_scorer',
            'backend.core.pair_selector',
            'backend.core.score_composer',
            'backend.core.algorithm_optimizer',
            'backend.core.deep_mining_engine',
            'backend.data_acquisition.fetch_kl8_history',
            'backend.data_acquisition.generate_hot_excel',
            'backend.data_acquisition.process_hot_numbers',
            'backend.pipeline.auto_generate_daily_report',
            'backend.pipeline.run_full_pipeline',
            'backend.audit.v3_trinity_audit',
            'backend.audit.matrix_detailed_audit',
            'backend.learning.autonomous_learner',
            'backend.learning.paper_trading',
            'backend.recognition.simplified_env_recognition',
            'backend.format.apply_formats',
            'backend.config.config_loader',
            'backend.utils.paths',
            'backend.utils.data_validator',
        ]
        for m in modules_to_test:
            mod = importlib.import_module(m)
            self.assertIsNotNone(mod, f"Failed to import: {m}")
        print(f"[PASS] 04_backend_imports: {len(modules_to_test)} key modules imported successfully")

    def test_05_storage_structure(self):
        """验证持久化数据中心目录结构"""
        s_dir = get_storage_dir()
        expected_storage = [
            'raw',
            'reports',
            'reviews',
            'cache',
            'chaos_tensors',
            'logs',
            'backup',
            'archive',
            'scratch'
        ]
        for sub in expected_storage:
            sub_path = os.path.join(s_dir, sub)
            self.assertTrue(os.path.isdir(sub_path), f"Missing storage directory: {sub}")
        print(f"[PASS] 05_storage_structure: {len(expected_storage)} storage directories verified")


if __name__ == '__main__':
    unittest.main()
