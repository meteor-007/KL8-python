#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双层LSTM 深度学习全流程独立执行器
=================================
用法: python run_lstm_daily.py [backfill_n=10]
功能: 数据预检 -> 历史无泄露回填 -> 全量双层LSTM训练 -> 目标期预测 -> 近期实测复盘 -> 报告落盘
"""
import os
import sys

_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ = _PROJ_DIR

from models.lstm.lstm_service import LSTMService

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print(f"🚀 启动双层LSTM每日量化推演流程 (回填期数: {n})...")
    res = LSTMService.run_daily_pipeline(backfill_n=n, verbose=True)
    print("✅ 双层LSTM 每日全流程执行完成！")
