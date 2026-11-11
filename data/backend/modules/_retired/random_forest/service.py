# -*- coding: utf-8 -*-
"""随机森林号码预测服务层"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from backend.utils.paths import get_project_root, get_outputs_dir
from backend.utils.history_loader import load_history
from backend.modules._retired.random_forest.random_forest_engine import RandomForestEngine, TRAIN_WINDOW, CACHE_TAG_RF

logger = logging.getLogger("k8quant.random_forest.service")


def get_output_paths() -> Dict[str, str]:
    root = get_project_root()
    reports = os.path.join(get_outputs_dir(), "reports")
    return {
        "storage_json": os.path.join(get_outputs_dir(), "random_forest_latest.json"),
        "frontend_json": os.path.join(root, "frontend", "static", "random_forest_analysis.json"),
        "report_md": os.path.join(reports, "random_forest_report_latest.md"),
    }


def run_random_forest_pipeline(limit: Optional[int] = None) -> Dict[str, Any]:
    load_limit = TRAIN_WINDOW if limit is None else limit
    history = load_history(limit=load_limit)
    if not history:
        raise ValueError("无法加载历史开奖数据")

    engine = RandomForestEngine(history_data=history)
    result = engine.run_prediction()
    if result.get("error"):
        raise ValueError(result["error"])
    result["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    paths = get_output_paths()
    for p in paths.values():
        os.makedirs(os.path.dirname(p), exist_ok=True)

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    with open(paths["storage_json"], "w", encoding="utf-8") as f:
        f.write(payload)
    with open(paths["frontend_json"], "w", encoding="utf-8") as f:
        f.write(payload)

    with open(paths["report_md"], "w", encoding="utf-8") as f:
        f.write(_generate_report(result))

    logger.info(
        "随机森林号码预测完成 target=%s top5=%s",
        result.get("target_issue"),
        result.get("top3_gold") or result.get("top5_gold"),
    )
    return result


def get_latest_random_forest_data() -> Dict[str, Any]:
    paths = get_output_paths()
    if os.path.exists(paths["frontend_json"]):
        try:
            with open(paths["frontend_json"], "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("prediction_mode") == "number_rank_rf" and data.get("train_window") == 100:
                return data
        except Exception as e:
            logger.warning("读取 RF 缓存失败: %s", e)
    return run_random_forest_pipeline()


def get_random_forest_review(n: int = 30, force_refresh: bool = False) -> Dict[str, Any]:
    from backend.modules.common_ai_review import compute_rolling_ai_review
    return compute_rolling_ai_review(
        module_name="random_forest",
        engine_class=RandomForestEngine,
        n=n,
        force_refresh=force_refresh,
        history_buffer=TRAIN_WINDOW,
        cache_tag=CACHE_TAG_RF,
    )


def _generate_report(data: Dict[str, Any]) -> str:
    top3 = " ".join(f"{x:02d}" for x in data.get("top3_gold") or data.get("top5_gold", []))
    imp = data.get("feature_importance") or {}
    imp_str = "、".join(f"{k} {v}%" for k, v in list(imp.items())[:5]) or "无"
    return f"""# 随机森林号码预测 · 第 {data.get('target_issue')} 期

> 近 {data.get('history_used')}/{data.get('train_window')} 期 · 球级 RF 概率排序（无选2）
> 生成时间：{data.get('generated_at')}

## 推荐
- Top3：{top3}

## 特征重要性 Top
{imp_str}
"""
