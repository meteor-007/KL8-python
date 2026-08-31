#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KillSeeker (KL8 极致低分杀号与五维反哺决策) - 每日全流程一键分析推演引擎 v3.0 (主系统整合版)
=================================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 核心大白话逻辑：各引擎评分越低 = 越不可能开出 = 坚决排除杀掉。
2. 5大引擎协同：
   - 相似走势匹配 (看图形)
   - 密集区域检测 (找冷门区域)
   - 形态识别 (看形态偏不偏)
   - 曲线分析 (看冷热势头)
   - 马尔可夫链 (找跟班概率)
3. 产出分层：
   - 高置信杀号 10 码 (极力推荐排除)
   - 中置信杀号 10 码
   - 低置信杀号 5 码 (观察区)
   - 共 25 码杀号池 + 8 码安全保留区
4. 反哺交叉校验：对比定金选2、重点点位、LSTM等多维系统进行安全避雷。

用法：
  python run_killseeker_daily.py              # 完整杀号流程 (复盘+预测+交叉反哺)
  python run_killseeker_daily.py --predict    # 仅做预测
  python run_killseeker_daily.py --review     # 仅做复盘
  python run_killseeker_daily.py --diagnose   # 环境预检诊断
  python run_killseeker_daily.py --backtest N # 样本外回测 N 期
"""
import os
import sys
from pathlib import Path

_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ_DIR = _PROJ_DIR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import kill_seeker.main as kill_main

if __name__ == "__main__":
    kill_main.main()
