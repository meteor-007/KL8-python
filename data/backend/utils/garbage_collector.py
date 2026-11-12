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
from utils.paths import get_project_root, data_path, get_logs_dir, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()

# 根 logs/ 迁移到 storage/logs 时，最近 N 秒内仍在写入的文件跳过（避免截断活跃日志）
_LOG_ACTIVE_WINDOW_SEC = 120
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] GC: %(message)s')
logger = logging.getLogger("GarbageCollector")

HOT_DIR = data_path('热码统计')
BACKUP_HOT_DIR = data_path('backup', 'hot_numbers')

# 时间阈值 (秒)
HOT_EXPIRE_SECONDS = 7 * 24 * 3600  # 7天
BAK_EXPIRE_SECONDS = 3 * 24 * 3600  # 3天

# 根目录误生成物（正式活数据在 storage/）
ROOT_CLUTTER_NAMES = (
    'output',
    'outputs',
    'reports',
    'kl8_012_roads_summary.csv',
    'kl8_prime_composite_summary.csv',
)


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


def clean_root_clutter():
    """清扫根目录误生成的 output/outputs/reports 与汇总 CSV，归入 storage。"""
    from utils.paths import get_stats_dir, get_outputs_dir, get_reports_dir

    logger.info("开始清扫根目录误生成物...")
    cleaned = 0
    stats_dir = get_stats_dir()
    outputs_dir = get_outputs_dir()
    reports_dir = get_reports_dir()

    def _merge_tree(src: str, dst: str):
        nonlocal cleaned
        if not os.path.exists(src):
            return
        os.makedirs(dst, exist_ok=True)
        for name in os.listdir(src):
            s = os.path.join(src, name)
            d = os.path.join(dst, name)
            try:
                if os.path.isdir(s):
                    _merge_tree(s, d)
                    if os.path.isdir(s) and not os.listdir(s):
                        os.rmdir(s)
                else:
                    if (not os.path.exists(d)) or (os.path.getmtime(s) >= os.path.getmtime(d)):
                        shutil.copy2(s, d)
                    os.remove(s)
                    cleaned += 1
            except OSError as e:
                logger.warning(f"  [跳过] {s}: {e}")

    # CSV → storage/stats
    for name in ('kl8_012_roads_summary.csv', 'kl8_prime_composite_summary.csv'):
        src = os.path.join(_PROJ, name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(stats_dir, name)
        try:
            shutil.copy2(src, dst)
            os.remove(src)
            cleaned += 1
            logger.info(f"  [归位] {name} -> storage/stats/")
        except OSError as e:
            # 被 WPS 等占用时写入 .latest，根文件留给下次再删
            try:
                latest = dst + '.latest'
                shutil.copy2(src, latest)
                logger.warning(f"  [占用] {name} 无法删除，已备份到 {os.path.basename(latest)}: {e}")
            except OSError as e2:
                logger.warning(f"  [失败] {name}: {e2}")

    mapping = {
        'output': os.path.join(outputs_dir, 'point_omission'),
        'outputs': outputs_dir,
        'reports': reports_dir,
    }
    for name, dest in mapping.items():
        src = os.path.join(_PROJ, name)
        if not os.path.exists(src):
            continue
        _merge_tree(src, dest)
        try:
            if os.path.isdir(src) and not os.listdir(src):
                os.rmdir(src)
                logger.info(f"  [移除] 空目录 {name}/")
            elif os.path.isdir(src):
                shutil.rmtree(src, ignore_errors=True)
                if not os.path.exists(src):
                    logger.info(f"  [移除] {name}/")
        except OSError as e:
            logger.warning(f"  [失败] 无法移除 {name}/: {e}")

    # 根 logs 内容迁到 storage/logs（目录本身可保留为空，gitignore 已忽略）
    root_logs = os.path.join(_PROJ, 'logs')
    storage_logs = get_logs_dir()
    if os.path.isdir(root_logs):
        for name in os.listdir(root_logs):
            s = os.path.join(root_logs, name)
            if not os.path.isfile(s):
                continue
            # 正在写入的日志不能搬：copy + remove 会让写入方的文件句柄失效，
            # 后半段输出直接丢失（流水线跑到一半日志被截断就是这么来的）。
            try:
                if time.time() - os.path.getmtime(s) < _LOG_ACTIVE_WINDOW_SEC:
                    logger.info(f"  [活跃] logs/{name} 最近仍在写入，跳过迁移")
                    continue
            except OSError:
                continue
            d = os.path.join(storage_logs, name)
            try:
                if (not os.path.exists(d)) or (os.path.getmtime(s) >= os.path.getmtime(d)):
                    shutil.copy2(s, d)
                os.remove(s)
                cleaned += 1
                logger.info(f"  [归位] logs/{name} -> storage/logs/")
            except OSError as e:
                logger.warning(f"  [跳过] logs/{name}: {e}")

    if cleaned == 0:
        logger.info("  根目录无误生成物需要清扫。")
    return cleaned


def run_garbage_collection():
    print("=" * 60)
    print(" 🗑️ 启动全局垃圾回收管线 (Garbage Collector)")
    print("=" * 60)
    
    c1 = clean_excel_locks()
    c2 = clean_old_bak_files()
    c3 = archive_old_hot_numbers()
    c4 = clean_root_clutter()
    
    print("-" * 60)
    logger.info(
        f"执行完毕! 共删除锁 {c1} 个, 删除过期备份 {c2} 个, "
        f"归档冷热码 {c3} 份, 根目录归位 {c4} 项。"
    )
    print("=" * 60)


if __name__ == '__main__':
    run_garbage_collection()
