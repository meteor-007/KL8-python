# -*- coding: utf-8 -*-
"""随机森林号码预测每日入口"""
import sys
import os

curr = os.path.dirname(os.path.abspath(__file__))
root = curr
while root and os.path.dirname(root) != root:
    if os.path.exists(os.path.join(root, "backend")):
        break
    root = os.path.dirname(root)
if root not in sys.path:
    sys.path.insert(0, root)

from backend.modules.legacy.random_forest.service import run_random_forest_pipeline


def main():
    result = run_random_forest_pipeline()
    print("RF OK", result.get("target_issue"), "top5=", result.get("top3_gold") or result.get("top5_gold"))
    return result


if __name__ == "__main__":
    main()
