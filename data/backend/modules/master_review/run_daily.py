#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_master_review_daily.py — 快乐8 全模块多维实战命中复盘总决算执行器
====================================================================
用法: python run_master_review_daily.py [30]
"""
import os
import sys

# 路径自适应 (模块迁入 backend/modules 后：向上定位项目根)
def _find_project_root(start: str) -> str:
    curr = start
    for _ in range(8):
        if os.path.isdir(os.path.join(curr, "backend")) and os.path.isdir(os.path.join(curr, "frontend")):
            return curr
        if os.path.exists(os.path.join(curr, "GEMINI.md")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return start

_PROJ_DIR = _find_project_root(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ_DIR = _PROJ_DIR


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.master_reviewer import MasterReviewEngine, print_master_review_table


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30
    engine = MasterReviewEngine(_PROJ_DIR)
    res = engine.run_master_review(n_review=n)
    print_master_review_table(res)


if __name__ == "__main__":
    main()
