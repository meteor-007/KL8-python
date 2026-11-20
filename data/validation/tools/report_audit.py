# -*- coding: utf-8 -*-
"""报告协议检查（对应整改清单 5.1.10）。

每份对外报告必须同时给出：效应量、95%CI、p、样本量 T、MDE、基线、免责声明。
缺任何一项即视为不合格。
"""
from __future__ import annotations

import re
from pathlib import Path

REQUIRED = {
    "effect_size": r"lift|效应量",
    "ci": r"95\s*%|置信区间|\bCI\b",
    "p_value": r"\bp\s*=",
    "sample_size": r"\bT\s*=",
    "mde": r"MDE|最小可检测",
    "baseline": r"随机基准|基线|baseline",
    "disclaimer": r"不构成(任何)?投注建议",
}


def check_text(text: str) -> list[str]:
    return [name for name, pattern in REQUIRED.items()
            if not re.search(pattern, text, re.IGNORECASE)]


def check_file(path: str | Path) -> list[str]:
    return check_text(Path(path).read_text(encoding="utf-8-sig"))


def render(path: str | Path, missing: list[str]) -> str:
    if not missing:
        return f"✓ {path}：协议字段齐全"
    return (f"✗ {path}：缺少 {', '.join(missing)}；"
            f"按整改清单 5.1.10，报告必须同时给出效应量、95%CI、p、T、MDE、基线、免责声明")