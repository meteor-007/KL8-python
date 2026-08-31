#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理残留锁文件工具 v2.0 — 使用excel_lock v3.0的智能清理"""
import os
import sys

# 确保可以import excel_lock模块
_utils_dir = os.path.dirname(os.path.abspath(__file__))
if _utils_dir not in sys.path:
    sys.path.insert(0, _utils_dir)

from excel_lock import clean_all_locks

if __name__ == '__main__':
    data_dir = os.path.dirname(_utils_dir)
    print(f"扫描目录: {data_dir}")
    cleaned = clean_all_locks(data_dir)
    if cleaned == 0:
        print("无需清理，没有残留锁文件")
