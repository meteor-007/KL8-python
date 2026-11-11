# -*- coding: utf-8 -*-
"""前瞻账现算水位工具 (Ledger-backed honesty helper)
=====================================================================
大白话: 各模块研报里长期写死"40% 胜率""13.33% 底蕴"这类数字, 既没有当期依据, 也
无法复核。本工具从前瞻账 storage/cache/paper_trading_modules.jsonl 现算某模块的
真实命中率与 Lift, 供研报署名, 做到"报告里出现的数字都能查到出处"。
"""
from __future__ import annotations

import os
import json
from typing import Optional

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER_FILE = os.path.join(_PROJ_DIR, "storage", "cache", "paper_trading_modules.jsonl")
BASELINE = 0.25


def ledger_stat_label(module_id: str, baseline: float = BASELINE) -> str:
    """返回该模块的前瞻账实测水位描述; 无记录时如实标注未证实。"""
    if not os.path.exists(LEDGER_FILE):
        return "`前瞻账无记录（该口径未证实）`"
    picks = hits = periods = 0
    try:
        with open(LEDGER_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("module") != module_id or r.get("hits") is None or not r.get("picks"):
                    continue
                periods += 1
                picks += len(r["picks"])
                hits += r["hits"]
    except OSError:
        return "`前瞻账读取失败`"
    if not picks:
        return "`前瞻账无记录（该口径未证实）`"
    rate = hits / picks
    lift = rate / baseline if baseline else 0.0
    note = "样本不足未显著" if periods < 200 else "未做显著性复核"
    return f"近 {periods} 期前瞻账实测 {rate * 100:.1f}%（Lift {lift:.2f}x，{note}）"


def ledger_pair_rate(module_id: str) -> Optional[float]:
    """前瞻账里该模块的选2双全中率 (无记录返回 None)。"""
    label = ledger_stat_label(module_id)
    if "实测" not in label:
        return None
    try:
        return float(label.split("实测 ")[1].split("%")[0]) / 100.0
    except (IndexError, ValueError):
        return None