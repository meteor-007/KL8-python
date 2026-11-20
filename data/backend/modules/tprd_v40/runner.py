#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TPRD v4.0 模块集成运行器 (Runner)
支持独立执行与被夜间自动流水线调用
"""

import os
import sys
from pathlib import Path

# 解析统一账本路径
_DATA_DIR = Path(__file__).resolve().parents[2]
_HISTORY_PATH = _DATA_DIR / "storage" / "raw" / "kl8_history_final.txt"
_TPRD_ROOT = Path("D:/project/Python-Project/kl8_tprd_system").resolve()

if str(_TPRD_ROOT) not in sys.path:
    sys.path.insert(0, str(_TPRD_ROOT))

from main import run_predict, run_custom_matrix


def run_daily_tprd(backtest_periods: int = 30):
    output_dir = str(_TPRD_ROOT / "output")
    return run_predict(str(_HISTORY_PATH), output_dir=output_dir, backtest_periods=backtest_periods)


if __name__ == "__main__":
    run_daily_tprd()
