# -*- coding: utf-8 -*-
"""
路径工具模块：统一解析项目根目录与数据文件路径，
避免子目录中 __file__ 引用指向错误位置。
"""
import os
import sys

_PROJECT_ROOT_CACHE = None


def _ensure_project_path():
    """确保项目根目录在sys.path中，避免导入错误。
    
    替代各文件中重复的:
        _PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _PROJ not in sys.path:
            sys.path.insert(0, _PROJ)
    
    使用方式:
        from utils.paths import _ensure_project_path
        _ensure_project_path()
    """
    root = get_project_root()
    if root not in sys.path:
        sys.path.insert(0, root)


def get_project_root():
    """获取项目根目录 (data/ 目录)"""
    global _PROJECT_ROOT_CACHE
    if _PROJECT_ROOT_CACHE is not None:
        return _PROJECT_ROOT_CACHE
    # 当前文件在 data/utils/paths.py, 上溯1层到 data/
    _PROJECT_ROOT_CACHE = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    return _PROJECT_ROOT_CACHE

def data_path(*subpaths):
    """拼接数据文件路径 (相对于 data/ 根目录)

    Usage:
        data_path('kl8_history_final.txt')
        data_path('热码统计', '20260512-2026122期-热码统计.xlsx')
    """
    return os.path.join(get_project_root(), *subpaths)

def script_path(module_name):
    """拼接同级目录下脚本路径

    Usage:
        script_path('process_hot_numbers.py')
    """
    caller_dir = os.path.dirname(os.path.abspath(
        __import__('sys')._getframe(1).f_globals.get('__file__', __file__)
    ))
    # 如果是子目录，往根目录查
    parent = os.path.dirname(caller_dir)
    for candidate in (os.path.join(caller_dir, module_name),
                      os.path.join(parent, module_name)):
        if os.path.exists(candidate):
            return candidate
    return os.path.join(caller_dir, module_name)

if __name__ == '__main__':
    print(f"Project root: {get_project_root()}")
    print(f"History file: {data_path('kl8_history_final.txt')}")
