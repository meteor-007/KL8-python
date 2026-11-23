# -*- coding: utf-8 -*-
"""统一缓存工具：文件指纹失效 + 进程内记忆化 + 可选 TTL。

背景：项目里各模块此前手写缓存（key 策略不一：mtime、(n, period)、
文件签名……），既难复用又容易漏失效。这里提供统一原语：

- file_fingerprint(path)      → (绝对路径, mtime_ns, 大小)，文件被替换即变
- glob_fingerprint(patterns) → 目录型签名（每个匹配文件的 basename+mtime+size）
- memoize(key_fn, ttl=0)      → 装饰器：按 key_fn(*args, **kwargs) 缓存结果

约定：
- ttl=0 表示「只按 key 失效」，适合文件型数据（key 用文件指纹）；
- ttl>0 表示额外按时间过期，适合重计算但数据变化不频繁的场景；
- 缓存都是进程内的；当前服务为单进程部署，无需分布式缓存；
- 缓存对象按只读共享对待，调用方不得原地修改返回值。
"""
from __future__ import annotations

import glob
import os
import threading
import time
import functools
from typing import Any, Callable, Dict, Tuple


def file_fingerprint(path: str) -> Tuple[str, int, int]:
    """单文件指纹：绝对路径 + mtime_ns + 大小。"""
    st = os.stat(path)
    return (os.path.abspath(path), st.st_mtime_ns, st.st_size)


def glob_fingerprint(patterns) -> Tuple[Tuple[str, int, int], ...]:
    """目录/通配型指纹：每个匹配文件的 (basename, mtime_ns, size) 排序元组。

    新文件出现、旧文件被改/删都会改变签名。
    """
    sig = []
    for pat in patterns:
        for fp in glob.glob(pat):
            st = os.stat(fp)
            sig.append((os.path.basename(fp), st.st_mtime_ns, st.st_size))
    return tuple(sorted(sig))


def memoize(key_fn: Callable[..., Any], *, ttl: float = 0.0):
    """按 key_fn 缓存函数结果。

    用法：
        @memoize(lambda path: file_fingerprint(path))
        def parse_file(path): ...

        @memoize(lambda n: n, ttl=300)
        def heavy_compute(n): ...
    key_fn 抛异常（如文件不存在）时直接透传，不缓存。
    """
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        store: Dict[Any, Tuple[float, Any]] = {}
        locks: Dict[Any, threading.Lock] = {}
        lock = threading.Lock()

        def _expired(hit: Tuple[float, Any]) -> bool:
            return ttl > 0 and (time.time() - hit[0]) >= ttl

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            with lock:
                hit = store.get(key)
                if hit is not None and not _expired(hit):
                    return hit[1]
                klock = locks.setdefault(key, threading.Lock())
            # 单飞：同一 key 只允许一个线程计算，其余线程等待后复用结果
            # （避免启动预热与首个请求并发重复解析同一份文件）
            with klock:
                with lock:
                    hit = store.get(key)
                    if hit is not None and not _expired(hit):
                        return hit[1]
                val = fn(*args, **kwargs)
                with lock:
                    store[key] = (time.time(), val)
                return val

        wrapper.cache_clear = lambda: store.clear()  # 便于测试/运维
        return wrapper
    return deco
