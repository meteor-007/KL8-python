#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""残差改错预测模块每日运行脚本"""
import logging
import os
import sys

_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from backend.modules.error_correction.service import run_error_correction_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> None:
    try:
        result = run_error_correction_pipeline()
        top5_str = " ".join(f"{x:02d}" for x in result.get("top3_gold") or result.get("top5_gold", []))
        print(f"\n[OK] 残差改错推演完成 | 目标期: {result.get('target_issue')} | Top5 金胆: {top5_str}")
    except Exception as e:
        print(f"\n[ERROR] 残差改错推演失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
