# -*- coding: utf-8 -*-
"""
残差改错预测服务层 (Residual Error-Correction Service)
======================================================
【业务背景与架构定位】:
统一承接残差改错预测管道调度、推演数据持久化、Web前端大屏报表同步，
以及基于 Walk-Forward 的逐期滚动样本外实战对账能力。

@author K8-Quant Error Correction Team
@since 2026-09-15
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from backend.utils.paths import get_project_root, get_outputs_dir
from backend.utils.history_loader import load_history
from backend.modules.error_correction.residual_engine import (
    ResidualCorrectionEngine,
    TRAIN_WINDOW,
    CACHE_TAG_EC,
)

logger = logging.getLogger("k8quant.error_correction.service")


def get_output_paths() -> Dict[str, str]:
    """获取残差改错模块标准输出路径字典"""
    root = get_project_root()
    reports = os.path.join(get_outputs_dir(), "reports")
    return {
        "storage_json": os.path.join(get_outputs_dir(), "error_correction_latest.json"),
        "frontend_json": os.path.join(root, "frontend", "static", "error_correction_analysis.json"),
        "report_md": os.path.join(reports, "error_correction_report_latest.md"),
    }


def run_error_correction_pipeline(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    一键运行残差改错预测全流程
    @param limit 加载历史样本期数 (默认 TRAIN_WINDOW=100)
    @return Dict 完整预测与诊断分析字典
    """
    load_limit = TRAIN_WINDOW if limit is None else limit
    history = load_history(limit=load_limit)
    if not history:
        raise ValueError("无法加载历史开奖数据，请检查开奖源文件！")

    engine = ResidualCorrectionEngine(history_data=history)
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
        "残差改错预测完成 target=%s top5=%s 拔除雷号=%d 提拔黑马=%d",
        result.get("target_issue"),
        result.get("top3_gold") or result.get("top5_gold"),
        len(result.get("traps_avoided", [])),
        len(result.get("rebounds_promoted", [])),
    )
    return result


def get_latest_error_correction_data() -> Dict[str, Any]:
    """读取最近一次残差改错预测结果，若无有效缓存则即时推演"""
    paths = get_output_paths()
    if os.path.exists(paths["frontend_json"]):
        try:
            with open(paths["frontend_json"], "r", encoding="utf-8") as f:
                data = json.load(f)
            if (
                data.get("prediction_mode") == "residual_boosting_gbdt"
                and data.get("train_window") == TRAIN_WINDOW
            ):
                return data
        except Exception as e:
            logger.warning("读取残差改错前端缓存失败，触发即时推演: %s", e)
    return run_error_correction_pipeline()


def get_error_correction_review(n: int = 30, force_refresh: bool = False) -> Dict[str, Any]:
    """
    基于 Walk-Forward 的严格无未来函数逐期滚动实战对账
    接入系统顶级 common_ai_review 引擎
    """
    from backend.modules.common_ai_review import compute_rolling_ai_review
    return compute_rolling_ai_review(
        module_name="error_correction",
        engine_class=ResidualCorrectionEngine,
        n=n,
        force_refresh=force_refresh,
        history_buffer=TRAIN_WINDOW,
        cache_tag=CACHE_TAG_EC,
    )


def _generate_report(data: Dict[str, Any]) -> str:
    """生成大白话实战对账与纠偏研报 Markdown"""
    top3 = " ".join(f"{x:02d}" for x in data.get("top3_gold") or data.get("top5_gold", []))

    # 拔除雷号与提拔黑马
    traps = data.get("traps_avoided", [])
    if traps:
        traps_md = "\n".join(
            f"- 🚨 **号码 {t['ball_str']}**：基准得分 {t['base_score']} 分，改错裁判严厉扣除 **{abs(t['residual_penalty'])}** 分（{t['reason']}）"
            for t in traps[:5]
        )
    else:
        traps_md = "- 暂无显著虚火诱多雷号（各高分码势头平稳）"

    rebounds = data.get("rebounds_promoted", [])
    if rebounds:
        rebounds_md = "\n".join(
            f"- 🚀 **号码 {r['ball_str']}**：基准仅 {r['base_score']} 分，改错裁判强力补给 **+{r['residual_bonus']}** 分（{r['reason']}）"
            for r in rebounds[:5]
        )
    else:
        rebounds_md = "- 暂无极端回补爆冷黑马（无超长遗漏逼近极值）"

    # 黄金选2
    pairs = data.get("gold_pairs", [])
    if pairs:
        pair_str = f"**{pairs[0].get('pair')}**（共现亲和度分值：{pairs[0].get('co_score', 0):.0f}，{pairs[0].get('desc')}）"
    else:
        pair_str = "无"

    # 特征重要性
    imp = data.get("feature_importance") or {}
    feature_name_map = {
        "base_score": "底仓基准分（看前人判断）",
        "gap": "当前遗漏（看冷热空窗）",
        "gap_ratio": "弹簧压制比（看憋了多久）",
        "freq_recent_20": "近20期出号频次",
        "freq_short_5": "近5期短线热度",
        "momentum_slope": "动能冷热势头（看是加速还是跳水）",
        "in_last": "上期开出与否（看是否连开）",
        "consecutive_streak": "连击数（连续开出或连续落空）",
        "zone_density": "区间拥挤度（看是不是扎堆打架）",
        "co_affinity": "共现亲和力（看跟班走势）",
        "road": "012路特征",
        "is_prime": "质数特征",
        "ball_id": "球号自身编号",
    }
    imp_lines = []
    for k, v in list(imp.items())[:6]:
        cn_k = feature_name_map.get(k, k)
        imp_lines.append(f"- **{cn_k}**: 权重贡献 **{v}%**")
    imp_str = "\n".join(imp_lines) if imp_lines else "- 默认平滑先验"

    return f"""# 🧬 残差改错预测研报 · 第 {data.get('target_issue')} 期
> **模型算法**：LightGBM 残差梯度提升回归树（大白话：专攻错题本的 AI 改错裁判）  
> **核心定位**：第一棒由基准底仓模型打底，第二棒由 LightGBM 死磕历史错题，负责“抓内鬼”和“提黑马”。  
> **推演样本**：近 {data.get('history_used')}/{data.get('train_window')} 期实战对账 | 纠偏调节步长 $\\lambda = {data.get('correction_lambda', 0.35)}$  
> **生成时间**：{data.get('generated_at')}  

---

## 一、 核心终审成果
* 💎 **纠偏金胆 Top3**：`{top3}`
* 🎯 **改错黄金选2搭档**：{pair_str}

---

## 二、 错题纠偏风控实录（抓内鬼 vs 提黑马）

### 🚨 1. 拔除虚火诱多雷号（大白话：推荐爆雷/假信号避坑）
{traps_md}

### 🚀 2. 提拔极限回补黑马（大白话：大冷门破冰抓反弹）
{rebounds_md}

---

## 三、 改错树特征重要性榜单（大白话：改错裁判看谁最管用）
{imp_str}

---
*注：本模块完全遵循严格无未来函数的时间序列 Walk-Forward 推进准则，全参数受物理熔断（大白话：紧急刹车）与残差步长守卫，坚决防学过头（防过拟合）。*
"""
