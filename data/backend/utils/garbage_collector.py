# -*- coding: utf-8 -*-
"""
垃圾回收与自动化收容模块 (Garbage Collector)
===========================================
清理过期的锁文件、过期的备份文件，并对旧数据进行冷归档收容。
"""
import os
import sys
import glob
import time
import shutil
import logging

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ============================================================================
#  配置与常量
# ============================================================================
import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] GC: %(message)s')
logger = logging.getLogger("GarbageCollector")

HOT_DIR = data_path('热码统计')
BACKUP_HOT_DIR = data_path('backup', 'hot_numbers')

# 时间阈值 (秒)
HOT_EXPIRE_SECONDS = 7 * 24 * 3600  # 7天
BAK_EXPIRE_SECONDS = 3 * 24 * 3600  # 3天


def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def clean_excel_locks():
    """彻底清除所有遗留的 .excel_lock 僵尸锁"""
    logger.info("开始扫描全局 .excel_lock 僵尸文件...")
    locks = glob.glob(os.path.join(_PROJ, '*.excel_lock'))
    cleaned = 0
    for lock in locks:
        try:
            os.remove(lock)
            cleaned += 1
            logger.info(f"  [删除] 已粉碎僵尸锁: {os.path.basename(lock)}")
        except Exception as e:
            logger.warning(f"  [失败] 无法删除锁 {lock}: {e}")
    if cleaned == 0:
        logger.info("  未发现僵尸锁。")
    return cleaned


def archive_old_hot_numbers():
    """将超过 7 天的热码统计文件移动到 backup/hot_numbers/"""
    logger.info("开始扫描老旧热码统计文件进行归档...")
    _ensure_dir(BACKUP_HOT_DIR)
    
    files = glob.glob(os.path.join(HOT_DIR, '*-热码统计.xlsx'))
    now = time.time()
    archived = 0
    for f in files:
        mtime = os.path.getmtime(f)
        if now - mtime > HOT_EXPIRE_SECONDS:
            basename = os.path.basename(f)
            dest = os.path.join(BACKUP_HOT_DIR, basename)
            try:
                shutil.move(f, dest)
                archived += 1
                logger.info(f"  [归档] 已移动到冷库: {basename}")
            except Exception as e:
                logger.warning(f"  [失败] 无法归档 {basename}: {e}")
                
    if archived == 0:
        logger.info("  未发现需要归档的老旧热码文件。")
    return archived


def clean_old_bak_files():
    """删除超过 3 天的多余 .bak 备份文件"""
    logger.info("开始扫描冗余的 Excel 备份文件 (.bak)...")
    baks = glob.glob(os.path.join(_PROJ, '*.bak_*'))
    now = time.time()
    cleaned = 0
    for f in baks:
        mtime = os.path.getmtime(f)
        if now - mtime > BAK_EXPIRE_SECONDS:
            basename = os.path.basename(f)
            try:
                os.remove(f)
                cleaned += 1
                logger.info(f"  [删除] 已粉碎过期备份: {basename}")
            except Exception as e:
                logger.warning(f"  [失败] 无法删除备份 {basename}: {e}")
                
    if cleaned == 0:
        logger.info("  未发现过期的冗余备份文件。")
    return cleaned


def run_garbage_collection():
    print("=" * 60)
    print(" 🗑️ 启动全局垃圾回收管线 (Garbage Collector)")
    print("=" * 60)
    
    c1 = clean_excel_locks()
    c2 = clean_old_bak_files()
    c3 = archive_old_hot_numbers()
    
    print("-" * 60)
    logger.info(f"执行完毕! 共删除锁 {c1} 个, 删除过期备份 {c2} 个, 归档冷热码 {c3} 份。")
    print("=" * 60)


if __name__ == '__main__':
    run_garbage_collection()
