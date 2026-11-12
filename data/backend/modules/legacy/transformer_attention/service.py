# -*- coding: utf-8 -*-
"""Transformer Attention Service Layer"""
import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from backend.utils.paths import get_project_root, get_outputs_dir
from backend.utils.history_loader import load_history
from backend.modules.legacy.transformer_attention.transformer_engine import TransformerAttentionEngine

logger = logging.getLogger("k8quant.transformer.service")


def get_output_paths() -> Dict[str, str]:
    root = get_project_root()
    return {
        "storage_json": os.path.join(get_outputs_dir(), "transformer_latest.json"),
        "frontend_json": os.path.join(root, "frontend", "static", "transformer_analysis.json"),
        "report_md": os.path.join(get_outputs_dir(), "reports", "transformer_report_latest.md"),
    }


def run_transformer_pipeline(limit: Optional[int] = None) -> Dict[str, Any]:
    history = load_history(limit=limit)
    if not history:
        raise ValueError("无法加载历史开奖数据")

    engine = TransformerAttentionEngine(history_data=history)
    result = engine.run_prediction()
    result["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    paths = get_output_paths()
    for p in paths.values():
        os.makedirs(os.path.dirname(p), exist_ok=True)

    json_str = json.dumps(result, ensure_ascii=False, indent=2)
    with open(paths["storage_json"], "w", encoding="utf-8") as f:
        f.write(json_str)
    with open(paths["frontend_json"], "w", encoding="utf-8") as f:
        f.write(json_str)

    return result


def get_latest_transformer_data() -> Dict[str, Any]:
    paths = get_output_paths()
    if os.path.exists(paths["frontend_json"]):
        try:
            with open(paths["frontend_json"], "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return run_transformer_pipeline()


def get_transformer_review(n: int = 30, force_refresh: bool = False) -> Dict[str, Any]:
    """获取近 N 期 Transformer 全局时序自注意力 Walk-Forward 样本外滚动对账流水与统计指标"""
    from backend.modules.common_ai_review import compute_rolling_ai_review
    return compute_rolling_ai_review(
        module_name="transformer_attention",
        engine_class=TransformerAttentionEngine,
        n=n,
        force_refresh=force_refresh
    )

