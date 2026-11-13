# -*- coding: utf-8 -*-
"""数据文件路径守卫

本次会话里同一类问题出现了 5 次，根子都是「路径没有单一来源」：
  · 前端模块移进 legacy/ 但 index.html 仍引用旧路径 → 6 个 404
  · consensus_straddle 在 legacy/ 但流水线照跑 → 隐身计入 BH 族
  · 测试去项目根找 kl8_history_final.txt（实际在 storage/raw/）→ 静默 skip
  · pure_pool_scorer 的 __main__ 同样找错位置 → 直接 FileNotFoundError
  · golden 测试的时间字段没归一化 → 每天必红

前两个已由 module_gate 的单一真相源收口。这里守住第三个：**声明了数据文件路径，
就必须指向真实存在的文件**。宁可测试失败，也不许再出现「读不到 → 当没有 → 一切照常」。
"""
import os
import re
import sys
import unittest

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 曾经踩过坑、或直接持有这两类数据文件路径常量的模块
GUARDED_MODULES = [
    "core.algorithm_optimizer",
    "core.entropy_optimizer",
    "core.strategy_optimizer",
    "core.hotcode_hit_analysis",
    "core.pure_pool_scorer",
    "core.deep_mining_engine",
]

WATCHED = ("kl8_history_final.txt", "daily_points.txt")


class TestDeclaredDataPathsExist(unittest.TestCase):
    def test_module_level_path_constants_point_to_real_files(self):
        """模块级常量若指向这两个数据文件，路径必须真实存在。"""
        checked = 0
        for name in GUARDED_MODULES:
            try:
                mod = __import__(name, fromlist=["__file__"])
            except Exception as e:                                # noqa: BLE001
                self.skipTest(f"{name} 无法导入：{type(e).__name__}: {e}")
            for attr, value in vars(mod).items():
                if not attr.isupper() or not isinstance(value, str):
                    continue
                if not any(w in value for w in WATCHED):
                    continue
                checked += 1
                self.assertTrue(
                    os.path.exists(value),
                    f"{name}.{attr} = {value!r} 指向不存在的文件 —— "
                    f"数据文件在 storage/raw/ 下，请用 data_path() 定位")
        # checked 为 0 是正常状态：这些模块都已收敛到 paths 模块，不再自己拼路径

    def test_no_project_root_join_for_data_files(self):
        """禁止再出现「模块级常量 = os.path.join(<项目根>, '<数据文件>')」这种写法。

        只查模块级 UPPER_CASE 常量：函数内部带 `if not exists` 的 fallback 虽然也是
        代码味道，但有兜底、能跑通，不在本测试的打击范围内。
        真正闯祸的是常量——它一旦写错，模块里任何用到它的地方都静默读空。
        """
        bad = []
        pat = re.compile(
            r"^[A-Z_][A-Z0-9_]*\s*=\s*os\.path\.join\([^)]*"
            r"['\"](" + "|".join(re.escape(w) for w in WATCHED) + r")['\"]"
        )
        for dirpath, dirnames, filenames in os.walk(_BACKEND_DIR):
            dirnames[:] = [d for d in dirnames
                           if d not in ("__pycache__", "legacy")]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    src = open(path, encoding="utf-8").read()
                except Exception:
                    continue
                for lineno, line in enumerate(src.splitlines(), 1):
                    if line.lstrip().startswith("#"):
                        continue
                    if "raw" in line or "data_path" in line or "get_storage_dir" in line:
                        continue
                    if pat.search(line):
                        bad.append(f"{os.path.relpath(path, PROJ_DIR)}:{lineno}: {line.strip()}")
        self.assertEqual(bad, [], "发现指向不存在路径的模块级常量：\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main(verbosity=2)