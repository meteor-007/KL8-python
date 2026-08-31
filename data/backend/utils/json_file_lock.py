# -*- coding: utf-8 -*-
"""
JSON文件锁工具 v1.0：防止多进程并发读写共享JSON文件
====================================================
复用 excel_lock.py 的可重入锁架构，适配JSON场景。

用法:
    with json_file_lock(json_path):
        data = json.load(open(json_path))
        data['new_key'] = 'new_value'
        json.dump(data, open(json_path, 'w'))

    # 可重入：同一进程可嵌套
    with json_file_lock(path):
        with json_file_lock(path):  # 不死锁
            ...
"""
import os
import sys
import time
import uuid
import atexit
import logging
import threading
from contextlib import contextmanager

_IS_WINDOWS = os.name == 'nt'
logger = logging.getLogger("JsonFileLock")

# ── 全局注册表 & 活跃锁表 ──
_LOCK_REGISTRY = []
_ACTIVE_LOCKS = {}
_ACTIVE_LOCKS_MUTEX = threading.Lock()


def _cleanup_all_locks():
    """进程退出时清理所有残留锁文件"""
    for lock_path, lock_id in _LOCK_REGISTRY:
        try:
            if os.path.exists(lock_path):
                with open(lock_path, 'r') as f:
                    if f.read().strip() == lock_id:
                        os.remove(lock_path)
        except Exception:
            pass


atexit.register(_cleanup_all_locks)


@contextmanager
def json_file_lock(file_path: str, timeout: float = 30.0, stale_seconds: float = 60.0):
    """
    JSON文件的可重入锁上下文管理器
    
    Args:
        file_path: 要保护的JSON文件路径
        timeout: 获取锁的超时时间(秒)
        stale_seconds: 锁文件超过此时间视为过期(秒)
    
    Yields:
        lock_path: 锁文件路径
    """
    lock_path = file_path + ".json_lock"
    lock_id = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
    
    # ── 检查可重入 ──
    with _ACTIVE_LOCKS_MUTEX:
        if lock_path in _ACTIVE_LOCKS:
            if lock_id not in _ACTIVE_LOCKS[lock_path]:
                # 同进程但不同lock_id，也允许重入
                pass
            _ACTIVE_LOCKS[lock_path][lock_id] = _ACTIVE_LOCKS[lock_path].get(lock_id, 0) + 1
            yield lock_path
            _ACTIVE_LOCKS[lock_path][lock_id] -= 1
            if _ACTIVE_LOCKS[lock_path][lock_id] <= 0:
                del _ACTIVE_LOCKS[lock_path][lock_id]
                if not _ACTIVE_LOCKS[lock_path]:
                    del _ACTIVE_LOCKS[lock_path]
            return
    
    # ── 首次获取锁 ──
    deadline = time.time() + timeout
    
    while time.time() < deadline:
        # 检查stale锁
        if os.path.exists(lock_path):
            try:
                mtime = os.path.getmtime(lock_path)
                if time.time() - mtime > stale_seconds:
                    logger.warning(f"清理过期锁: {lock_path} (age={time.time()-mtime:.0f}s)")
                    os.remove(lock_path)
            except FileNotFoundError:
                pass
        
        # 尝试创建锁 (原子 O_CREAT|O_EXCL, 避免先 exists 再 open 的 TOCTOU)
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, lock_id.encode())
            finally:
                os.close(fd)
            break
        except (FileExistsError, OSError):
            pass
        
        time.sleep(0.1)
    else:
        raise TimeoutError(f"获取文件锁超时({timeout}s): {lock_path}")
    
    # 注册锁
    _LOCK_REGISTRY.append((lock_path, lock_id))
    with _ACTIVE_LOCKS_MUTEX:
        _ACTIVE_LOCKS[lock_path] = _ACTIVE_LOCKS.get(lock_path, {})
        _ACTIVE_LOCKS[lock_path][lock_id] = 1
    
    try:
        yield lock_path
    finally:
        # 释放锁
        with _ACTIVE_LOCKS_MUTEX:
            if lock_path in _ACTIVE_LOCKS and lock_id in _ACTIVE_LOCKS[lock_path]:
                _ACTIVE_LOCKS[lock_path][lock_id] -= 1
                if _ACTIVE_LOCKS[lock_path][lock_id] <= 0:
                    del _ACTIVE_LOCKS[lock_path][lock_id]
                    if not _ACTIVE_LOCKS[lock_path]:
                        del _ACTIVE_LOCKS[lock_path]
        
        # Windows 上读后删可能被索引器占用；直接按本进程 lock_id 重试删除即可
        for _attempt in range(3):
            try:
                if not os.path.exists(lock_path):
                    break
                owned = False
                try:
                    with open(lock_path, 'r') as f:
                        owned = (f.read().strip() == lock_id)
                except OSError:
                    owned = True  # 无法读取时仍尝试清理本进程锁
                if owned:
                    os.remove(lock_path)
                break
            except OSError:
                time.sleep(0.05)
        else:
            try:
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            except OSError:
                pass
        
        try:
            _LOCK_REGISTRY.remove((lock_path, lock_id))
        except ValueError:
            pass
