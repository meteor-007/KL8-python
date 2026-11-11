# -*- coding: utf-8 -*-
"""快乐8 点位+遗漏号深度分析实验舱（kl8_lab）。

原为独立项目《点位+遗漏号分析》（含 13 个方法模块 + 统计检验 + 无前视回测），
2026-09-10 迁移整合进 K8-QUANT 主系统，作为「点位 × 遗漏号」深度分析菜单模块的后端引擎。

定位（迁移后保持不变）：**统计观察工具，不是预测器**。
上游数据只读本仓库根目录的 `daily_points.txt`（点位档案）与 `kl8_history_final.txt`（开奖历史），
产出写入 `outputs/kl8_lab/`，不参与主系统加权推荐链路。

入口：
  · CLI      —— `python -m backend.core.kl8_lab.cli <命令>`（或 `python backend/core/kl8_lab/cli.py`）
  · 服务层   —— `backend.core.kl8_lab.service`（Web 层只读 + 每日任务触发）
  · 每日脚本 —— 仓库根 `run_kl8_lab_daily.py`
"""

__version__ = "2.0.0"

__all__ = ["__version__"]
