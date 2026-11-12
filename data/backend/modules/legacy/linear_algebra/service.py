# -*- coding: utf-8 -*-
"""
线性代数空间投影量化分析服务层 (Linear Algebra Service)
======================================================
【业务背景与架构定位】:
负责协调历史数据加载、核心矩阵计算、分析结果落盘缓存与报告生成。

@author K8-Quant Linear Algebra Team
@since 2026-09-11
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from backend.utils.paths import get_project_root, get_outputs_dir
from backend.utils.history_loader import load_history
from backend.modules.legacy.linear_algebra.linear_algebra_engine import LinearAlgebraEngine

logger = logging.getLogger("k8quant.linear_algebra.service")


def get_output_paths() -> Dict[str, str]:
    """获取标准输出文件路径（活数据统一 storage/，研报在 storage/outputs/reports）。"""
    root = get_project_root()
    reports = os.path.join(get_outputs_dir(), "reports")
    return {
        "storage_json": os.path.join(get_outputs_dir(), "linear_algebra_latest.json"),
        "frontend_json": os.path.join(root, "frontend", "static", "linear_algebra_analysis.json"),
        "report_md": os.path.join(reports, "linear_algebra_report_latest.md"),
    }


def run_linear_algebra_pipeline(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    步骤 1: 加载近窗历史（默认 TRAIN_WINDOW=100）
    步骤 2: 启动线性代数矩阵推演引擎
    步骤 3: 格式化结果并持久化落盘
    步骤 4: 生成操盘手实战大白话研报
    """
    from backend.modules.legacy.linear_algebra.linear_algebra_engine import TRAIN_WINDOW

    logger.info("启动线性代数空间投影全流程流水线（近 %s 期等权）...", TRAIN_WINDOW)
    # 默认只拉近窗；显式 limit 仍可覆盖（引擎内部也会再截断到 TRAIN_WINDOW）
    load_limit = TRAIN_WINDOW if limit is None else limit
    history = load_history(limit=load_limit)
    if not history:
        raise ValueError("无法加载历史开奖数据，请检查 kl8_history_final.txt 文件")

    engine = LinearAlgebraEngine(history_data=history)
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

    report_content = _generate_markdown_report(result)
    with open(paths["report_md"], "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info("线性代数空间投影计算完成，目标期号: %s，使用 %s 期", result.get("target_issue"), result.get("history_used"))
    return result


def get_latest_linear_algebra_data() -> Dict[str, Any]:
    """获取最新的线性代数分析数据，如果不存在则自动触发计算"""
    paths = get_output_paths()
    if os.path.exists(paths["frontend_json"]):
        try:
            with open(paths["frontend_json"], "r", encoding="utf-8") as f:
                data = json.load(f)
            # 旧缓存仍带半衰期/全量口径或非 dual_pick2 时强制重算
            if (
                data.get("weighting") == "equal"
                and data.get("train_window") == 100
                and data.get("prediction_mode") == "dual_pick2_hedge"
            ):
                return data
        except Exception as e:
            logger.warning("读取线性代数缓存失败，重新执行推演: %s", e)

    return run_linear_algebra_pipeline()


def get_linear_algebra_review(n: int = 30, force_refresh: bool = False) -> Dict[str, Any]:
    """获取近 N 期线性代数空间投影 Walk-Forward 样本外滚动对账流水与统计指标"""
    from backend.modules.common_ai_review import compute_rolling_ai_review
    from backend.modules.legacy.linear_algebra.linear_algebra_engine import TRAIN_WINDOW, CACHE_TAG_PICK2
    return compute_rolling_ai_review(
        module_name="linear_algebra",
        engine_class=LinearAlgebraEngine,
        n=n,
        force_refresh=force_refresh,
        history_buffer=TRAIN_WINDOW,
        cache_tag=CACHE_TAG_PICK2,
    )


def _generate_markdown_report(data: Dict[str, Any]) -> str:
    """生成大白话实战操盘研报（主推两组最优选2）"""
    target_issue = data.get("target_issue", "N/A")
    latest_issue = data.get("latest_issue", "N/A")
    top5 = "、".join(f"{x:02d}" for x in data.get("top3_gold") or data.get("top5_gold", []))
    top12 = " ".join(f"{x:02d}" for x in data.get("top3_gold") or data.get("top12_elite", []))
    hist_used = data.get("history_used", data.get("total_historical_draws", 0))
    train_window = data.get("train_window", 100)

    pairs_lines = []
    for p in data.get("gold_pairs", [])[:2]:
        gap_info = ""
        if p.get("gap_a") is not None:
            gap_info = f", 遗漏 {p.get('gap_a')}/{p.get('gap_b')}"
        pairs_lines.append(
            f"- 💎 **第{p.get('rank', '?')}组 {p['pair']}** "
            f"({p.get('desc', '冷热对冲')}; 对子分: {p.get('pair_score', p.get('affinity_score', '-'))}, "
            f"近窗同开: {p.get('cooccur_count', 0)}次{gap_info})"
        )
    pairs_str = "\n".join(pairs_lines) if pairs_lines else "- 暂无"

    matches_lines = []
    for m in data.get("top_historical_matches", [])[:3]:
        overlap_str = "、".join(f"{x:02d}" for x in m.get("overlap_with_top12", [])) or "无"
        matches_lines.append(
            f"- 🧬 **历史第 {m['target_issue']} 期** (切片走势: `{m['period_range']}`, 相似度: **{m['similarity_pct']}%**, 融合权重: {m.get('ensemble_weight', 0)}%)\n"
            f"  - 当年后继开奖: `{' '.join(f'{x:02d}' for x in m['next_numbers'])}`\n"
            f"  - 与当期Top12重合共振: 【{overlap_str}】 (重合 {m.get('overlap_count', 0)} 码)"
        )
    matches_str = "\n".join(matches_lines) if matches_lines else "- 暂无"

    pca_meta = data.get("pca_meta", {})
    cum_var = pca_meta.get("cumulative_variance_ratio", 0.0)

    md = f"""# 📐 第 {target_issue} 期 · 线性代数 · 两组最优选2 操盘研报

> **报告基准**：基于第 {latest_issue} 期最新实开 · **近 {hist_used}/{train_window} 期等权** · 主产品 **两组互不重叠选2**  
> **生成时间**：{data.get('generated_at', '')}  
> **算法模型**：等权 SVD 融合球分 + **动能热胆×遗漏甜区(7~13)冷热对冲** 两组选2

---

### 一、 核心实战推荐（主推选2）

| 战术分类 | 推荐 |
| :--- | :--- |
| 💎 **两组最优选2（主推）** | 见下文专栏 *(共现×融合能量×对称马尔可夫，互不重叠)* |
| 👑 **旁路 Top 5** | **【 {top5} 】** |
| 🛡️ **旁路 Top 12** | `[ {top12} ]` |

---

### 二、 两组最优选2 专栏
{pairs_str}

---

### 三、 历史走势余弦镜像匹配 Top 3
*近 {hist_used} 期内找近5天孪生切片：*

{matches_str}

---

### 四、 SVD 主成分子空间能量解读
- **训练窗**：近 **{train_window}** 期 · 等权
- **实际使用期数**：{hist_used}
- **提取主成分数**：{pca_meta.get('n_components_used', 8)} 维
- **累计方差解释率**：**{cum_var}%**

---
*声明：本报告由 K8-Quant 线性代数引擎自动生成，仅供量化推演参考。*
"""
    return md
