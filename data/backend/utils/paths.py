# -*- coding: utf-8 -*-
"""
路径中枢工具模块 (Unified Paths Resolver)
统一解析系统根目录、后端模块、前端静态资源与持久化数据存储路径。
自动向上回溯定位项目根目录，避免子目录中 __file__ 引用指向错误位置。
"""
import os
import sys

_PROJECT_ROOT_CACHE = None


def get_project_root():
    """获取项目根目录 (即 data/ 目录)"""
    global _PROJECT_ROOT_CACHE
    if _PROJECT_ROOT_CACHE is not None:
        return _PROJECT_ROOT_CACHE

    curr = os.path.dirname(os.path.abspath(__file__))
    # 向上寻找包含 'backend', 'frontend', 或 'GEMINI.md' 的目录作为根目录
    for _ in range(5):
        if os.path.exists(os.path.join(curr, 'backend')) or \
           os.path.exists(os.path.join(curr, 'frontend')) or \
           os.path.exists(os.path.join(curr, 'GEMINI.md')):
            _PROJECT_ROOT_CACHE = curr
            return _PROJECT_ROOT_CACHE
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent

    # 兜底：如果是 backend/utils/paths.py，上溯2层；如果是 utils/paths.py，上溯1层
    file_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(os.path.dirname(file_dir)) == 'backend':
        _PROJECT_ROOT_CACHE = os.path.dirname(os.path.dirname(file_dir))
    else:
        _PROJECT_ROOT_CACHE = os.path.dirname(file_dir)
    return _PROJECT_ROOT_CACHE


def get_backend_dir():
    """获取后端模块根目录 (data/backend/)"""
    return os.path.join(get_project_root(), "backend")


def get_frontend_dir():
    """获取前端模块根目录 (data/frontend/)"""
    return os.path.join(get_project_root(), "frontend")


def get_storage_dir():
    """获取数据持久化存储根目录 (data/archive/storage_legacy/ 或 data/storage/)"""
    root = get_project_root()
    legacy = os.path.join(root, "archive", "storage_legacy")
    if os.path.exists(legacy):
        return legacy
    return os.path.join(root, "storage")


def get_config_dir():
    """获取配置模块根目录 (data/backend/config/ 或 data/config/)"""
    backend_cfg = os.path.join(get_backend_dir(), "config")
    if os.path.exists(backend_cfg):
        return backend_cfg
    return os.path.join(get_project_root(), "config")


def _ensure_project_path():
    """确保项目根目录与 backend 目录在 sys.path 中，避免导入错误。"""
    root = get_project_root()
    backend_dir = get_backend_dir()
    for p in [root, backend_dir]:
        if p not in sys.path:
            sys.path.insert(0, p)


def data_path(*subpaths):
    """
    智能解析数据文件路径：
    优先顺序：
    1. 相对于 data/ 根目录 (如 root/kl8_history_final.txt)
    2. 兼容 '热码统计' 映射到 archive/historical_stats
    3. 兼容 'backup' 映射到 archive/backup
    4. 兼容 'scratch' 映射到 archive/scratch
    5. 相对于 data/archive/ 目录
    6. 相对于 data/storage/ 或 data/archive/storage_legacy/
    7. 相对于 backend/config/ 目录
    8. 兜底返回相对于根目录的标准路径
    """
    root = get_project_root()
    direct_path = os.path.join(root, *subpaths)
    if os.path.exists(direct_path):
        return direct_path

    # 兼容历史热码统计目录映射到 archive/historical_stats
    if subpaths and subpaths[0] in ('热码统计', 'historical_stats'):
        hist_stats = os.path.join(root, "archive", "historical_stats", *subpaths[1:])
        if os.path.exists(hist_stats):
            return hist_stats

    # 兼容历史 backup 映射到 archive/backup
    if subpaths and subpaths[0] == 'backup':
        backup_p = os.path.join(root, "archive", "backup", *subpaths[1:])
        if os.path.exists(backup_p):
            return backup_p

    # 兼容历史 scratch 映射到 archive/scratch
    if subpaths and subpaths[0] == 'scratch':
        scratch_p = os.path.join(root, "archive", "scratch", *subpaths[1:])
        if os.path.exists(scratch_p):
            return scratch_p

    # 尝试 archive 相对路径
    archive_path = os.path.join(root, "archive", *subpaths)
    if os.path.exists(archive_path):
        return archive_path

    # 尝试 storage / storage_legacy 相对路径
    storage_path = os.path.join(get_storage_dir(), *subpaths)
    if os.path.exists(storage_path):
        return storage_path

    # 尝试 storage/raw
    storage_raw_path = os.path.join(get_storage_dir(), "raw", *subpaths)
    if os.path.exists(storage_raw_path):
        return storage_raw_path

    # 尝试 storage/reports
    storage_rep_path = os.path.join(get_storage_dir(), "reports", *subpaths)
    if os.path.exists(storage_rep_path):
        return storage_rep_path

    # 尝试 backend/config
    cfg_path = os.path.join(get_config_dir(), *subpaths)
    if os.path.exists(cfg_path):
        return cfg_path

    # 如果是寻找热码统计但尚未创建，默认指向 archive/historical_stats
    if subpaths and subpaths[0] in ('热码统计', 'historical_stats'):
        return os.path.join(root, 'archive', 'historical_stats', *subpaths[1:])

    # 兜底返回根目录路径 (便于新建文件时写入)
    return direct_path


def script_path(module_name):
    """拼接同级或 backend 目录下脚本路径"""
    caller_dir = os.path.dirname(os.path.abspath(
        __import__('sys')._getframe(1).f_globals.get('__file__', __file__)
    ))
    candidates = [
        os.path.join(caller_dir, module_name),
        os.path.join(os.path.dirname(caller_dir), module_name),
        os.path.join(get_backend_dir(), module_name),
        os.path.join(get_project_root(), module_name),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return os.path.join(caller_dir, module_name)


# 模块导入时自动确保 sys.path 包含根目录与 backend 目录
_ensure_project_path()

if __name__ == '__main__':
    print(f"Project root : {get_project_root()}")
    print(f"Backend dir  : {get_backend_dir()}")
    print(f"Frontend dir : {get_frontend_dir()}")
    print(f"Storage dir  : {get_storage_dir()}")
    print(f"History file : {data_path('kl8_history_final.txt')}")
