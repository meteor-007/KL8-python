# -*- coding: utf-8 -*-
"""导入别名：把顶层 core / utils / modules 映射到 backend.*。

背景（架构审计发现）：项目同时把 data/ 与 data/backend/ 注入 sys.path，
代码里因此并存两种写法：
    from core.module_gate import ...      # 模块对象 A
    from backend.core.module_gate import ...  # 模块对象 B（同一文件）
同一个文件被加载成两个模块对象，导致模块级缓存、全局注册表状态分裂
（典型：ModuleGate 注册表两份、history_loader 缓存两份）。

做法：注册一个 meta_path 查找器，把所有 `core.* / utils.* / modules.*`
的导入重定向到 `backend.core.* / backend.utils.* / backend.modules.*`，
并复用同一模块对象。data/ 下并不存在同名的 core/utils/modules 包，
所以重定向不会遮蔽任何真实顶层包。

在 backend/__init__.py 中最先安装，保证后续任何 `from core.xxx import ...`
都与 `backend.core.xxx` 共享同一对象。
"""
from __future__ import annotations

import sys
import importlib
import importlib.abc
from importlib.machinery import ModuleSpec

_ALIAS_ROOTS = {
    "core": "backend.core",
    "utils": "backend.utils",
    "modules": "backend.modules",
}


class _AliasLoader(importlib.abc.Loader):
    """把已导入的目标模块直接作为 create_module 的返回值（不再执行代码）。"""

    def __init__(self, mod):
        self._mod = mod

    def create_module(self, spec):
        return self._mod

    def exec_module(self, module):
        pass


class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root, _, rest = fullname.partition(".")
        if root not in _ALIAS_ROOTS:
            return None
        target_name = _ALIAS_ROOTS[root] + ("." + rest if rest else "")
        try:
            mod = importlib.import_module(target_name)
        except Exception:
            return None
        # 不预置 sys.modules：由导入系统通过 create_module 的返回值注册，
        # 保证 fullname 与 target_name 指向同一模块对象。
        return ModuleSpec(fullname, _AliasLoader(mod), is_package=hasattr(mod, "__path__"))


def install() -> None:
    if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _AliasFinder())


install()
